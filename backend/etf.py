"""ETF-Bereich: tägliches Signal für den SPDR MSCI ACWI IMI (Xetra SPYI.DE, Euro).

Liefert für die App (site/data/etf.json): Kurs, 200-Tage-Linie, Allzeithoch, Abstand zum Hoch, Ampel und Kursverlauf.
Ampel-Regeln: siehe level(). Grundlage: backend/etftest.py und backend/etffactors.py (Okt. 2026; S&P 500 1990–2007 und
2008–2026 getrennt, Welt-Proxy 2004–2026; Monatsende-Stichproben, Rendite der nächsten 12 Monate):
- Sparrate zurückhalten und warten brachte nichts → die Sparrate läuft bei jeder Farbe; die Ampel steuert nur Extra-Geld.
- In ALLEN drei Zeiträumen gleich: VIX ≥ 30 (Panik) → beste Folgejahre (+16 / +25 / +28 %); VIX 20–30 → schwächste (+5 / +8 / +5 %).
  Ruhiger Markt (VIX < 14) war KEIN Warnsignal (+11 % in allen drei).
- Unter der 200-Tage-Linie und schwacher Kreditmarkt (HYG/IEF): nicht schlechtere Rendite, aber deutlich öfter noch
  ein weiterer Rückgang um 10 % (≈ 50 % statt ≈ 30 %) → Extra-Geld in Raten statt auf einmal.
- Widersprüchlich und daher NICHT in der Ampel: Abstand zum Hoch (≥ 20 % darunter: 1990–2007 schlecht, ab 2008 gut),
  Zinskurve (invertiert: 1990–2007 −5 %, ab 2008 +20 %), 12-Monats-Trend.
Kein Rot: „Nicht kaufen“ hat im Test Geld gekostet.
"""

from __future__ import annotations

import pandas as pd

TICKER = "SPYI.DE"
NAME = "SPDR MSCI ACWI IMI (SPYI)"


def level(vix: float | None, below_sma: bool, credit_weak: bool | None) -> dict:
    """Ampel für Extra-Geld (die Sparrate läuft immer). Nur Faktoren, die in allen Testzeiträumen gleich wirkten."""
    risk = [x for x, on in (("unter der 200-Tage-Linie", below_sma), ("Kreditmarkt schwächelt", credit_weak),
                            ("VIX nervös (20–30)", vix is not None and 20 <= vix < 30)) if on]
    if vix is not None and vix >= 30:
        return {"lv": "green2", "t": "Panik – beste Kaufgelegenheit", "risk": risk,
                "s": f"VIX {vix:.0f}: In allen Testzeiträumen folgten auf Panik die besten 12 Monate (Ø +16 bis +28 %). "
                     "Sparrate weiter und verfügbares Extra-Geld investieren – gern in 2–3 Raten über einige Wochen."}
    if len(risk) >= 2:
        return {"lv": "yellow", "t": "Unruhig – Extra-Geld in Raten", "risk": risk,
                "s": "Mehrere Warnzeichen (" + ", ".join(risk) + "). Historisch nicht unbedingt schlechtere Rendite, aber oft noch ein "
                     "weiterer Rückgang um 10 %. Sparrate unbedingt weiterlaufen lassen; Extra-Geld über 3–6 Monate verteilen."}
    return {"lv": "blue", "t": "Normal – Sparrate wie geplant", "risk": risk,
            "s": "Keine Panik, höchstens ein Warnzeichen" + (f" ({risk[0]})" if risk else "") + ". Auch nahe am Hoch lag der ETF ein Jahr "
                 "später im Schnitt rund 9–12 % höher – ein Allzeithoch ist kein Wartesignal. Extra-Geld kann sofort investiert werden."}


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


def _last(x: pd.Series | None):
    if x is None:
        return None
    x = x.dropna()
    return float(x.iloc[-1]) if len(x) else None


def compute(df: pd.DataFrame, vix: pd.Series | None = None, hyg: pd.Series | None = None, ief: pd.Series | None = None) -> dict:
    c = clean(df["Close"].dropna().astype(float))
    if len(c) < 210:
        return {}
    sma = c.rolling(200).mean()
    hi = c.cummax()
    last, s, h = float(c.iloc[-1]), float(sma.iloc[-1]), float(hi.iloc[-1])
    dd = 1 - last / h
    v = _last(vix)
    cw = None
    if hyg is not None and ief is not None:
        cr = (hyg / ief).dropna()
        if len(cr) >= 200:
            cw = bool(cr.iloc[-1] < cr.rolling(200).mean().iloc[-1])
    out = {"ticker": TICKER, "name": NAME, "n": len(c), "date": str(c.index[-1].date()), "c": round(last, 2), "sma200": round(s, 2),
           "ath": round(h, 2), "ath_date": str(c[c == h].index[-1].date()), "dd": round(dd, 4), "vs_sma": round(last / s - 1, 4),
           "vix": None if v is None else round(v, 1), "credit_weak": cw, **level(v, last < s, cw)}
    w = c[c.index >= c.index[-1] - pd.Timedelta(days=3 * 365)]
    ws = sma.reindex(w.index)
    out["hist"] = [[str(t.date()), round(float(x), 2), None if pd.isna(m) else round(float(m), 2)] for t, x, m in zip(w.index, w.values, ws.values)]
    return out
