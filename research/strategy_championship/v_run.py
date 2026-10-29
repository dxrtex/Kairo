"""Gate C – einmalige Validierung 2017–2021 der 8 vorab festgelegten Finalisten (08_VALIDATION_PLAN.md).

python -m research.strategy_championship.v_run --data DIR --finalist S07-B --out OUT [--signals DIR] [--seeds 200]

Braucht KAIRO_VALIDATION_UNSEALED=1. Regeln exakt wie im Train (Protokoll v1.1/v1.2), keine Änderung.
Je Finalist: 5.000 € und 20.000 €, Basis- und Stresskosten, Risiko 1 % und 0,5 % (Stop-Strategien);
Zufalls-Null mit denselben Regeln, 200 Seeds, bei 5.000 € und 20.000 € (Stop-Strategien mit 1 %).
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

from . import s01, wave2
from .b2_baselines import bootstrap, metrics
from .data import UNIVERSE, load
from .engine import Costs, Order, run
from .wave1 import Panel, spreads

FINALISTS = ["S13-ETF", "S16-B", "S16-A", "S07-B", "S05-B", "S01-B", "S02-B", "S08-A"]
STOP = {"S01-B", "S02-B", "S08-A"}
ETF = {"S13-ETF", "S16-A", "S16-B", "ACWI"}
MIN_FILL = 0.5
_G: dict = {}


def s13_orders(acwi, fx_usd, start, end):
    """Wie Train: Monatsschluss ACWI (gesamt, EUR) > SMA 10 Monatsschlüsse → investiert. Zustand ab dem ersten
    Monatsende im Zeitraum (SMA aus der Vorgeschichte), Kauf frühestens nach diesem Monatsende."""
    px = (acwi["AdjClose"] / fx_usd.reindex(acwi.index, method="ffill")).dropna()
    px = px[px.index <= end]
    me = px.groupby(px.index.to_period("M")).tail(1)
    sma = me.rolling(10).mean()
    orders, exits, on = [], {}, False
    for d, v in me.items():
        if d < start or not np.isfinite(sma.loc[d]):
            continue
        want = v > sma.loc[d]
        if want and not on:
            orders.append(Order(d, "ACWI", weight=0.995, tag="S13-ETF"))
        if on and not want:
            exits.setdefault("ACWI", []).append(d)
        on = want
    return orders, exits


def s01_orders(sig: pd.DataFrame, risk: float) -> list[Order]:
    P, out = _G["P"], []
    for x in sig.itertuples(index=False):
        if x.ticker not in P.raw:
            continue
        out += s01.base_orders(P.raw[x.ticker], int(x.i), float(x.atr), x.ticker, f"{x.ticker}|{x.date}", "B", risk,
                               prio=-float(x.atr) / float(x.close), adj=_G["adj"][x.ticker])
    return out


def s01_null(sig: pd.DataFrame, seed: int) -> pd.DataFrame:
    P, rng, rows = _G["P"], np.random.default_rng(seed), []
    for d, g in sig.groupby("date"):
        pool = P.pool.get(pd.Timestamp(d))
        if pool is None or not len(pool):
            continue
        for t in rng.choice(pool, min(len(g), len(pool)), replace=False):
            idx = P.raw[t].index
            if pd.Timestamp(d) not in idx:
                continue
            i = int(idx.get_loc(pd.Timestamp(d)))
            rows.append({"ticker": t, "date": pd.Timestamp(d), "i": i, "atr": float(P.F[t]["atr"].iloc[i]),
                         "close": float(P.F[t]["C"].iloc[i])})
    return pd.DataFrame(rows, columns=["ticker", "date", "i", "atr", "close"])


def build(fid, risk, mo, seed=None):
    P, bench, (start, end) = _G["P"], _G["bench"], _G["per"]
    rng = None if seed is None else np.random.default_rng(seed)
    if fid == "S13-ETF":
        return s13_orders(bench["ACWI"], _G["fx"]["USD"], start, end)
    if fid == "ACWI":
        return [Order(_G["cal"][0], "ACWI", weight=0.995, tag="Bench")], {}
    if fid in ("S16-A", "S16-B"):
        o, ex, _ = wave2.etf_rotation(bench, fid, start, end, rng)
        return o, ex
    if fid == "S05-B":
        return P.monthly(fid, rng)
    if fid == "S07-B":
        return wave2.monthly_stock(P, fid, bench, rng)
    if fid == "S01-B":
        sig = _G["sig"] if seed is None else s01_null(_G["sig"], seed)
        orders = s01_orders(sig, risk)
        if seed is not None:
            r2 = np.random.default_rng(seed + 10_000)
            for o in orders:
                o.prio = float(r2.random())
        return orders, {}
    cand = _G["cand"] if seed is None else P.null_candidates(_G["cand"], fid, seed)
    orders = P.orders(cand, fid, risk, mo)
    return orders, P.exits(fid, {o.ticker for o in orders})


def mo_of(fid, cash):
    if fid in ETF:
        return 3
    if fid in ("S05-B", "S07-B"):
        return 10
    return 5 if cash == 5000 else 10


def depot(fid, orders, ex, cash, costs):
    frames = _G["etf_frames"] if fid in ETF else _G["P"].raw_ema
    cur = _G["etf_cur"] if fid in ETF else _G["cur"]
    return run(frames, cur, _G["fx"], orders, cash, costs, mo_of(fid, cash), calendar=_G["cal"], exit_when=ex, min_fill=MIN_FILL)


def _null(args):
    fid, cash, seed = args
    orders, ex = build(fid, 0.01, mo_of(fid, cash), seed)
    m = metrics(depot(fid, orders, ex, cash, _G["base"]))
    return fid, cash, seed, {k: m.get(k) for k in ("cagr", "max_dd", "sharpe", "trades", "final_eur")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--finalist", required=True, choices=FINALISTS + ["ETF"])
    ap.add_argument("--signals")
    ap.add_argument("--out", default="v_out")
    ap.add_argument("--seeds", type=int, default=200)
    ap.add_argument("--period", default="validation", help="nur für Probeläufe: train")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    prices, cur, fx, bench, (start, end) = load(a.data, a.period)
    uni = pd.read_csv(UNIVERSE)
    region = dict(zip(uni["ticker"], uni["region"]))
    fids = ["S13-ETF", "ACWI", "S16-A", "S16-B"] if a.finalist == "ETF" else [a.finalist]
    P = Panel(prices, cur, region, bench, start, end)
    wave2.extra(P)
    P.raw_ema = {t: s01.with_ema(df) for t, df in P.raw.items()} if "S01-B" in fids else P.raw
    cal = pd.DatetimeIndex(sorted(set().union(*[f.index[(f.index >= start) & (f.index <= end)] for f in P.raw.values()])))
    sp = spreads(P.raw, cur, region)
    base = Costs(fee_eur=0.99, spread=0.001, spread_by_ticker=sp)
    stress = Costs(fee_eur=1.99, spread=0.002, slippage=0.0005, fx_fee=0.001, spread_by_ticker={k: 2 * v for k, v in sp.items()})
    etf_frames = {t: bench[t][["Open", "High", "Low", "Close", "AdjClose"]] for t in wave2.SECTORS + ["SPY", "EFA", "QQQ", "SHY", "ACWI"]}
    _G.update(P=P, bench=bench, cur=cur, fx=fx, cal=cal, base=base, per=(start, end), etf_frames=etf_frames,
              etf_cur={t: "USD" for t in etf_frames})
    if "S01-B" in fids:
        sig = pd.concat([pd.read_parquet(p) for p in sorted(Path(a.signals).glob("s01_signals_*.parquet"))], ignore_index=True)
        sig["date"] = pd.to_datetime(sig["date"])
        _G["sig"] = sig[(sig["date"] >= start) & (sig["date"] <= end)].sort_values(["date", "ticker"]).reset_index(drop=True)
        _G["adj"] = {t: s01.adjusted(df) for t, df in P.raw.items()}
        print(f"S01-Signale 2017–2021: {len(_G['sig'])}", flush=True)
    if fids[0] in ("S02-B", "S08-A"):
        _G["cand"] = P.candidates(fids[0])
        print(f"{fids[0]}: {len(_G['cand'])} Kandidaten", flush=True)
    acwi = bench["ACWI"]
    acwi_r = (acwi["AdjClose"] / fx["USD"].reindex(acwi.index, method="ffill")).pct_change()
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        commit = None
    results, log = {}, []
    ts = lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    for fid in fids:
        for cash in (5000, 20000):
            for risk in ((0.01, 0.005) if fid in STOP else (None,)):
                orders, ex = build(fid, risk, mo_of(fid, cash))
                for cname, costs in (("base", base), ("stress", stress)):
                    res = depot(fid, orders, ex, cash, costs)
                    m = metrics(res, acwi_r)
                    m.update(bootstrap(res))
                    name = f"{fid} · {cash} €" + (f" · Risiko {risk:.1%}" if risk else "") + (" · Kostenstress" if cname == "stress" else "")
                    results[name] = {"fid": fid, "config": {"cash": cash, "risk": risk, "costs": cname}, "metrics": m}
                    log.append({"id": f"V-{fid}-{len(log) + 1:03d}", "name": name, "period": a.period, "commit": commit,
                                "protocol": "v1.2", "ts": ts(), "cagr": m.get("cagr"), "max_dd": m.get("max_dd"),
                                "sharpe": m.get("sharpe"), "trades": m.get("trades")})
                    print(f"{name}: CAGR {m.get('cagr', 0):+.2%} · MaxDD {m.get('max_dd', 0):.1%} · Sharpe {m.get('sharpe')} · "
                          f"Trades {m.get('trades')} · {m['checks']}", flush=True)
                    if cname == "base" and (risk in (None, 0.01)):
                        res.trades.to_csv(out / f"vtrades_{fid}_{cash}.csv", index=False)
                        res.equity.to_csv(out / f"vequity_{fid}_{cash}.csv")
    nullable = [f for f in fids if f not in ("S13-ETF", "ACWI")]
    if nullable and a.seeds:
        jobs = [(f, c, s) for f in nullable for c in (5000, 20000) for s in range(a.seeds)]
        with Pool() as pool:
            nulls = pool.map(_null, jobs, chunksize=2)
        for f in nullable:
            for c in (5000, 20000):
                arr = pd.DataFrame([{"seed": s, **m} for x, cc, s, m in nulls if x == f and cc == c])
                ref = results[f"{f} · {c} €" + (" · Risiko 1.0%" if f in STOP else "")]["metrics"]
                summ = {"n": int(len(arr)), "cagr_median": float(arr["cagr"].median()),
                        "cagr_p05_p95": [float(arr["cagr"].quantile(.05)), float(arr["cagr"].quantile(.95))],
                        "sharpe_median": float(arr["sharpe"].median()) if arr["sharpe"].notna().any() else None,
                        "p_cagr": float((arr["cagr"] >= ref["cagr"]).mean()),
                        "p_sharpe": float((arr["sharpe"].fillna(-9) >= (ref.get("sharpe") or -9)).mean())}
                results[f"Null {f} · {c} €"] = {"fid": f, "summary": summ}
                log.append({"id": f"V-{f}-{len(log) + 1:03d}", "name": f"Null {f} · {c} €", "period": a.period,
                            "seeds": a.seeds, "commit": commit, "protocol": "v1.2", "ts": ts(), **summ})
                arr.to_csv(out / f"vnull_{f}_{c}.csv", index=False)
                print(f"Null {f} {c}: {summ}", flush=True)
    tag = a.finalist
    (out / f"v_{tag}.json").write_text(json.dumps(results, indent=1, default=str, ensure_ascii=False))
    (out / f"v_{tag}_experiments.jsonl").write_text("\n".join(json.dumps(x, default=str, ensure_ascii=False) for x in log) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
