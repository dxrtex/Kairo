"""Review 2, W6: Dieselben Kurse → dieselbe B60-Entscheidung in Live-Bilanz (shortswing.simulate), App-Status (h4live),
Papier-Depot (paper/kairo.py) und Test-Software (research s01 + engine): Kauftag, Kaufkurs, Stop, Verkaufstag, Verkaufskurs."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backend import h4live, live
from paper import kairo, run

S = 279


def _market(after):
    days = pd.bdate_range("2025-01-01", periods=340)
    rng = np.random.default_rng(1)
    pre = np.linspace(130, 100, 280) + rng.normal(0, 0.3, 280)
    base = [100.0, 100.3, 99.9, 100.2, 100.1, 99.95, 100.25, 100.05]
    c = np.r_[pre, base, after][:340]
    o = np.r_[c[0], c[:-1]] + 0.05
    df = pd.DataFrame({"Open": o, "High": np.maximum(o, c) + 0.5, "Low": np.minimum(o, c) - 0.5, "Close": c,
                       "Volume": 1e6, "AdjClose": c}, index=days)
    return df, days


SCEN = {"ema": list(np.linspace(100.6, 108, 25)) + list(np.linspace(107.5, 101, 27)),
        "stop": [100.3, 99.6] + list(np.linspace(97, 92, 50))}


@pytest.mark.parametrize("name", list(SCEN))
def test_gleiche_entscheidung_ueberall(name):
    df, days = _market(SCEN[name])
    ohlc = df[["Open", "High", "Low", "Close"]]
    lv = live.strat(ohlc, S, live.RULE60)
    ev = h4live.evaluate(ohlc, str(days[S].date()), None)
    # Papier-Depot
    uni = pd.DataFrame({"ticker": ["AAA", "SPY"], "currency": "USD", "region": "us"})
    mk = run.Market(uni, {"AAA": df, "SPY": df}, {"USD": pd.Series(1.0, index=days)})
    st = run.load_state(Path("/nonexistent"), "KAIRO")
    sig = [{"t": "AAA", "k": "hit", "region": "us", "d": str(days[S].date())}]
    for k in range(S, 339):
        kairo.day(st, mk, days[k], days[k - 1], sig, run.equity, run.close_pos, run.open_pos)
    pt = st["trades"][0]
    # Test-Software
    s01 = pytest.importorskip("research.strategy_championship.s01")
    from research.strategy_championship.engine import Costs, run as erun
    adj = s01.adjusted(s01.clean(df))
    orders = s01.base_orders(df, S, float(s01.atr14(df).iloc[S]), "AAA", "g", "B", 0.01, adj=adj)
    for o in orders:
        o.max_days = 60
    et = erun({"AAA": s01.with_ema(df)}, {"AAA": "EUR"}, {}, orders, 1e9, Costs(fee_eur=0, spread=0), 5,
              calendar=pd.DatetimeIndex(days[S:]), min_fill=0).trades.iloc[0]

    entry_day = ev["base"]["ed"]
    assert entry_day == pt["entry_ts"] == str(et["entry_date"].date())                     # Kauftag
    assert abs(lv["e"] - pt["entry"]) < 1e-6 and abs(pt["entry"] - et["entry_px"]) < 1e-6  # Kaufkurs
    assert abs(lv["sl"] - ev["base"]["sl"]) < 1e-4 and abs(ev["base"]["sl"] - pt["stop0"]) < 1e-4 and abs(pt["stop0"] - et["stop"]) < 1e-4
    ix = list(days)
    held = ix.index(pd.Timestamp(pt["exit_ts"])) - ix.index(pd.Timestamp(pt["entry_ts"])) + 1
    assert lv["days"] == held and pt["exit_ts"] == str(et["exit_date"].date())             # Verkaufstag
    assert abs(pt["exit"] - et["exit_px"]) < 1e-6                                          # Verkaufskurs
    assert {"ema": "ema", "stop": "stop"}[name] == lv["res"]
