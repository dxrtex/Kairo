from backend.finhist import annual, parse


def _dur(y, v, form="10-K", filed=None, start=None):
    return {"start": start or f"{y - 1}-10-01", "end": f"{y}-09-30", "val": v, "form": form, "fp": "FY", "filed": filed or f"{y}-11-01"}


def _inst(y, v):
    return {"end": f"{y}-09-30", "val": v, "form": "10-K", "fp": "FY", "filed": f"{y}-11-01"}


FACTS = {
    "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [_dur(y, 100e9 + y) for y in range(2017, 2026)]
        + [{"start": "2025-07-01", "end": "2025-09-30", "val": 1, "form": "10-K", "fp": "FY", "filed": "2025-11-01"}]}},   # Quartal im 10-K → ignorieren
    "NetIncomeLoss": {"units": {"USD": [_dur(y, 20e9) for y in range(2019, 2026)] + [_dur(2024, 25e9, filed="2025-11-01")]}},  # Korrektur gilt
    "EarningsPerShareDiluted": {"units": {"USD/shares": [_dur(y, 6.123) for y in range(2020, 2026)]}},
    "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": [_dur(y, 30e9) for y in range(2020, 2026)]}},
    "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": [_dur(y, 10e9) for y in range(2020, 2026)]}},
    "StockholdersEquity": {"units": {"USD": [_inst(y, 50e9) for y in range(2018, 2026)] + [{"end": "2025-06-30", "val": 1, "form": "10-Q", "fp": "Q3"}]}},
}


def test_annual_skips_quarters_and_10q():
    a = annual(FACTS, "RevenueFromContractWithCustomerExcludingAssessedTax", False)
    assert "2025-09-30" in a and a["2025-09-30"] == 100e9 + 2025
    assert annual(FACTS, "StockholdersEquity", True).get("2025-06-30") is None


def test_parse_six_years_fcf_and_restated():
    p = parse(FACTS)
    assert p["y"] == ["2020", "2021", "2022", "2023", "2024", "2025"]
    assert p["fcf"] == [20e9] * 6 and "ocf" not in p and "capex" not in p
    assert p["ni"][4] == 25e9
    assert p["eps"][0] == 6.12
    assert p["eq"][-1] == 50e9 and "debt" not in p


def test_parse_none_without_revenue_or_income():
    assert parse({"GrossProfit": FACTS["NetIncomeLoss"]}) is None


def test_parse_merges_tag_switch():
    f = {"Revenues": {"units": {"USD": [_dur(y, 1e9) for y in range(2014, 2019)]}},
         "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [_dur(y, 2e9) for y in range(2018, 2026)]}}}
    p = parse(f)
    assert p["y"][-1] == "2025" and p["rev"][-1] == 2e9 and len(p["y"]) == 6


def test_filings_list():
    from backend.finhist import filings
    sub = {"cik": "0000320193", "filings": {"recent": {"form": ["4", "8-K", "10-Q"], "accessionNumber": ["a", "0000320193-26-000001", "0000320193-26-000002"],
           "filingDate": ["2026-11-01", "2026-10-30", "2026-08-01"], "primaryDocument": ["x.xml", "a8k.htm", "q.htm"], "items": ["", "2.02,9.01", ""],
           "primaryDocDescription": ["", "8-K", "10-Q"]}}}
    fl = filings(sub)
    assert [f[1] for f in fl] == ["8-K", "10-Q"]
    assert fl[0][2] == "Quartalszahlen" and fl[0][3].endswith("/320193/000032019326000001/a8k.htm")
