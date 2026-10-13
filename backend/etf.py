"""ETF-Bereich: tägliches Signal für den SPDR MSCI ACWI IMI (Xetra SPYI.DE, Euro).

Liefert für die App (site/data/etf.json): Kurs, 200-Tage-Linie, Allzeithoch, Abstand zum Hoch, Ampel und Kursverlauf.
Ampel-Regeln: siehe level() – abgeleitet aus backend/etftest.py (Okt. 2026, ACWI ab 2008 und Welt-Proxy ab 2003):
- Sparrate zurückhalten und auf Rücksetzer warten brachte NICHTS (Endwert −0,3 bis −1,5 % gegenüber stur jeden Monat),
  ein Trendfilter kostete sogar ein Fünftel des Endwerts (halbierte aber die Rückgänge). → Die Sparrate läuft immer.
- Nach Rücksetzern war die Folge-Rendite aber deutlich höher: ≥ 20 % unter dem Hoch im Schnitt +21 % in 12 Monaten
  (nur 1–7 % der Fälle im Minus), am Hoch +9 %. → Extra-Geld (Bonus, Rücklage) lohnt sich besonders bei Grün.
Deshalb gibt es kein Rot: „Nicht kaufen“ hätte im Test Geld gekostet.
"""

from __future__ import annotations

import pandas as pd

TICKER = "SPYI.DE"
NAME = "SPDR MSCI ACWI IMI (SPYI)"


def level(close: float, sma200: float, dd: float) -> dict:
    """Ampel. dd = Abstand zum Allzeithoch (0,12 = 12 % darunter). Die Sparrate läuft bei jeder Farbe."""
    if dd >= 0.20:
        return {"lv": "green2", "t": "Ausverkauf – Extra-Geld jetzt", "s": f"{dd * 100:.0f} % unter dem Hoch. Historisch im Schnitt "
                "+21 % in den nächsten 12 Monaten, fast nie im Minus. Sparrate weiter und verfügbares Extra-Geld investieren."}
    if dd >= 0.10 or close < sma200:
        return {"lv": "green", "t": "Günstige Phase – gern mehr", "s": "Rücksetzer bzw. unter der 200-Tage-Linie. Historisch im Schnitt "
                "+15–18 % in 12 Monaten. Sparrate weiter; Extra-Geld lohnt sich jetzt mehr als sonst."}
    return {"lv": "blue", "t": "Normal sparen", "s": "Nahe am Hoch. Das ist der Normalfall und kein Warnsignal: Auch vom Hoch aus lag der "
            "ETF nach 12 Monaten im Schnitt rund 9 % höher. Sparrate wie geplant, nicht warten."}


def clean(c: pd.Series) -> pd.Series:
    """Einzelne Fehlkurse von Yahoo entfernen (Sprung > 15 %, der am nächsten Tag zurückläuft) – ein Welt-ETF macht so etwas nicht."""
    c = c[c > 0]
    for _ in range(3):
        r = c.pct_change()
        bad = (r.abs() > 0.15) & ((r.shift(-1) * r) < 0) & (r.shift(-1).abs() > 0.12)
        if not bad.any():
            break
        c = c[~bad]
    return c


def compute(df: pd.DataFrame) -> dict:
    c = clean(df["Close"].dropna().astype(float))
    if len(c) < 210:
        return {}
    sma = c.rolling(200).mean()
    hi = c.cummax()
    last, s, h = float(c.iloc[-1]), float(sma.iloc[-1]), float(hi.iloc[-1])
    dd = 1 - last / h
    out = {"ticker": TICKER, "name": NAME, "n": len(c), "date": str(c.index[-1].date()), "c": round(last, 2), "sma200": round(s, 2),
           "ath": round(h, 2), "ath_date": str(c[c == h].index[-1].date()), "dd": round(dd, 4), "vs_sma": round(last / s - 1, 4),
           **level(last, s, dd)}
    w = c[c.index >= c.index[-1] - pd.Timedelta(days=3 * 365)]
    ws = sma.reindex(w.index)
    out["hist"] = [[str(t.date()), round(float(v), 2), None if pd.isna(m) else round(float(m), 2)] for t, v, m in zip(w.index, w.values, ws.values)]
    return out
