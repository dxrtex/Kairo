"""Heutige Yahoo-Branche je US-Titel (für den Sektor-ETF-Vergleich in S19; nicht zeitpunktgenau, ändert sich selten).

python -m research.strategy_championship.sectors --out DIR
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd
import yfinance as yf

from .data import UNIVERSE


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="sectors")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    uni = pd.read_csv(UNIVERSE)
    us = [t for t in uni.loc[uni["region"] == "us", "ticker"] if not t.endswith(".TO")]
    rows = []
    for k, t in enumerate(us):
        sec = None
        for n in range(3):
            try:
                info = yf.Ticker(t).get_info()
                sec = info.get("sector")
                break
            except Exception:
                time.sleep(2 * (n + 1))
        rows.append({"ticker": t, "sector": sec})
        if k % 200 == 0:
            print(f"{k + 1}/{len(us)} {t}: {sec}", flush=True)
        time.sleep(0.15)
    df = pd.DataFrame(rows)
    df.to_csv(out / "sectors_v1.csv", index=False)
    print(f"{len(df)} Titel, mit Branche {df['sector'].notna().sum()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
