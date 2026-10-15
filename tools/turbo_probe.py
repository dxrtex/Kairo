"""Probe: Lassen sich Turbo-Daten (Kurs, K.-o., Hebel, Basiswert) frei per WKN/ISIN abrufen? (onvista-API)"""
import json
import sys

import requests

H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def get(url):
    try:
        r = requests.get(url, headers=H, timeout=20)
        print("GET", url, "→", r.status_code, len(r.text))
        return r.json() if r.ok else None
    except Exception as exc:
        print("GET", url, "Fehler", repr(exc)[:200])
        return None


def short(x, n=2500):
    return json.dumps(x, ensure_ascii=False)[:n]


for q in sys.argv[1:] or ["Rheinmetall Turbo Long", "Nvidia Turbo"]:
    j = get(f"https://api.onvista.de/api/v1/instruments/query?searchValue={requests.utils.quote(q)}&limit=5")
    print(short(j, 1500))
    items = (j or {}).get("list") or []
    for it in items[:2]:
        ev, typ = it.get("entityValue"), it.get("entityType")
        print("Treffer:", typ, it.get("wkn"), it.get("isin"), it.get("name"), ev)
        for path in (f"derivatives/{ev}/snapshot", f"derivatives/ISIN:{it.get('isin')}/snapshot", f"instruments/{typ}/{ev}/snapshot"):
            s = get(f"https://api.onvista.de/api/v1/{path}")
            if s:
                print(short(s, 4000))
                break
    # direkte Abfrage per WKN/ISIN
    if items:
        w = items[0].get("wkn")
        print(short(get(f"https://api.onvista.de/api/v1/instruments/query?searchValue={w}&limit=1"), 800))
