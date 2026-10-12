"""Probe: Eigengeschäfte von Führungskräften (Directors' Dealings, Art. 19 MAR) aus der BaFin-Datenbank."""

from __future__ import annotations

import requests

BASE = "https://portal.mvp.bafin.de/database/DealingsInfo/sucheForm.do"


def probe(isin: str = "DE0007030009") -> None:
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 (Kairo Scanner)"
    for label, params in (("html", {"emittentIsin": isin, "zeitraum": "0", "meldepflichtigerName": "", "emittentName": "", "zeitraumVon": "", "zeitraumBis": "", "emittentButton": "Suche Emittent"}),
                          ("csv", {"emittentIsin": isin, "zeitraum": "0", "meldepflichtigerName": "", "emittentName": "", "zeitraumVon": "", "zeitraumBis": "", "emittentButton": "Suche Emittent", "d-4000784-e": "1", "6578706f7274": "1"})):
        try:
            r = s.get(BASE, params=params, timeout=30)
            print(f"BaFin {label}: Status {r.status_code}, {len(r.text)} Zeichen, Typ {r.headers.get('content-type')}")
            print(r.text[:1500].replace("\n", " ")[:1500])
            if "<table" in r.text:
                i = r.text.find('<table id="result"')
                print("TABELLE:", r.text[i:i + 3000].replace("\n", " ") if i >= 0 else r.text[r.text.find("<table"):r.text.find("<table") + 2000])
        except Exception as exc:
            print(f"BaFin {label}: {exc!r}")


if __name__ == "__main__":
    probe()
