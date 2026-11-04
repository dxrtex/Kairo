"""Einmal-Nachladen: Sektor, Branche und Firmensitz (Yahoo) für alle Aktien ohne Branche bzw. US-Notierungen ohne Sitz.

Die Branche (→ Branchen-ETF, Sektor-Ansicht „Branchen“) kommt sonst nur nach und nach über den Stimmungs-Cache
(höchstens 300 Abfragen je Abendscan). Dieses Skript holt sie in einem Lauf für alle Aktien des letzten Suchindex,
die noch keine Branche haben – größte zuerst – und schreibt nur `sec`/`ind` in data/sentiment.json.
Der Zeitstempel bestehender Einträge bleibt unverändert (Kursziele, Schlagzeilen usw. werden nicht angefasst).

    python -m backend.sector_backfill <search.json> [Sekunden]
"""

from __future__ import annotations

import json
import sys
import time

from . import sentiment


def todo(rows: list[dict], senti: dict) -> list[str]:
    """Aktien ohne Branchen-Zuordnung und ohne bekannte Yahoo-Branche – dazu US-Notierungen ohne bekannten Firmensitz
    (ADRs wie ASML, TSMC) –, nach Börsenwert absteigend."""
    def need(r):
        e = senti.get(r.get("t")) or {}
        return (not r.get("ig") and not e.get("ind")) or (r.get("r") == "us" and not e.get("co"))
    xs = [r for r in rows if need(r)]
    return [r["t"] for r in sorted(xs, key=lambda r: -(r.get("mc") or 0))]


def main(path: str, budget_s: float = 2400) -> None:
    import yfinance as yf

    raw = json.load(open(path, encoding="utf-8"))
    rows = raw if isinstance(raw, list) else raw.get("rows", [])
    senti = sentiment.load()
    ts = todo(rows, senti)
    print(f"Ohne Branche: {len(ts)} von {len(rows)} Aktien")
    got = tried = 0
    start = time.time()
    for t in ts:
        if time.time() - start > budget_s:
            break
        tried += 1
        try:
            info = yf.Ticker(t).get_info() or {}
        except Exception:
            info = {}
        if info.get("sector") or info.get("country"):
            e = senti.setdefault(t, {"ts": 0})
            if info.get("sector"):
                e["sec"], e["ind"] = info["sector"], info.get("industry") or ""
            if info.get("country"):
                e["co"] = info["country"]
            got += 1
        if tried % 200 == 0:
            print(f"… {tried} abgefragt, {got} mit Sektor")
            sentiment.save(senti)
        time.sleep(0.2)
    sentiment.save(senti)
    print(f"Fertig: {tried} abgefragt, {got} mit Sektor/Branche ergänzt, {len(ts) - tried} übrig (Zeitlimit)")


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 2400)
