"""Papier-Depot SP2F: S&P 500 mit 2-fachem Hebel, nur solange der Index über seiner 200-Tage-Linie liegt (Forschung v4).

In 1989–2026 in allen drei Zeiträumen besser als der S&P 500 mit kleinerem Rückgang (−45 % statt −55 %), nach den vorab
festgelegten Regeln aber knapp nicht bestanden (mit der 100-Tage-Linie schlechter als der Index). Deshalb nur Papier.

Jeden Handelstag aus dem Schluss des Vortags: S&P 500 (^GSPC) über SMA200 → gehebelten ETF halten, sonst Bargeld.
Ausführung zur Tageseröffnung, ganzer Topf. Instrument: Xtrackers S&P 500 2x Leveraged Daily Swap UCITS ETF
(DBPG.DE, in Deutschland handelbar). Bargeld ohne Zinsen (vorsichtig gerechnet).
"""

from __future__ import annotations

import math

import pandas as pd

from . import core

ETF = "DBPG.DE"
INDEX = "^GSPC"
SMA = 200
TICKERS = [ETF]


def above(mk, d: pd.Timestamp) -> bool | None:
    """S&P 500 am Schluss von d über seiner 200-Tage-Linie?"""
    x = mk.daily.get(INDEX)
    if x is None:
        return None
    c = x["Close"][x.index <= d].dropna()
    if len(c) < SMA:
        return None
    return bool(c.iloc[-1] > c.iloc[-SMA:].mean())


def _open(mk, t, D):
    x = mk.daily.get(t)
    if x is None or not (x.index == D).any():
        return None
    v = float(x["Open"][x.index == D].iloc[0])
    return v if v == v and v > 0 else None


def day(st: dict, mk, D: pd.Timestamp, D_prev: pd.Timestamp, equity, close_pos) -> None:
    on = above(mk, D_prev)
    if on is not None and on != st.get("on"):
        st["events"].append(f"{D.date()} S&P 500 {'über' if on else 'unter'} der 200-Tage-Linie → {'investieren' if on else 'Bargeld'}")
    if on is not None:
        st["on"] = on
        st["top"] = [ETF] if on else []
    if mk.daily.get(ETF) is None:                  # Kursquelle liefert den ETF nicht: sichtbar machen statt still nichts tun
        msg = f"{D.date()} Keine Kursdaten für {ETF} – kein Handel möglich"
        if not st["events"] or not st["events"][-1].endswith("kein Handel möglich"):
            st["events"].append(msg)
    op = _open(mk, ETF, D)                         # Börsenfeiertag in Deutschland: Wechsel am nächsten Handelstag
    if op is not None and on is False:
        for p in list(st["positions"]):
            close_pos(st, mk, p, op, "unter SMA200", str(D.date()))
    if op is not None and on and not st["positions"]:
        sp, rate = mk.spread(ETF, D_prev), mk.rate(ETF, D_prev)
        px = op * (1 + sp / 2)
        q = int(math.floor(min(equity(st, mk, D_prev) * 0.99, st["cash"] - core.FEE) * rate / px))
        if q > 0:
            cost = q * px / rate + core.fee(q * px / rate)
            st["cash"] -= cost
            st["positions"].append({"sid": st["sid"], "t": ETF, "entry_ts": str(D.date()), "entry": op, "stop": 0.0,
                                    "stop0": op, "qty": q, "cost_eur": cost, "risk_eur": None, "regime": "-"})
            st["events"].append(f"{D.date()} KAUF {ETF} {q} Stk @ {op:.4g} (S&P 500 2×)")
    st["equity"].append({"date": str(D.date()), "eur": round(equity(st, mk, D), 2), "open": len(st["positions"])})
