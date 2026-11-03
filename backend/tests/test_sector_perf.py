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


def test_day_moves_periods_and_rvol():
    from backend.run_scan import day_moves
    df = _df(n=80, start="2024-11-01")
    df["Volume"] = 1000.0
    df.iloc[-1, df.columns.get_loc("Volume")] = 3000.0
    r = day_moves(df)
    assert r["rv"] == 3.0 and r["m1"] is not None and r["m3"] is not None and r["ytd"] is not None


def test_rank_history():
    out = market_context({"XLK": _df(step=0.002), "XLE": _df(step=-0.001), "XLV": _df(step=0.0005)})
    rh = {s["k"]: s["rh"] for s in out["sectors"]}
    assert len(rh["XLK"]) == 13 and rh["XLK"][-1] == 1 and rh["XLE"][-1] == 3


def test_rotation_quadrants_and_hot():
    from backend.analysis import rotation
    n = 300
    idx = pd.bdate_range("2025-01-02", periods=n)
    mk = lambda c: pd.DataFrame({"Open": c, "High": c, "Low": c, "Close": c}, index=idx)
    base = 100 * np.cumprod(np.full(n, 1.0005))
    up_late = base * np.r_[np.ones(n - 30), np.cumprod(np.full(30, 1.004))]          # zieht zuletzt an → stärker, Schwung hoch
    down_late = base * np.r_[np.ones(n - 30), np.cumprod(np.full(30, 0.996))]
    hist = {"^GSPC": mk(base), "A": mk(up_late), "B": mk(down_late), "C": mk(base * 1.0), "D": mk(base), "E": mk(base)}
    rows = [{"k": k} for k in "ABCDE"]
    rotation(rows, hist, hot_n=2)
    by = {x["k"]: x for x in rows}
    assert by["A"]["rrg"]["q"] == "leading" and by["B"]["rrg"]["q"] == "lagging"
    assert len(by["A"]["rrg"]["tail"]) == 5 and "hot" in by["A"] and "hot" not in by["B"]
