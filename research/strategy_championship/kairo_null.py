"""Protokoll v2.3 – Kairo (S01-B) mit Kosten Scalable PRIME+ gegen Zufalls-Einstiege, 2008–2026, je Trade.

python -m research.strategy_championship.kairo_null --data DIR --signals FILE --out OUT --part kairo|null [--seed-start K --seed-n N]
        python -m research.strategy_championship.kairo_null --combine DIR --out OUT

Kairo: jeder Treffer → S01-B-Basis-Einstieg (Seitwärtsphase, Stop unter der Basis, EMA20-Ausstieg ab Tag 10, max. 40 T.).
Zufall: an jedem Treffer-Tag stattdessen ein zufälliger zulässiger Titel (gleicher Grundfilter), gleiche Basis-Regel.
Keine Kapitalgrenze (jeder Trade einzeln). R netto für ein 5.000-€- bzw. 10.000-€-Depot mit 1 % Risiko:
Orderwert = Risiko × Einstieg ÷ (Einstieg − Stop); Gebühr 0,99 € je Order unter 250 €, sonst 0 (PRIME+); Spread 0,1 % je Seite/2.
"""

from __future__ import annotations

import argparse
import json
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

from . import s01
from .data import PERIODS, load
from .engine import Costs, run

_G: dict = {}


def orders_for(rows) -> list:
    out = []
    for t, i, atr, gid in rows:
        for o in s01.base_orders(_G["prices"][t], int(i), float(atr), t, gid, "B", 1e-5, adj=_G["adj"][t]):
            o.tag = gid
            out.append(o)
    return out


def evaluate(rows) -> pd.DataFrame:
    r = run(_G["raw"], _G["cur"], _G["fx"], orders_for(rows), 1e9, Costs(fee_eur=0.0, spread=0.001), 10 ** 6,
            calendar=_G["cal"], min_fill=0.0)
    t = r.trades.copy()
    if not len(t):
        return t
    t["R"] = t["pnl_eur"] / t["risk_eur"]
    d = pd.to_datetime(t["tag"].str.split("|").str[1])
    t["abschnitt"] = np.select([d <= pd.Timestamp(PERIODS["train"][1]), d <= pd.Timestamp(PERIODS["validation"][1])],
                               ["Train", "Validierung"], "Holdout")
    stop_dist = (t["entry_px"] - t["stop"]) / t["entry_px"]
    for cap in (5000, 10000):
        risk = cap * 0.01
        val = risk / stop_dist.clip(lower=1e-4)
        fees = np.where(val.clip(upper=cap) >= 250, 0.0, 0.99) * 2
        t[f"R_net_{cap}"] = t["R"] - fees / risk
    return t


def summarize(t: pd.DataFrame) -> dict:
    out = {}
    for ab in ("Train", "Validierung", "Holdout", "Gesamt"):
        s = t if ab == "Gesamt" else t[t["abschnitt"] == ab]
        out[ab] = {"n": int(len(s)), "R": float(s["R"].mean()) if len(s) else None,
                   "R_net_5000": float(s["R_net_5000"].mean()) if len(s) else None,
                   "R_net_10000": float(s["R_net_10000"].mean()) if len(s) else None,
                   "win": float((s["R"] > 0).mean()) if len(s) else None}
    return out


def _null(seed: int) -> dict:
    rng = np.random.default_rng(seed)
    rows = []
    for d, n in _G["per_day"].items():
        pool = _G["pool"].get(d)
        if pool is None or not len(pool):
            continue
        for t in rng.choice(pool, min(n, len(pool)), replace=False):
            i = _G["pos"][t].get(d)
            a = _G["atr"][t].get(d)
            if i is None or a is None or not np.isfinite(a):
                continue
            rows.append((t, i, a, f"{t}|{pd.Timestamp(d).date()}|z{seed}"))
    return summarize(evaluate(rows))


def combine(d: Path) -> dict:
    kairo = json.loads((d / "kairo_summary.json").read_text())
    nulls = [x for f in sorted(d.glob("null_*.json")) for x in json.loads(f.read_text())]
    res = {"kairo": kairo, "zufall": {}, "seeds": len(nulls)}
    for ab in kairo:
        z = np.array([n[ab]["R_net_5000"] for n in nulls if n[ab]["R_net_5000"] is not None])
        zr = np.array([n[ab]["R"] for n in nulls if n[ab]["R"] is not None])
        res["zufall"][ab] = {"R_median": float(np.median(zr)), "R_net_5000_median": float(np.median(z)),
                             "p_R": float((zr >= kairo[ab]["R"]).mean()), "seeds": int(len(z))}
    for ab in kairo:
        k, z = kairo[ab], res["zufall"][ab]
        print(f"{ab:12s} Kairo R {k['R']:+.3f} netto5k {k['R_net_5000']:+.3f} netto10k {k['R_net_10000']:+.3f} (n {k['n']}) | "
              f"Zufall R {z['R_median']:+.3f} netto5k {z['R_net_5000_median']:+.3f} | p {z['p_R']:.2f}", flush=True)
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data")
    ap.add_argument("--signals")
    ap.add_argument("--out", default="kn_out")
    ap.add_argument("--part", choices=["kairo", "null"], default=None)
    ap.add_argument("--seed-start", type=int, default=0)
    ap.add_argument("--seed-n", type=int, default=2)
    ap.add_argument("--combine")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.combine:
        (out / "kairo_null.json").write_text(json.dumps(combine(Path(a.combine)), indent=1, ensure_ascii=False))
        return 0
    sig = pd.read_parquet(a.signals)
    prices, cur, fx, _b, (start, end) = load(a.data, "full")
    prices = {t: df for t, df in prices.items() if len(s01.clean(df)) >= 300}
    adj = {t: s01.adjusted(s01.clean(df)) for t, df in prices.items()}
    raw = {t: s01.with_ema(df) for t, df in prices.items()}
    cal = pd.DatetimeIndex(sorted(set().union(*[f.index[(f.index >= start) & (f.index <= end)] for f in raw.values()])))
    _G.update(prices=prices, adj=adj, raw=raw, cur=cur, fx=fx, cal=cal)
    sig = sig[sig["ticker"].isin(prices)]
    if a.part == "kairo":
        kt = evaluate([(r.ticker, r.i, r.atr, f"{r.ticker}|{pd.Timestamp(r.date).date()}") for r in sig.itertuples(index=False)])
        kt.to_csv(out / "kairo_trades.csv", index=False)
        (out / "kairo_summary.json").write_text(json.dumps(summarize(kt), indent=1))
        print(json.dumps(summarize(kt), indent=1))
        return 0
    pool, pos, atr = {}, {}, {}
    for t, A in adj.items():
        ok = s01.eligible(A, cur.get(t, "USD"))
        pos[t] = {d: k for k, d in enumerate(A.index)}
        atr[t] = s01.atr14(prices[t]).to_dict()
        for d in A.index[ok & (A.index >= start)]:
            pool.setdefault(d, []).append(t)
    _G.update(pool={d: np.array(v) for d, v in pool.items()}, pos=pos, atr=atr,
              per_day=pd.to_datetime(sig["date"]).value_counts().to_dict())
    seeds = list(range(a.seed_start, a.seed_start + a.seed_n))
    with Pool(min(len(seeds), 4)) as p:
        nulls = p.map(_null, seeds, chunksize=1)
    (out / f"null_{a.seed_start}.json").write_text(json.dumps(nulls))
    print(f"Zufall {seeds}: R " + ", ".join(f"{n['Gesamt']['R']:+.3f}" for n in nulls))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
