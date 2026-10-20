"""Stimmung/Angst: ruhiger Markt → niedrig, Ausverkauf mit VIX-Sprung → hoch."""
import numpy as np
import pandas as pd

from backend import fear


def _df(vals):
    idx = pd.bdate_range("2025-01-01", periods=len(vals))
    return pd.DataFrame({"Close": vals}, index=idx)


def _hist(vix, vix3m, ndx, smh, hyg):
    n = len(ndx)
    return {"^VIX": _df(vix), "^VIX3M": _df(vix3m), "^NDX": _df(ndx), "SMH": _df(smh), "HYG": _df(hyg), "IEF": _df(np.full(n, 100.0))}


def test_calm_vs_panic():
    n = 300
    up = np.linspace(100, 130, n)
    calm = fear.fear(_hist(np.full(n, 13.0), np.full(n, 16.0), up, up, np.full(n, 80.0)), {"n": 5000, "above50": 0.72, "lows": 0.002})
    crash = np.r_[up[:-20], np.linspace(130, 100, 20)]
    vix = np.r_[np.full(n - 6, 15.0), [18, 22, 26, 30, 34, 38.0]]
    panic = fear.fear(_hist(vix, np.full(n, 28.0), crash, crash, np.r_[np.full(n - 20, 80.0), np.linspace(80, 76, 20)]),
                      {"n": 5000, "above50": 0.22, "lows": 0.09})
    assert calm["score"] < 25 and calm["label"] == "Sorglos"
    assert panic["score"] >= 80 and panic["label"] == "Panik" and panic["tone"] == "red"
    assert {p["k"] for p in panic["parts"]} == {"vix", "vix5", "term", "tech", "breadth", "lows", "credit"}


def test_breadth_needs_enough_stocks():
    assert fear.breadth([_df(np.linspace(1, 2, 100))] * 10) is None
    b = fear.breadth([_df(np.linspace(1, 2, 300))] * 250)
    assert b["above50"] == 1.0 and b["lows"] == 0.0
