"""ETF-Ampel: Fehlkurse raus, Farben nach Abstand zum Hoch und 200-Tage-Linie, nie Rot."""

import numpy as np
import pandas as pd

from backend.etf import clean, compute, level


def test_levels():
    assert level(100, 90, 0.01)["lv"] == "blue"
    assert level(100, 105, 0.05)["lv"] == "green"
    assert level(100, 90, 0.12)["lv"] == "green"
    assert level(100, 120, 0.25)["lv"] == "green2"


def test_clean_removes_spike_and_compute():
    idx = pd.bdate_range("2023-01-02", periods=400)
    c = pd.Series(np.linspace(100, 140, 400), index=idx)
    c.iloc[300] = 5.0                                   # Fehlkurs
    assert clean(c).min() > 90
    out = compute(pd.DataFrame({"Close": c}))
    assert out["lv"] == "blue" and out["dd"] < 0.01 and len(out["hist"]) > 300
