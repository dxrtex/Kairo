"""Insider-Test 3c: Originaltexte britischer PDMR-Meldungen (Shell, AstraZeneca) – Abschnitt b) bis e)."""
import re, requests, html
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15"}
for u in ("https://www.investegate.co.uk/announcement/gnw/shell--shel/director-pdmr-shareholding/9706040",
          "https://www.investegate.co.uk/announcement/rns/astrazeneca--azn/director-pdmr-shareholding/9779859",
          "https://www.investegate.co.uk/announcement/rns/astrazeneca--azn/director-pdmr-shareholding/9773534",
          "https://www.investegate.co.uk/company/BP"):
    t = requests.get(u, headers=UA, timeout=30).text
    t = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?s)<(script|style).*?</\1>", " ", t))).split())
    k = t.find("Nature of the transaction")
    print("\n==", u); print(t[max(0, k - 200):k + 2500] if k >= 0 else t[:1500])
