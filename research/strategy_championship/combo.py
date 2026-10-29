"""Kombi-Test (Nutzer-Auftrag 28./29.10.2026): alle in der Schwellen-Prüfung bestandenen Werte GEMEINSAM gegen heute.

Vorab festgelegt: Übernahme nur, wenn die Kombination in Train, Validierung UND Holdout ein höheres Ø R netto (5.000 €)
hat als heute und mindestens 50 % der heutigen Trades behält. Beide Signal-Sätze aus demselben Lauf.
Änderungen kommen als JSON (combo.json), z. B. {"correction.min_drawdown": 0.15, "rsi.rsi_window": 2}.

python -m research.strategy_championship.combo signals --data DIR --shard K --shards N --out OUT
python -m research.strategy_championship.combo compare --base A.csv --var B.csv
"""
from __future__ import annotations

import argparse
import copy
import json
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

from backend.config import CONFIG
from backend.scanner import evaluate
from . import s01
from .data import UNIVERSE, adjusted, load

HERE = Path(__file__).parent
OVR = json.loads((HERE / "combo.json").read_text())
VAR = copy.deepcopy(CONFIG)
for k, v in OVR.items():
    if k.startswith("_"):
        continue
    obj, *path, last = k.split(".")
    node = getattr(VAR, obj)
    for p in path:
        node = getattr(node, p)
    setattr(node, last, tuple(v) if isinstance(v, list) else v)
DROP = set(OVR.get("_drop", []))          # Kriterien, die ganz wegfallen
COLS = ["ticker", "date", "i", "atr", "close", "score"]
_CTX = {}


def _passed(r):
    return all(c.ok for c in r.criteria if c.mandatory and c.key not in DROP)


def _sig(t):
    raw, cur, (start, end) = _CTX["p"][t], _CTX["cur"].get(t, "USD"), _CTX["per"]
    raw = raw.dropna(subset=["Open", "High", "Low", "Close", "AdjClose"])
    raw = raw[raw["Close"] > 0]
    adj = adjusted(raw)
    ok = s01.eligible(adj, cur)
    idx = adj.index
    first = int(np.searchsorted(idx.values, np.datetime64(start - pd.Timedelta(days=14))))
    out, last = {"base": [], "var": []}, {"base": -99, "var": -99}
    for i in range(first, len(adj)):
        if not ok[i]:
            continue
        w = adj.iloc[max(0, i - s01.WINDOW + 1): i + 1]
        for k, cfg in (("base", CONFIG), ("var", VAR)):
            try:
                r = evaluate(w, {"currency": cur}, cfg=cfg, ticker=t)
            except Exception:
                continue
            if not (r.passed if k == "base" else _passed(r)):
                continue
            fresh, last[k] = i - last[k] > s01.GAP, i
            if fresh and start <= idx[i] <= end:
                out[k].append({"ticker": t, "date": idx[i], "i": i, "atr": float(r.flags.get("atr") or np.nan), "close": float(r.close), "score": int(r.score)})
    return out


def signals(a):
    uni = sorted(pd.read_csv(UNIVERSE)["ticker"])
    mine = [t for k, t in enumerate(uni) if k % a.shards == a.shard]
    p, cur, _fx, _b, per = load(a.data, "full", mine)
    _CTX.update(p=p, cur=cur, per=per)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    acc = {"base": [], "var": []}
    with Pool() as pool:
        for k, o in enumerate(pool.imap_unordered(_sig, sorted(p), chunksize=1)):
            for x in acc:
                acc[x] += o[x]
            if k % 20 == 0:
                print(f"{k + 1}/{len(p)}: heute {len(acc['base'])} / Kombi {len(acc['var'])}", flush=True)
    for x in acc:
        pd.DataFrame(acc[x], columns=COLS).to_parquet(out / f"{x}_signals_{a.shard}.parquet", index=False)


def compare(a):
    B, V = pd.read_csv(a.base), pd.read_csv(a.var)
    AB, ok = ("Train", "Validierung", "Holdout"), True
    print("Änderungen:", json.dumps(OVR, ensure_ascii=False))
    for ab in AB:
        b, v = B[B["abschnitt"] == ab]["R_net_5000"], V[V["abschnitt"] == ab]["R_net_5000"]
        ok &= v.mean() > b.mean() and len(v) >= 0.5 * len(b)
        print(f"{ab:<12} heute {b.mean():+.3f} R (n {len(b)}, Σ {b.sum():+.0f}, Quote {(b > 0).mean():.0%})  ·  Kombi {v.mean():+.3f} R (n {len(v)}, Σ {v.sum():+.0f}, Quote {(v > 0).mean():.0%})")
    print("ERGEBNIS:", "BESTANDEN – Kombination übernehmen" if ok else "NICHT BESTANDEN")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["signals", "compare"])
    ap.add_argument("--data"); ap.add_argument("--shard", type=int, default=0); ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--out", default="out"); ap.add_argument("--base"); ap.add_argument("--var")
    a = ap.parse_args()
    signals(a) if a.cmd == "signals" else compare(a)
