"""Phase D – Kern + Satellit auf Train + Validierung 2008–2021 (Plan: 10_PHASE_D_PLAN.md).

python -m research.strategy_championship.d_run --data DIR --out OUT      (braucht KAIRO_VALIDATION_UNSEALED=1)

Jeder Topf wird einzeln mit der Engine gerechnet (eigenes Startkapital, echte Gebühren), die Depotwerte werden täglich
addiert (keine Umschichtung). Kennzahlen gesamt und je Abschnitt (Train 2008–2016, Validierung 2017–2021).
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
from .data import UNIVERSE, load
from .engine import Costs, Order, run
from .v_run import s13_orders
from .wave1 import Panel, spreads

CORES = ["S13-ETF", "ACWI", "S16-B"]
SATS = ["S07-B", "S07-B-T"]
SHARES = [0.2, 0.3, 0.4]
CAPS = [5000, 10000, 20000]
SPLIT = pd.Timestamp("2016-12-31")
_G: dict = {}


def orders_for(sid):
    P, bench, (start, end), fx = _G["P"], _G["bench"], _G["per"], _G["fx"]
    if sid == "S13-ETF":
        return s13_orders(bench["ACWI"], fx["USD"], start, end)
    if sid == "ACWI":
        return [Order(_G["cal"][0], "ACWI", weight=0.995, tag="ACWI")], {}
    if sid == "S16-B":
        o, ex, _ = wave2.etf_rotation(bench, "S16-B", start, end)
        return o, ex
    if sid == "S07-B":
        return wave2.monthly_stock(P, "S07-B", bench)
    if sid == "S07-B-T":
        return wave2.monthly_stock(P, "S07-B", bench, regime=_G["regime"])
    raise KeyError(sid)


def _sleeve(args):
    sid, cash, cname = args
    o, ex = _G["orders"][sid]
    etf = sid in CORES
    res = run(_G["etf_frames"] if etf else _G["P"].raw, _G["etf_cur"] if etf else _G["cur"], _G["fx"], o, cash,
              _G["costs"][cname], 1 if etf and sid != "S16-B" else (3 if etf else 10), calendar=_G["cal"], exit_when=ex,
              min_fill=0.5)
    return (sid, cash, cname), res.equity, res.checks, len(res.trades), float(res.trades[["fees_eur", "spread_eur"]].sum().sum()) if len(res.trades) else 0.0


def stats(e: pd.Series) -> dict:
    e = e.dropna()
    yrs = (e.index[-1] - e.index[0]).days / 365.25
    r = e.pct_change().dropna()
    dd = e / e.cummax() - 1
    return {"cagr": float((e.iloc[-1] / e.iloc[0]) ** (1 / yrs) - 1), "max_dd": float(dd.min()),
            "sharpe": float(r.mean() / r.std() * np.sqrt(252)) if r.std() > 0 else None,
            "worst_year": float(e.resample("YE").last().pct_change().min()) if len(e) > 300 else None,
            "final": float(e.iloc[-1])}


def seg(e: pd.Series) -> dict:
    return {"gesamt": stats(e), "train": stats(e[e.index <= SPLIT]), "validierung": stats(e[e.index > SPLIT])}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default="d_out")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    prices, cur, fx, bench, (start, end) = load(a.data, "trainval")
    uni = pd.read_csv(UNIVERSE)
    region = dict(zip(uni["ticker"], uni["region"]))
    P = Panel(prices, cur, region, bench, start, end)
    wave2.extra(P)
    cal = pd.DatetimeIndex(sorted(set().union(*[f.index[(f.index >= start) & (f.index <= end)] for f in P.raw.values()])))
    sp = spreads(P.raw, cur, region)
    costs = {"base": Costs(fee_eur=0.99, spread=0.001, spread_by_ticker=sp),
             "stress": Costs(fee_eur=1.99, spread=0.002, slippage=0.0005, fx_fee=0.001, spread_by_ticker={k: 2 * v for k, v in sp.items()})}
    etf_frames = {t: bench[t][["Open", "High", "Low", "Close", "AdjClose"]] for t in ["SPY", "EFA", "QQQ", "SHY", "ACWI"]}
    s13o, s13x = s13_orders(bench["ACWI"], fx["USD"], start, end)
    # Regime für S07-B-T: Monatsenden, an denen S13-ETF investiert ist (gleiche Regel)
    acwi = (bench["ACWI"]["AdjClose"] / fx["USD"].reindex(bench["ACWI"].index, method="ffill")).dropna()
    acwi = acwi[acwi.index <= end]
    me = acwi.groupby(acwi.index.to_period("M")).tail(1)
    on_months = {p for p, ok in zip(me.index.to_period("M"), (me > me.rolling(10).mean()).to_numpy()) if ok}
    regime = {d for d in wave2._month_ends(P) if pd.Timestamp(d).to_period("M") in on_months}
    _G.update(P=P, bench=bench, per=(start, end), fx=fx, cal=cal, cur=cur, costs=costs, etf_frames=etf_frames,
              etf_cur={t: "USD" for t in etf_frames}, regime=regime)
    _G["orders"] = {sid: orders_for(sid) for sid in CORES + SATS}
    amounts = sorted({round(c * s) for c in CAPS for s in SHARES + [1 - x for x in SHARES] + [1.0]})
    jobs = [(sid, amt, cn) for sid in CORES + SATS for amt in amounts for cn in costs]
    with Pool() as pool:
        rr = pool.map(_sleeve, jobs, chunksize=1)
    eq = {k: e for k, e, *_ in rr}
    info = {f"{k[0]}|{k[1]}|{k[2]}": {"checks": c, "trades": n, "costs_eur": round(cst, 2)} for k, _, c, n, cst in rr}
    idx = cal

    def curve(sid, amt, cn):
        return eq[(sid, amt, cn)].reindex(idx).ffill().bfill()

    results = {}
    for cap in CAPS:
        for cn in costs:
            for sid in CORES + SATS:
                results[f"{sid} rein · {cap} € · {cn}"] = seg(curve(sid, cap, cn))
            for core in CORES:
                for sat in SATS:
                    for sh in SHARES:
                        e = curve(core, round(cap * (1 - sh)), cn) + curve(sat, round(cap * sh), cn)
                        results[f"{core} + {int(sh * 100)} % {sat} · {cap} € · {cn}"] = seg(e)
    # Auswahl nach Plan
    pick = {}
    for fam, cores in (("K1/K2", ["S13-ETF", "ACWI"]), ("K3", ["S16-B"])):
        cands = []
        for core in cores:
            pure = results[f"{core} rein · 5000 € · base"]["gesamt"]["cagr"]
            for sat in SATS:
                for sh in SHARES:
                    n = f"{core} + {int(sh * 100)} % {sat} · 5000 € · "
                    b, s = results[n + "base"]["gesamt"], results[n + "stress"]["gesamt"]
                    if b["max_dd"] >= -0.20 and s["max_dd"] >= -0.22 and b["cagr"] > pure:
                        cands.append((b["cagr"], b["sharpe"] or 0, n.strip(" ·")))
        cands.sort(reverse=True)
        best = None
        if cands:
            best = cands[0]
            for c in cands[1:]:
                if best[0] - c[0] < 0.005 and c[1] > best[1]:
                    best = c
        pick[fam] = {"auswahl": best[2] if best else None, "kandidaten_regelkonform": [c[2] for c in cands]}
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        commit = None
    (out / "d_results.json").write_text(json.dumps({"results": results, "pick": pick, "sleeves": info, "commit": commit,
                                                    "ts": datetime.now(timezone.utc).isoformat(timespec="seconds")},
                                                   indent=1, ensure_ascii=False, default=str))
    pd.DataFrame({f"{k[0]}|{k[1]}|{k[2]}": v.reindex(idx) for k, v in eq.items() if k[1] in (1000, 1500, 2000, 3500, 4000, 5000)}).to_csv(out / "d_equity_5k.csv")
    print(json.dumps(pick, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
