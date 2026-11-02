"""Aussetzer des Screeners dürfen die Aktienliste nicht schrumpfen lassen."""

import pandas as pd

from backend.universe import guard


def test_guard_fills_missing_on_big_drop():
    prev = pd.DataFrame({"ticker": [f"T{i}" for i in range(100)], "name": "x"})
    new = prev.iloc[:60]
    out = guard(new, prev, "us")
    assert len(out) == 100 and set(out["ticker"]) == set(prev["ticker"])


def test_guard_keeps_normal_changes():
    prev = pd.DataFrame({"ticker": [f"T{i}" for i in range(100)], "name": "x"})
    new = pd.concat([prev.iloc[:95], pd.DataFrame({"ticker": ["NEU"], "name": "y"})])
    assert len(guard(new, prev, "us")) == 96 and len(guard(new, None, "us")) == 96


def test_heimatboerse_statt_wiener_zweitlisting():
    """BYD und Tencent fehlten: das Wiener Zweitlisting (fast kein Umsatz) verdrängte die Börse Hongkong."""
    import pandas as pd
    from backend.universe import COLUMNS, pick_home
    row = lambda t, n, reg, adv, cap=1e10: {**{c: None for c in COLUMNS}, "ticker": t, "name": n, "country": reg, "adv_usd": adv, "market_cap_usd": cap}
    us = pd.DataFrame([row("BABA", "Alibaba Group Holding Limited", "us", 9e8)], columns=COLUMNS)
    eu = pd.DataFrame([row("BY6.VI", "BYD Company Limited", "at", 12343), row("NNND.VI", "Tencent Holdings Limited", "at", 529),
                       row("SAP.DE", "SAP SE", "de", 5e8), row("9988.VI", "Alibaba Group Holding Limited", "at", 10)], columns=COLUMNS)
    asia = pd.DataFrame([row("1211.HK", "BYD Company Limited", "hk", 4e8), row("0700.HK", "Tencent Holdings Limited", "hk", 1.5e9),
                         row("9988.HK", "Alibaba Group Holding Limited", "hk", 1e9)], columns=COLUMNS)
    out = pick_home({"us": us, "ca": pd.DataFrame(columns=COLUMNS), "eu": eu, "asia": asia})
    assert set(out["asia"]["ticker"]) == {"1211.HK", "0700.HK"}          # Alibaba bleibt in den USA (BABA)
    assert list(out["eu"]["ticker"]) == ["SAP.DE"] and list(out["us"]["ticker"]) == ["BABA"]
