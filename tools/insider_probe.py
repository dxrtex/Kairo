"""Welche Insider-Register großer Länder liefern frei und maschinenlesbar Directors' Dealings? (nur Test, ändert nichts)

Je Quelle: HTTP-Status, Inhaltstyp, Größe und ein kurzer Ausschnitt – damit entschieden werden kann, welche sich für
den Abendscan eignen (wie SEC/BaFin/AFM/ASX in backend/insider.py)."""
from __future__ import annotations

import datetime as dt
import sys

import requests

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
      "Accept": "application/json, text/csv, text/html;q=0.9, */*;q=0.8", "Accept-Language": "de-DE,de;q=0.9,en;q=0.8"}
D0 = (dt.date.today() - dt.timedelta(days=14)).isoformat()
D1 = dt.date.today().isoformat()
D0dmy = (dt.date.today() - dt.timedelta(days=14)).strftime("%d-%m-%Y")
D1dmy = dt.date.today().strftime("%d-%m-%Y")

CANDIDATES = [
    ("Schweden FI (CSV)", f"https://marknadssok.fi.se/publiceringsklient/sv-SE/Search/Search?SearchFunctionType=Insyn&Utgivare=&PersonILedandeStallningNamn=&Transaktionsdatum.From={D0}&Transaktionsdatum.To={D1}&button=export", None),
    ("Schweden FI (HTML)", f"https://marknadssok.fi.se/publiceringsklient/sv-SE/Search/Search?SearchFunctionType=Insyn&Transaktionsdatum.From={D0}&Transaktionsdatum.To={D1}&button=search", None),
    ("Schweiz SER/SIX overview", "https://www.ser-ag.com/sheldon/management_transactions/v1/overview.json?pageSize=20&pageNumber=0&sortAttribute=byDate", None),
    ("Schweiz SIX alt", "https://www.six-group.com/sheldon/management_transactions/v1/overview.json?pageSize=20&pageNumber=0", None),
    ("Frankreich AMF BDIF API", "https://bdif.amf-france.org/back/api/v1/informations?typesInformation=DD&from=0&size=20", None),
    ("Frankreich AMF BDIF API 2", "https://bdif.amf-france.org/back/api/v1/informations?typesDocument=DeclarationDirigeants&from=0&size=20", None),
    ("Indien NSE PIT", f"https://www.nseindia.com/api/corporates-pit?index=equities&from_date={D0dmy}&to_date={D1dmy}", "https://www.nseindia.com/companies-listing/corporate-filings-insider-trading"),
    ("Norwegen Oslo Newsweb", "https://api3.oslo.oslobors.no/v1/newsreader/list?category=1102&fromDate=" + D0 + "&toDate=" + D1, None),
    ("UK Investegate PDMR", "https://www.investegate.co.uk/category/director-pdmr-shareholding", None),
    ("Kanada SEDI", "https://www.sedi.ca/sedi/SVTItdController?locale=en_CA", None),
    ("Hongkong HKEX DI", "https://di.hkex.com.hk/di/NSAllFormList.aspx?sa2=an&sid=1&corpn=&sd=" + D0dmy.replace("-", "/") + "&ed=" + D1dmy.replace("-", "/") + "&cid=0&sa1=da&scsd=&sced=&src=MAIN&lang=EN", None),
    ("Japan EDINET (ohne Schlüssel)", f"https://api.edinet-fsa.go.jp/api/v2/documents.json?date={D1}&type=2", None),
]


def main() -> int:
    s = requests.Session()
    s.headers.update(UA)
    for name, url, warm in CANDIDATES:
        try:
            if warm:
                s.get(warm, timeout=20)
            r = s.get(url, timeout=25)
            body = r.content[:100000]
            try:
                txt = body.decode(r.encoding or "utf-8", errors="replace")
            except Exception:
                txt = body.decode("utf-8", errors="replace")
            print(f"=== {name}: {r.status_code} · {r.headers.get('content-type', '')} · {len(r.content)} Bytes")
            print("    " + " ".join(txt[:700].split())[:700])
        except Exception as exc:
            print(f"=== {name}: FEHLER {exc!r}"[:300])
    return 0


if __name__ == "__main__":
    sys.exit(main())
