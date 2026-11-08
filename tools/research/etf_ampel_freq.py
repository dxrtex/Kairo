"""Wie oft stand die neue ETF-Ampel auf welcher Stufe (Monatsenden) – und was folgte in 12 Monaten?
Stufen: Gelegenheit (VIX ≥ 30) · Raten (unter der 200-Tage-Linie UND Kreditmarkt schwach: HYG/IEF unter seinem 200-Tage-Schnitt) · Normal.
    python tools/research/etf_ampel_freq.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np, pandas as pd
from backend.grandtest import _closes

px = _closes(["SPY", "ACWI", "^VIX", "HYG", "IEF"])
for nm in ("SPY", "ACWI"):
    c = px[nm].dropna(); idx = c.index
    sma = c.rolling(200).mean(); vix = px["^VIX"].reindex(idx).ffill()
    cr = (px["HYG"] / px["IEF"]).reindex(idx).ffill(); crw = cr < cr.rolling(200).mean()
    me = pd.Series(idx, index=idx).groupby([idx.year, idx.month]).last().values
    rows = []
    for t in me:
        t = pd.Timestamp(t)
        if pd.isna(sma.get(t)) or pd.isna(cr.get(t)) or pd.isna(cr.rolling(200).mean().get(t)):
            continue
        i = idx.get_loc(t); j = min(len(c) - 1, i + 252)
        if j - i < 240:
            continue
        fwd = c.iloc[j] / c.iloc[i] - 1; mn = c.iloc[i:j].min() / c.iloc[i] - 1
        st = "gelegenheit" if vix[t] >= 30 else "raten" if (c[t] < sma[t] and crw[t]) else "normal"
        rows.append((st, fwd, mn <= -0.10))
    df = pd.DataFrame(rows, columns=["st", "fwd", "dd10"])
    print(f"== {nm} {len(df)} Monatsenden")
    for st, g in df.groupby("st"):
        print(f"  {st:12s} {len(g)/len(df):5.0%}  Ø 12M {g.fwd.mean():+.1%}  Median {g.fwd.median():+.1%}  danach noch −10 %: {g.dd10.mean():.0%}")
