"""ETF-Bereich: tägliches Signal für den SPDR MSCI ACWI IMI (Xetra SPYI.DE, Euro).

Liefert für die App (site/data/etf.json): Kurs, 200-Tage-Linie, Allzeithoch, Abstand zum Hoch, Ampel und Kursverlauf.
Ampel-Regeln: siehe level() – abgeleitet aus backend/etftest.py (Sparplan-Regeln mit gleichem Geldeinsatz).
"""

from __future__ import annotations

import pandas as pd

TICKER = "SPYI.DE"
NAME = "SPDR MSCI ACWI IMI (SPYI)"


def level(close: float, sma200: float, dd: float) -> dict:
    """Ampel für die nächste Sparrate. dd = Abstand zum Allzeithoch (0,12 = 12 % darunter)."""
    if dd >= 0.20:
        return {"lv": "green2", "t": "Kräftig nachkaufen", "s": f"{dd * 100:.0f} % unter dem Hoch – Reserve vollständig investieren."}
    if dd >= 0.10 or close <= sma200 * 1.02:
        return {"lv": "green", "t": "Mehr kaufen", "s": "Rücksetzer – Sparrate plus die Hälfte der Reserve investieren."}
    return {"lv": "yellow", "t": "Normal sparen", "s": "Normale Sparrate investieren."}


def compute(df: pd.DataFrame) -> dict:
    c = df["Close"].dropna().astype(float)
    if len(c) < 210:
        return {}
    sma = c.rolling(200).mean()
    hi = c.cummax()
    last, s, h = float(c.iloc[-1]), float(sma.iloc[-1]), float(hi.iloc[-1])
    dd = 1 - last / h
    out = {"ticker": TICKER, "name": NAME, "date": str(c.index[-1].date()), "c": round(last, 2), "sma200": round(s, 2),
           "ath": round(h, 2), "ath_date": str(c[c == h].index[-1].date()), "dd": round(dd, 4), "vs_sma": round(last / s - 1, 4),
           **level(last, s, dd)}
    w = c[c.index >= c.index[-1] - pd.Timedelta(days=3 * 365)]
    ws = sma.reindex(w.index)
    out["hist"] = [[str(t.date()), round(float(v), 2), None if pd.isna(m) else round(float(m), 2)] for t, v, m in zip(w.index, w.values, ws.values)]
    return out
