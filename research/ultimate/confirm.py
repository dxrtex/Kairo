"""Kairo Ultimate – Bestätigung auf Daten, die für diese Hypothesen nie benutzt wurden (Plan §7.4).

  pre   USA/Europa 1999–2007 (eingefrorenes Universum, Kurse ab 1996 kostenlos von Yahoo neu geladen)
  asia  Asien 2008–2026 (Universum des Live-Scanners)

Je Shard: Kurse laden → Treffer mit dem unveränderten Scanner → Trades je Variante (unbegrenztes Kapital, Stress-Kosten ohne
feste Gebühr, Ausstieg B60). Nur der RELATIVE Vergleich zählt (Variante vs. E0): Survivorship ist hier noch stärker.
Wechselkurse werden nicht gebraucht (R je Trade ist währungsfrei); Fremdwährungs-Aufschlag fällt für alle Varianten gleich weg.

    python -m research.ultimate.confirm run --set pre|asia --shard K --shards N --out OUT [--universe U.csv] [--sec DIR]
    python -m research.ultimate.confirm combine --dir DIR --out OUT      → confirm_<Variante>.json, prices_<set>.parquet
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from research.strategy_championship import s01
from research.strategy_championship import v2_test as V
from research.strategy_championship.wave1 import spreads

from . import round1 as R

SETS = {"pre": ("1996-01-01", "2008-01-01", "1999-01-01", "2007-12-31"),
        "asia": ("2005-01-01", "2026-10-17", "2008-01-01", "2026-10-16")}
VARS = {"pre": ("E0", "E1", "E2", "V1", "N1", "C1"), "asia": ("E0", "E1", "E2", "V1", "C1")}


def download(tickers: list[str], start: str, end: str) -> dict[str, pd.DataFrame]:
    import yfinance as yf
    out = {}
    for i in range(0, len(tickers), 60):
        part = tickers[i:i + 60]
        d = None
        for att in range(4):
            try:
                d = yf.download(part, start=start, end=end, interval="1d", auto_adjust=False, actions=False,
                                group_by="ticker", progress=False, threads=True)
                break
            except Exception as exc:
                print("Fehler", repr(exc)[:100]); time.sleep(10 * 2 ** att)
        if d is None or d.empty:
            continue
        for t in part:
            try:
                x = d[t] if isinstance(d.columns, pd.MultiIndex) else d
            except KeyError:
                continue
            x = x.dropna(subset=["Close"]).rename(columns={"Adj Close": "AdjClose"})
            if len(x) < 300 or "AdjClose" not in x:
                continue
            x = x[["Open", "High", "Low", "Close", "AdjClose", "Volume"]]
            x.index = pd.to_datetime(x.index).tz_localize(None)
            out[t] = x
        print(f"  {min(i + 60, len(tickers))}/{len(tickers)} geladen", flush=True)
        time.sleep(2)
    return out


def run_shard(a) -> None:
    dl0, dl1, s0, s1 = SETS[a.set]
    uni = pd.read_csv(a.universe).sort_values("ticker")
    mine = uni.iloc[a.shard::a.shards]
    prices = download(list(mine["ticker"]), dl0, dl1)
    start, end = pd.Timestamp(s0), pd.Timestamp(s1)
    prices = {t: x[x.index <= end] for t, x in prices.items()}
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    if not prices:
        print("keine Kurse"); return
    pd.concat([x.assign(ticker=t).reset_index(names="date") for t, x in prices.items()]).to_parquet(
        out / f"px_{a.set}_{a.shard}.parquet", index=False)
    real_cur = dict(zip(uni["ticker"], uni["currency"].fillna("USD")))
    from multiprocessing import Pool
    with Pool() as pool:
        sigs = pool.starmap(s01.signals, [(prices[t], real_cur.get(t, "USD"), start, end, t) for t in prices])
    S = pd.DataFrame([s for l in sigs for s in l])
    print(f"Shard {a.shard}: {len(prices)} Aktien, {len(S)} Treffer", flush=True)
    if not len(S):
        return
    sp = out / f"sig_{a.set}_{a.shard}.parquet"
    S.to_parquet(sp, index=False)
    cur = {t: "EUR" for t in prices}
    sig, meta = V._setup(None, sp, prices, cur, {}, start, end)
    region = {"asia": "asia"}.get(a.set)
    R._G["region"] = {t: region or ("us" if "." not in t else "eu") for t in prices}
    R._G["spread"] = spreads(R._G["raw"], {t: real_cur.get(t, "USD") for t in prices}, R._G["region"])
    R._G["cur_real"] = real_cur
    R.load_sec(a.sec)
    for v in VARS[a.set]:
        t = R.per_trade(R.build(sig, meta, v, 1e-5))
        t.to_csv(out / f"ctr_{a.set}_{v}_{a.shard}.csv", index=False)
        print(f"  {v}: {len(t)} Trades, Ø R Stress {t['R_stress'].mean() if len(t) else float('nan'):+.3f}", flush=True)


def combine(d: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    res: dict[str, dict] = {}
    lines = []
    for s, vs in VARS.items():
        T = {}
        for v in vs:
            fs = sorted(d.glob(f"ctr_{s}_{v}_*.csv"))
            parts = [pd.read_csv(f) for f in fs if f.stat().st_size > 0]
            if parts:
                T[v] = pd.concat(parts)
        if "E0" not in T:
            continue
        e0 = T["E0"]
        for v, t in T.items():
            x, y = (t, e0)
            if v == "N1":                               # nur US-Titel und nur, wo SEC-Termine existieren (ab 2004)
                x, y = t[~t["ticker"].str.contains(r"\.")], e0[~e0["ticker"].str.contains(r"\.")]
            dr = float(x["R_stress"].mean() - y["R_stress"].mean())
            lines.append(f"{s} {v}: Ø R Stress {x['R_stress'].mean():+.3f} (n {len(x)}) vs. E0 {y['R_stress'].mean():+.3f} (n {len(y)}) → Δ {dr:+.3f}")
            if v != "E0":
                res.setdefault(v, {})[{"pre": "vorzeit", "asia": "asien"}[s]] = dr
        px = sorted(d.glob(f"px_{s}_*.parquet"))
        if px:
            (out / s).mkdir(exist_ok=True)
            pd.concat([pd.read_parquet(f) for f in px]).to_parquet(out / s / "prices_v1.parquet", index=False)
    for v, r in res.items():
        (out / f"confirm_{v}.json").write_text(json.dumps(r))
    (out / "confirm.txt").write_text("\n".join(lines))
    print("\n".join(lines))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "combine"])
    ap.add_argument("--set", choices=list(SETS)); ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--shards", type=int, default=1); ap.add_argument("--universe"); ap.add_argument("--sec")
    ap.add_argument("--out", default="cf_out"); ap.add_argument("--dir")
    a = ap.parse_args(argv)
    if a.cmd == "combine":
        combine(Path(a.dir), Path(a.out)); return 0
    run_shard(a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
