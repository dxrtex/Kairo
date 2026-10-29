"""Phase 2 – Hybrid Trend + Mean Reversion (Plan 15_HYBRID_PLAN.md) – nur Train 2008–2016.

python -m research.strategy_championship.c5_hybrid --data DIR --out OUT

Ampel A1: S&P 500 über EMA200 = gut. A2: zusätzlich realisierte 20-T.-Volatilität ≤ ihrem 1-Jahres-Median.
T1 = S07-B (Momentum 6-1 / Vol, Top 10, monatlich), investiert nur an Monatsenden mit guter Ampel (H0 ohne Ampel als Vergleich).
M2 = RSI(2) < 10 über EMA200 (wie S11-A), M3 = Markt-Verlierer 5 T. (wie S04-M) – Einstiege nur an Tagen mit schlechter Ampel
(„bad“) bzw. immer („all“). H1 = T1 + M2-bad, H2 = T1 + M3-bad, H3 = T1 + M2-all; ein gemeinsamer Topf.
Kosten: base, stress und „null“ (ohne Kosten – zeigt den Vorteil vor Gebühren).
"""

from __future__ import annotations

import argparse
import json
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

from . import wave2
from .b2_baselines import metrics
from .data import UNIVERSE, load
from .engine import Costs, run
from .wave1 import Panel, spreads

CAPS = (2000, 5000, 10000)
_G: dict = {}


def regimes(bench, cal) -> dict:
    g = bench["^GSPC"]["Close"]
    bull = g > g.ewm(span=200, adjust=False).mean()
    v20 = np.log(g).diff().rolling(20).std()
    calm = v20 <= v20.rolling(252).median()
    out = {"A1": bull, "A2": bull & calm}
    return {k: v.reindex(cal, method="ffill").fillna(False).astype(bool) for k, v in out.items()}


def build(P, bench, cal) -> dict:
    reg = regimes(bench, cal)
    me = wave2._month_ends(P)
    strat = {}
    strat["T1"] = wave2.monthly_stock(P, "S07-B", bench)
    strat["T1-top5"] = wave2.monthly_stock(P, "S07-B", bench, n=5)       # PRIME+: größere Positionen (≥ 250 € ab ~1.300 €)
    t1r = {}
    for a, s in reg.items():
        good = {d for d in me if bool(s.get(pd.Timestamp(d), False))}
        t1r[a] = wave2.monthly_stock(P, "S07-B", bench, regime=good)
        strat[f"T1-{a}"] = t1r[a]
        strat[f"T1-{a}-top5"] = wave2.monthly_stock(P, "S07-B", bench, regime=good, n=5)
    mr = {}
    for mid, sid in (("M2", "S11-A"), ("M3", "S04-M")):
        cand = P.candidates(sid)
        mr[(mid, "all")] = P.orders(cand, sid, 0.01, 10)
        for a, s in reg.items():
            bad = cand[~cand["date"].map(lambda d: bool(s.get(pd.Timestamp(d), True)))]
            mr[(mid, a)] = P.orders(bad, sid, 0.01, 10)
    for mid in ("M2", "M3"):
        strat[f"{mid}-alle"] = (mr[(mid, "all")], {})
        for a in reg:
            strat[f"{mid}-schlecht-{a}"] = (mr[(mid, a)], {})
    for a in reg:
        o, ex = t1r[a]
        strat[f"H1-{a}"] = (o + mr[("M2", a)], ex)
        strat[f"H2-{a}"] = (o + mr[("M3", a)], ex)
        strat[f"H3-{a}"] = (o + mr[("M2", "all")], ex)
    share = {a: float(s[(s.index >= P.start) & (s.index <= P.end)].mean()) for a, s in reg.items()}
    return strat, share


def _job(args):
    sid, cash, cn = args
    o, ex = _G["strat"][sid]
    r = run(_G["P"].raw, _G["cur"], _G["fx"], o, cash, _G["costs"][cn], 10, calendar=_G["cal"], exit_when=ex, min_fill=0.5)
    m = metrics(r)
    t = r.trades
    by = {}
    if len(t):
        for tag, g in t.groupby("tag"):
            by[tag] = {"trades": int(len(g)), "pnl_eur": round(float(g["pnl_eur"].sum()), 2),
                       "kosten_eur": round(float(g[["fees_eur", "spread_eur"]].sum().sum()), 2)}
    return (sid, cash, cn), {"cagr": m.get("cagr"), "max_dd": m.get("max_dd"), "sharpe": m.get("sharpe"),
                             "trades": m.get("trades"), "je_teil": by, "checks_ok": all(v for v in r.checks.values() if isinstance(v, bool))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default="c5_out")
    ap.add_argument("--only-prime", action="store_true", help="nur Kostenmodell Scalable PRIME+ (ab 250 € gebührenfrei)")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    prices, cur, fx, bench, (start, end) = load(a.data, "train")
    uni = pd.read_csv(UNIVERSE)
    region = dict(zip(uni["ticker"], uni["region"]))
    P = Panel(prices, cur, region, bench, start, end)
    wave2.extra(P)
    cal = pd.DatetimeIndex(sorted(set().union(*[f.index[(f.index >= start) & (f.index <= end)] for f in P.raw.values()])))
    sp = spreads(P.raw, cur, region)
    costs = {"base": Costs(fee_eur=0.99, spread=0.001, spread_by_ticker=sp),
             "stress": Costs(fee_eur=1.99, spread=0.002, slippage=0.0005, fx_fee=0.001, spread_by_ticker={k: 2 * v for k, v in sp.items()}),
             "null": Costs(fee_eur=0.0, spread=0.0),
             "prime": Costs(fee_eur=0.99, spread=0.001, spread_by_ticker=sp, fee_free_from=250.0),
             "prime_stress": Costs(fee_eur=1.99, spread=0.002, slippage=0.0005, fx_fee=0.001, fee_free_from=250.0,
                                   spread_by_ticker={k: 2 * v for k, v in sp.items()})}
    if a.only_prime:
        costs = {k: v for k, v in costs.items() if k.startswith("prime")}
    strat, share = build(P, bench, cal)
    _G.update(P=P, cur=cur, fx=fx, cal=cal, costs=costs, strat=strat)
    jobs = [(s, c, cn) for s in strat for c in CAPS for cn in costs]
    with Pool() as pool:
        rr = pool.map(_job, jobs, chunksize=1)
    res = {f"{k[0]} · {k[1]} € · {k[2]}": v for k, v in rr}
    (out / ("c5_prime.json" if a.only_prime else "c5_hybrid.json")).write_text(json.dumps({"ampel_gut_anteil": share, "results": res}, indent=1, default=str,
                                                   ensure_ascii=False))
    for s in strat:
        print(s, " | ".join(f"{k.split(' · ', 1)[1]}: {v['cagr']:+.1%} DD {v['max_dd']:.0%}" for k, v in res.items()
                            if k.startswith(s + " · ")), flush=True)
    print("Ampel gut (Anteil Tage):", share)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
