"""4H-Top-Setup live (h4live.py) muss genau die Trades des 4H-Tests (h4study.py, HB|RMBS|zeit) liefern."""

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from backend import h4live as hl
from backend import h4study as hs


def _series(seed: int):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2025-01-02", "2026-03-31")
    idx = pd.DatetimeIndex([d + pd.Timedelta(hours=13.5 + k) for d in days for k in range(7)]).tz_localize("UTC")
    reg = np.repeat(rng.choice([0.35, 1.0, 1.6], size=len(days)), 7)
    c = 50 * np.exp(np.cumsum(rng.normal(0, 1, len(idx)) * np.where(rng.random(len(idx)) < .5, .004, .009) * reg))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, .002, len(idx))))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, .002, len(idx))))
    hx = pd.DataFrame({"Open": o, "High": h, "Low": l, "Close": c}, index=idx)
    loc = hx.copy()
    loc.index = loc.index.tz_convert(None)
    g = loc.groupby(loc.index.normalize())
    daily = pd.DataFrame({"Open": g.Open.first(), "High": g.High.max(), "Low": g.Low.min(), "Close": g.Close.last()})
    return hx, daily


def test_same_trades_as_study():
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
            lv = r.get("trade") if r["st"] in ("stop", "zeit") else None
            assert (v is None) == (lv is None), (seed, d, v, r)
            if v:
                trades += 1
                assert v["ti"] == lv["ti"] and abs(v["r"] - lv["r"]) < 2e-3, (seed, d, v, lv)
    assert trades > 0


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
