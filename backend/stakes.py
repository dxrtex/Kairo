"""Großbeteiligungen über 5 % aus den SEC-Meldungen Schedule 13D und 13G – „Smart Money“, das frischer ist als 13F.

Wer mehr als 5 % einer US-Firma erwirbt, muss das melden: 13D (aktiv, z. B. Aktivisten wie Elliott oder Icahn, die Einfluss
nehmen wollen) innerhalb von 5 Geschäftstagen, 13G (passiv, z. B. Fonds ohne Einflussabsicht) innerhalb von 45 Tagen bzw.
bei über 10 % innerhalb von 5 Geschäftstagen. Seit 12/2024 heißen die Formulare „SCHEDULE 13D/13G“ (vorher „SC 13D/13G“).

Quelle: EDGAR „aktuelle Meldungen“ (Atom-Feed) – kostenlos, verlangt aber eine Kontaktadresse im User-Agent (Secret
SEC_CONTACT). Ohne sie bleibt die Liste leer. Nur Information, nie Teil der Kairo-Regel.

    python -m backend.stakes        # Test: druckt die neuesten Meldungen
"""
from __future__ import annotations

import html
import os
import re
import time
from datetime import date, timedelta
from urllib.parse import quote

import requests

UA = {"User-Agent": f"Kairo Scanner {os.environ.get('SEC_CONTACT', '')}".strip(), "Accept-Encoding": "gzip, deflate"}
FEED = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type={t}&owner=include&count=100&start={s}&output=atom"
FORMS = ("SCHEDULE 13D", "SCHEDULE 13G", "SC 13D", "SC 13G")
TICKERS = "https://www.sec.gov/files/company_tickers.json"
# Passive Großanleger melden 13G laufend für hunderte Firmen – deren 13G sind Rauschen (13D von ihnen bleibt drin)
PASSIVE = re.compile(r"\b(vanguard|blackrock|state street|fmr|fidelity|geode|capital (research|world|international)|t\. ?rowe|"
                     r"wellington|invesco|northern trust|morgan stanley|jpmorgan|j\.p\. morgan|goldman|ubs|bank of america|"
                     r"dimensional|norges|charles schwab|franklin|amundi|legal & general|nuveen|columbia|jane street|susquehanna)\b", re.I)
ENTRY = re.compile(r"<entry>(.*?)</entry>", re.S)
TITLE = re.compile(r"<title>(.*?)</title>", re.S)
LINK = re.compile(r'<link[^>]*href="([^"]+)"')
UPD = re.compile(r"<updated>(\d{4}-\d{2}-\d{2})")
NAME = re.compile(r"^(?P<form>[^-]+?)\s+-\s+(?P<name>.*?)\s+\((?P<cik>\d{6,10})\)\s+\((?P<role>Subject|Filed by|Reporting)\)", re.I)
ACC = re.compile(r"/(\d{10}-\d{2}-\d{6})-index")


def parse_feed(xml: str) -> list[dict]:
    """Atom-Feed → Einträge {acc, form, name, cik, role, d, url}. Jede Meldung erscheint zweimal: als Subject und als Filed by."""
    out = []
    for e in ENTRY.findall(xml or ""):
        t, ln, up = TITLE.search(e), LINK.search(e), UPD.search(e)
        m = NAME.match(html.unescape(t.group(1)).strip()) if t else None
        a = ACC.search(ln.group(1)) if ln else None
        if not (m and a):
            continue
        out.append({"acc": a.group(1), "form": " ".join(m["form"].split()).upper(), "name": m["name"].strip(), "cik": int(m["cik"]),
                    "role": "subject" if m["role"].lower() == "subject" else "filer", "d": up.group(1) if up else "",
                    "url": ln.group(1) if ln.group(1).startswith("http") else "https://www.sec.gov" + ln.group(1)})
    return out


def pair(entries: list[dict], cik_ticker: dict[int, str]) -> list[dict]:
    """Subject- und Filer-Zeile einer Meldung zusammenführen → {t, n, f, form, act, amend, d, url}. Nur Firmen mit Börsenkürzel."""
    by: dict[str, dict] = {}
    for x in entries:
        g = by.setdefault(x["acc"], {"form": x["form"], "d": x["d"], "url": x["url"]})
        g["subj" if x["role"] == "subject" else "filer"] = x
    out = []
    for acc, g in by.items():
        s, f = g.get("subj"), g.get("filer")
        if not s or not f or s["cik"] == f["cik"]:
            continue
        t = cik_ticker.get(s["cik"])
        if not t:
            continue
        form = g["form"].replace("SCHEDULE", "SC")
        act, amend = "13D" in form, form.endswith("/A")
        if not act and PASSIVE.search(f["name"]):
            continue
        out.append({"acc": acc, "t": t, "n": s["name"].title() if s["name"].isupper() else s["name"], "f": f["name"].title() if f["name"].isupper() else f["name"],
                    "form": ("13D" if act else "13G") + ("/A" if amend else ""), "act": act, "amend": amend, "d": g["d"], "url": g["url"]})
    return sorted(out, key=lambda x: x["d"], reverse=True)


def accumulate(hist: list[dict], new: list[dict], days: int = 120, today: str | None = None) -> list[dict]:
    since = ((date.fromisoformat(today) if today else date.today()) - timedelta(days=days)).isoformat()
    seen, out = set(), []
    for x in [*new, *hist]:
        if x.get("acc") in seen or (x.get("d") or "") < since:
            continue
        seen.add(x.get("acc"))
        out.append(x)
    return sorted(out, key=lambda x: x.get("d") or "", reverse=True)


def fetch(pages: int = 2, budget_s: float = 90) -> list[dict]:
    if "@" not in UA["User-Agent"]:
        print("13D/13G: kein SEC_CONTACT gesetzt – übersprungen")
        return []
    s, t0, ents = requests.Session(), time.time(), []
    s.headers.update(UA)
    try:
        cik_ticker = {int(v["cik_str"]): v["ticker"] for v in s.get(TICKERS, timeout=30).json().values()}
    except Exception as exc:
        print(f"13D/13G: Kürzelliste nicht geladen {exc!r}"[:140])
        return []
    for form in FORMS:
        for pg in range(pages):
            if time.time() - t0 > budget_s:
                break
            try:
                r = s.get(FEED.format(t=quote(form), s=pg * 100), timeout=20)
                got = parse_feed(r.text)
            except Exception as exc:
                print(f"13D/13G: Feed {form} nicht erreichbar {exc!r}"[:140])
                break
            ents += got
            time.sleep(.15)
            if len(got) < 100:
                break
    out = pair(ents, cik_ticker)
    print(f"13D/13G: {len(ents)} Feed-Einträge → {len(out)} Meldungen ({sum(x['act'] for x in out)} aktiv/13D)")
    return out


if __name__ == "__main__":
    for x in fetch()[:20]:
        print(x["d"], x["form"], x["t"], "←", x["f"])
