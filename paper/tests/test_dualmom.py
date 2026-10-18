"""DM: bester ETF nach 12-M.-Rendite, sonst SHY; Wechsel nur zum Monatsanfang zur Eröffnung."""
from pathlib import Path

import numpy as np
import pandas as pd

from paper import dualmom, run


def market(qqq_drift=0.001, all_down=False):
    days = pd.bdate_range("2023-01-02", "2025-03-31")
    d = {}
    for t, dr in {"SPY": 0.0004, "EFA": 0.0002, "QQQ": qqq_drift, "SHY": 0.0001, "BIL": 0.00015}.items():
        dr = -0.001 if all_down and t in ("SPY", "EFA", "QQQ") else dr
        c = 100 * np.exp(np.cumsum(np.full(len(days), dr)))
        d[t] = pd.DataFrame({"Open": c, "High": c, "Low": c, "Close": c, "Volume": 1e7}, index=days)
    uni = pd.DataFrame({"ticker": ["XXX"], "currency": "USD", "region": "us"})
    return run.Market(uni, d, {"USD": pd.Series(1.0, index=days)}), days


def test_picks_best_or_shy():
    m, days = market()
    assert dualmom.target(m, days[-1]) == "QQQ"
    m2, days2 = market(all_down=True)
    assert dualmom.target(m2, days2[-1]) == "SHY"


def test_monthly_switch_at_open():
    m, days = market()
    st = run.load_state(Path("/nonexistent"), "DM")
    feb = days[days.to_period("M") == pd.Period("2025-02")]
    dualmom.day(st, m, feb[0], days[days < feb[0]][-1], run.equity, run.close_pos)
    assert [p["t"] for p in st["positions"]] == ["QQQ"] and st["positions"][0]["entry"] == m.daily["QQQ"]["Open"][feb[0]]
    dualmom.day(st, m, feb[1], feb[0], run.equity, run.close_pos)
    assert len(st["positions"]) == 1 and not st["trades"]
