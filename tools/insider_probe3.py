"""Test 3e: L&G – Preis/Volumen-Abschnitt im Original."""
import re, html, requests
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15"}
def strip(t): return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?s)<(script|style).*?</\1>", " ", t))).split())
for u in ("https://www.investegate.co.uk/announcement/rns/legal-general-group--lgen/director-pdmr-shareholding/9854351",
          "https://www.investegate.co.uk/announcement/rns/legal-general-group--lgen/director-pdmr-shareholding/9750279"):
    t = strip(requests.get(u, headers=UA, timeout=30).text)
    for m in re.finditer(r"Nature of the transaction", t):
        print("\n==", u.split("/")[-1], "@", m.start()); print(t[m.start(): m.start() + 700])
