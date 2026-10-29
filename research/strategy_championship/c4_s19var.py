"""S19-Varianten (Protokoll v1.7) – nur Train 2008–2016, zur Orientierung.

python -m research.strategy_championship.c4_s19var --data DIR --sectors DIR --out OUT
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from . import s01, wave3
from .b2_baselines import metrics
from .data import UNIVERSE, load
from .engine import Costs, run
from .wave1 import Panel, spreads

VARS = {"S19": (2.5, "strict"), "S19-A": (2.0, "strict"), "S19-B": (2.5, "2of3"), "S19-C": (2.0, "2of3")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--sectors", required=True)
    ap.add_argument("--out", default="c4_out")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    prices, cur, fx, bench, (start, end) = load(a.data, "train")
    uni = pd.read_csv(UNIVERSE)
    region = dict(zip(uni["ticker"], uni["region"]))
    prices = {t: v for t, v in prices.items() if region.get(t) == "us" and not t.endswith(".TO")}
    sc = pd.read_csv(Path(a.sectors) / "sectors_v1.csv")
    sectors = dict(zip(sc["ticker"], sc["sector"]))
    mcap = dict(zip(uni["ticker"], uni["market_cap_usd"]))
    yrs = (end - start).days / 365.25
    res = {}
    for qmode in ("pit", "today"):
        P = Panel(prices, cur, region, bench, start, end)
        wave3.prepare(P, bench, sectors, qmode, mcap)
        raw_ema = {t: s01.with_ema(df) for t, df in P.raw.items()}
        cal = pd.DatetimeIndex(sorted(set().union(*[f.index[(f.index >= start) & (f.index <= end)] for f in P.raw.values()])))
        sp = spreads(P.raw, cur, region)
        costs = {"base": Costs(fee_eur=0.99, spread=0.001, spread_by_ticker=sp),
                 "stress": Costs(fee_eur=1.99, spread=0.002, slippage=0.0005, fx_fee=0.001, spread_by_ticker={k: 2 * v for k, v in sp.items()})}
        for vid, (sig, vol) in VARS.items():
            for entry in ("trigger", "open"):
                cand, n = wave3.s19_variant(P, sig, vol, entry)
                orders = wave3.s19_orders(P, cand)
                row = {"signale_pro_jahr": round(n["signale"] / yrs, 1), "ausloeser": n["ausloeser"], "crv_ok": n["crv_ok"],
                       "crv_ok_pro_jahr": round(n["crv_ok"] / yrs, 1)}
                for cash, cn in ((2000, "base"), (2000, "stress"), (20000, "base")):
                    r = run(raw_ema, cur, fx, orders, cash, costs[cn], 5 if cash == 2000 else 10, calendar=cal, min_fill=0.5)
                    m = metrics(r)
                    t = r.trades
                    rn = (t["pnl_eur"] / t["risk_eur"]).mean() if len(t) else None
                    row[f"{cash}_{cn}"] = {"cagr": m.get("cagr"), "max_dd": m.get("max_dd"), "trades": m.get("trades"),
                                           "avg_r_net": None if rn is None else float(rn),
                                           "win_rate": m.get("win_rate"), "exits": m.get("exits")}
                    if cash == 2000 and cn == "base" and len(t):
                        t.to_csv(out / f"trades_{vid}_{entry}_{qmode}.csv", index=False)
                key = f"{vid} · {entry} · {qmode.upper()}"
                res[key] = row
                b = row["2000_base"]
                print(f"{key:28s} Signale/J {row['signale_pro_jahr']:5.1f} · CRV ok {n['crv_ok']:4d} ({row['crv_ok_pro_jahr']}/J) · "
                      f"Trades {b['trades']} · Ø R netto {b['avg_r_net']} · CAGR 2k {b['cagr']} · DD {b['max_dd']}", flush=True)
    (out / "c4_s19var.json").write_text(json.dumps(res, indent=1, default=str, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
