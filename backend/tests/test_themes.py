"""Themen-Körbe ohne ETF (Neoclouds, Quantencomputer …): Index aus den Hauptwerten, Einbau in den Markt-Überblick."""
import numpy as np
import pandas as pd

from backend.analysis import THEME_ETF, basket_frame, market_context, theme_tickers

IDX = pd.bdate_range("2025-01-01", periods=420)


def _df(seed: int, start: int = 0, drift: float = .001) -> pd.DataFrame:
    r = np.random.default_rng(seed).normal(drift, .02, len(IDX))
    s = pd.Series(100 * np.cumprod(1 + r), index=IDX)
    return pd.DataFrame({"Close": s.iloc[start:]})


def test_basket_equal_weight_and_late_listing():
    h = {"A": _df(1), "B": _df(2), "C": _df(3), "D": _df(4, start=250)}
    b = basket_frame(h, ["A", "B", "C", "D", "FEHLT"])
    assert b is not None and len(b) >= len(IDX) - 2
    r = b["Close"].pct_change().dropna()
    exp = pd.DataFrame({k: h[k]["Close"] for k in "ABCD"}).pct_change().mean(axis=1).reindex(r.index)
    assert np.allclose(r.to_numpy(), exp.to_numpy(), atol=1e-9)        # Tagesrendite = Mittel der vorhandenen Werte


def test_basket_needs_three_members_and_drops_bad_ticks():
    h = {"A": _df(1), "B": _df(2)}
    assert basket_frame(h, ["A", "B", "X"]) is None
    c = _df(3); c.iloc[100, 0] *= 5                                   # Datenfehler: +400 % an einem Tag
    h["C"] = c
    b = basket_frame(h, ["A", "B", "C"])
    assert b is not None and b["Close"].pct_change().abs().max() < .3


def test_theme_tickers_cover_baskets_not_keys():
    tk = theme_tickers()
    assert not any(t.startswith("*") for t in tk)
    assert {"CRWV", "NBIS", "IONQ"} <= tk and "CIBR" in tk
    assert any(k.startswith("*") and "Neocloud" in v[0] for k, v in THEME_ETF.items())


def test_market_context_lists_basket_themes():
    neo = THEME_ETF["*NEO"][1]
    h = {t: _df(i + 10) for i, t in enumerate(neo)}
    h["^GSPC"] = _df(99, drift=.0005)
    out = market_context(h)
    th = {x["k"]: x for x in out.get("themes", [])}
    assert "*NEO" in th and th["*NEO"].get("bk") == 1 and th["*NEO"]["m1"] is not None
