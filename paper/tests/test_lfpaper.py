"""LF10: Probe-Depot der Langfrist-Strategie – Start mit dem App-Depot, Tausch nur am Quartalsanfang, Puffer, Steuer."""
from pathlib import Path

import numpy as np
import pandas as pd

from backend import langfrist as LF
from paper import lfpaper, run


def mk_market():
    days = pd.bdate_range("2023-06-01", "2025-05-30")
    rng = np.random.default_rng(1)
    d, tick = {}, []
    for k in range(7):
        c = 50 * np.exp(np.cumsum(0.0005 * (k + 1) + rng.normal(0, 0.01, len(days))))
        d[f"T{k}"] = pd.DataFrame({"Open": c, "High": c * 1.01, "Low": c * 0.99, "Close": c, "Volume": 1e6}, index=days)
        tick.append(f"T{k}")
    d["SPY"] = d["T0"]
    uni = pd.DataFrame({"ticker": tick + ["SPY"], "currency": "USD", "region": "us"})
    return run.Market(uni, d, {"USD": pd.Series(1.0, index=days)}), days, tick


def test_lf10_start_swap_buffer_tax(monkeypatch):
    monkeypatch.setitem(LF.RULE, "n", 2)
    monkeypatch.setitem(LF.RULE, "hold", 4)
    m, days, tick = mk_market()
    data, meta = {t: m.daily[t] for t in tick}, {t: {"currency": "USD"} for t in tick}
    st = run.load_state(Path("/nonexistent"), "LF10")
    assert st["start_cash"] == 10000.0
    feb = days[days.to_period("M") == pd.Period("2025-02")]
    lfpaper.day(st, m, feb[3], feb[2], days, data, meta, run.equity)            # Start mitten im Quartal: kaufen zur Eröffnung
    held = {p["t"] for p in st["positions"]}
    assert len(held) == 2 and all(p["entry"] == m.daily[p["t"]]["Open"][feb[3]] for p in st["positions"])
    lfpaper.day(st, m, feb[4], feb[3], days, data, meta, run.equity)            # kein Tauschtag: nichts tun
    assert {p["t"] for p in st["positions"]} == held and not st["trades"]
    loser = sorted(held)[-1]
    m.daily[loser].loc[feb[5]:, ["Open", "High", "Low", "Close"]] *= 0.2          # stürzt ab → am Tauschtag raus
    apr = days[days.to_period("M") == pd.Period("2025-04")]
    lfpaper.day(st, m, apr[0], days[days < apr[0]][-1], days, data, meta, run.equity)
    assert loser not in {p["t"] for p in st["positions"]} and len(st["positions"]) == 2
    tr = [t for t in st["trades"] if t["t"] == loser][0]
    assert tr["pnl_eur"] < 0 and tr["tax_eur"] == 0 and st["tax_pot"] > 0     # Verlust → Verlusttopf, keine Steuer
    assert st["cash"] >= 0 and st["fees"] > 0 and st["equity"][-1]["eur"] > 0


def test_lf10_is_rebal():
    assert lfpaper.is_rebal(pd.Timestamp("2027-01-04"), pd.Timestamp("2026-12-31"))
    assert not lfpaper.is_rebal(pd.Timestamp("2027-01-05"), pd.Timestamp("2027-01-04"))
    assert not lfpaper.is_rebal(pd.Timestamp("2027-02-01"), pd.Timestamp("2027-01-29"))


def test_lf10_gain_taxed_after_loss_pot():
    m, days, tick = mk_market()
    st = run.load_state(Path("/nonexistent"), "LF10")
    st["tax_pot"] = 100.0
    D, prev = days[-1], days[-2]
    p = {"t": "T1", "entry_ts": "2025-01-02", "entry": 10.0, "qty": 100, "cost_eur": 1000.0}
    st["positions"].append(p)
    lfpaper.sell(st, m, p, 15.0, "Test", D, prev)                                  # ≈ 500 € Gewinn − 100 € Verlusttopf
    tr = st["trades"][-1]
    assert abs(tr["tax_eur"] - (tr["pnl_eur"] - 100) * lfpaper.TAX) < 0.02 and st["tax_pot"] == 0
