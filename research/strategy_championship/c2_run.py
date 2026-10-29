"""Phase C, Welle 2 – Screening (Train 2008–2016, Protokoll v1.2). Aufbau wie c1_run.

python -m research.strategy_championship.c2_run --data DIR --family S07 --out OUT [--seeds 200]
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

from . import wave2
from .b2_baselines import bootstrap, metrics
from .data import UNIVERSE, load
from .engine import Costs, run
from .wave1 import Panel, spreads

FAMILIES = {"S06": ["S06-P"], "S07": ["S07-A", "S07-B"], "S09": ["S09-A", "S09-B"], "S14": ["S14-A", "S14-B"],
            "S16": ["S16-A", "S16-B"]}
STOCK_MONTHLY = {"S06-P", "S07-A", "S07-B"}
ETF = {"S14-A", "S14-B", "S16-A", "S16-B"}
MIN_FILL = 0.5
_G: dict = {}


def build(sid, risk, mo, rng=None, cand=None):
    P, bench = _G["P"], _G["bench"]
    if sid in STOCK_MONTHLY:
        return wave2.monthly_stock(P, sid, bench, rng)
    if sid in ETF:
        o, ex, _ = wave2.etf_rotation(bench, sid, P.start, P.end, rng)
        return o, ex
    c = cand if cand is not None else _G["cand"][sid]
    orders = P.orders(c, sid, risk, mo)
    return orders, P.exits("S08", {o.ticker for o in orders})        # S09: Ausstieg wie S08 (Schluss < 20-T.-Tief)


def depot(sid, orders, ex, cash, mo, costs):
    frames = _G["etf_frames"] if sid in ETF else _G["P"].raw
    cur = _G["etf_cur"] if sid in ETF else _G["cur"]
    return run(frames, cur, _G["fx"], orders, cash, costs, mo, calendar=_G["cal"], exit_when=ex, min_fill=MIN_FILL)


def _mo(sid, cash):
    if sid in STOCK_MONTHLY:
        return 10
    if sid in ETF:
        return 3
    return 5 if cash == 5000 else 10


def _null(args):
    sid, seed = args
    rng = np.random.default_rng(seed)
    if sid.startswith("S09"):
        orders, ex = build(sid, 0.01, 5, cand=wave2.s09_null(_G["P"], _G["cand"][sid], seed))
    else:
        orders, ex = build(sid, None, _mo(sid, 5000), rng=rng)
    m = metrics(depot(sid, orders, ex, 5000, _mo(sid, 5000), _G["base"]))
    return sid, seed, {k: m.get(k) for k in ("cagr", "max_dd", "sharpe", "avg_r_net", "trades", "win_rate", "final_eur")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--family", required=True, choices=list(FAMILIES))
    ap.add_argument("--out", default="c2_out")
    ap.add_argument("--seeds", type=int, default=200)
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
    base = Costs(fee_eur=0.99, spread=0.001, spread_by_ticker=sp)
    stress = Costs(fee_eur=1.99, spread=0.002, slippage=0.0005, fx_fee=0.001, spread_by_ticker={k: 2 * v for k, v in sp.items()})
    etf_frames = {t: bench[t][["Open", "High", "Low", "Close", "AdjClose"]] for t in wave2.SECTORS + ["SPY", "EFA", "QQQ", "SHY"]}
    cand = {sid: wave2.s09_candidates(P, sid) for sid in FAMILIES[a.family] if sid.startswith("S09")}
    for sid, c in cand.items():
        print(f"{sid}: {len(c)} Kandidaten, {c['ticker'].nunique()} Titel", flush=True)
    _G.update(P=P, bench=bench, cur=cur, fx=fx, cal=cal, base=base, cand=cand, etf_frames=etf_frames,
              etf_cur={t: "USD" for t in etf_frames})
    acwi = bench["ACWI"]
    acwi_r = (acwi["AdjClose"] / fx["USD"].reindex(acwi.index, method="ffill")).pct_change()
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        commit = None
    results, log = {}, []

    def record(name, sid, res, cfg):
        m = metrics(res, acwi_r)
        m.update(bootstrap(res))
        results[name] = {"sid": sid, "config": cfg, "metrics": m}
        log.append({"id": f"C2-{a.family}-{len(log) + 1:03d}", "name": name, "period": "train", "config": cfg, "commit": commit,
                    "protocol": "v1.2", "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "cagr": m.get("cagr"), "max_dd": m.get("max_dd"), "sharpe": m.get("sharpe"), "trades": m.get("trades")})
        print(f"{name}: CAGR {m.get('cagr', 0):+.2%} · MaxDD {m.get('max_dd', 0):.1%} · Sharpe {m.get('sharpe')} · "
              f"Trades {m.get('trades')} · {m['checks']}", flush=True)

    for sid in FAMILIES[a.family]:
        stop = sid.startswith("S09")
        for cash in (5000, 20000):
            mo = _mo(sid, cash)
            for risk in ((0.01, 0.005) if stop else (None,)):
                orders, ex = build(sid, risk, mo)
                lbl = f"{sid} · {cash} €" + (f" · Risiko {risk:.1%}" if stop else "")
                res = depot(sid, orders, ex, cash, mo, base)
                record(lbl, sid, res, {"cash": cash, "max_open": mo, "risk": risk, "costs": "base", "min_fill": MIN_FILL})
                if cash == 5000:
                    res.trades.to_csv(out / f"trades_{sid}_{risk}.csv", index=False)
                    record(lbl + " · Kostenstress", sid, depot(sid, orders, ex, cash, mo, stress),
                           {"cash": cash, "max_open": mo, "risk": risk, "costs": "stress", "min_fill": MIN_FILL})
    with Pool() as pool:
        nulls = pool.map(_null, [(sid, s) for sid in FAMILIES[a.family] for s in range(a.seeds)], chunksize=2)
    for sid in FAMILIES[a.family]:
        arr = pd.DataFrame([{"seed": s, **m} for x, s, m in nulls if x == sid])
        refname = f"{sid} · 5000 €" + (" · Risiko 1.0%" if sid.startswith("S09") else "")
        ref = results[refname]["metrics"]
        summ = {"n": int(len(arr)), "cagr_median": float(arr["cagr"].median()),
                "cagr_p05_p95": [float(arr["cagr"].quantile(.05)), float(arr["cagr"].quantile(.95))],
                "sharpe_median": float(arr["sharpe"].median()) if arr["sharpe"].notna().any() else None,
                "max_dd_median": float(arr["max_dd"].median()), "trades_median": float(arr["trades"].median()),
                "p_cagr": float((arr["cagr"] >= ref["cagr"]).mean()),
                "p_sharpe": float((arr["sharpe"].fillna(-9) >= (ref.get("sharpe") or -9)).mean())}
        results[f"Null {sid} (200 Seeds) · 5000 €"] = {"sid": sid, "config": {"seeds": a.seeds, "ref": refname}, "summary": summ}
        log.append({"id": f"C2-{a.family}-{len(log) + 1:03d}", "name": f"Null {sid}", "period": "train", "seeds": a.seeds,
                    "commit": commit, "protocol": "v1.2", "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **summ})
        arr.to_csv(out / f"null_{sid}.csv", index=False)
        print(f"Null {sid}: {summ}", flush=True)
    (out / f"c2_{a.family}.json").write_text(json.dumps(results, indent=1, default=str, ensure_ascii=False))
    (out / f"c2_{a.family}_experiments.jsonl").write_text("\n".join(json.dumps(x, default=str, ensure_ascii=False) for x in log) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
