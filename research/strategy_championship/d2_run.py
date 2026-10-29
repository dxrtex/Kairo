"""Phase D2 – Gesamtsystem: ETF-Kern + 10/20/30 % Trading-Teil Momentum Top 5 (Kosten Scalable PRIME+), 2008–2021.

python -m research.strategy_championship.d2_run --data DIR --out OUT      (braucht KAIRO_VALIDATION_UNSEALED=1)

Wie d_run: jeder Topf einzeln mit eigener Engine, Depotwerte täglich addiert (kein Umschichten zwischen den Töpfen).
Kerne: ACWI kaufen & halten, S13-ETF (ACWI nur über SMA 10 Monate). Trading-Teil: T1-top5 (S07-B mit 5 Titeln).
"""

from __future__ import annotations

import argparse
import json
from multiprocessing import Pool
from pathlib import Path

import pandas as pd

from . import d_run, wave2
from .d_run import seg, stats
from .data import UNIVERSE, load
from .engine import Costs, Order, run
from .v_run import s13_orders
from .wave1 import Panel, spreads

CORES = ["ACWI", "S13-ETF"]
SAT = "Momentum"
SHARES = [0.1, 0.2, 0.3]
CAPS = [10000, 20000, 50000]
_G = d_run._G


def _sleeve(args):
    sid, cash, cn = args
    o, ex = _G["orders"][sid]
    etf = sid in CORES
    res = run(_G["etf_frames"] if etf else _G["P"].raw, _G["etf_cur"] if etf else _G["cur"], _G["fx"], o, cash,
              _G["costs"][cn], 1 if etf else 12, calendar=_G["cal"], exit_when=ex, min_fill=0.5)
    return (sid, cash, cn), res.equity


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default="d2_out")
    ap.add_argument("--period", default="trainval", choices=["trainval", "holdout"])
    ap.add_argument("--n", type=int, default=5, help="Titel im Momentum-Teil (5 oder 10)")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    prices, cur, fx, bench, (start, end) = load(a.data, a.period)
    uni = pd.read_csv(UNIVERSE)
    region = dict(zip(uni["ticker"], uni["region"]))
    P = Panel(prices, cur, region, bench, start, end)
    wave2.extra(P)
    cal = pd.DatetimeIndex(sorted(set().union(*[f.index[(f.index >= start) & (f.index <= end)] for f in P.raw.values()])))
    sp = spreads(P.raw, cur, region)
    costs = {"prime": Costs(fee_eur=0.99, spread=0.001, spread_by_ticker=sp, fee_free_from=250.0),
             "prime_stress": Costs(fee_eur=1.99, spread=0.002, slippage=0.0005, fx_fee=0.001, fee_free_from=250.0,
                                   spread_by_ticker={k: 2 * v for k, v in sp.items()})}
    etf_frames = {"ACWI": bench["ACWI"][["Open", "High", "Low", "Close", "AdjClose"]]}
    _G.update(P=P, fx=fx, cal=cal, cur=cur, costs=costs, etf_frames=etf_frames, etf_cur={"ACWI": "USD"})
    _G["orders"] = {"ACWI": ([Order(cal[0], "ACWI", weight=0.995, tag="ACWI")], {}),
                    "S13-ETF": s13_orders(bench["ACWI"], fx["USD"], start, end),
                    SAT: wave2.monthly_stock(P, "S07-B", bench, n=a.n)}
    amounts = sorted({round(c * s) for c in CAPS for s in SHARES + [1 - x for x in SHARES] + [1.0]})
    jobs = [(sid, amt, cn) for sid in CORES + [SAT] for amt in amounts for cn in costs]
    with Pool() as pool:
        rr = pool.map(_sleeve, jobs, chunksize=1)
    eq = {k: e.reindex(cal).ffill().bfill() for k, e in rr}
    res = {}
    sg = (lambda e: {"gesamt": stats(e)}) if a.period == "holdout" else seg
    for cap in CAPS:
        for cn in costs:
            for sid in CORES + [SAT]:
                res[f"{sid} rein · {cap} € · {cn}"] = sg(eq[(sid, cap, cn)])
            for core in CORES:
                for sh in SHARES:
                    e = eq[(core, round(cap * (1 - sh)), cn)] + eq[(SAT, round(cap * sh), cn)]
                    res[f"{core} + {int(sh * 100)} % {SAT} · {cap} € · {cn}"] = sg(e)
    (out / f"d2_{a.period}_top{a.n}.json").write_text(json.dumps(res, indent=1, default=str, ensure_ascii=False))
    for k, v in res.items():
        if "20000 € · prime" in k and "stress" not in k:
            g = v["gesamt"]
            print(f"{k:50s} {g['cagr']:+.1%} DD {g['max_dd']:.0%} Sharpe {g['sharpe']:.2f}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
