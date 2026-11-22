import numpy as np
import pandas as pd

from backend.shortside import LABELS, UNIVERSE, compact, detail, evaluate_short, invert


def _df(vals):
    idx = pd.bdate_range("2024-01-01", periods=len(vals))
    c = pd.Series(vals, index=idx, dtype=float)
    return pd.DataFrame({"Open": c.shift(1).fillna(c), "High": c * 1.01, "Low": c * 0.99, "Close": c, "Volume": 2e6})


def test_invert_twice_is_identity_and_keeps_last_close():
    df = _df(np.linspace(50, 80, 300))
    inv = invert(df)
    assert abs(inv["Close"].iloc[-1] - df["Close"].iloc[-1]) < 1e-9
    assert (inv["High"] >= inv["Low"]).all()
    back = invert(inv)
    assert np.allclose(back["Close"], df["Close"])


def test_short_plan_has_stop_above_and_targets_below():
    v = np.concatenate([np.linspace(100, 60, 200), np.linspace(60, 82, 60), 82 + np.sin(np.arange(20)) * 0.3])
    res, plan = evaluate_short(_df(v), {"market_cap_usd": 5e10})
    c = compact(res, plan)
    assert c["of"] == 11 and 0 <= c["met"] <= 11
    if plan.get("stop"):
        assert plan["stop"] > v[-1] and plan["target2"] < v[-1]
    d = detail(res, plan)
    assert len(d["crit"]) == 11 and all(k in LABELS and k not in UNIVERSE for k, *_ in d["crit"])
