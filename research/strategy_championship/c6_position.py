"""Welle 3 Position-Trading (Protokoll v1.9) – monatliche Top-5-Auswahl, Kosten Scalable PRIME+.

python -m research.strategy_championship.c6_position --data DIR --out OUT [--period train|validation] [--only ID ...]

Referenz T1-top5 = S07-B mit 5 Titeln (Momentum 6-1 / Vol 6 M.). Neu (vorab festgelegt, keine weiteren):
  P1 52W   – Nähe zum 52-Wochen-Hoch (Schluss ÷ höchster Schluss 252 T.), Top 5 (George & Hwang 2004)
  P2 KOMBI – Rangmittel aus Momentum 6-1/Vol und 52W-Nähe, Top 5
  P3 VOLSK – T1-top5, Gewicht je Titel × min(1, 15 % ÷ Vol 6 M. des S&P 500) (vereinfachte Volatilitätssteuerung)
  P4 TREND – T1-top5, aber nur Titel über ihrer EMA200 (Trendfilter je Aktie, wie Clenow)
Zufall: 5 zufällige zulässige Titel je Monat (100 Seeds) – gleiche Kosten, gleiche Ausführung.
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
from .engine import Costs, Order, run
from .wave1 import Panel, spreads

N = 5
CAPS = (2000, 5000, 10000)
SEEDS = 100
IDS = ["T1-top5", "P1-52W", "P2-KOMBI", "P3-VOLSK", "P4-TREND"]
_G: dict = {}


def monthly(P, sid: str, bench, rng=None, n: int | None = None) -> tuple[list, dict]:
    n = n or (10 if sid.endswith("top10") else N)
    me = wave2._month_ends(P)
    g = bench["^GSPC"]["Close"]
    mvol = np.log(g).diff().rolling(126).std() * np.sqrt(252)
    tops, orders, ex, prev, wts = {}, [], {}, [], {}
    for d in me:
        pool = P.pool.get(d)
        if pool is None or not len(pool):
            continue
        if rng is not None:
            tops[d] = list(rng.choice(pool, min(n, len(pool)), replace=False))
            wts[d] = 0.99 / n
            continue
        rows = []
        for t in pool:
            f = P.F[t]
            if d not in f.index:
                continue
            r = f.loc[d]
            m = r["mom61"] / r["vol6m"] if r["vol6m"] and np.isfinite(r["vol6m"]) else np.nan
            h = r["C"] / r["c252max"] if r["c252max"] else np.nan
            if sid == "P4-TREND" and not r["C"] > r["ema200"]:
                continue
            rows.append((t, m, h))
        df = pd.DataFrame(rows, columns=["t", "m", "h"]).replace([np.inf, -np.inf], np.nan)
        if sid == "P1-52W":
            df = df.dropna(subset=["h"]).sort_values(["h", "m"], ascending=False)
        elif sid == "P2-KOMBI":
            df = df.dropna(subset=["m", "h"])
            df["s"] = df["m"].rank(pct=True) + df["h"].rank(pct=True)
            df = df.sort_values("s", ascending=False)
        else:
            df = df.dropna(subset=["m"]).sort_values("m", ascending=False)
        tops[d] = df["t"].head(n).tolist()
        w = 0.99 / n
        if sid == "P3-VOLSK":
            v = mvol.asof(pd.Timestamp(d))
            w *= min(1.0, 0.15 / v) if v and np.isfinite(v) else 1.0
        wts[d] = w
    for d, pick in tops.items():
        for t in prev:
            if t not in pick:
                ex.setdefault(t, []).append(d)
        for k, t in enumerate(pick):
            orders.append(Order(d, t, weight=wts[d], prio=-k, tag=sid))
        prev = pick
    return orders, ex


def _job(args):
    sid, cash, cn, seed = args
    if seed is None:
        o, ex = _G["orders"][sid]
    else:
        o, ex = monthly(_G["P"], "null", _G["bench"], np.random.default_rng(seed), _G["null_n"])
    r = run(_G["P"].raw, _G["cur"], _G["fx"], o, cash, _G["costs"][cn], 12, calendar=_G["cal"], exit_when=ex, min_fill=0.5)
    m = metrics(r)
    keep = ("cagr", "max_dd", "sharpe", "trades", "win_rate", "calmar", "worst_year") if seed is None else ("cagr", "max_dd")
    out = {k: m.get(k) for k in keep}
    if seed is None:
        out["checks_ok"] = all(v for v in r.checks.values() if isinstance(v, bool))
        e = r.equity
        yr = e.resample("YE").last().pct_change().dropna()
        out["jahre_positiv"] = f"{int((yr > 0).sum())}/{len(yr)}"
        if len(r.trades):
            t = r.trades.sort_values("pnl_eur", ascending=False)
            k = max(1, int(round(len(t) * 0.01)))
            out["ohne_top1pct_eur"] = round(float(t["pnl_eur"].iloc[k:].sum()), 2)
    return (sid if seed is None else f"null-{seed}", cash, cn), out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default="c6_out")
    ap.add_argument("--period", default="train", choices=["train", "validation", "holdout"])
    ap.add_argument("--only", nargs="*", default=None)
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    prices, cur, fx, bench, (start, end) = load(a.data, a.period)
    uni = pd.read_csv(UNIVERSE)
    region = dict(zip(uni["ticker"], uni["region"]))
    P = Panel(prices, cur, region, bench, start, end)
    wave2.extra(P)
    for f in P.F.values():
        f["c252max"] = f["C"].rolling(252).max()
    cal = pd.DatetimeIndex(sorted(set().union(*[f.index[(f.index >= start) & (f.index <= end)] for f in P.raw.values()])))
    sp = spreads(P.raw, cur, region)
    costs = {"prime": Costs(fee_eur=0.99, spread=0.001, spread_by_ticker=sp, fee_free_from=250.0),
             "prime_stress": Costs(fee_eur=1.99, spread=0.002, slippage=0.0005, fx_fee=0.001, fee_free_from=250.0,
                                   spread_by_ticker={k: 2 * v for k, v in sp.items()})}
    ids = a.only or IDS
    _G.update(P=P, cur=cur, fx=fx, cal=cal, costs=costs, bench=bench, orders={s: monthly(P, s, bench) for s in ids},
              null_n=10 if all(s.endswith("top10") for s in ids) else N)
    jobs = [(s, c, cn, None) for s in ids for c in CAPS for cn in costs]
    jobs += [("null", 5000, "prime", s) for s in range(SEEDS)]
    with Pool() as pool:
        rr = pool.map(_job, jobs, chunksize=1)
    res = {f"{k[0]} · {k[1]} € · {k[2]}": v for k, v in rr if not k[0].startswith("null")}
    null = np.array([v["cagr"] for k, v in rr if k[0].startswith("null")])
    for s in ids:
        c = res[f"{s} · 5000 € · prime"]["cagr"]
        res[f"{s} · 5000 € · prime"]["p_zufall"] = float((null >= c).mean())
    summ = {"period": a.period, "zufall_median_cagr": float(np.median(null)), "zufall_p90_cagr": float(np.quantile(null, 0.9)),
            "results": res}
    (out / f"c6_{a.period}{'_top10' if _G['null_n'] == 10 else ''}.json").write_text(json.dumps(summ, indent=1, default=str, ensure_ascii=False))
    for s in ids:
        b, st = res[f"{s} · 5000 € · prime"], res[f"{s} · 5000 € · prime_stress"]
        print(f"{s:10s} 5k {b['cagr']:+.1%} stress {st['cagr']:+.1%} DD {b['max_dd']:.0%} Sharpe {b['sharpe']:.2f} "
              f"p {b['p_zufall']:.2f} Jahre+ {b['jahre_positiv']} ohneTop1% {b.get('ohne_top1pct_eur')}", flush=True)
    print(f"Zufall Median {np.median(null):+.1%} · 90 % {np.quantile(null, 0.9):+.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
