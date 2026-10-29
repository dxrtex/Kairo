import json

import pandas as pd

from backend import earnfast


def test_watch_file_cik_und_uhrzeit(tmp_path):
    ev = [{"kind": "earnings", "ticker": "AAPL", "name": "Apple", "date": "2026-10-29", "watch": True},
          {"kind": "earnings", "ticker": "SAP.DE", "name": "SAP", "date": "2026-10-30"},
          {"kind": "earnings", "ticker": "RHM.DE", "name": "Rheinmetall", "date": "2026-10-29"},      # keine SEC-Nummer
          {"kind": "earnings", "ticker": "MSFT", "name": "Microsoft", "date": "2026-11-20"}]         # zu weit weg
    nexts = {"AAPL": {"date": "2026-10-29", "ts": "2026-10-29T16:30:00-04:00"}}
    n = earnfast.watch_file(ev, nexts, tmp_path, pd.Timestamp("2026-10-29"), learn=False)
    j = json.loads((tmp_path / "earn_watch.json").read_text())
    assert n == 2 and [x["t"] for x in j["items"]] == ["AAPL", "SAP.DE"]
    a = j["items"][0]
    assert a["cik"] == 320193 and a["ts"].startswith("2026-10-29T20:30:00") and a["w"] is True
    assert j["items"][1]["ts"] is None and j["items"][1]["cik"] == earnfast.ciks()["SAP"]


def test_ergebnis_text():
    m = earnfast.result_text("AAPL", "Apple", {"eps_s": 0.12, "rev_s": 0.02, "guide": {"d": 1}, "view": {"lbl": "eher positiv"}})
    assert m["title"] == "📊 Apple: eher positiv"
    assert "Gewinn +12,0 % vs. Erwartung" in m["body"] and "Ausblick angehoben" in m["body"] and "61 % der Fälle" in m["body"]


def test_sec_push_ohne_secrets_merkt_nichts_falsches(tmp_path, monkeypatch):
    monkeypatch.delenv("PUSH_SUBS", raising=False)
    assert earnfast.sec_pushes("aapl, msft", [], tmp_path) == ["AAPL", "MSFT"]
    assert earnfast.sec_pushes("", [], tmp_path) == []


def test_gelernte_meldezeit(monkeypatch, tmp_path):
    class R:
        def json(self):
            return {"filings": {"recent": {
                "form": ["4", "8-K", "8-K", "10-Q", "8-K", "8-K", "8-K"],
                "items": ["", "2.02,9.01", "5.02", "", "2.02,9.01", "2.02", "2.02,9.01"],
                "acceptanceDateTime": ["2026-10-20T10:00:00.000Z", "2026-07-30T20:31:10.000Z", "2026-06-01T12:00:00.000Z", "",
                                       "2026-05-01T20:30:40.000Z", "2026-01-29T21:32:00.000Z", "2025-10-30T20:33:00.000Z"]}}}
    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: R())
    monkeypatch.setattr(earnfast, "nasdaq_day", lambda d: {"AAPL": "after"})
    assert earnfast.typical_time(320193) == "16:32"            # New York, Median der letzten 4 Meldungen
    ev = [{"kind": "earnings", "ticker": "AAPL", "name": "Apple", "date": "2026-10-29"}]
    nexts = {"AAPL": {"date": "2026-10-29", "ts": "2026-10-29T16:00:00-04:00"}}
    earnfast.watch_file(ev, nexts, tmp_path, pd.Timestamp("2026-10-29"))
    a = json.loads((tmp_path / "earn_watch.json").read_text())["items"][0]
    assert a["exact"] is True and a["ts"].startswith("2026-10-29T20:32:00")
    assert a["ok2"] is True and a["from"].startswith("2026-10-29T19:32:00") and a["to"].startswith("2026-10-29T23:32:00")


def test_archiv(tmp_path):
    rec = {"BE": {"last": {"date": "2026-10-22", "eps_s": 0.38, "reva": -0.245, "guide": {"d": 1}, "rx": {"d1": -0.112}}}}
    assert earnfast.archive(rec, tmp_path) == 1
    a = json.loads((tmp_path / "earn_archive.json").read_text())["BE|2026-10-22"]
    assert a == {"s": 0.38, "ra": -0.245, "g": 1, "r1": -0.112}


def test_nasdaq_widerspruch(monkeypatch, tmp_path):
    monkeypatch.setattr(earnfast, "_times", lambda tk, out, today: {"AAPL": "16:32"})
    monkeypatch.setattr(earnfast, "nasdaq_day", lambda d: {"AAPL": "pre"})
    ev = [{"kind": "earnings", "ticker": "AAPL", "name": "Apple", "date": "2026-10-29"}]
    earnfast.watch_file(ev, {}, tmp_path, pd.Timestamp("2026-10-29"))
    a = json.loads((tmp_path / "earn_watch.json").read_text())["items"][0]
    assert "exact" not in a and "abweichend" in a["check"]
