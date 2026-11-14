"""Implied Move: Straddle am Geld im ersten Verfall nach dem Reaktionstag, geteilt durch den Kurs."""
from types import SimpleNamespace

import pandas as pd

from backend.earnings import implied_move


class FakeTk:
    def __init__(self, options, calls, puts):
        self.options = options
        self._ch = SimpleNamespace(calls=pd.DataFrame(calls), puts=pd.DataFrame(puts))

    def option_chain(self, exp):
        self.asked = exp
        return self._ch


CALLS = [{"strike": 95.0, "bid": 7.8, "ask": 8.2, "lastPrice": 8.0}, {"strike": 100.0, "bid": 4.9, "ask": 5.1, "lastPrice": 5.0}]
PUTS = [{"strike": 100.0, "bid": 3.9, "ask": 4.1, "lastPrice": 4.0}, {"strike": 105.0, "bid": 7.0, "ask": 7.4, "lastPrice": 7.2}]


def test_straddle_after_reaction_day():
    tk = FakeTk(("2026-11-13", "2026-11-20", "2026-11-27"), CALLS, PUTS)
    ts = pd.Timestamp("2026-11-19 16:05", tz="America/New_York")     # nach Börsenschluss → Reaktion am 20.11.
    assert implied_move(tk, ts, 100.2) == 0.0898                       # (5,0 + 4,0) / 100,2
    assert tk.asked == "2026-11-20"


def test_no_value_without_fitting_expiry_or_price():
    ts = pd.Timestamp("2026-11-19 08:00", tz="America/New_York")
    assert implied_move(FakeTk(("2026-12-18",), CALLS, PUTS), ts, 100) is None   # erster Verfall > 10 Tage später
    assert implied_move(FakeTk(("2026-11-20",), CALLS, PUTS), ts, None) is None
    bad = [{"strike": 100.0, "bid": 0.0, "ask": 0.0, "lastPrice": 0.0}]
    assert implied_move(FakeTk(("2026-11-20",), bad, bad), ts, 100) is None
