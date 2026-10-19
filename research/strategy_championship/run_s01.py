"""B2 – S01-Signale eines Shards (Trainingszeitraum) + Gegenrechnung jedes Signals gegen den Alt-Simulator.

python -m research.strategy_championship.run_s01 --data DIR --shard K --shards N --out OUT
"""

from __future__ import annotations

import argparse
import json
from multiprocessing import Pool
from pathlib import Path

import pandas as pd

from . import crosscheck, s01
from .data import UNIVERSE, load

_CTX = {}


def _one(t):
    df, cur, (s, e) = _CTX["p"][t], _CTX["cur"].get(t, "USD"), _CTX["per"]
    try:
        sg = s01.signals(df, cur, s, e, t)
    except Exception as ex:                          # pragma: no cover - im Lauf protokolliert
        return t, [], [{"ticker": t, "error": repr(ex)}]
    cc = []
    for x in ([] if _CTX.get("nocc") else sg):
        try:
            cc.append(crosscheck.compare(df, t, x))
        except Exception as ex:
            cc.append({"ticker": t, "date": str(x["date"].date()), "error": repr(ex)})
    return t, sg, cc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--out", default="out")
    ap.add_argument("--period", default="train")
    ap.add_argument("--tickers", nargs="*")
    ap.add_argument("--no-crosscheck", action="store_true")
    a = ap.parse_args(argv)
    uni = sorted(pd.read_csv(UNIVERSE)["ticker"])
    mine = a.tickers or [t for k, t in enumerate(uni) if k % a.shards == a.shard]
    p, cur, _fx, _b, per = load(a.data, a.period, mine)
    _CTX.update(p=p, cur=cur, per=per, nocc=a.no_crosscheck)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sigs, ccs = [], []
    with Pool() as pool:
        for k, (t, sg, cc) in enumerate(pool.imap_unordered(_one, sorted(p), chunksize=1)):
            sigs += sg
            ccs += cc
            if k % 10 == 0:
                print(f"{k + 1}/{len(p)} {t}: {len(sg)} Signale", flush=True)
    pd.DataFrame(sigs, columns=["ticker", "date", "i", "atr", "close", "score", "fib_ok", "fib_ret", "fib_H", "fib_L",
                                "fib_079", "support_ok"]).to_parquet(out / f"s01_signals_{a.shard}.parquet", index=False)
    (out / f"crosscheck_{a.shard}.json").write_text(json.dumps(ccs, default=str))
    ok = sum(1 for c in ccs if c.get("match"))
    print(f"Shard {a.shard}: {len(p)} Titel, {len(sigs)} Signale, Gegenrechnung {ok}/{len(ccs)} gleich")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
