"""SP2F: gehebelter S&P-500-ETF nur über der 200-Tage-Linie, sonst Bargeld; Wechsel zur Eröffnung des Folgetags."""
from pathlib import Path

import numpy as np
import pandas as pd

from paper import run, sp2f


def market(up_days=260, down_days=40):
    days = pd.bdate_range("2024-01-01", periods=up_days + down_days)
    g = np.r_[100 * np.exp(np.cumsum(np.full(up_days, 0.001))), 0]
    g = np.r_[g[:up_days], g[up_days - 1] * np.exp(np.cumsum(np.full(down_days, -0.01)))]
    e = 50 * g / g[0]
    d = {"^GSPC": pd.DataFrame({"Open": g, "High": g, "Low": g, "Close": g, "Volume": 1e9}, index=days),
         sp2f.ETF: pd.DataFrame({"Open": e, "High": e, "Low": e, "Close": e, "Volume": 1e6}, index=days)}
    uni = pd.DataFrame({"ticker": [sp2f.ETF], "currency": "EUR", "region": "eu"})
    return run.Market(uni, d, {"USD": pd.Series(1.0, index=days)}), days


def test_buy_above_sell_below():
    m, days = market()
    st = run.load_state(Path("/nonexistent"), "SP2F")
    for i in range(sp2f.SMA, len(days)):
        sp2f.day(st, m, days[i], days[i - 1], run.equity, run.close_pos)
    assert st["trades"] and st["trades"][0]["why"] == "unter SMA200" and not st["positions"]
    first = st["trades"][0]
    assert first["entry"] == m.daily[sp2f.ETF]["Open"][days[sp2f.SMA]]      # Kauf zur Eröffnung am Tag nach dem Signal
    assert st["cash"] > 0 and st["on"] is False


def test_too_little_history_does_nothing():
    m, days = market(up_days=100, down_days=0)
    st = run.load_state(Path("/nonexistent"), "SP2F")
    sp2f.day(st, m, days[50], days[49], run.equity, run.close_pos)
    assert not st["positions"] and st.get("on") is None
