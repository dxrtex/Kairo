"""Probe: alle Daten der onvista-API zu einer WKN/ISIN (Turbo) ausgeben – Feldnamen für K.-o., Bezugsverhältnis, Kurs."""
import json
import re
import sys

import requests

H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
API = "https://api.onvista.de/api/v1"
NOISE = re.compile(r"topBroker|logo|urls|\.chart\.|\.quote\.|cnPerformance|finderUnderlying|derivativesUnderlyingList\.list\[\d\]\.(chart|quote)", re.I)
HIT = re.compile(r"knock|barrier|ratio|cover|strike|leverage|hebel|direction|underly|financing|stoploss|bezug", re.I)


def get(url, js=True):
    try:
        r = requests.get(url, headers=H, timeout=20)
        print("GET", url, "→", r.status_code, len(r.text), flush=True)
        if not r.ok:
            return None
        return r.json() if js else r.text
    except Exception as exc:
        print("GET", url, "Fehler", repr(exc)[:200])
        return None


def walk(x, path=""):
    if isinstance(x, dict):
        for k, v in x.items():
            yield from walk(v, f"{path}.{k}")
    elif isinstance(x, list):
        for i, v in enumerate(x[:3]):
            yield from walk(v, f"{path}[{i}]")
    else:
        yield path, x


for q in [a for x in sys.argv[1:] for a in x.split()]:
    j = get(f"{API}/instruments/query?searchValue={q}&limit=3")
    for it in ((j or {}).get("list") or [])[:1]:
        typ, ev, sub, isin = it["entityType"], it["entityValue"], it.get("entitySubType"), it.get("isin")
        paths = [f"derivatives/{ev}/snapshot", f"derivatives/{sub}/{ev}/snapshot", f"instruments/{typ}/{ev}/details",
                 f"derivatives/{ev}/details", f"derivatives/{ev}", f"instruments/{typ}/{ev}",
                 f"derivatives/ISIN:{isin}/snapshot", f"instruments/{typ}/{ev}/snapshot?withDetails=true",
                 f"derivatives/{ev}/keyFigures", f"derivatives/{ev}/master_data"]
        for path in paths:
            s = get(f"{API}/{path}")
            if not s:
                continue
            print("==== ", path)
            for p, v in walk(s):
                if HIT.search(p) or "derivative" in p.lower():
                    print("  *", p, "=", str(v)[:120])
        url = (it.get("urls") or {}).get("WEBSITE")
        html = get(url, js=False) if url else None
        if html:
            m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
            if m:
                nd = json.loads(m.group(1))
                for p, v in walk(nd):
                    if HIT.search(p) and not NOISE.search(p):
                        print("  NEXT", p, "=", str(v)[:120])
            for u in sorted(set(re.findall(r"api\.onvista\.de/api/v1/[A-Za-z0-9_/{}.:-]+", html)))[:40]:
                print("  API-URL", u)
