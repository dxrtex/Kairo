"""Pflichtprüfung nach dem Scan (Review W13): Nur ein vollständiges, gültiges Ergebnis wird gespeichert und veröffentlicht.

Prüft site/data: Dateien lesbar (JSON), Grundstruktur vorhanden, Kurse für ≥ 85 % des Universums geladen, Suchindex
nicht leer. Exit-Code 1 → der Workflow sichert keinen Zustand und veröffentlicht nicht; die alte Version bleibt online.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "site" / "data"


def check(data: Path = DATA) -> list[str]:
    errs = []

    def load(name):
        try:
            return json.loads((data / name).read_text(encoding="utf-8"))
        except Exception as exc:
            errs.append(f"{name}: nicht lesbar ({exc!r})")
            return None

    res, search, h4 = load("results.json"), load("search.json"), load("h4.json")
    if res is not None:
        st = res.get("stats") or {}
        if not isinstance(res.get("results"), list):
            errs.append("results.json: Liste „results“ fehlt")
        if not res.get("generated"):
            errs.append("results.json: Zeitstempel fehlt")
        u, n = st.get("universe") or 0, st.get("loaded") or 0
        if not u or n / u < 0.85:
            errs.append(f"results.json: nur {n} von {u} Aktien mit Kursen (< 85 %)")
    if search is not None:
        rows = search.get("rows") if isinstance(search, dict) else None
        if not rows or len(rows) < 1000:
            errs.append(f"search.json: Suchindex zu klein ({len(rows or [])})")
    if h4 is not None and not isinstance(h4.get("items"), list):
        errs.append("h4.json: Liste „items“ fehlt")
    return errs


if __name__ == "__main__":
    e = check()
    for x in e:
        print("::error::" + x)
    print("Ergebnis-Prüfung:", "bestanden" if not e else f"{len(e)} Fehler")
    sys.exit(1 if e else 0)
