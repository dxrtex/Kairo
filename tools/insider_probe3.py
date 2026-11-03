"""Test 3d: Originaltexte der Ausreißer (Oslo, UK) – Abschnitt rund um Preis/Volumen."""
import re, html, requests
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15"}
def strip(t): return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?s)<(script|style).*?</\1>", " ", t))).split())
for mid in ("680907", "679629", "682835", "681457"):
    msg = (requests.get(f"https://api3.oslo.oslobors.no/v1/newsreader/message?messageId={mid}", headers=UA, timeout=30).json().get("data") or {}).get("message") or {}
    print("\n== OSLO", mid, msg.get("issuerSign"), msg.get("title")); print(strip(msg.get("body") or "")[:1500])
for u in ("https://www.investegate.co.uk/announcement/rns/legal-general-group--lgen/director-pdmr-shareholding/9854351",
          "https://www.investegate.co.uk/announcement/prn/rightmove--rmv/director-pdmr-shareholding/9834525",
          "https://www.investegate.co.uk/announcement/rns/seplat-energy-di---sepl/director-pdmr-shareholding/9800105",
          "https://www.investegate.co.uk/announcement/rns/canal-sa--can/director-pdmr-shareholding/9816570"):
    t = strip(requests.get(u, headers=UA, timeout=30).text); k = t.find("Nature of the transaction")
    print("\n== UK", u.split("/")[-3]); print(t[max(0, k - 300):k + 1300] if k >= 0 else t[:1500])
