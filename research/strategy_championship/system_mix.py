"""Protokoll v2.8 – Systemtest Welt-ETF + Dual Momentum (S16-B) + Kairo-S (K60S 20 × 0,25 %), 2008–2026, PRIME+.

python -m research.strategy_championship.system_mix --data DIR --signals FILE --out OUT
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import kairo_depot as kd
from . import s01, wave2
from .data import UNIVERSE, load
from .engine import Costs, Order, run

CASH = 20000
MIXES = {"M0 100 ACWI": (1.0, 0.0, 0.0), "M1 70/15/15": (0.7, 0.15, 0.15), "M2 70/30 ACWI/DM": (0.7, 0.3, 0.0),
         "M3 70/30 ACWI/Kairo-S": (0.7, 0.0, 0.3), "M4 50/25/25": (0.5, 0.25, 0.25)}
REB_COST = {"base": 0.001, "stress": 0.002}


def mix(rets: pd.DataFrame, w: tuple, cost: float) -> pd.Series:
    """Tagesrenditen der Bausteine → Depotkurve mit jährlichem Rebalancing auf die Zielgewichte."""
    w0 = np.array(w, float)
    h, eq, out = w0.copy(), 1.0, []
    year = None
    for d, r in zip(rets.index, rets.to_numpy()):
        if year is not None and d.year != year:
            cur = h / h.sum()
            eq *= 1 - cost * np.abs(cur - w0).sum()
            h = w0 * eq
        year = d.year
        h = h * (1 + r)
        eq = float(h.sum())
        out.append(eq)
    return pd.Series(out, index=rets.index)


def sharpe(r: np.ndarray) -> float:
    return float(r.mean() / r.std() * np.sqrt(252)) if r.std() > 0 else 0.0


def boot_p(ra: pd.Series, rb: pd.Series, n: int = 2000, block: int = 21, seed: int = 7) -> float:
    """Block-Bootstrap: Anteil der Stichproben mit Sharpe(a) − Sharpe(b) ≤ 0 (einseitig)."""
    a, b = ra.to_numpy(), rb.to_numpy()
    T, rng, cnt = len(a), np.random.default_rng(seed), 0
    for _ in range(n):
        idx = (rng.integers(0, T - block, T // block + 1)[:, None] + np.arange(block)).ravel()[:T]
        cnt += sharpe(a[idx]) - sharpe(b[idx]) <= 0
    return float((cnt + 1) / (n + 1))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--signals", required=True)
    ap.add_argument("--out", default="mix_out")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sig = pd.read_parquet(a.signals)
    prices, cur, fx, bench, (start, end) = load(a.data, "full")
    prices = {t: df for t, df in prices.items() if len(s01.clean(df)) >= 300}
    adj = {t: s01.adjusted(s01.clean(df)) for t, df in prices.items()}
    raw = {t: s01.with_ema(df) for t, df in prices.items()}
    cal = pd.DatetimeIndex(sorted(set().union(*[f.index[(f.index >= start) & (f.index <= end)] for f in raw.values()])))
    uni = pd.read_csv(UNIVERSE)
    from .wave1 import spreads
    sp = spreads(raw, cur, dict(zip(uni["ticker"], uni["region"])))
    costs = {"base": Costs(fee_eur=0.99, spread=0.001, spread_by_ticker=sp, fee_free_from=250.0),
             "stress": Costs(fee_eur=1.99, spread=0.002, slippage=0.0005, fx_fee=0.001, fee_free_from=250.0,
                             spread_by_ticker={k: 2 * v for k, v in sp.items()})}
    kd._G.update(prices=prices, adj=adj, raw=raw, cur=cur, fx=fx, cal=cal, costs=costs)
    sig = sig[sig["ticker"].isin(prices)]
    rows = []
    for r in sig.itertuples(index=False):
        C = adj[r.ticker]["Close"].to_numpy(float)
        i = int(r.i)
        rows.append((r.ticker, i, r.atr, f"{r.ticker}|{pd.Timestamp(r.date).date()}", float(C[i]),
                     float(C[i - 21] / C[i - 126] - 1) if i >= 126 else np.nan))
    etf = {t: bench[t][["Open", "High", "Low", "Close", "AdjClose"]] for t in ("SPY", "EFA", "QQQ", "SHY", "BIL", "ACWI")}
    ecur = {t: "USD" for t in etf}
    o_dm, ex_dm, _ = wave2.etf_rotation(bench, "S16-B", start, end)
    res, curves = {}, {}
    for cn, co in costs.items():
        k = run(raw, cur, fx, kd.orders(rows, 60, "mom", 0.0025), CASH, co, 20, calendar=cal, min_fill=0.5).equity
        d = run(etf, ecur, fx, o_dm, CASH, co, 3, calendar=cal, exit_when=ex_dm, min_fill=0.5).equity
        w = run(etf, ecur, fx, [Order(cal[0], "ACWI", weight=0.995)], CASH, co, 1, calendar=cal).equity
        eq = pd.DataFrame({"ACWI": w, "DM": d, "KairoS": k}).sort_index().ffill().dropna()
        eq = eq[eq.index >= eq.index[(eq["ACWI"].diff().abs() > 0).argmax()]]          # ab erstem ACWI-Kurs
        rets = eq.pct_change().fillna(0.0)
        res[f"Korrelation · {cn}"] = rets.corr().round(3).to_dict()
        for name, wt in MIXES.items():
            e = mix(rets, wt, REB_COST[cn])
            curves[(name, cn)] = e
            res[f"{name} · {cn}"] = kd.segs(e)
            g = res[f"{name} · {cn}"]
            print(name, cn, {ab: (round(g[ab]["cagr"], 3), round(g[ab]["max_dd"], 2), round(g[ab]["sharpe"], 2))
                             for ab in ("Train", "Validierung", "Holdout", "gesamt") if g.get(ab)}, flush=True)
    m1, m0 = res["M1 70/15/15 · stress"], res["M0 100 ACWI · stress"]
    p = boot_p(curves[("M1 70/15/15", "stress")].pct_change().dropna(), curves[("M0 100 ACWI", "stress")].pct_change().dropna())
    crit = {"sharpe_alle_drei": all(m1[ab]["sharpe"] > m0[ab]["sharpe"] for ab in ("Train", "Validierung", "Holdout")),
            "dd_ok": m1["gesamt"]["max_dd"] >= m0["gesamt"]["max_dd"] - 0.02, "p_bootstrap": p}
    crit["bestanden"] = bool(crit["sharpe_alle_drei"] and crit["dd_ok"] and p <= 0.05)
    res["_entscheidung_M1_vs_M0_stress"] = crit
    print(crit)
    (out / "system_mix.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str))
    pd.DataFrame({f"{n} · {c}": e for (n, c), e in curves.items()}).to_csv(out / "system_mix_curves.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
