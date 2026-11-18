import pandas as pd

from backend.fundamentals import quarter_revenue, short_desc, updowns


def test_quarter_revenue():
    df = pd.DataFrame({pd.Timestamp("2026-06-30"): [10.0], pd.Timestamp("2026-03-31"): [9.0]}, index=["Total Revenue"])
    assert quarter_revenue(df) == [["2026-03-31", 9], ["2026-06-30", 10]]


def test_updowns_newest_first():
    df = pd.DataFrame({"Firm": ["A", "B"], "ToGrade": ["Buy", "Hold"], "FromGrade": ["Hold", "Buy"], "Action": ["up", "down"], "currentPriceTarget": [100, 0]},
                      index=pd.to_datetime(["2026-01-01", "2026-02-01"]))
    u = updowns(df)
    assert u[0][:5] == ["2026-02-01", "B", "Buy", "Hold", "down"] and u[0][5] is None and u[1][5] == 100


def test_short_desc():
    t = "Apple Inc. designs phones. It sells services worldwide. " + "x" * 400
    d = short_desc(t)
    assert d.startswith("Apple Inc") and len(d) <= 341
    assert short_desc("") == ""
