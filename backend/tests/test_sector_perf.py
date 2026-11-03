import numpy as np
import pandas as pd

from backend.analysis import industry_group, market_context, perf_row


def _df(n=300, start="2025-01-02", step=0.001):
    idx = pd.bdate_range(start, periods=n)
    c = 100 * np.cumprod(np.full(n, 1 + step))
    return pd.DataFrame({"Open": c, "High": c, "Low": c, "Close": c}, index=idx)


def test_perf_row_periods_and_lag():
    r = perf_row(_df())
    assert abs(r["d1"] - 0.001) < 1e-4 and abs(r["m1"] - (1.001 ** 21 - 1)) < 1e-4
    assert r["ytd"] is not None and r["p"]["w1"] is not None and r["p"]["d1"] is not None


def test_industry_group_mapping():
    assert industry_group("Semiconductors") == "SOXX"
    assert industry_group("REIT - Office") == "VNQ"
    assert industry_group("Unbekannt") is None and industry_group(None) is None and industry_group(float("nan")) is None


def test_market_context_industries_sorted():
    out = market_context({"XLK": _df(step=0.002), "XLE": _df(step=-0.001), "SOXX": _df(step=0.003), "GDX": _df(step=0.0005)})
    assert [s["k"] for s in out["sectors"]] == ["XLK", "XLE"] and "w1" in out["sectors"][0]
    assert [s["k"] for s in out["industries"]] == ["SOXX", "GDX"]
