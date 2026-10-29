"""Test 28.10.2026 (Nutzer-Frage D-Wave): RSI-Divergenz mit „tiefstem RSI ± 2 Tage um das Kurs-Tief“ statt RSI genau am Tief.

Vorab festgelegt: Die neue Regel wird nur übernommen, wenn (1) das Ø R netto (5.000 €) aller Trades mit neuer Regel in
Train, Validierung UND Holdout mindestens so hoch ist wie mit der alten, und (2) die neu hinzukommenden Trades gepoolt
(Validierung+Holdout) kein schlechteres Ø R haben als die alten Trades (einseitiger Permutationstest, p ≥ 0,05 für „schlechter“).
Beide Signal-Sätze kommen aus demselben Lauf (gleiche Daten, gleicher Scanner, nur die Divergenz-Messung unterscheidet sich).

python -m research.strategy_championship.div_test signals --data DIR --shard K --shards N --out OUT
python -m research.strategy_championship.div_test compare --base A.csv --var B.csv
"""
from __future__ import annotations

import argparse
import copy
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

from backend.config import CONFIG
from backend.indicators import rsi
from backend.scanner import evaluate, find_rsi_divergence
from . import s01
from .data import UNIVERSE, adjusted, load

VAR = copy.deepcopy(CONFIG)
VAR.rsi.rsi_window = 2
_CTX = {}
COLS = ["ticker", "date", "i", "atr", "close", "score", "fib_ok", "fib_ret", "fib_H", "fib_L", "fib_079", "support_ok"]


def _sig(t):
    raw, cur, (start, end) = _CTX["p"][t], _CTX["cur"].get(t, "USD"), _CTX["per"]
    raw = raw.dropna(subset=["Open", "High", "Low", "Close", "AdjClose"])
    raw = raw[raw["Close"] > 0]
    adj = adjusted(raw)
    ok = s01.eligible(adj, cur)
    idx = adj.index
    first = int(np.searchsorted(idx.values, np.datetime64(start - pd.Timedelta(days=14))))
    out = {"base": [], "var": []}
    last = {"base": -99, "var": -99}
    for i in range(first, len(adj)):
        if not ok[i]:
            continue
        w = adj.iloc[max(0, i - s01.WINDOW + 1): i + 1]
        try:
            r = evaluate(w, {"currency": cur}, cfg=VAR, ticker=t)
        except Exception:
            continue
        others = all(c.ok for c in r.criteria if c.mandatory and c.key != "rsi_div")
        if not others:
            continue
        var_ok = r.passed
        base_div, _ = find_rsi_divergence(w["Low"], rsi(w["Close"], CONFIG.rsi.length).to_numpy(), CONFIG.rsi)
        for k, passed in (("base", base_div is not None), ("var", var_ok)):
            if not passed:
                continue
            fresh, last[k] = i - last[k] > s01.GAP, i
            if fresh and start <= idx[i] <= end:
                fz = (r.zone or {}).get("fib") or {}
                lv = fz.get("levels") or {}
                out[k].append({"ticker": t, "date": idx[i], "i": i, "atr": float(r.flags.get("atr") or np.nan),
                               "close": float(r.close), "score": int(r.score), "fib_ok": bool(fz.get("ok")),
                               "fib_ret": float(fz.get("retracement", np.nan)), "fib_H": float((r.zone or {}).get("H") or np.nan),
                               "fib_L": float(fz.get("L", np.nan)), "fib_079": float(lv.get("0.79", np.nan)),
                               "support_ok": bool((r.zone or {}).get("support"))})
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
                print(f"{k + 1}/{len(p)}: alt {len(acc['base'])} / neu {len(acc['var'])}", flush=True)
    for x in acc:
        pd.DataFrame(acc[x], columns=COLS).to_parquet(out / f"{x}_signals_{a.shard}.parquet", index=False)
    print(f"Shard {a.shard}: alt {len(acc['base'])}, neu {len(acc['var'])} Signale")


def perm_p_worse(x, y, n=10000, seed=1):
    """p für „x schlechter als y“."""
    rng = np.random.default_rng(seed); obs = x.mean() - y.mean(); z = np.concatenate([x, y]); k = len(x); c = 0
    for _ in range(n):
        rng.shuffle(z); c += (z[:k].mean() - z[k:].mean()) <= obs
    return (c + 1) / (n + 1)


def compare(a):
    B, V = pd.read_csv(a.base), pd.read_csv(a.var)
    for d in (B, V):
        d["key"] = d["tag"]
    new, gone = V[~V["key"].isin(B["key"])], B[~B["key"].isin(V["key"])]
    AB, ok1 = ("Train", "Validierung", "Holdout"), True
    print(f"Trades alt {len(B)} · neu {len(V)} · hinzu {len(new)} · weg {len(gone)}\n")
    print(f"{'Abschnitt':<12}{'alt Ø R (n)':>22}{'neu Ø R (n)':>22}{'hinzu Ø R (n)':>22}{'weg Ø R (n)':>22}{'Summe R alt → neu':>24}")
    for ab in AB:
        f = lambda d: d[d["abschnitt"] == ab]["R_net_5000"]
        b, v, nw, gn = f(B), f(V), f(new), f(gone)
        ok1 &= v.mean() >= b.mean()
        cell = lambda s: f"{s.mean():+.3f} ({len(s)})" if len(s) else "–"
        print(f"{ab:<12}{cell(b):>22}{cell(v):>22}{cell(nw):>22}{cell(gn):>22}{f'{b.sum():+.0f} → {v.sum():+.0f}':>24}")
    o = lambda d: d[d["abschnitt"].isin(AB[1:])]["R_net_5000"].to_numpy()
    p = perm_p_worse(o(new), o(B)) if len(o(new)) > 5 else float("nan")
    ok2 = not (p < 0.05)
    print(f"\n(1) neu überall ≥ alt: {ok1} · (2) hinzukommende nicht schlechter (p schlechter = {p:.4f}): {ok2}")
    print("ERGEBNIS:", "BESTANDEN – neue Regel übernehmen (mit Freigabe)" if ok1 and ok2 else "NICHT BESTANDEN – alte Regel bleibt")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["signals", "compare"])
    ap.add_argument("--data"); ap.add_argument("--shard", type=int, default=0); ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--out", default="out"); ap.add_argument("--base"); ap.add_argument("--var")
    a = ap.parse_args()
    signals(a) if a.cmd == "signals" else compare(a)
