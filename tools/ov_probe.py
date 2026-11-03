"""Einmal-Test: onvista-Snapshot des SPDR MSCI ACWI IMI (IE00B3YLTY66) – welche Börsen/Felder (gettex)?"""
import json
import requests
OV = "https://api.onvista.de/api/v1"
q = requests.get(f"{OV}/instruments/query?searchValue=IE00B3YLTY66&limit=1", timeout=20).json()
it = q["list"][0]
print("Treffer:", it.get("entityType"), it.get("entityValue"), it.get("name"))
sn = requests.get(f"{OV}/instruments/{it['entityType']}/{it['entityValue']}/snapshot", timeout=20).json()
print("Schlüssel:", list(sn))
print("quote:", json.dumps(sn.get("quote"), ensure_ascii=False)[:800])
for m in (sn.get("quoteList") or {}).get("list", []):
    print("MARKT", json.dumps({k: m.get(k) for k in ("market", "last", "previousLast", "performancePct", "datetimeLast", "bid", "ask", "isoCurrency", "idNotation")}, ensure_ascii=False)[:400])
