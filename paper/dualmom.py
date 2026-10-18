"""Papier-Depot DM: Dual Momentum SPY / EFA / QQQ → SHY (S16-B; einzige Strategie, die in Train, Validierung und Holdout
netto besser als ACWI war – im Holdout aber nicht signifikant besser als Zufall, p = 0,07).

Am ersten Handelstag jedes Monats aus dem Schluss des Vortags: 12-Monats-Rendite (252 Handelstage) von SPY, EFA, QQQ;
der beste ETF wird gehalten, wenn seine Rendite über der von BIL (Geldmarkt) liegt, sonst SHY (kurze US-Anleihen).
Ausführung zur Tageseröffnung, ganzer Topf in einem ETF.
"""

from __future__ import annotations

import math

import pandas as pd

from . import core

TICKERS = ["SPY", "EFA", "QQQ", "SHY", "BIL"]


def r12(mk, t: str, d: pd.Timestamp) -> float | None:
    x = mk.daily.get(t)
    if x is None or d not in x.index:
        return None
    i = int(x.index.get_loc(d))
    return float(x["Close"].iloc[i] / x["Close"].iloc[i - 252] - 1) if i >= 252 else None


def target(mk, d: pd.Timestamp) -> str | None:
    sc = {t: r12(mk, t, d) for t in ("SPY", "EFA", "QQQ")}
    sc = {t: v for t, v in sc.items() if v is not None}
    bil = r12(mk, "BIL", d)
    if not sc or bil is None:
        return None
    best = max(sc, key=sc.get)
    return best if sc[best] > bil else "SHY"


def day(st: dict, mk, D: pd.Timestamp, D_prev: pd.Timestamp, equity, close_pos) -> None:
    last = st.get("rebal")
    if last is None or pd.Timestamp(last).to_period("M") != D.to_period("M"):
        t = target(mk, D_prev)
        st["rebal"] = str(D.date())
        if t is not None:
            st["top"] = [t]
            for p in [p for p in st["positions"] if p["t"] != t]:
                x = mk.daily[p["t"]]
                op = float(x["Open"][x.index == D].iloc[0]) if (x.index == D).any() else mk.last_close(p["t"], D_prev)
                close_pos(st, mk, p, op, "monatswechsel", str(D.date()))
            x = mk.daily.get(t)
            if not st["positions"] and x is not None and (x.index == D).any():
                op = float(x["Open"][x.index == D].iloc[0])
                sp, rate = mk.spread(t, D_prev), mk.rate(t, D_prev)
                px = op * (1 + sp / 2)
                q = int(math.floor((min(equity(st, mk, D_prev) * 0.99, st["cash"] - core.FEE)) * rate / px))
                if q > 0:
                    cost = q * px / rate + core.fee(q * px / rate)
                    st["cash"] -= cost
                    st["positions"].append({"sid": st["sid"], "t": t, "entry_ts": str(D.date()), "entry": op, "stop": 0.0,
                                            "stop0": op, "qty": q, "cost_eur": cost, "risk_eur": None, "regime": "-"})
                    st["events"].append(f"{D.date()} KAUF {t} {q} Stk @ {op:.4g} (Dual Momentum)")
            st["events"].append(f"{D.date()} Dual Momentum: Ziel {t}")
    st["equity"].append({"date": str(D.date()), "eur": round(equity(st, mk, D), 2), "open": len(st["positions"])})
