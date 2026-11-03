"""Insider-Verlauf für den Scanner-Filter: Käufe über Abende sammeln, Dubletten einmal, älter als 90 Tage raus."""
from backend import insider


def test_accumulate_dedupe_and_age():
    hist = [{"t": "AAA", "who": "X", "d": "2026-09-01", "kind": "buy", "val": 1e5},
            {"t": "OLD", "who": "Y", "d": "2026-06-01", "kind": "buy", "val": 1e5}]
    new = [{"t": "AAA", "who": "X", "d": "2026-09-01", "kind": "buy", "val": 1e5},     # doppelt
           {"t": "BBB", "who": "Z", "d": "2026-11-02", "kind": "buy", "val": 5e5},
           {"t": "CCC", "who": "Q", "d": "2026-11-02", "kind": "sell", "val": 9e5}]   # Verkauf zählt nicht
    out = insider.accumulate(hist, new, days=90, today="2026-11-03")
    assert sorted(x["t"] for x in out) == ["AAA", "BBB"]


def test_signal_from_history():
    rows = [{"t": "BBB", "who": "CEO A", "role": "CEO", "d": "2026-11-02", "kind": "buy", "val": 2e6, "opp": True, "own": 12},
            {"t": "BBB", "who": "Dir B", "role": "Director", "d": "2026-10-20", "kind": "buy", "val": 1e5}]
    sig = insider.signal(rows, days=36500)
    assert sig["BBB"]["buyers"] == 2 and sig["BBB"]["top"] and sig["BBB"]["score"] == 3
