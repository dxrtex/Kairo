"""Hypothese v2.2: Kairo-Treffer (S01-B) nach Fib-Tiefe – „Konsolidierung an der 0,79“.

python -m research.strategy_championship.fib_test --data DIR --signals FILE --out OUT     (Holdout-Freigabe nötig)

Jeder Treffer wird einzeln gehandelt (keine Kapitalgrenze): S01-B-Basis-Einstieg, Stop unter der Basis, Ausstieg EMA20 ab
Tag 10, max. 40 Tage. R = Ergebnis ÷ Risiko (vor Ordergebühr, nach halbem Spread je Seite).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import s01
from .data import PERIODS, load
from .engine import Costs, run

BINS = [(-9, 0.70, "< 0,70"), (0.70, 0.75, "0,70–0,75"), (0.75, 0.83, "0,75–0,83 (an der 0,79)"), (0.83, 0.886, "0,83–0,886"),
        (0.886, 9, "> 0,886")]
AT079 = "0,75–0,83 (an der 0,79)"


def bucket(x):
    if not np.isfinite(x):
        return "ohne Fib"
    for lo, hi, n in BINS:
        if lo <= x < hi:
            return n
    return "ohne Fib"


def perm_p(a: np.ndarray, b: np.ndarray, n: int = 10000, seed: int = 1) -> float:
    if len(a) < 5 or len(b) < 5:
        return float("nan")
    rng, d0, both = np.random.default_rng(seed), a.mean() - b.mean(), np.concatenate([a, b])
    cnt = 0
    for _ in range(n):
        rng.shuffle(both)
        cnt += both[:len(a)].mean() - both[len(a):].mean() >= d0
    return float((cnt + 1) / (n + 1))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--signals", required=True)
    ap.add_argument("--out", default="fib_out")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sig = pd.read_parquet(a.signals)
    prices, cur, fx, _b, (start, end) = load(a.data, "full", sorted(sig["ticker"].unique()))
    raw = {t: s01.with_ema(df) for t, df in prices.items()}
    adj = {t: s01.adjusted(s01.clean(df)) for t, df in prices.items()}
    orders = []
    for x in sig.itertuples(index=False):
        if x.ticker not in prices:
            continue
        gid = f"{x.ticker}|{pd.Timestamp(x.date).date()}"
        for o in s01.base_orders(prices[x.ticker], int(x.i), float(x.atr), x.ticker, gid, "B", 1e-5, adj=adj[x.ticker]):
            o.tag = gid
            orders.append(o)
    cal = pd.DatetimeIndex(sorted(set().union(*[f.index[(f.index >= start) & (f.index <= end)] for f in raw.values()])))
    r = run(raw, cur, fx, orders, 1e9, Costs(fee_eur=0.0, spread=0.001), 10 ** 6, calendar=cal, min_fill=0.0)
    t = r.trades.copy()
    t["R"] = t["pnl_eur"] / t["risk_eur"]
    sig["gid"] = sig["ticker"] + "|" + pd.to_datetime(sig["date"]).dt.date.astype(str)
    t = t.merge(sig[["gid", "date", "fib_ok", "fib_ret", "fib_H", "fib_L", "support_ok"]], left_on="tag", right_on="gid", how="left")
    deep = []                                       # Tiefe des Basis-Tiefs beim Einstieg (gleicher Fib-Anker, bereinigte Kurse)
    for x in t.itertuples(index=False):
        A = adj[x.ticker]
        k = int(np.searchsorted(A.index.values, np.datetime64(x.entry_date))) - 1
        lo = float(A["Low"].iloc[max(0, k - s01.CK + 1): k + 1].min())
        deep.append((x.fib_H - lo) / (x.fib_H - x.fib_L) if x.fib_H > x.fib_L else np.nan)
    t["base_ret"] = deep
    t["abschnitt"] = np.select([t["date"] <= pd.Timestamp(PERIODS["train"][1]), t["date"] <= pd.Timestamp(PERIODS["validation"][1])],
                               ["Train", "Validierung"], "Holdout")
    res = {"signale": int(len(sig)), "trades": int(len(t))}
    for col in ("fib_ret", "base_ret"):
        t["g"] = t[col].map(bucket)
        tab = {}
        for ab in ("Train", "Validierung", "Holdout", "Gesamt"):
            s = t if ab == "Gesamt" else t[t["abschnitt"] == ab]
            tab[ab] = {g: {"n": int(len(v)), "avg_R": round(float(v["R"].mean()), 3), "median_R": round(float(v["R"].median()), 3),
                           "win": round(float((v["R"] > 0).mean()), 3)} for g, v in s.groupby("g")}
            a_ = s.loc[s["g"] == AT079, "R"].to_numpy()
            b_ = s.loc[s[col].between(0.618, 0.75, inclusive="left"), "R"].to_numpy()
            tab[ab]["_vergleich"] = {"an_079_avg": float(a_.mean()) if len(a_) else None,
                                    "flach_avg": float(b_.mean()) if len(b_) else None,
                                    "n_079": int(len(a_)), "n_flach": int(len(b_)), "p": perm_p(a_, b_)}
        res[col] = tab
    t.to_csv(out / "fib_trades.csv", index=False)
    (out / "fib_result.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str))
    for col in ("fib_ret", "base_ret"):
        print("==", col)
        for ab, v in res[col].items():
            c = v["_vergleich"]
            print(f"  {ab:12s} an 0,79: {c['an_079_avg']} (n={c['n_079']}) · 0,618–0,75: {c['flach_avg']} (n={c['n_flach']}) · p={c['p']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
