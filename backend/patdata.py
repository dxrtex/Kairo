"""Kursverläufe für die Formations-Studie (tools/patstudy.js) herunterladen – 10 Jahre Tageskerzen je Aktie.

    python -m backend.patdata --shard 0 --shards 8 --n 1200 --period 10y   → pat_px_0.json

Ändert nichts an Scan oder App.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--n", type=int, default=1200)
    ap.add_argument("--period", default="10y")
    a = ap.parse_args(argv)
    from .data_provider import YFinanceProvider
    from .universe import load as load_universe

    tickers = list(load_universe()["ticker"])
    random.Random(11).shuffle(tickers)
    mine = tickers[: a.n][a.shard::a.shards]
    data = YFinanceProvider().history(mine, a.period)
    out = {}
    for t, df in data.items():
        df = df.dropna(subset=["Close"])
        if len(df) < 400:
            continue
        r = lambda s: [None if v != v else round(float(v), 4) for v in s]
        out[t] = {"t": [d.strftime("%Y-%m-%d") for d in df.index], "o": r(df["Open"]), "h": r(df["High"]), "l": r(df["Low"]),
                  "c": r(df["Close"]), "v": [None if v != v else int(v) for v in df["Volume"]]}
    Path(f"pat_px_{a.shard}.json").write_text(json.dumps(out, separators=(",", ":")))
    print(f"Shard {a.shard}: {len(out)} von {len(mine)} Aktien")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
