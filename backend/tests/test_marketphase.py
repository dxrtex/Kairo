import numpy as np
import pandas as pd

from backend.marketphase import market_phase


def _df(vals, start="2024-01-01"):
    idx = pd.bdate_range(start, periods=len(vals))
    return pd.DataFrame({"Close": vals}, index=idx)


def test_uptrend_is_bull_and_stable():
    v = 100 * np.cumprod(np.full(500, 1.0008))
    p = market_phase(_df(v), _df(np.full(500, 15.0)))
    assert p["k"] == "bull" and p["tone"] == "green" and p["weeks"] > 30 and p["hist"][-1][1] == "bull"


def test_crash_gives_bear_immediately():
    v = list(100 * np.cumprod(np.full(450, 1.0008))) + list(np.linspace(140, 100, 20))
    p = market_phase(_df(v))
    assert p["k"] == "bear" and p["dd"] <= -0.2


def test_single_bad_week_does_not_flip():
    v = list(100 * np.cumprod(np.full(480, 1.0008)))
    v[-3:] = [v[-4] * 0.94] * 3                      # eine Woche −6 %: noch keine Korrektur bestätigt
    p = market_phase(_df(v), _df(np.full(len(v), 15.0)))
    assert p["k"] in ("bull", "neutral")


def test_too_short_returns_none():
    assert market_phase(_df(np.full(100, 1.0))) is None and market_phase(None) is None
