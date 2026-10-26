"""Watchlist: Sterne aus der App (über den Kursdienst) vor data/watchlist.json."""
import json

from backend import run_scan


class _R:
    def __init__(self, j):
        self._j = j

    def json(self):
        return self._j


def _reset(monkeypatch, subs, reply):
    run_scan._WATCH = None
    if subs is None:
        monkeypatch.delenv("PUSH_SUBS", raising=False)
    else:
        monkeypatch.setenv("PUSH_SUBS", json.dumps(subs))
    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: _R(reply))


def test_remote_list_wins(monkeypatch):
    _reset(monkeypatch, [{"s": {}, "sync": "https://kd.example.workers.dev", "key": "x" * 32}],
           {"p": [], "d": [], "w": [{"t": "AAPL", "n": "Apple"}, {"t": "RHM.DE", "n": "Rheinmetall"}, {"t": "bad ticker!"}]})
    assert run_scan.load_watchlist() == {"AAPL": "Apple", "RHM.DE": "Rheinmetall"}


def test_fallback_to_file(monkeypatch):
    _reset(monkeypatch, [{"s": {}, "sync": "https://kd.example.workers.dev", "key": "x" * 32}], {"p": [], "d": []})
    w = run_scan.load_watchlist()
    assert len(w) > 20 and "AAPL" in w
    _reset(monkeypatch, None, {})
    assert "AAPL" in run_scan.load_watchlist()
    run_scan._WATCH = None
