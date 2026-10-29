"""Varianten-Generatoren der Runde 1 an künstlichen Kursen (Treffer an Kerze 100, ATR = 1)."""
import numpy as np
import pandas as pd
import pytest

from research.ultimate import round1 as R


def setup_px(h, l, c, t="AAA"):
    idx = pd.bdate_range("2015-01-01", periods=len(c))
    a = pd.DataFrame({"Open": c, "High": h, "Low": l, "Close": c, "Volume": 1e6, "f": 1.0}, index=idx)
    R._G.clear()
    R._G.update(adj={t: a}, cur={t: "USD"}, spread={t: 0.001}, sec={}, calm={t: R.V.calm_arrays(a)})
    return idx


def base_path(n=130):
    c = np.full(n, 100.0); h = c + 0.3; l = c - 0.3
    l[95] = 99.0                                       # Tief vor dem Treffer (Invalidierung 99)
    return h, l, c


def test_e0_und_e2_basis_dann_buy_stop():
    h, l, c = base_path()
    idx = setup_px(h, l, c)
    e0 = R.orders_E0("AAA", 100, 1.0, "g", {"mom": 0.1}, 0.01)
    assert e0 and e0[0].decision_date == idx[105] and e0[0].entry_band == (pytest.approx(99.7), pytest.approx(100.3))
    e2 = R.orders_E2("AAA", 100, 1.0, "g", {"mom": 0.1}, 0.01)
    assert len(e2) == 10 and e2[0].entry_stop == pytest.approx(100.35) and e2[0].entry_cap == pytest.approx(100.8)
    assert e2[0].stop == pytest.approx(99.45) and e2[0].decision_date == idx[105]


def test_e2_stoppt_nach_ausbruch_oder_bruch():
    h, l, c = base_path()
    h[107] = 101.0                                     # Ausbruch an Kerze 107 → danach keine neuen Orders
    setup_px(h, l, c)
    assert len(R.orders_E2("AAA", 100, 1.0, "g", {"mom": 0.1}, 0.01)) == 2
    h, l, c = base_path(); l[106] = 99.5               # Basis gebrochen
    setup_px(h, l, c)
    assert len(R.orders_E2("AAA", 100, 1.0, "g", {"mom": 0.1}, 0.01)) == 1


def test_e1_umkehrkerze_ab_kerze_3():
    h, l, c = base_path()
    c[103] = 100.5; h[103] = 100.6; l[103] = 99.9      # Schluss oben, über Vortageshoch 100,3
    idx = setup_px(h, l, c)
    e1 = R.orders_E1("AAA", 100, 1.0, "g", {"mom": 0.1}, 0.01)
    assert e1[0].decision_date == idx[103]
    assert e1[0].stop == pytest.approx(99.7 - 0.25) and e1[0].entry_band[1] == pytest.approx(101.0)


def test_v1_streicht_nach_gescheiterter_umkehr_und_c1_kosten():
    h, l, c = base_path()
    idx = setup_px(h, l, c)
    n = len(c)
    ml, ms, r = np.zeros(n), np.zeros(n), np.full(n, 40.0)
    R._G["ind"] = {"AAA": (ml, ms, r)}
    assert R.orders_V1("AAA", 100, 1.0, "g", {"mom": 0.1}, 0.01)        # nie gescheitert
    ml[103] = -1.0; r[103] = 35.0                                         # MACD unter Signal UND RSI < Treffertag
    assert not R.orders_V1("AAA", 100, 1.0, "g", {"mom": 0.1}, 0.01)
    # C1: Stop-Abstand ≈ 0,85 % bei 100 → Kosten 2×(0,1 %+0,05 %+0,1 %) = 0,5 % → 0,59 R > 0,10 → raus
    assert not R.orders_C1("AAA", 100, 1.0, "g", {"mom": 0.1}, 0.01)
    c2 = c.copy(); h2, l2 = c2 + 3, c2 - 3; l2[95] = 90.0           # breite Basis: ATR 10, Stop-Abstand ≈ 8,5 %
    setup_px(h2, l2, c2)
    assert R.orders_C1("AAA", 100, 10.0, "g", {"mom": 0.1}, 0.01)


def test_n1_quartalszahlen_rueckgang():
    h, l, c = base_path()
    c[80:] = 100.0; c[:80] = 110.0                     # Sturz −9 % an Kerze 80 (im 60-Tage-Fenster)
    idx = setup_px(h, l, c)
    R._G["sec"] = {"AAA": np.array([np.datetime64(idx[79])])}   # Meldung am Vorabend → Reaktion am Folgetag
    assert R.news_drop("AAA", 100)
    assert not R.orders_N1("AAA", 100, 1.0, "g", {"mom": 0.1}, 0.01)
    R._G["sec"] = {"AAA": np.array([np.datetime64(idx[20])])}   # außerhalb des Fensters
    assert not R.news_drop("AAA", 100)


def test_holm_und_kennzahlen():
    h = R.holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert h["a"] == pytest.approx(0.03) and h["c"] == pytest.approx(0.06) and h["b"] == pytest.approx(0.06)
    e = pd.Series(np.linspace(100, 121, 253), index=pd.bdate_range("2020-01-01", periods=253))
    m = R.metrics(e)
    assert m["max_dd"] == 0 and 0.2 < m["cagr"] < 0.23
