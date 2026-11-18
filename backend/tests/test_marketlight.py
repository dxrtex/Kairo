import numpy as np
import pandas as pd

from backend import marketlight as ML


def _df(vals):
    idx = pd.bdate_range("2024-01-01", periods=len(vals))
    return pd.DataFrame({"Close": vals, "Volume": np.full(len(vals), 1e9)}, index=idx)


def test_steady_uptrend_is_green():
    x = ML.light(_df(np.linspace(100, 160, 520)))
    assert x and x["lv"] == 3 and x["k"] == "bull"


def test_crash_is_red_immediately():
    v = np.concatenate([np.linspace(100, 160, 500), np.linspace(160, 120, 20)])
    x = ML.light(_df(v))
    assert x and x["lv"] == 0


def test_pullback_in_uptrend_is_not_green():
    v = np.concatenate([np.linspace(100, 160, 500), np.linspace(160, 151, 12)])
    x = ML.light(_df(v))
    assert x and x["lv"] in (1, 2)


def test_upgrade_needs_confirmation():
    raw = pd.Series([3, 3, 1, 3, 3, 3, 3, 3, 3], dtype=float)
    out = ML.smooth(raw, 5).tolist()
    assert out[2] == 1 and out[6] == 1 and out[7] == 3


def test_overall_is_weaker_us_index():
    up = _df(np.linspace(100, 160, 520))
    dn = _df(np.concatenate([np.linspace(100, 160, 500), np.linspace(160, 120, 20)]))
    lt = ML.market_lights({"^GSPC": up, "^NDX": dn})
    assert lt["all"]["lv"] == 0 and lt["all"]["src"] == "^NDX"
