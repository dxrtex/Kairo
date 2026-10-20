"""Stimmung / Angst am Aktienmarkt (0 = sorglos … 100 = Panik) – Anzeige neben der Trend-Ampel.

Sieben frei verfügbare Messgrößen, jede auf 0–100 umgerechnet, dann gemittelt:
VIX-Höhe, VIX-Anstieg (5 Tage), VIX ÷ VIX3M (kurzfristige über langfristiger Angst = Stress), Tech/KI (Nasdaq 100 und
Halbleiter-ETF SMH: Abstand zum 52-Wochen-Hoch), Marktbreite aus dem eigenen Scan (Anteil über der EMA 50), neue
52-Wochen-Tiefs im Scan, Kreditmarkt (Hochzins- gegen Staatsanleihen, HYG ÷ IEF gegen ihren 50-Tage-Schnitt).
Die Schwellen sind Erfahrungswerte (z. B. VIX 12 ruhig, 35 Panik) – eine Einordnung, keine getestete Handelsregel.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TICKERS = ("^VIX", "^VIX3M", "^NDX", "SMH", "HYG", "IEF")
LEVELS = ((80, "Panik", "red"), (65, "Angst", "red"), (45, "Vorsicht", "yellow"), (25, "Neutral", "green"), (0, "Sorglos", "green"))


def _lin(x: float, calm: float, panic: float) -> float:
    """x auf 0 (ruhig) … 100 (Panik) abbilden, begrenzt."""
    return float(np.clip((x - calm) / (panic - calm) * 100, 0, 100))


def _close(hist: dict, t: str) -> pd.Series | None:
    df = hist.get(t)
    if df is None or not len(df):
        return None
    c = df["Close"].dropna()
    return c if len(c) > 5 else None


def _dd(c: pd.Series) -> float:
    return float(c.iloc[-1] / c.iloc[-252:].max() - 1)


def breadth(frames) -> dict | None:
    """Anteil der Scan-Aktien über ihrer EMA 50 und Anteil am 52-Wochen-Tief (± 1 %)."""
    above = low = n = 0
    for df in frames:
        try:
            c = df["Close"].dropna()
            if len(c) < 60:
                continue
            e50 = c.ewm(span=50, adjust=False).mean().iloc[-1]
            n += 1
            above += int(c.iloc[-1] > e50)
            low += int(c.iloc[-1] <= c.iloc[-252:].min() * 1.01)
        except Exception:
            continue
    return {"n": n, "above50": above / n, "lows": low / n} if n >= 200 else None


def fear(hist: dict, br: dict | None) -> dict | None:
    parts = []
    vix, v3 = _close(hist, "^VIX"), _close(hist, "^VIX3M")
    if vix is not None:
        v = float(vix.iloc[-1])
        parts.append(("vix", "VIX", f"{v:.1f}", _lin(v, 12, 35)))
        ch = float(vix.iloc[-1] / vix.iloc[-6] - 1)
        parts.append(("vix5", "VIX-Anstieg 5 Tage", f"{ch * 100:+.0f} %", _lin(ch, 0.0, 0.5)))
        if v3 is not None and v3.iloc[-1] > 0:
            r = v / float(v3.iloc[-1])
            parts.append(("term", "Kurz- ÷ langfristige Angst", f"{r:.2f}", _lin(r, 0.85, 1.05)))
    tech = {}
    for t, name in (("^NDX", "Nasdaq 100"), ("SMH", "Halbleiter (SMH)")):
        c = _close(hist, t)
        if c is not None and len(c) > 60:
            tech[t] = _dd(c)
    if tech:
        dd = float(np.mean(list(tech.values())))
        parts.append(("tech", "Tech/KI vom Hoch", f"{dd * 100:.0f} %", _lin(-dd, 0.02, 0.20)))
    if br:
        parts.append(("breadth", "Aktien über EMA 50", f"{br['above50'] * 100:.0f} %", _lin(-br["above50"], -0.70, -0.25)))
        parts.append(("lows", "an 52-Wochen-Tief", f"{br['lows'] * 100:.1f} %", _lin(br["lows"], 0.0, 0.08)))
    hyg, ief = _close(hist, "HYG"), _close(hist, "IEF")
    if hyg is not None and ief is not None:
        q = (hyg / ief.reindex(hyg.index).ffill()).dropna()
        if len(q) > 55:
            gap = float(q.iloc[-1] / q.iloc[-50:].mean() - 1)
            parts.append(("credit", "Kreditmarkt", f"{gap * 100:+.1f} %", _lin(-gap, 0.0, 0.03)))
    if len(parts) < 3:
        return None
    score = round(float(np.mean([p[3] for p in parts])))
    lvl = next(x for x in LEVELS if score >= x[0])
    return {"score": score, "label": lvl[1], "tone": lvl[2],
            "parts": [{"k": k, "l": l, "v": v, "s": round(s)} for k, l, v, s in parts],
            "tech": {k: round(v, 4) for k, v in tech.items()}, "breadth": br}
