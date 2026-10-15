"""Wichtige Markt-Termine automatisch von den offiziellen Seiten holen.

- Fed-Zinsentscheide (FOMC):          federalreserve.gov
- EZB-Zinsentscheide:                 ecb.europa.eu
- US-Inflation (CPI), Arbeitsmarkt:   bls.gov (Release-Kalender)
- ALLE wichtigen Wirtschaftstermine weltweit (USA, Eurozone, China, Japan, UK, …) für diese und nächste
  Woche: Wirtschaftskalender von Forex Factory (nfs.faireconomy.media, frei, JSON) – Inflation, Erzeugerpreise,
  Arbeitsmarkt, BIP, Einzelhandel, Einkaufsmanager, Fed-Protokolle, Reden der Notenbank-Chefs, Feiertage …
  Gesehene Termine werden im Zustand (state/macro_seen.json) gemerkt, damit sie nach der Woche nicht verschwinden.

Jede Quelle wird einzeln versucht; schlägt eine fehl, bleiben die von Hand gepflegten Termine aus
data/macro_events.json als Ersatz. Ergebnis: Liste von {date, title, region}.
"""

from __future__ import annotations

import re
import urllib.request
from datetime import date

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
                    "Version/17.0 Safari/605.1.15", "Accept-Language": "en-US,en;q=0.9"}
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _get(url: str) -> str:
    """Seite laden – zuerst mit Browser-Imitation (curl_cffi, kommt mit yfinance), sonst urllib.
    bls.gov lehnt einfache Abrufe mit 403 ab."""
    try:
        from curl_cffi import requests as cr

        r = cr.get(url, impersonate="chrome", timeout=40)
        r.raise_for_status()
        return r.text
    except ImportError:
        pass
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "replace")


def _month(name: str) -> int:
    return MONTHS[name.strip().lower()[:3]]


def fed_meetings(html: str) -> list[dict]:
    """FOMC-Sitzungen je Jahr; Zinsentscheid = letzter Sitzungstag."""
    out = []
    for block in re.split(r"(?=<h4[^>]*>\s*<a[^>]*>\s*\d{4} FOMC Meetings|<h4[^>]*>\s*\d{4} FOMC Meetings)", html):
        y = re.search(r"(\d{4}) FOMC Meetings", block)
        if not y:
            continue
        year = int(y.group(1))
        pairs = re.findall(r'fomc-meeting__month[^>]*>\s*<strong>([^<]+)</strong>.*?fomc-meeting__date[^>]*>\s*([^<]+?)\s*<',
                           block, re.S)
        for mon, days in pairs:
            nums = [int(x) for x in re.findall(r"\d+", days)]
            if not nums:
                continue
            months = [m for m in re.split(r"[/-]", mon) if m.strip()]
            m = _month(months[-1]) if len(nums) > 1 and nums[-1] < nums[0] and len(months) > 1 else _month(months[0])
            out.append({"date": date(year, m, nums[-1]).isoformat(), "title": "USA: Fed-Zinsentscheid", "region": "us", "imp": "high", "time": "20:00", "why": "Leitzins USA – bewegt alle Aktien weltweit"})
    return out


def ecb_meetings(html: str) -> list[dict]:
    """EZB-Ratssitzungen zur Geldpolitik; Zinsentscheid = Tag mit Pressekonferenz."""
    out = []
    for d, mth, y, text in re.findall(r"(\d{1,2})/(\d{1,2})/(\d{4})\s*</dt>\s*<dd[^>]*>(.*?)</dd>", html, re.S):
        t = re.sub(r"<[^>]+>", " ", text).lower()
        if "monetary policy meeting" in t and ("day 2" in t or "press conference" in t):
            out.append({"date": date(int(y), int(mth), int(d)).isoformat(), "title": "Eurozone: EZB-Zinsentscheid", "region": "europe", "imp": "high", "time": "14:15", "why": "Leitzins Eurozone"})
    return out


def bls_releases(html: str, title: str, why: str = "") -> list[dict]:
    """Release-Termine aus einer BLS-Kalenderseite (z. B. „Oct. 15, 2026“)."""
    out = []
    cells = r"<td[^>]*>\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),\s+(\d{4})"
    for mon, d, y in re.findall(cells, html):
        try:
            out.append({"date": date(int(y), _month(mon), int(d)).isoformat(), "title": title, "region": "us", "imp": "high", "time": "14:30", "why": why})
        except ValueError:
            continue
    return out


SOURCES = (
    ("Fed", "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm", fed_meetings),
    ("EZB", "https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html", ecb_meetings),
    ("US-CPI", "https://www.bls.gov/schedule/news_release/cpi.htm", lambda h: bls_releases(h, "USA: Inflation (CPI)", "Inflation – wichtig für Zinsen")),
    ("US-Arbeitsmarkt", "https://www.bls.gov/schedule/news_release/empsit.htm",
     lambda h: bls_releases(h, "USA: Arbeitsmarktbericht (Non-Farm Payrolls)", "neue Jobs – stark marktbewegend")),
)


# ---------- Wirtschaftskalender (Forex Factory) ----------
FF_URLS = ("https://nfs.faireconomy.media/ff_calendar_thisweek.json",
           "https://nfs.faireconomy.media/ff_calendar_nextweek.json")
FF_REGION = {"USD": "us", "EUR": "europe", "GBP": "europe", "CHF": "europe", "CNY": "asia", "JPY": "asia",
             "AUD": "asia", "NZD": "asia", "CAD": "us", "ALL": "all"}
FF_LAND = {"USD": "USA", "EUR": "Eurozone", "GBP": "Großbritannien", "CHF": "Schweiz", "CNY": "China", "JPY": "Japan",
           "AUD": "Australien", "NZD": "Neuseeland", "CAD": "Kanada", "ALL": "Welt"}
FF_MEDIUM = {"USD", "EUR", "CNY"}            # mittlere Wichtigkeit nur für die großen Märkte
# (Muster im englischen Titel, deutscher Titel, kurze Erklärung) – erstes passendes Muster gewinnt
FF_DE = (
    (r"^Federal Funds Rate|^FOMC Statement|^FOMC Economic Projections", "Fed-Zinsentscheid", "Leitzins USA – bewegt alle Aktien weltweit"),
    (r"^FOMC Press Conference", "Fed-Pressekonferenz", "Ausblick auf weitere Zinsschritte"),
    (r"^FOMC Meeting Minutes", "Fed-Protokoll", "Protokoll der letzten Zinssitzung"),
    (r"^Main Refinancing Rate|^Monetary Policy Statement", "EZB-Zinsentscheid", "Leitzins Eurozone"),
    (r"^ECB Press Conference", "EZB-Pressekonferenz", "Ausblick auf weitere Zinsschritte"),
    (r"^Official Bank Rate", "BoE-Zinsentscheid", "Leitzins Großbritannien"),
    (r"^BOJ Policy Rate|^BOJ Outlook", "BoJ-Zinsentscheid", "Leitzins Japan – bewegt Yen und Asien-Börsen"),
    (r"^SNB Policy Rate", "SNB-Zinsentscheid", "Leitzins Schweiz"),
    (r"^(1-y|5-y)? ?Loan Prime Rate", "China: Leitzins (LPR)", "Kreditzins China"),
    (r"^Core CPI", "Inflation (CPI)", "Inflation – wichtig für Zinsen"),
    (r"^CPI Flash Estimate", "Inflation (Schnellschätzung)", "Inflation – wichtig für Zinsen"),
    (r"^Core PCE|^PCE Price", "PCE-Inflation", "Lieblings-Inflationsmaß der Fed"),
    (r"^CPI", "Inflation (CPI)", "Inflation – wichtig für Zinsen"),
    (r"^Core PPI|^PPI", "Erzeugerpreise (PPI)", "Vorlauf für die Inflation"),
    (r"^Non-Farm Employment Change", "Arbeitsmarktbericht (Non-Farm Payrolls)", "neue Jobs – stark marktbewegend"),
    (r"^Unemployment Rate", "Arbeitsmarktbericht (Non-Farm Payrolls)", "neue Jobs – stark marktbewegend"),
    (r"^Unemployment Claims", "Erstanträge Arbeitslosenhilfe", "wöchentlicher Arbeitsmarkt-Check"),
    (r"^JOLTS", "Offene Stellen (JOLTS)", "Arbeitsmarkt"),
    (r"^ADP Non-Farm", "ADP-Arbeitsmarkt", "Vorbote für den Arbeitsmarktbericht"),
    (r"^Average Hourly Earnings", "Arbeitsmarktbericht (Non-Farm Payrolls)", "neue Jobs – stark marktbewegend"),
    (r"GDP", "BIP (Wirtschaftswachstum)", "Konjunktur"),
    (r"^Core Retail Sales|^Retail Sales", "Einzelhandelsumsatz", "Konsum"),
    (r"ISM Manufacturing PMI", "ISM Industrie", "Konjunktur-Stimmung Industrie"),
    (r"ISM Services PMI", "ISM Dienstleistungen", "Konjunktur-Stimmung Dienstleister"),
    (r"Manufacturing PMI", "Einkaufsmanager Industrie", "Konjunktur-Stimmung"),
    (r"Services PMI", "Einkaufsmanager Dienstleistungen", "Konjunktur-Stimmung"),
    (r"Ifo Business Climate", "ifo-Geschäftsklima", "Stimmung deutsche Wirtschaft"),
    (r"ZEW Economic Sentiment", "ZEW-Konjunkturerwartungen", "Stimmung Finanzexperten"),
    (r"Consumer Sentiment|Consumer Confidence", "Verbraucherstimmung", "Konsum-Ausblick"),
    (r"Industrial Production", "Industrieproduktion", "Konjunktur"),
    (r"Trade Balance", "Handelsbilanz", "Export/Import"),
    (r"Durable Goods", "Auftragseingänge langlebige Güter", "Investitionen"),
    (r"Building Permits|Housing Starts|Existing Home Sales|New Home Sales", "Immobilienmarkt", "Bau und Immobilien"),
    (r"Crude Oil Inventories", "Öl-Lagerbestände", "Ölpreis"),
    (r"Speaks|Testifies", None, "Rede – kann Zinserwartungen bewegen"),
    (r"Bank Holiday", "Feiertag", "Börse dort evtl. geschlossen oder dünner Handel"),
)


def _ff_title(title: str, cur: str) -> tuple[str, str]:
    land = FF_LAND.get(cur, cur)
    for pat, de, why in FF_DE:
        if re.search(pat, title, re.I):
            if de is None:                               # Reden: Namen behalten („Fed Chair Powell Speaks“)
                who = re.sub(r"\s*(Speaks|Testifies).*$", "", title).strip()
                return f"{land}: Rede {who}", why
            return f"{land}: {de}", why
    return f"{land}: {title}", ""


def ff_events(items: list[dict]) -> list[dict]:
    """Forex-Factory-JSON → Kairo-Termine (Uhrzeit in Berlin)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    out = []
    for it in items or []:
        cur, imp, title = str(it.get("country", "")).upper(), str(it.get("impact", "")), str(it.get("title", "")).strip()
        if not title or not (imp == "High" or (imp == "Medium" and cur in FF_MEDIUM)
                             or (imp == "Holiday" and cur in ("USD", "EUR", "CNY", "JPY", "GBP"))):
            continue
        try:
            dt = datetime.fromisoformat(str(it["date"])).astimezone(ZoneInfo("Europe/Berlin"))
        except Exception:
            continue
        de, why = _ff_title(title, cur)
        ev = {"date": dt.date().isoformat(), "title": de, "region": FF_REGION.get(cur, "all"),
              "imp": "high" if imp == "High" else "mid" if imp == "Medium" else "info", "why": why}
        if imp != "Holiday" and (dt.hour, dt.minute) != (0, 0):
            ev["time"] = dt.strftime("%H:%M")
        for k, k2 in (("forecast", "fc"), ("previous", "prev")):
            if str(it.get(k) or "").strip():
                ev[k2] = str(it[k]).strip()
        if not any(o["date"] == ev["date"] and o["title"] == ev["title"] for o in out):
            out.append(ev)
    return out


def _ff_fetch() -> list[dict]:
    import json

    events = []
    for url in FF_URLS:
        try:
            events += ff_events(json.loads(_get(url)))
        except Exception as exc:
            print(f"Wirtschaftskalender {url.rsplit('/', 1)[-1]}: {exc!r}")
    return events


def remember(events: list[dict], seen: list[dict], keep_days: int = 45) -> list[dict]:
    """Neue Termine mit den schon gesehenen zusammenführen (neuere Angaben gewinnen), alte wegwerfen."""
    from datetime import timedelta

    cut = (date.today() - timedelta(days=keep_days)).isoformat()
    by = {(e["date"], e["title"]): e for e in seen if e.get("date", "") >= cut}
    by.update({(e["date"], e["title"]): e for e in events})
    return sorted(by.values(), key=lambda e: (e["date"], e.get("time", ""), e["title"]))


def fetch_macro_events() -> tuple[list[dict], dict[str, int]]:
    events, stats = [], {}
    from . import state

    ff = _ff_fetch()
    stats["Wirtschaftskalender"] = len(ff)
    seen = remember(ff, state.load("macro_seen.json", []))
    state.save("macro_seen.json", seen)
    events += seen
    for name, url, parse in SOURCES:
        try:
            found = parse(_get(url))
        except Exception as exc:
            print(f"Markt-Termine {name}: Fehler {exc!r}")
            found = []
        stats[name] = len(found)
        events += found
    uniq = {(e["date"], e["title"]): e for e in events}
    return sorted(uniq.values(), key=lambda e: e["date"]), stats
