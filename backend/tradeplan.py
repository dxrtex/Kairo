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


def structure(df: pd.DataFrame, atr: float | None) -> dict:
    """Basis, Tiefs, Stop-Vorschlag und Widerstände. Leeres Dict, wenn zu wenig Daten."""
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
    return out
