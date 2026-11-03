"""Insider-Geschäfte (MAR Art. 19) aus Schweden und der Schweiz – für ALLE gescannten Aktien dieser Länder, nicht nur die Watchlist.

- Schweden: Finansinspektionen, Insynsregistret (CSV-Export, alle Emittenten, mit Person, Funktion, Volumen und Preis)
- Schweiz:  SIX Exchange Regulation, Management-Transaktionen (JSON, alle Emittenten, mit Betrag in CHF, ohne Namen)

Beide Register melden nach ISIN. Die Zuordnung ISIN → Börsenkürzel läuft über OpenFIGI (frei, ohne Schlüssel) und wird
zwischengespeichert; ohne Treffer dort hilft beim schwedischen Register der Firmenname.
Beträge werden grob in Euro umgerechnet (feste Kurse), damit das Insider-Signal Länder vergleichen kann.

    python -m backend.insider_eu        # Test: druckt Käufe der letzten 30 Tage (ohne Universum: nur Rohdaten)
"""
from __future__ import annotations

import csv
import io
import re
import sys
import time
from datetime import date, timedelta

import requests

UA = {"User-Agent": "Mozilla/5.0 (Kairo Scanner)", "Accept": "application/json, text/csv, */*"}
FI = ("https://marknadssok.fi.se/publiceringsklient/sv-SE/Search/Search?SearchFunctionType=Insyn&Utgivare="
      "&PersonILedandeStallningNamn=&Transaktionsdatum.From={d0}&Transaktionsdatum.To={d1}&button=export")
FI_PAGE = "https://marknadssok.fi.se/publiceringsklient/sv-SE/Search/Search?SearchFunctionType=Insyn&Utgivare={q}&button=search"
SIX = "https://www.ser-ag.com/sheldon/management_transactions/v1/overview.json?pageSize=100&pageNumber={p}&sortAttribute=byDate"
SIX_PAGE = "https://www.ser-ag.com/en/resources/notifications-market-participants/management-transactions.html"
FIGI = "https://api.openfigi.com/v3/mapping"
EUR = {"EUR": 1.0, "SEK": 0.087, "CHF": 1.06, "NOK": 0.085, "DKK": 0.134, "USD": 0.92, "GBP": 1.17}
SIX_ROLE = {"1": "Geschäftsleitung", "2": "Verwaltungsrat"}


def _key(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def _name_key(s: str) -> str:
    s = re.sub(r"\b(ab|publ|ag|sa|ltd|plc|holding|group|the|aktiebolag|asa|oyj|nv|se)\b", " ", (s or "").lower())
    return re.sub(r"[^a-z0-9]", "", s)


def _num(x: str) -> float:
    x = (x or "").replace("\xa0", "").replace(" ", "")
    if "," in x and "." in x:
        x = x.replace(".", "")
    try:
        return float(x.replace(",", "."))
    except ValueError:
        return 0.0


def figi_map(isins: list[str], cache: dict, budget_s: float = 90) -> dict:
    """ISIN → Liste normalisierter Börsenkürzel (OpenFIGI, je Anfrage 10 ISINs, ohne Schlüssel ~25 Anfragen/Minute)."""
    todo, t0 = [i for i in dict.fromkeys(isins) if i and i not in cache], time.time()
    for k in range(0, len(todo), 10):
        if time.time() - t0 > budget_s:
            break
        part = todo[k:k + 10]
        try:
            r = requests.post(FIGI, json=[{"idType": "ID_ISIN", "idValue": i} for i in part], headers={"Content-Type": "application/json"}, timeout=20)
            if r.status_code == 429:
                time.sleep(30)
                continue
            for i, res in zip(part, r.json()):
                cache[i] = sorted({_key(d.get("ticker")) for d in (res.get("data") or []) if d.get("ticker")})
        except Exception as exc:
            print(f"OpenFIGI: {exc!r}"[:120])
            break
        time.sleep(2.5)
    return cache


def _match(isin: str, firm: str, uni: dict[str, str], figi: dict, by_key: dict, by_name: dict) -> str | None:
    for k in figi.get(isin) or []:
        if k in by_key:
            return by_key[k]
    nk = _name_key(firm)                              # ohne FIGI-Treffer nur bei exakt gleichem Firmennamen (Volvo ≠ Volvo Car)
    if len(nk) >= 4 and nk in by_name:
        return by_name[nk]
    return None


def _index(uni: dict[str, str], suffix: str) -> tuple[dict, dict]:
    sub = {t: n for t, n in uni.items() if t.endswith(suffix)}
    return {_key(t[: -len(suffix)]): t for t in sub}, {_name_key(n): t for t, n in sub.items() if n}


def _decode(raw: bytes) -> str:
    """FI liefert UTF-16 (mit oder ohne BOM)."""
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    if len(raw) > 3 and raw[1:2] == b"\x00":
        return raw.decode("utf-16-le", "replace")
    return raw.decode("utf-8-sig", "replace")


CORP = re.compile(r"\b(AB|Aktiebolag|Holding|Invest|Förvaltning|Stiftelse|Ltd|GmbH|AS|A/S|Oy|Fond|Capital|Partners|LLC|Trust)\b", re.I)


def _role_se(r: str) -> str:
    r = (r or "").replace("\xa0", " ")
    return ("Vorstand (CEO)" if re.search(r"\bvd\b|verkställande direktör", r, re.I) else
            "Finanzvorstand (CFO)" if re.search(r"finans|ekonomichef|cfo", r, re.I) else
            "Vorsitz" if re.search(r"ordförande", r, re.I) else
            "Aufsichtsrat" if re.search(r"styrelse", r, re.I) else "Führungskraft")


def net_rows(rows: list[dict]) -> list[dict]:
    """Käufe und Verkäufe derselben Person am selben Tag verrechnen (Umschichtungen sind kein Signal)."""
    acc = {}
    for x in rows:
        k = (x["t"], x["who"], x["d"])
        o = acc.setdefault(k, {**x, "val": 0})
        o["val"] += x["val"] if x["kind"] == "buy" else -x["val"]
    out = []
    for o in acc.values():
        if abs(o["val"]) >= 5_000:
            out.append({**o, "kind": "buy" if o["val"] > 0 else "sell", "val": abs(o["val"])})
    return out


def parse_fi(text: str) -> list[dict]:
    """FI-CSV (Semikolon, Kopfzeile auf Schwedisch) → Geschäfte. Nur Börsengeschäfte mit Aktien, ohne Aktienprogramme/Korrekturen."""
    rd = csv.DictReader(io.StringIO(text), delimiter=";")
    out = []
    for r in rd:
        g = lambda *ks: next((r[k] for x in ks for k in r if k and x.lower() in k.lower() and r[k] is not None), "") or ""
        kind = g("Karaktär").strip().lower()
        kind = "buy" if kind.startswith("förvärv") else "sell" if kind.startswith("avyttring") else ""
        if not kind or "aktie" not in g("Instrumenttyp").lower():
            continue
        if g("aktieprogram").strip().lower() in ("ja", "yes") or g("Status").lower().startswith("rev"):
            continue
        vol, px, cur = _num(g("Volym")), _num(g("Pris")), (g("Valuta") or "SEK").strip().upper()
        rep, who = g("Anmälningsskyldig").strip(), g("Person i ledande").strip()
        if rep and who and rep != who and CORP.search(rep):  # nahestehende Firma (Holding, Beteiligungsgesellschaft) – kein eigenes Geld
            continue
        out.append({"isin": g("ISIN").strip(), "firm": g("Emittent").strip(), "who": (who or rep).replace("\xa0", " "),
                    "role": g("Befattning").strip(), "rel": g("Närstående").strip().lower() in ("ja", "yes"),
                    "kind": kind, "d": g("Transaktionsdatum")[:10], "val": round(vol * px * EUR.get(cur, 0.1)), "cur": "EUR"})
    return out


def fetch_se(uni: dict[str, str], figi: dict, days: int = 90) -> list[dict]:
    d1, d0 = date.today(), date.today() - timedelta(days=days)
    r = requests.get(FI.format(d0=d0.isoformat(), d1=d1.isoformat()), headers=UA, timeout=90)
    raw = r.content
    rows = parse_fi(_decode(raw))
    figi_map([x["isin"] for x in rows], figi)
    by_key, by_name = _index(uni, ".ST")
    out = []
    for x in rows:
        t = _match(x["isin"], x["firm"], uni, figi, by_key, by_name)
        if t:
            out.append({"t": t, "n": uni.get(t), "who": x["who"] or x["firm"], "role": _role_se(x["role"]) + (" · nahestehend" if x["rel"] else ""),
                        "kind": x["kind"], "d": x["d"], "val": x["val"], "cur": "EUR", "src": "FI Schweden",
                        "url": FI_PAGE.format(q=requests.utils.quote(x["firm"]))})
    out = net_rows(out)
    print(f"Insider Schweden: nicht zugeordnet z. B. {[(x['firm'], figi.get(x['isin'])) for x in rows if not _match(x['isin'], x['firm'], uni, figi, by_key, by_name)][:6]}")
    print(f"Insider Schweden: {len(rows)} Geschäfte, {len(out)} zugeordnet ({sum(x['kind'] == 'buy' for x in out)} Käufe)")
    return out


def parse_six(items: list[dict]) -> list[dict]:
    out = []
    for it in items:
        bs = str(it.get("buySellIndicator") or "")
        kind = "buy" if bs == "1" else "sell" if bs == "2" else ""
        d = str(it.get("transactionDate") or "")
        if not kind or len(d) != 8 or it.get("correcteeId"):
            continue
        fn = str(it.get("obligorFunctionCode") or "")
        out.append({"isin": it.get("ISIN") or "", "firm": it.get("notificationSubmitter") or "", "kind": kind,
                    "d": f"{d[:4]}-{d[4:6]}-{d[6:]}", "val": round((it.get("transactionAmountCHF") or 0) * EUR["CHF"]),
                    "role": SIX_ROLE.get(fn, "Führungskraft") + (" · nahestehend" if it.get("obligorRelatedPartyInd") else ""),
                    "who": f"{SIX_ROLE.get(fn, 'Führungskraft')} ({it.get('ISIN')})", "id": it.get("notificationId")})
    return out


def fetch_ch(uni: dict[str, str], figi: dict, days: int = 90, max_pages: int = 40) -> list[dict]:
    since, items = (date.today() - timedelta(days=days)).strftime("%Y%m%d"), []
    for p in range(max_pages):
        d = requests.get(SIX.format(p=p), headers=UA, timeout=30).json()
        lst = d.get("itemList") or []
        items += lst
        if not lst or min(str(i.get("transactionDate") or "99999999") for i in lst) < since:
            break
        time.sleep(0.3)
    rows = [x for x in parse_six(items) if x["d"].replace("-", "") >= since]
    figi_map([x["isin"] for x in rows], figi)
    by_key, by_name = _index(uni, ".SW")
    out = []
    for x in rows:
        t = _match(x["isin"], "", uni, figi, by_key, by_name)
        if t:
            out.append({"t": t, "n": uni.get(t), "who": x["who"], "role": x["role"], "kind": x["kind"], "d": x["d"], "val": x["val"],
                        "cur": "EUR", "src": "SIX Schweiz", "url": SIX_PAGE})
    out = net_rows(out)
    miss = [(x["isin"], figi.get(x["isin"])) for x in rows if not _match(x["isin"], "", uni, figi, by_key, by_name)][:6]
    print(f"Insider Schweiz: nicht zugeordnet z. B. {miss}")
    print(f"Insider Schweiz: {len(rows)} Geschäfte, {len(out)} zugeordnet ({sum(x['kind'] == 'buy' for x in out)} Käufe)")
    return out


BAFIN = "https://portal.mvp.bafin.de/database/DealingsInfo/sucheForm.do"
NORDIC = ("https://api.news.eu.nasdaq.com/news/query.action?type=json&showAttachments=false&showCnsSpecific=true&showCompany=true"
          "&countResults=true&freeText=&company=&market={m}&cnscategory=Managers%27+Transactions&fromDate={d0}&toDate={d1}"
          "&globalGroup=exchangeNotice&globalName=NordicAllMarkets&displayLanguage=en&language=en&timeZone=CET"
          "&dateMask=yyyy-MM-dd+HH%3Amm%3Ass&limit=100&start={st}&dir=DESC")
NORDIC_MKT = {"CO": "Main Market, Copenhagen", "HE": "Main Market, Helsinki"}
OSLO = "https://api3.oslo.oslobors.no/v1/newsreader/list?category=1102&fromDate={d0}&toDate={d1}"


def fetch_de(uni: dict[str, str], figi: dict, days: int = 90) -> list[dict]:
    """Deutschland: BaFin-Datenbank für ALLE Emittenten (Zeitraum-Suche, je 10 Tage), Zuordnung über die ISIN (OpenFIGI)."""
    from .bafin import parse_csv
    s = requests.Session(); s.headers.update(UA)
    rows, seen, since = [], set(), (date.today() - timedelta(days=days)).isoformat()
    for pg in range(1, 13):                           # der CSV-Export liefert je Seite ~29 Zeilen (neueste zuerst); Zeitraum wird ignoriert
        p = {"meldepflichtigerName": "", "emittentName": "", "emittentIsin": "", "zeitraum": "0", "zeitraumVon": "", "zeitraumBis": "",
             "emittentButton": "Suche Emittent", "d-4000784-e": "1", "6578706f7274": "1", "d-4000784-p": str(pg)}
        r = s.get(BAFIN, params=p, timeout=60)
        r.encoding = "utf-8"
        got = parse_csv(r.text) if r.ok and "csv" in r.headers.get("content-type", "") else []
        new = [x for x in got if (x["isin"], x["who"], x["d"], x["kind"], x["val"]) not in seen]
        seen |= {(x["isin"], x["who"], x["d"], x["kind"], x["val"]) for x in got}
        rows += new
        oldest = min((x["d"] for x in got), default="")
        print(f"BaFin Seite {pg}: {len(got)} Zeilen, {len(new)} neu, älteste {oldest}")
        if not new or (oldest and oldest < since):
            break
        time.sleep(0.6)
    rows = [x for x in rows if x["d"] >= since]
    rows = [x for x in rows if "aktie" in (x.get("inst") or "").lower() or not x.get("inst")]
    figi_map([x["isin"] for x in rows], figi)
    by_key, by_name = _index(uni, ".DE")
    out = []
    for x in rows:
        t = _match(x["isin"], x["n"], uni, figi, by_key, by_name)
        if t:
            role = x.get("role") or ""
            out.append({"t": t, "n": uni.get(t), "who": x["who"], "role": "Vorstand" if re.search(r"vorstand", role, re.I) else "Aufsichtsrat" if re.search(r"aufsicht", role, re.I) else role or "Führungskraft",
                        "kind": x["kind"], "d": x["d"], "val": x["val"], "cur": "EUR", "src": "BaFin",
                        "url": f"{BAFIN}?emittentIsin={x['isin']}&zeitraum=0&emittentButton=Suche+Emittent"})
    out = net_rows(out)
    print(f"Insider Deutschland (alle): {len(rows)} Geschäfte, {len(out)} zugeordnet ({sum(x['kind'] == 'buy' for x in out)} Käufe)")
    return out


NUM = r"(\d{1,3}(?:[ ,.\u00a0]\d{3})*(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"


def _nnum(x: str) -> float:
    x = x.replace("\u00a0", " ").strip()
    if re.fullmatch(r"\d{1,3}(?:[ ,]\d{3})+(?:\.\d+)?", x):          # 1,234,567.89 / 1 234 567
        return float(x.replace(",", "").replace(" ", ""))
    if re.fullmatch(r"\d{1,3}(?:[ .]\d{3})+(?:,\d+)?", x):            # 1.234.567,89
        return float(x.replace(".", "").replace(" ", "").replace(",", "."))
    return float(x.replace(",", ".").replace(" ", ""))


def parse_mar(text: str) -> dict | None:
    """MAR-Artikel-19-Formular (Nasdaq-Nordic-Meldung als Text): Art (Kauf/Verkauf), Person, Funktion, Volumen × Preis, Währung."""
    t = re.sub(r"\s+", " ", text)
    kind = "buy" if re.search(r"Nature of the transaction[^.]{0,40}?\b(Acquisition|Purchase|Subscription|Køb|Osto|Merkintä)", t, re.I) else \
           "sell" if re.search(r"Nature of the transaction[^.]{0,40}?\b(Disposal|Sale|Salg|Myynti)", t, re.I) else None
    if not kind:
        return None
    vol = re.search(r"(?:Aggregated volume|Volume\(s\)|Volume)[\s:]{0,6}" + NUM, t, re.I)          # Zahl direkt nach dem Feld
    px = re.search(r"(?:Aggregated price|Volume weighted average price|Price\(s\)|Price)[\s:]{0,6}" + NUM, t, re.I)
    cur = re.search(r"\b(DKK|EUR|SEK|NOK|USD|ISK)\b", t)
    who = re.search(r"Name[: ]+([A-ZÆØÅÄÖ][\w .'-]{2,60}?)(?: Reason| Position|\s+2\b|\s+b\))", t)
    role = re.search(r"Position/status[: ]+([\w ,/&-]{2,60}?)(?: b\)| Initial| Amendment)", t, re.I)
    try:
        v, p = _nnum(vol.group(1)), _nnum(px.group(1))
    except Exception:
        return {"kind": kind, "val": None, "who": who.group(1).strip() if who else "", "role": role.group(1).strip() if role else ""}
    c = cur.group(1) if cur else "EUR"
    return {"kind": kind, "val": round(v * p * EUR.get(c, 0.1)), "who": who.group(1).strip() if who else "", "role": role.group(1).strip() if role else ""}


def fetch_nordic(uni: dict[str, str], figi: dict, days: int = 90, max_msgs: int = 400) -> list[dict]:
    """Dänemark/Finnland: Nasdaq-Nordic-Meldungen „Managers' Transactions“; Betrag aus dem MAR-Formular im Meldungstext,
    sonst Meldung ohne Betrag. Zuordnung über den Firmennamen (exakt)."""
    d0, d1, out, n = date.today() - timedelta(days=days), date.today(), [], 0
    for suf, mkt in NORDIC_MKT.items():
        _, by_name = _index(uni, "." + suf)
        items, st = [], 0
        while st < 1000:
            j = requests.get(NORDIC.format(m=requests.utils.quote(mkt), d0=d0, d1=d1, st=st), headers=UA, timeout=30).json()
            got = ((j.get("results") or {}).get("item")) or []
            items += got
            if len(got) < 100:
                break
            st += 100
        items = [it for it in items if (it.get("releaseTime") or "")[:10] >= str(d0)]   # die Schnittstelle ignoriert fromDate
        for it in items:
            t = by_name.get(_name_key(it.get("company") or ""))
            if not t or n >= max_msgs:
                continue
            n += 1
            try:
                html = requests.get(it["messageUrl"], headers=UA, timeout=20).text
                txt = re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style).*?</\1>", " ", html))
                m = parse_mar(txt)
            except Exception:
                m = None
            base = {"t": t, "n": uni.get(t), "d": (it.get("releaseTime") or "")[:10], "src": "Nasdaq Nordic", "url": it.get("messageUrl")}
            if m and m.get("val"):
                out.append({**base, "who": m["who"] or "Führungskraft (Name in der Meldung)", "role": m["role"] or "Führungskraft", "kind": m["kind"], "val": m["val"], "cur": "EUR"})
            else:
                out.append({**base, "who": (it.get("headline") or "")[:120], "role": "Führungskraft", "kind": "meld"})
            time.sleep(0.2)
        print(f"Insider {suf} (Nasdaq Nordic): {len(items)} Meldungen")
    trades = net_rows([x for x in out if x["kind"] != "meld"])
    melds = [x for x in out if x["kind"] == "meld"]
    print(f"Insider Dänemark/Finnland: {len(trades)} Geschäfte mit Betrag ({sum(x['kind'] == 'buy' for x in trades)} Käufe), {len(melds)} ohne Betrag")
    return trades + melds


def fetch_oslo(uni: dict[str, str], days: int = 90) -> list[dict]:
    """Norwegen: Osloer Börse (Newsweb, Kategorie Meldepflichtiger Handel) – nur Meldung, Betrag steht im PDF."""
    d0, d1 = date.today() - timedelta(days=days), date.today()
    j = requests.get(OSLO.format(d0=d0, d1=d1), headers=UA, timeout=30).json()
    out = []
    for m in (j.get("data") or {}).get("messages") or []:
        t = f"{m.get('issuerSign')}.OL"
        if t in uni and not re.search(r"bond|obligasjon|\d{4}/\d{4}", m.get("title") or "", re.I):
            out.append({"t": t, "n": uni[t], "who": m.get("title") or "", "role": "Primærinnsider", "kind": "meld",
                        "d": (m.get("publishedTime") or "")[:10], "src": "Oslo Børs",
                        "url": f"https://newsweb.oslobors.no/message/{m.get('messageId')}"})
    print(f"Insider Norwegen (Oslo Børs): {len(out)} Meldungen ohne Betrag")
    return out


def fetch(uni: dict[str, str], figi: dict, days: int = 90) -> tuple[list[dict], set]:
    """Alle zugeordneten Geschäfte (Schweden, Schweiz, Deutschland alle, Dänemark/Finnland) und Meldungen (Norwegen);
    zweites Ergebnis: Länder-Endungen, deren Quelle ausgefallen ist."""
    rows, bad = [], set()
    for suf, fn in (("ST", fetch_se), ("SW", fetch_ch), ("DE", fetch_de), ("CO", fetch_nordic), ("OL", lambda u, f, d: fetch_oslo(u, d))):
        try:
            rows += fn(uni, figi, days)
        except Exception as exc:
            bad.add(suf)
            print(f"Insider {suf}: Fehler {exc!r}"[:160])
    return rows, bad


def main() -> int:
    uni = {"VOLV-B.ST": "AB Volvo (publ)", "NESN.SW": "Nestlé S.A.", "SAP.DE": "SAP SE", "AAD.DE": "Amadeus Fire AG", "UBK.DE": "UmweltBank AG",
           "NOVO-B.CO": "Novo Nordisk A/S", "DNORD.CO": "Dampskibsselskabet NORDEN A/S", "NOKIA.HE": "Nokia Oyj", "EQNR.OL": "Equinor ASA", "AIRX.OL": "AirX Group Holdings Ltd."}
    figi: dict = {}
    for name, fn in (("DE", lambda: fetch_de(uni, figi, 30)), ("Nordic", lambda: fetch_nordic(uni, figi, 30, 40)), ("Oslo", lambda: fetch_oslo(uni, 30))):
        try:
            rows = fn()
            print(name, len(rows), rows[:4])
        except Exception as exc:
            print(name, "Fehler", repr(exc))
    # MAR-Parser an einer echten Nordic-Meldung prüfen
    try:
        j = requests.get(NORDIC.format(m=requests.utils.quote(NORDIC_MKT["CO"]), d0=date.today() - timedelta(days=10), d1=date.today(), st=0), headers=UA, timeout=30).json()
        for it in ((j.get("results") or {}).get("item") or [])[:6]:
            html = requests.get(it["messageUrl"], headers=UA, timeout=20).text
            txt = re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style).*?</\1>", " ", html))
            k = txt.find("Nature of the transaction")
            print("MAR", it.get("company"), "→", parse_mar(txt), "| Ausschnitt:", re.sub(r"\s+", " ", txt[max(0, k - 300):k + 600])[:900] if k >= 0 else "(kein Formular im Text)")
    except Exception as exc:
        print("MAR-Test Fehler", repr(exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
