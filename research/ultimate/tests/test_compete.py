"""Steuer, Umschalt-Regel und Mischung (Wettbewerb B) an einfachen Zahlen."""
import numpy as np
import pandas as pd
import pytest

from research.ultimate import compete as C


def test_steuer_toepfe_und_vortrag():
    idx = pd.bdate_range("2020-01-01", "2021-12-31")
    e = pd.Series(10000.0, index=idx)
    # 2020: Aktienverlust −1000, allgemeiner Gewinn +500 → keine Steuer, Aktien-Verlust wird vorgetragen
    # 2021: Aktiengewinn +2000 − 1000 Vortrag = 1000 → 263,75 € Steuer
    t = {2020: {"aktien": -1000.0, "allgemein": 500.0}, 2021: {"aktien": 2000.0, "allgemein": 0.0}}
    a = C.after_tax(e, t)
    assert a[a.index.year == 2020].iloc[-1] == pytest.approx(10000 * (1 - 0.26375 * 500 / 10000))
    assert a.iloc[-1] == pytest.approx(10000 * (1 - 0.26375 * 500 / 10000) * (1 - 0.26375 * 1000 / 10000))


def test_allgemeiner_verlust_gegen_aktiengewinn():
    idx = pd.bdate_range("2020-01-01", "2020-12-31")
    a = C.after_tax(pd.Series(10000.0, index=idx), {2020: {"aktien": 1000.0, "allgemein": -400.0}})
    assert a.iloc[-1] == pytest.approx(10000 * (1 - 0.26375 * 600 / 10000))


def test_sma_umschalten_und_mischung():
    idx = pd.bdate_range("2014-01-01", periods=500)
    s = pd.Series(np.r_[np.linspace(100, 150, 300), np.linspace(150, 90, 200)], index=idx)
    o, ex = C.sma_switch(s, "SPY", "BIL", idx[0], idx[-1])
    assert [x.ticker for x in o] == ["SPY", "BIL"] and ex["SPY"]
    a = pd.Series(np.linspace(100, 200, 300), index=idx[:300]); b = pd.Series(100.0, index=idx[:300])
    m = C.mix2(a, b, 0.5, 0.0)
    assert 140 < m.iloc[-1] < 150
    w = C.risk_scale(pd.Series(np.r_[np.linspace(100, 70, 200), np.linspace(70, 120, 300)], index=idx), pd.Series(0.0, index=idx), 0.10)
    assert w == 0.25                                  # 0,30 ergäbe durch Zinseszins knapp über 10 %
