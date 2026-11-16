"""Börsengänge (IPOs) für den Kalender – Wunsch 16.11.2026: „Anthropic kommt die Woche an die Börse und steht nicht drin“.

Quelle: öffentlicher IPO-Kalender von Nasdaq (api.nasdaq.com, kostenlos, ohne Schlüssel; deckt alle US-Börsen ab:
Nasdaq und NYSE). Dazu data/ipo_events.json von Hand für große, angekündigte Börsengänge, deren Termin noch offen ist
oder die der Kalender (noch) nicht führt – z. B. Europa.

Ausgabe je Termin: {"kind": "ipo", "date", "title", "name", "sym", "ex", "price", "val", "status", "region", "big"}
  status: "expected" (Preisfestsetzung erwartet), "priced" (Erstnotiz/gepreist), "filed" (nur Antrag, Termin offen)
  big:    Emissionsvolumen ≥ 500 Mio. $ oder von Hand als wichtig markiert – erscheint unter „Nur wichtige Termine“
"""
from __future__ import annotations

import json
import re
import urllib.request
from datetime import date, timedelta
from pathlib import Path

URL = "https://api.nasdaq.com/api/ipo/calendar?date={ym}"
HEAD = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Accept": "application/json, text/plain, */*", "Origin": "https://www.nasdaq.com", "Referer": "https://www.nasdaq.com/"}
BIG_USD = 500e6


def _num(x) -> float | None:
    """„$1,234,567“ / „18.00-20.00“ / „1,000“ → Zahl (bei Spannen der Mittelwert)."""
    if x is None:
        return None
    nums = [float(v.replace(",", "")) for v in re.findall(r"[\d][\d,]*\.?\d*", str(x))]
    return sum(nums) / len(nums) if nums else None


def _iso(x) -> str | None:
    """„11/20/2026“ oder „2026-11-20“ → „2026-11-20“."""
    s = str(x or "").strip()
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    return m.group(0) if m else None


def _ev(name, sym, d, ex, price, shares, val, status) -> dict | None:
    if not name or not d:
        return None
    v = _num(val)
    if v is None and _num(price) and _num(shares):
        v = _num(price) * _num(shares)
    ex = str(ex or "").replace("NASDAQ Global Select", "Nasdaq").replace("NASDAQ Global", "Nasdaq").replace("NASDAQ Capital", "Nasdaq")
    ex = "Nasdaq" if ex.upper().startswith("NASDAQ") else "NYSE" if ex.upper().startswith("NYSE") else ex
    name = re.sub(r"\s+", " ", str(name)).strip()
    return {"kind": "ipo", "date": d, "name": name, "sym": (sym or "").strip() or None, "ex": ex or None,
            "price": str(price).strip() if price not in (None, "") else None, "val": round(v) if v else None,
            "status": status, "region": "us", "big": bool(v and v >= BIG_USD),
            "title": f"Börsengang: {name}" + (f" ({sym.strip()})" if sym and sym.strip() else "")}


def parse_nasdaq(j: dict) -> list[dict]:
    """Antwort von api.nasdaq.com/api/ipo/calendar → Termine (erwartet, gepreist; Anträge nur mit großem Volumen)."""
    d = (j or {}).get("data") or {}
    rows = lambda k: ((d.get(k) or {}).get("upcomingTable") or {}).get("rows") if k == "upcoming" else (d.get(k) or {}).get("rows")
    out = []
    for r in rows("upcoming") or []:
        out.append(_ev(r.get("companyName"), r.get("proposedTickerSymbol"), _iso(r.get("expectedPriceDate")), r.get("proposedExchange"),
                       r.get("proposedSharePrice"), r.get("sharesOffered"), r.get("dollarValueOfSharesOffered"), "expected"))
    for r in rows("priced") or []:
        out.append(_ev(r.get("companyName"), r.get("proposedTickerSymbol"), _iso(r.get("pricedDate")), r.get("proposedExchange"),
                       r.get("proposedSharePrice"), r.get("sharesOffered"), r.get("dollarValueOfSharesOffered"), "priced"))
    return [e for e in out if e]


def _fetch(ym: str) -> dict | None:
    try:
        req = urllib.request.Request(URL.format(ym=ym), headers=HEAD)
        return json.loads(urllib.request.urlopen(req, timeout=25).read().decode("utf-8"))
    except Exception as exc:                       # Quelle aus → Kalender läuft ohne IPOs weiter
        print(f"IPO-Kalender {ym}: {exc}")
        return None


def manual(path: Path) -> list[dict]:
    """data/ipo_events.json: {"events": [{"name", "sym", "date" (oder null = Termin offen), "ex", "price", "note", "region", "big"}]}"""
    if not path.exists():
        return []
    try:
        l = json.load(open(path, encoding="utf-8")).get("events", [])
    except Exception:
        return []
    out = []
    for x in l:
        if not x.get("name"):
            continue
        e = {"kind": "ipo", "date": x.get("date"), "name": x["name"], "sym": x.get("sym"), "ex": x.get("ex"), "price": x.get("price"),
             "val": x.get("val"), "status": "expected" if x.get("date") else "open", "region": x.get("region", "us"),
             "big": x.get("big", True), "note": x.get("note"), "manual": True,
             "title": f"Börsengang: {x['name']}" + (f" ({x['sym']})" if x.get("sym") else "")}
        out.append(e)
    return out


def fetch_ipos(today: date | None = None, root: Path | None = None) -> list[dict]:
    """IPOs der letzten 2 Wochen bis 6 Wochen voraus. Erste Angabe je Firma gewinnt: Nasdaq (genau) vor Handeintrag."""
    today = today or date.today()
    months = sorted({(today + timedelta(days=k)).strftime("%Y-%m") for k in (-14, 0, 31, 42)})
    events: list[dict] = []
    for ym in months:
        events += parse_nasdaq(_fetch(ym) or {})
    if root is not None:
        events += manual(root / "data" / "ipo_events.json")
    lo, hi = (today - timedelta(days=14)).isoformat(), (today + timedelta(days=42)).isoformat()
    seen, out = set(), []
    for e in events:
        if e.get("date") and not lo <= e["date"] <= hi:
            continue
        k = re.sub(r"[^a-z0-9]", "", e["name"].lower().replace(" inc", "").replace(" corp", "").replace(" ltd", "").replace("pbc", ""))[:14]
        if k in seen:
            continue
        seen.add(k)
        out.append(e)
    return out
