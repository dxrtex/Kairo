"""S01 – Kairo-Treffer (11/11, unveränderter Scanner) mit Basis-Einstieg wie QRULE.

Signal: `backend.scanner.evaluate` auf auto_adjust-Kursen (Faktor AdjClose/Close), Fenster = letzte 504 Kerzen
(≈ 2 Jahre wie der Produktiv-Scan), `passed` = alle Pflichtkriterien inkl. Grundfilter. Neue Signal-Phase erst nach
> 5 Tagen ohne Treffer (wie bilanz.scan_history, GAP = 5).

Einstieg (QRULE, shortswing.simulate entry="base"): Invalidierung = tiefstes Tief der 10 Kerzen bis zum Signaltag.
Nach dem Signal höchstens 10 Kerzen warten; Tief unter der Invalidierung → Signal gescheitert. Sobald die letzten 5
Kerzen nach dem Signal eng laufen (Hoch − Tief ≤ 1,5 × ATR14 des Signaltags), Kauf zur nächsten Eröffnung – nur wenn
diese in (Tief, Hoch] der Basis liegt; Stop = Basis-Tief − 0,25 × ATR; Risiko 0,5–3 ATR, sonst verworfen.
Ausstieg A: Zeit 20 Tage (Schluss Tag 20). B: ab Tag 10 Schluss < EMA20 → nächste Eröffnung, spätestens Tag 40.

Alle Schwellen in Kurs-Einheiten werden mit dem Faktor des Entscheidungstags in unbereinigte Kurse umgerechnet.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backend.indicators import atr as _atr, ema as _ema
from backend.scanner import FX_USD, evaluate

from .data import adjusted
from .engine import Order

WINDOW, GAP, WAIT, CK, CM, BUF, RISK = 504, 5, 10, 5, 1.5, 0.25, (0.5, 3.0)


def eligible(adj: pd.DataFrame, cur: str) -> np.ndarray:
    """Grundfilter des Scanners (Liquidität, Kurs, Historie) je Tag – exakt dieselben Formeln, als billiger Vorfilter.
    Marktkapitalisierung: im Backtest unbekannt → zählt als erfüllt (wie im Scanner bei fehlendem Wert)."""
    c, v = adj["Close"].to_numpy(float), adj["Volume"].fillna(0).to_numpy(float)
    dv = pd.Series(v * c).rolling(20, min_periods=1).mean().to_numpy() * FX_USD.get(cur, 1.0)
    bars = np.minimum(np.arange(len(c)) + 1, WINDOW)
    return (dv >= 5e6) & (c >= 1.0) & (bars >= 300)


def signals(raw: pd.DataFrame, cur: str, start: pd.Timestamp, end: pd.Timestamp, ticker: str = "") -> list[dict]:
    """Frische Treffer-Tage im Zeitraum [start, end] (Kurse danach dürfen nicht übergeben werden)."""
    raw = raw.dropna(subset=["Open", "High", "Low", "Close", "AdjClose"])
    raw = raw[raw["Close"] > 0]
    adj = adjusted(raw)
    ok = eligible(adj, cur)
    idx = adj.index
    first = int(np.searchsorted(idx.values, np.datetime64(start - pd.Timedelta(days=14))))
    out, last = [], -99
    for i in range(first, len(adj)):
        if not ok[i]:
            continue
        try:
            r = evaluate(adj.iloc[max(0, i - WINDOW + 1): i + 1], {"currency": cur}, ticker=ticker)
        except Exception:
            continue
        if not r.passed:
            continue
        fresh, last = i - last > GAP, i
        if fresh and idx[i] >= start and idx[i] <= end:
            fz = (r.zone or {}).get("fib") or {}
            lv = fz.get("levels") or {}
            out.append({"ticker": ticker, "date": idx[i], "i": i, "atr": float(r.flags.get("atr") or np.nan),
                        "close": float(r.close), "score": int(r.score),
                        "fib_ok": bool(fz.get("ok")), "fib_ret": float(fz.get("retracement", np.nan)),
                        "fib_H": float((r.zone or {}).get("H") or np.nan), "fib_L": float(fz.get("L", np.nan)),
                        "fib_079": float(lv.get("0.79", np.nan)), "support_ok": bool((r.zone or {}).get("support"))})
    return out


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    raw = raw.dropna(subset=["Open", "High", "Low", "Close", "AdjClose"])
    return raw[raw["Close"] > 0]


def base_orders(raw: pd.DataFrame, sig_i: int, atr_adj: float, ticker: str, gid: str, variant: str = "A",
                risk_frac: float = 0.01, prio: float = 0.0, adj: pd.DataFrame | None = None) -> list[Order]:
    """Bedingte Orders für die Basis-Tage nach einem Signal (je Tag nur mit Kursen bis zu diesem Tag).
    `adj` = adjusted(clean(raw)) vorberechnet (schneller bei vielen Signalen)."""
    if adj is None:
        adj = adjusted(clean(raw))
    lo_, hi_, f = adj["Low"].to_numpy(float), adj["High"].to_numpy(float), adj["f"].to_numpy(float)
    if not (atr_adj > 0):
        return []
    inv = lo_[max(0, sig_i - 9): sig_i + 1].min()
    orders = []
    for j in range(WAIT):
        k = sig_i + 1 + j
        if k >= len(adj) - 1:
            break
        if lo_[k] < inv:
            break                                   # Signal gescheitert
        if j < CK - 1:
            continue
        hi, lo = hi_[k - CK + 1: k + 1].max(), lo_[k - CK + 1: k + 1].min()
        if hi - lo > CM * atr_adj:
            continue
        fk = f[k]
        kw = dict(max_days=20) if variant == "A" else dict(max_days=40, exit_rule=("ema", 10))
        orders.append(Order(adj.index[k], ticker, stop=(lo - BUF * atr_adj) / fk, risk_frac=risk_frac, prio=prio,
                            tag=f"S01-{variant}", entry_band=(lo / fk, hi / fk), atr=atr_adj / fk, risk_atr=RISK,
                            group=gid, **kw))
    return orders


def with_ema(raw: pd.DataFrame) -> pd.DataFrame:
    """Kursrahmen für die Engine (unbereinigt) + EMA20 der bereinigten Schlusskurse in unbereinigte Einheiten."""
    raw = raw.dropna(subset=["Open", "High", "Low", "Close", "AdjClose"])
    raw = raw[raw["Close"] > 0].copy()
    adj = adjusted(raw)
    raw["EMA"] = _ema(adj["Close"], 20) / adj["f"]
    return raw


def atr14(raw: pd.DataFrame) -> pd.Series:
    raw = raw.dropna(subset=["Open", "High", "Low", "Close", "AdjClose"])
    return _atr(adjusted(raw[raw["Close"] > 0]), 14)
