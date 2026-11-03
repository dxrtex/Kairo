"""Insider-Quellen, Runde 3b: Investegate je Firma (Verlauf 90 Tage?) und Oslo-Text."""
import re, sys, requests
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15", "Accept-Language": "en-GB,en;q=0.9"}
def strip(t): return " ".join(re.sub(r"<[^>]+>", " ", re.sub(r"(?s)<(script|style).*?</\1>", " ", t)).split())
for u in ("https://www.investegate.co.uk/company/LSEG", "https://www.investegate.co.uk/company/SHEL", "https://www.investegate.co.uk/company/LSEG?page=2",
          "https://www.investegate.co.uk/company/BARC/announcements", "https://www.investegate.co.uk/advanced-search/?category=DSH",
          "https://www.investegate.co.uk/archive?date=2026-10-15"):
    try:
        r = requests.get(u, headers=UA, timeout=30)
        rows = re.findall(r'(?s)<tr[^>]*>(.*?)</tr>', r.text)
        pd = [strip(x)[:160] for x in rows if re.search(r"PDMR|Director", x)]
        links = re.findall(r'href="(https://www\.investegate\.co\.uk/announcement/[^"]+)"', r.text)
        print("\n==", u, r.status_code, len(r.text), "rows", len(rows), "links", len(links), "PDMR-Zeilen", len(pd))
        for x in pd[:6]: print("   ", x)
        print("   Ausschnitt:", strip(r.text)[:500])
        print("   pagination:", re.findall(r'href="([^"]*page=\d+[^"]*)"', r.text)[:4])
    except Exception as e: print(u, "FEHLER", e)
