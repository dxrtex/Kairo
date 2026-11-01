"""Lern-Grundlage: unveränderliche Momentaufnahme jedes NEUEN Kairo-Signals (Point-in-Time).

Warum: Gewinner und Verlierer lassen sich später nur fair vergleichen, wenn die Werte vom SIGNALTAG stammen – nicht von
heute. Darum hält dieser Schritt beim ersten Erkennen eines Signals fest, was der Scanner in diesem Moment sah:
- alle 11 Pflichtkriterien (erfüllt? Wert, Schwelle), RSI, MACD-, MBI-Stand, ATR, Volatilität, Score
- Plan: Einstieg, Stop, Stop-Abstand in % und in ATR; Vormomentum (Rendite Monat −6…−1, wie die Depot-Rangfolge)
- Marktlage (Regime, Stimmung), Region, Sektor
- Versionen: Regel (B60), Aufbau dieser Datei (SCHEMA), Programmstand (Commit), Zeitpunkt des Scans
- Signaltag ≠ Kauftag: „d“ ist der Signaltag (letzte Tageskerze), der Kauf (Seitwärtsphase) folgt später und wird getrennt
  unter „buy“ nachgetragen, das Ergebnis unter „exit“. Der Block „sig“ wird danach NIE wieder verändert.
- Spät erkannt: Fällt der Scan aus und sieht ein Signal erst Tage später, steht das in „late“ (Handelstage zwischen
  Signaltag und Scan). Alte Signale werden nie mit heutigen Werten nachgefüllt – ohne Momentaufnahme bleibt es ohne.

Datei: state/snapshots.json (Branch des Zustands), Schlüssel „Ticker|Art|Signaltag“. Nur Abendscans schreiben neue Einträge.
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .config import ROOT
from .rule import KAIRO

SCHEMA = 1
FILE = "snapshots.json"
FLAG_KEYS = ("atr", "atr_pct", "volatility", "rsi", "macd_hist", "macd_cross_age", "macd_cross_done", "mbi_green",
             "raw_mbi_age", "raw_mbi_ref", "raw_mbi_fade", "market_cap_usd", "earnings_risk")


def _num(v):
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, float, np.integer, np.floating)):
        f = float(v)
        return round(f, 6) if f == f else None
    return v


def versions() -> dict:
    """Stand von Regel, Datei-Aufbau, Konfiguration und Programm – damit spätere Auswertungen je Stand getrennt bleiben."""
    try:
        cfg = hashlib.sha1((ROOT / "config.yaml").read_bytes()).hexdigest()[:10]
    except Exception:
        cfg = None
    return {"rule": KAIRO["version"], "schema": SCHEMA, "config": cfg, "code": (os.environ.get("GITHUB_SHA") or "")[:10] or None}


def momentum(df: pd.DataFrame | None, d: str) -> float | None:
    """Vormomentum am Signaltag: Schluss vor 21 Handelstagen / Schluss vor 126 Handelstagen − 1 (wie paper/kairo.py)."""
    if df is None or df.empty:
        return None
    c = df["Close"].dropna()
    i = int(c.index.searchsorted(pd.Timestamp(d), side="right") - 1)
    if i < 126:
        return None
    return round(float(c.iloc[i - 21] / c.iloc[i - 126] - 1), 4)


def _bdays(a: str, b: str) -> int:
    try:
        return max(0, int(np.busday_count(pd.Timestamp(a).date(), pd.Timestamp(b).date())))
    except Exception:
        return 0


def take(s: dict, r: dict, df: pd.DataFrame | None, market: dict | None, today: str, now: datetime | None = None) -> dict:
    """Momentaufnahme eines neuen Signals s (aus live.update) mit der Scan-Zeile r. Reine Funktion – schreibt nichts."""
    now = now or datetime.now(timezone.utc)
    fl = r.get("flags") or {}
    entry, stop = s.get("entry"), s.get("stop")
    atr = fl.get("atr")
    crit = {c.get("key") or c.get("k"): {"ok": bool(c.get("ok")), "v": c.get("value", c.get("v")), "th": c.get("threshold", c.get("th"))}
            for c in (r.get("criteria") or [])}
    reg = (market or {}).get("regime") or {}
    fear = (market or {}).get("fear") or {}
    sig = {
        "crit": crit, "met": r.get("met"), "total": r.get("total"), "score": r.get("score"), "close": _num(r.get("close")),
        "rsi": _num(r.get("rsi")), "macd": r.get("macd_status"), "mbi": r.get("mbi_status"), "div": r.get("divergence"),
        "flags": {k: _num(fl[k]) for k in FLAG_KEYS if k in fl},
        "entry": _num(entry), "stop": _num(stop),
        "stop_pct": round((entry - stop) / entry, 4) if entry and stop else None,
        "stop_atr": round((entry - stop) / atr, 3) if entry and stop and atr else None,
        "mom": momentum(df, s["d"]),
        "market": {"regime": reg.get("label"), "tone": reg.get("tone"), "fear": _num(fear.get("score"))},
        "region": r.get("region"), "sector": r.get("sector"), "grade": s.get("grade"),
        "earn": (r.get("earnings_date") or fl.get("earnings_date") or None),   # nächster Quartalszahlen-Termin am Signaltag
    }
    return {"t": s["t"], "k": s["k"], "d": s["d"], "scan": today, "at": now.isoformat(timespec="seconds"),
            "late": _bdays(s["d"], today), "ver": versions(), "sig": sig}


def add(snaps: dict, new: list[dict], rows_by_t: dict, data: dict, market: dict | None, today: str, now=None) -> int:
    """Neue Signale aufnehmen – vorhandene Einträge bleiben unangetastet (wiederholte Scans, Doppel-Läufe)."""
    n = 0
    for s in new:
        key = f"{s['t']}|{s['k']}|{s['d']}"
        r = rows_by_t.get(s["t"])
        if key in snaps or r is None:
            continue
        try:
            snaps[key] = take(s, r, data.get(s["t"]), market, today, now)
            n += 1
        except Exception as exc:                     # die Momentaufnahme darf den Scan nie stoppen
            print("Momentaufnahme:", key, repr(exc)[:120])
    return n


def track(snaps: dict, sig: list[dict], today: str) -> None:
    """Kauf und Ergebnis nach Regel B60 (st60 aus live.py) nachtragen – nur „buy“/„exit“, nie den Block „sig“."""
    by = {f"{s['t']}|{s['k']}|{s['d']}": s for s in sig}
    for key, sn in snaps.items():
        s = by.get(key)
        st = (s or {}).get("st60") or {}
        res = st.get("res")
        if not res or res == "wait":
            continue
        if res == "nobase":
            sn.setdefault("exit", {"res": "nobase", "seen": today, "why": st.get("why")})
            continue
        if "buy" not in sn and st.get("e") is not None:
            sn["buy"] = {"e": st["e"], "sl": st.get("sl"), "seen": today}
        if res in ("stop", "zeit", "ema") and "exit" not in sn:
            sn["exit"] = {"res": res, "r": st.get("r"), "days": st.get("days"), "seen": today}


def table(snaps: dict) -> pd.DataFrame:
    """Flache Tabelle für die Gewinner-/Verlierer-Auswertung: eine Zeile je abgeschlossenem Treffer mit R."""
    out = []
    for key, sn in snaps.items():
        x = sn.get("exit") or {}
        if sn.get("k") != "hit" or x.get("r") is None:
            continue
        g = sn["sig"]
        row = {"key": key, "d": sn["d"], "late": sn.get("late"), "rule": sn["ver"]["rule"], "r": x["r"], "win": x["r"] > 0,
               "rsi": g.get("rsi"), "mom": g.get("mom"), "stop_pct": g.get("stop_pct"), "stop_atr": g.get("stop_atr"),
               "score": g.get("score"), "regime": g["market"].get("tone"), "region": g.get("region")}
        row.update({f"f_{k}": v for k, v in g.get("flags", {}).items() if isinstance(v, (int, float))})
        out.append(row)
    return pd.DataFrame(out)


def compare(snaps: dict, min_n: int = 30) -> dict | None:
    """Gewinner gegen Verlierer: Median je Merkmal. Erst ab min_n abgeschlossenen Treffern – sonst keine Aussage."""
    t = table(snaps)
    if len(t) < min_n:
        return {"n": len(t), "need": min_n}
    num = [c for c in t.columns if c not in ("key", "d", "rule", "win", "regime", "region") and pd.api.types.is_numeric_dtype(t[c])]
    return {"n": len(t), "win_rate": round(float(t["win"].mean()), 3),
            "median": {c: {"win": _num(t.loc[t.win, c].median()), "loss": _num(t.loc[~t.win, c].median())} for c in num if c != "r"}}
