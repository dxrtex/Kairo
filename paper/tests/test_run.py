"""Ablauf-Test ohne Netz: wartendes S20-Setup → H4-Auslöser → Kauf → Break-even → Trailing → Verkauf; S19 mit CRV-Ablehnung."""
import numpy as np
import pandas as pd

from paper import core, run


def market():
    days = pd.bdate_range("2025-01-01", periods=300)
    c = np.linspace(50, 100, 300)
    d = pd.DataFrame({"Open": c, "High": c * 1.01, "Low": c * 0.99, "Close": c, "Volume": np.full(300, 1e6)}, index=days)
    uni = pd.DataFrame({"ticker": ["AAA", "SPY"], "currency": ["USD", "USD"], "region": ["us", "us"]})
    fx = {"USD": pd.Series(1.0, index=days)}
    mk = run.Market(uni, {"AAA": d, "SPY": d}, fx)
    D_prev, D = days[-2], days[-1]
    hrs = pd.date_range(D.normalize() + pd.Timedelta(hours=13, minutes=30), periods=7, freq="1h")
    old = pd.date_range(D_prev.normalize() + pd.Timedelta(hours=13, minutes=30), periods=7, freq="1h")
    o = [99.0] * 7 + [99.0, 101.0, 103.0, 104.0, 104.0, 103.0, 101.0]
    h = pd.DataFrame({"Open": o, "High": [x + 0.5 for x in o], "Low": [x - 0.5 for x in o], "Close": o,
                      "Volume": [100] * 7 + [500] * 7}, index=old.append(hrs))
    h.iloc[7:11, h.columns.get_loc("Close")] = [100.5, 102.5, 103.8, 104]
    mk.h4["AAA"] = core.to_h4(h)
    return mk, days, D_prev, D


def test_s20_flow():
    mk, days, D_prev, D = market()
    st = run.load_state(__import__("pathlib").Path("/nonexistent"), "S20")
    st["pending"] = [{"t": "AAA", "day": str(D_prev.date()), "expiry": str(D.date()), "atr": 1.0}]
    mk.h4["AAA"]["ema20"] = 95.0
    mk.h4["AAA"]["vma20"] = 50.0
    run.process_day(st, mk, D, D_prev, days, True)
    assert st["positions"] or st["trades"], st["events"]
    assert any("KAUF AAA" in e for e in st["events"])
    assert st["equity"][-1]["eur"] > 0


def test_s19_crv_reject():
    mk, days, D_prev, D = market()
    st = run.load_state(__import__("pathlib").Path("/nonexistent"), "S19")
    mk.h4["AAA"].iloc[0, mk.h4["AAA"].columns.get_loc("Close")] = 98.0       # rote Kerze vor dem Auslöser
    st["pending"] = [{"t": "AAA", "day": str(D_prev.date()), "expiry": str(D.date()), "panic": 90.0, "atr": 2.0, "z": -3}]
    run.process_day(st, mk, D, D_prev, days, True)
    assert not st["positions"] and any("CRV" in e for e in st["events"]), st["events"]
