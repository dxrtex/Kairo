"""Tägliche Käufe und Verkäufe der ARK-Fonds (Cathie Wood) – aus den Bestandslisten, die ARK jeden Handelstag veröffentlicht.

Anders als 13F (bis zu 45 Tage alt) zeigt das, was ein bekannter Fonds GESTERN gekauft oder verkauft hat. Kairo vergleicht die
Liste von heute mit der gespeicherten von gestern (Zustand ark_prev.json) und sammelt die Bewegungen 30 Tage (ark_hist.json).
Kleine Änderungen unter 2 % der Position (Zu-/Abflüsse im ETF) gelten nicht als Kauf/Verkauf. Nur Information.
"""
from __future__ import annotations

import csv
import io
import re
from datetime import date, timedelta

import requests

BASE = "https://assets.ark-funds.com/fund-documents/funds-etf-csv/"
FUNDS = {"ARKK": "ARK_INNOVATION_ETF_ARKK_HOLDINGS.csv", "ARKW": "ARK_NEXT_GENERATION_INTERNET_ETF_ARKW_HOLDINGS.csv",
         "ARKG": "ARK_GENOMIC_REVOLUTION_ETF_ARKG_HOLDINGS.csv", "ARKQ": "ARK_AUTONOMOUS_TECH._&_ROBOTICS_ETF_ARKQ_HOLDINGS.csv",
         "ARKF": "ARK_FINTECH_INNOVATION_ETF_ARKF_HOLDINGS.csv", "ARKX": "ARK_SPACE_EXPLORATION_&_INNOVATION_ETF_ARKX_HOLDINGS.csv"}
MIN_CHG = .02


def _num(x: str) -> float:
    try:
        return float(re.sub(r"[^0-9.\-]", "", x or "") or 0)
    except ValueError:
        return 0.0


def parse(text: str) -> tuple[str, dict[str, dict]]:
    """CSV → (Datum, {Kürzel: {n, sh, w}}). Zeilen ohne Kürzel (Bargeld, Fußnoten) fallen weg."""
    rows = list(csv.DictReader(io.StringIO(text or "")))
    out, d = {}, ""
    for r in rows:
        r = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
        t = (r.get("ticker") or "").split()[0].upper() if r.get("ticker") else ""
        if not t or not re.fullmatch(r"[A-Z0-9.\-]{1,10}", t):
            continue
        dd = r.get("date") or ""
        m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", dd)
        d = d or (f"{m[3]}-{int(m[1]):02d}-{int(m[2]):02d}" if m else dd[:10])
        out[t] = {"n": r.get("company") or t, "sh": _num(r.get("shares")), "w": _num(r.get("weight (%)") or r.get("weight(%)") or r.get("weight"))}
    return d, out


def diff(fund: str, d: str, new: dict, old: dict) -> list[dict]:
    """Bewegungen eines Fonds zwischen zwei Tagen: neu, aufgestockt, reduziert, komplett verkauft."""
    out = []
    for t in set(new) | set(old):
        a, b = old.get(t), new.get(t)
        if a and b:
            if not a["sh"]:
                continue
            ch = b["sh"] / a["sh"] - 1
            if abs(ch) < MIN_CHG:
                continue
            out.append({"f": fund, "t": t, "n": b["n"], "d": d, "a": "auf" if ch > 0 else "ab", "chg": round(ch, 3), "sh": round(b["sh"] - a["sh"]), "w": b["w"]})
        elif b:
            out.append({"f": fund, "t": t, "n": b["n"], "d": d, "a": "neu", "chg": None, "sh": round(b["sh"]), "w": b["w"]})
        else:
            out.append({"f": fund, "t": t, "n": a["n"], "d": d, "a": "raus", "chg": -1, "sh": -round(a["sh"]), "w": 0})
    return out


def update(prev: dict, hist: list[dict], fetch=None, days: int = 30, today: str | None = None) -> tuple[dict, list[dict]]:
    """prev = {Fonds: {d, h}} (Stand des letzten Laufs). Gibt neuen Stand und gesammelte Bewegungen (neueste zuerst) zurück."""
    get = fetch or (lambda f: requests.get(BASE + FUNDS[f], headers={"User-Agent": "Mozilla/5.0 (Kairo Scanner)"}, timeout=25).text)
    moves, state = [], dict(prev)
    for f in FUNDS:
        try:
            d, h = parse(get(f))
        except Exception as exc:
            print(f"ARK {f}: nicht geladen {exc!r}"[:120])
            continue
        if not h or not d:
            continue
        p = prev.get(f) or {}
        if p.get("d") and p.get("d") < d:
            moves += diff(f, d, h, p.get("h") or {})
        if not p.get("d") or p.get("d") <= d:
            state[f] = {"d": d, "h": h}
    since = ((date.fromisoformat(today) if today else date.today()) - timedelta(days=days)).isoformat()
    seen, out = set(), []
    for x in [*moves, *hist]:
        k = (x["f"], x["t"], x["d"])
        if k in seen or x["d"] < since:
            continue
        seen.add(k)
        out.append(x)
    print(f"ARK: {len(moves)} neue Bewegungen, {len(out)} in {days} Tagen")
    return state, sorted(out, key=lambda x: (x["d"], abs(x["sh"])), reverse=True)
