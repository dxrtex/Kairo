import numpy as np

from backend.scanner import evaluate
from backend.tests.test_scanner import _df


def _cap(res):
    return next(c for c in res.criteria if c.key == "cap")


def test_small_cap_fails_without_watchlist():
    df = _df(np.linspace(50, 120, 420))
    c = _cap(evaluate(df, {"currency": "USD", "market_cap": 1.2e9}))
    assert not c.ok and "Watchlist" not in c.value


def test_small_cap_counts_on_watchlist():
    df = _df(np.linspace(50, 120, 420))
    c = _cap(evaluate(df, {"currency": "USD", "market_cap": 1.2e9, "watch": True}))
    assert c.ok and "Watchlist" in c.value


def test_big_cap_unchanged_on_watchlist():
    df = _df(np.linspace(50, 120, 420))
    a = _cap(evaluate(df, {"currency": "USD", "market_cap": 5e9}))
    b = _cap(evaluate(df, {"currency": "USD", "market_cap": 5e9, "watch": True}))
    assert a.ok and b.ok and a.value == b.value
