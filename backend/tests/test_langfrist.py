import numpy as np
import pandas as pd

from backend import langfrist as LF


def _df(drift, n=600, seed=0, vol=1e6):
    idx = pd.bdate_range("2024-01-01", periods=n)
    r = np.random.default_rng(seed)
    c = 50 * np.exp(np.cumsum(r.normal(drift, 0.01, n)))
    return pd.DataFrame({"Open": c, "High": c, "Low": c, "Close": c, "Volume": np.full(n, vol)}, index=idx)


def test_rebalance_dates_quarterly():
    idx = pd.bdate_range("2025-01-01", "2025-12-31")
    d = LF.rebalance_dates(idx, 3)
    assert [x.month for x in d] == [1, 4, 7, 10]
    assert all(x == idx[(idx.year == x.year) & (idx.month == x.month)][0] for x in d)


def test_build_picks_strongest_and_skips_non_us_and_illiquid():
    data = {f"S{i}": _df(0.0005 * i, seed=i) for i in range(30)}
    data["EU.DE"] = _df(0.01, seed=99)                 # stärkste, aber nicht USA
    data["TINY"] = _df(0.01, seed=98, vol=10)          # stärkste, aber illiquide
    meta = {t: {"name": t} for t in data}
    out = LF.build(data, meta, bench=_df(0.0003, seed=5), rule={"n": 5})
    held = [x["t"] for x in out["hold"]]
    assert len(held) == 5 and "EU.DE" not in held and "TINY" not in held
    assert set(held) <= {f"S{i}" for i in range(20, 30)}
    assert out["next"] > out["since"] and out["ret"] is not None and out["bench"] is not None


def test_no_lookahead_rank_uses_only_past():
    a = _df(0.002, seed=1)
    cut = a.index[400]
    b = a.copy()
    b.loc[b.index >= cut, "Close"] *= 10                # Zukunft verändern
    r1 = LF.rank({"A": a, "B": _df(0.001, seed=2)}, {}, cut)
    r2 = LF.rank({"A": b, "B": _df(0.001, seed=2)}, {}, cut)
    assert r1 == r2
