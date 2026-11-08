"""ETF-Bereich: tägliches Signal für den SPDR MSCI ACWI IMI (Xetra SPYI.DE, Euro).

Liefert für die App (site/data/etf.json): Kurs, 200-Tage-Linie, Allzeithoch, Abstand zum Hoch, Ampel und Kursverlauf.
Ampel (neu 11/2026): Gelegenheit · Normal · In Raten – siehe level(), backend/etfextra.py und tools/research/etf_ampel_freq.py.
Frühere Grundlage: Grundlage: backend/etftest.py und backend/etffactors.py (Okt. 2026; S&P 500 1990–2007 und
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

import numpy as np
import pandas as pd

TICKER = "SPYI.DE"
REF = "IUSQ.DE"                    # Gegenprobe: iShares MSCI ACWI (Xetra) – läuft fast gleich, andere Datenreihe
NAME = "SPDR MSCI ACWI IMI (SPYI)"


GO_DD, GO_VIX, PANIC_VIX, MAX_WAIT_M = 0.05, 25, 30, 3


def level(vix: float | None, below_sma: bool, credit_weak: bool | None, last_go: str | None = None, today: str | None = None) -> dict:
    """Ampel für Extra-Geld (die Sparrate läuft immer) – neu 11/2026. Auslöser: Jonny „steht gefühlt immer auf jetzt investieren“.
    Befund backend/etfextra.py (S&P 500 ab 1990, SPY, Welt-Proxy ab 2003, ACWI ab 2008): JEDE Warte-Regel war schlechter als
    Extra-Geld sofort zu investieren – strengere Regeln (seltener grün) kosteten mehr (−1 bis −3 % statt −0,1 bis −0,7 %).
    Darum gibt es kein „Abwarten“ mehr. Die Ampel unterscheidet nur noch, was laut tools/research/etf_ampel_freq.py zählt
    (Monatsenden 2007–2025, SPY / ACWI):
    - Gelegenheit (VIX ≥ 30, ~10 % der Monate): Ø +28 / +30 % in 12 Monaten → zusätzlich nachlegen (Reserve, Bonus).
    - In Raten (unter der 200-Tage-Linie UND Kreditmarkt schwach, ~11 %): Rendite nicht verlässlich schlechter, aber beim S&P 500
      öfter noch ein weiterer Rückgang um 10 % (46 % statt 33 %) → Extra-Geld auf 3 Monate verteilen statt auf einmal.
    - Normal (~79 %): Extra-Geld wie geplant anlegen."""
    if vix is not None and vix >= PANIC_VIX:
        return {"lv": "go2", "t": "Gelegenheit – zusätzlich nachlegen", "why": [f"VIX {vix:.0f} (≥ {PANIC_VIX}, Angst am Markt)"],
                "s": f"VIX {vix:.0f}: In den Tests folgten auf solche Angstphasen die besten 12 Monate (Ø +28 bis +30 %). "
                     "Extra-Geld jetzt anlegen – wer eine Reserve hat, legt zusätzlich nach, gern in 2–3 Raten über einige Wochen."}
    if below_sma and credit_weak:
        return {"lv": "rate", "t": "In Raten anlegen", "why": ["unter der 200-Tage-Linie", "Kreditmarkt schwach"],
                "s": "Kurs unter der 200-Tage-Linie und der Kreditmarkt schwächelt: Die Rendite war danach nicht verlässlich schlechter, "
                     "aber öfter kam noch ein weiterer Rückgang. Extra-Geld auf 3 Monate verteilen statt auf einmal. Die Sparrate läuft weiter."}
    return {"lv": "go", "t": "Normal – Extra-Geld anlegen", "why": [],
            "s": "Kein besonderes Signal. Extra-Geld wie geplant anlegen – auf einen besseren Zeitpunkt zu warten hat im Test "
                 "über 35 Jahre immer Geld gekostet. Die Sparrate läuft weiter."}


def clean(c: pd.Series) -> pd.Series:
    """Yahoo-Fehler beheben – ein Welt-ETF bewegt sich nie um 35 % an einem Tag:
    1) einzelne Fehlkurse (Sprung, der am nächsten Tag zurückläuft) entfernen,
    2) dauerhafte Sprünge = nicht bereinigter Split: alle Kurse davor auf das neue Niveau umrechnen."""
    c = c[c > 0].astype(float)
    for _ in range(3):
        r = c.pct_change()
        bad = (r.abs() > 0.15) & ((r.shift(-1) * r) < 0) & (r.shift(-1).abs() > 0.12)
        if not bad.any():
            break
        c = c[~bad]
    r = c / c.shift(1)
    for t in r.index[(r > 1.35) | (r < 1 / 1.35)]:
        i = c.index.get_loc(t)
        k = float(c.iloc[i] / c.iloc[i - 1])
        c.iloc[:i] = c.iloc[:i] * k
    return c


def _last(x: pd.Series | None):
    if x is None:
        return None
    x = x.dropna()
    return float(x.iloc[-1]) if len(x) else None


def crosscheck(c: pd.Series, ref: pd.Series | None) -> dict:
    """Gegenprobe mit einem zweiten Welt-ETF: Entwicklung über 1/5/20 Tage darf kaum abweichen, sonst Datenfehler."""
    if ref is None:
        return {"ref": None}
    r = clean(ref.dropna().astype(float))
    j = pd.concat([c, r], axis=1, join="inner").dropna()
    if len(j) < 25:
        return {"ref": None}
    dev = max(abs((j.iloc[-1, 0] / j.iloc[-1 - k, 0]) - (j.iloc[-1, 1] / j.iloc[-1 - k, 1])) for k in (1, 5, 20))
    return {"ref": REF, "ref_dev": round(float(dev), 4), "ref_ok": bool(dev < 0.04)}


def compute(df: pd.DataFrame, vix: pd.Series | None = None, hyg: pd.Series | None = None, ief: pd.Series | None = None,
            ref: pd.Series | None = None, today: str | None = None) -> dict:
    c = clean(df["Close"].dropna().astype(float))
    if len(c) < 210:
        return {}
    sma = c.rolling(200).mean()
    e100 = c.ewm(span=100, adjust=False).mean()
    hi = c.cummax()
    last, s, h = float(c.iloc[-1]), float(sma.iloc[-1]), float(hi.iloc[-1])
    dd = 1 - last / h
    v = _last(vix)
    cw = None
    if hyg is not None and ief is not None:
        cr = (hyg / ief).dropna()
        if len(cr) >= 200:
            cw = bool(cr.iloc[-1] < cr.rolling(200).mean().iloc[-1])
    xc = crosscheck(c, ref)
    age = (pd.Timestamp(today) - c.index[-1]).days if today else 0
    out = {"ticker": TICKER, "name": NAME, "n": len(c), "ok": bool(dd < 0.6 and xc.get("ref_ok", True)), "age": int(age), **xc, "date": str(c.index[-1].date()), "c": round(last, 2), "sma200": round(s, 2),
           "ath": round(h, 2), "ath_date": str(c[c == h].index[-1].date()), "dd": round(dd, 4), "vs_sma": round(last / s - 1, 4),
           "vix": None if v is None else round(v, 1), "credit_weak": cw, "e100": round(float(e100.iloc[-1]), 2),
           "vs_e100": round(last / float(e100.iloc[-1]) - 1, 4)}
    # letzter Tag mit Kaufsignal (für „höchstens 3 Monate warten“)
    vx = vix.reindex(c.index).ffill() if vix is not None else pd.Series(np.nan, index=c.index)
    go = (c < e100) | (1 - c / hi >= GO_DD) | (vx >= GO_VIX)
    last_go = str(go[go].index[-1].date()) if go.any() else None
    out.update(level(v, last < s, cw, last_go, today or str(c.index[-1].date())))
    out["last_go"] = last_go
    w = c[c.index >= c.index[-1] - pd.Timedelta(days=3 * 365)]
    ws = sma.reindex(w.index)
    out["hist"] = [[str(t.date()), round(float(x), 2), None if pd.isna(m) else round(float(m), 2)] for t, x, m in zip(w.index, w.values, ws.values)]
    return out
