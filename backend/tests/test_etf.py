"""ETF-Ampel: Fehlkurse raus; Extra-Geld jetzt (Rücksetzer/VIX) oder abwarten (höchstens 3 Monate)."""

import numpy as np
import pandas as pd

from backend.etf import clean, compute, level


def test_levels():
    assert level(13, False, 0.01, "2026-09-01", "2026-10-14")["lv"] == "wait"   # nahe Hoch, über EMA 100, ruhig → abwarten
    assert level(13, False, 0.01, "2026-06-01", "2026-10-14")["lv"] == "go"     # über 3 Monate gewartet → trotzdem rein
    assert level(13, True, 0.01)["lv"] == "go"                                   # unter der EMA 100
    assert level(13, False, 0.06)["lv"] == "go"                                  # ≥ 5 % unter dem Hoch
    assert level(26, False, 0.0)["lv"] == "go"                                   # VIX ≥ 25
    assert level(35, True, 0.2)["lv"] == "go2"                                   # Panik
    assert level(None, False, 0.0)["lv"] == "wait"


def test_clean_removes_spike_and_compute():
    idx = pd.bdate_range("2023-01-02", periods=400)
    c = pd.Series(np.linspace(100, 140, 400), index=idx)
    c.iloc[300] = 5.0                                   # Fehlkurs
    assert clean(c).min() > 90
    out = compute(pd.DataFrame({"Close": c}))
    assert out["lv"] in ("wait", "go") and out["dd"] < 0.01 and len(out["hist"]) > 300


def test_split_is_adjusted():
    idx = pd.bdate_range("2023-01-02", periods=400)
    c = pd.Series(np.linspace(200, 240, 400), index=idx)
    c.iloc[350:] = c.iloc[350:] / 20                      # Split 20:1, Historie nicht bereinigt
    out = compute(pd.DataFrame({"Close": c}))
    assert out["dd"] < 0.02 and out["ok"] and 11 < out["c"] < 13


def test_crosscheck_flags_bad_data():
    idx = pd.bdate_range("2023-01-02", periods=400)
    c = pd.Series(np.linspace(200, 240, 400), index=idx)
    ref = pd.Series(np.linspace(80, 96, 400), index=idx)
    assert compute(pd.DataFrame({"Close": c}), ref=ref)["ok"]
    bad = c.copy(); bad.iloc[-3:] = bad.iloc[-3:] * 0.9            # 10 % daneben, Vergleichs-ETF ruhig
    out = compute(pd.DataFrame({"Close": bad}), ref=ref)
    assert out["ref_ok"] is False and out["ok"] is False
