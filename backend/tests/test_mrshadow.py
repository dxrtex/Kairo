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
    assert book["start"] == today and set(book["items"]) == {f"A5|AAA|{today}", f"W2|AAA|{today}", f"ETF|XLK|{today}"}   # Asien nicht
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


def test_w2_limit_fill_or_no_buy():
    df = _df([119, 118, 117, 116.5, 121, 122])
    d = str(df.index[-6 + 2].date())
    lim = 116.0                                                                      # Tief am Folgetag 116,5 × 0,99 = 115,3 ≤ 116
    r = M.replay(df, d, lim)
    assert r["res"] == "closed" and r["e"] == 116.0 and r["x"] == 122
    assert M.replay(df, d, 110.0)["res"] == "kein_kauf"                              # Limit nicht erreicht → kein Kauf
    s = M.signal_today(_df([119, 118, 117]), "A5")
    assert s["lim"] < s["close"]
    book = M.step({}, [{"ticker": "X", "region": "us"}], {"X": _df([119, 118, 117])}, None, s["d"])
    assert any(k.startswith("W2|X|") for k in book["items"]) and "W2" in M.summary(book)


def test_learn_finds_filter_candidate_and_lists_losers():
    items = []
    for k in range(40):
        bad = k % 2 == 0
        items.append({"rule": "W2", "t": f"T{k}", "res": "closed", "exit": f"2026-12-{k % 28 + 1:02d}",
                      "gross": (-0.02 if bad else 0.01) + 0.001 * (k % 5), "f": {"tief": bad, "extrem": k % 3 == 0}, "f2": {"luecke": False}})
    L = M.learn(items)
    row = {r["k"]: r for r in L["features"]}
    assert row["tief"]["status"] == "Filter-Kandidat" and row["tief"]["with"] < row["tief"]["without"]
    assert row["luecke"]["status"] == "zu wenig Fälle"                                  # keine Fälle mit Lücke
    assert L["losers"] and "Fall der 3 Tage größer als 2 ATR" in L["losers"][0]["f"]
    s = M.signal_today(_df([119, 118, 117]), "A5")
    assert set(s["f"]) >= {"extrem", "tief", "unruhig"}


def test_only_strongest_signals_per_day_are_stored():
    data = {f"X{k}": _df([119, 118, 117 - 0.1 * k]) for k in range(15)}               # 15 Signale am selben Tag
    rows = [{"ticker": t, "region": "us"} for t in data]
    today = str(next(iter(data.values())).index[-1].date())
    book = M.step({}, rows, data, None, today)
    a5 = [x for x in book["items"].values() if x["rule"] == "A5"]
    assert len(a5) == M.MAX_DAY and book["signals_today"] == 15
    kept = {x["t"] for x in a5}
    assert "X14" in kept and "X0" not in kept                                          # tiefster Fall = niedrigster RSI(2)


def test_event_depot_no_backfill_log_append_only_and_frozen():
    """W2-Audit: Depot über backend/mrsim – bestes Signal (nicht gefüllt) belegt seinen Platz; Log wächst nur, Abschlüsse bleiben."""
    a = _df([119, 118, 117, 117.5, 118, 118.5, 119, 125, 126, 127, 128])
    b = _df([119, 118, 116.5, 110, 112, 118, 125, 126, 127, 128, 129])
    a.iloc[-8, a.columns.get_loc("Low")] = 117.4                           # A: Limit am Folgetag nie erreicht
    d = str(a.index[-9].date())
    items = {}
    for t, df in (("A", a), ("B", b)):
        s = M.signal_today(df.iloc[:-8], "A5")
        assert s and s["d"] == d
        for rule in ("A5", "W2"):
            items[f"{rule}|{t}|{d}"] = {"rule": rule, "t": t, **s, "rsi2": 1.0 if t == "A" else 2.0, "adv": 1e9}
    book = {"start": d, "items": items}
    import backend.mrsim as S
    old = S.SLOTS
    try:
        M.step(book, [], {"A": a, "B": b}, None, str(a.index[-1].date()), record=False)
    finally:
        S.SLOTS = old
    dep = book["depot"]["W2|opt"]["counts"]
    assert dep["orders"] == 2 and dep["nicht_gefuellt"] == 1                 # 5 Plätze: beide Orders, A nicht gefüllt
    n_log, closed = len(book["log"]), dict(book["closed"])
    M.step(book, [], {"A": a, "B": b}, None, str(a.index[-1].date()), record=False)
    assert len(book["log"]) == n_log and book["closed"] == closed           # wiederholter Lauf: nichts doppelt, nichts geändert
    assert all(e["ev"] in ("order_geplant", "order_ausgefuehrt", "order_nicht_ausgefuehrt", "position_geschlossen", "kein_platz",
                           "order_zu_klein", "order_abgelaufen") for e in book["log"])
