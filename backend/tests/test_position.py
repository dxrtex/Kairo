import numpy as np
import pandas as pd
import pytest

from backend.position import engine, exit_signals, filters, position_sizing, scoring
from backend.position.config import Config, CFG


def _panel(n=420, k=8, seed=0, drift=None):
    idx = pd.bdate_range("2020-01-01", periods=n)
    r = np.random.default_rng(seed)
    drift = drift if drift is not None else np.linspace(0.0004, 0.002, k)
    rets = r.normal(drift, 0.01, (n, k))
    C = pd.DataFrame(50 * np.exp(np.cumsum(rets, axis=0)), index=idx, columns=[f"S{i}" for i in range(k)])
    O = C.shift(1).fillna(C) * (1 + r.normal(0, 0.002, C.shape))
    H = np.maximum(O, C) * 1.005
    L = np.minimum(O, C) * 0.995
    V = pd.DataFrame(1e6, index=idx, columns=C.columns)
    return O, H, L, C, V


def _market(**kw):
    O, H, L, C, V = _panel(**kw)
    ix = pd.Series(100 * np.exp(np.cumsum(np.full(len(C), 0.0005))), index=C.index)
    secs = {t: f"Sek{i % 4}" for i, t in enumerate(C.columns)}
    return engine.Market(O, H, L, C, V, ix, mcap=pd.Series(5e9, index=C.columns), sectors=secs)


# ---------- Momentum (Clenow) ----------
def test_clenow_perfect_exponential():
    idx = pd.bdate_range("2021-01-01", periods=120)
    C = pd.DataFrame({"A": 100 * np.exp(0.001 * np.arange(120))}, index=idx)
    v = scoring.clenow(C, 90).iloc[-1, 0]
    assert v == pytest.approx(np.expm1(0.252), rel=1e-9)       # R² = 1


def test_clenow_matches_polyfit_with_noise_and_nan_window():
    r = np.random.default_rng(3)
    idx = pd.bdate_range("2021-01-01", periods=150)
    C = pd.DataFrame({"A": 50 * np.exp(np.cumsum(r.normal(0.001, 0.02, 150)))}, index=idx)
    y = np.log(C["A"].to_numpy()[-90:])
    b, a = np.polyfit(np.arange(90), y, 1)
    r2 = np.corrcoef(np.arange(90), y)[0, 1] ** 2
    assert scoring.clenow(C, 90).iloc[-1, 0] == pytest.approx(np.expm1(b * 252) * r2, rel=1e-6)
    C.iloc[-5, 0] = np.nan                                        # Lücke im Fenster → kein Wert
    assert np.isnan(scoring.clenow(C, 90).iloc[-1, 0])


def test_mom_6_1():
    idx = pd.bdate_range("2021-01-01", periods=130)
    C = pd.DataFrame({"A": np.arange(1, 131, dtype=float)}, index=idx)
    assert scoring.mom_6_1(C).iloc[-1, 0] == pytest.approx(C["A"].iloc[-22] / C["A"].iloc[-127] - 1)


# ---------- Perzentile & Scores ----------
def test_percentile_rank():
    s = pd.Series([1.0, 2.0, 3.0, np.nan], index=list("abcd"))
    assert scoring.pct(s).tolist()[:3] == [0.0, 50.0, 100.0] and np.isnan(scoring.pct(s)["d"])
    assert scoring.pct(s, higher_better=False).tolist()[:3] == [100.0, 50.0, 0.0]
    assert scoring.pct(pd.Series([7.0], index=["x"]))["x"] == 50.0
    inf = scoring.pct(pd.Series([1.0, np.inf, 0.5]), higher_better=False)
    assert inf.iloc[1] == 0.0                                     # EBITDA ≤ 0 → schlechtester Rang


def test_missing_fundamentals_neutral_50():
    mom = pd.Series({"A": 0.9, "B": 0.5, "C": 0.1})
    sc = scoring.score_day(["A", "B", "C"], mom, None)
    assert (sc["qual"] == 50).all() and (sc["val"] == 50).all()
    assert list(sc.index) == ["A", "B", "C"]
    assert sc.loc["A", "total"] == pytest.approx(0.5 * 100 + 0.3 * 50 + 0.2 * 50)


def test_quality_and_value_direction():
    mom = pd.Series(0.5, index=list("ABC"))
    f = pd.DataFrame({"roe": [0.30, 0.10, np.nan], "nde": [0.5, 3.0, np.nan], "peg": [1.0, -2.0, np.nan], "fpe_rel": [0.8, 1.4, np.nan]}, index=list("ABC"))
    sc = scoring.score_day(list("ABC"), mom, f)
    assert sc.loc["A", "qual"] > sc.loc["B", "qual"] and sc.loc["C", "qual"] == 50
    assert sc.loc["A", "val"] > sc.loc["B", "val"] and sc.loc["C", "val"] == 50


def test_select_sector_cap_and_top_quantile():
    sc = pd.DataFrame({"total": range(10, 0, -1)}, index=[f"T{i}" for i in range(10)])
    sectors = {f"T{i}": ("Tech" if i < 6 else f"S{i}") for i in range(10)}
    sel = scoring.select(sc, sectors, Config(top_n=5, sector_cap=3))
    assert sel == ["T0", "T1", "T2", "T6", "T7"]
    assert scoring.top_quantile(sc, 0.25) == {"T0", "T1", "T2"}


# ---------- Positionsgröße ----------
def test_atr_sizing():
    assert position_sizing.shares(100_000, 2.0, 50.0) == 50          # 100 € Risiko / 2 ATR
    assert position_sizing.shares(100_000, 0.1, 50.0) == 160         # Deckel 8 % = 8.000 € / 50
    assert position_sizing.shares(100_000, float("nan"), 50.0) == 0
    assert position_sizing.shares(100_000, 0.0, 50.0) == 0


def test_atr_true_range():
    idx = pd.bdate_range("2021-01-01", periods=3)
    H = pd.DataFrame({"A": [10, 12, 11]}, index=idx, dtype=float)
    L = pd.DataFrame({"A": [9, 10, 8]}, index=idx, dtype=float)
    C = pd.DataFrame({"A": [9.5, 11, 9]}, index=idx, dtype=float)
    a = position_sizing.atr(H, L, C, 2)
    assert a.iloc[-1, 0] == pytest.approx((max(2, 12 - 9.5, 10 - 9.5) + max(3, 11 - 11, abs(8 - 11))) / 2)


# ---------- Filter ----------
def test_filters_trend_gap_liquidity():
    O, H, L, C, V = _panel(n=300, k=3, drift=np.array([0.002, 0.002, -0.002]))
    C.iloc[-30, 1] = C.iloc[-31, 1] * 0.8                             # −20 % Tagesverlust → Gap-Filter
    ind = filters.indicators(C, V, None)
    p = filters.pool(C, ind, pd.Series({"S0": 5e9, "S1": 5e9, "S2": 5e9}))
    assert bool(p.iloc[-1]["S0"]) and not p.iloc[-1]["S1"] and not p.iloc[-1]["S2"]
    p2 = filters.pool(C, ind, pd.Series({"S0": 1e9, "S1": 5e9, "S2": 5e9}))
    assert not p2.iloc[-1]["S0"]                                     # Börsenwert < 2 Mrd.


def test_dedupe_keeps_more_liquid_listing():
    names = {"SAP": "SAP SE ADR", "SAP.DE": "SAP SE", "MSFT": "Microsoft Corporation"}
    out = filters.dedupe(["SAP.DE", "SAP", "MSFT"], names, {"SAP": 5e7, "SAP.DE": 2e8, "MSFT": 1e10})
    assert out == ["SAP.DE", "MSFT"]


# ---------- Exits ----------
def test_exit_reasons():
    assert exit_signals.exit_reasons(96, 97, 100, 2, False, True) == ["trend"]
    assert exit_signals.exit_reasons(93, 90, 100, 2, False, True) == ["stop"]          # 93 < 100 − 6
    assert exit_signals.exit_reasons(99, 90, 100, 2, True, False) == ["rank"]
    assert exit_signals.exit_reasons(99, 90, 100, 2, False, False) == []


# ---------- Engine: Ausführung, Steuer, Delisting, kein Blick in die Zukunft ----------
def test_engine_executes_at_next_open_and_no_nan():
    m = _market()
    res = engine.run(m, m.C.index[260], tax=True)
    assert res["trades"] or res["pos"]
    assert res["equity"].notna().all()
    for tk, p in res["pos"].items():
        assert p.entry_px == pytest.approx(float(m.O.at[p.entry_date, tk]))   # Kauf zum Open, nicht zum Schluss


def test_engine_no_lookahead():
    m = _market(seed=5)
    cut = m.C.index[340]
    a = engine.run(m, m.C.index[260], end=cut, tax=False)
    m2 = _market(seed=5)
    for df in (m2.O, m2.H, m2.L, m2.C):
        df.loc[df.index > cut] *= 3                                  # Zukunft verändern
    b = engine.run(m2, m2.C.index[260], end=cut, tax=False)
    assert a["trades"] == b["trades"] and a["equity"].equals(b["equity"])


def test_engine_delisting_forced_sale():
    m = _market(seed=7, k=4, drift=np.array([0.003, 0.0025, 0.002, 0.0015]))
    res0 = engine.run(m, m.C.index[260], end=m.C.index[300], tax=False)
    held = list(res0["pos"])
    assert held
    gone = held[0]
    cut = m.C.index[310]
    for df in (m.O, m.H, m.L, m.C, m.V):
        df.loc[df.index > cut, gone] = np.nan                        # Kursreihe endet
    res = engine.run(m, m.C.index[260], tax=False)
    tr = [x for x in res["trades"] if x["t"] == gone and x["why"] == "delisted"]
    assert tr and tr[-1]["out"] == cut.strftime("%Y-%m-%d") and gone not in res["pos"]
    assert res["equity"].notna().all()


def test_tax_and_loss_pot():
    cfg = Config(cost=0.0)
    res = {"cash": 0.0, "pot": 300.0, "last_close": {"A": 120.0}, "pos": {"A": engine.Pos(10, pd.Timestamp("2021-01-04"), 100.0, 1000.0, 120.0)}}
    # Gewinn 200, Verlusttopf 300 → keine Steuer, Topf sinkt auf 100
    assert engine.liquidate_after_tax(res, cfg) == pytest.approx(1200.0)
    res["pot"] = 50.0                                                # 150 steuerpflichtig
    assert engine.liquidate_after_tax(res, cfg) == pytest.approx(1200.0 - 150 * 0.26375)


def test_engine_tax_reduces_capital_vs_untaxed():
    m = _market(seed=11)
    a = engine.run(m, m.C.index[260], tax=False)
    b = engine.run(m, m.C.index[260], tax=True)
    assert b["taxes"] >= 0 and (b["taxes"] == 0 or b["equity"].iloc[-1] <= a["equity"].iloc[-1] + 1e-6)


def test_bear_market_blocks_buys():
    m = _market(seed=2)
    m.index_close = pd.Series(np.linspace(200, 100, len(m.C)), index=m.C.index)   # dauerhaft unter SMA 200
    res = engine.run(m, m.C.index[260], tax=False)
    assert not res["trades"] and not res["pos"]


def test_backtest_report_runs_with_synthetic_data(monkeypatch):
    from backend.position import backtest
    m = _market(seed=13)
    monkeypatch.setattr(backtest, "_yf", lambda t, start="2010-01-01": pd.DataFrame({"Close": m.index_close}))
    rep = backtest.report(m, {"missing": {"peg"}, "notes": [], "n_prices": 8}, m.C.index[260].strftime("%Y-%m-%d"), CFG)
    for k in ("end_pre_tax", "end_after_tax", "cagr_pre", "mdd", "sharpe", "trades", "costs", "taxes", "bench_cagr"):
        assert k in rep and rep[k] == rep[k]
    assert rep["end_after_tax"] <= rep["end_pre_tax"] + 1e-6 or rep["taxes"] == 0
    backtest.print_report(rep, "Test")


def test_live_scan_build_outputs_model_and_signals():
    from backend.position import scan
    O, H, L, C, V = _panel(n=480, k=10, seed=21)
    data = {t: pd.DataFrame({"Open": O[t], "High": H[t], "Low": L[t], "Close": C[t], "Volume": V[t]}) for t in C.columns}
    meta = {t: {"name": f"Firma {t}", "currency": "USD", "market_cap_usd": 5e9, "sector": f"Sek{i % 4}",
                "earnings_date": (C.index[-1] + pd.Timedelta(days=2)).strftime("%Y-%m-%d") if i == 0 else None} for i, t in enumerate(C.columns)}
    ix = pd.DataFrame({"Close": 100 * np.exp(np.cumsum(np.full(len(C), 0.0005)))}, index=C.index)
    fund = {"S9": {"roe": 0.3, "mc": 1e10, "debt": 1e9, "cash": 2e9, "ev": 12, "peg": 1.1, "fpe": 20}}
    out = scan.build(data, meta, ix, {"USD": 1.0}, fund=fund)
    assert out["regime"]["on"] is True and out["rank"] and out["model"]["value"] > 0
    assert all(r["score"] is not None for r in out["rank"])
    assert out["coverage"]["roe"] == 0.1
    s0 = next((r for r in out["rank"] if r["t"] == "S0"), None)
    assert s0 is None or s0["earn"] is True
    for p in out["model"]["positions"]:
        assert p["stop"] is not None and p["since"] >= out["model"]["start"]
    assert out["checks"] == ["liq", "trend", "stab", "mom", "qual", "val", "sector", "earn"]
    for r in out["rank"]:
        assert len(r["chk"]) == 8 and r["nchk"] == sum(r["chk"])
    s0 = next((r for r in out["rank"] + out["watch"] if r["t"] == "S0"), None)
    assert s0 is None or s0["chk"][7] == 0                           # Quartalszahlen in 2 Tagen → Earnings-Häkchen fehlt
    for w in out["watch"]:
        assert w["nchk"] >= 6 and not w["top15"] and not w["held"] and len(w["miss"]) == 8 - w["nchk"]


def test_watchlist_checks_near_candidates():
    from backend.position import scan
    O, H, L, C, V = _panel(n=480, k=10, seed=21)
    V["S1"] = 1.0                                                     # S1 illiquide → Liquidität fehlt, Rest kann passen
    data = {t: pd.DataFrame({"Open": O[t], "High": H[t], "Low": L[t], "Close": C[t], "Volume": V[t]}) for t in C.columns}
    meta = {t: {"name": t, "currency": "USD", "market_cap_usd": 5e9, "sector": f"Sek{i}"} for i, t in enumerate(C.columns)}
    ix = pd.DataFrame({"Close": 100 * np.exp(np.cumsum(np.full(len(C), 0.0005)))}, index=C.index)
    out = scan.build(data, meta, ix, {"USD": 1.0}, fund={})
    every = {r["t"]: r for r in out["rank"] + out["watch"]}
    assert "S1" not in [r["t"] for r in out["rank"]]                  # nicht im Kaufpool
    if "S1" in every:
        assert every["S1"]["chk"][0] == 0 and "liq" in every["S1"]["miss"]


def test_vs_percentile_against_pool():
    from backend.position import scan
    d = np.array([1.0, 2.0, 3.0, 4.0])
    assert scan._vs(d, 5.0) == 100.0 and scan._vs(d, 0.0) == 0.0
    assert scan._vs(d, 0.0, higher_better=False) == 100.0 and scan._vs(d, float("nan")) is None


def test_baseline_old_strategy_runs_same_costs_and_tax():
    from backend.position import backtest
    m = _market(seed=13, k=30)
    m.V.loc[:, :] = 1e6
    start = m.C.index[300]
    r = backtest.run_baseline(m, start, CFG, tax=True, rule={"n": 5})
    r0 = backtest.run_baseline(m, start, CFG, tax=False, rule={"n": 5})
    assert len(r["pos"]) <= 5 and r["costs"] > 0
    assert r["equity"].iloc[-1] <= r0["equity"].iloc[-1] + 1e-6
    ins = [x for x in r["trades"] if x["why"] == "rank"]
    assert all(pd.Timestamp(x["out"]).month in (1, 4, 7, 10) for x in ins)


def test_pe_5y_avg_plausibility():
    from backend.position import scan
    f = {"pe": 20, "fa": {"y": ["2022", "2023", "2024", "2025"], "fye": "12-31", "eps": [5, 5, 5, 5]},
         "pxm": {"m0": "2021-01", "c": [100.0] * 60}}
    assert scan.pe_5y_avg(f) == pytest.approx(20.0)
    f["pe"] = 200                                                    # unplausibel → verworfen
    assert scan.pe_5y_avg(f) is None


def test_mixed_calendars_do_not_break_indicators():
    m = _market(seed=17)
    extra = pd.bdate_range(m.C.index[0], m.C.index[-1]).difference(m.C.index)
    hol = m.C.index[300]                                    # „fremder“ Handelstag: alle Kurse NaN (z. B. US-Feiertag)
    for df in (m.O, m.H, m.L, m.C, m.V):
        df.loc[hol] = np.nan
    P = engine.prepare(m)
    t = m.C.index[320]
    assert P["pool"].loc[t].any()                           # Pool 20 Tage nach dem Feiertag nicht leer
    assert P["mom"].loc[t].notna().all()


def test_rebalance_days_monthly_quarterly():
    idx = pd.bdate_range("2021-01-01", "2021-12-31")
    mo = engine.rebalance_days(idx, "monthly")
    assert len(mo) == 11 and pd.Timestamp("2021-01-29") in mo and pd.Timestamp("2021-03-31") in mo
    assert engine.rebalance_days(idx, "quarterly") == {pd.Timestamp(d) for d in ("2021-03-31", "2021-06-30", "2021-09-30")}
    assert all(t.weekday() == 4 for t in engine.rebalance_days(idx, "weekly"))


def test_engine_monthly_rebalance_buys_only_on_month_end_signal():
    from dataclasses import replace
    m = _market(seed=3)
    cfg = replace(CFG, rebalance="monthly", risk_per_atr=0.004, max_weight=0.10)
    res = engine.run(m, m.C.index[260], cfg=cfg, tax=False)
    reb = engine.rebalance_days(m.C.index, "monthly")
    nxt = {m.C.index[m.C.index.get_loc(t) + 1].strftime("%Y-%m-%d") for t in reb if m.C.index.get_loc(t) + 1 < len(m.C.index)}
    first = m.C.index[260].strftime("%Y-%m-%d")
    assert all(x["in"] in nxt for x in res["trades"])
    assert all(x["out"] in nxt for x in res["trades"] if x["why"] == "rank")
    assert all(p.entry_date.strftime("%Y-%m-%d") in nxt | {first} for p in res["pos"].values())


def test_baseline_regime_filter_modes():
    from backend.position import backtest
    m = _market(seed=13, k=30)
    n = len(m.C)
    m.index_close = pd.Series(np.r_[np.linspace(100, 150, n - 60), np.linspace(150, 60, 60)], index=m.C.index)
    start = m.C.index[300]
    none = backtest.run_baseline(m, start, CFG, tax=False, rule={"n": 5})
    daily = backtest.run_baseline(m, start, CFG, tax=False, rule={"n": 5, "regime": "daily"})
    assert any(x["why"] == "regime" for x in daily["trades"]) and not daily["pos"]
    assert not any(x["why"] == "regime" for x in none["trades"])
    buys = backtest.run_baseline(m, start, CFG, tax=False, rule={"n": 5, "regime": "buys"})
    assert not any(x["why"] == "regime" for x in buys["trades"])
