"""Einmal-Test: onvista-Snapshot des SPDR MSCI ACWI IMI (IE00B3YLTY66) – welche Börsen/Felder (gettex)?"""
import json
import requests
OV = "https://api.onvista.de/api/v1"
H = {"User-Agent": "Mozilla/5.0"}
q = requests.get(f"{OV}/instruments/query?searchValue=IE00B3YLTY66&limit=1", headers=H, timeout=20)
print("query", q.status_code, q.text[:600])
for u in ("/instruments/FUND/ISIN:IE00B3YLTY66/snapshot", "/funds/ISIN:IE00B3YLTY66/snapshot"):
    r = requests.get(OV + u, headers=H, timeout=20)
    print(u, r.status_code)
    if r.ok:
        sn = r.json()
        print("Schlüssel:", list(sn))
        print("quote:", json.dumps(sn.get("quote"), ensure_ascii=False)[:900])
        for m in (sn.get("quoteList") or {}).get("list", []):
            print("MARKT", json.dumps(m, ensure_ascii=False)[:600])
        break
