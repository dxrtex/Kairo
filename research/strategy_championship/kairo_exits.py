"""Protokoll v2.5 – Ausstiegsregeln für Kairo-Treffer (Basis-Einstieg unverändert), 2008–2026, je Trade.

python -m research.strategy_championship.kairo_exits --data DIR --signals FILE --out OUT

V0 Basis: ab Tag 10 Schluss unter EMA20 → Verkauf, spätestens Tag 40 (S01-B, live im Papier-Depot)
V1 Zeit: Verkauf zum Schluss von Tag 20 (S01-A)
V2 EMA früh: EMA20-Regel schon ab Tag 5, spätestens Tag 40
V3 Nachziehen: ab +2 ATR Stop auf Einstand, danach unter das Vortagestief, spätestens Tag 40
V4 länger: EMA20 ab Tag 10, spätestens Tag 60
Besser als V0 nur, wenn Ø R (netto, 5.000 €, PRIME+) in allen drei Abschnitten höher UND gepoolt p ≤ 0,05/4 (gepaart je Treffer).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import kairo_null as kn
from . import s01
from .data import load

VARS = {"V0 Basis": {}, "V1 Zeit 20 T.": {"max_days": 20, "exit_rule": None},
        "V2 EMA ab Tag 5": {"exit_rule": ("ema", 5)}, "V3 Nachziehen": {"trail": "atr2", "exit_rule": None},
        "V4 bis Tag 60": {"max_days": 60}}


def run_variant(sig, mod: dict) -> pd.DataFrame:
    orig = kn.orders_for

    def patched(rows):
        out = orig(rows)
        for o in out:
            for k, v in mod.items():
                if k == "trail":
                    o.trail = ("be_prevlow", 2 * o.atr)
                else:
                    setattr(o, k, v)
        return out
    kn.orders_for = patched
    try:
        return kn.evaluate([(r.ticker, r.i, r.atr, f"{r.ticker}|{pd.Timestamp(r.date).date()}") for r in sig.itertuples(index=False)])
    finally:
        kn.orders_for = orig


def paired_p(a: pd.Series, b: pd.Series, n: int = 5000, seed: int = 1) -> float:
    d = (a - b).dropna().to_numpy()
    if len(d) < 10:
        return float("nan")
    rng, d0, cnt = np.random.default_rng(seed), d.mean(), 0
    for _ in range(n):
        cnt += (d * rng.choice([-1, 1], len(d))).mean() >= d0
    return float((cnt + 1) / (n + 1))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--signals", required=True)
    ap.add_argument("--out", default="kx_out")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sig = pd.read_parquet(a.signals)
    prices, cur, fx, _b, (start, end) = load(a.data, "full", sorted(sig["ticker"].unique()))
    prices = {t: df for t, df in prices.items() if len(s01.clean(df)) >= 300}
    kn._G.update(prices=prices, adj={t: s01.adjusted(s01.clean(df)) for t, df in prices.items()},
                 raw={t: s01.with_ema(df) for t, df in prices.items()}, cur=cur, fx=fx)
    kn._G["cal"] = pd.DatetimeIndex(sorted(set().union(*[f.index[(f.index >= start) & (f.index <= end)] for f in kn._G["raw"].values()])))
    sig = sig[sig["ticker"].isin(prices)]
    res, per = {}, {}
    for name, mod in VARS.items():
        t = run_variant(sig, mod)
        per[name] = t.set_index("tag")
        res[name] = kn.summarize(t)
        print(name, {ab: round(v["R_net_5000"], 3) for ab, v in res[name].items()}, flush=True)
    base = per["V0 Basis"]
    for name in VARS:
        if name == "V0 Basis":
            continue
        x = per[name]
        common = base.index.intersection(x.index)
        oos_better = all(res[name][ab]["R_net_5000"] > res["V0 Basis"][ab]["R_net_5000"] for ab in ("Train", "Validierung", "Holdout"))
        p = paired_p(x.loc[common, "R_net_5000"], base.loc[common, "R_net_5000"])
        res[name]["_vergleich"] = {"in_allen_besser": oos_better, "p_gepaart": p, "bestaetigt": bool(oos_better and p <= 0.0125)}
        print(f"  {name}: in allen besser {oos_better}, p {p:.4f}", flush=True)
    (out / "kairo_exits.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
