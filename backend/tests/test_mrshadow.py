"""Schattentests A5/ETF: Signal wie in der Meisterschaft, Ausstieg 5-Tage-Linie bzw. Tag 10, nur künftige Signale, Einfrieren."""
import numpy as np
import pandas as pd

from backend import mrshadow as M


def _df(tail, n=230, start="2025-01-01"):
    c = list(np.linspace(80, 120, n)) + list(tail)                # Aufwärtstrend, dann das Muster
    d = pd.DataFrame({"Close": c}, index=pd.bdate_range(start, periods=len(c)))
    d["Open"], d["High"], d["Low"], d["Volume"] = d["Close"], d["Close"] * 1.01, d["Close"] * 0.99, 1e6
    return d


def test_a5_signal_needs_three_down_closes_trend_and_liquidity():
    df = _df([119, 118, 117])
    s = M.signal_today(df, "A5")
    assert s and s["d"] == str(df.index[-1].date()) and s["rsi2"] < 30
    assert M.signal_today(_df([119, 120, 117]), "A5") is None                       # keine 3 Verlusttage
    low = _df([119, 118, 117]); low["Volume"] = 10
    assert M.signal_today(low, "A5") is None                                         # zu wenig Umsatz
    fall = _df([60, 59, 58])                                                         # unter der 200-Tage-Linie
    assert M.signal_today(fall, "A5") is None


def test_replay_exit_sma5_next_open_and_time_exit():
    df = _df([119, 118, 117, 116.5, 121, 122])
    d = str(df.index[-6 + 2].date())                                                 # Signal am 3. Verlusttag
    r = M.replay(df, d)
    assert r["res"] == "closed" and r["why"] == "sma5" and r["e"] == 116.5 and r["x"] == 122 and r["gross"] > 0
    assert r["net_stress"] < r["net_normal"] < r["gross"]
    flat = _df([119, 118, 117] + [116 - 0.1 * k for k in range(12)])
    r = M.replay(flat, str(flat.index[-13].date()))
    assert r["res"] == "closed" and r["why"] == "zeit" and r["days"] == 10
    assert M.replay(df, str(df.index[-1].date()))["res"] == "signal"


def test_step_only_new_signals_and_freeze():
    df = _df([119, 118, 117])
    today = str(df.index[-1].date())
    rows = [{"ticker": "AAA", "region": "us"}, {"ticker": "BBB", "region": "asia"}]
    book = M.step({}, rows, {"AAA": df, "BBB": df}, {"XLK": df}, today)
    assert book["start"] == today and set(book["items"]) == {f"A5|AAA|{today}", f"ETF|XLK|{today}"}   # Asien nicht
    later = _df([119, 118, 117, 116.5, 121, 122])
    M.step(book, rows, {"AAA": later}, {}, "2099-01-01", record=False)
    it = book["items"][f"A5|AAA|{today}"]
    assert it["res"] == "closed"
    frozen = dict(it)
    M.step(book, rows, {"AAA": _df([119, 118, 117, 100, 90, 80])}, {}, "2099-01-02", record=False)
    assert book["items"][f"A5|AAA|{today}"] == frozen
    s = M.summary(book)
    assert s["A5"]["signals"] == 1 and s["A5"]["closed"] == 1 and s["A5"]["gross"] > 0


def test_old_signals_before_start_ignored_and_depot_slots():
    df = _df([119, 118, 117])
    book = {"start": "2099-01-01", "items": {}}
    M.step(book, [{"ticker": "AAA", "region": "us"}], {"AAA": df}, {}, "2099-01-01")
    assert book["items"] == {}
    xs = [{"t": f"T{i}", "d": "2026-01-02", "rsi2": float(i), "res": "closed", "exit": "2026-01-09"} for i in range(8)]
    sel = M.depot(xs, 5)
    assert [x["t"] for x in sel] == ["T0", "T1", "T2", "T3", "T4"]
