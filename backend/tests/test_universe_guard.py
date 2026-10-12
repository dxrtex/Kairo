"""Aussetzer des Screeners dürfen die Aktienliste nicht schrumpfen lassen."""

import pandas as pd

from backend.universe import guard


def test_guard_fills_missing_on_big_drop():
    prev = pd.DataFrame({"ticker": [f"T{i}" for i in range(100)], "name": "x"})
    new = prev.iloc[:60]
    out = guard(new, prev, "us")
    assert len(out) == 100 and set(out["ticker"]) == set(prev["ticker"])


def test_guard_keeps_normal_changes():
    prev = pd.DataFrame({"ticker": [f"T{i}" for i in range(100)], "name": "x"})
    new = pd.concat([prev.iloc[:95], pd.DataFrame({"ticker": ["NEU"], "name": "y"})])
    assert len(guard(new, prev, "us")) == 96 and len(guard(new, None, "us")) == 96
