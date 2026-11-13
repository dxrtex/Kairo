"""Hedgefonds-Bewegungen aus den offiziellen SEC-13F-Meldungen – „Smart Money“ wie bei TipRanks, kostenlos.

Große US-Vermögensverwalter (über 100 Mio. USD) müssen jedes Quartal ihre US-Aktienpositionen melden (Formular 13F-HR,
spätestens 45 Tage nach Quartalsende). Kairo liest für eine feste Liste bekannter Fonds die beiden letzten Meldungen,
vergleicht sie (neu, aufgestockt, reduziert, verkauft) und schreibt site/data/funds.json:

    funds: [{name, cik, period, filed, value, n, top: [...], moves: [...]}]     je Fonds
    by:    {ticker: [{f, a, chg, sh, val, w}]}                                   je Aktie (a = neu/auf/ab/raus/halt)
    sum:   {ticker: {buy, sell, new, out, n}}                                    Zusammenfassung je Aktie

Wichtig für die Einordnung: 13F-Daten sind bis zu 45 Tage alt, enthalten nur Long-Positionen in US-Werten und keine
Leerverkäufe – sie zeigen, was große Anleger halten, nicht was sie heute tun. Nur Information, nie Teil der Kairo-Regel.

    python -m backend.hedgefunds            # schreibt site/data/funds.json (und den CUSIP-Cache)
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site" / "data" / "funds.json"
CACHE = ROOT / "data" / "cusip_map.json"
UA = {"User-Agent": f"Kairo Scanner {os.environ.get('SEC_CONTACT', '') or 'github.com/dxrtex/Kairo'}".strip(),
      "Accept-Encoding": "gzip, deflate"}

# Bekannte Fonds (Name, CIK). Der Name aus der SEC-Antwort wird zur Kontrolle mitgeschrieben – passt eine CIK nicht, fällt
# der Fonds einfach heraus (keine 13F-HR-Meldung gefunden).
FUNDS = [
    ("Berkshire Hathaway (Buffett)", 1067983), ("Bridgewater Associates (Dalio)", 1350694),
    ("Renaissance Technologies", 1037389), ("Citadel Advisors (Griffin)", 1423053),
    ("Pershing Square (Ackman)", 1336528), ("Scion Asset Management (Burry)", 1649339),
    ("Appaloosa (Tepper)", 1656456), ("Baupost Group (Klarman)", 1061768),
    ("Tiger Global", 1167483), ("Coatue Management", 1135730), ("Third Point (Loeb)", 1040273),
    ("Duquesne Family Office (Druckenmiller)", 1536411), ("Lone Pine Capital", 1061165),
    ("Viking Global", 1103804), ("Soros Fund Management", 1029160), ("Icahn Capital", 921669),
    ("Greenlight Capital (Einhorn)", 1079114), ("Two Sigma", 1179392), ("D. E. Shaw", 1009207),
    ("Millennium Management", 1273087), ("Point72 (Cohen)", 1603466), ("Altimeter Capital", 1541617),
    ("ValueAct Capital", 1418814), ("Trian Fund (Peltz)", 1345471), ("Maverick Capital", 934639),
    ("Elliott Investment Management", 1791786), ("Fundsmith (Smith)", 1569205), ("Akre Capital", 1112520),
    ("Gotham Asset Management (Greenblatt)", 1510387), ("Polen Capital", 1034524),
]
ACT_DE = {"neu": "neu gekauft", "auf": "aufgestockt", "ab": "reduziert", "raus": "komplett verkauft", "halt": "unverändert"}


def _get(url: str, **kw):
    for i in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=40, **kw)
            if r.status_code == 200:
                return r
            if r.status_code in (403, 404):
                return None
        except requests.RequestException:
            pass
        time.sleep(1.5 * (i + 1))
    return None


def filings(cik: int, k: int = 2) -> tuple[str, list[dict]]:
    """Die letzten k 13F-HR-Meldungen eines Fonds: Name laut SEC + [{acc, filed, period}]."""
    r = _get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
    if not r:
        return "", []
    j = r.json()
    rec = j.get("filings", {}).get("recent", {})
    out = []
    for f, a, d, p in zip(rec.get("form", []), rec.get("accessionNumber", []), rec.get("filingDate", []), rec.get("reportDate", [])):
        if f == "13F-HR" and not any(x["period"] == p for x in out):     # je Quartal die erste (neueste) Meldung
            out.append({"acc": a, "filed": d, "period": p})
        if len(out) >= k:
            break
    return j.get("name", ""), out


def parse_infotable(xml_text: str) -> dict[str, dict]:
    """13F-Infotable → {cusip: {name, sh, val}} (nur Aktien, keine Optionen; Werte in USD)."""
    xml_text = re.sub(r'\sxmlns(:\w+)?="[^"]+"', "", xml_text, count=0)     # Namensräume entfernen
    xml_text = re.sub(r"<(/?)\w+:", r"<\1", xml_text)
    root = ET.fromstring(xml_text)
    out: dict[str, dict] = {}
    for it in root.iter("infoTable"):
        g = lambda tag: (it.findtext(tag) or "").strip()
        if g("putCall"):
            continue
        cus = g("cusip").upper()
        sh_el = it.find("shrsOrPrnAmt")
        if not cus or sh_el is None or (sh_el.findtext("sshPrnamtType") or "SH").strip() != "SH":
            continue
        try:
            sh = float(sh_el.findtext("sshPrnamt") or 0)
            val = float(g("value") or 0)
        except ValueError:
            continue
        x = out.setdefault(cus, {"name": g("nameOfIssuer"), "sh": 0.0, "val": 0.0})
        x["sh"] += sh
        x["val"] += val
    return out


def holdings(cik: int, acc: str) -> dict[str, dict]:
    """Positionen einer Meldung: Infotable-XML aus dem Index der Meldung suchen und lesen."""
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}"
    r = _get(base + "/index.json")
    if not r:
        return {}
    files = [x["name"] for x in r.json().get("directory", {}).get("item", []) if x["name"].lower().endswith(".xml")]
    files.sort(key=lambda n: (("info" not in n.lower() and "table" not in n.lower()), n.lower() == "primary_doc.xml"))
    for fn in files:
        if fn.lower() == "primary_doc.xml":
            continue
        x = _get(f"{base}/{fn}")
        if x is not None:
            try:
                h = parse_infotable(x.text)
                if h:
                    return h
            except ET.ParseError:
                continue
    return {}


def compare(new: dict[str, dict], old: dict[str, dict]) -> list[dict]:
    """Bewegungen zwischen zwei Quartalen: neu, aufgestockt (≥ +5 %), reduziert (≤ −5 %), komplett verkauft, unverändert."""
    tot = sum(x["val"] for x in new.values()) or 1.0
    out = []
    for cus in set(new) | set(old):
        a, b = new.get(cus), old.get(cus)
        if a and not b:
            act, chg = "neu", None
        elif b and not a:
            act, chg = "raus", -1.0
        else:
            chg = a["sh"] / b["sh"] - 1 if b["sh"] else None
            act = "auf" if chg is not None and chg >= .05 else "ab" if chg is not None and chg <= -.05 else "halt"
        x = a or b
        out.append({"cusip": cus, "name": x["name"], "a": act, "chg": None if chg is None else round(chg, 3),
                    "sh": round((a or {}).get("sh", 0)), "val": round((a or {}).get("val", 0)), "w": round((a or {}).get("val", 0) / tot, 4)})
    return out


def map_cusips(cusips: list[str], cache: dict[str, str | None]) -> dict[str, str | None]:
    """CUSIP → US-Ticker über OpenFIGI (kostenlos, ohne Schlüssel 25 Anfragen/Minute à 10 Werte). Ergebnis im Cache."""
    todo = [c for c in dict.fromkeys(cusips) if c not in cache]
    for i in range(0, len(todo), 10):
        chunk = todo[i:i + 10]
        try:
            r = requests.post("https://api.openfigi.com/v3/mapping", json=[{"idType": "ID_CUSIP", "idValue": c, "exchCode": "US"} for c in chunk],
                              headers={"Content-Type": "application/json"}, timeout=30)
            if r.status_code == 429:
                time.sleep(60)
                r = requests.post("https://api.openfigi.com/v3/mapping", json=[{"idType": "ID_CUSIP", "idValue": c, "exchCode": "US"} for c in chunk],
                                  headers={"Content-Type": "application/json"}, timeout=30)
            res = r.json() if r.ok else [{} for _ in chunk]
        except Exception as exc:
            print(f"OpenFIGI: Fehler {exc!r}")
            break
        for c, x in zip(chunk, res):
            d = (x or {}).get("data") or []
            eq = [y for y in d if (y.get("securityType2") or "").startswith("Common") or y.get("marketSector") == "Equity"]
            cache[c] = ((eq or d)[0].get("ticker") if (eq or d) else None)
        time.sleep(2.6)                                   # 25 Anfragen je Minute
    return cache


SUFFIX = re.compile(r"\b(INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LTD|LIMITED|PLC|SA|NV|AG|SE|HLDGS?|HOLDINGS?|GROUP|GRP|THE|CL(ASS)? ?[A-C]|COM|NEW|DEL|ORD|SHS|ADR|SPONSORED|REIT|TR|TRUST|LP|LLC)\b")


def norm(name: str) -> str:
    n = re.sub(r"[^A-Z0-9 ]", " ", str(name).upper().replace("&", " AND "))
    return re.sub(r"\s+", " ", SUFFIX.sub(" ", n)).strip()


def name_map() -> dict[str, str]:
    """Firmenname (normalisiert) → Ticker aus der SEC-Liste company_tickers.json (eine Anfrage, ~10.000 US-Werte)."""
    r = _get("https://www.sec.gov/files/company_tickers.json")
    out: dict[str, str] = {}
    if not r:
        return out
    for x in r.json().values():
        k = norm(x.get("title", ""))
        if k and k not in out:                         # erste Zeile = Hauptgattung (SEC-Reihenfolge nach Größe)
            out[k] = x.get("ticker")
    return out


def build(sleep: float = .15) -> dict:
    cache = {}
    if CACHE.exists():
        try:
            cache = json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:
            cache = {}
    funds, moves_all = [], []
    for name, cik in FUNDS:
        sec_name, fl = filings(cik)
        time.sleep(sleep)
        if len(fl) < 1:
            print(f"{name}: keine 13F-HR-Meldung (CIK {cik})")
            continue
        new = holdings(cik, fl[0]["acc"]); time.sleep(sleep)
        old = holdings(cik, fl[1]["acc"]) if len(fl) > 1 else {}; time.sleep(sleep)
        if not new:
            print(f"{name}: Meldung ohne lesbare Positionen")
            continue
        mv = compare(new, old)
        tot = sum(x["val"] for x in new.values())
        top = sorted([m for m in mv if m["a"] != "raus"], key=lambda m: -m["val"])[:25]
        chg = sorted([m for m in mv if m["a"] in ("neu", "auf", "ab", "raus")],
                     key=lambda m: -(m["val"] if m["a"] != "raus" else (old.get(m["cusip"], {}).get("val", 0))))[:40]
        funds.append({"name": name, "sec": sec_name, "cik": cik, "period": fl[0]["period"], "filed": fl[0]["filed"],
                      "prev": fl[1]["period"] if len(fl) > 1 else None, "value": round(tot), "n": len(new), "top": top, "moves": chg})
        moves_all += [(name, m) for m in mv if (m["a"] != "halt" or m["w"] >= .01) and (m["w"] >= .0005 or (m["a"] == "raus" and old.get(m["cusip"], {}).get("val", 0) >= .0005 * sum(x["val"] for x in old.values())))]
        print(f"{name}: {sec_name} · {fl[0]['period']} · {len(new)} Positionen · {tot / 1e9:,.1f} Mrd. USD · {len(chg)} Bewegungen")
    # Ticker zuordnen: zuerst über den Firmennamen (SEC-Liste, sofort), OpenFIGI nur für die wichtigsten offenen Fälle
    # (Top-Positionen und große Bewegungen) – die Gratis-Grenze von 25 Anfragen/Minute reicht sonst bei Quant-Fonds nicht
    names = name_map()
    print(f"SEC-Namensliste: {len(names)} Werte")
    allm = {m["cusip"]: m["name"] for _, m in moves_all} | {m["cusip"]: m["name"] for f in funds for m in f["top"] + f["moves"]}
    for cus, nm in allm.items():
        if cus not in cache or cache[cus] is None:
            t = names.get(norm(nm))
            if t:
                cache[cus] = t
    key = [m["cusip"] for f in funds for m in f["top"] + f["moves"] if not cache.get(m["cusip"])]
    key = list(dict.fromkeys(key))[:400]
    print(f"Zuordnung: {sum(1 for c in allm if cache.get(c))} von {len(allm)} über Namen/Cache, OpenFIGI für {len(key)}")
    cache = map_cusips(key, cache)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, separators=(",", ":")), encoding="utf-8")
    for f in funds:
        for m in f["top"] + f["moves"]:
            m["t"] = cache.get(m["cusip"])
    by: dict[str, list] = {}
    for fname, m in moves_all:
        t = cache.get(m["cusip"])
        if not t:
            continue
        by.setdefault(t, []).append({"f": fname, "n": m["name"].title()[:40], "a": m["a"], "chg": m["chg"], "sh": m["sh"], "val": m["val"], "w": m["w"]})
    summ = {}
    for t, xs in by.items():
        xs.sort(key=lambda x: -x["val"])
        summ[t] = {"buy": sum(x["a"] in ("neu", "auf") for x in xs), "sell": sum(x["a"] in ("ab", "raus") for x in xs),
                   "new": sum(x["a"] == "neu" for x in xs), "out": sum(x["a"] == "raus" for x in xs), "n": sum(x["a"] != "raus" for x in xs)}
    periods = sorted({f["period"] for f in funds})
    return {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "period": periods[-1] if periods else None,
            "funds": funds, "by": by, "sum": summ}


def main() -> None:
    d = build()
    if len(d["funds"]) < 5:
        print(f"Nur {len(d['funds'])} Fonds gelesen – nichts geschrieben (SEC_CONTACT gesetzt?)", file=sys.stderr)
        sys.exit(1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"funds.json: {len(d['funds'])} Fonds, {len(d['by'])} Aktien")


if __name__ == "__main__":
    main()
