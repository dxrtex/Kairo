"""Kairo Short (23.11.2026): dieselbe getestete Kairo-Logik – gespiegelt für fallende Kurse.

Idee: Ein Short-Setup ist das Spiegelbild eines Long-Setups. Statt eine zweite, ungetestete Regel zu schreiben, wird der
Kursverlauf gespiegelt (Kurs → K / Kurs, Hoch ↔ Tief) und die UNVERÄNDERTE Kairo-Prüfung (backend/scanner.evaluate)
darauf angewendet. Aus „Rücksetzer ≥ 12 % an eine Unterstützung, bullische RSI-Divergenz, MACD dreht unter 0, grünes MBI-X“
wird so „Anstieg ≥ 12 % an einen Widerstand, bärische RSI-Divergenz, MACD dreht über 0, rotes MBI-X“ – 11 Kriterien,
genau wie bei Long. K = letzter Schlusskurs², damit der heutige Kurs gleich bleibt (Kurs-, Liquiditäts-Grenzen stimmen).
Grenzen der Spiegelung: RSI/MACD auf K/Kurs entsprechen fast (nicht exakt) 100 − RSI bzw. −MACD des Originals.
Die Long-Regel bleibt unberührt. Reine Analyse/Anzeige – keine Orders.
"""
from __future__ import annotations

import pandas as pd

# Bezeichnungen der 11 Setup-Kriterien für die Short-Seite (Schlüssel wie bei Long)
LABELS = {
    "drawdown": "Anstieg vom Swing-Tief (20–180 T.) ≥ 12 %",
    "no_crash": "Rally statt Kurssprung (max. Tagesgewinn 10 T.)",
    "structure": "Über EMA 20 & 50, EMA 20 steigt",
    "zone": "Widerstandszone (Fib 0,618–0,79 des Abwärtsimpulses oder Mehrfach-Hoch)",
    "flattening": "Abflachung der letzten 10 Kerzen (oder obere Lunten im Widerstand)",
    "rsi_div": "RSI bärische Divergenz (klassisch/versteckt)",
    "rsi_range": "RSI aktuell ≈ 52–72",
    "macd_below0": "MACD-Linie und Signal über 0",
    "macd_turn": "MACD dreht nach unten (Kreuz ≤ 7 T. oder Histogramm fällt Richtung 0)",
    "mbi": "MBI: rotes X auf grüner Spitze, Kaufdruck läuft aus",
    "crv": "Chance-Risiko (Ziel 2 / Stop) ≥ 2,0",
}
UNIVERSE = ("cap", "liquidity", "price", "history")


def invert(df: pd.DataFrame) -> pd.DataFrame:
    """OHLC spiegeln: K / Kurs, Hoch und Tief tauschen. Volumen bleibt."""
    d = df.dropna(subset=["Open", "High", "Low", "Close"])
    k = float(d["Close"].iloc[-1]) ** 2
    out = pd.DataFrame(index=d.index)
    out["Open"] = k / d["Open"]
    out["High"] = k / d["Low"]
    out["Low"] = k / d["High"]
    out["Close"] = k / d["Close"]
    out["Volume"] = d["Volume"]
    for c in d.columns:
        if c not in out:
            out[c] = d[c]
    return out


def evaluate_short(df: pd.DataFrame, info: dict | None = None, ticker: str = ""):
    """Kairo-Prüfung auf dem gespiegelten Kursverlauf → (Result, Plan in Originalkursen)."""
    from .scanner import evaluate
    d = df.dropna(subset=["Open", "High", "Low", "Close"])
    k = float(d["Close"].iloc[-1]) ** 2
    res = evaluate(invert(d), info, ticker=ticker)
    back = lambda x: (k / x) if x else None
    p = res.plan or {}
    plan = {}
    if p:
        plan = {"entry": back(p.get("entry")), "stop": back(p.get("stop")), "target1": back(p.get("target1")),
                "target2": back(p.get("target2")), "crv": p.get("crv"), "stop_pct": p.get("stop_pct"),
                "sell_stop": back(p.get("buy_stop"))}
    return res, plan


def compact(res, plan: dict) -> dict:
    """Kurzform für die App: Status, erfüllte Setup-Kriterien (von 11), fehlende Kriterien, Plan."""
    setup = [c for c in res.criteria if c.key not in UNIVERSE]
    met = sum(1 for c in setup if c.ok)
    uni_ok = all(c.ok for c in res.criteria if c.key in UNIVERSE)
    st = "hit" if res.passed else "fast" if res.fast_hit else "near" if res.near_hit else ""
    r6 = lambda x: None if x is None else round(float(x), 6)
    return {"s": st, "met": met, "of": len(setup), "uni": uni_ok,
            "miss": [c.key for c in setup if not c.ok],
            "pl": {k: r6(v) for k, v in plan.items() if v is not None} if plan else None}


def _val(c, f: dict) -> str:
    """Kurzer Wert in ORIGINALKURSEN (die Texte der Long-Prüfung nennen Kurse des gespiegelten Verlaufs)."""
    try:
        if c.key == "drawdown" and f.get("raw_dd") is not None:
            return f"+{(1 / (1 - f['raw_dd']) - 1) * 100:.1f} % vom Swing-Tief".replace(".", ",")
        if c.key == "no_crash" and f.get("raw_worst") is not None:
            return f"größter Tagesgewinn +{(1 / (1 + f['raw_worst']) - 1) * 100:.1f} %".replace(".", ",")
        if c.key == "rsi_range" and f.get("rsi") is not None:
            return f"RSI {100 - float(f['rsi']):.1f}".replace(".", ",")
        if c.key in ("rsi_div", "macd_turn", "mbi", "flattening", "zone", "structure", "macd_below0"):
            return "erfüllt" if c.ok else "nicht erfüllt"
        if c.key == "crv":
            return c.value
    except Exception:
        pass
    return "erfüllt" if c.ok else "nicht erfüllt"


def detail(res, plan: dict) -> dict:
    """Kriterienliste für die Detailkarte (Short-Seite)."""
    out = compact(res, plan)
    out["crit"] = [[c.key, LABELS.get(c.key, c.label), bool(c.ok), _val(c, res.flags)] for c in res.criteria if c.key not in UNIVERSE]
    return out
