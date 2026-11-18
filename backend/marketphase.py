"""Marktphase für Swing-Trader (18.11.2026): mittelfristig aus Wochenkursen, springt nicht täglich um.

Die bisherige Tageslage (S&P 500 über EMA 50 und VIX < 20) wechselt schon, wenn der VIX um 20 pendelt. Für Trades über
Tage bis Wochen zählt die Phase dahinter: Aufwärtstrend, Seitwärts, Korrektur oder Abwärtstrend. Klassische Bausteine:
  · Wochenschluss gegen den 40-Wochen-Schnitt (≈ 200-Tage-Linie) und 10- gegen 40-Wochen-Schnitt
  · Abstand zum 52-Wochen-Hoch (−10 % Korrektur, −20 % Bärenmarkt)
  · VIX im 4-Wochen-Schnitt (nur USA)
Eine neue Phase gilt erst, wenn sie zwei Wochen in Folge vorliegt (Ausnahme: −20 % sofort) – so bleibt die Ampel ruhig.
Reine Anzeige: Die Kairo-Regel nutzt die Phase nicht.
"""
from __future__ import annotations

import pandas as pd

PH = {"bull": ("Aufwärtstrend", "green"), "neutral": ("Seitwärts", "yellow"), "corr": ("Korrektur", "orange"), "bear": ("Abwärtstrend", "red")}


def _weekly(s: pd.Series) -> pd.Series:
    s = s.dropna()
    return s.resample("W-FRI").last().dropna()


def market_phase(df: pd.DataFrame | None, vix: pd.DataFrame | None = None, keep: int = 52, confirm_n: int = 2) -> dict | None:
    """Tageskurse eines Index (Spalte Close) → {k, label, tone, since, weeks, why, hist: [[wochenende, k], …]}."""
    if df is None or "Close" not in df or len(df) < 230:
        return None
    w = _weekly(df["Close"])
    if len(w) < 46:
        return None
    s10, s40 = w.rolling(10).mean(), w.rolling(40).mean()
    hi52 = w.rolling(52, min_periods=40).max()
    dd = w / hi52 - 1
    v4 = None
    if vix is not None and "Close" in vix and len(vix) > 30:
        v4 = _weekly(vix["Close"]).rolling(4).mean().reindex(w.index, method="ffill")
    raw = []
    for i in range(len(w)):
        if pd.isna(s40.iloc[i]) or pd.isna(dd.iloc[i]):
            raw.append(None)
            continue
        c, a, b, d = float(w.iloc[i]), float(s10.iloc[i]), float(s40.iloc[i]), float(dd.iloc[i])
        b4 = float(s40.iloc[i - 4]) if i >= 4 and not pd.isna(s40.iloc[i - 4]) else b
        vx = float(v4.iloc[i]) if v4 is not None and not pd.isna(v4.iloc[i]) else None
        if d <= -0.20 or (c < b and a < b and b < b4):
            raw.append("bear")
        elif d <= -0.10 or c < b:
            raw.append("corr")
        elif c > b and a > b and d > -0.08 and (vx is None or vx < 24):
            raw.append("bull")
        else:
            raw.append("neutral")
    state, since, hist = None, None, []
    for i, r in enumerate(raw):
        if r is None:
            continue
        if state is None:
            state, since = r, i
        elif r != state:
            confirm = confirm_n <= 1 or (i >= 1 and raw[i - 1] == r) or (r == "bear" and float(dd.iloc[i]) <= -0.20)
            if confirm:
                state, since = r, (i - 1 if raw[i - 1] == r else i)
        hist.append([w.index[i].strftime("%Y-%m-%d"), state])
    if state is None:
        return None
    c, a, b, d = float(w.iloc[-1]), float(s10.iloc[-1]), float(s40.iloc[-1]), float(dd.iloc[-1])
    why = [f"{'über' if c >= b else 'unter'} dem 40-Wochen-Schnitt (≈ 200-Tage-Linie, {(c / b - 1) * 100:+.1f} %)".replace(".", ","),
           f"10-Wochen-Schnitt {'über' if a >= b else 'unter'} dem 40-Wochen-Schnitt",
           (f"{abs(d) * 100:.1f} % unter dem 52-Wochen-Hoch" if d < -0.005 else "nahe am 52-Wochen-Hoch").replace(".", ",")]
    if v4 is not None and not pd.isna(v4.iloc[-1]):
        why.append(f"VIX im 4-Wochen-Schnitt {float(v4.iloc[-1]):.0f}")
    label, tone = PH[state]
    return {"k": state, "label": label, "tone": tone, "since": w.index[since].strftime("%Y-%m-%d"), "weeks": len(w) - since,
            "why": why, "dd": round(d, 4), "hist": hist[-keep:]}
