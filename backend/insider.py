"""Insider-Geschäfte aus den offiziellen SEC-Meldungen (Formular 4, EDGAR) – für den Nachrichtenbereich der App.

Holt die neuesten Formular-4-Meldungen (Vorstände, Aufsichtsräte, Großaktionäre), liest Käufe und Verkäufe über die
Börse (Code P = Kauf, S = Verkauf) und schreibt die bedeutenden nach site/data/insider.json.
Käufe aus eigener Tasche sind das stärkere Signal: Insider verkaufen aus vielen Gründen, kaufen aber nur aus einem.

    python -m backend.insider            # druckt die Liste (Test)

Politiker-Geschäfte (US-Kongress) gibt es nicht als freie, verlässliche Quelle – Quiver Quant & Co. sind kostenpflichtig.
"""

from __future__ import annotations

import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests

UA = {"User-Agent": "KairoScanner/1.0 (+https://github.com/dxrtex/Kairo)", "Accept-Encoding": "gzip, deflate"}
FEED = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&owner=include&count=100&start={start}&output=atom"
MIN_BUY, MIN_SELL = 50_000, 1_000_000                 # USD: kleinere Käufe/Verkäufe sind Rauschen


def _t(el, path):
    x = el.find(path)
    return (x.text or "").strip() if x is not None and x.text else ""


def parse_form4(xml_text: str) -> list[dict]:
    """Börsengeschäfte (Code P/S) aus einem Formular-4-XML. Leere Liste, wenn nichts Passendes drin ist."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    sym = _t(root, "issuer/issuerTradingSymbol").upper()
    name = _t(root, "issuer/issuerName")
    owner = _t(root, "reportingOwner/reportingOwnerId/rptOwnerName")
    rel = root.find("reportingOwner/reportingOwnerRelationship")
    role = ""
    if rel is not None:
        title = _t(rel, "officerTitle")
        role = title or ("Direktor" if _t(rel, "isDirector") in ("1", "true") else "Großaktionär (10 %)" if _t(rel, "isTenPercentOwner") in ("1", "true") else "")
    out = []
    for tx in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
        code = _t(tx, "transactionCoding/transactionCode")
        if code not in ("P", "S"):
            continue
        try:
            sh = float(_t(tx, "transactionAmounts/transactionShares/value") or 0)
            px = float(_t(tx, "transactionAmounts/transactionPricePerShare/value") or 0)
        except ValueError:
            continue
        if sh <= 0 or px <= 0:
            continue
        out.append({"t": sym, "n": name, "who": owner.title(), "role": role, "kind": "buy" if code == "P" else "sell",
                    "d": _t(tx, "transactionDate/value")[:10], "sh": round(sh), "px": round(px, 2), "val": round(sh * px)})
    return out


def _merge(rows: list[dict]) -> list[dict]:
    """Mehrere Teil-Geschäfte derselben Person am selben Tag zu einem zusammenfassen."""
    acc = {}
    for r in rows:
        k = (r["t"], r["who"], r["kind"], r["d"])
        if k in acc:
            a = acc[k]
            a["val"] += r["val"]; a["sh"] += r["sh"]; a["px"] = round(a["val"] / a["sh"], 2)
        else:
            acc[k] = dict(r)
    return list(acc.values())


def fetch(pages: int = 3, budget_s: float = 150) -> dict:
    t0, s = time.time(), requests.Session()
    s.headers.update(UA)
    rows = []
    links = []
    for pg in range(pages):
        try:
            feed = s.get(FEED.format(start=pg * 100), timeout=20).text
        except Exception as exc:                    # Netz/Sperre – Scan läuft trotzdem weiter
            print("Insider: Feed nicht erreichbar", repr(exc)[:100])
            break
        links += re.findall(r'<link[^>]+href="(https://www\.sec\.gov/Archives/edgar/data/[^"]+-index\.htm)"', feed)
    seen = set()
    for url in links:
        if time.time() - t0 > budget_s:
            break
        base = url.rsplit("/", 1)[0]
        if base in seen:
            continue
        seen.add(base)
        try:
            idx = s.get(base + "/index.json", timeout=15).json()
            xmlf = next((i["name"] for i in idx.get("directory", {}).get("item", []) if i["name"].endswith(".xml") and not i["name"].startswith("xsl")), None)
            if not xmlf:
                continue
            for r in parse_form4(s.get(f"{base}/{xmlf}", timeout=15).text):
                r["url"] = url
                rows.append(r)
            time.sleep(0.12)                        # SEC: höchstens ~10 Abfragen pro Sekunde
        except Exception:
            continue
    rows = _merge(rows)
    buys = sorted([r for r in rows if r["kind"] == "buy" and r["val"] >= MIN_BUY], key=lambda r: -r["val"])
    sells = sorted([r for r in rows if r["kind"] == "sell" and r["val"] >= MIN_SELL], key=lambda r: -r["val"])
    return {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "filings": len(seen),
            "buys": buys[:60], "sells": sells[:40], "source": "SEC EDGAR Formular 4"}


def main(argv=None) -> int:
    res = fetch()
    print(f"Insider: {res['filings']} Meldungen, {len(res['buys'])} Käufe, {len(res['sells'])} Verkäufe")
    print("===BEGIN===")
    print(json.dumps({**res, "buys": res["buys"][:15], "sells": res["sells"][:8]}, ensure_ascii=False))
    print("===END===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
