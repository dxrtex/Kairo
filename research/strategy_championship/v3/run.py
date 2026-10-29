"""Protokoll v3.0 – Läufe für K1–K4, Zufall und Benchmarks (27_PROTOCOL_V3.md).

python -m research.strategy_championship.v3.run main     --data DIR --sec DIR [--splits FILE] --period v3_train --out OUT
python -m research.strategy_championship.v3.run null     --data DIR --sec DIR [--splits FILE] --period v3_trainval --seed-start 0 --seed-n 25 --out OUT
python -m research.strategy_championship.v3.run combine  --inp DIR --out OUT
"""

from __future__ import annotations

import argparse
import json
import os
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

from ..b2_baselines import metrics
from ..data import PERIODS, UNIVERSE, load
from ..engine import FX, Costs, Order, run
from ..wave1 import Panel, spreads
from ..wave2 import etf_rotation
from . import bench as B
from . import fundamentals as FU
from . import strategies as S
from . import tax as T

IDS = ["K1", "K2", "K3", "K4"]
CAPS = (5000, 20000)
ETFS = ("ACWI", "SPY", "EFA", "QQQ", "SHY", "BIL")
_G: dict = {}


def setup(a) -> None:
    t0 = time.time()
    prices, cur, fx, bench, (start, end) = load(a.data, a.period)
    sec = Path(a.sec)
    cmap = pd.read_csv(sec / "cik_map.csv")
    t2c = {t: int(c) for t, c in zip(cmap["ticker"], cmap["cik"]) if t in prices}
    c2t = {c: t for t, c in t2c.items()}
    uni = pd.read_csv(UNIVERSE)
    region = dict(zip(uni["ticker"], uni["region"]))
    prices = {t: prices[t] for t in t2c}
    P = Panel(prices, cur, region, bench, start, end)
    t2c = {t: c for t, c in t2c.items() if t in P.F}
    c2t = {c: t for t, c in t2c.items()}
    tlp = sec / "fund_timeline.csv.gz"
    if tlp.exists():
        tl = pd.read_csv(tlp, parse_dates=["filed", "avail", "shares_end"])
    else:
        f = pd.read_csv(sec / "fund.csv.gz", dtype={"val": str, "start": str, "end": str, "filed": str})
        f["start"] = f["start"].fillna("")
        tl = FU.build(f)
    filings = pd.read_csv(sec / "filings.csv.gz", dtype={"items": str})
    ins = pd.read_csv(sec / "insider_buys.csv.gz", dtype={"role": str, "owner": str})
    splits, adj = None, True
    if a.splits and Path(a.splits).exists():
        splits = pd.read_csv(a.splits, parse_dates=["date"])
        chk = Path(a.splits).with_suffix(".json")
        if chk.exists():
            adj = bool(json.loads(chk.read_text()).get("close_is_split_adjusted", True))
    cal = pd.DatetimeIndex(sorted(set().union(*[f.index[(f.index >= start) & (f.index <= end)] for f in P.raw.values()])))
    sp = spreads(P.raw, cur, region)
    costs = {"prime": Costs(fee_eur=0.99, spread=0.001, spread_by_ticker=sp, fee_free_from=250.0),
             "prime_stress": Costs(fee_eur=1.99, spread=0.002, slippage=0.0005, fx_fee=0.001, fee_free_from=250.0,
                                   spread_by_ticker={k: 2 * v for k, v in sp.items()})}
    etf = {t: bench[t][["Open", "High", "Low", "Close", "AdjClose"]].dropna() for t in ETFS if t in bench}
    spy = bench["SPY"]["AdjClose"]
    mt = S.month_table(P, tl, t2c, splits, adj)
    ev, k3 = S.pead_events(P, filings, c2t, spy)
    k4 = S.insider_signals(P, ins, c2t)
    _G.update(P=P, cur=cur, fx=fx, cal=cal, costs=costs, etf=etf, t2c=t2c, mt=mt, k3=k3, k4=k4, ev=ev, start=start, end=end,
              us=set(t2c), period=a.period, splits_ok=splits is not None, close_split_adjusted=adj)
    print(f"Setup {a.period}: {len(P.F)} US-Titel mit CIK, Monatszeilen {len(mt)}, 8-K-Ereignisse {len(ev)}, "
          f"K3-Signale {len(k3)}, K4-Signale {len(k4)} ({time.time() - t0:.0f} s)", flush=True)


def orders_for(sid: str, rng=None):
    if sid in ("K1", "K2"):
        o, ex, info = S.monthly_orders(_G["mt"], sid, rng)
        return o, ex
    sig = _G["k3"] if sid == "K3" else _G["k4"]
    if rng is None:
        return S.event_orders(sig, sid, "ear" if sid == "K3" else "value_usd"), None
    return S.event_null(_G["P"], sig, _G["us"], rng, sid), None


def fx_rate(cur, d):
    return FX(_G["fx"]).rate(cur, np.datetime64(pd.Timestamp(d), "ns"))


def sim(sid: str, cash: float, cn: str, rng=None):
    o, ex = orders_for(sid, rng)
    return run(_G["P"].raw, _G["cur"], _G["fx"], o, cash, _G["costs"][cn], 10, calendar=_G["cal"], exit_when=ex, min_fill=0.5)


def with_tax(res, prices) -> dict:
    yrs = T.yearly_from_engine(res, prices, fx_rate)
    return T.after_tax(res.equity, T.taxes(yrs))


def _main_job(args):
    sid, cash, cn = args
    if sid in IDS:
        r = sim(sid, cash, cn)
        px = _G["P"].raw
    else:
        e, ecur = _G["etf"], {t: "USD" for t in _G["etf"]}
        if sid == "ACWI":
            r = run(e, ecur, _G["fx"], [Order(_G["cal"][0], "ACWI", weight=0.995)], cash, _G["costs"][cn], 1, calendar=_G["cal"])
        elif sid == "S16-B":
            o, ex, _ = etf_rotation(e, "S16-B", _G["start"], _G["end"])
            r = run(e, ecur, _G["fx"], o, cash, _G["costs"][cn], 3, calendar=_G["cal"], exit_when=ex, min_fill=0.5)
        else:                                       # 70/30
            b = B.run_7030(e, _G["fx"], _G["start"], _G["end"], cash, _G["costs"][cn])
            m = {"cagr": None}
            eq = b["equity"]
            yrs = (eq.index[-1] - eq.index[0]).days / 365.25
            rr = eq.pct_change().dropna()
            dd = eq / eq.cummax() - 1
            m = {"start": str(eq.index[0].date()), "end": str(eq.index[-1].date()), "final_eur": float(eq.iloc[-1]),
                 "cagr": float((eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1), "max_dd": float(dd.min()),
                 "sharpe": float(rr.mean() / rr.std() * np.sqrt(252)), "sortino": float(rr.mean() / rr[rr < 0].std() * np.sqrt(252))}
            m.update(T.after_tax(eq, T.taxes(b["years"])))
            return (sid, cash, cn), m, eq
        px = e
    acwi = _G.get("acwi_ret")
    m = metrics(r, acwi)
    m.update(with_tax(r, px))
    if sid in IDS and len(r.trades):
        yr = r.equity.resample("YE").last().pct_change().dropna()
        m["jahre_positiv"] = f"{int((yr > 0).sum())}/{len(yr)}"
        t = r.trades.sort_values("pnl_eur", ascending=False)
        k = max(1, int(round(len(t) * 0.01)))
        m["ohne_top1pct_eur"] = round(float(t["pnl_eur"].iloc[k:].sum()), 2)
        m["by_year_cagr"] = {int(y.year): float(v) for y, v in r.equity.resample("YE").last().pct_change().dropna().items()}
    m["checks_ok"] = all(v for v in r.checks.values() if isinstance(v, bool)) if r.checks else True
    return (sid, cash, cn), m, r.equity


def cmd_main(a) -> int:
    setup(a)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    e = _G["etf"]["ACWI"]["AdjClose"]
    _G["acwi_ret"] = (e / FX(_G["fx"]).rate("USD", np.datetime64(e.index[0], "ns"))).pct_change()  # nur Beta (≈)
    ids = a.only or (IDS + ["ACWI", "S16-B", "70/30"])
    jobs = [(s, c, cn) for s in ids for c in CAPS for cn in ("prime", "prime_stress")]
    with Pool(int(os.environ.get("NPROC", os.cpu_count() or 2))) as pool:
        rr = pool.map(_main_job, jobs, chunksize=1)
    res = {f"{k[0]} · {k[1]} € · {k[2]}": m for k, m, _ in rr}
    curves = pd.DataFrame({f"{k[0]} · {k[1]} · {k[2]}": eq for k, _, eq in rr})
    info = {"period": a.period, "start": str(_G["start"].date()), "end": str(_G["end"].date()), "n_us_cik": len(_G["us"]),
            "splits_ok": _G["splits_ok"], "close_split_adjusted": _G["close_split_adjusted"], "k3_signals": len(_G["k3"]), "k4_signals": len(_G["k4"]),
            "k3_events_total": len(_G["ev"]),
            "pool_per_year_K1": _G["mt"].groupby(_G["mt"]["date"].dt.year)["ticker"].nunique().to_dict(),
            "month_pool_median": {sid: float(np.median([len(S.score_month(g, sid)) for _, g in _G["mt"].groupby("date")]))
                                  for sid in ("K1", "K2")}}
    (out / f"v3_main_{a.period}.json").write_text(json.dumps({"info": info, "results": res}, indent=1, default=str, ensure_ascii=False))
    curves.to_csv(out / f"v3_curves_{a.period}.csv.gz")
    _G["k3"].to_csv(out / f"v3_k3_signals_{a.period}.csv", index=False)
    _G["k4"].to_csv(out / f"v3_k4_signals_{a.period}.csv", index=False)
    for s in ids:
        b, st = res[f"{s} · 5000 € · prime"], res[f"{s} · 5000 € · prime_stress"]
        print(f"{s:6s} 5k CAGR {b['cagr']:+.1%} Stress {st['cagr']:+.1%} DD {b['max_dd']:.0%} Sharpe {b.get('sharpe') or 0:.2f} "
              f"nachSt.(Stress) {st['cagr_after_tax']:+.1%} Trades {b.get('trades', '-')}", flush=True)
    return 0


def _null_job(args):
    sid, seed = args
    r = sim(sid, 5000, "prime", np.random.default_rng(10_000 * (IDS.index(sid) + 1) + seed))
    e = r.equity
    yrs = (e.index[-1] - e.index[0]).days / 365.25
    return sid, seed, float((e.iloc[-1] / e.iloc[0]) ** (1 / yrs) - 1)


def cmd_null(a) -> int:
    setup(a)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    ids = a.only or IDS
    jobs = [(s, k) for s in ids for k in range(a.seed_start, a.seed_start + a.seed_n)]
    with Pool(int(os.environ.get("NPROC", os.cpu_count() or 2))) as pool:
        rr = pool.map(_null_job, jobs, chunksize=1)
    res = {}
    for sid, seed, c in rr:
        res.setdefault(sid, {})[seed] = c
    (out / f"v3_null_{a.period}_{a.seed_start}.json").write_text(json.dumps(res, indent=1))
    print({s: float(np.median(list(v.values()))) for s, v in res.items()})
    return 0


def cmd_combine(a) -> int:
    inp, out = Path(a.inp), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    main = {p: json.loads((inp / f"v3_main_{p}.json").read_text()) for p in ("v3_train", "v3_validation", "v3_trainval", "v3_holdout")
            if (inp / f"v3_main_{p}.json").exists()}
    null: dict = {}
    for f in sorted(inp.glob("v3_null_v3_trainval_*.json")):
        for sid, v in json.loads(f.read_text()).items():
            null.setdefault(sid, {}).update(v)
    alpha = 0.05 / len(IDS)
    dec = {}
    for sid in IDS:
        g = lambda p, cap, cn: main[p]["results"].get(f"{sid} · {cap} € · {cn}") if p in main else None
        acw = lambda p, cn: main[p]["results"].get(f"ACWI · 5000 € · {cn}") if p in main else None
        tr, va, tv = g("v3_train", 5000, "prime_stress"), g("v3_validation", 5000, "prime_stress"), g("v3_trainval", 5000, "prime")
        ns = np.array(list(null.get(sid, {}).values()))
        p = float(((ns >= tv["cagr"]).sum() + 1) / (len(ns) + 1)) if len(ns) and tv else None
        tvs = g("v3_trainval", 5000, "prime_stress")
        ok = {
            "1_stress_cagr_pos_train_val": bool(tr and va and tr["cagr"] > 0 and va["cagr"] > 0),
            "2_stress_cagr_gt_acwi_train_val": bool(tr and va and tr["cagr"] > acw("v3_train", "prime_stress")["cagr"]
                                                     and va["cagr"] > acw("v3_validation", "prime_stress")["cagr"]),
            "3_p_vs_zufall": p, "3_ok": bool(p is not None and p <= alpha),
            "4_after_tax_gt_acwi": bool(tvs and tvs["cagr_after_tax"] > acw("v3_trainval", "prime_stress")["cagr_after_tax"]),
            "5_umfang_train": (g("v3_train", 5000, "prime") or {}).get("trades"),
        }
        n_min = 100 if sid in ("K3", "K4") else 0
        ok["5_ok"] = bool((ok["5_umfang_train"] or 0) >= n_min) if sid in ("K3", "K4") else True
        ok["zufall_median"] = float(np.median(ns)) if len(ns) else None
        ok["zufall_n"] = int(len(ns))
        ok["bestanden"] = bool(ok["1_stress_cagr_pos_train_val"] and ok["2_stress_cagr_gt_acwi_train_val"] and ok["3_ok"]
                               and ok["4_after_tax_gt_acwi"] and ok["5_ok"])
        dec[sid] = ok
    (out / "v3_results.json").write_text(json.dumps({"alpha_bonferroni": alpha, "entscheidung": dec, "main": main}, indent=1,
                                                    default=str, ensure_ascii=False))
    print(json.dumps(dec, indent=1, default=str))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["main", "null", "combine"])
    ap.add_argument("--data")
    ap.add_argument("--sec")
    ap.add_argument("--splits", default=None)
    ap.add_argument("--period", default="v3_train", choices=[k for k in PERIODS if k.startswith("v3_")])
    ap.add_argument("--out", default="v3_out")
    ap.add_argument("--inp", default="v3_out")
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--seed-start", type=int, default=0)
    ap.add_argument("--seed-n", type=int, default=25)
    a = ap.parse_args(argv)
    return {"main": cmd_main, "null": cmd_null, "combine": cmd_combine}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
