"""Mitteilungen nur bei wichtigen Ereignissen – und jede nur einmal."""

import pandas as pd

from backend.push import messages


def _df(lows, highs, closes, start="2026-10-05"):
    idx = [str(d.date()) for d in pd.bdate_range(start, periods=len(lows))]
    return pd.DataFrame({"Low": lows, "High": highs, "Close": closes}, index=idx)


def test_stop_exit_and_dedup():
    dev = {"p": [{"i": "a1", "t": "AXON", "n": "Axon", "cur": "USD", "d": "2026-10-06", "sl": 395.0, "ko": 360.0, "x": "2026-10-09"}]}
    prices = {"AXON": _df([380, 400, 396, 394, 398], [410, 412, 405, 404, 402], [405, 404, 400, 399, 400])}
    sent = {}
    m = messages(dev, prices, "2026-10-09", sent)
    titles = [x["title"] for x in m]
    assert any("Stop erreicht" in t for t in titles)          # Tief 394 nach dem Kauftag (380 am Vortag zählt nicht)
    assert any("Verkaufstag" in t for t in titles)
    assert not any("K.-o." in t for t in titles)               # 10 % Abstand: kein Alarm
    assert messages(dev, prices, "2026-10-09", sent) == []     # kein zweites Mal


def test_nothing_when_calm_and_ko_near_depot():
    dev = {"p": [{"i": "b", "t": "SAP.DE", "d": "2026-10-05", "sl": 150.0, "x": "2026-11-01"}], "d": [{"t": "NVDA", "ko": 172.0}]}
    prices = {"SAP.DE": _df([160, 161], [170, 171], [165, 166]), "NVDA": _df([175, 176], [182, 181], [180, 179])}
    m = messages(dev, prices, "2026-10-06", {})
    assert len(m) == 1 and "K.-o. nah" in m[0]["title"]


def test_synced_overrides_from_kursdienst(monkeypatch):
    import requests
    from backend.push import synced

    class R:
        ok, status_code = True, 200
        def json(self):
            return {"p": [{"i": "x", "t": "RHM.DE", "sl": 900}], "d": []}
    seen = {}
    monkeypatch.setattr(requests, "get", lambda url, params=None, timeout=None: seen.update(url=url, params=params) or R())
    dev = {"s": {}, "p": [], "d": [{"t": "OLD"}], "sync": "https://k.workers.dev/", "key": "k" * 20}
    out = synced(dev)
    assert out["p"][0]["t"] == "RHM.DE" and out["d"] == [] and seen["url"] == "https://k.workers.dev/trades" and seen["params"]["key"] == "k" * 20
    assert synced({"p": [1]}) == {"p": [1]}


def test_ema_exit_only_from_day_10_and_closed_days():
    closes = [100 + i for i in range(30)] + [110]                 # Trend, dann ein Schluss unter der EMA 20
    idx = [str(d.date()) for d in pd.bdate_range("2026-08-03", periods=len(closes))]
    df = pd.DataFrame({"Low": closes, "High": closes, "Close": closes}, index=idx)
    p = {"i": "e1", "t": "X", "n": "X", "d": idx[-12], "sl": 50.0, "x": "2026-12-31", "e": 1}
    today = str((pd.Timestamp(idx[-1]) + pd.offsets.BDay(1)).date())
    m = messages({"p": [p]}, {"X": df}, today, {})
    assert any("EMA 20" in x["title"] for x in m)
    assert not messages({"p": [{**p, "d": idx[-5]}]}, {"X": df}, today, {})          # erst Tag 5 – zu früh
    assert not messages({"p": [{**p, "e": None}]}, {"X": df}, today, {})              # kein 4H-Trade – alte Regel
    assert not messages({"p": [p]}, {"X": df}, idx[-1], {})                           # laufender Tag (110) zählt noch nicht


def test_watchlist_only_on_upgrade(monkeypatch):
    from backend import push, state
    store = {}
    monkeypatch.setattr(state, "load", lambda n, d: store.get(n, d))
    monkeypatch.setattr(state, "save", lambda n, o: store.__setitem__(n, o))
    rows = [{"ticker": "1211.HK", "name": "BYD", "in_watchlist": True, "fast_hit": True, "missing": ["MBI: grünes X auf roter Spitze"]},
            {"ticker": "TUI1.DE", "name": "TUI", "in_watchlist": True}, {"ticker": "ZZZ", "name": "Z", "fast_hit": True}]
    m = push.watch_messages("2026-10-14", rows)
    assert len(m) == 1 and "BYD" in m[0]["title"] and "MBI" in m[0]["body"]
    assert push.watch_messages("2026-10-15", rows) == []                            # gleicher Stand: nichts
    rows[0].update(passed=True)
    m = push.watch_messages("2026-10-16", rows)
    assert len(m) == 1 and "Treffer" in m[0]["title"]
    rows[0].update(passed=False, fast_hit=False)
    push.watch_messages("2026-10-17", rows)
    rows[0].update(fast_hit=True)
    assert push.watch_messages("2026-10-18", rows) == []                            # kurz weg und wieder da: kein zweites Mal


def test_h4_messages_only_for_real_entries():
    from backend.push import h4_messages
    base = {"t": "A", "n": "A", "d": "2026-10-10", "st": "go", "cur": "USD", "base": {"sl": 9.0, "lo": 9.5, "hi": 10.5}, "trig": {"c": 10.0}}
    items = [base, {**base, "t": "B", "n": "B", "grp": "10"}, {**base, "t": "C", "n": "C", "grp": "9"}, {**base, "t": "D", "n": "D", "grp": "10s", "soft": True}]
    m = h4_messages(items, "2026-10-14", {}, None)
    assert [x["title"].split(": ")[1].split(" –")[0] for x in m] == ["A", "D"]


def test_watchlist_many_become_one_message(monkeypatch):
    from backend import push, state
    store = {}
    monkeypatch.setattr(state, "load", lambda n, d: store.get(n, d))
    monkeypatch.setattr(state, "save", lambda n, o: store.__setitem__(n, o))
    rows = [{"ticker": f"T{i}", "name": f"Firma {i}", "in_watchlist": True, "fast_hit": True, "missing": ["MBI: x"]} for i in range(7)]
    m = push.watch_messages("2026-10-14", rows)
    assert len(m) == 1 and "7 Aktien" in m[0]["title"] and "Firma 0" in m[0]["body"] and "_n" not in m[0]


def test_insider_messages_first_run_silent_then_new(monkeypatch):
    from backend import push, state
    store = {}
    monkeypatch.setattr(state, "load", lambda n, d=None: store.get(n, d))
    monkeypatch.setattr(state, "save", lambda n, v: store.__setitem__(n, v))
    today = "2026-10-25"
    old = {"t": "PLTR", "n": "Palantir", "who": "A", "role": "CEO", "kind": "buy", "d": "2026-10-20", "val": 500_000, "opp": True}
    assert push.insider_messages(today, {"watch": [old]}) == []                    # erste Prüfung: nur merken
    new = [dict(old, who="B", d="2026-10-24"), dict(old, who="C", d="2026-10-24", val=20_000, opp=False),
           {"t": "AIR.PA", "n": "Airbus", "who": "Kitcher J.", "kind": "meld", "d": "2026-10-23", "src": "AFM"}]
    m = push.insider_messages(today, {"watch": [old] + new, "signal": {}})
    titles = [x["title"] for x in m]
    assert len(m) == 2 and any("Palantir" in t for t in titles) and any("Airbus" in t for t in titles)


def test_ko_untertags_beruehrt():
    """Review K7: Tagestief unter der K.-o.-Schwelle, Schluss wieder darüber → Turbo vermutlich ausgeknockt."""
    dev = {"d": [{"t": "NVDA", "ko": 172.0}], "p": []}
    prices = {"NVDA": _df([175, 170], [182, 181], [180, 179])}
    m = messages(dev, prices, "2026-10-06", {})
    assert len(m) == 1 and "K.-o. vermutlich erreicht" in m[0]["title"] and "Tagestief" in m[0]["body"]
    short = {"d": [{"t": "NVDA", "ko": 180.5, "dir": "short"}], "p": []}         # Tageshoch 181 ≥ 180,5
    assert "vermutlich" in messages(short, prices, "2026-10-06", {})[0]["title"]
