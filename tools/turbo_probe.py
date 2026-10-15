"""Probe: Turbo-Daten (Kurs, K.-o., Hebel, Basiswert) per WKN/ISIN über die onvista-API."""
import json
import re
import sys

import requests

H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
API = "https://api.onvista.de/api/v1"


def get(url):
    try:
        r = requests.get(url, headers=H, timeout=20)
        print("GET", url, "→", r.status_code, len(r.text))
        return r.json() if r.ok else None
    except Exception as exc:
        print("GET", url, "Fehler", repr(exc)[:200])
        return None


def walk(x, path=""):
    if isinstance(x, dict):
        for k, v in x.items():
            yield from walk(v, f"{path}.{k}")
    elif isinstance(x, list):
        for i, v in enumerate(x[:30]):
            yield from walk(v, f"{path}[{i}]")
    else:
        yield path, x


def snapshot(q):
    j = get(f"{API}/instruments/query?searchValue={requests.utils.quote(q)}&limit=3")
    it = ((j or {}).get("list") or [None])[0]
    if not it:
        return None, None
    return it, get(f"{API}/instruments/{it['entityType']}/{it['entityValue']}/snapshot")


ids = [a for x in sys.argv[1:] for a in x.split()] or ["703000"]
for q in ids:
    it, s = snapshot(q)
    print("==", q, it and (it["entityType"], it.get("name")))
    if not s:
        continue
    # alle Derivate, die irgendwo im Snapshot vorkommen (z. B. Turbo-Box der Aktie)
    ders = sorted({(p, v) for p, v in walk(s) if re.search(r"entityType$", p) and v not in ("STOCK", "INDEX", "FUND")})
    print("Derivat-Typen im Snapshot:", ders[:10])
    wk = [v for p, v in walk(s) if p.endswith(".wkn") and isinstance(v, str)]
    print("WKNs im Snapshot:", wk[:15])
    for p, v in walk(s):
        if re.search(r"knock|barrier|strike|leverage|lever|ratio|cap|underlying|gearing|nameUnderlying|issuer", p, re.I):
            print("  ", p, "=", v)
    # ersten Turbo/Optionsschein aus dem Aktien-Snapshot genauer ansehen
    if it["entityType"] == "STOCK":
        for w in wk:
            if w != it.get("wkn"):
                it2, s2 = snapshot(w)
                if it2 and it2["entityType"] not in ("STOCK",):
                    print("== Derivat", w, it2["entityType"], it2.get("name"))
                    for p, v in walk(s2):
                        if re.search(r"knock|barrier|strike|leverage|ratio|underlying|bid|ask|last|issuer|subType|name$|currency", p, re.I):
                            print("  ", p, "=", v)
                    break
