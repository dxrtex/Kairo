"""KAIRO: Treffer → Seitwärtsphase (5 Kerzen ≤ 1,5 ATR) → Kauf zur nächsten Eröffnung in der Spanne → Stop / EMA-Ausstieg."""
from pathlib import Path

import numpy as np
import pandas as pd

from paper import kairo, run


def market(after):
    days = pd.bdate_range("2025-01-01", periods=300)
    c = np.r_[np.linspace(120, 100, 280), after]
    c = c[:300]
    d = pd.DataFrame({"Open": c, "High": c + 0.4, "Low": c - 0.4, "Close": c, "Volume": 1e6}, index=days)
    uni = pd.DataFrame({"ticker": ["AAA", "SPY"], "currency": "USD", "region": "us"})
    return run.Market(uni, {"AAA": d, "SPY": d}, {"USD": pd.Series(1.0, index=days)}), days


def go(mk, days, st, sig, upto):
    for k in range(279, upto):
        kairo.day(st, mk, days[k], days[k - 1], sig, run.equity, run.close_pos, run.open_pos)


def test_base_entry_then_stop():
    flat = [100.0] * 8 + [100.2] + [95.0] * 11                 # Seitwärtsphase, dann Absturz unter den Stop
    mk, days = market(flat)
    st = run.load_state(Path("/nonexistent"), "KAIRO")
    sig = [{"t": "AAA", "k": "hit", "region": "us", "d": str(days[279].date())}]
    go(mk, days, st, sig, 300)
    tr = st["trades"]
    assert len(tr) == 1 and tr[0]["why"] in ("stop", "stop_gap")
    assert pd.Timestamp(tr[0]["entry_ts"]) > days[279 + 5]          # frühestens nach 5 Kerzen Basis
    assert tr[0]["pnl_eur"] < 0 and st["cash"] > 0


def test_asia_and_seen_ignored():
    mk, days = market([100.0] * 20)
    st = run.load_state(Path("/nonexistent"), "KAIROS")
    sig = [{"t": "AAA", "k": "hit", "region": "asia", "d": str(days[279].date())},
           {"t": "AAA", "k": "fast", "region": "us", "d": str(days[279].date())}]
    go(mk, days, st, sig, 290)
    assert not st["pending"] and not st["positions"] and not st["trades"]
    assert kairo.currency("SAP.DE") == "EUR" and kairo.currency("AAPL") == "USD" and kairo.currency("BP.L") == "GBp"
