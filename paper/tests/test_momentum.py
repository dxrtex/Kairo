"""MOM5: Rangliste 6-1/Vol, Kauf zur Eröffnung am ersten Handelstag des Monats, Verkauf beim Monatswechsel."""
from pathlib import Path

import numpy as np
import pandas as pd

from paper import momentum, run


def mk_market():
    days = pd.bdate_range("2023-06-01", "2025-03-31")
    rng = np.random.default_rng(1)
    d, tick = {}, []
    for k in range(7):
        drift = 0.0005 * (k + 1)                       # T6 stärkster Trend
        c = 50 * np.exp(np.cumsum(drift + rng.normal(0, 0.01, len(days))))
        d[f"T{k}"] = pd.DataFrame({"Open": c, "High": c * 1.01, "Low": c * 0.99, "Close": c, "Volume": 1e6}, index=days)
        tick.append(f"T{k}")
    d["SPY"] = d["T0"]
    uni = pd.DataFrame({"ticker": tick + ["SPY"], "currency": "USD", "region": "us"})
    m = run.Market(uni, d, {"USD": pd.Series(1.0, index=days)})
    return m, days, tick


def test_rebalance_monthly_top5():
    m, days, tick = mk_market()
    st = run.load_state(Path("/nonexistent"), "MOM5")
    feb = days[days.to_period("M") == pd.Period("2025-02")]
    momentum.day(st, m, feb[0], days[days < feb[0]][-1], tick, run.equity, run.close_pos)
    held = {p["t"] for p in st["positions"]}
    assert len(held) == 5 and "T6" in held and "T0" not in held
    assert all(p["entry"] == m.daily[p["t"]]["Open"][feb[0]] for p in st["positions"])   # Eröffnung, nicht Schluss
    momentum.day(st, m, feb[1], feb[0], tick, run.equity, run.close_pos)                 # gleicher Monat: nichts tun
    assert len(st["positions"]) == 5 and not st["trades"]
    m.daily["T6"].loc[feb[2]:, ["Open", "High", "Low", "Close"]] *= 0.5
    mar = days[days.to_period("M") == pd.Period("2025-03")]
    momentum.day(st, m, mar[0], days[days < mar[0]][-1], tick, run.equity, run.close_pos)
    assert "T6" not in {p["t"] for p in st["positions"]} and any(t["t"] == "T6" and t["why"] == "monatswechsel" for t in st["trades"])
    assert st["cash"] >= 0 and st["equity"][-1]["eur"] > 0
