"""Macht der Ausblick die Prognose nach Quartalszahlen genauer? Rekonstruktion für vergangene Berichte und Test.

Anlass: Intel 29.10.2026 – Gewinn +30 % über Erwartung, Ausblick gesenkt, Aktie −28 %; die App zeigte 64 % „steigt“, weil sie
nur die Gewinn-Überraschung kannte. Hier wird für jeden Quartalsbericht der größten US-Aktien seit 2023 die Richtung des
Ausblicks aus den Schlagzeilen der Tage danach rekonstruiert (gleiche Erkennung wie die App: backend.earnings.guidance) und
geprüft, ob Gewinn + Ausblick die Richtung am Tag danach besser treffen als der Gewinn allein.

Ausblick-Erkennung: Stand nach der Korrektur vom 30.10.2026 (Ratingagenturen, Analysten, Konjunktur, fremde Firmen und
Quellen-Namen zählen nicht mehr).

Vorab festgelegt (vor dem ersten Lauf):
- Lernzeitraum: Berichte bis 31.03.2025; Prüfzeitraum: ab 01.04.2025 (zeitlich getrennt, nichts aus der Prüfzeit fließt ein).
- M0 = heutige App (Quote je Gewinn-Stufe). M1 = Quote je Gewinn-Stufe × Ausblick (gesenkt / bestätigt / angehoben / keine
  Meldung), zur Gewinn-Stufe hin geglättet (20 Pseudo-Berichte). M2 = M1 + eigene Vorgeschichte der Aktie (Anteil gestiegener
  Reaktionen der letzten 8 Berichte, nur Vergangenheit), ebenfalls geglättet.
- Maß: Brier-Score (mittlerer quadratischer Fehler der Wahrscheinlichkeit) und Trefferquote in der Prüfzeit; Block-Bootstrap
  über Monate für den Unterschied. Übernommen wird ein Modell nur, wenn es in der Prüfzeit besser ist und das 95-%-Intervall
  des Brier-Unterschieds die Null nicht enthält.

    python tools/research/earn_guide.py collect <universe_us.csv> <out.csv> --shard K --shards N [--max 600]
    python tools/research/earn_guide.py analyze <ordner mit csv> <out_dir>
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend import earnings as E  # noqa: E402

BUCKETS = [(-1e9, -10, "deutlich unter Erwartung"), (-10, -2, "unter Erwartung"), (-2, 2, "im Rahmen"),
           (2, 10, "über Erwartung"), (10, 1e9, "deutlich über Erwartung")]
SINCE = pd.Timestamp("2023-01-01")
SPLIT = pd.Timestamp("2025-04-01")
K_SMOOTH = 20


def bucket(s: float) -> int:
    return next(i for i, (lo, hi, _) in enumerate(BUCKETS) if lo <= s < hi)


def collect(uni_csv: str, out_csv: str, shard: int, shards: int, n_max: int) -> None:
    import yfinance as yf
    uni = pd.read_csv(uni_csv)
    uni = uni[~uni["ticker"].astype(str).str.contains(r"\.")].sort_values("market_cap_usd", ascending=False).head(n_max)
    uni = uni.iloc[shard::shards]
    names = dict(zip(uni["ticker"], uni["name"] if "name" in uni else uni["ticker"]))
    tks = list(uni["ticker"])
    px = yf.download(tks, period="5y", interval="1d", auto_adjust=True, progress=False, group_by="ticker", threads=True)
    rows, nq = [], 0
    for tk in tks:
        try:
            c = px[tk]["Close"].dropna()
            ed = yf.Ticker(tk).get_earnings_dates(limit=20)
        except Exception as exc:
            print(f"{tk}: {exc!r}")
            continue
        if ed is None or not len(ed) or len(c) < 100:
            continue
        idx = c.index
        words = E._words(str(names.get(tk) or tk), tk)
        for ts, row in ed.iterrows():
            est, rep = row.get("EPS Estimate"), row.get("Reported EPS")
            if pd.isna(rep) or pd.isna(est):
                continue
            ts = pd.Timestamp(ts)
            local = ts.tz_convert("America/New_York") if ts.tzinfo else ts
            day = pd.Timestamp(local.date())
            if day < SINCE:
                continue
            pre = local.hour < 12
            i = idx.searchsorted(day) if pre else idx.searchsorted(day, side="right")
            if i <= 20 or i >= len(idx):
                continue
            sur = row.get("Surprise(%)")
            if pd.isna(sur):
                sur = (rep - est) / abs(est) * 100 if est else np.nan
            if pd.isna(sur) or abs(sur) >= 500:
                continue
            q = (f"{words[0]} guidance OR outlook OR forecast "
                 f"after:{(day - pd.Timedelta(days=1)).date()} before:{(day + pd.Timedelta(days=4)).date()}")
            items = E._rss(q)
            nq += 1
            g = E.guidance(items, words, ts.tz_convert("UTC") if ts.tzinfo else ts.tz_localize("America/New_York").tz_convert("UTC"))
            rows.append({"t": tk, "d": str(idx[i].date()), "s": float(sur), "r1": float(c.iloc[i] / c.iloc[i - 1] - 1),
                         "r5": float(c.iloc[min(i + 4, len(idx) - 1)] / c.iloc[i - 1] - 1),
                         "run20": float(c.iloc[i - 1] / c.iloc[i - 21] - 1), "n_items": len(items),
                         "g": None if not g else g.get("d"), "g_t": None if not g else (g.get("t") or "")[:160]})
            time.sleep(1.2)
        print(f"{tk}: {len(rows)} Berichte, {nq} Abfragen", flush=True)
    pd.DataFrame(rows).to_csv(out_csv, index=False)


def _brier(p, y):
    return float(np.mean((p - y) ** 2))


def _fit(train: pd.DataFrame) -> dict:
    """Quoten aus dem Lernzeitraum: je Gewinn-Stufe und je Stufe × Ausblick (geglättet)."""
    base = train.groupby("b")["y"].agg(["sum", "count"])
    pb = {b: (r["sum"] + 0.5 * 2) / (r["count"] + 2) for b, r in base.iterrows()}
    cell = {}
    for (b, g), r in train.groupby(["b", "gk"])["y"].agg(["sum", "count"]).iterrows():
        cell[(b, g)] = (r["sum"] + K_SMOOTH * pb.get(b, .5)) / (r["count"] + K_SMOOTH)
    return {"pb": pb, "cell": cell}


def _predict(D: pd.DataFrame, m: dict) -> pd.DataFrame:
    D = D.copy()
    D["p0"] = D["b"].map(m["pb"]).fillna(.5)
    D["p1"] = [m["cell"].get((b, g), m["pb"].get(b, .5)) for b, g in zip(D["b"], D["gk"])]
    # M2: eigene Vorgeschichte (letzte 8 Berichte vor diesem), zur M1-Quote hin geglättet (8 Pseudo-Berichte)
    D["p2"] = (D["own_up"] * D["own_n"] + 8 * D["p1"]) / (D["own_n"] + 8)
    return D


def _boot(D: pd.DataFrame, a: str, b: str, n: int = 2000, seed: int = 5) -> tuple[float, float, float]:
    """Brier(a) − Brier(b) mit Block-Bootstrap über Kalendermonate; negativ = a besser."""
    rng = np.random.default_rng(seed)
    D = D.assign(m=D["d"].str[:7])
    grp = {k: g for k, g in D.groupby("m")}
    keys = list(grp)
    diffs = []
    for _ in range(n):
        s = pd.concat([grp[k] for k in rng.choice(keys, len(keys))])
        diffs.append(_brier(s[a], s["y"]) - _brier(s[b], s["y"]))
    d0 = _brier(D[a], D["y"]) - _brier(D[b], D["y"])
    return d0, float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))


def analyze(src: str, out_dir: str) -> None:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    parts = [pd.read_csv(f) for f in sorted(Path(src).glob("*.csv")) if f.stat().st_size > 10]
    D = pd.concat(parts, ignore_index=True).drop_duplicates(["t", "d"]).sort_values("d").reset_index(drop=True)
    D["y"] = (D["r1"] > 0).astype(float)
    D["b"] = D["s"].map(bucket)
    D["gk"] = D["g"].map({-1.0: "gesenkt", 0.0: "bestätigt", 1.0: "angehoben"}).fillna("keine Meldung")
    own_up, own_n = [], []
    hist: dict[str, list[float]] = {}
    for r in D.itertuples():
        h = hist.get(r.t, [])[-8:]
        own_up.append(float(np.mean(h)) if h else .5); own_n.append(len(h))
        hist.setdefault(r.t, []).append(r.y)
    D["own_up"], D["own_n"] = own_up, own_n
    dt = pd.to_datetime(D["d"])
    train, test = D[dt < SPLIT], D[dt >= SPLIT]
    m = _fit(train)
    T = _predict(test, m)
    L = []
    p = L.append
    p("# Quartalszahlen: macht der Ausblick die Prognose genauer?\n")
    p(f"Berichte: {len(D)} aus {D['t'].nunique()} US-Aktien seit {D['d'].min()} · Lernzeit bis {SPLIT.date()} ({len(train)}), "
      f"Prüfzeit danach ({len(test)}).\n")
    cov = D["gk"].value_counts(normalize=True)
    p("Ausblick erkannt: " + " · ".join(f"{k} {v:.0%}" for k, v in cov.items()) + "\n")
    p("## Wie oft stieg die Aktie am Tag danach? (alle Berichte; n in Klammern)\n")
    p("| Gewinn | gesenkt | bestätigt | angehoben | keine Meldung | alle |\n|---|---|---|---|---|---|")
    for i, (_, _, name) in enumerate(BUCKETS):
        s = D[D["b"] == i]
        cells = []
        for g in ("gesenkt", "bestätigt", "angehoben", "keine Meldung"):
            x = s[s["gk"] == g]
            cells.append(f"{x['y'].mean():.0%} ({len(x)}) · Median {x['r1'].median():+.1%}" if len(x) else "–")
        p(f"| {name} | " + " | ".join(cells) + f" | {s['y'].mean():.0%} ({len(s)}) |")
    p("\n## Prüfzeit (ab April 2025) – vorher festgelegte Modelle\n")
    p("| Modell | Brier (kleiner = besser) | Trefferquote | Treffer bei klarer Aussage (≥ 60 % / ≤ 40 %) | Anteil klarer Aussagen |\n|---|---|---|---|---|")
    res = {}
    for k, name in (("p0", "M0 Gewinn allein (heutige App)"), ("p1", "M1 Gewinn × Ausblick"), ("p2", "M2 + eigene Vorgeschichte")):
        pr = T[k]
        hit = float(((pr > .5) == (T["y"] > .5)).mean())
        clear = (pr >= .6) | (pr <= .4)
        hc = float(((pr[clear] > .5) == (T["y"][clear] > .5)).mean()) if clear.any() else float("nan")
        res[k] = {"brier": _brier(pr, T["y"]), "hit": hit, "hit_clear": hc, "clear": float(clear.mean())}
        p(f"| {name} | {res[k]['brier']:.4f} | {hit:.1%} | {hc:.1%} | {clear.mean():.0%} |")
    p("\nUnterschied im Brier-Score (Block-Bootstrap über Monate, 95-%-Intervall; negativ = besser):\n")
    dec = {}
    for a, b in (("p1", "p0"), ("p2", "p1")):
        d0, lo, hi = _boot(T, a, b)
        dec[a] = d0 < 0 and hi < 0
        p(f"- {a} gegen {b}: {d0:+.4f} [{lo:+.4f}; {hi:+.4f}] → {'besser (übernehmen)' if dec[a] else 'nicht nachweisbar besser'}")
    g = T[T["gk"] == "gesenkt"]
    if len(g):
        p(f"\nNur Berichte mit gesenktem Ausblick in der Prüfzeit (n {len(g)}): gestiegen {g['y'].mean():.0%}; "
          f"M0 sagte im Schnitt {g['p0'].mean():.0%}, M1 {g['p1'].mean():.0%}.")
    p("\n## Stichprobe der erkannten Ausblick-Schlagzeilen (zur Kontrolle der Erkennung)\n")
    for r in D[D["g"].notna()].sample(min(40, int(D["g"].notna().sum())), random_state=1).itertuples():
        p(f"- {r.t} {r.d} [{int(r.g):+d}] {r.g_t} → Tag danach {r.r1:+.1%}")
    (out / "earn_guide_report.md").write_text("\n".join(L), encoding="utf-8")
    # Tabelle für die App: aus allen Daten (nach dem Test), gleiche Glättung
    mf = _fit(D)
    table = {f"{b}|{g}": round(v, 3) for (b, g), v in mf["cell"].items()}
    ns = {f"{b}|{g}": int(n) for (b, g), n in D.groupby(["b", "gk"]).size().items()}
    json.dump({"n": int(len(D)), "since": str(D["d"].min()), "buckets": [x[2] for x in BUCKETS], "p": table, "n_cell": ns,
               "test": res, "adopt": {k: bool(v) for k, v in dec.items()}}, open(out / "earn_guide.json", "w"), ensure_ascii=False)
    D.to_csv(out / "earn_guide_rows.csv", index=False)
    print("\n".join(L[:40]))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["collect", "analyze"])
    ap.add_argument("a"); ap.add_argument("b")
    ap.add_argument("--shard", type=int, default=0); ap.add_argument("--shards", type=int, default=1); ap.add_argument("--max", type=int, default=600)
    x = ap.parse_args(argv)
    if x.cmd == "collect":
        collect(x.a, x.b, x.shard, x.shards, x.max)
    else:
        analyze(x.a, x.b)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
