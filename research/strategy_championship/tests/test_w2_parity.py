"""W2-Audit – Parität: gemeinsame Simulation (backend/mrsim.py) gegen research/reversal/mrconfirm.portfolio und gegen die
Live-Signalerkennung (backend/mrshadow.signal_today) auf identischen synthetischen Kursen."""
import numpy as np
import pandas as pd

from backend import mrshadow, mrsim as S
from research.reversal import mrconfirm as MC


def _market(n_t=25, n=420, seed=11):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2024-01-01", periods=n)
    out = {}
    for k in range(n_t):
        lc = np.log(50) + np.cumsum(rng.normal(0.0008, 0.018, n))
        c = np.exp(lc)
        o = np.r_[c[0], c[:-1]] * np.exp(rng.normal(0, 0.006, n))
        h, lo = np.maximum(o, c) * (1 + abs(rng.normal(0, 0.006, n))), np.minimum(o, c) * (1 - abs(rng.normal(0, 0.006, n)))
        out[f"T{k}"] = pd.DataFrame({"Open": o, "High": h, "Low": lo, "Close": c, "Volume": 2e6}, index=idx)
    return out


def _prepare(model="opt"):
    mk = _market()
    ind = {t: S.indicators(df, "USD") for t, df in mk.items()}
    px = {t: S.make_px(x) for t, x in ind.items()}
    sig = [s for t, x in ind.items() for s in S.signal_rows(t, x, start=x.index[230], end=x.index[-15])]
    return mk, ind, px, sig


def test_signals_identical_to_live_scanner():
    mk, ind, px, sig = _prepare()
    for t in list(mk)[:8]:
        df = mk[t]
        for j in range(240, 400, 7):
            live = mrshadow.signal_today(df.iloc[:j + 1], "A5")
            res = bool(ind[t]["sig"].iat[j])
            assert (live is not None) == res, (t, j)
            if live:
                assert abs(live["lim"] - ind[t]["lim"].iat[j]) < 1e-4          # live auf 4 Stellen gerundet


def test_depot_parity_with_mrconfirm_portfolio():
    mk, ind, px, sig = _prepare()
    # gleiche Teilmenge: Trades ohne Zeitausstieg (mrconfirm gibt Plätze nach Zeitausstieg schon zur Eröffnung frei – Audit-Fund F5)
    rows, keep = [], []
    for s in sig:
        P = px[s["t"]]
        i = P.at(s["d"])
        r = S.trade_of(P, i, "W2", s["lim"], 0.0, S.COSTS["null"], "opt")
        if r["res"] == "kein_kauf" or (r["res"] == "closed" and r["why"] == "sma5"):
            keep.append(s)
            rows.append({"t": s["t"], "sig": s["d"], "buy_d": P.idx[i + 1], "rk": s["rsi2"], "fill": r["res"] == "closed",
                         "e": r.get("e", np.nan), "x": r.get("x", np.nan),
                         "sell_d": pd.Timestamp(r["exit"]) if r["res"] == "closed" else pd.NaT})
    T = pd.DataFrame(rows)
    closes = pd.DataFrame({t: x["c"] for t, x in ind.items()})
    cal = closes.index[closes.index >= closes.index[231]]
    a = MC.portfolio(T, closes.loc[cal], 0.0)
    b = S.simulate(keep, px, "W2", "opt", S.COSTS["null"], cash0=MC.CAP0, slots=MC.SLOTS, integer=False, calendar=cal)
    tr = {(x["t"], x["buy"]) for x in b["trades"]}
    exp = {(r.t, str(r.buy_d.date())) for r in T.itertuples() if r.fill}
    assert tr <= exp and len(tr) > 20
    rel = (b["equity"].iloc[-1] / a.iloc[-1]) - 1
    assert abs(rel) < 0.02, rel                                   # gleiche Entscheidungen; Rest: Kassen-Rundung beim Nachkauf


def test_conservative_fill_never_better_than_optimistic():
    mk, ind, px, sig = _prepare()
    res = {m: S.simulate(sig, px, "W2", m, S.COSTS["null"], cash0=10000) for m in S.FILLS}
    assert res["opt"]["counts"]["gefuellt"] >= res["kons"]["counts"]["gefuellt"] >= res["streng"]["counts"]["gefuellt"]
    assert res["opt"]["counts"]["orders"] > 0
