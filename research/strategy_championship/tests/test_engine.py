"""Synthetische Prüfungen der Ledger-Engine (B3). Jede Zahl ist von Hand nachgerechnet."""
import pandas as pd
import pytest

from research.strategy_championship.engine import Costs, Order, dividends, run

D = pd.bdate_range("2020-01-06", periods=10)
NOCOST = Costs(fee_eur=0.0, spread=0.0)


def bars(o, h, l, c, adj=None, idx=D):
    n = len(o)
    df = pd.DataFrame({"Open": o, "High": h, "Low": l, "Close": c}, index=idx[:n])
    df["AdjClose"] = adj if adj is not None else df["Close"]
    return df


def flat(p=10.0, n=10):
    return bars([p] * n, [p] * n, [p] * n, [p] * n)


def one(prices, orders, **kw):
    return run(prices, {t: "EUR" for t in prices}, {}, orders, **kw)


def test_constant_prices_no_cost_keeps_equity():
    r = one({"A": flat()}, [Order(D[0], "A", stop=9.0, risk_frac=0.01, max_days=3)], start_cash=1000, costs=NOCOST)
    assert r.equity.iloc[-1] == pytest.approx(1000)
    t = r.trades.iloc[0]
    assert t["entry_date"] == D[1] and t["why"] == "time" and t["exit_date"] == D[3]    # Kauf Folgetag, Tag 3 = D[3]
    assert r.checks["cash_consistent"] and r.checks["pnl_matches_equity"]


def test_entry_next_open_never_same_day():
    px = bars([10, 11, 12, 12, 12], [10, 11, 12, 12, 12], [10, 11, 12, 12, 12], [10, 11, 12, 12, 12])
    r = one({"A": px}, [Order(D[0], "A", stop=5.0, weight=0.5, max_days=2)], start_cash=1000, costs=NOCOST)
    assert r.trades.iloc[0]["entry_px"] == 11       # Eröffnung D[1], nicht Schluss D[0]


def test_gap_below_stop_sells_at_open():
    px = bars([10, 10, 8, 8], [10, 10.5, 8.2, 8], [10, 9.8, 7.5, 8], [10, 10, 8, 8])
    r = one({"A": px}, [Order(D[0], "A", stop=9.5, risk_frac=0.05)], start_cash=1000, costs=NOCOST)
    t = r.trades.iloc[0]
    assert t["why"] == "stop_gap" and t["exit_px"] == 8.0
    assert t["qty"] == 100                          # 50 € Risiko / (10 − 9,5)


def test_intraday_stop_fills_at_stop():
    px = bars([10, 10, 10, 10], [10, 10.5, 10.2, 10], [10, 9.8, 9.0, 10], [10, 10, 9.6, 10])
    r = one({"A": px}, [Order(D[0], "A", stop=9.5, risk_frac=0.05)], start_cash=1000, costs=NOCOST)
    t = r.trades.iloc[0]
    assert t["why"] == "stop" and t["exit_px"] == 9.5 and t["pnl_eur"] == pytest.approx(-50)


def test_stop_and_target_same_bar_counts_as_stop():
    px = bars([10, 10, 10, 10], [10, 10, 12, 10], [10, 10, 9, 10], [10, 10, 10, 10])
    r = one({"A": px}, [Order(D[0], "A", stop=9.5, target=11.5, risk_frac=0.05)], start_cash=1000, costs=NOCOST)
    assert r.trades.iloc[0]["why"] == "stop"


def test_open_below_stop_means_no_trade():
    px = bars([10, 9, 9, 9], [10, 9, 9, 9], [10, 9, 9, 9], [10, 9, 9, 9])
    r = one({"A": px}, [Order(D[0], "A", stop=9.5, risk_frac=0.05)], start_cash=1000, costs=NOCOST)
    assert r.trades.empty and r.equity.iloc[-1] == 1000


def test_costs_fee_and_spread():
    r = one({"A": flat()}, [Order(D[0], "A", stop=9.0, weight=0.5, max_days=2)], start_cash=1000,
            costs=Costs(fee_eur=1.0, spread=0.002))
    t = r.trades.iloc[0]
    assert t["entry_px"] == pytest.approx(10.01) and t["exit_px"] == pytest.approx(9.99)
    q = t["qty"]                                    # floor(500 / 10,01) = 49
    assert q == 49 and t["pnl_eur"] == pytest.approx(q * (9.99 - 10.01) - 2.0)
    assert r.equity.iloc[-1] == pytest.approx(1000 + t["pnl_eur"])


def test_dividend_from_adjclose_is_credited():
    c = [10.0] * 6
    adj = [9.8, 9.8, 9.8, 10.0, 10.0, 10.0]          # Ex-Tag D[3]: D = 10 × (1 − 0,98) = 0,20
    px = bars(c, c, c, c, adj=adj)
    assert dividends(px).iloc[3] == pytest.approx(0.2)
    r = one({"A": px}, [Order(D[0], "A", stop=5.0, weight=1.0, max_days=5)], start_cash=1000, costs=NOCOST)
    divs = r.ledger[r.ledger["kind"] == "DIV"]
    assert len(divs) == 1 and divs["cash_flow_eur"].iloc[0] == pytest.approx(100 * 0.2)
    assert r.equity.iloc[-1] == pytest.approx(1020) and r.checks["pnl_matches_equity"]


def test_fx_conversion_usd_position():
    fx = {"USD": pd.Series([1.25, 1.25, 1.0, 1.0, 1.0], index=D[:5])}       # 1 EUR = 1,25 USD → später 1,00
    px = flat(10.0, 5)
    r = run({"A": px}, {"A": "USD"}, fx, [Order(D[0], "A", stop=5.0, weight=0.5, max_days=3)], start_cash=1000, costs=NOCOST)
    t = r.trades.iloc[0]
    assert t["qty"] == 62                           # 500 € = 625 $ → 62 Stück à 10 $
    assert t["pnl_eur"] == pytest.approx(62 * 10 / 1.0 - 62 * 10 / 1.25)    # reiner Währungsgewinn


def test_pence_quoted_stock():
    fx = {"GBP": pd.Series([0.8] * 5, index=D[:5])}
    px = flat(500.0, 5)                             # 500 Pence = 5 GBP = 6,25 EUR
    r = run({"A": px}, {"A": "GBp"}, fx, [Order(D[0], "A", stop=400, weight=0.5, max_days=2)], start_cash=1000, costs=NOCOST)
    assert r.trades.iloc[0]["qty"] == 80            # 500 € / 6,25 €


def test_missing_bar_waits_and_data_end_forces_exit():
    idx = D.delete(1)                               # A handelt an D[1] nicht
    a = bars([10] * 5, [10] * 5, [10] * 5, [10] * 5, idx=idx)
    b = flat(20.0, 9)                               # B liefert den Kalender
    r = one({"A": a, "B": b}, [Order(D[0], "A", stop=5, weight=0.5)], start_cash=1000, costs=NOCOST)
    t = r.trades.iloc[0]
    assert t["entry_date"] == D[2]                  # erste Eröffnung nach der Entscheidung
    assert t["why"] == "data_end"                   # A endet vor dem Kalender (Delisting im Datensatz)


def test_max_open_and_priority():
    p = {k: flat() for k in "ABC"}
    o = [Order(D[0], "A", stop=9, weight=0.2, prio=1), Order(D[0], "B", stop=9, weight=0.2, prio=3),
         Order(D[0], "C", stop=9, weight=0.2, prio=2)]
    r = one(p, o, start_cash=1000, costs=NOCOST, max_open=2)
    assert set(r.trades["ticker"]) == {"B", "C"}


def test_signal_exit_next_open():
    px = bars([10, 10, 10, 11, 12, 12], [10] * 3 + [11, 12, 12], [10] * 3 + [11, 12, 12], [10, 10, 10, 11, 12, 12])
    r = one({"A": px}, [Order(D[0], "A", stop=5, weight=0.5)], start_cash=1000, costs=NOCOST, exit_signals={(D[2], "A")})
    t = r.trades.iloc[0]
    assert t["why"] == "signal" and t["exit_date"] == D[3] and t["exit_px"] == 11


def test_no_negative_cash_and_never_more_than_cash():
    p = {k: flat() for k in "AB"}
    o = [Order(D[0], "A", stop=9.99, risk_frac=0.5), Order(D[0], "B", stop=9.99, risk_frac=0.5)]
    r = one(p, o, start_cash=1000, costs=Costs(fee_eur=0.99, spread=0.0))
    assert r.checks["no_negative_cash"] and r.checks["cash_consistent"]


def test_entry_band_retries_and_group_fills_once():
    px = bars([10, 13, 11, 11, 11, 11], [10, 13, 11, 11, 11, 11], [10, 13, 11, 11, 11, 11], [10, 13, 11, 11, 11, 11])
    o = [Order(D[0], "A", stop=5, weight=0.5, max_days=2, entry_band=(10, 12), valid_days=3, group="g1"),
         Order(D[2], "A", stop=5, weight=0.5, max_days=2, entry_band=(10, 12), group="g1")]
    r = one({"A": px}, o, start_cash=1000, costs=NOCOST)
    assert len(r.trades) == 1 and r.trades.iloc[0]["entry_date"] == D[2]    # D[1] 13 außerhalb → D[2] 11 innerhalb
    assert r.skipped["band"] == 1 and r.skipped["group"] == 1


def test_risk_atr_rejects():
    o = [Order(D[0], "A", stop=9.9, weight=0.5, atr=1.0, risk_atr=(0.5, 3.0))]     # Risiko 0,1 ATR < 0,5
    r = one({"A": flat()}, o, start_cash=1000, costs=NOCOST)
    assert len(r.trades) == 0 and r.skipped["risk_atr"] == 1


def test_ema_exit_next_open():
    c = [10, 10, 10, 9, 8, 8, 8]
    px = bars(c, c, c, c)
    px["EMA"] = 9.5
    r = one({"A": px}, [Order(D[0], "A", stop=1, weight=0.5, exit_rule=("ema", 2))], start_cash=1000, costs=NOCOST)
    t = r.trades.iloc[0]
    assert t["why"] == "signal" and t["exit_date"] == D[4] and t["exit_px"] == 8   # Schluss D[3] < EMA → Eröffnung D[4]


def test_exit_when_mask_sells_next_open():
    px = bars([10, 10, 10, 11, 12, 12], [10, 10, 10, 11, 12, 12], [10, 10, 10, 11, 12, 12], [10, 10, 10, 11, 12, 12])
    r = run({"A": px}, {"A": "EUR"}, {}, [Order(D[0], "A", stop=5, weight=0.5)], start_cash=1000, costs=NOCOST,
            exit_when={"A": [D[3]]})
    t = r.trades.iloc[0]
    assert t["why"] == "signal" and t["exit_date"] == D[4] and t["exit_px"] == 12


def test_min_fill_skips_rest_position():
    p = {k: flat() for k in "AB"}
    o = [Order(D[0], "A", stop=9.9, risk_frac=0.01, prio=2), Order(D[0], "B", stop=9.9, risk_frac=0.01, prio=1)]
    # A: 1 % von 1000 = 10 € Risiko / 0,1 = 100 Stück = 1000 € → ganzes Cash; B bekäme 0 → kein Kauf
    r = one(p, o, start_cash=1000, costs=NOCOST, min_fill=0.5)
    assert list(r.trades["ticker"]) == ["A"]
    o2 = [Order(D[0], "A", stop=9.9, risk_frac=0.006, prio=2), Order(D[0], "B", stop=9.9, risk_frac=0.006, prio=1)]
    r2 = one(p, o2, start_cash=1000, costs=NOCOST, min_fill=0.5)   # A 600 €, B nur 40 von 60 Stück → 0,67 ≥ 0,5 → kauft
    assert set(r2.trades["ticker"]) == {"A", "B"}
    r3 = one(p, o2, start_cash=1000, costs=NOCOST, min_fill=0.7)
    assert list(r3.trades["ticker"]) == ["A"] and r3.skipped["small"] == 1


def test_touch_ema_target_sells_at_prior_ema():
    o = [10, 10, 10, 10.5, 11, 11]
    h = [10, 10, 10.2, 11.2, 11, 11]
    px = bars(o, h, [10, 9.9, 9.9, 10.4, 11, 11], [10, 10, 10.1, 11, 11, 11])
    px["EMA"] = 11.0
    r = one({"A": px}, [Order(D[0], "A", stop=9, weight=0.5, exit_rule=("touch_ema",))], start_cash=1000, costs=NOCOST)
    t = r.trades.iloc[0]
    assert t["why"] == "target" and t["exit_date"] == D[3] and t["exit_px"] == 11.0


def test_trailing_breakeven_then_prev_low():
    o = [10, 10, 11, 12.5, 12.6, 12.0]
    h = [10, 10.5, 12.2, 13.0, 12.8, 12.1]
    l = [10, 9.8, 10.9, 12.3, 12.2, 11.0]
    px = bars(o, h, l, [10, 10.4, 12.0, 12.8, 12.4, 11.5])
    r = one({"A": px}, [Order(D[0], "A", stop=8.5, weight=0.5, trail=("be_prevlow", 2.0))], start_cash=1000, costs=NOCOST)
    t = r.trades.iloc[0]
    # Kauf 10 (D1); D2 Hoch 12,2 ≥ 12 → Einstand; D3 Stop = Vortagestief 10,9; D4 Stop = Vortagestief 12,3, Tief 12,2 → Stop 12,3
    assert t["why"] == "stop" and t["exit_date"] == D[4] and t["exit_px"] == 12.3


def test_max_open_cap():
    p = {k: flat() for k in "ABC"}
    o = [Order(D[0], k, stop=9, weight=0.2, prio=3 - i, max_open_cap=2) for i, k in enumerate("ABC")]
    r = one(p, o, start_cash=1000, costs=NOCOST, max_open=5)
    assert set(r.trades["ticker"]) == {"A", "B"}


def test_stop_from_fill():
    px = bars([10, 12, 12, 11, 11], [10, 12, 12, 11, 11], [10, 12, 12, 10.4, 11], [10, 12, 12, 11, 11])
    r = one({"A": px}, [Order(D[0], "A", stop_from_fill=1.5, risk_frac=0.01)], start_cash=1000, costs=NOCOST)
    t = r.trades.iloc[0]
    assert t["stop"] == 10.5 and t["qty"] == 6 and t["why"] == "stop" and t["exit_px"] == 10.5   # 10 € Risiko / 1,5


def test_prime_plus_fee_free_from_250():
    # 30 Stück à 10 € = 300 € ≥ 250 € → keine Gebühr; 20 Stück = 200 € → 0,99 € je Seite
    c = Costs(fee_eur=0.99, spread=0.0, fee_free_from=250.0)
    for w, fee in ((0.3, 0.0), (0.2, 0.99)):
        r = one({"A": flat()}, [Order(D[0], "A", weight=w, max_days=3)], start_cash=1000.0, costs=c)
        assert r.trades["fees_eur"].iloc[0] == pytest.approx(2 * fee)
        assert r.equity.iloc[-1] == pytest.approx(1000.0 - 2 * fee)


def test_buy_stop_fills_at_trigger_or_higher_open():
    # D[1]: Hoch 10,4 < 10,5 → nicht ausgelöst; D[2]: Eröffnung 10,2, Hoch 10,8 → Kauf zum Stop-Kurs 10,5
    px = bars([10, 10, 10.2, 10.6, 10.6], [10, 10.4, 10.8, 10.7, 10.7], [10, 9.9, 10.1, 10.5, 10.5], [10, 10, 10.6, 10.6, 10.6])
    o = Order(D[0], "A", stop=9.5, risk_frac=0.01, max_days=2, entry_stop=10.5, entry_cap=11.0, valid_days=3)
    r = one({"A": px}, [o], start_cash=1000, costs=NOCOST)
    t = r.trades.iloc[0]
    assert t["entry_date"] == D[2] and t["entry_px"] == pytest.approx(10.5)
    # Eröffnung 10,7 über dem Stop-Kurs (unter der Grenze) → Kauf zur Eröffnung
    px2 = bars([10, 10.7, 10.7, 10.7], [10, 10.9, 10.8, 10.8], [10, 10.6, 10.6, 10.6], [10, 10.7, 10.7, 10.7])
    r2 = one({"A": px2}, [Order(D[0], "A", stop=9.5, risk_frac=0.01, max_days=2, entry_stop=10.5, entry_cap=11.0)],
             start_cash=1000, costs=NOCOST)
    assert r2.trades.iloc[0]["entry_px"] == pytest.approx(10.7)


def test_buy_stop_gap_over_cap_cancels_and_same_day_low_stops():
    px = bars([10, 11.5, 11.5], [10, 11.6, 11.6], [10, 11.4, 11.4], [10, 11.5, 11.5])
    r = one({"A": px}, [Order(D[0], "A", stop=9.5, risk_frac=0.01, max_days=2, entry_stop=10.5, entry_cap=11.0, valid_days=2)],
            start_cash=1000, costs=NOCOST)
    assert not len(r.trades) and r.skipped["gap_cap"] == 1
    # Auslösung und Tief unter dem Stop am selben Tag → vorsichtig ausgestoppt
    px2 = bars([10, 10.0, 10.0], [10, 10.6, 10.0], [10, 9.4, 10.0], [10, 9.6, 10.0])
    r2 = one({"A": px2}, [Order(D[0], "A", stop=9.5, risk_frac=0.01, max_days=5, entry_stop=10.5)], start_cash=1000, costs=NOCOST)
    t = r2.trades.iloc[0]
    assert t["entry_date"] == D[1] and t["why"] == "stop" and t["exit_px"] == pytest.approx(9.5)


def test_min_order_value_raises_or_skips():
    px = bars([10.0] * 5, [10.2] * 5, [9.9] * 5, [10.0] * 5)
    # Risiko 1 % von 1.000 € = 10 €, Stop 0,5 € unter Kauf → 20 Stück = 200 € < 250 € → 25 Stück (Risiko 12,50 € ≤ 2 × 10 €)
    o = Order(D[0], "A", stop=9.5, risk_frac=0.01, max_days=2, min_value_eur=250.0)
    r = one({"A": px}, [o], start_cash=1000, costs=NOCOST)
    assert r.trades.iloc[0]["qty"] == 25
    # Stop 0,2 € → 50 Stück = 500 € ≥ 250 € → unverändert
    r2 = one({"A": px}, [Order(D[0], "A", stop=9.8, risk_frac=0.01, max_days=2, min_value_eur=250.0)], start_cash=1000, costs=NOCOST)
    assert r2.trades.iloc[0]["qty"] == 50
    # Risiko nur 0,2 % = 2 € bei Stop 0,5 € → 4 Stück; 25 Stück wären 12,50 € > 2 × 2 € → auslassen
    r3 = one({"A": px}, [Order(D[0], "A", stop=9.5, risk_frac=0.002, max_days=2, min_value_eur=250.0)], start_cash=1000, costs=NOCOST)
    assert not len(r3.trades) and r3.skipped["fee_small"] == 1
