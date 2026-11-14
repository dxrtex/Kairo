import math

import pandas as pd

from backend.fundamentals import eps_history, income_history


def test_eps_history_sorts_and_drops_future():
    ix = pd.to_datetime(["2027-02-01", "2026-11-01", "2026-08-01", "2026-05-01"])
    df = pd.DataFrame({"EPS Estimate": [1.1, 1.0, 0.9, math.nan], "Reported EPS": [math.nan, 1.2, 0.8, 0.7]}, index=ix)
    assert eps_history(df) == [["2026-05-01", None, 0.7], ["2026-08-01", 0.9, 0.8], ["2026-11-01", 1.0, 1.2]]


def test_income_history_rows_and_order():
    df = pd.DataFrame({pd.Timestamp("2025-12-31"): [200.0, 20.0], pd.Timestamp("2024-12-31"): [150.0, -5.0]}, index=["TotalRevenue", "NetIncome"])
    assert income_history(df) == [["2024", 150, -5], ["2025", 200, 20]]


def test_empty_inputs():
    assert eps_history(None) == [] and income_history(pd.DataFrame()) == []
