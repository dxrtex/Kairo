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
SCREEN = "http://openinsider.com/screener?s={t}&fd=1095&xp=1&xs=1&cnt=500"  # je Aktie: Käufe + Verkäufe, 3 Jahre (Routine-Erkennung)
AFM = "https://www.afm.nl/export.aspx?type=0ee836dc-5520-459d-bcf4-a4a689de6614&format=csv"   # Niederlande (MAR 19): Datum, Firma, Person
AFM_PAGE = "https://www.afm.nl/en/sector/registers/meldingenregisters/transacties-leidinggevenden-mar19-"
ASX = "https://asx.api.markitdigital.com/asx-research/1.0/companies/{t}/announcements?count=100"          # Australien: Appendix 3Y
ASX_DOC = "https://cdn-api.markitdigital.com/apiman-gateway/ASX/asx-research/1.0/file/{k}"
TOP = re.compile(r"\b(CEO|Chief Executive|CFO|Chief Financial|President|Chairman|Chair|COO|Vorstand|Vorsitz)", re.I)
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
                                    "d": ("trade date",), "px": ("price",), "sh": ("qty",), "val": ("value",), "own": ("δown", "Δown")}.items()}
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
        own = g("own").strip()
        out.append({"t": tk, "n": g("n"), "who": g("who"), "role": g("role"), "kind": kind, "d": g("d")[:10],
                    "sh": round(abs(_num_us(g("sh")))), "px": round(px, 2), "val": round(val),
                    "url": f"http://openinsider.com/{tk}",
                    **({"own": "neu" if own.lower().startswith("new") else round(_num_us(own))} if own and own != "-" else {})})
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


def _days_ago(n: int) -> str:
    from datetime import date, timedelta
    return (date.today() - timedelta(days=n)).isoformat()


def routine(rows: list[dict]) -> None:
    """Routine oder Gelegenheit (Cohen/Malloy/Pomorski 2012): Wer in den beiden Vorjahren im selben Kalendermonat ebenfalls
    gekauft hat, kauft nach Plan (Routine) – solche Käufe sagen kaum etwas. Alle anderen Käufe gelten als „gezielt“
    (opportunistisch); nur sie hatten in der Studie eine deutliche Überrendite. Setzt x["opp"] bei Käufen."""
    months = {}
    for x in rows:
        if x["kind"] == "buy" and len(x.get("d") or "") >= 7:
            months.setdefault(x["who"], set()).add(x["d"][:7])
    for x in rows:
        if x["kind"] != "buy" or len(x.get("d") or "") < 7:
            continue
        y, m = int(x["d"][:4]), x["d"][5:7]
        x["opp"] = not all(f"{y - k}-{m}" in months.get(x["who"], ()) for k in (1, 2))


def signal(rows: list[dict], days: int = 90) -> dict:
    """Insider-Signal je Aktie aus den Käufen der letzten `days` Tage: Käufer, Summe, Vorstandsspitze, gezielt, Anteil.
    Stärke 0–3: +1 mehrere Käufer (Cluster), +1 CEO/CFO/Vorsitz kauft, +1 gezielter Kauf mit ≥ 10 % mehr Aktien oder ≥ 1 Mio."""
    since, out = _days_ago(days), {}
    for x in rows:
        if x.get("kind") != "buy" or (x.get("d") or "") < since:
            continue
        o = out.setdefault(x["t"], {"who": set(), "val": 0.0, "top": False, "opp": 0, "unk": 0, "own": 0, "last": "", "cur": x.get("cur") or "USD", "n": x.get("n")})
        o["who"].add(x.get("who"))
        o["val"] += x.get("val") or 0
        o["top"] = o["top"] or bool(TOP.search(x.get("role") or ""))
        o["opp"] += x.get("opp") is True
        o["unk"] += "opp" not in x                                           # BaFin: ohne Historie keine Routine-Prüfung
        ow = x.get("own")
        o["own"] = max(o["own"], 100 if ow == "neu" else ow if isinstance(ow, (int, float)) else 0)
        o["last"] = max(o["last"], x.get("d") or "")
    res = {}
    for t, o in out.items():
        big = (o["opp"] or o["unk"]) and (o["own"] >= 10 or o["val"] >= 1_000_000)
        res[t] = {"buyers": len(o["who"]), "val": round(o["val"]), "cur": o["cur"], "top": o["top"], "opp": o["opp"], "unk": o["unk"],
                  "own": o["own"], "last": o["last"], "n": o["n"], "score": int(len(o["who"]) >= 2) + int(o["top"]) + int(bool(big))}
    return res


def fetch_afm(watch: dict[str, str], days: int = 365) -> list[dict]:
    """Niederlande (AFM, MAR 19): Meldungen von Führungskräften – nur Datum und Person, ohne Betrag und Richtung.
    Zuordnung über den Firmennamen (Airbus SE, ASML Holding N.V. …)."""
    import csv
    import io
    r = requests.get(AFM, headers={"User-Agent": "Mozilla/5.0 (Kairo Scanner)"}, timeout=60)
    try:
        text = r.content.decode("utf-8")
    except UnicodeDecodeError:
        text = r.content.decode("cp1252", "replace")                       # AFM liefert Windows-1252
    since, rows = _days_ago(days), []
    keys = {t: re.sub(r"[^a-z0-9]", "", (n or "").lower()) for t, n in watch.items()}
    for row in csv.reader(io.StringIO(text), delimiter=";"):
        if len(row) < 3 or not row[0][:4].isdigit() or row[0][:10] < since:
            continue
        firm = re.sub(r"[^a-z0-9]", "", row[1].lower())
        for t, k in keys.items():
            if len(k) >= 4 and firm.startswith(k):
                rows.append({"t": t, "n": watch[t], "who": row[2], "role": "Führungskraft", "kind": "meld", "d": row[0][:10],
                             "src": "AFM", "url": AFM_PAGE})
    return rows


def fetch_asx(watch: dict[str, str], days: int = 365) -> list[dict]:
    """Australien (ASX): „Change of Director's Interest Notice“ (Appendix 3Y) – Meldung mit Link, Betrag steht im PDF."""
    since, rows = _days_ago(days), []
    for t, name in watch.items():
        if not str(t).endswith(".AX"):
            continue
        try:
            d = requests.get(ASX.format(t=t[:-3]), headers={"User-Agent": "Mozilla/5.0 (Kairo Scanner)"}, timeout=20).json()
            for it in (d.get("data") or {}).get("items") or []:
                h = it.get("headline") or ""
                if re.search(r"director'?s'? interest|appendix 3y|change of director", h, re.I) and (it.get("date") or "")[:10] >= since:
                    rows.append({"t": t, "n": name, "who": h, "role": "Director", "kind": "meld", "d": it["date"][:10], "src": "ASX",
                                 "url": ASX_DOC.format(k=it.get("documentKey"))})
        except Exception as exc:
            print(f"ASX {t}: {exc!r}"[:120])
    return rows


def fetch_watch(watch: dict[str, str], budget_s: float = 240) -> tuple[list[dict], int]:
    """Gezielt für Watchlist, Merkliste und Depot: Insider-Käufe und -Verkäufe je US-Aktie der letzten 12 Monate (OpenInsider-Screener).
    Nur US-Börsenkürzel (ohne Punkt) – europäische und asiatische Werte melden nicht an die SEC."""
    t0, rows, done = time.time(), [], 0
    for t, name in watch.items():
        if "." in t or "^" in t or time.time() - t0 > budget_s:
            continue
        try:
            r = requests.get(SCREEN.format(t=t), headers={"User-Agent": "Mozilla/5.0 (Kairo Scanner)"}, timeout=20)
            got = _merge([x for x in parse_openinsider(r.text) if x["t"] == t])
            done += 1
            routine(got)
            since = _days_ago(365)
            for x in [x for x in got if x["d"] >= since]:
                if x["val"] >= (10_000 if x["kind"] == "buy" else 250_000):     # Kleinstkäufe (Sparpläne) und Routine-Verkäufe auslassen
                    rows.append({**x, "n": x.get("n") or name, "url": f"http://openinsider.com/{t}"})
            time.sleep(0.4)
        except Exception as exc:
            print(f"Insider Watchlist {t}: {exc!r}"[:140])
    newest = lambda x: (x["d"], x["val"])                 # neueste zuerst – so fällt beim Kürzen nie ein frischer Kauf weg
    buys = sorted([x for x in rows if x["kind"] == "buy"], key=newest, reverse=True)
    sells = sorted([x for x in rows if x["kind"] == "sell"], key=newest, reverse=True)[:80]
    rows = buys[:250] + sells
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
        for nm, fn in (("AFM", fetch_afm), ("ASX", fetch_asx)):
            try:
                extra = fn(watch)
                out["watch"] += extra
                out[f"watch_{nm.lower()}_n"] = len(extra)
                print(f"Insider {nm}: {len(extra)} Meldungen")
            except Exception as exc:
                print(f"Insider {nm}: Fehler {exc!r}"[:160])
        out["signal"] = signal(out["watch"])
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
