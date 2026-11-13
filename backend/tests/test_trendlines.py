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


def test_chart_alarm_level_and_message():
    a = {"i": "x1", "t": "ABC", "n": "Abc", "k": "tl", "p": 10.0, "d1": "2026-11-02", "p2": 11.0, "d2": "2026-11-09", "dir": "up", "at": "2026-11-09"}
    assert abs(push.alert_level(a, "2026-11-16") - 12.0) < 1e-9          # 5 Handelstage je 1,0 → eine Woche später 12
    df = pd.DataFrame({"High": [11.0, 12.5], "Low": [10.0, 11.5], "Close": [10.5, 12.2]}, index=["2026-11-13", "2026-11-16"])
    sent = {}
    m = push.messages({"a": [a]}, {"ABC": df}, "2026-11-16", sent)
    assert len(m) == 1 and "kreuzt" in m[0]["title"] and "sec=chart&t=ABC" in m[0]["url"]
    assert push.messages({"a": [a]}, {"ABC": df}, "2026-11-16", sent) == []   # nur einmal
    h = {**a, "i": "x2", "k": "hl", "p": 13.0}
    assert push.messages({"a": [h]}, {"ABC": df}, "2026-11-16", {}) == []     # Hoch 12,5 erreicht 13 nicht
