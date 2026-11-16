import json
from datetime import date
from pathlib import Path

from backend import ipos

SAMPLE = {"data": {
    "priced": {"rows": [{"proposedTickerSymbol": "ABCD", "companyName": "Abcd Holdings Inc.", "proposedExchange": "NYSE",
                         "proposedSharePrice": "21.00", "sharesOffered": "10,000,000", "pricedDate": "11/12/2026",
                         "dollarValueOfSharesOffered": "$210,000,000"}]},
    "upcoming": {"upcomingTable": {"rows": [
        {"proposedTickerSymbol": "ANT", "companyName": "Anthropic PBC", "proposedExchange": "NASDAQ Global Select",
         "proposedSharePrice": "100.00-110.00", "sharesOffered": "60,000,000", "expectedPriceDate": "11/19/2026",
         "dollarValueOfSharesOffered": "$6,600,000,000"},
        {"proposedTickerSymbol": "TINY", "companyName": "Tiny Corp", "proposedExchange": "NASDAQ Capital",
         "proposedSharePrice": "4.00", "sharesOffered": "1,000,000", "expectedPriceDate": "11/20/2026", "dollarValueOfSharesOffered": ""}]}},
    "filed": {"rows": []}}}


def test_parse_nasdaq():
    ev = ipos.parse_nasdaq(SAMPLE)
    by = {e["sym"]: e for e in ev}
    assert by["ANT"]["date"] == "2026-11-19" and by["ANT"]["ex"] == "Nasdaq" and by["ANT"]["big"] and by["ANT"]["status"] == "expected"
    assert by["ANT"]["title"] == "Börsengang: Anthropic PBC (ANT)"
    assert by["ABCD"]["status"] == "priced" and by["ABCD"]["date"] == "2026-11-12" and not by["ABCD"]["big"]
    assert by["TINY"]["val"] == 4_000_000 and not by["TINY"]["big"]


def test_parse_empty():
    assert ipos.parse_nasdaq({}) == [] and ipos.parse_nasdaq({"data": None}) == []


def test_manual_and_dedupe(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "ipo_events.json").write_text(json.dumps({"events": [
        {"name": "Anthropic", "date": None, "note": "Termin offen"}, {"name": "Neu AG", "date": "2026-11-25", "region": "europe"}]}))
    monkeypatch.setattr(ipos, "_fetch", lambda ym: SAMPLE)
    ev = ipos.fetch_ipos(date(2026, 11, 16), tmp_path)
    names = [e["name"] for e in ev]
    assert names.count("Anthropic PBC") == 1 and "Anthropic" not in names     # Nasdaq gewinnt vor Handeintrag
    assert any(e["name"] == "Neu AG" and e["region"] == "europe" for e in ev)


def test_manual_open_kept(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "ipo_events.json").write_text(json.dumps({"events": [{"name": "Anthropic", "date": None}]}))
    monkeypatch.setattr(ipos, "_fetch", lambda ym: None)
    ev = ipos.fetch_ipos(date(2026, 11, 16), tmp_path)
    assert len(ev) == 1 and ev[0]["status"] == "open" and ev[0]["date"] is None


def test_repo_manual_file_valid():
    root = Path(__file__).resolve().parents[2]
    l = ipos.manual(root / "data" / "ipo_events.json")
    assert all(e["name"] for e in l)
