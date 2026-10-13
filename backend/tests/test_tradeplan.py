"""Trade-Plan-Struktur: Basis erkennen, Stop unter der Basis, ohne Basis 10-Tage-Tief, nur Vergangenheit."""

import numpy as np
import pandas as pd

from backend.tradeplan import structure


def frame(lows, highs, closes):
    idx = pd.bdate_range("2026-01-01", periods=len(lows))
    return pd.DataFrame({"Open": closes, "High": highs, "Low": lows, "Close": closes, "Volume": 1e6}, index=idx)


def test_base_detected_and_stop_below_base():
    n = 30
    lows = list(np.linspace(120, 100, n - 5)) + [99.0, 99.5, 99.2, 99.4, 99.3]
    highs = [x + 2 for x in lows[:-5]] + [100.5, 100.8, 100.6, 100.7, 100.9]
    closes = [x + 1 for x in lows[:-5]] + [100.0, 100.2, 100.1, 100.3, 100.5]
    s = structure(frame(lows, highs, closes), atr=2.0)
    assert s["base"]["k"] == 5 and s["base"]["lo"] == 99.0
    assert abs(s["stop"] - (99.0 - 0.25 * 2.0)) < 1e-9 and "Basis" in s["src"]


def test_no_base_uses_10_day_low():
    n = 30
    closes = list(np.linspace(130, 100, n))
    lows = [x - 3 for x in closes]
    highs = [x + 3 for x in closes]
    s = structure(frame(lows, highs, closes), atr=2.0)
    assert s["base"] is None and abs(s["stop"] - (min(lows[-10:]) - 0.5)) < 1e-9


def test_future_bars_do_not_change_past_structure():
    n = 40
    rng = np.random.default_rng(3)
    closes = list(100 + np.cumsum(rng.normal(0, 1, n)))
    lows = [x - 1 for x in closes]
    highs = [x + 1 for x in closes]
    df = frame(lows, highs, closes)
    a = structure(df.iloc[:30], atr=2.0)
    b = structure(df.iloc[:31].iloc[:30], atr=2.0)
    assert a == b


def test_marks_above_close_sorted_and_merged():
    import pandas as pd
    from backend.tradeplan import structure
    n = 30
    c = [100 - i * 0.5 for i in range(n - 5)] + [88, 88.5, 88.2, 88.4, 88.3]
    df = pd.DataFrame({"Open": c, "High": [x + 0.5 for x in c], "Low": [x - 0.5 for x in c], "Close": c})
    pl = structure(df, 1.0, {"0": 120, "0.618": 95.0, "0.706": 95.2, "1": 80})
    vals = [v for _, v in pl["tg"]]
    assert vals == sorted(vals) and all(v > 88.3 for v in vals) and len(vals) <= 4
    assert any("Fib 0,618 / Fib 0,706" in lb for lb, _ in pl["tg"])


def test_nan_inputs_give_no_nan_in_json():
    import json
    import math
    import pandas as pd
    from backend.tradeplan import structure
    c = [100 - i * 0.3 for i in range(30)]
    df = pd.DataFrame({"Open": c, "High": [x + 0.5 for x in c], "Low": [x - 0.5 for x in c], "Close": c})
    assert structure(df, float("nan")) == {}
    pl = structure(df, 1.0, {"0.618": float("nan"), "0.5": 120.0})
    json.dumps(pl, allow_nan=False)                     # wirft bei NaN/Infinity
    assert all(not math.isnan(v) for _, v in pl["tg"])


def test_only_tested_base_counts():
    """Kairo: nur 5 Tage ≤ 1,5 ATR; eine 3-Tage-Spanne reicht nicht (ungetestet), beim Trend-Rücksetzer schon."""
    n = 30
    lows = list(np.linspace(120, 100, n - 3)) + [99.0, 99.5, 99.2]
    highs = [x + 3 for x in lows[:-3]] + [101.0, 101.5, 101.2]
    closes = [x + 1 for x in lows]
    df = frame(lows, highs, closes)
    assert structure(df, atr=2.0)["base"] is None
    assert structure(df, atr=2.0, kind="trend")["base"]["k"] == 3
