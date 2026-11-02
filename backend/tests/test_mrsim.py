"""W2-Audit: gemeinsame Ereignis-Simulation (backend/mrsim.py) – Ausführung, Reservierung, Kosten, Ausstieg."""
import numpy as np
import pandas as pd
import pytest

from backend import mrsim as S


def _ind(closes, opens=None, lows=None, highs=None, start="2025-01-01"):
    c = np.asarray(closes, float)
    o = np.asarray(opens if opens is not None else c, float)
    lo = np.asarray(lows if lows is not None else np.minimum(o, c) * 0.995, float)
    hi = np.asarray(highs if highs is not None else np.maximum(o, c) * 1.005, float)
    df = pd.DataFrame({"Open": o, "High": hi, "Low": lo, "Close": c, "Volume": 1e6}, index=pd.bdate_range(start, periods=len(c)))
    return S.indicators(df, "USD")


def _trend(tail, n=230):
    return list(np.linspace(80, 120, n)) + list(tail)


# ---------------------------------------------------------------- Signal
def test_signal_three_down_closes_trend_liquidity_and_fx():
    ind = _ind(_trend([119, 118, 117]))
    assert bool(ind["sig"].iat[-1]) and not bool(ind["sig"].iat[-2])
    assert ind["lim"].iat[-1] == pytest.approx(117 - 0.5 * ind["atr"].iat[-1])
    df = pd.DataFrame({"Open": _trend([119, 118, 117]), "Close": _trend([119, 118, 117])}, index=pd.bdate_range("2025-01-01", periods=233))
    df["High"], df["Low"], df["Volume"] = df["Close"] * 1.005, df["Close"] * 0.995, 1e6
    assert bool(S.indicators(df, "USD")["sig"].iat[-1])            # 117 Mio. $ Umsatz
    df["Volume"] = 3e5                                               # 35 Mio. SEK ≈ 3,3 Mio. $ < 5 Mio. $
    assert not bool(S.indicators(df, "SEK")["sig"].iat[-1]) and bool(S.indicators(df, "USD")["sig"].iat[-1])


# ---------------------------------------------------------------- Limit-Ausführung
@pytest.mark.parametrize("o,low,lim,model,exp", [
    (100, 99, 99.5, "opt", 99.5),           # berührt/unterschritten → Limit
    (100, 99.5, 99.5, "opt", 99.5),         # exakt berührt → opt füllt
    (100, 99.5, 99.5, "kons", None),        # exakt berührt → kons nicht (Brief nie am Limit)
    (100, 99.2, 99.5, "kons", 99.5),        # deutlich durch (99.5·(1−0.00075−0.001)=99.33) → kons füllt
    (100, 99.2, 99.5, "streng", None),      # streng braucht 99.5·(1−0.00075−0.005)=98.93
    (98, 97, 99.5, "opt", 98),              # Eröffnung unter Limit → Eröffnung
    (98, 97, 99.5, "kons", 98 * 1.00075),   # kons: Briefkurs zur Eröffnung
    (100, 100, 99.5, "opt", None),          # nicht erreicht
])
def test_fill_models(o, low, lim, model, exp):
    r = S.fill_limit(o, low, lim, 0.00075, model)
    assert (r is None and exp is None) or r == pytest.approx(exp)


def test_trade_exit_sma5_next_open_and_day10():
    ind = _ind(_trend([119, 118, 117, 116.5, 121, 122]))
    P = S.make_px(ind)
    i = len(ind) - 4                                                 # Signal am 3. Verlusttag (117)
    r = S.trade_of(P, i, "A5", None, 0.0, S.COSTS["null"])
    assert r["res"] == "closed" and r["why"] == "sma5" and r["e"] == 116.5 and r["x"] == 122
    flat = _ind(_trend([119, 118, 117] + [116 - 0.1 * k for k in range(12)]))
    r = S.trade_of(S.make_px(flat), len(flat) - 13, "A5", None, 0.0, S.COSTS["null"])
    assert r["why"] == "zeit" and r["days"] == 10


# ---------------------------------------------------------------- Depot: Reservierung, kein Nachrücken
def _px_set():
    idx = pd.bdate_range("2026-01-05", periods=8)
    def P(o, lo, c):
        n = len(idx)
        o, lo, c = (np.full(n, v, float) if np.isscalar(v) else np.asarray(v, float) for v in (o, lo, c))
        return S.Px(idx, o, np.maximum(o, c) * 1.01, lo, c, np.full(n, 1e9), np.ones(n), "EUR")
    # A: bestes Signal (RSI 1), Limit 90 wird nie erreicht; B: zweitbestes (RSI 2), Limit 90 wird erreicht
    return idx, {"A": P(100, 95, 100), "B": P(100, 85, 100)}


def test_unfilled_limit_keeps_slot_no_backfill():
    idx, px = _px_set()
    sig = [{"t": "A", "d": idx[0], "rsi2": 1.0, "lim": 90.0, "adv": 1e9}, {"t": "B", "d": idx[0], "rsi2": 2.0, "lim": 90.0, "adv": 1e9}]
    r = S.simulate(sig, px, "W2", "opt", S.COSTS["null"], cash0=1000, slots=1)
    assert r["counts"]["orders"] == 1 and r["counts"]["kein_platz"] == 1 and r["counts"]["nicht_gefuellt"] == 1
    assert r["counts"]["gefuellt"] == 0 and not r["trades"] and not r["open"]          # B rückt NICHT nach
    r2 = S.simulate(sig, px, "W2", "opt", S.COSTS["null"], cash0=1000, slots=2)
    assert r2["counts"]["gefuellt"] == 1 and "B" in r2["open"]


def test_integer_shares_fee_threshold_and_min_order():
    idx, px = _px_set()
    sig = [{"t": "B", "d": idx[0], "rsi2": 2.0, "lim": 90.0, "adv": 1e9}]
    r = S.simulate(sig, px, "W2", "opt", S.COSTS["basis"], cash0=500, slots=5)        # 100 € je Platz → 1 Stück à 90 €, 0,99 € Gebühr
    assert r["open"]["B"]["qty"] == 1 and r["counts"]["gebuehren"] == pytest.approx(0.99)
    r = S.simulate(sig, px, "W2", "opt", S.COSTS["basis"], cash0=500, slots=5, min_order=250)   # 2 Plätze à 250 € → gebührenfrei
    assert r["open"]["B"]["qty"] == 3 and r["counts"]["gebuehren"] == 0                     # 3 × 90 € ≥ 250 € → gebührenfrei
    r = S.simulate(sig, px, "W2", "opt", S.COSTS["basis"], cash0=50, slots=5)          # 10 € je Platz < 1 Stück
    assert r["counts"]["zu_teuer"] == 1


def test_exit_frees_slot_only_when_known():
    idx = pd.bdate_range("2026-01-05", periods=15)
    n = len(idx)
    c = np.full(n, 100.0); c[2] = 105                                # Schluss Tag 2 > SMA5 → Verkauf Tag 3 Eröffnung
    sma = np.full(n, 101.0)
    A = S.Px(idx, np.full(n, 100.0), np.full(n, 106.0), np.full(n, 99.0), c, sma, np.ones(n), "EUR")
    B = S.Px(idx, np.full(n, 100.0), np.full(n, 101.0), np.full(n, 99.0), np.full(n, 100.0), sma, np.ones(n), "EUR")
    sig = [{"t": "A", "d": idx[0], "rsi2": 1, "lim": None, "adv": 1e9}, {"t": "B", "d": idx[2], "rsi2": 1, "lim": None, "adv": 1e9}]
    r = S.simulate(sig, {"A": A, "B": B}, "A5", "opt", S.COSTS["null"], cash0=1000, slots=1)
    assert r["counts"]["gefuellt"] == 2                               # Platz von A ist am Abend von Tag 2 bekannt frei
    assert r["trades"][0]["t"] == "A" and r["trades"][0]["exit"] == str(idx[3].date())


def test_costs_reduce_return_and_currency():
    idx, px = _px_set()
    sig = [{"t": "B", "d": idx[0], "rsi2": 2.0, "lim": 90.0, "adv": 1e9}]
    a = S.simulate(sig, px, "A5", "opt", S.COSTS["null"], cash0=10000, slots=1)        # Marktorder zahlt den halben Spread
    b = S.simulate(sig, px, "A5", "opt", S.COSTS["stress"], cash0=10000, slots=1)
    assert b["equity"].iloc[-1] < a["equity"].iloc[-1]
