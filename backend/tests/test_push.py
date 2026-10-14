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
