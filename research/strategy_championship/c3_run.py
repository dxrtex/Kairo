"""S19 / S20 (Nutzer-Spezifikation, Protokoll v1.5) – Train und einmalige Validierung im selben Lauf.

python -m research.strategy_championship.c3_run --data DIR --fund DIR --sid S19 --period train --out OUT [--seeds 200]
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

from . import s01, wave3
from .b2_baselines import bootstrap, metrics
from .data import UNIVERSE, load
from .engine import Costs, run
from .wave1 import Panel, spreads

MIN_FILL = 0.5
_G: dict = {}


def build(sid, cand):
    P = _G["P"]
    return wave3.s19_orders(P, cand) if sid == "S19" else wave3.s20_orders(P, cand)


def depot(orders, cash, costs):
    return run(_G["P"].raw_ema, _G["cur"], _G["fx"], orders, cash, costs, 5 if cash == 5000 else 10, calendar=_G["cal"],
               min_fill=MIN_FILL)


def _null(args):
    sid, cash, seed = args
    P = _G["P"]
    nc = wave3.s19_null(P, _G["cand"], seed) if sid == "S19" else wave3.s20_null(P, _G["cand"], seed)
    m = metrics(depot(build(sid, nc), cash, _G["base"]))
    return cash, seed, {k: m.get(k) for k in ("cagr", "max_dd", "sharpe", "trades", "final_eur")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--fund")
    ap.add_argument("--sid", required=True, choices=["S19", "S20"])
    ap.add_argument("--period", required=True, choices=["train", "validation"])
    ap.add_argument("--out", default="c3_out")
    ap.add_argument("--seeds", type=int, default=200)
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    prices, cur, fx, bench, (start, end) = load(a.data, a.period)
    uni = pd.read_csv(UNIVERSE)
    region = dict(zip(uni["ticker"], uni["region"]))
    if a.sid == "S19":                               # nur US-Aktien
        prices = {t: v for t, v in prices.items() if region.get(t) == "us" and not t.endswith(".TO")}
    P = Panel(prices, cur, region, bench, start, end)
    fund, sic = None, {}
    if a.sid == "S19":
        fund = pd.read_parquet(Path(a.fund) / "edgar_fund_v1.parquet")
        sc = pd.read_csv(Path(a.fund) / "edgar_sic_v1.csv")
        sic = dict(zip(sc["ticker"], sc["sic"]))
    wave3.prepare(P, bench, fund, sic)
    P.raw_ema = {t: s01.with_ema(df) for t, df in P.raw.items()}
    cal = pd.DatetimeIndex(sorted(set().union(*[f.index[(f.index >= start) & (f.index <= end)] for f in P.raw.values()])))
    sp = spreads(P.raw, cur, region)
    base = Costs(fee_eur=0.99, spread=0.001, spread_by_ticker=sp)
    stress = Costs(fee_eur=1.99, spread=0.002, slippage=0.0005, fx_fee=0.001, spread_by_ticker={k: 2 * v for k, v in sp.items()})
    cand = wave3.s19_candidates(P) if a.sid == "S19" else wave3.s20_candidates(P)
    if a.sid == "S19":
        P.pool19 = wave3.s19_pool(P)
        q = sum(int(x["qual"].sum()) for x in P.G.values())
        print(f"S19: Qualitäts-Titeltage {q}, Titel mit Qualität {sum(bool(x['qual'].any()) for x in P.G.values())}", flush=True)
    print(f"{a.sid} {a.period}: {len(cand)} Einstiege, {cand['ticker'].nunique() if len(cand) else 0} Titel", flush=True)
    cand.to_csv(out / f"cand_{a.sid}_{a.period}.csv", index=False)
    _G.update(P=P, cur=cur, fx=fx, cal=cal, base=base, cand=cand)
    acwi = bench["ACWI"]
    acwi_r = (acwi["AdjClose"] / fx["USD"].reindex(acwi.index, method="ffill")).pct_change()
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        commit = None
    ts = lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    results, log = {}, []
    orders = build(a.sid, cand)
    for cash in (5000, 20000):
        for cname, costs in (("base", base), ("stress", stress)):
            res = depot(orders, cash, costs)
            m = metrics(res, acwi_r)
            m.update(bootstrap(res))
            name = f"{a.sid} · {cash} €" + (" · Kostenstress" if cname == "stress" else "")
            results[name] = {"config": {"cash": cash, "costs": cname}, "metrics": m}
            log.append({"id": f"C3-{a.sid}-{a.period}-{len(log) + 1:03d}", "name": name, "period": a.period, "protocol": "v1.5",
                        "commit": commit, "ts": ts(), "cagr": m.get("cagr"), "max_dd": m.get("max_dd"), "sharpe": m.get("sharpe"),
                        "trades": m.get("trades")})
            print(f"{name}: CAGR {m.get('cagr', 0):+.2%} · MaxDD {m.get('max_dd', 0):.1%} · Sharpe {m.get('sharpe')} · "
                  f"Trades {m.get('trades')} · Ø R {m.get('avg_r_net')} · {m.get('exits')} · {m['checks']}", flush=True)
            if cname == "base":
                res.trades.to_csv(out / f"trades_{a.sid}_{a.period}_{cash}.csv", index=False)
    if a.seeds and len(cand):
        with Pool() as pool:
            nulls = pool.map(_null, [(a.sid, c, s) for c in (5000, 20000) for s in range(a.seeds)], chunksize=2)
        for c in (5000, 20000):
            arr = pd.DataFrame([{"seed": s, **m} for cc, s, m in nulls if cc == c])
            ref = results[f"{a.sid} · {c} €"]["metrics"]
            summ = {"n": int(len(arr)), "cagr_median": float(arr["cagr"].median()),
                    "cagr_p05_p95": [float(arr["cagr"].quantile(.05)), float(arr["cagr"].quantile(.95))],
                    "sharpe_median": float(arr["sharpe"].median()) if arr["sharpe"].notna().any() else None,
                    "p_cagr": float((arr["cagr"] >= ref["cagr"]).mean()),
                    "p_sharpe": float((arr["sharpe"].fillna(-9) >= (ref.get("sharpe") or -9)).mean())}
            results[f"Null {a.sid} · {c} €"] = {"summary": summ}
            log.append({"id": f"C3-{a.sid}-{a.period}-{len(log) + 1:03d}", "name": f"Null {a.sid} · {c} €", "period": a.period,
                        "protocol": "v1.5", "seeds": a.seeds, "commit": commit, "ts": ts(), **summ})
            print(f"Null {c}: {summ}", flush=True)
    tag = f"{a.sid}_{a.period}"
    (out / f"c3_{tag}.json").write_text(json.dumps(results, indent=1, default=str, ensure_ascii=False))
    (out / f"c3_{tag}_experiments.jsonl").write_text("\n".join(json.dumps(x, default=str, ensure_ascii=False) for x in log) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
