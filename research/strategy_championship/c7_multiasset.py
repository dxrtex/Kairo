"""Welle 4 – Multi-Asset-Trendfolge mit ETFs (Protokoll v2.0), Kosten Scalable PRIME+.

python -m research.strategy_championship.c7_multiasset --data DIR --extra DIR --out OUT [--period train|validation]

Alle Entscheidungen am Monatsende (Gesamtrendite aus AdjClose), Ausführung zur nächsten Eröffnung. Cash = SHY.
  G1 GTAA5  – Faber 2007: SPY, EFA, IEF, GSG, VNQ je 20 %, nur über dem 10-Monats-Durchschnitt, sonst SHY
  G2 AGG3   – 13 ETFs (SPY IWM EFA EEM VGK EWJ VNQ TLT IEF LQD TIP GLD GSG): Top 3 nach Ø der 1/3/6/12-M.-Rendite,
              nur über dem 10-Monats-Durchschnitt, sonst der Anteil in SHY
  G3 GEM    – Antonacci: SPY vs. EFA nach 12-M.-Rendite; Gewinner, wenn besser als BIL, sonst AGG
  G4 TSMOM6 – SPY EFA EEM TLT GLD GSG, Gewicht ∝ 1/Vol 6 M., nur mit positiver 12-M.-Rendite, Rest SHY
Vergleich: ACWI halten, S13-ETF, S16-B (Werte aus früheren Läufen gleicher Engine). Zufall: gleiche Anzahl zufälliger ETFs
aus demselben Universum je Monat (100 Seeds).
"""

from __future__ import annotations

import argparse
import json
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

from .b2_baselines import metrics
from .data import _cut, load
from .engine import Costs, Order, run

U = {"G1-GTAA5": ["SPY", "EFA", "IEF", "GSG", "VNQ"],
     "G2-AGG3": ["SPY", "IWM", "EFA", "EEM", "VGK", "EWJ", "VNQ", "TLT", "IEF", "LQD", "TIP", "GLD", "GSG"],
     "G3-GEM": ["SPY", "EFA", "AGG"],
     "G4-TSMOM6": ["SPY", "EFA", "EEM", "TLT", "GLD", "GSG"]}
CAPS = (2000, 6000, 20000)
SEEDS = 100
_G: dict = {}


def month_table(adj: pd.DataFrame, start, end) -> tuple[pd.DataFrame, list]:
    me = adj.groupby(adj.index.to_period("M")).tail(1)
    return me, [d for d in me.index if start <= d <= end]


def targets(sid: str, me: pd.DataFrame, daily: pd.DataFrame, d) -> dict:
    """Zielgewichte am Monatsende d (nur Information bis d)."""
    k = me.index.get_loc(d)
    if k < 12:
        return {}
    row = me.iloc[k]
    sma10 = me.iloc[k - 9:k + 1].mean()

    def r(t, m):
        return row[t] / me[t].iloc[k - m] - 1

    if sid == "G1-GTAA5":
        return {t: 0.2 for t in U[sid] if row[t] > sma10[t]} | ({"SHY": 0.2 * sum(row[t] <= sma10[t] for t in U[sid])}
                                                              if any(row[t] <= sma10[t] for t in U[sid]) else {})
    if sid == "G2-AGG3":
        sc = {t: np.mean([r(t, m) for m in (1, 3, 6, 12)]) for t in U[sid] if np.isfinite(row[t]) and np.isfinite(me[t].iloc[k - 12])}
        top = sorted(sc, key=lambda t: -sc[t])[:3]
        w = {t: 1 / 3 for t in top if row[t] > sma10[t]}
        if len(w) < 3:
            w["SHY"] = (3 - len(w)) / 3
        return w
    if sid == "G3-GEM":
        best = "SPY" if r("SPY", 12) >= r("EFA", 12) else "EFA"
        return {best: 1.0} if r(best, 12) > r("BIL", 12) else {"AGG": 1.0}
    if sid == "G4-TSMOM6":
        ret = daily[U[sid]][daily.index <= d].pct_change().iloc[-126:]
        vol = ret.std() * np.sqrt(252)
        ok = [t for t in U[sid] if r(t, 12) > 0 and vol[t] > 0]
        inv = {t: 1 / vol[t] for t in U[sid] if vol[t] > 0}
        tot = sum(inv.values())
        w = {t: inv[t] / tot for t in ok}
        if sum(w.values()) < 0.999:
            w["SHY"] = 1 - sum(w.values())
        return w
    raise KeyError(sid)


def orders(sid: str, rng=None) -> tuple[list, dict]:
    me, ds, daily = _G["me"], _G["dates"], _G["adj"]
    out, ex, prev = [], {}, {}
    for d in ds:
        w = targets(sid, me, daily, d)
        if rng is not None and w:
            n = len([t for t in w if t != "SHY"])
            pick = list(rng.choice(U[sid], n, replace=False)) if n else []
            w = {t: (1 - w.get("SHY", 0)) / n for t in pick} | ({"SHY": w["SHY"]} if "SHY" in w else {})
        for t in prev:
            if t not in w:
                ex.setdefault(t, []).append(d)
        for t, x in w.items():
            if x > 0.001:
                out.append(Order(d, t, weight=0.99 * x, prio=x, tag=sid))
        prev = w
    return out, ex


def _job(args):
    sid, cash, cn, seed = args
    o, ex = orders(sid, None if seed is None else np.random.default_rng(seed))
    r = run(_G["frames"], {t: "USD" for t in _G["frames"]}, _G["fx"], o, cash, _G["costs"][cn], 14, calendar=_G["cal"],
            exit_when=ex, min_fill=0.5)
    m = metrics(r)
    if seed is not None:
        return (sid, seed), m.get("cagr")
    e = r.equity
    yr = e.resample("YE").last().pct_change().dropna()
    return (sid, cash, cn), {k: m.get(k) for k in ("cagr", "max_dd", "sharpe", "trades", "calmar")} | {
        "jahre_positiv": f"{int((yr > 0).sum())}/{len(yr)}", "checks_ok": all(v for v in r.checks.values() if isinstance(v, bool))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--extra", required=True)
    ap.add_argument("--out", default="c7_out")
    ap.add_argument("--period", default="train", choices=["train", "validation"])
    ap.add_argument("--only", nargs="*", default=None)
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    _, _, fx, bench, (start, end) = load(a.data, a.period, tickers=["__keine__"])
    ext = _cut(pd.read_parquet(Path(a.extra) / "bench_extra_v1.parquet"), end)
    frames = {t: g.drop(columns="ticker").set_index("date").sort_index() for t, g in ext.groupby("ticker")}
    frames.update({t: bench[t] for t in ("SPY", "EFA", "SHY", "BIL", "ACWI")})
    frames = {t: f[["Open", "High", "Low", "Close", "AdjClose"]] for t, f in frames.items()}
    adj = pd.DataFrame({t: f["AdjClose"] for t, f in frames.items()}).sort_index()
    adj = adj[adj.index <= end]
    me, ds = month_table(adj, start, end)
    cal = adj.index[(adj.index >= start) & (adj.index <= end)]
    costs = {"prime": Costs(fee_eur=0.99, spread=0.001, fee_free_from=250.0),
             "prime_stress": Costs(fee_eur=1.99, spread=0.002, slippage=0.0005, fx_fee=0.001, fee_free_from=250.0)}
    _G.update(frames=frames, fx=fx, me=me, dates=ds, adj=adj, cal=cal, costs=costs)
    ids = a.only or list(U)
    jobs = [(s, c, cn, None) for s in ids for c in CAPS for cn in costs] + [(s, 6000, "prime", k) for s in ids for k in range(SEEDS)]
    with Pool() as pool:
        rr = pool.map(_job, jobs, chunksize=4)
    res = {f"{k[0]} · {k[1]} € · {k[2]}": v for k, v in rr if len(k) == 3}
    for s in ids:
        null = np.array([v for k, v in rr if len(k) == 2 and k[0] == s])
        c = res[f"{s} · 6000 € · prime"]["cagr"]
        res[f"{s} · 6000 € · prime"].update(p_zufall=float((null >= c).mean()), zufall_median=float(np.median(null)))
    acwi = run(frames, {t: "USD" for t in frames}, fx, [Order(cal[0], "ACWI", weight=0.995)], 6000, costs["prime"], 1,
               calendar=cal)
    res["ACWI halten · 6000 € · prime"] = {k: metrics(acwi).get(k) for k in ("cagr", "max_dd", "sharpe")}
    (out / f"c7_{a.period}.json").write_text(json.dumps(res, indent=1, default=str, ensure_ascii=False))
    for s in ids + ["ACWI halten"]:
        b = res[f"{s} · 6000 € · prime"]
        st = res.get(f"{s} · 6000 € · prime_stress", {})
        print(f"{s:12s} {b['cagr']:+.1%} stress {st.get('cagr', float('nan')):+.1%} DD {b['max_dd']:.0%} Sharpe {b['sharpe']:.2f} "
              f"p {b.get('p_zufall', float('nan')):.2f} Zufall {b.get('zufall_median', float('nan')):+.1%} "
              f"Jahre+ {b.get('jahre_positiv')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
