"""Live-Bilanz nach der Strategie: Kauf in der Seitwärtsphase, Stop = Basistief − 0,25 ATR, Verkauf an Tag 20."""

import numpy as np
import pandas as pd

from backend.live import strat, strat_stats


def _df(after):
    # 30 ruhige Tage um 100, Signaltag = Index 29, danach `after` (Liste von (o, h, l, c))
    rows = [(100, 101, 99, 100)] * 30 + list(after)
    d = pd.DataFrame(rows, columns=["Open", "High", "Low", "Close"], dtype=float)
    d.index = pd.bdate_range("2026-01-01", periods=len(d))
    d["Volume"] = 1e6
    return d


def test_base_then_hold_20_days():
    base = [(100, 100.5, 99.5, 100)] * 5                     # enge Basis → Kauf am Folgetag
    run = [(100.2, 101, 99.8, 100.5)] + [(101 + k * .2, 102 + k * .2, 100.5 + k * .2, 101.5 + k * .2) for k in range(25)]
    r = strat(_df(base + run), 29)
    assert r["res"] == "zeit" and r["days"] == 20 and r["r"] > 0 and r["sl"] < 99.5


def test_stop_and_waiting():
    base = [(100, 100.5, 99.5, 100)] * 5
    crash = [(100.2, 100.4, 99.9, 100)] + [(95, 95, 90, 91)] * 25
    r = strat(_df(base + crash), 29)
    assert r["res"] == "stop" and r["r"] < -0.9
    assert strat(_df(base[:2]), 29)["res"] == "wait"
    sig = [{"k": "hit", "st": r}, {"k": "hit", "st": {"res": "zeit", "r": 1.5}}, {"k": "hit", "st": {"res": "wait"}}]
    s = strat_stats(sig)
    assert s["n"] == 2 and s["win"] == 0.5 and s["stop"] == 0.5 and s["run"] == 1
