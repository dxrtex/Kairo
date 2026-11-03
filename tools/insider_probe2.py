"""Insider-Quellen, Runde 2 (03.11.2026): Gibt es weitere freie, maschinenlesbare Directors'-Dealings-Quellen?
Nur Test, ändert nichts. Je Quelle: Status, Größe, Ausschnitt – und ob Beträge/Personen drinstehen."""
from __future__ import annotations

import datetime as dt
import json
import re
import sys

import requests

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
      "Accept": "application/json, text/csv, text/html;q=0.9, */*;q=0.8", "Accept-Language": "de-DE,de;q=0.9,en;q=0.8"}
D0 = (dt.date.today() - dt.timedelta(days=30))
D1 = dt.date.today()


def show(name, r, n=700):
    body = r.content[:200000]
    try:
        txt = body.decode(r.encoding or "utf-8", errors="replace")
    except Exception:
        txt = body.decode("utf-8", errors="replace")
    print(f"=== {name}: {r.status_code} · {r.headers.get('content-type', '')} · {len(r.content)} Bytes")
    print("    " + " ".join(txt[:n].split())[:n])
    return txt


def tryit(name, fn):
    try:
        fn()
    except Exception as exc:
        print(f"=== {name}: FEHLER {exc!r}"[:300])


def bafin_all():
    """Deutschland: BaFin-Datenbank ohne Emittent, nur Zeitraum → alle Firmen?"""
    s = requests.Session(); s.headers.update(UA)
    base = "https://portal.mvp.bafin.de/database/DealingsInfo/sucheForm.do"
    p = {"meldepflichtigerName": "", "emittentName": "", "emittentIsin": "", "zeitraum": "1", "zeitraumVon": D0.strftime("%d.%m.%Y"),
         "zeitraumBis": D1.strftime("%d.%m.%Y"), "emittentButton": "Suche Emittent", "d-4000784-e": "1", "6578706f7274": "1"}
    t = show("BaFin alle Emittenten 30 Tage (CSV)", s.get(base, params=p, timeout=60), 500)
    print("    Zeilen:", t.count("\n"))


def nasdaq_nordic():
    """Dänemark/Finnland/Schweden/Island: Nasdaq-Nordic-Nachrichten, Kategorie „Managers' transactions“."""
    u = ("https://api.news.eu.nasdaq.com/news/query.action?type=json&showAttachments=true&showCnsSpecific=true&showCompany=true"
         "&countResults=true&freeText=&company=&market=Main%20Market%2C+Copenhagen&cnscategory=Managers%27+Transactions"
         f"&fromDate={D0}&toDate={D1}&globalGroup=exchangeNotice&globalName=NordicAllMarkets&displayLanguage=en&language=en&timeZone=CET&dateMask=yyyy-MM-dd+HH%3Amm%3Ass&limit=20&start=0&dir=DESC")
    t = show("Nasdaq Nordic Managers' transactions (Kopenhagen)", requests.get(u, headers=UA, timeout=30), 900)
    m = re.search(r'"messageUrl"\s*:\s*"([^"]+)"', t)
    if m:
        show("  → erste Meldung (Text)", requests.get(m.group(1).replace("\\/", "/"), headers=UA, timeout=30), 900)


def oslo_body():
    """Norwegen: Newsweb-Meldung „Mandatory notification of trade“ – steht der Betrag im Text?"""
    lst = requests.get(f"https://api3.oslo.oslobors.no/v1/newsreader/list?category=1102&fromDate={D0}&toDate={D1}", headers=UA, timeout=30).json()
    msgs = (lst.get("data") or {}).get("messages") or []
    print(f"=== Oslo Newsweb: {len(msgs)} Meldungen; erste: {json.dumps(msgs[:1], ensure_ascii=False)[:400]}")
    if msgs:
        mid = msgs[0].get("messageId") or msgs[0].get("id")
        show("  → Text", requests.get(f"https://api3.oslo.oslobors.no/v1/newsreader/message?messageId={mid}", headers=UA, timeout=30), 1200)


def fca_nsm():
    """Großbritannien: FCA National Storage Mechanism – PDMR-Meldungen (Director/PDMR Shareholding)."""
    body = {"from": 0, "size": 10, "sort": "submitted_date", "sortorder": "desc",
            "criteriaObj": {"criteria": [{"name": "latest_flag", "value": "Y"}, {"name": "tag_esef", "value": ""},
                                         {"name": "type", "value": "Director/PDMR Shareholding"}], "dateCriteria": [{"name": "submitted_date", "value": {"from": f"{D0}T00:00:00Z", "to": f"{D1}T23:59:59Z"}}]}}
    t = show("FCA NSM PDMR (JSON-Suche)", requests.post("https://api.data.fca.org.uk/search?index=fca-nsm-searchdata", json=body, headers={**UA, "Content-Type": "application/json"}, timeout=30), 900)
    m = re.search(r'"download_link"\s*:\s*"([^"]+)"', t)
    if m:
        show("  → erste Meldung", requests.get("https://data.fca.org.uk/artefacts/" + m.group(1), headers=UA, timeout=30), 1200)


def amf_detail():
    """Frankreich: AMF BDIF – Detail einer Dirigeants-Meldung (Betrag/Person?)."""
    j = requests.get("https://bdif.amf-france.org/back/api/v1/informations?typesInformation=DD&from=0&size=3", headers=UA, timeout=30).json()
    it = (j.get("result") or j.get("hits") or j.get("content") or [])
    print("=== AMF Liste Schlüssel:", list(j)[:10], "· erstes:", json.dumps(it[:1] if isinstance(it, list) else it, ensure_ascii=False)[:900])
    first = it[0] if isinstance(it, list) and it else {}
    num = first.get("numero") or first.get("id")
    if num:
        show("  → Detail", requests.get(f"https://bdif.amf-france.org/back/api/v1/informations/{num}", headers=UA, timeout=30), 1500)


def india():
    """Indien: NSE PIT (mit Cookie aus der Startseite) und BSE."""
    s = requests.Session(); s.headers.update({**UA, "Referer": "https://www.nseindia.com/"})
    s.get("https://www.nseindia.com/", timeout=20)
    s.get("https://www.nseindia.com/companies-listing/corporate-filings-insider-trading", timeout=20)
    show("NSE PIT", s.get(f"https://www.nseindia.com/api/corporates-pit?index=equities&from_date={D0:%d-%m-%Y}&to_date={D1:%d-%m-%Y}", timeout=30), 700)
    show("BSE Insider", requests.get(f"https://api.bseindia.com/BseIndiaAPI/api/InsiderTrade15/w?scripcode=&fromdt={D0:%Y%m%d}&todt={D1:%Y%m%d}",
                                     headers={**UA, "Referer": "https://www.bseindia.com/", "Origin": "https://www.bseindia.com"}, timeout=30), 700)


def hkex():
    show("HKEX DI (alle, 7 Tage)", requests.get("https://di.hkex.com.hk/di/NSSrchCorpList.aspx?sa1=da&scsd=" + (D1 - dt.timedelta(days=7)).strftime("%d/%m/%Y")
                                               + "&sced=" + D1.strftime("%d/%m/%Y") + "&src=MAIN&lang=EN", headers=UA, timeout=30), 900)


def canada():
    show("Kanada SEDI (neu, CSA)", requests.get("https://www.sedi.ca/sedi/SVTWeeklySummaryACL?name=W1ALLPDFI&locale=en_CA", headers=UA, timeout=30), 700)
    show("Kanada CanadianInsider", requests.get("https://www.canadianinsider.com/latest-insider-trading-filings", headers=UA, timeout=30), 500)


def spain():
    show("Spanien CNMV Directivos", requests.get("https://www.cnmv.es/portal/Consultas/BusquedaPorEntidad.aspx", headers=UA, timeout=30), 400)


def asx_pdf():
    """Australien: Appendix 3Y als PDF – steht der Betrag maschinenlesbar drin?"""
    d = requests.get("https://asx.api.markitdigital.com/asx-research/1.0/companies/BHP/announcements?count=50", headers=UA, timeout=30).json()
    its = [i for i in (d.get("data") or {}).get("items") or [] if re.search(r"director|3Y", i.get("headline") or "", re.I)]
    print("=== ASX BHP 3Y:", len(its), its[:1])
    if its:
        r = requests.get("https://cdn-api.markitdigital.com/apiman-gateway/ASX/asx-research/1.0/file/" + its[0]["documentKey"], headers=UA, timeout=30)
        print("  → PDF", r.status_code, r.headers.get("content-type"), len(r.content))


def korea():
    show("Korea OpenDART (ohne Schlüssel)", requests.get("https://opendart.fss.or.kr/api/elestock.json?crtfc_key=&corp_code=00126380", headers=UA, timeout=30), 300)


def main() -> int:
    for name, fn in (("BaFin", bafin_all), ("Nasdaq Nordic", nasdaq_nordic), ("Oslo", oslo_body), ("FCA", fca_nsm), ("AMF", amf_detail),
                     ("Indien", india), ("HKEX", hkex), ("Kanada", canada), ("Spanien", spain), ("ASX", asx_pdf), ("Korea", korea)):
        tryit(name, fn)
    return 0


if __name__ == "__main__":
    sys.exit(main())
