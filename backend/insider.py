"""Insider-Geschäfte aus den offiziellen SEC-Meldungen (Formular 4, EDGAR) – für den Nachrichtenbereich der App.

Holt die neuesten Formular-4-Meldungen (Vorstände, Aufsichtsräte, Großaktionäre), liest Käufe und Verkäufe über die
Börse (Code P = Kauf, S = Verkauf) und schreibt die bedeutenden nach site/data/insider.json.
Käufe aus eigener Tasche sind das stärkere Signal: Insider verkaufen aus vielen Gründen, kaufen aber nur aus einem.

    python -m backend.insider            # druckt die Liste (Test)

Politiker-Geschäfte (US-Kongress) gibt es nicht als freie, verlässliche Quelle – Quiver Quant & Co. sind kostenpflichtig.
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests

# SEC verlangt „Name echte-Kontakt-E-Mail“ im User-Agent (sonst 403). Ohne Secret SEC_CONTACT nutzt Kairo OpenInsider –
# dieselben Formular-4-Meldungen, frei abrufbar und schon aufbereitet.
UA = {"User-Agent": f"Kairo Scanner {os.environ.get('SEC_CONTACT', '')}".strip(), "Accept-Encoding": "gzip, deflate"}
OI = {"buy": "http://openinsider.com/latest-insider-purchases-25k", "sell": "http://openinsider.com/latest-insider-sales-100k"}
SCREEN = "http://openinsider.com/screener?s={t}&fd=180&xp=1&xs=1&cnt=40"   # je Aktie: Käufe + Verkäufe, 180 Tage
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


def _cells(row: str) -> list[str]:
    # Tags samt Attributen entfernen – auch wenn ein Attribut (Tooltip) selbst „>“ enthält
    return [re.sub(r"\s+", " ", html.unescape(re.sub(r"""<(?:[^>"']|"[^"]*"|'[^']*')*>""", " ", c))).strip()
            for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]


def _num_us(x: str) -> float:
    try:
        return float(re.sub(r"[^0-9.\-]", "", x) or 0)
    except ValueError:
        return 0.0


def parse_openinsider(page: str) -> list[dict]:
    """Tabelle „tinytable“ von OpenInsider → Geschäfte. Spalten über die Überschriften zugeordnet (robust gegen Umbauten)."""
    m = re.search(r'<table[^>]*class="tinytable"[^>]*>(.*?)</table>', page, re.S)
    if not m:
        return []
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(1), re.S)
    if not rows:
        return []
    head = [h.replace("\xa0", " ").lower() for h in _cells(rows[0])]
    col = lambda *names: next((i for i, h in enumerate(head) if any(h.startswith(n) for n in names)), None)
    ix = {k: col(*v) for k, v in {"t": ("ticker",), "n": ("company",), "who": ("insider",), "role": ("title",), "type": ("trade type",),
                                    "d": ("trade date",), "px": ("price",), "sh": ("qty",), "val": ("value",)}.items()}
    if ix["t"] is None or ix["type"] is None:
        return []
    out = []
    for r in rows[1:]:
        c = _cells(r)
        if len(c) < len(head):
            continue
        g = lambda k: c[ix[k]] if ix[k] is not None else ""
        kind = "buy" if g("type").startswith("P") else "sell" if g("type").startswith("S") else None
        val, px = abs(_num_us(g("val"))), _num_us(g("px"))
        tk = (re.findall(r"[A-Z][A-Z0-9.\-]{0,7}", g("t").upper()) or [""])[-1]
        if not kind or not tk or val <= 0 or px <= 0 or px > 1e5 or val >= 2e9:   # Meldefehler (Wert am Zahlen-Höchstwert 2^31) auslassen
            continue
        out.append({"t": tk, "n": g("n"), "who": g("who"), "role": g("role"), "kind": kind, "d": g("d")[:10],
                    "sh": round(abs(_num_us(g("sh")))), "px": round(px, 2), "val": round(val),
                    "url": f"http://openinsider.com/{tk}"})
    return out


def fetch_openinsider() -> list[dict]:
    rows = []
    for kind, url in OI.items():
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Kairo Scanner)"}, timeout=25)
            got = parse_openinsider(r.text)
            print(f"Insider (OpenInsider {kind}): Status {r.status_code}, {len(got)} Geschäfte")
            rows += got
        except Exception as exc:
            print(f"Insider (OpenInsider {kind}): nicht erreichbar {exc!r}"[:160])
    return rows


def fetch_watch(watch: dict[str, str], budget_s: float = 120) -> tuple[list[dict], int]:
    """Gezielt für die Watchlist: Insider-Käufe und -Verkäufe je US-Aktie der letzten 6 Monate (OpenInsider-Screener).
    Nur US-Börsenkürzel (ohne Punkt) – europäische und asiatische Werte melden nicht an die SEC."""
    t0, rows, done = time.time(), [], 0
    for t, name in watch.items():
        if "." in t or "^" in t or time.time() - t0 > budget_s:
            continue
        try:
            r = requests.get(SCREEN.format(t=t), headers={"User-Agent": "Mozilla/5.0 (Kairo Scanner)"}, timeout=20)
            got = [x for x in parse_openinsider(r.text) if x["t"] == t]
            done += 1
            for x in _merge(got):
                if x["val"] >= (25_000 if x["kind"] == "buy" else 1_000_000):   # Mini-Käufe (Sparpläne) und Routine-Verkäufe auslassen
                    rows.append({**x, "n": x.get("n") or name, "url": f"http://openinsider.com/{t}"})
            time.sleep(0.4)
        except Exception as exc:
            print(f"Insider Watchlist {t}: {exc!r}"[:140])
    buys = sorted([x for x in rows if x["kind"] == "buy"], key=lambda x: -x["val"])
    sells = sorted([x for x in rows if x["kind"] == "sell"], key=lambda x: -x["val"])[:40]
    rows = buys[:120] + sells
    print(f"Insider Watchlist: {done} Aktien geprüft, {sum(x['kind'] == 'buy' for x in rows)} Käufe, {sum(x['kind'] == 'sell' for x in rows)} Verkäufe")
    return rows, done


def fetch(pages: int = 3, budget_s: float = 150, watch: dict[str, str] | None = None) -> dict:
    t0, s = time.time(), requests.Session()
    s.headers.update(UA)
    rows = []
    links = []
    sec = "@" in UA["User-Agent"]
    for pg in range(pages if sec else 0):
        try:
            resp = s.get(FEED.format(start=pg * 100), timeout=20)
            feed = resp.text
        except Exception as exc:                    # Netz/Sperre – Scan läuft trotzdem weiter
            print("Insider: Feed nicht erreichbar", repr(exc)[:100])
            break
        found = re.findall(r'href="((?:https://www\.sec\.gov)?/Archives/edgar/data/[^"]+-index\.html?)"', feed)
        if pg == 0:
            print(f"Insider: Feed Status {resp.status_code}, {len(feed)} Zeichen, {len(found)} Links" + ("" if found else f" · Anfang: {feed[:160]!r}"))
        links += [u if u.startswith("http") else "https://www.sec.gov" + u for u in found]
        if not found:
            break
    seen, errs = set(), 0
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
        except Exception as exc:
            errs += 1
            if errs <= 2:
                print("Insider: Meldung nicht lesbar", url, repr(exc)[:120])
            continue
    src = "SEC EDGAR Formular 4"
    if not rows:                                     # ohne SEC-Kontakt oder bei Sperre: OpenInsider (gleiche Meldungen)
        rows, src = fetch_openinsider(), "OpenInsider (SEC Formular 4)"
    rows = _merge(rows)
    buys = sorted([r for r in rows if r["kind"] == "buy" and r["val"] >= MIN_BUY], key=lambda r: -r["val"])
    sells = sorted([r for r in rows if r["kind"] == "sell" and r["val"] >= MIN_SELL], key=lambda r: -r["val"])
    out = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "filings": len(seen) or len(rows),
           "buys": buys[:60], "sells": sells[:40], "source": src}
    if watch:
        out["watch"], out["watch_n"] = fetch_watch(watch)
        try:                                        # deutsche Werte: Directors' Dealings der BaFin
            from . import bafin
            de = bafin.fetch(watch)
            out["watch"] += [{**x, "url": f"{bafin.BASE}?emittentIsin={x['isin']}&zeitraum=0&emittentButton=Suche+Emittent"} for x in de["rows"]]
            out["watch_de_n"] = de["n"]
        except Exception as exc:
            print(f"BaFin: Fehler {exc!r}"[:160])
    return out


def main(argv=None) -> int:
    from .run_scan import load_watchlist
    res = fetch(watch=load_watchlist())
    print(f"Insider: {res['filings']} Meldungen, {len(res['buys'])} Käufe, {len(res['sells'])} Verkäufe")
    print("===BEGIN===")
    print(json.dumps({**res, "buys": res["buys"][:15], "sells": res["sells"][:8], "watch": res.get("watch", [])[:40]}, ensure_ascii=False))
    print("===END===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
