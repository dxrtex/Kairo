import numpy as np
import pandas as pd

from backend import live, trackpage


def _df(n=200, seed=3):
    rng = np.random.default_rng(seed)
    c = 100 * np.cumprod(1 + rng.normal(0.0005, 0.012, n))
    idx = pd.bdate_range("2025-01-01", periods=n)
    return pd.DataFrame({"Open": c * (1 + rng.normal(0, 0.002, n)), "High": c * 1.01, "Low": c * 0.99, "Close": c, "Volume": 1e6}, index=idx)


def test_strat_rule60_states():
    df = _df()
    for i in (60, 100, 150, 195):
        st = live.strat(df, i, live.RULE60)
        assert st["res"] in ("wait", "nobase", "run", "stop", "ema", "zeit")
        if st["res"] in ("stop", "ema", "zeit"):
            assert st["days"] <= 61


def test_render_counts():
    sig = [{"t": "A", "n": "Alpha", "k": "hit", "d": "2026-10-01", "region": "us", "score": 80, "st60": {"res": "ema", "r": 1.5}},
           {"t": "B", "n": "Beta", "k": "hit", "d": "2026-10-02", "region": "europe", "st60": {"res": "stop", "r": -1.0}},
           {"t": "C", "n": "<x>", "k": "hit", "d": "2026-10-03", "region": "asia", "st60": {"res": "nobase"}},
           {"t": "D", "n": "Delta", "k": "fast", "d": "2026-10-03", "region": "us"}]
    s = trackpage.summary([x for x in sig if x["k"] == "hit"])
    assert (s["n"], s["done"], s["nobase"]) == (3, 2, 1) and abs(s["avg"] - 0.25) < 1e-9 and s["win"] == 0.5
    h = trackpage.render(sig, "2026-10-19")
    assert "Delta" not in h and "&lt;x&gt;" in h and "seit 2026-10-01" in h
