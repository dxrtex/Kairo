from backend.analysis import home_region
from backend.sector_backfill import todo


def test_todo_largest_first_without_branch():
    rows = [{"t": "A", "mc": 5}, {"t": "B", "mc": 9}, {"t": "C", "mc": 1, "ig": "JETS"}, {"t": "D", "mc": 7}, {"t": "E"}]
    senti = {"D": {"ind": "Airlines"}}               # Branche schon bekannt → nicht erneut abfragen
    assert todo(rows, senti) == ["B", "A", "E"]


def test_todo_us_listing_without_country():
    rows = [{"t": "ASML", "mc": 9, "r": "us", "ig": "SOXX"}, {"t": "IFX.DE", "mc": 5, "r": "europe", "ig": "SOXX"},
            {"t": "NVDA", "mc": 8, "r": "us", "ig": "SOXX"}]
    assert todo(rows, {"NVDA": {"co": "United States"}}) == ["ASML"]


def test_home_region():
    assert home_region("Netherlands") == "europe"
    assert home_region("Taiwan") == "asia"
    assert home_region("United States") == "us"
    assert home_region("Ireland") is None and home_region(None) is None
