"""Zusätzliche ETFs für Multi-Asset-Strategien (Welle 4) – gleiche Zeitspanne und Form wie bench_v1.

python -m research.strategy_championship.etf_freeze --out etf      → etf/bench_extra_v1.parquet + Manifest
Nur US-ETFs mit Historie möglichst vor 2008 (Anleihen, Gold, Rohstoffe, Immobilien, Schwellenländer, Regionen, Stil).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .data_freeze import END, START, _dl, sha

EXTRA = ["TLT", "IEF", "LQD", "TIP", "AGG", "HYG", "BND", "GLD", "SLV", "DBC", "GSG", "DBA", "VNQ", "IYR", "EEM", "VWO",
         "VEU", "VGK", "EWJ", "IWM", "IWD", "IWF", "MDY", "XLRE", "XLC"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="etf")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(exist_ok=True)
    df = _dl(EXTRA, batch=30)
    p = out / "bench_extra_v1.parquet"
    df.to_parquet(p, index=False)
    first = df.groupby("ticker")["date"].min().astype(str).to_dict()
    (out / "MANIFEST_extra_v1.json").write_text(json.dumps({"start": START, "end_exclusive": END, "tickers": EXTRA,
                                                             "first_date": first, "rows": int(len(df)), "sha256": sha(p)},
                                                            indent=1))
    print(json.dumps(first, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
