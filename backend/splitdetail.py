"""Tempo (18.11.2026): fund.json und fin.json für die App aufteilen – nur Auslieferung, an den Daten ändert sich nichts.

Vorher lud die App beim Start 5,7 MB fund.json und beim ersten Unternehmen 4,5 MB fin.json. Jetzt:
  · site/data/fund.json   schlank: nur Kennzahlen je Aktie (für Screener, Schneeflocke, fairen Wert)
  · site/data/co/NNN.json 128 kleine Dateien mit den Details je Aktie, die erst beim Öffnen einer Aktie geladen werden:
                          eh (Gewinn je Quartal), ih (Umsatz/Gewinn je Jahr), ud (Analysten-Einstufungen),
                          qh (Umsatz je Quartal), pm (Monatskurse 12 Jahre), fin (SEC-Jahreszahlen und Meldungen; außerhalb der USA Yahoo-Jahresberichte „fa“)
  · site/data/fin.json    entfällt (steckt komplett in den Detaildateien)
Die Datei einer Aktie: bucket(ticker) – dieselbe Rechnung steht in site/index.html (detB).

    python -m backend.splitdetail [site/data]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

DET_N = 128
FIELDS = ("eh", "ih", "ud", "qh", "fa", "pm")


def bucket(t: str) -> int:
    """Ticker → Nummer der Detaildatei. Punkt, Bindestrich und ~ zählen nicht (BRK-B und BRK.B landen in derselben Datei)."""
    h = 0
    for c in re.sub(r"[.\-~]", "", str(t).upper()):
        h = (h * 31 + ord(c)) & 0xFFFFFFFF
    return h % DET_N


def split(fund: dict | None, fin: dict | None) -> tuple[dict | None, dict]:
    """→ (schlanke fund.json, {nummer: {ticker: {eh, ih, ud, qh, fin}}})."""
    det: dict = {}
    if fund and isinstance(fund.get("by"), dict):
        by = {}
        for t, v in fund["by"].items():
            x = {k: v[k] for k in FIELDS if k in v}
            by[t] = {k: w for k, w in v.items() if k not in FIELDS}
            if x:
                det.setdefault(bucket(t), {}).setdefault(t, {}).update(x)
        fund = {**fund, "by": by, "det": DET_N}
    if fin and isinstance(fin.get("by"), dict):
        for t, v in fin["by"].items():
            det.setdefault(bucket(t), {}).setdefault(t, {})["fin"] = v
    for b in det.values():                             # außerhalb der USA: Jahrestabelle aus Yahoo (fa), wenn die SEC nichts hat
        for x in b.values():
            fa = x.pop("fa", None)
            if fa and "fin" not in x:
                x["fin"] = fa
    return fund, det


def main(argv=None) -> int:
    d = Path((argv if argv is not None else sys.argv[1:] or ["site/data"])[0])
    fp, np_ = d / "fund.json", d / "fin.json"
    fund = json.loads(fp.read_text()) if fp.exists() else None
    fin = json.loads(np_.read_text()) if np_.exists() else None
    if fund is None and fin is None:
        print("Keine fund.json / fin.json – nichts aufzuteilen")
        return 0
    if fund is not None and fund.get("det"):
        print("fund.json ist schon aufgeteilt")
        return 0
    slim, det = split(fund, fin)
    out = d / "co"
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.json"):
        old.unlink()
    meta = {"generated": (fund or fin or {}).get("generated"), "fin": (fin or {}).get("generated")}
    for i in range(DET_N):
        (out / f"{i:03d}.json").write_text(json.dumps({**meta, "by": det.get(i, {})}, ensure_ascii=False, separators=(",", ":")))
    if slim is not None:
        fp.write_text(json.dumps(slim, ensure_ascii=False, separators=(",", ":")))
    if np_.exists():
        np_.unlink()
    sizes = sorted(p.stat().st_size for p in out.glob("*.json"))
    print(f"fund.json {fp.stat().st_size / 1e6:.1f} MB · {len(sizes)} Detaildateien, je {sizes[0] / 1e3:.0f}–{sizes[-1] / 1e3:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
