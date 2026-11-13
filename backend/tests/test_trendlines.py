import numpy as np
import pandas as pd

from backend import autota, push, state


def _df(c):
    c = np.asarray(c, dtype=float)
    return pd.DataFrame({"High": c * 1.01, "Low": c * 0.99, "Close": c})


def test_rising_support_and_break():
    # Zickzack nach oben: Tiefs steigen gleichmäßig → steigende Trendlinie; am Ende deutlicher Fall darunter
    x = np.arange(200)
    c = 100 + 0.2 * x + 4 * np.sin(x / 6)
    tl = autota.trendlines(_df(c))
    assert tl and tl["sup"] and tl["sup"]["touch"] >= 2 and tl["brk"] is None
    c2 = np.concatenate([c, [c[-1] * 0.9]])
    assert autota.trendlines(_df(c2))["brk"] == "down"


def test_too_short():
    assert autota.trendlines(_df(np.linspace(10, 20, 50))) is None


def test_push_once_per_direction(monkeypatch):
    store = {}
    monkeypatch.setattr(state, "load", lambda n, d: store.get(n, d))
    monkeypatch.setattr(state, "save", lambda n, o: store.__setitem__(n, o))
    rows = [{"ticker": "ABC", "name": "Abc AG", "in_watchlist": True, "tl": {"brk": "down", "sup": {"now": 10.5, "touch": 3}}},
            {"ticker": "XYZ", "name": "Xyz", "in_watchlist": False, "tl": {"brk": "up", "res": {"now": 5, "touch": 2}}}]
    m = push.trendline_messages("2026-11-13", rows)
    assert len(m) == 1 and "Abc AG" in m[0]["title"] and "10,50" in m[0]["body"] and "sec=chart&t=ABC" in m[0]["url"]
    assert push.trendline_messages("2026-11-14", rows) == []          # gleiche Richtung innerhalb 10 Tagen: nicht nochmal
    assert len(push.trendline_messages("2026-11-30", rows)) == 1      # nach 10 Tagen wieder möglich
