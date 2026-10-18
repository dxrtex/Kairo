"""Ablauf-Test ohne Netz: wartendes S20-Setup → H4-Auslöser → Kauf → Break-even → Trailing → Verkauf; S19 mit CRV-Ablehnung."""
import numpy as np
import pandas as pd

from paper import core, run


def market():
    days = pd.bdate_range("2025-01-01", periods=300)
    c = np.linspace(50, 100, 300)
    d = pd.DataFrame({"Open": c, "High": c * 1.01, "Low": c * 0.99, "Close": c, "Volume": np.full(300, 1e6)}, index=days)
    uni = pd.DataFrame({"ticker": ["AAA", "SPY"], "currency": ["USD", "USD"], "region": ["us", "us"]})
    fx = {"USD": pd.Series(1.0, index=days)}
    mk = run.Market(uni, {"AAA": d, "SPY": d}, fx)
    D_prev, D = days[-2], days[-1]
    hrs = pd.date_range(D.normalize() + pd.Timedelta(hours=13, minutes=30), periods=7, freq="1h")
    old = pd.date_range(D_prev.normalize() + pd.Timedelta(hours=13, minutes=30), periods=7, freq="1h")
    o = [99.0] * 7 + [99.0, 101.0, 103.0, 104.0, 104.0, 103.0, 101.0]
    h = pd.DataFrame({"Open": o, "High": [x + 0.5 for x in o], "Low": [x - 0.5 for x in o], "Close": o,
                      "Volume": [100] * 7 + [500] * 7}, index=old.append(hrs))
    h.iloc[7:11, h.columns.get_loc("Close")] = [100.5, 102.5, 103.8, 104]
    mk.h4["AAA"] = core.to_h4(h)
    return mk, days, D_prev, D


def test_s20_flow():
    mk, days, D_prev, D = market()
    st = run.load_state(__import__("pathlib").Path("/nonexistent"), "S20")
    st["pending"] = [{"t": "AAA", "day": str(D_prev.date()), "expiry": str(D.date()), "atr": 1.0}]
    mk.h4["AAA"]["ema20"] = 95.0
    mk.h4["AAA"]["vma20"] = 50.0
    run.process_day(st, mk, D, D_prev, days, True)
    assert st["positions"] or st["trades"], st["events"]
    assert any("KAUF AAA" in e for e in st["events"])
    assert st["equity"][-1]["eur"] > 0


def test_s19_crv_reject():
    mk, days, D_prev, D = market()
    st = run.load_state(__import__("pathlib").Path("/nonexistent"), "S19")
    mk.h4["AAA"].iloc[0, mk.h4["AAA"].columns.get_loc("Close")] = 98.0       # rote Kerze vor dem Auslöser
    st["pending"] = [{"t": "AAA", "day": str(D_prev.date()), "expiry": str(D.date()), "panic": 90.0, "atr": 2.0, "z": -3}]
    run.process_day(st, mk, D, D_prev, days, True)
    assert not st["positions"] and any("CRV" in e for e in st["events"]), st["events"]


def test_start_cash_migration(tmp_path):
    import json
    st = run.load_state(tmp_path, "S20")
    st.update(start_cash=5000.0, cash=5000.0, equity=[{"date": "2026-10-16", "eur": 5000.0, "open": 0}],
              pending=[{"t": "AAA", "day": "2026-10-16", "expiry": "2026-10-23", "atr": 1.0}])
    (tmp_path / "s20.json").write_text(json.dumps(st))
    st2 = run.load_state(tmp_path, "S20")
    assert st2["start_cash"] == st2["cash"] == run.START_CASH == 2000.0
    assert st2["equity"][0]["eur"] == 2000.0 and len(st2["pending"]) == 1


def test_s19_funnel_counts():
    mk, days, D_prev, D = market()
    st = run.load_state(__import__("pathlib").Path("/nonexistent"), "S19")
    fund = {"AAA": {"mcap": 2e11, "opm": 0.2, "sector": "Technology"}}
    run.new_setups(st, mk, D, days, ["AAA"], True, fund, {"XLK": {D: 0.01}}, dry=True)
    f = st["funnel"]
    assert f["Qualität"] == 1 and f["Kursdaten"] == 1 and f["liquide"] == 1 and f["Signale"] == 0
    assert f["≥ 2,5 Std unter EMA20"] == 0 and not st["pending"]          # gleichmäßiger Aufwärtstrend: keine Überdehnung


def test_fill_next_open_priority_and_net_r():
    mk, days, D_prev, D = market()
    mk.h4["BBB"] = mk.h4["AAA"].copy()
    mk.daily["BBB"] = mk.daily["AAA"]
    mk.cur["BBB"], mk.region["BBB"] = "USD", "us"
    for t in ("AAA", "BBB"):
        mk.h4[t]["ema20"] = 95.0
    mk.h4["AAA"]["vma20"] = 100.0                        # AAA: Volumen 20× Ø, BBB: 40× Ø → BBB zuerst
    mk.h4["BBB"]["vma20"] = 50.0
    st = run.load_state(__import__("pathlib").Path("/nonexistent"), "S20")
    st["pending"] = [{"t": t, "day": str(D_prev.date()), "expiry": str(D.date()), "atr": 1.0} for t in ("AAA", "BBB")]
    run.MAX_OPEN, old = 1, run.MAX_OPEN
    try:
        run.process_day(st, mk, D, D_prev, days, True)
    finally:
        run.MAX_OPEN = old
    buys = [e for e in st["events"] if " KAUF " in e]
    assert len(buys) == 1 and "KAUF BBB" in buys[0]                    # stärkeres Signal bekommt den einzigen Platz
    assert any("AAA: Auslöser, aber Depot voll" in e for e in st["events"])
    t = (st["trades"] or [None])[0]
    trig = mk.h4["BBB"].index[2]
    assert pd.Timestamp((t or st["positions"][0])["entry_ts"]) > trig     # Kauf erst nach der Auslöse-Kerze
    if t:
        assert t["R_net"] < t["R"]                                         # netto nach Kosten schlechter


def test_s19_variant_funnel_label():
    mk, days, D_prev, D = market()
    st = run.load_state(__import__("pathlib").Path("/nonexistent"), "S19C")
    fund = {"AAA": {"mcap": 2e11, "opm": 0.2, "sector": "Technology"}}
    run.new_setups(st, mk, D, days, ["AAA"], True, fund, {"XLK": {D: 0.01}}, dry=True)
    assert "≥ 2,0 Std unter EMA20" in st["funnel"] and st["funnel"]["Signale"] == 0
