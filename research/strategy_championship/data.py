"""Zugriff auf Datensatz v1 – mit Zeitraum-Sperre.

Jede Auswertung lädt Kurse NUR bis zum Ende des freigegebenen Zeitraums (`period`). Validierung braucht
KAIRO_VALIDATION_UNSEALED=1, der finale Holdout KAIRO_HOLDOUT_UNSEALED=1 (erst nach „FINALEN HOLDOUT FREIGEGEBEN“).
Was nach dem Periodenende liegt, wird abgeschnitten, bevor irgendein Signal oder Trade gerechnet wird.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
UNIVERSE = HERE / "data" / "universe_frozen_2026-10-16.csv"

PERIODS = {
    "train": ("2008-01-01", "2016-12-31"),
    "validation": ("2017-01-01", "2021-12-31"),
    "holdout": ("2022-01-01", "2026-10-16"),
    "trainval": ("2008-01-01", "2021-12-31"),     # Phase D: Train + Validierung durchgehend (nach Gate C)
}
WARMUP_START = "2005-01-01"
FX_TICKERS = {"USD": "EURUSD=X", "GBP": "EURGBP=X", "CHF": "EURCHF=X", "SEK": "EURSEK=X", "NOK": "EURNOK=X",
              "DKK": "EURDKK=X", "PLN": "EURPLN=X", "CAD": "EURCAD=X", "JPY": "EURJPY=X"}


def period(name: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    if name in ("validation", "trainval") and os.environ.get("KAIRO_VALIDATION_UNSEALED") != "1":
        raise PermissionError("Validierung gesperrt (KAIRO_VALIDATION_UNSEALED=1 erst nach Gate C)")
    if name == "holdout" and os.environ.get("KAIRO_HOLDOUT_UNSEALED") != "1":
        raise PermissionError("Finaler Holdout versiegelt – nur nach „FINALEN HOLDOUT FREIGEGEBEN“")
    a, b = PERIODS[name]
    return pd.Timestamp(a), pd.Timestamp(b)


def _cut(df: pd.DataFrame, end: pd.Timestamp) -> pd.DataFrame:
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    return df[df["date"] <= end]


def load(dirpath: str | Path, name: str, tickers: list[str] | None = None):
    """→ (prices {Ticker: DataFrame}, currency {Ticker: Code}, fx {Code: Serie}, bench {Ticker: DataFrame}, (Start, Ende))."""
    start, end = period(name)
    d = Path(dirpath)
    uni = pd.read_csv(UNIVERSE)
    cur = dict(zip(uni["ticker"], uni["currency"].fillna("USD")))
    filt = [("ticker", "in", list(tickers))] if tickers is not None else None
    px = _cut(pd.read_parquet(d / "prices_v1.parquet", filters=filt), end)
    prices = {t: g.drop(columns="ticker").set_index("date").sort_index() for t, g in px.groupby("ticker")}
    fxr = _cut(pd.read_parquet(d / "fx_v1.parquet"), end)
    fx = {}
    for code, yt in FX_TICKERS.items():
        g = fxr[fxr["ticker"] == yt].set_index("date")["Close"].sort_index()
        fx[code] = g[g > 0]
    bench = {t: g.drop(columns="ticker").set_index("date").sort_index()
             for t, g in _cut(pd.read_parquet(d / "bench_v1.parquet"), end).groupby("ticker")}
    return prices, cur, fx, bench, (start, end)


def adjusted(df: pd.DataFrame) -> pd.DataFrame:
    """OHLC wie yfinance auto_adjust=True (Faktor AdjClose/Close), Volumen unverändert – so rechnet der Produktiv-Scanner."""
    f = (df["AdjClose"] / df["Close"]).astype(float)
    out = df[["Open", "High", "Low", "Close"]].mul(f, axis=0)
    out["Volume"] = df["Volume"]
    out["f"] = f
    return out
