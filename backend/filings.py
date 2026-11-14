"""Wichtige Firmenmeldungen (SEC 8-K) für deine Aktien – schneller als Presseartikel, direkt von der Börsenaufsicht.

US-Firmen müssen wesentliche Ereignisse innerhalb von 4 Geschäftstagen als 8-K melden: Quartalszahlen (Item 2.02),
Vorstandswechsel (5.02), Übernahmen (2.01), wesentliche Verträge (1.01), Restrukturierung (2.05), Bilanzwarnung (4.02) …
Kairo liest den EDGAR-Feed der aktuellen 8-K-Meldungen und behält nur Firmen aus Watchlist, Merkliste und Depot.
Braucht SEC_CONTACT (Kontaktadresse im User-Agent). Gesammelt über 60 Tage (Zustand filings_hist.json). Nur Information.
"""
from __future__ import annotations

import html
import os
import re
import time
from datetime import date, timedelta

import requests

UA = {"User-Agent": f"Kairo Scanner {os.environ.get('SEC_CONTACT', '')}".strip(), "Accept-Encoding": "gzip, deflate"}
FEED = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&owner=include&count=100&start={s}&output=atom"
TICKERS = "https://www.sec.gov/files/company_tickers.json"
ITEMS = {"1.01": ("Wesentlicher Vertrag", 2), "1.02": ("Vertrag beendet", 2), "1.03": ("Insolvenz", 3), "1.05": ("Cyber-Vorfall", 3),
         "2.01": ("Übernahme/Verkauf abgeschlossen", 2), "2.02": ("Quartalszahlen", 1), "2.03": ("Neue Schulden", 1), "2.05": ("Restrukturierung", 2),
         "2.06": ("Abschreibung", 2), "3.01": ("Börsennotiz gefährdet", 3), "3.02": ("Neue Aktien ausgegeben", 1), "3.03": ("Rechte der Aktionäre geändert", 1),
         "4.01": ("Wirtschaftsprüfer gewechselt", 2), "4.02": ("Frühere Bilanz nicht verlässlich", 3), "5.01": ("Kontrollwechsel", 3),
         "5.02": ("Vorstand/Aufsichtsrat gewechselt", 2), "5.03": ("Satzung geändert", 0), "5.07": ("Hauptversammlung", 0), "7.01": ("Information an Anleger", 0),
         "8.01": ("Sonstiges Ereignis", 0), "9.01": ("Anlagen", -1)}
ENTRY = re.compile(r"<entry>(.*?)</entry>", re.S)
TITLE = re.compile(r"<title>(.*?)</title>", re.S)
LINK = re.compile(r'<link[^>]*href="([^"]+)"')
UPD = re.compile(r"<updated>(\d{4}-\d{2}-\d{2})")
SUMM = re.compile(r"<summary[^>]*>(.*?)</summary>", re.S)
NAME = re.compile(r"^(?P<form>8-K(?:/A)?)\s+-\s+(?P<name>.*?)\s+\((?P<cik>\d{6,10})\)", re.I)
ITEM = re.compile(r"Item\s+(\d\.\d\d)", re.I)
ACC = re.compile(r"/(\d{10}-\d{2}-\d{6})-index")


def parse_feed(xml: str, cik_ticker: dict[int, str], want: set[str] | None = None) -> list[dict]:
    """Atom-Feed → [{acc, t, n, form, d, items: [[code, text, gewicht]], w, url}], nur gesuchte Kürzel (want), ohne reine Anlagen."""
    out = []
    for e in ENTRY.findall(xml or ""):
        t, ln = TITLE.search(e), LINK.search(e)
        m = NAME.match(html.unescape(t.group(1)).strip()) if t else None
        if not (m and ln):
            continue
        tk = cik_ticker.get(int(m["cik"]))
        if not tk or (want is not None and tk not in want):
            continue
        a = ACC.search(ln.group(1))
        sm = html.unescape(SUMM.search(e).group(1)) if SUMM.search(e) else ""
        codes = list(dict.fromkeys(ITEM.findall(sm)))
        items = [[c, *ITEMS.get(c, ("Meldung", 0))] for c in codes if ITEMS.get(c, ("", 0))[1] >= 0]
        if not items:
            continue
        up = UPD.search(e)
        url = ln.group(1) if ln.group(1).startswith("http") else "https://www.sec.gov" + ln.group(1)
        out.append({"acc": a.group(1) if a else url, "t": tk, "n": m["name"].title() if m["name"].isupper() else m["name"],
                    "form": m["form"].upper(), "d": up.group(1) if up else "", "items": items, "w": max(i[2] for i in items), "url": url})
    return out


def accumulate(hist: list[dict], new: list[dict], days: int = 60, today: str | None = None) -> list[dict]:
    since = ((date.fromisoformat(today) if today else date.today()) - timedelta(days=days)).isoformat()
    seen, out = set(), []
    for x in [*new, *hist]:
        if x.get("acc") in seen or (x.get("d") or "") < since:
            continue
        seen.add(x.get("acc"))
        out.append(x)
    return sorted(out, key=lambda x: x.get("d") or "", reverse=True)


def fetch(want: set[str], pages: int = 6, budget_s: float = 90) -> list[dict]:
    if "@" not in UA["User-Agent"]:
        print("8-K: kein SEC_CONTACT gesetzt – übersprungen")
        return []
    s, t0 = requests.Session(), time.time()
    s.headers.update(UA)
    try:
        cik_ticker = {int(v["cik_str"]): v["ticker"] for v in s.get(TICKERS, timeout=30).json().values()}
    except Exception as exc:
        print(f"8-K: Kürzelliste nicht geladen {exc!r}"[:140])
        return []
    want = {w.upper() for w in want if w and "." not in w}            # nur US-Kürzel
    out = []
    for pg in range(pages):
        if time.time() - t0 > budget_s:
            break
        try:
            xml = s.get(FEED.format(s=pg * 100), timeout=20).text
        except Exception as exc:
            print(f"8-K: Feed nicht erreichbar {exc!r}"[:140])
            break
        got = parse_feed(xml, cik_ticker, want)
        out += got
        time.sleep(.15)
        if xml.count("<entry>") < 100:
            break
    print(f"8-K: {len(out)} Meldungen deiner Aktien")
    return out
