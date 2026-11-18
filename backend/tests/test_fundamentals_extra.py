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


def test_annual_fin_builds_fin_table_from_yahoo_frames():
    import pandas as pd
    from backend.fundamentals import annual_fin
    cols = [pd.Timestamp("2025-12-31"), pd.Timestamp("2024-12-31"), pd.Timestamp("2023-12-31"), pd.Timestamp("2022-12-31")]
    inc = pd.DataFrame({c: v for c, v in zip(cols, [[100.0, 40.0, 20.0, 15.0, 1.5], [90.0, 35.0, 18.0, 12.0, 1.2], [80.0, 30.0, 15.0, 10.0, 1.0], [float("nan")] * 5])},
                       index=["TotalRevenue", "GrossProfit", "OperatingIncome", "NetIncome", "DilutedEPS"])
    bal = pd.DataFrame({cols[0]: [5.0, 50.0, 70.0], cols[1]: [4.0, 55.0, 60.0]}, index=["CashAndCashEquivalents", "LongTermDebt", "StockholdersEquity"])
    cf = pd.DataFrame({cols[0]: [12.0], cols[1]: [9.0]}, index=["FreeCashFlow"])
    f = annual_fin(inc, bal, cf, "EUR")
    assert f["y"] == ["2023", "2024", "2025"] and f["fye"] == "12-31" and f["cur"] == "EUR" and f["src"] == "yahoo"
    assert f["rev"] == [80, 90, 100] and f["eps"] == [1.0, 1.2, 1.5] and f["cash"] == [None, 4, 5] and f["fcf"] == [None, 9, 12]
    assert annual_fin(None) is None and annual_fin(inc[[cols[0]]]) is None


def test_split_uses_yahoo_table_only_without_sec():
    from backend import splitdetail as sd
    fund = {"by": {"SAP.DE": {"pe": 1, "fa": {"y": ["2025"], "src": "yahoo"}}, "MSFT": {"pe": 2, "fa": {"y": ["x"]}}}}
    slim, det = sd.split(fund, {"by": {"MSFT": {"y": ["2025"]}}})
    assert "fa" not in slim["by"]["SAP.DE"] and det[sd.bucket("SAP.DE")]["SAP.DE"] == {"fin": {"y": ["2025"], "src": "yahoo"}}
    assert det[sd.bucket("MSFT")]["MSFT"] == {"fin": {"y": ["2025"]}}


def test_monthly_keeps_12_years_with_4_digits():
    import pandas as pd
    from backend.fundamentals import monthly
    idx = pd.date_range("2010-01-01", periods=200, freq="MS")
    m = monthly(pd.DataFrame({"Close": [123.456789 + i for i in range(200)]}, index=idx))
    assert len(m["c"]) == 144 and m["m0"] == idx[-144].strftime("%Y-%m") and m["c"][-1] == 322.5
    assert monthly(pd.DataFrame({"Close": [1.0] * 5}, index=idx[:5])) is None
