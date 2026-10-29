"""B0 – eingefrorener Forschungsdatensatz (Version 1).

Lädt für ein festes Universum (eingefrorene Liste) Tageskerzen ab 2005 von Yahoo – UNBEREINIGT (Open/High/Low/Close wie
gehandelt) plus „Adj Close“ (Splits + Dividenden) – sowie Benchmarks, Wechselkurse und Volatilität/Zins.
Ergebnis je Shard eine Parquet-Datei; `--combine` fügt zusammen und schreibt ein Manifest mit Prüfsummen.

    python -m research.strategy_championship.data_freeze --universe UNI.csv --shard 0 --shards 12
    python -m research.strategy_championship.data_freeze --combine out/
Bekannte Grenzen (bewusst, siehe 01_DATA_FEASIBILITY.md): heutiges Universum (Survivorship), Yahoo-Historien können sich
nachträglich ändern – deshalb wird genau dieser Download eingefroren und nur noch mit Prüfsumme verwendet.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import pandas as pd

START, END = "2005-01-01", "2026-10-17"          # END exklusiv → letzter Tag 2026-10-16
BENCH = ["ACWI", "URTH", "SPY", "QQQ", "EFA", "IWDA.AS", "EUNL.DE", "SPYI.DE", "XLK", "XLF", "XLE", "XLV", "XLI", "XLY",
         "XLP", "XLU", "XLB", "^GSPC", "^STOXX", "^GDAXI", "^VIX", "^IRX", "BIL", "SHY"]
FX = ["EURUSD=X", "EURGBP=X", "EURCHF=X", "EURSEK=X", "EURNOK=X", "EURDKK=X", "EURPLN=X", "EURCAD=X", "EURJPY=X"]


def _dl(tickers: list[str], batch: int = 80, pause: float = 3.0) -> pd.DataFrame:
    import yfinance as yf
    rows = []
    for i in range(0, len(tickers), batch):
        part = tickers[i:i + batch]
        for attempt in range(4):
            try:
                d = yf.download(part, start=START, end=END, interval="1d", auto_adjust=False, actions=False,
                                group_by="ticker", progress=False, threads=True)
                break
            except Exception as exc:                       # Rate-Limit: warten und erneut
                print("Fehler", repr(exc)[:120]); time.sleep(10 * 2 ** attempt); d = None
        if d is None or d.empty:
            continue
        for t in part:
            try:
                x = d[t] if isinstance(d.columns, pd.MultiIndex) else d
            except KeyError:
                continue
            x = x.dropna(subset=["Close"])
            if not len(x):
                continue
            x = x.rename(columns={"Adj Close": "AdjClose"})[["Open", "High", "Low", "Close", "AdjClose", "Volume"]]
            x.index = pd.to_datetime(x.index).tz_localize(None)
            rows.append(x.assign(ticker=t).reset_index(names="date"))
        print(f"  {min(i + batch, len(tickers))}/{len(tickers)} geladen", flush=True)
        time.sleep(pause)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--out", default="out")
    ap.add_argument("--combine")
    a = ap.parse_args(argv)
    out = Path(a.out); out.mkdir(exist_ok=True)
    if a.combine:
        src = Path(a.combine)
        px = pd.concat([pd.read_parquet(p) for p in sorted(src.glob("px_*.parquet"))], ignore_index=True)
        px = px.drop_duplicates(["ticker", "date"]).sort_values(["ticker", "date"]).reset_index(drop=True)
        px.to_parquet(out / "prices_v1.parquet", index=False)
        for name in ("bench", "fx"):
            p = next(src.glob(f"{name}_*.parquet"), None)
            if p:
                pd.read_parquet(p).to_parquet(out / f"{name}_v1.parquet", index=False)
        man = {"version": 1, "created": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "start": START, "end_exclusive": END,
               "source": "Yahoo Finance via yfinance (auto_adjust=False)", "files": {}}
        for p in sorted(out.glob("*.parquet")):
            d = pd.read_parquet(p)
            man["files"][p.name] = {"sha256": sha(p), "rows": len(d), "tickers": int(d["ticker"].nunique()),
                                    "first": str(d["date"].min().date()), "last": str(d["date"].max().date())}
        per = px.groupby("ticker")["date"].agg(["min", "count"])
        man["coverage"] = {"tickers_with_data": int(len(per)), "start_before_2008": int((per["min"] < "2008-01-01").sum()),
                           "start_before_2012": int((per["min"] < "2012-01-01").sum()), "median_bars": int(per["count"].median())}
        (out / "MANIFEST_v1.json").write_text(json.dumps(man, indent=1))
        print(json.dumps(man, indent=1))
        return 0
    uni = pd.read_csv(a.universe, dtype={"ticker": str})
    mine = list(uni["ticker"])[a.shard::a.shards]
    print(f"Shard {a.shard}: {len(mine)} Aktien")
    _dl(mine).to_parquet(out / f"px_{a.shard}.parquet", index=False)
    if a.shard == 0:
        _dl(BENCH, batch=30).to_parquet(out / "bench_0.parquet", index=False)
        _dl(FX, batch=30).to_parquet(out / "fx_0.parquet", index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
