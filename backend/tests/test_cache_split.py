"""Kurs-Speicher: rückwirkende Anpassung (Split/Dividende) erkennen und komplett neu laden (Review 29.10.2026, K1)."""
import numpy as np
import pandas as pd

from backend.data_provider import CachedProvider, DataProvider


class Fake(DataProvider):
    def __init__(self, frames):
        self.frames, self.calls = frames, []

    def history(self, tickers, period, end=None):
        self.calls.append((tuple(tickers), period))
        n = 22 if period == "1mo" else None
        return {t: (f.tail(n) if n else f).copy() for t, f in self.frames.items() if t in tickers}

    def info(self, ticker):
        return {}


def _frame(close):
    idx = pd.bdate_range("2025-01-01", periods=len(close))
    c = pd.Series(close, index=idx, dtype=float)
    return pd.DataFrame({"Open": c, "High": c * 1.01, "Low": c * 0.99, "Close": c, "Volume": 1e6})


def test_split_wird_erkannt_und_neu_geladen(tmp_path):
    base = np.linspace(100, 120, 400)
    fake = Fake({"AAA": _frame(base), "BBB": _frame(base)})
    cp = CachedProvider(fake, tmp_path / "c.sqlite")
    cp.history(["AAA", "BBB"], "2y")                       # erster Lauf: alles in den Speicher
    # Tag später: AAA hat einen 2:1-Split, Yahoo liefert die GANZE Historie halbiert (plus einen neuen Tag)
    split = np.r_[base, 121.0] / 2
    fake.frames = {"AAA": _frame(split), "BBB": _frame(np.r_[base, 121.0])}
    out = cp.history(["AAA", "BBB"], "2y")
    a = out["AAA"]["Close"]
    assert abs(a.iloc[0] - 50) < 1e-6 and abs(a.iloc[-1] - 60.5) < 1e-6      # keine Mischung alt/neu → kein künstlicher Absturz
    assert float((a.pct_change().dropna()).min()) > -0.05
    assert ("AAA",) in [c[0] for c in fake.calls if c[1] == "2y"][-1:] or any("AAA" in c[0] and c[1] == "2y" for c in fake.calls[2:])
    assert len(out["BBB"]) == 401                                                 # unveränderte Aktie: nur nachgeladen


def test_unveraendert_kein_neuladen(tmp_path):
    base = np.linspace(50, 60, 300)
    fake = Fake({"CCC": _frame(base)})
    cp = CachedProvider(fake, tmp_path / "c.sqlite")
    cp.history(["CCC"], "2y")
    fake.frames = {"CCC": _frame(np.r_[base, 60.2])}
    cp.history(["CCC"], "2y")
    assert [c[1] for c in fake.calls] == ["2y", "1mo"]
