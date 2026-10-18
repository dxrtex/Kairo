"""Papier-Depot MOM5: Momentum 6-1 / Volatilität, Top 5, monatlich (S07-B mit 5 statt 10 Titeln, siehe Forschung C5).

Am ersten Handelstag jedes Monats: Rangliste aus dem Schluss des Vortags (= letzter Handelstag des Vormonats):
  Score = Rendite Monat −6 … −1 (Kurs vor 21 Handelstagen ÷ Kurs vor 126 Handelstagen − 1) ÷ Volatilität 6 Monate.
  Zulässig: Ø-Dollarvolumen 20 T. ≥ 5 Mio. USD, Kurs ≥ 1 USD, ≥ 300 Handelstage Historie (Grundfilter wie in der Forschung).
Ausführung zur Tageseröffnung: erst verkaufen, was nicht mehr in den Top 5 ist, dann gleichgewichtet (Depotwert ÷ 5) kaufen.
Bestehende Titel werden nicht umgeschichtet (wie im Backtest). Kein Stop – Ausstieg nur beim Monatswechsel.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import core

N = 5
MIN_BARS = 300


def score(x: pd.DataFrame, i: int) -> float | None:
    """Momentum 6-1 / Vol 6 M. am Tag i (Schluss); None, wenn Historie zu kurz."""
    if i < max(MIN_BARS - 1, 126):
        return None
    C = x["Close"].to_numpy(float)
    m = C[i - 21] / C[i - 126] - 1
    r = np.diff(np.log(C[i - 126:i + 1]))
    v = r.std() * math.sqrt(252)
    return float(m / v) if v > 0 and np.isfinite(m) else None


def ranking(mk, tickers, d: pd.Timestamp) -> list[tuple[str, float]]:
    out = []
    for t in tickers:
        x = mk.daily.get(t)
        if x is None or d not in x.index:
            continue
        i = int(x.index.get_loc(d))
        c = x["Close"].iloc[max(0, i - 19):i + 1]
        v = x["Volume"].iloc[max(0, i - 19):i + 1].fillna(0)
        usd = 1.0 if mk.cur.get(t, "USD") == "USD" else mk.rate("SPY", d) / mk.rate(t, d)
        if not (np.isfinite(usd) and (c * v).mean() * usd >= 5e6 and float(x["Close"].iloc[i]) * usd >= 1.0):
            continue
        s = score(x, i)
        if s is not None and np.isfinite(s):
            out.append((t, s))
    return sorted(out, key=lambda z: -z[1])


def day(st: dict, mk, D: pd.Timestamp, D_prev: pd.Timestamp, tickers, equity, close_pos, n: int = N) -> None:
    """Ein Handelstag: am ersten Tag eines neuen Monats (oder beim ersten Lauf ohne Positionen) umschichten."""
    last = st.get("rebal")
    due = (last is None and not st["positions"]) or (last is not None and pd.Timestamp(last).to_period("M") != D.to_period("M"))
    if due:
        top = [t for t, _ in ranking(mk, tickers, D_prev)[:n]]
        st["rebal"] = str(D.date())
        st["top"] = top
        for p in [p for p in st["positions"] if p["t"] not in top]:
            x = mk.daily.get(p["t"])
            op = float(x["Open"][x.index == D].iloc[0]) if x is not None and (x.index == D).any() else mk.last_close(p["t"], D_prev)
            close_pos(st, mk, p, op, "monatswechsel", str(D.date()))
        held = {p["t"] for p in st["positions"]}
        eq = equity(st, mk, D_prev)
        for t in top:
            if t in held:
                continue
            x = mk.daily.get(t)
            if x is None or not (x.index == D).any():
                st["events"].append(f"{D.date()} {t}: heute kein Kurs – Kauf entfällt bis zum nächsten Monat")
                continue
            op = float(x["Open"][x.index == D].iloc[0])
            sp, rate = mk.spread(t, D_prev), mk.rate(t, D_prev)
            px = op * (1 + sp / 2)
            if not (np.isfinite(rate) and px > 0):
                continue
            q = int(math.floor(min(eq * 0.99 / n, st["cash"] - core.FEE) * rate / px))
            if q <= 0:
                st["events"].append(f"{D.date()} {t}: zu wenig Cash – kein Kauf")
                continue
            cost = q * px / rate + core.fee(q * px / rate)
            st["cash"] -= cost
            st["positions"].append({"sid": st["sid"], "t": t, "entry_ts": str(D.date()), "entry": op, "stop": 0.0, "stop0": op,
                                    "qty": q, "cost_eur": cost, "risk_eur": None, "regime": "-"})
            st["events"].append(f"{D.date()} KAUF {t} {q} Stk @ {op:.4g} (Momentum Top {n})")
        st["events"].append(f"{D.date()} Umschichtung: Top {n} = {', '.join(top)}")
    st["equity"].append({"date": str(D.date()), "eur": round(equity(st, mk, D), 2), "open": len(st["positions"])})
