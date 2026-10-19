"""Protokoll v2.6 – Kairo als echtes Depot (begrenztes Kapital), 2008–2026, Kosten Scalable PRIME+.

python -m research.strategy_championship.kairo_depot --data DIR --signals FILE --out OUT --part kairo|null [--seed-start K --seed-n N]
python -m research.strategy_championship.kairo_depot --combine DIR --out OUT

Varianten (S01-B-Basis-Einstieg, 1 % Risiko, max. 5 Positionen, Mindestfüllung 50 %):
  K40  Ausstieg EMA20 ab Tag 10, max. 40 T., Vorrang ruhigere Titel (Backtest-Original)
  K60  wie K40, aber max. 60 T. (v2.5)
  K60S wie K60, Vorrang schwächeres Vormomentum (v2.4)
Kapital 5.000 / 10.000 €, Kosten Basis und Stress. Zufall: K60-Regeln mit zufälligen zulässigen Titeln an denselben Tagen (20 Seeds).
Vergleich: ACWI halten (gleiche Engine). Kennzahlen je Abschnitt Train / Validierung / Holdout und gesamt.
Bestanden (Empfehlung „Kairo fürs echte Geld“), wenn die beste vorab benannte Variante K60S: (a) Stress-CAGR in allen drei
Abschnitten > 0, (b) gesamt besser als ACWI risikobereinigt (Sharpe), (c) gesamt über dem Zufalls-Median in allen drei Abschnitten.
"""

from __future__ import annotations

import argparse
import json
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

from . import s01
from .d_run import stats
from .data import PERIODS, load
from .engine import Costs, Order, run

_G: dict = {}
VARS = {"K40": (40, "vol"), "K60": (60, "vol"), "K60S": (60, "mom")}
CAPS = (5000, 10000)


def orders(rows, hold: int, prio: str) -> list:
    out = []
    for t, i, atr, gid, close, mom in rows:
        p = -(atr / close) if prio == "vol" else (-(mom) if np.isfinite(mom) else -9.0)
        for o in s01.base_orders(_G["prices"][t], int(i), float(atr), t, gid, "B", 0.01, prio=float(p), adj=_G["adj"][t]):
            o.max_days = hold
            out.append(o)
    return out


def segs(e: pd.Series) -> dict:
    e = e.dropna()
    out = {"gesamt": stats(e)}
    for ab, (a, b) in (("Train", PERIODS["train"]), ("Validierung", PERIODS["validation"]), ("Holdout", PERIODS["holdout"])):
        s = e[(e.index >= pd.Timestamp(a)) & (e.index <= pd.Timestamp(b))]
        out[ab] = stats(s) if len(s) > 20 else None
    return out


def sim(rows, hold, prio, cash, cn) -> dict:
    r = run(_G["raw"], _G["cur"], _G["fx"], orders(rows, hold, prio), cash, _G["costs"][cn], 5, calendar=_G["cal"], min_fill=0.5)
    out = segs(r.equity)
    out["trades"] = int(len(r.trades))
    out["checks_ok"] = all(v for v in r.checks.values() if isinstance(v, bool))
    return out


def _null(seed):
    rng = np.random.default_rng(seed)
    rows = []
    for d, n in _G["per_day"].items():
        pool = _G["pool"].get(d)
        if pool is None or not len(pool):
            continue
        for t in rng.choice(pool, min(n, len(pool)), replace=False):
            i, a = _G["pos"][t].get(d), _G["atr"][t].get(d)
            if i is None or a is None or not np.isfinite(a):
                continue
            rows.append((t, i, a, f"{t}|{pd.Timestamp(d).date()}|z{seed}", 1.0, np.nan))
    return sim(rows, 60, "vol", 5000, "base")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data")
    ap.add_argument("--signals")
    ap.add_argument("--out", default="kd_out")
    ap.add_argument("--part", choices=["kairo", "null"])
    ap.add_argument("--seed-start", type=int, default=0)
    ap.add_argument("--seed-n", type=int, default=2)
    ap.add_argument("--combine")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.combine:
        d = Path(a.combine)
        res = json.loads((d / "kairo_depot.json").read_text())
        nulls = [x for f in sorted(d.glob("null_*.json")) for x in json.loads(f.read_text())]
        res["zufall_K60_5000_base"] = {ab: {"cagr_median": float(np.median([n[ab]["cagr"] for n in nulls if n.get(ab)])),
                                            "seeds": len(nulls)} for ab in ("Train", "Validierung", "Holdout", "gesamt")}
        (out / "kairo_depot_final.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str))
        for k, v in res.items():
            if isinstance(v, dict) and "gesamt" in v:
                print(k, {ab: (round(v[ab]["cagr"], 3), round(v[ab]["max_dd"], 2)) for ab in ("Train", "Validierung", "Holdout", "gesamt") if v.get(ab)})
        print("Zufall", res["zufall_K60_5000_base"])
        return 0
    sig = pd.read_parquet(a.signals)
    prices, cur, fx, bench, (start, end) = load(a.data, "full")
    prices = {t: df for t, df in prices.items() if len(s01.clean(df)) >= 300}
    adj = {t: s01.adjusted(s01.clean(df)) for t, df in prices.items()}
    raw = {t: s01.with_ema(df) for t, df in prices.items()}
    cal = pd.DatetimeIndex(sorted(set().union(*[f.index[(f.index >= start) & (f.index <= end)] for f in raw.values()])))
    from .wave1 import spreads
    from .data import UNIVERSE
    uni = pd.read_csv(UNIVERSE)
    sp = spreads(raw, cur, dict(zip(uni["ticker"], uni["region"])))
    costs = {"base": Costs(fee_eur=0.99, spread=0.001, spread_by_ticker=sp, fee_free_from=250.0),
             "stress": Costs(fee_eur=1.99, spread=0.002, slippage=0.0005, fx_fee=0.001, fee_free_from=250.0,
                             spread_by_ticker={k: 2 * v for k, v in sp.items()})}
    _G.update(prices=prices, adj=adj, raw=raw, cur=cur, fx=fx, cal=cal, costs=costs)
    sig = sig[sig["ticker"].isin(prices)]
    if a.part == "kairo":
        rows = []
        for r in sig.itertuples(index=False):
            A = adj[r.ticker]
            C = A["Close"].to_numpy(float)
            i = int(r.i)
            mom = C[i - 21] / C[i - 126] - 1 if i >= 126 else np.nan
            rows.append((r.ticker, i, r.atr, f"{r.ticker}|{pd.Timestamp(r.date).date()}", float(C[i]), float(mom)))
        res = {}
        for name, (hold, prio) in VARS.items():
            for cash in CAPS:
                for cn in costs:
                    k = f"{name} · {cash} € · {cn}"
                    res[k] = sim(rows, hold, prio, cash, cn)
                    g = res[k]["gesamt"]
                    print(k, f"CAGR {g['cagr']:+.1%} DD {g['max_dd']:.0%} Sharpe {g['sharpe']:.2f} Trades {res[k]['trades']}", flush=True)
        fr = {"ACWI": bench["ACWI"][["Open", "High", "Low", "Close", "AdjClose"]]}
        ra = run(fr, {"ACWI": "USD"}, fx, [Order(cal[0], "ACWI", weight=0.995)], 5000, costs["base"], 1, calendar=cal)
        res["ACWI halten · 5000 € · base"] = segs(ra.equity)
        (out / "kairo_depot.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str))
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
    (out / f"null_{a.seed_start}.json").write_text(json.dumps(nulls, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
