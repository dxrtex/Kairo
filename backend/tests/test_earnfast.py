import json

import pandas as pd

from backend import earnfast


def test_watch_file_cik_und_uhrzeit(tmp_path):
    ev = [{"kind": "earnings", "ticker": "AAPL", "name": "Apple", "date": "2026-10-29", "watch": True},
          {"kind": "earnings", "ticker": "SAP.DE", "name": "SAP", "date": "2026-10-30"},
          {"kind": "earnings", "ticker": "RHM.DE", "name": "Rheinmetall", "date": "2026-10-29"},      # keine SEC-Nummer
          {"kind": "earnings", "ticker": "MSFT", "name": "Microsoft", "date": "2026-11-20"}]         # zu weit weg
    nexts = {"AAPL": {"date": "2026-10-29", "ts": "2026-10-29T16:30:00-04:00"}}
    n = earnfast.watch_file(ev, nexts, tmp_path, pd.Timestamp("2026-10-29"))
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
