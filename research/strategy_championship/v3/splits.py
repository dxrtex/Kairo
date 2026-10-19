"""Protokoll v3.0 – Aktiensplits (Yahoo, kostenlos) für die Umrechnung der XBRL-Aktienanzahl (K2-Börsenwert).

python -m research.strategy_championship.v3.splits --sec DIR --data DIR --out splits_v3.csv
Prüft zusätzlich an jedem Split-Tag, ob die eingefrorenen Kurse (Datensatz v1, Spalte Close) split-bereinigt sind.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd


def main(argv=None) -> int:
    import yfinance as yf
    ap = argparse.ArgumentParser()
    ap.add_argument("--sec", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default="splits_v3.csv")
    a = ap.parse_args(argv)
    tick = pd.read_csv(Path(a.sec) / "cik_map.csv")["ticker"].tolist()
    rows, failed = [], []
    for i in range(0, len(tick), 50):
        part = tick[i:i + 50]
        for rnd in range(3):
            try:
                d = yf.download(part, start="2008-01-01", end="2026-10-17", actions=True, auto_adjust=False, progress=False,
                                threads=True, group_by="ticker")
                break
            except Exception as e:
                print("Fehler", repr(e)[:100], flush=True)
                time.sleep(20)
        else:
            failed += part
            continue
        for t in part:
            try:
                s = d[t]["Stock Splits"].dropna()
            except Exception:
                failed.append(t)
                continue
            for dt, r in s[s > 0].items():
                rows.append({"ticker": t, "date": pd.Timestamp(dt).strftime("%Y-%m-%d"), "ratio": float(r)})
        time.sleep(2)
    sp = pd.DataFrame(rows, columns=["ticker", "date", "ratio"])
    sp.to_csv(a.out, index=False)
    # Prüfung: Kurssprung am Split-Tag im Datensatz v1?
    px = pd.read_parquet(Path(a.data) / "prices_v1.parquet", columns=["ticker", "date", "Close"],
                         filters=[("ticker", "in", sp["ticker"].unique().tolist())]) if len(sp) else pd.DataFrame()
    jumps = []
    for r in sp[(sp["ratio"] >= 1.5) | (sp["ratio"] <= 0.67)].itertuples(index=False):
        g = px[px["ticker"] == r.ticker].set_index("date")["Close"].sort_index()
        g.index = pd.to_datetime(g.index)
        k = g.index.searchsorted(pd.Timestamp(r.date))
        if 0 < k < len(g):
            jumps.append(abs(np.log(g.iloc[k - 1] / g.iloc[k]) - np.log(r.ratio)) < 0.15)
    info = {"splits": len(sp), "tickers_with_splits": int(sp["ticker"].nunique()), "failed": failed[:50], "n_failed": len(failed),
            "checked": len(jumps), "share_unadjusted_jump": float(np.mean(jumps)) if jumps else None,
            "close_is_split_adjusted": bool(not jumps or np.mean(jumps) < 0.5)}
    Path(a.out).with_suffix(".json").write_text(json.dumps(info, indent=1))
    print(info)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
