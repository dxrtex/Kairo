"""Protokoll v2.4 – Welche Merkmale machen Kairo-Treffer besser? (Trades aus kairo_null, 2008–2026)

python -m research.strategy_championship.kairo_features --data DIR --signals FILE --trades CSV --out OUT

Merkmale je Treffer (nur Information bis zum Signaltag):
  score (Kairo-Score, Terzile) · zone (Fib / nur Support) · markt (S&P 500 über/unter EMA200) · mom (eigene Rendite
  Monat −6…−1, Terzile) · vola (ATR ÷ Kurs, Terzile) · region (US/EU) · tiefe (Abstand Kurs zum Swing-Hoch, Terzile)
Vorgehen: Terzil-Grenzen nur aus Train. Je Merkmal beste und schlechteste Gruppe aus Train; bestätigt, wenn dieselbe
Reihenfolge in Validierung UND Holdout gilt und der Unterschied gepoolt (Validierung+Holdout) p ≤ 0,05/7 hat.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import s01
from .data import load
from .fib_test import perm_p

FEATS = ["score", "zone", "markt", "mom", "vola", "region", "tiefe"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--signals", required=True)
    ap.add_argument("--trades", required=True)
    ap.add_argument("--out", default="kf_out")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sig = pd.read_parquet(a.signals)
    sig["gid"] = sig["ticker"] + "|" + pd.to_datetime(sig["date"]).dt.date.astype(str)
    t = pd.read_csv(a.trades).merge(sig, left_on="tag", right_on="gid", how="left", suffixes=("", "_s"))
    prices, cur, _fx, bench, _ = load(a.data, "full", sorted(t["ticker"].unique()))
    from .data import UNIVERSE
    region = dict(zip(pd.read_csv(UNIVERSE)["ticker"], pd.read_csv(UNIVERSE)["region"]))
    g = bench["^GSPC"]["Close"]
    bull = (g > g.ewm(span=200, adjust=False).mean())
    mom = {}
    for tk, df in prices.items():
        A = s01.adjusted(s01.clean(df))
        mom[tk] = (A["Close"].shift(21) / A["Close"].shift(126) - 1)
    t["date"] = pd.to_datetime(t["date"])
    t["markt"] = [("gut" if bool(bull.asof(d)) else "schlecht") for d in t["date"]]
    t["mom_v"] = [float(mom[tk].asof(d)) if tk in mom else np.nan for tk, d in zip(t["ticker"], t["date"])]
    t["vola_v"] = t["atr"] / t["close"]
    t["tiefe_v"] = 1 - t["close"] / t["fib_H"]
    t["zone"] = np.where(t["fib_ok"], "Fib", "nur Support")
    t["region"] = t["ticker"].map(lambda x: region.get(x, "?"))
    tr = t[t["abschnitt"] == "Train"]
    for f, col in (("score", "score"), ("mom", "mom_v"), ("vola", "vola_v"), ("tiefe", "tiefe_v")):
        q1, q2 = tr[col].quantile([1 / 3, 2 / 3])
        t[f] = np.select([t[col] <= q1, t[col] <= q2], ["niedrig", "mittel"], "hoch")
        t.loc[t[col].isna(), f] = np.nan
    res = {}
    for f in FEATS:
        tab = {ab: {k: {"n": int(len(v)), "R_net": round(float(v["R_net_5000"].mean()), 3)} for k, v in t[t["abschnitt"] == ab].groupby(f)}
               for ab in ("Train", "Validierung", "Holdout")}
        trm = tab["Train"]
        if len(trm) < 2:
            continue
        best = max(trm, key=lambda k: trm[k]["R_net"])
        worst = min(trm, key=lambda k: trm[k]["R_net"])
        same = all(tab[ab].get(best, {}).get("R_net", -9) > tab[ab].get(worst, {}).get("R_net", 9) for ab in ("Validierung", "Holdout"))
        oos = t[t["abschnitt"].isin(["Validierung", "Holdout"])]
        p = perm_p(oos.loc[oos[f] == best, "R_net_5000"].to_numpy(), oos.loc[oos[f] == worst, "R_net_5000"].to_numpy(), n=5000)
        res[f] = {"tabelle": tab, "beste": best, "schlechteste": worst, "gleiche_richtung": same, "p_oos": p,
                  "bestaetigt": bool(same and p <= 0.05 / len(FEATS))}
        print(f"{f:7s} Train beste={best} schlechteste={worst} | Richtung hält: {same} | p={p:.4f} | "
              f"{'BESTÄTIGT' if res[f]['bestaetigt'] else '–'}", flush=True)
        for ab in ("Train", "Validierung", "Holdout"):
            print("   ", ab, {k: v["R_net"] for k, v in tab[ab].items()})
    (out / "kairo_features.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
