"""Synthetische Prüfungen der Papier-Handelslogik (S19/S20)."""
import numpy as np
import pandas as pd

from paper import core


def h4(rows):
    idx = pd.date_range("2026-01-05 13:30", periods=len(rows), freq="4h")
    b = pd.DataFrame(rows, columns=["Open", "High", "Low", "Close", "Volume"], index=idx)
    b["day"] = b.index.normalize()
    b["ema20"] = core.ema(b["Close"], 20)
    b["vma20"] = b["Volume"].rolling(3).mean()
    return b


def test_s19_trigger_green_above_last_red_high():
    b = h4([[10, 10.5, 9.8, 10.2, 1], [10.2, 10.4, 9.5, 9.6, 1], [9.6, 10.6, 9.6, 10.5, 1], [10.5, 10.6, 10.3, 10.4, 1]])
    assert not core.s19_trigger(b, 1)               # rot
    assert core.s19_trigger(b, 2)                   # grün, Schluss 10,5 > Hoch der roten Kerze 10,4
    b2 = h4([[10, 10.5, 9.8, 10.2, 1], [10.2, 10.8, 9.5, 9.6, 1], [9.6, 10.6, 9.6, 10.5, 1]])
    assert not core.s19_trigger(b2, 2)              # grün, aber unter dem roten Hoch 10,8


def test_s20_trigger_volume_and_distance():
    b = h4([[10, 10, 10, 10, 100]] * 3 + [[10, 10.3, 10, 10.2, 200]])
    b["ema20"] = 10.0
    assert core.s20_trigger(b, 3)                   # 10,2 > 10,1 und Volumen 200 > Ø
    b.loc[b.index[3], "Close"] = 10.05
    assert not core.s20_trigger(b, 3)               # < 1 % über der EMA


def test_s19_exit_stop_then_target():
    p = {"sid": "S19", "entry": 10.0, "stop": 9.0}
    bar = pd.Series({"Open": 9.5, "High": 11.0, "Low": 8.9, "Close": 10.5})
    assert core.step_position(dict(p), bar, None, 10.8) == (9.0, "stop")      # Stop vor Ziel (vorsichtig)
    bar = pd.Series({"Open": 10.2, "High": 10.9, "Low": 10.1, "Close": 10.5})
    assert core.step_position(dict(p), bar, None, 10.8) == (10.8, "ziel_ema20")
    bar = pd.Series({"Open": 8.5, "High": 9.2, "Low": 8.4, "Close": 9.0})
    assert core.step_position(dict(p), bar, None, 10.8) == (8.5, "stop_gap")


def test_s20_breakeven_then_trailing_under_prev_h4_low():
    p = {"sid": "S20", "entry": 10.0, "stop": 8.5, "atr": 1.0, "be": False}
    assert core.step_position(p, pd.Series({"Open": 10, "High": 12.1, "Low": 9.9, "Close": 12}), None, None) is None
    assert p["be"] and p["stop"] == 10.0
    prev = pd.Series({"Open": 12, "High": 12.5, "Low": 11.6, "Close": 12.4})
    assert core.step_position(p, pd.Series({"Open": 12.4, "High": 12.6, "Low": 12.0, "Close": 12.5}), prev, None) is None
    assert p["stop"] == 11.6
    prev = pd.Series({"Open": 12.4, "High": 12.6, "Low": 12.0, "Close": 12.5})
    assert core.step_position(p, pd.Series({"Open": 12.3, "High": 12.4, "Low": 11.9, "Close": 12.0}), prev, None) == (12.0, "trail")


def test_size_risk_and_min_fill():
    assert core.size(5000, 5000, 0.01, 10.0, 9.0, 1.0, 0.0) == 50            # 50 € Risiko / 1 €
    assert core.size(5000, 200, 0.01, 10.0, 9.0, 1.0, 0.0) == 0              # nur 19 von 50 Stück → < 50 %
    assert core.size(5000, 300, 0.01, 10.0, 9.0, 1.0, 0.0) == 29             # 29 von 50 → ≥ 50 % → erlaubt
    assert core.size(5000, 5000, 0.01, 10.0, 9.0, 1.25, 0.0) == 62           # USD-Titel: 1 € = 1,25 $


def test_s19_signal_and_s20_setup():
    n = 260
    c = np.r_[np.linspace(50, 100, n - 4), [97, 94, 90, 85]]
    v = np.r_[np.full(n - 3, 1e6), [9e5, 8e5, 7e5]]
    df = pd.DataFrame({"Open": c, "High": c * 1.01, "Low": c * 0.99, "Close": c, "Volume": v},
                      index=pd.bdate_range("2025-01-01", periods=n))
    x = core.daily_frame(df)
    s = core.s19_signal(x, n - 1, sec_ret3=0.0)
    assert s is not None and s["z"] <= -2.5
    assert core.s19_signal(x, n - 1, sec_ret3=-0.5) is None                  # Branche fiel stärker
    assert core.s20_setup(x, n - 1) is None                                  # kein Aufwärtstrend am Ende


def test_s19_variants_volume_and_sigma():
    V = np.array([100, 90, 95, 80.0])                     # nur 2 von 3 Rückgängen
    assert not core.vol_exhausted(V, 3, "strict") and core.vol_exhausted(V, 3, "2of3")
    assert not core.vol_exhausted(np.array([80, 90, 95, 100.0]), 3, "2of3")
    assert core.S19_VARIANTS == {"S19": (2.5, "strict"), "S19B": (2.5, "2of3"), "S19C": (2.0, "2of3")}


def test_s19_variant_positions_hit_ema20_target():
    bar = pd.Series({"Open": 100.0, "High": 106.0, "Low": 99.0, "Close": 105.0})
    for sid in ("S19", "S19B", "S19C"):
        p = {"sid": sid, "entry": 100.0, "stop": 95.0, "stop0": 95.0}
        assert core.step_position(p, bar, None, 105.0) == (105.0, "ziel_ema20")


def test_prime_plus_fee():
    assert core.fee(250.0) == 0.0 and core.fee(249.99) == 0.99
