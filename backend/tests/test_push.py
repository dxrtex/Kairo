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
