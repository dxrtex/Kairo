"""Trade-Plan-Struktur je Aktie (für den Reiter „Einstieg“): Basis, Invalidierung, Stop, Widerstände.

Regeln aus der Kurzfrist-Studie (backend/shortswing.py, 5 Jahre, 1.600 Aktien, netto):
- Kairo-Reversals: am besten IN einer engen Seitwärtsphase (Basis) kaufen, nicht sofort beim Signal.
  Basis = die letzten 5 (ersatzweise 3) Handelstage liegen in einer Spanne von höchstens 1,5 (ersatzweise 2,5) ATR.
- Stop = Tief der Basis − 0,25 ATR. Ohne Basis: Tief der letzten 10 Tage − 0,25 ATR (vorläufig, „keine Basis“).
- Ein Stop mehr als 3 ATR unter dem Einstieg passt nicht zur Strategie (Trade ablehnen bzw. auf Basis warten);
  weniger als 0,5 ATR ist so eng, dass normales Rauschen ihn auslöst.
Die Positionsgröße, Hebel/K.-o. und Kosten rechnet die App auf dem Gerät (Depotwert, Risiko, eigener Kaufkurs).
Nur Kurse bis zum letzten Handelstag – nichts aus der Zukunft.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

BASES = ((5, 1.5), (5, 2.5), (3, 1.5), (3, 2.5))     # (Tage, max. Spanne in ATR) – strengste zuerst
STOP_BUF = 0.25                                      # ATR unter der Invalidierung
MAX_STOP_ATR, MIN_STOP_ATR = 3.0, 0.5


def structure(df: pd.DataFrame, atr: float | None, fib: dict | None = None) -> dict:
    """Basis, Tiefs, Stop-Vorschlag, Widerstände und nahe Kursmarken. Leeres Dict, wenn zu wenig Daten.

    fib: Fibonacci-Niveaus der Kairo-Zone ({"0.618": Kurs, …}), falls vorhanden.
    """
    d = df.dropna(subset=["High", "Low", "Close"])
    if len(d) < 12 or not atr or atr <= 0:
        return {}
    h, l, c = (d[k].to_numpy(float) for k in ("High", "Low", "Close"))
    r4 = lambda x: round(float(x), 4)
    base = None
    for k, m in BASES:
        lo, hi = float(l[-k:].min()), float(h[-k:].max())
        if hi - lo <= m * atr:
            base = {"k": k, "lo": r4(lo), "hi": r4(hi), "m": m, "w": round((hi - lo) / atr, 2)}
            break
    l10 = float(l[-10:].min())
    inv, src = (base["lo"], f"Tief der {base['k']}-Tage-Basis") if base else (l10, "Tief der letzten 10 Tage (keine Basis)")
    stop = inv - STOP_BUF * atr
    out = {"base": base, "l3": r4(l[-3:].min()), "l10": r4(l10), "h10": r4(h[-10:].max()), "inv": r4(inv), "src": src,
           "stop": r4(stop), "atr": r4(atr), "sd": round((float(c[-1]) - stop) / atr, 2)}
    try:
        from .analysis import swing_levels
        lv = swing_levels(d, float(c[-1]), atr)
        out["res"] = [r4(z["p"]) for z in lv[:3]]
    except Exception:
        out["res"] = []
    out["tg"] = marks(d, atr, base, fib)
    return out


def marks(d: pd.DataFrame, atr: float, base: dict | None, fib: dict | None) -> list:
    """Nahe Kursmarken über dem Schluss (Orientierung, keine festen Ziele): Basis-Hoch, 10-Tage-Hoch, EMA 20/50, Fibonacci.

    Höchstens 4, aufsteigend; Marken näher als 0,3 ATR beieinander werden zusammengefasst.
    """
    c = d["Close"].astype(float)
    last = float(c.iloc[-1])
    cand = []
    if base:
        cand.append(("Basis-Hoch", base["hi"]))
    cand.append(("10-Tage-Hoch", float(d["High"].astype(float).iloc[-10:].max())))
    for n in (20, 50):
        cand.append((f"EMA {n}", float(c.ewm(span=n, adjust=False).mean().iloc[-1])))
    for k, v in (fib or {}).items():
        if k not in ("0", "1") and v:
            cand.append((f"Fib {str(k).replace('.', ',')}", float(v)))
    cand = sorted((x for x in cand if x[1] > last + 0.1 * atr), key=lambda x: x[1])
    out = []
    for lb, v in cand:
        if out and v - out[-1][1] < 0.3 * atr:
            out[-1][0] += " / " + lb
            continue
        out.append([lb, round(v, 4)])
    return out[:4]
