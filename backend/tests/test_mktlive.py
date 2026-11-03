import numpy as np
import pandas as pd

from backend import mktlive


def _df(n=300, step=0.001):
    idx = pd.bdate_range("2025-06-02", periods=n)
    c = 100 * np.cumprod(np.full(n, 1 + step))
    return pd.DataFrame({"Open": c, "High": c, "Low": c, "Close": c, "Volume": 1000.0}, index=idx)


def test_pick_top_per_region_and_de():
    rows = [{"t": f"U{i}", "r": "us", "mc": i} for i in range(300)] + [{"t": "SAP.DE", "r": "europe", "mc": 1}]
    got = mktlive.pick(rows)
    assert "U299" in got and "U50" not in got and "SAP.DE" in got


def test_build(monkeypatch):
    monkeypatch.setattr(mktlive, "_frames", lambda ts, period: {t: _df() for t in ts if t in ("XLK", "SOXX", "AAA")})
    out = mktlive.build([{"t": "AAA", "r": "us", "mc": 5}])
    assert out["sectors"][0]["k"] == "XLK" and out["industries"][0]["k"] == "SOXX"
    assert set(out["rows"]) == {"AAA"} and out["rows"]["AAA"]["d1"] is not None and "c" in out["rows"]["AAA"]


def test_pick_skips_illiquid_listings():
    from backend.mktlive import pick
    rows = [{"t": "HPQ", "r": "us", "mc": 3e10}, {"t": "HPQ.VI", "r": "europe", "mc": 3e10, "km": ["liquidity"]},
            {"t": "SAP.DE", "r": "europe", "mc": 2e11, "km": ["drawdown"]}]
    assert pick(rows) == ["HPQ", "SAP.DE"]
