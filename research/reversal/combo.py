"""Kombinations-Test historisch: Bringt „11 Kriterien + X“ höhere, nachweisbare Renditen als B60 allein?

Vorab festgelegt (01.11.2026, vor dem ersten Lauf). Alle B60-Trades 2008–2026 (korrigierte Engine, je Trade, Stress-Kosten).
Je Hypothese: Ø R der Trades MIT Merkmal gegen OHNE Merkmal (nur Trades, bei denen das Merkmal bestimmbar ist).

Insider (nur USA, SEC Formular 4, offene Marktkäufe Code P; zählt nur, wenn bis zum Signaltag GEMELDET – kein Blick voraus):
  H1 ins_buy      mindestens ein Insider-Kauf in den 90 Tagen vor dem Signal
  H2 ins_cluster  mindestens zwei verschiedene Insider kauften
  H3 ins_officer  ein Vorstand/Officer (CEO, CFO, President …) kaufte
  H4 ins_big      Kaufsumme ≥ 100.000 $
Kurs und Volumen (alle Regionen):
  H5 sma200_up    Schluss über der 200-Tage-Linie (Rücksetzer im langfristigen Aufwärtstrend)
  H6 deep_dd      ≥ 40 % unter dem 52-Wochen-Hoch
  H7 vol_spike    Volumen am Signaltag ≥ 2 × Ø der 50 Tage davor (Kapitulation)
  H8 drop5        Wochenverlust (5 Tage) ≤ −10 %
Quartalszahlen (nur USA, SEC 8-K Punkt 2.02 bis zum Signaltag angenommen):
  H9 earn_recent  Quartalszahlen in den 10 Handelstagen vor dem Signal
Paare: P1 ins_buy+deep_dd · P2 vol_spike+index_u200 · P3 sma200_up+index_u200

Entscheidungsregel: Ein Merkmal ist „Kandidat für den Depot-Test“ (als Verstärker: bevorzugt kaufen, oder als Filter:
weglassen), wenn der Unterschied in Train, Validierung UND Holdout dasselbe Vorzeichen hat und jeweils |Δ| ≥ 0,05 R beträgt
UND der Benjamini-Hochberg-q-Wert über alle 12 Tests ≤ 0,10 ist. Kein Kandidat ändert die Regel – nächster Schritt wäre ein
Depot-Test (Rangfolge/Filter vs. B60, alle Raster), danach Schattentest und Freigabe.

    python -m research.reversal.combo --data v1 --signals sig.parquet --sec sec --insider sec/insider_buys.csv.gz --out out
"""
from __future__ import annotations

import argparse
import json
from math import erf, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

from research.reversal import learn as LR
from research.ultimate import round1 as R

AB = ("Train", "Validierung", "Holdout")
HYP = {"ins_buy": "Insider-Kauf (90 T.)", "ins_cluster": "≥ 2 Insider kauften", "ins_officer": "Vorstand/Officer kaufte",
       "ins_big": "Insider-Käufe ≥ 100.000 $", "sma200_up": "über der 200-Tage-Linie", "deep_dd": "≥ 40 % unter 52-Wochen-Hoch",
       "vol_spike": "Volumen ≥ 2 × Ø (Kapitulation)", "drop5": "Wochenverlust ≤ −10 %", "earn_recent": "Quartalszahlen ≤ 10 Tage davor"}
PAIRS = (("ins_buy", "deep_dd"), ("vol_spike", "index_u200"), ("sma200_up", "index_u200"))
MIN_D, Q = 0.05, 0.10
OFFICER = ("officer", "ceo", "cfo", "president", "chief", "coo", "chair")


def insider_index(path: str | None, cik_map: str | None) -> dict:
    """Ticker → DataFrame (filed, owner, officer, value) der offenen Marktkäufe."""
    if not path or not Path(path).exists() or not cik_map:
        return {}
    ins = pd.read_csv(path, dtype={"role": str, "owner": str, "title": str})
    cm = pd.read_csv(cik_map)
    c2t = {int(c): t for t, c in zip(cm["ticker"], cm["cik"])}
    ins["t"] = ins["cik"].map(lambda c: c2t.get(int(c)) if pd.notna(c) else None)
    ins = ins.dropna(subset=["t", "filed"])
    ins["filed"] = pd.to_datetime(ins["filed"], errors="coerce")
    ins["val"] = ins["shares"].fillna(0) * ins["price"].fillna(0)
    txt = (ins["role"].fillna("") + " " + ins["title"].fillna("")).str.lower()
    ins["officer"] = txt.apply(lambda s: any(k in s for k in OFFICER))
    return {t: g.sort_values("filed") for t, g in ins.groupby("t")}


def features(df: pd.DataFrame, ins: dict, us: set) -> pd.DataFrame:
    adj, prices, sec = R._G["adj"], R._G.get("prices", {}), R._G.get("sec", {})
    rows = []
    for x in df.itertuples(index=False):
        a = adj[x.ticker]
        c = a["Close"].to_numpy(float)
        sd = pd.Timestamp(x.signal_date)
        i = int(a.index.searchsorted(sd, side="right") - 1)
        o = {"sma200_up": bool(c[i] > c[i - 199:i + 1].mean()) if i >= 199 else None,
             "deep_dd": bool(c[i] / c[max(0, i - 251):i + 1].max() - 1 <= -0.40) if i >= 60 else None,
             "drop5": bool(c[i] / c[i - 5] - 1 <= -0.10) if i >= 5 else None, "vol_spike": None,
             "ins_buy": None, "ins_cluster": None, "ins_officer": None, "ins_big": None, "earn_recent": None}
        p = prices.get(x.ticker)
        if p is not None and "Volume" in p:
            v = p["Volume"].reindex(a.index).to_numpy(float)
            if i >= 50 and np.isfinite(v[i]) and np.nanmean(v[i - 50:i]) > 0:
                o["vol_spike"] = bool(v[i] >= 2 * np.nanmean(v[i - 50:i]))
        if x.ticker in us:
            g = ins.get(x.ticker)
            if g is None:
                o.update(ins_buy=False, ins_cluster=False, ins_officer=False, ins_big=False)
            else:
                w = g[(g["filed"] <= sd) & (g["filed"] > sd - pd.Timedelta(days=90))]
                o.update(ins_buy=len(w) > 0, ins_cluster=w["owner"].nunique() >= 2, ins_officer=bool(w["officer"].any()),
                         ins_big=float(w["val"].sum()) >= 100_000)
            e = sec.get(x.ticker.upper())
            if e is not None:
                lo = a.index[max(0, i - 10)]
                o["earn_recent"] = bool(((e > np.datetime64(lo)) & (e <= np.datetime64(sd))).any())
            elif sec:
                o["earn_recent"] = False
        rows.append(o)
    return df.reset_index(drop=True).join(pd.DataFrame(rows))


def _p(a: np.ndarray, b: np.ndarray) -> float:
    va, vb = a.var(ddof=1) / len(a), b.var(ddof=1) / len(b)
    z = abs(a.mean() - b.mean()) / sqrt(va + vb) if va + vb > 0 else 0.0
    return float(2 * (1 - 0.5 * (1 + erf(z / sqrt(2)))))


def evaluate(df: pd.DataFrame) -> dict:
    tests = list(HYP.items()) + [(f"{a}+{b}", f"{HYP.get(a, a)} UND {LR.FEATS.get(b, HYP.get(b, b))}") for a, b in PAIRS]
    res = {}
    for k, lbl in tests:
        parts = k.split("+")
        known = df.dropna(subset=parts)
        if not len(known):
            res[k] = {"l": lbl, "n": 0, "status": "keine Daten"}
            continue
        m = np.logical_and.reduce([known[c].astype(bool).to_numpy() for c in parts])
        a, b = known.loc[m, "R_stress"].to_numpy(), known.loc[~m, "R_stress"].to_numpy()
        row = {"l": lbl, "n": int(m.sum()), "n_known": int(len(known)), "share": float(m.mean()),
               "mit": float(a.mean()) if len(a) else None, "ohne": float(b.mean()) if len(b) else None,
               "mit_base": float(known.loc[m, "R_base"].mean()) if len(a) else None, "ab": {}}
        for ab in AB:
            s = known[known["abschnitt"] == ab]
            ms = np.logical_and.reduce([s[c].astype(bool).to_numpy() for c in parts]) if len(s) else np.array([], bool)
            row["ab"][ab] = {"n": int(ms.sum()), "diff": float(s.loc[ms, "R_stress"].mean() - s.loc[~ms, "R_stress"].mean())
                             if ms.sum() >= 5 and (~ms).sum() >= 5 else None}
        row["p"] = _p(a, b) if len(a) >= 10 and len(b) >= 10 else None
        res[k] = row
    ps = sorted([(r["p"], k) for k, r in res.items() if r.get("p") is not None])
    prev = 1.0
    for rank in range(len(ps), 0, -1):
        p, k = ps[rank - 1]
        prev = min(prev, p * len(ps) / rank)
        res[k]["q"] = prev
    for k, r in res.items():
        if r.get("status"):
            continue
        ds = [v["diff"] for v in r["ab"].values()]
        same = all(d is not None and abs(d) >= MIN_D for d in ds) and (all(d > 0 for d in ds) or all(d < 0 for d in ds))
        ok = same and r.get("q") is not None and r["q"] <= Q
        r["status"] = ("Kandidat (Verstärker) für den Depot-Test" if ds[0] > 0 else "Kandidat (Filter) für den Depot-Test") if ok \
            else "kein beständiger Effekt"
    return res


def report(df: pd.DataFrame, res: dict) -> str:
    f = lambda v: "–" if v is None else f"{v:+.3f}"
    L = ["# Kombinations-Test: 11 Kriterien + X (2008–2026)\n", __doc__.split("\n", 1)[1].split("    python")[0].strip(), "",
         f"**{len(df):,} B60-Trades**, davon USA {int(df['ticker'].map(lambda t: '.' not in t).sum()):,} · Ø R Stress {df['R_stress'].mean():+.3f}\n".replace(",", "."),
         "| Merkmal | mit X (Anteil) | Ø R Stress mit | ohne | Δ Train | Δ Validierung | Δ Holdout | q (BH) | Ergebnis |", "|---|---|---|---|---|---|---|---|---|"]
    for k, r in res.items():
        if not r.get("n_known"):
            L.append(f"| {r['l']} | – | – | – | – | – | – | – | {r.get('status')} |")
            continue
        L.append(f"| {r['l']} | {r['n']} ({r['share']:.0%} von {r['n_known']}) | {f(r['mit'])} | {f(r['ohne'])} | "
                 + " | ".join(f"{f(r['ab'][ab]['diff'])} ({r['ab'][ab]['n']})" for ab in AB)
                 + " | " + ("–" if r.get("q") is None else f"{r['q']:.3f}") + f" | **{r['status']}** |")
    cand = [k for k, r in res.items() if str(r.get("status", "")).startswith("Kandidat")]
    L.append("\n## Ergebnis\n")
    L.append(("Kandidaten: " + ", ".join(f"**{res[k]['l']}** ({'Verstärker' if 'Verstärker' in res[k]['status'] else 'Filter'})" for k in cand)
              + ". Nächster Schritt: Depot-Test (bevorzugt kaufen bzw. weglassen, alle Raster) – erst dann Schattentest und Freigabe.")
             if cand else "**Keine Kombination bringt beständig und nach Mehrfachtest-Korrektur mehr** – B60 bleibt unverändert.")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data"); ap.add_argument("--signals"); ap.add_argument("--sec"); ap.add_argument("--insider")
    ap.add_argument("--out", default="combo_out")
    ap.add_argument("--universe", default="research/strategy_championship/data/universe_frozen_2026-10-16.csv")
    a = ap.parse_args(argv)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    sig, meta = R.setup(a.data, a.signals, a.sec)
    t = R.per_trade(R.build(sig, meta, "E0", 1e-5))
    uni = pd.read_csv(a.universe)
    base = LR.features(t, R._G["adj"], dict(zip(uni["ticker"], uni["region"])), dict(zip(uni["ticker"], uni["sector"])))
    cm = Path(a.sec) / "cik_map.csv" if a.sec else None
    us = set(pd.read_csv(cm)["ticker"]) if cm and cm.exists() else set()
    ins = insider_index(a.insider, str(cm) if cm else None)
    print(f"Insider-Index: {len(ins)} Aktien mit Käufen · US-Titel mit CIK: {len(us)}", flush=True)
    df = features(base, ins, us)
    df.to_csv(out / "combo_trades.csv.gz", index=False)
    res = evaluate(df)
    (out / "combo_result.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    txt = report(df, res)
    (out / "combo_report.md").write_text(txt, encoding="utf-8")
    print(txt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
