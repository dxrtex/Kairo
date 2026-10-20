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


def test_kairoz_target_filter_and_goal_exit():
    """KAIROZ: nur mit attraktivem Kursziel; Verkauf bei 80 % des Wegs zum Ziel, nicht beim EMA-Ausstieg."""
    up = [100.0] * 8 + [100.2] + list(np.linspace(100.5, 125, 11))     # Seitwärtsphase, dann kräftiger Anstieg
    mk, days = market(up)
    d0 = str(days[279].date())
    st = run.load_state(Path("/nonexistent"), "KAIROZ")
    sig = [{"t": "AAA", "k": "hit", "region": "us", "d": d0, "tup": 0.25, "vol": 0.20, "na": 8}]   # Ziel +25 % = 1,25 × Schwankung
    go(mk, days, st, sig, 300)
    assert len(st["trades"]) == 1 and st["trades"][0]["why"] == "ziel" and st["trades"][0]["pnl_eur"] > 0
    st2 = run.load_state(Path("/nonexistent"), "KAIROZ")
    go(mk, days, st2, [{**sig[0], "tup": 0.10}], 300)                      # Ziel nur +10 % = 0,5 × Schwankung → kein Kauf
    assert not st2["trades"] and not st2["positions"]
    st3 = run.load_state(Path("/nonexistent"), "KAIROZ")
    go(mk, days, st3, [{**sig[0], "na": 1}], 300)                          # zu wenige Analysten
    assert not st3["trades"] and not st3["positions"]


def test_kairol_holds_through_ema_dip():
    """KAIROL: kein EMA-Ausstieg – erst das Sicherheitsnetz (−30 %) oder das Ziel beendet den Trade."""
    path = [100.0] * 8 + [100.2] + [99.5] * 11                            # leicht unter EMA 20, aber weit über −30 %
    mk, days = market(path)
    st = run.load_state(Path("/nonexistent"), "KAIROL")
    sig = [{"t": "AAA", "k": "hit", "region": "us", "d": str(days[279].date()), "vol": 0.3}]
    go(mk, days, st, sig, 300)
    assert len(st["positions"]) == 1 and not st["trades"]
    assert abs(st["positions"][0]["stop"] / st["positions"][0]["entry"] - 0.7) < 1e-9
