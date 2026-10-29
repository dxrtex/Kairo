"""4H-Top-Setup live (h4live.py) muss genau die Trades des 4H-Tests (h4study.py, HB|RMBS|zeit) liefern."""

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from backend import h4live as hl
from backend import h4study as hs


def _series(seed: int, drift: float = 0.0):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2025-01-02", "2026-03-31")
    idx = pd.DatetimeIndex([d + pd.Timedelta(hours=13.5 + k) for d in days for k in range(7)]).tz_localize("UTC")
    reg = np.repeat(rng.choice([0.35, 1.0, 1.6], size=len(days)), 7)
    c = 50 * np.exp(np.cumsum(rng.normal(0, 1, len(idx)) * np.where(rng.random(len(idx)) < .5, .004, .009) * reg
                                + drift * np.sin(np.arange(len(idx)) / 90)))   # Wellen: Trends, die unter die EMA fallen
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, .002, len(idx))))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, .002, len(idx))))
    hx = pd.DataFrame({"Open": o, "High": h, "Low": l, "Close": c}, index=idx)
    loc = hx.copy()
    loc.index = loc.index.tz_convert(None)
    g = loc.groupby(loc.index.normalize())
    daily = pd.DataFrame({"Open": g.Open.first(), "High": g.High.max(), "Low": g.Low.min(), "Close": g.Close.last()})
    return hx, daily


def test_same_trades_as_study(monkeypatch):
    monkeypatch.setitem(hl.QRULE, "calm", False)     # Gleichheit mit der Studie ohne Ruhe-Filter (der hat eigene Tests)
    trades = 0
    for seed in (3, 5, 8):
        hx, daily = _series(seed)
        b = hs.to4h(hx)
        for i in range(60, len(daily) - 45, 4):
            d = str(daily.index[i].date())
            px = {**hl._px(daily, i), "s": 0.95}
            v = hs.kairo_variants({"d": d, "px": px}, b).get("HB|RMBS|zeit")
            cut = daily.index[i + 40]
            r = hl.evaluate(daily[daily.index <= cut], d, hx[hx.index <= (cut + pd.Timedelta(hours=23)).tz_localize("UTC")],
                            now=(cut + pd.Timedelta(days=1)).tz_localize("UTC").to_pydatetime())
            lv = r.get("trade")                    # Gegenprobe „Tag 20“ (r20) = Trade des 4H-Tests
            lv = lv if lv and lv.get("r20") is not None else None
            assert (v is None) == (lv is None), (seed, d, v, r)
            if v:
                trades += 1
                assert v["ti"] == lv["ti"] and abs(v["r"] - lv["r20"]) < 2e-3, (seed, d, v, lv)
    assert trades > 0


def test_ema_exit_same_as_exit_study(monkeypatch):
    monkeypatch.setitem(hl.QRULE, "calm", False)
    """Neuer Ausstieg (EMA 20 ab Tag 10, max. Tag 40) = Regel „EMA20 ab T10·T40“ aus dem Ausstiegs-Test."""
    trades, ema_exits = 0, 0
    for seed, drift in ((3, 0), (5, 0), (7, .002)):
        hx, daily = _series(seed, drift)
        b = hs.to4h(hx)
        dc = b.groupby("day")["Close"].last()
        ema = b["day"].map(dc.ewm(span=20, adjust=False).mean()).to_numpy(float)
        lastbar = (b["day"] != b["day"].shift(-1)).to_numpy()
        for i in range(60, len(daily) - 70, 2):
            d = str(daily.index[i].date())
            px = {**hl._px(daily, i), "s": 0.95}
            v = hs.kairo_variants({"d": d, "px": px}, b).get("HB|RMBS|zeit")
            if not v:
                continue
            i0 = int(b.index.get_loc(pd.Timestamp(v["ti"])))
            x = hs._exit_sim(b, i0, v["sl"], {"T": 40, "ema": 20, "from": 10}, ema, lastbar)
            cut = daily.index[i + 65]
            r = hl.evaluate(daily[daily.index <= cut], d, hx[hx.index <= (cut + pd.Timedelta(hours=23)).tz_localize("UTC")],
                            now=(cut + pd.Timedelta(days=1)).tz_localize("UTC").to_pydatetime())
            if x is None or r["st"] not in ("stop", "zeit", "ema"):
                continue
            trades += 1
            ema_exits += r["st"] == "ema"
            assert abs(x["r"] - r["trade"]["r"]) < 2e-3, (seed, d, x, r["st"], r["trade"])
    assert trades > 0 and ema_exits > 0


def test_complete_only_drops_running_bars():
    idx = pd.DatetimeIndex([pd.Timestamp("2026-10-12") + pd.Timedelta(hours=13.5 + k) for k in range(7)]
                           + [pd.Timestamp("2026-10-13") + pd.Timedelta(hours=13.5 + k) for k in range(6)]).tz_localize("UTC")
    x = pd.DataFrame({"Open": 1.0, "High": 1.0, "Low": 1.0, "Close": 1.0}, index=idx)
    now = datetime(2026, 10, 13, 19, 0, tzinfo=timezone.utc)          # 13:30–17:30 fertig (+80 Min.), 18:30 läuft noch
    y = hl.complete_only(x, now)
    assert len(y) == 7 + 4                                             # heute nur die volle erste 4er-Gruppe


def test_base_waiting_and_failed():
    px = {"o": [1.0, 1.0], "h": [1.01, 1.01], "l": [.99, .99], "c": [1.0, 1.0], "atr": .02, "pl": [.97] * 10}
    assert hl.base_state(px)["st"] == "basis"
    px2 = {**px, "l": [.95, .99]}
    assert hl.base_state(px2)["st"] == "weg"


def test_ruhe_filter_am_basis_tag():
    """Mit calm=True zählt ein Basis-Tag nur, wenn er ruhig ist (live aus seit dem Depot-Test 29.10.2026, Mechanik bleibt geprüft)."""
    R = {**hl.QRULE, "calm": True}
    assert hl.QRULE["calm"] is False
    px = {"o": [1.0] * 12, "h": [1.01] * 12, "l": [0.99] * 12, "c": [1.0] * 12, "atr": 0.02, "pl": [0.98] * 10}
    assert hl.base_state({**px, "calm": [True] * 12}, R)["st"] == "base"
    unr = hl.base_state({**px, "o": px["o"][:6], "h": px["h"][:6], "l": px["l"][:6], "c": px["c"][:6], "calm": [False] * 6}, R)
    assert unr["st"] == "basis" and unr.get("unruhig")
    assert hl.base_state({**px, "calm": [False] * 12}, R)["st"] == "weg"
    later = hl.base_state({**px, "calm": [False] * 6 + [True] * 6}, R)
    assert later["st"] == "base" and later["s"] == 7          # erst der ruhige Basis-Tag (Tag 7) löst den Kauf aus
