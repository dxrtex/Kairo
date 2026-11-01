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

Teil 2 (vorab festgelegt 01.11.2026 nach Teil 1, vor dem eigenen Lauf; nur USA, SEC-Daten zeitgenau):
Grund des Rückgangs (8-K-Meldungen mit Annahmedatum in den 20 Handelstagen bis zum Signal; Chan 2003: Rückgänge OHNE
Nachricht erholen sich eher, Rückgänge MIT Nachricht setzen sich eher fort):
  N1 no_news      keine 8-K-Meldung
  N2 news_earn    Quartalszahlen-Meldung (8-K Punkt 2.02)
  N3 news_other   andere wesentliche Meldung (8-K ohne 2.02, nicht nur Anhänge 9.01)
Qualität (XBRL, nur bis zum Signaltag veröffentlichte Berichte, höchstens 200 Tage alt):
  Q1 profitable   Jahresüberschuss der letzten 12 Monate > 0
  Q2 gp_quality   Bruttogewinn / Bilanzsumme ≥ 0,20
  Q3 em_pos       letzter Quartalsgewinn über dem Vorjahresquartal
  Q4 low_lev      Eigenkapital / Bilanzsumme ≥ 0,40
Paare: no_news+profitable · news_earn+em_neg · profitable+deep_dd
Gleiche Entscheidungsregel, Benjamini-Hochberg innerhalb von Teil 2; zusätzlich der q-Wert über Teil 1 + 2 zusammen.

    python -m research.reversal.combo --data v1 --signals sig.parquet --sec sec --insider sec/insider_buys.csv.gz --out out [--part 2 --fund sec/fund_timeline.csv.gz]
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
HYP2 = {"no_news": "kein 8-K im Rückgang (keine Nachricht)", "news_earn": "Quartalszahlen im Rückgang (8-K 2.02)",
        "news_other": "andere Meldung im Rückgang", "profitable": "profitabel (12 Monate)", "gp_quality": "Bruttogewinn/Bilanzsumme ≥ 0,20",
        "em_pos": "Gewinn über Vorjahresquartal", "low_lev": "Eigenkapitalquote ≥ 40 %", "em_neg": "Gewinn unter Vorjahresquartal"}
PAIRS2 = (("no_news", "profitable"), ("news_earn", "em_neg"), ("profitable", "deep_dd"))
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


def features2(df: pd.DataFrame, filings: pd.DataFrame | None, tl: pd.DataFrame | None, t2c: dict) -> pd.DataFrame:
    """Teil 2: Nachrichten-Grund des Rückgangs (8-K) und Qualität (XBRL, zeitgenau) – nur US-Titel mit CIK."""
    adj = R._G["adj"]
    ev = {}
    if filings is not None:
        f = filings[filings["form"].astype(str).str.startswith("8-K")].copy()
        f["at"] = pd.to_datetime(f["accepted"], utc=True, errors="coerce").dt.tz_localize(None).dt.normalize()
        it = f["items"].fillna("").astype(str)
        f["earn"] = it.str.contains("2.02")
        f["other"] = ~f["earn"] & it.apply(lambda s: bool([x for x in s.replace(";", ",").split(",") if x.strip() and x.strip() not in ("9.01", "7.01")]))
        ev = {int(c): g[["at", "earn", "other"]].dropna(subset=["at"]).sort_values("at") for c, g in f.groupby("cik")}
    if tl is not None:
        tl = tl.copy()
        for c in ("avail", "filed"):
            tl[c] = pd.to_datetime(tl[c])
        tlg = {int(c): g.sort_values("avail") for c, g in tl.groupby("cik")}
    else:
        tlg = {}
    out = []
    for x in df.itertuples(index=False):
        o = dict.fromkeys(HYP2)
        c = t2c.get(x.ticker)
        if c is not None:
            a = adj[x.ticker]
            sd = pd.Timestamp(x.signal_date)
            i = int(a.index.searchsorted(sd, side="right") - 1)
            lo = a.index[max(0, i - 20)]
            if filings is not None:
                g = ev.get(int(c))
                w = g[(g["at"] > lo) & (g["at"] <= sd)] if g is not None else None
                o["no_news"] = w is None or len(w) == 0
                o["news_earn"] = bool(w is not None and w["earn"].any())
                o["news_other"] = bool(w is not None and w["other"].any())
            g = tlg.get(int(c))
            if g is not None:
                g = g[g["avail"] <= sd]
                if len(g) and (sd - g["filed"].iloc[-1]).days <= 200:
                    r = g.iloc[-1]
                    nz = lambda v: v is not None and pd.notna(v)
                    o["profitable"] = bool(r["ni_ttm"] > 0) if nz(r.get("ni_ttm")) else None
                    o["gp_quality"] = bool(r["gpa"] >= 0.20) if nz(r.get("gpa")) else None
                    o["em_pos"] = bool(r["em"] > 0) if nz(r.get("em")) else None
                    o["em_neg"] = bool(r["em"] < 0) if nz(r.get("em")) else None
                    o["low_lev"] = bool(r["equity"] / r["assets"] >= 0.40) if nz(r.get("equity")) and nz(r.get("assets")) and r["assets"] > 0 else None
        out.append(o)
    return df.reset_index(drop=True).join(pd.DataFrame(out))


def _p(a: np.ndarray, b: np.ndarray) -> float:
    va, vb = a.var(ddof=1) / len(a), b.var(ddof=1) / len(b)
    z = abs(a.mean() - b.mean()) / sqrt(va + vb) if va + vb > 0 else 0.0
    return float(2 * (1 - 0.5 * (1 + erf(z / sqrt(2)))))


def evaluate(df: pd.DataFrame, hyp: dict | None = None, pairs: tuple | None = None) -> dict:
    hyp, pairs = hyp or HYP, pairs if pairs is not None else PAIRS
    lab = lambda k: hyp.get(k) or HYP.get(k) or HYP2.get(k) or LR.FEATS.get(k, k)
    tests = [(k, v) for k, v in hyp.items() if k != "em_neg"] + [(f"{a}+{b}", f"{lab(a)} UND {lab(b)}") for a, b in pairs]
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


def report(df: pd.DataFrame, res: dict, part: int = 1) -> str:
    f = lambda v: "–" if v is None else f"{v:+.3f}"
    L = [f"# Kombinations-Test{' Teil 2 (Nachrichten-Grund, Qualität)' if part == 2 else ''}: 11 Kriterien + X (2008–2026)\n", __doc__.split("\n", 1)[1].split("    python")[0].strip(), "",
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
    ap.add_argument("--out", default="combo_out"); ap.add_argument("--part", type=int, default=1); ap.add_argument("--fund")
    ap.add_argument("--prev", help="combo_result.json aus Teil 1 für den gemeinsamen q-Wert")
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
    sfx = "" if a.part == 1 else "2"
    if a.part == 2:
        t2c = {t: int(c) for t, c in zip(pd.read_csv(cm)["ticker"], pd.read_csv(cm)["cik"])} if cm and cm.exists() else {}
        fil = pd.read_csv(Path(a.sec) / "filings.csv.gz", dtype={"items": str}, usecols=["cik", "form", "items", "accepted"]) if a.sec else None
        tl = None
        if a.fund and Path(a.fund).exists():
            tl = pd.read_csv(a.fund)
            if "gpa" not in tl.columns:                      # Rohdaten → Zeitleiste bauen
                from research.strategy_championship.v3 import fundamentals as FU
                f = pd.read_csv(a.fund, dtype={"val": str, "start": str, "end": str, "filed": str})
                f["start"] = f["start"].fillna("")
                tl = FU.build(f)
        print(f"Teil 2: 8-K {0 if fil is None else len(fil)} Zeilen · Zeitleiste {0 if tl is None else len(tl)} Zeilen", flush=True)
        df = features2(df, fil, tl, t2c)
        res = evaluate(df, HYP2, PAIRS2)
        if a.prev and Path(a.prev).exists():             # gemeinsamer BH-q-Wert über Teil 1 + 2
            prev = json.loads(Path(a.prev).read_text())
            allp = sorted([(v["p"], ("1", k)) for k, v in prev.items() if v.get("p") is not None] + [(v["p"], ("2", k)) for k, v in res.items() if v.get("p") is not None])
            m, q = len(allp), 1.0
            for rank in range(m, 0, -1):
                p, (part, k) = allp[rank - 1]
                q = min(q, p * m / rank)
                if part == "2":
                    res[k]["q_all"] = q
    else:
        res = evaluate(df)
    df.to_csv(out / f"combo{sfx}_trades.csv.gz", index=False)
    (out / f"combo{sfx}_result.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    txt = report(df, res, a.part)
    if a.part == 2:
        txt += "\nGemeinsamer q-Wert über Teil 1 + 2: " + ", ".join(f"{v['l']} {v['q_all']:.3f}" for v in res.values() if v.get("q_all") is not None) + "\n"
    (out / f"combo{sfx}_report.md").write_text(txt, encoding="utf-8")
    print(txt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
