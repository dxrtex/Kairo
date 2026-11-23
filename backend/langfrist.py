"""Kairo Langfrist (23.11.2026): Momentum-Depot für langfristiges Investieren neben dem Welt-ETF.

Regel aus der Studie tools/research/momentum_variants.py (Auswahl nur im Lernzeitraum 2016–2020, bestätigt 2021–2026):
Zu jedem Tauschtermin die RULE["n"] US-Aktien mit dem stärksten Kursanstieg der letzten RULE["lb"] Monate ohne den
letzten Monat (12-1-Momentum), gleich gewichtet; Universum wie im Backtest: Ø Umsatz ≥ 5 Mio. $ am Tag, Kurs ≥ 5 $.
Tauschtermine: erster Handelstag im Januar/April/Juli/Oktober (bei RULE["every"] = 3).
Ohne Zustand: Das aktuelle Depot wird bei jedem Scan aus den Kursen bis zum letzten Tauschtermin neu bestimmt.
Reine Analyse/Anzeige – keine Orders.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

RULE = {"n": 20, "lb": 12, "every": 3, "filter": False}
MIN_ADV, MIN_PX = 5e6, 5.0
# Studie momentum_variants.py (23.11.2026, 1.586 US-Aktien, deutsche Steuer, 0,15 % Kosten je Umsatz):
# Lernen 2016–2020 37,3 % p. a. nach Steuer · Prüfen 2021–2026 25,2 % (S&P-500-ETF 11,7 %) · größter Rückgang bis 44 % (ETF 24 %)
# 35/36 Varianten im Lernzeitraum, 20/36 im Prüfzeitraum über dem ETF; Marktfilter schadet (Ø 7,5 % statt 23,8 %).
BACKTEST = {"period": "2016–2026", "learn": 0.373, "test": 0.252, "etf_test": 0.117, "mdd": 0.44, "etf_mdd": 0.24}


def _is_us(t: str, m: dict | None) -> bool:
    return "." not in t and "^" not in t and (not m or (m.get("currency") or "USD") == "USD")


def rebalance_dates(idx: pd.DatetimeIndex, every: int = 3) -> list[pd.Timestamp]:
    """Erster Handelstag jedes Tauschmonats (Jan/Apr/Jul/Okt bei every=3) im Index."""
    months = set(range(1, 13, every))
    s = pd.Series(idx, index=idx)
    firsts = s.groupby([idx.year, idx.month]).first()
    return [d for (y, m), d in firsts.items() if m in months]


def _score(df: pd.DataFrame, upto: pd.Timestamp, lb: int) -> tuple[float, float] | None:
    """12-1-Momentum (ohne letzten Monat) und Ø Umsatz 63 Tage, nur mit Kursen VOR dem Stichtag."""
    d = df[df.index < upto]
    c = d["Close"].dropna()
    if len(c) < lb * 21 + 5:
        return None
    a, b = float(c.iloc[-21]), float(c.iloc[-(lb * 21)])
    if not (a > 0 and b > 0) or float(c.iloc[-1]) < MIN_PX:
        return None
    adv = float((d["Close"] * d["Volume"]).tail(63).mean()) if "Volume" in d else 0.0
    if not np.isfinite(adv) or adv < MIN_ADV:
        return None
    return a / b - 1, adv


def rank(data: dict, meta: dict, upto: pd.Timestamp, rule: dict | None = None) -> list[tuple[str, float]]:
    r = {**RULE, **(rule or {})}
    sc = []
    for t, df in data.items():
        if not _is_us(t, meta.get(t)):
            continue
        try:
            s = _score(df, upto, r["lb"])
        except Exception:
            s = None
        if s:
            sc.append((t, s[0]))
    sc.sort(key=lambda x: -x[1])
    return sc


def _px_on(df, d):
    c = df["Close"].dropna()
    i = c.index.searchsorted(d)
    return float(c.iloc[min(i, len(c) - 1)]) if len(c) else None


def build(data: dict, meta: dict, bench: pd.DataFrame | None = None, rule: dict | None = None) -> dict | None:
    """Aktuelles Langfrist-Depot, Entwicklung seit dem letzten Tausch, Vorschau auf den nächsten Tausch."""
    r = {**RULE, **(rule or {})}
    ref = bench if bench is not None and len(bench) else next((df for t, df in data.items() if _is_us(t, meta.get(t)) and len(df) > 300), None)
    if ref is None:
        return None
    idx = pd.DatetimeIndex(ref.index)
    rb = [d for d in rebalance_dates(idx, r["every"]) if d <= idx[-1]]
    if not rb:
        return None
    since = rb[-1]
    held = rank(data, meta, since, r)[: r["n"]]
    now = rank(data, meta, idx[-1] + pd.Timedelta(days=1), r)
    pos_now = {t: i + 1 for i, (t, _) in enumerate(now)}
    top_now = [t for t, _ in now[: r["n"]]]
    hold, rets = [], []
    for t, m0 in held:
        df = data[t]
        p0, p1 = _px_on(df, since), float(df["Close"].dropna().iloc[-1])
        ret = p1 / p0 - 1 if p0 else None
        rets.append(ret)
        hold.append({"t": t, "n": (meta.get(t) or {}).get("name") or t, "sec": (meta.get(t) or {}).get("sector"),
                     "m": round(m0, 4), "p0": round(p0, 4) if p0 else None, "p": round(p1, 4),
                     "ret": round(ret, 4) if ret is not None else None, "rk": pos_now.get(t)})
    port = float(np.nanmean([x for x in rets if x is not None])) if rets else None
    bret = None
    if bench is not None and len(bench):
        b0, b1 = _px_on(bench, since), float(bench["Close"].dropna().iloc[-1])
        bret = b1 / b0 - 1 if b0 else None
    y, m = since.year, since.month + r["every"]
    if m > 12:
        y, m = y + 1, m - 12
    nxt = pd.Timestamp(y, m, 1)
    while nxt.weekday() >= 5:
        nxt += pd.Timedelta(days=1)
    held_t = {x["t"] for x in hold}
    top = [{"t": t, "n": (meta.get(t) or {}).get("name") or t, "m": round(v, 4), "rk": i + 1,
            "p": round(float(data[t]["Close"].dropna().iloc[-1]), 4), "in": t in held_t} for i, (t, v) in enumerate(now[: r["n"] + 10])]
    return {"rule": r, "since": since.strftime("%Y-%m-%d"), "next": nxt.strftime("%Y-%m-%d"), "asof": idx[-1].strftime("%Y-%m-%d"),
            "hold": hold, "ret": round(port, 4) if port is not None else None, "bench": round(bret, 4) if bret is not None else None,
            "out": [t for t in held_t if t not in top_now], "inn": [t for t in top_now if t not in held_t], "top": top,
            "univ": len(now), "bt": BACKTEST}
