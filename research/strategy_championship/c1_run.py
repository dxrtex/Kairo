"""Phase C, Welle 1 – Screening einer Strategie-Familie im Entwicklungszeitraum (Train 2008–2016), Protokoll v1.1.

python -m research.strategy_championship.c1_run --data DIR --family S02 --out OUT [--seeds 200]

Je Variante: Depots 5.000 € (max. 5) und 20.000 € (max. 10), Risiko 1 % / 0,5 % (Stop-Strategien) bzw. Gewicht
(S05, S13-S), Basiskosten + Kostenstress (5.000 €), Mindestgröße 50 % (v1.1). Zufalls-Null mit denselben Regeln,
200 Seeds (5.000 €, 1 % bzw. Gewicht). Jeder Lauf ins Register.
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

from .b2_baselines import bootstrap, metrics
from .data import UNIVERSE, load
from .engine import Costs, run
from .wave1 import Panel, spreads

FAMILIES = {"S02": ["S02-A", "S02-B"], "S03": ["S03-P"], "S04": ["S04-M"], "S05": ["S05-A", "S05-B"],
            "S08": ["S08-A", "S08-B"], "S11": ["S11-A", "S11-B"], "S13": ["S13-S"]}
WEIGHT = {"S05-A", "S05-B", "S13-S"}
MIN_FILL = 0.5
_G: dict = {}


def _depot(sid, orders, exits, cash, mo, costs):
    P = _G["P"]
    return run(P.raw_ema, _G["cur"], _G["fx"], orders, cash, costs, mo, calendar=_G["cal"], exit_when=exits, min_fill=MIN_FILL)


def build(sid, risk, cash, mo, rng=None, cand=None):
    P = _G["P"]
    if sid.startswith("S05"):
        orders, ex = P.monthly(sid, rng)
        return orders, ex
    c = cand if cand is not None else _G["cand"][sid]
    orders = P.orders(c, sid, risk, mo)
    ex = P.exits(sid, {o.ticker for o in orders})
    return orders, ex


def _null(args):
    sid, seed = args
    P = _G["P"]
    if sid.startswith("S05"):
        orders, ex = build(sid, None, 5000, 10, rng=np.random.default_rng(seed))
        mo = 10
    else:
        nc = P.null_candidates(_G["cand"][sid], sid, seed)
        mo = 5
        orders, ex = build(sid, 0.01, 5000, mo, cand=nc)
    res = _depot(sid, orders, ex, 5000, mo, _G["base"])
    m = metrics(res)
    return sid, seed, {k: m.get(k) for k in ("cagr", "max_dd", "sharpe", "avg_r_net", "trades", "win_rate", "final_eur")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--family", required=True, choices=list(FAMILIES))
    ap.add_argument("--out", default="c1_out")
    ap.add_argument("--seeds", type=int, default=200)
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    prices, cur, fx, bench, (start, end) = load(a.data, "train")
    uni = pd.read_csv(UNIVERSE)
    region = dict(zip(uni["ticker"], uni["region"]))
    P = Panel(prices, cur, region, bench, start, end)
    P.raw_ema = {t: df for t, df in P.raw.items()}
    cal = pd.DatetimeIndex(sorted(set().union(*[f.index[(f.index >= start) & (f.index <= end)] for f in P.raw.values()])))
    sp = spreads(P.raw, cur, region)
    base = Costs(fee_eur=0.99, spread=0.001, spread_by_ticker=sp)
    stress = Costs(fee_eur=1.99, spread=0.002, slippage=0.0005, fx_fee=0.001, spread_by_ticker={k: 2 * v for k, v in sp.items()})
    cand = {sid: P.candidates(sid) for sid in FAMILIES[a.family] if not sid.startswith("S05")}
    for sid, c in cand.items():
        print(f"{sid}: {len(c)} Kandidaten, {c['date'].nunique() if len(c) else 0} Tage, {c['ticker'].nunique() if len(c) else 0} Titel", flush=True)
    _G.update(P=P, cur=cur, fx=fx, cal=cal, base=base, cand=cand)
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
        log.append({"id": f"C1-{a.family}-{len(log) + 1:03d}", "name": name, "period": "train", "config": cfg, "commit": commit,
                    "protocol": "v1.1", "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "cagr": m.get("cagr"), "max_dd": m.get("max_dd"), "sharpe": m.get("sharpe"), "trades": m.get("trades")})
        print(f"{name}: CAGR {m.get('cagr', 0):+.2%} · MaxDD {m.get('max_dd', 0):.1%} · Sharpe {m.get('sharpe')} · "
              f"Trades {m.get('trades')} · Ø R {m.get('avg_r_net')} · {m['checks']}", flush=True)

    for sid in FAMILIES[a.family]:
        w = sid in WEIGHT
        for cash, mo in ((5000, 5), (20000, 10)):
            mo_ = 10 if sid.startswith("S05") else mo
            for risk in ((None,) if w else (0.01, 0.005)):
                orders, ex = build(sid, risk, cash, mo_)
                lbl = f"{sid} · {cash} €" + ("" if w else f" · Risiko {risk:.1%}")
                res = _depot(sid, orders, ex, cash, mo_, base)
                record(lbl, sid, res, {"cash": cash, "max_open": mo_, "risk": risk, "costs": "base", "min_fill": MIN_FILL})
                if cash == 5000:
                    res.trades.to_csv(out / f"trades_{sid}_{risk}.csv", index=False)
                    res = _depot(sid, orders, ex, cash, mo_, stress)
                    record(lbl + " · Kostenstress", sid, res, {"cash": cash, "max_open": mo_, "risk": risk, "costs": "stress",
                                                                "min_fill": MIN_FILL})
    jobs = [(sid, s) for sid in FAMILIES[a.family] for s in range(a.seeds)]
    with Pool() as pool:
        nulls = pool.map(_null, jobs, chunksize=2)
    for sid in FAMILIES[a.family]:
        arr = pd.DataFrame([{"seed": s, **m} for x, s, m in nulls if x == sid])
        refname = f"{sid} · 5000 €" + ("" if sid in WEIGHT else " · Risiko 1.0%")
        ref = results[refname]["metrics"]
        summ = {"n": int(len(arr)), "cagr_median": float(arr["cagr"].median()),
                "cagr_p05_p95": [float(arr["cagr"].quantile(.05)), float(arr["cagr"].quantile(.95))],
                "sharpe_median": float(arr["sharpe"].median()) if arr["sharpe"].notna().any() else None,
                "max_dd_median": float(arr["max_dd"].median()), "trades_median": float(arr["trades"].median()),
                "p_cagr": float((arr["cagr"] >= ref["cagr"]).mean()),
                "p_sharpe": float((arr["sharpe"].fillna(-9) >= (ref.get("sharpe") or -9)).mean())}
        results[f"Null {sid} (200 Seeds) · 5000 €"] = {"sid": sid, "config": {"seeds": a.seeds, "ref": refname}, "summary": summ}
        log.append({"id": f"C1-{a.family}-{len(log) + 1:03d}", "name": f"Null {sid}", "period": "train", "seeds": a.seeds,
                    "commit": commit, "protocol": "v1.1", "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **summ})
        arr.to_csv(out / f"null_{sid}.csv", index=False)
        print(f"Null {sid}: {summ}", flush=True)
    (out / f"c1_{a.family}.json").write_text(json.dumps(results, indent=1, default=str, ensure_ascii=False))
    (out / f"c1_{a.family}_experiments.jsonl").write_text("\n".join(json.dumps(x, default=str, ensure_ascii=False) for x in log) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
