"""Insider-Quellen, Runde 3: PDF-Meldungen (Frankreich AMF, Nasdaq-Nordic-Anhänge, Oslo-Anhänge) und Großbritannien
(Investegate / FCA NSM). Nur Test – druckt Status, Links und den ausgelesenen Text, damit ein Parser gebaut werden kann."""
from __future__ import annotations

import datetime as dt
import io
import json
import re
import sys

import requests

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
      "Accept": "application/json, text/html;q=0.9, */*;q=0.8", "Accept-Language": "en-GB,en;q=0.9,de;q=0.8"}
D1 = dt.date.today(); D0 = D1 - dt.timedelta(days=10)


def pdf_text(b: bytes, n=1800) -> str:
    from pypdf import PdfReader
    t = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(b)).pages[:3])
    return " ".join(t.split())[:n]


def tryit(name, fn):
    print(f"\n######## {name}")
    try:
        fn()
    except Exception as exc:
        print(f"FEHLER {exc!r}"[:400])


def amf():
    j = requests.get("https://bdif.amf-france.org/back/api/v1/informations?typesInformation=DD&from=0&size=5", headers=UA, timeout=30).json()
    print("Schlüssel:", list(j)[:10])
    it = j.get("result") or j.get("hits") or j.get("content") or []
    print("erstes:", json.dumps(it[:1], ensure_ascii=False)[:1500])
    for x in it[:2]:
        txt = json.dumps(x)
        for path in re.findall(r'"(?:path|chemin|url|nomFichier|fileName|documentPath)"\s*:\s*"([^"]+)"', txt)[:3]:
            for base in ("https://bdif.amf-france.org/back/api/v1/documents/", "https://bdif.amf-france.org/back/api/v1/document/", "https://bdif.amf-france.org/"):
                u = path if path.startswith("http") else base + path.lstrip("/")
                r = requests.get(u, headers=UA, timeout=30)
                print("  ", u[:140], r.status_code, r.headers.get("content-type"), len(r.content))
                if r.ok and r.content[:4] == b"%PDF":
                    print("   PDF-TEXT:", pdf_text(r.content)); return
        num = x.get("numero") or x.get("id")
        if num:
            d = requests.get(f"https://bdif.amf-france.org/back/api/v1/informations/{num}", headers=UA, timeout=30)
            print("  Detail", d.status_code, d.text[:1500])


def nordic():
    u = ("https://api.news.eu.nasdaq.com/news/query.action?type=json&showAttachments=true&showCnsSpecific=true&showCompany=true"
         "&countResults=true&freeText=&company=&market=&cnscategory=Managers%27+Transactions"
         "&globalGroup=exchangeNotice&globalName=NordicAllMarkets&displayLanguage=en&language=en&timeZone=CET&dateMask=yyyy-MM-dd+HH%3Amm%3Ass&limit=20&start=0&dir=DESC")
    j = requests.get(u, headers=UA, timeout=30).json()
    its = ((j.get("results") or {}).get("item")) or []
    print("Meldungen:", len(its))
    done = 0
    for x in its:
        att = x.get("attachment") or []
        print(" ", x.get("company"), x.get("market"), x.get("releaseTime"), "Anhänge:", [a.get("fileName") for a in att][:3])
        for a in att:
            if done < 3 and str(a.get("attachmentUrl", "")).lower().endswith(".pdf"):
                r = requests.get(a["attachmentUrl"], headers=UA, timeout=30)
                print("   PDF", r.status_code, len(r.content)); print("   TEXT:", pdf_text(r.content, 1500)); done += 1


def oslo():
    lst = requests.get(f"https://api3.oslo.oslobors.no/v1/newsreader/list?category=1102&fromDate={D0}&toDate={D1}", headers=UA, timeout=30).json()
    msgs = (lst.get("data") or {}).get("messages") or []
    print("Meldungen:", len(msgs))
    for m in msgs[:4]:
        mid = m.get("messageId") or m.get("id")
        d = requests.get(f"https://api3.oslo.oslobors.no/v1/newsreader/message?messageId={mid}", headers=UA, timeout=30).json()
        msg = (d.get("data") or {}).get("message") or {}
        print(" ", msg.get("issuerSign"), msg.get("title"), "Anhänge:", json.dumps(msg.get("attachments"), ensure_ascii=False)[:300])
        body = re.sub(r"<[^>]+>", " ", msg.get("body") or "")
        print("   TEXT:", " ".join(body.split())[:900])
        for a in msg.get("attachments") or []:
            aid = a.get("id")
            if aid and str(a.get("name", "")).lower().endswith(".pdf"):
                r = requests.get(f"https://api3.oslo.oslobors.no/v1/newsreader/attachment?messageId={mid}&attachmentId={aid}", headers=UA, timeout=30)
                print("   PDF", r.status_code, len(r.content), r.content[:4])
                if r.content[:4] == b"%PDF":
                    print("   PDF-TEXT:", pdf_text(r.content, 1500))
                break


def investegate():
    for u in ("https://www.investegate.co.uk/category/director-pdmr-shareholding", "https://www.investegate.co.uk/today-announcements/",
              "https://www.investegate.co.uk/advanced-search?headline=PDMR", "https://www.investegate.co.uk/search?q=Director%2FPDMR+Shareholding"):
        r = requests.get(u, headers=UA, timeout=30)
        links = re.findall(r'href="([^"]*announcement[^"]*)"[^>]*>\s*([^<]{0,90})', r.text)
        pd = [l for l in links if re.search(r"PDMR|Director", l[1], re.I)]
        print(u, r.status_code, len(r.text), "Links:", len(links), "PDMR:", len(pd), pd[:4])
        if pd:
            a = pd[0][0]; a = a if a.startswith("http") else "https://www.investegate.co.uk" + a
            t = requests.get(a, headers=UA, timeout=30).text
            print("   TEXT:", " ".join(re.sub(r"<[^>]+>", " ", re.sub(r"(?s)<(script|style).*?</\1>", " ", t)).split())[:2500])
            return


def fca():
    for idx in ("fca-nsm-searchdata", "fca-nsm-searchdata-v2", "fca-nsm"):
        body = {"from": 0, "size": 5, "sortorder": "desc", "sort": "publication_date",
                "criteriaObj": {"criteria": [{"name": "latest_flag", "value": "Y"}], "dateCriteria": []}}
        r = requests.post(f"https://api.data.fca.org.uk/search?index={idx}", json=body, headers={**UA, "Content-Type": "application/json",
                          "Origin": "https://data.fca.org.uk", "Referer": "https://data.fca.org.uk/"}, timeout=30)
        print(idx, r.status_code, r.text[:600])


def lse():
    r = requests.get("https://api.londonstockexchange.com/api/gw/lse/instruments/alldata/news?worlds=quotes&categories=DSH&page=0&size=10", headers=UA, timeout=30)
    print("LSE DSH", r.status_code, r.text[:600])


def main() -> int:
    for n, f in (("Frankreich AMF (PDF)", amf), ("Nasdaq Nordic Anhänge (PDF)", nordic), ("Oslo Anhänge", oslo),
                 ("UK Investegate", investegate), ("UK FCA NSM", fca), ("UK LSE", lse)):
        tryit(n, f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
