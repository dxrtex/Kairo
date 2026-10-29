"""Holdout H2 – S16-B Dual Momentum SPY/EFA/QQQ → SHY gegen Zufall (zufälliger ETF derselben Auswahl) und ACWI halten.

python -m research.strategy_championship.h_s16 --data DIR --out OUT --period holdout   (braucht KAIRO_HOLDOUT_UNSEALED=1)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from . import wave2
from .b2_baselines import metrics
from .data import load
from .engine import Costs, Order, run

CAPS = (2000, 5000, 10000)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default="h_out")
    ap.add_argument("--period", default="holdout", choices=["train", "validation", "holdout"])
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    _, _, fx, bench, (start, end) = load(a.data, a.period, tickers=["__keine__"])
    frames = {t: bench[t][["Open", "High", "Low", "Close", "AdjClose"]] for t in ("SPY", "EFA", "QQQ", "SHY", "BIL", "ACWI")}
    cur = {t: "USD" for t in frames}
    cal = frames["SPY"].index[(frames["SPY"].index >= start) & (frames["SPY"].index <= end)]
    costs = {"prime": Costs(fee_eur=0.99, spread=0.001, fee_free_from=250.0),
             "prime_stress": Costs(fee_eur=1.99, spread=0.002, slippage=0.0005, fx_fee=0.001, fee_free_from=250.0)}
    res = {}
    o, ex, _ = wave2.etf_rotation(bench, "S16-B", start, end)
    for c in CAPS:
        for cn, co in costs.items():
            r = run(frames, cur, fx, o, c, co, 3, calendar=cal, exit_when=ex, min_fill=0.5)
            m = metrics(r)
            res[f"S16-B · {c} € · {cn}"] = {k: m.get(k) for k in ("cagr", "max_dd", "sharpe", "trades")} | {
                "checks_ok": all(v for v in r.checks.values() if isinstance(v, bool))}
            ra = run(frames, cur, fx, [Order(cal[0], "ACWI", weight=0.995)], c, co, 1, calendar=cal)
            res[f"ACWI halten · {c} € · {cn}"] = {k: metrics(ra).get(k) for k in ("cagr", "max_dd", "sharpe")}
    null = []
    for seed in range(100):
        on, exn, _ = wave2.etf_rotation(bench, "S16-B", start, end, rng=np.random.default_rng(seed))
        null.append(metrics(run(frames, cur, fx, on, 5000, costs["prime"], 3, calendar=cal, exit_when=exn, min_fill=0.5))["cagr"])
    null = np.array(null)
    res["S16-B · 5000 € · prime"].update(p_zufall=float((null >= res["S16-B · 5000 € · prime"]["cagr"]).mean()),
                                         zufall_median=float(np.median(null)))
    (out / f"h_s16_{a.period}.json").write_text(json.dumps(res, indent=1, default=str))
    for k, v in res.items():
        print(k, {x: (round(y, 4) if isinstance(y, float) else y) for x, y in v.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
