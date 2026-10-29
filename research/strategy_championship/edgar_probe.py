"""Diagnose: welche Header akzeptiert SEC EDGAR von GitHub Actions aus?"""
import gzip
import urllib.request

URLS = ["https://www.sec.gov/files/company_tickers.json", "https://data.sec.gov/api/xbrl/companyconcept/CIK0000320193/dei/EntityPublicFloat.json",
        "https://data.sec.gov/submissions/CIK0000320193.json"]
UAS = ["Kairo Research kairo-research@users.noreply.github.com", "KairoResearch/1.0 (kairo-research@users.noreply.github.com)",
       "Mozilla/5.0 (compatible; KairoResearch/1.0; +https://github.com/dxrtex/Kairo) kairo-research@users.noreply.github.com"]
for u in URLS:
    for ua in UAS:
        for enc in ("gzip, deflate", "identity"):
            h = {"User-Agent": ua, "Accept-Encoding": enc, "Accept": "application/json"}
            try:
                with urllib.request.urlopen(urllib.request.Request(u, headers=h), timeout=20) as r:
                    b = r.read()
                    if r.headers.get("Content-Encoding") == "gzip":
                        b = gzip.decompress(b)
                    print("OK ", r.status, len(b), u, "|", ua[:30], "|", enc)
            except Exception as e:
                print("ERR", e, u, "|", ua[:30], "|", enc)
