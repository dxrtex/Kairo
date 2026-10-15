"""Probe: alle Daten der onvista-API zu einer WKN/ISIN (Turbo) ausgeben – Feldnamen für K.-o., Bezugsverhältnis, Kurs."""
import json
import sys

import requests

H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
API = "https://api.onvista.de/api/v1"


def get(url):
    try:
        r = requests.get(url, headers=H, timeout=20)
        print("GET", url, "→", r.status_code, len(r.text), flush=True)
        return r.json() if r.ok else None
    except Exception as exc:
        print("GET", url, "Fehler", repr(exc)[:200])
        return None


def walk(x, path=""):
    if isinstance(x, dict):
        for k, v in x.items():
            yield from walk(v, f"{path}.{k}")
    elif isinstance(x, list):
        for i, v in enumerate(x[:4]):
            yield from walk(v, f"{path}[{i}]")
    else:
        yield path, x


for q in [a for x in sys.argv[1:] for a in x.split()]:
    j = get(f"{API}/instruments/query?searchValue={q}&limit=3")
    print(json.dumps(j, ensure_ascii=False)[:1500])
    for it in ((j or {}).get("list") or [])[:1]:
        typ, ev = it["entityType"], it["entityValue"]
        for path in (f"instruments/{typ}/{ev}/snapshot", f"derivatives/{ev}/snapshot", f"instruments/{typ}/ISIN:{it.get('isin')}/snapshot"):
            s = get(f"{API}/{path}")
            if not s:
                continue
            print("==== ", path)
            for p, v in walk(s):
                if "quoteList" in p or "logo" in p.lower() or "urls" in p:
                    continue
                print("  ", p, "=", str(v)[:120])
            break
