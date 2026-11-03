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
    nk = _name_key(firm)
    if len(nk) >= 4:
        if nk in by_name:
            return by_name[nk]
        for n, t in by_name.items():
            if len(n) >= 5 and (nk.startswith(n) or n.startswith(nk)):
                return t
    return None


def _index(uni: dict[str, str], suffix: str) -> tuple[dict, dict]:
    sub = {t: n for t, n in uni.items() if t.endswith(suffix)}
    return {_key(t[: -len(suffix)]): t for t in sub}, {_name_key(n): t for t, n in sub.items() if n}


def parse_fi(text: str) -> list[dict]:
    """FI-CSV (Semikolon, Kopfzeile auf Schwedisch) → Geschäfte. Nur Börsengeschäfte mit Aktien, ohne Aktienprogramme/Korrekturen."""
    rd = csv.DictReader(io.StringIO(text), delimiter=";")
    out = []
    for r in rd:
        g = lambda *ks: next((r[k] for k in r if k and any(x.lower() in k.lower() for x in ks) and r[k] is not None), "") or ""
        kind = g("Karaktär").strip().lower()
        kind = "buy" if kind.startswith("förvärv") else "sell" if kind.startswith("avyttring") else ""
        if not kind or "aktie" not in g("Instrumenttyp").lower():
            continue
        if g("aktieprogram").strip().lower() in ("ja", "yes") or g("Status").lower().startswith("rev"):
            continue
        vol, px, cur = _num(g("Volym")), _num(g("Pris")), (g("Valuta") or "SEK").strip().upper()
        out.append({"isin": g("ISIN").strip(), "firm": g("Emittent").strip(), "who": g("Person i ledande", "Anmälningsskyldig").strip(),
                    "role": g("Befattning").strip(), "rel": g("Närstående").strip().lower() in ("ja", "yes"),
                    "kind": kind, "d": g("Transaktionsdatum")[:10], "val": round(vol * px * EUR.get(cur, 0.1)), "cur": "EUR"})
    return out


def fetch_se(uni: dict[str, str], figi: dict, days: int = 90) -> list[dict]:
    d1, d0 = date.today(), date.today() - timedelta(days=days)
    r = requests.get(FI.format(d0=d0.isoformat(), d1=d1.isoformat()), headers=UA, timeout=90)
    raw = r.content
    text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8-sig", "replace")
    rows = parse_fi(text)
    figi_map([x["isin"] for x in rows], figi)
    by_key, by_name = _index(uni, ".ST")
    out = []
    for x in rows:
        t = _match(x["isin"], x["firm"], uni, figi, by_key, by_name)
        if t and x["val"] >= 5_000:
            role = ("Vorstand (CEO)" if re.search(r"\bvd\b|verkställande direktör", x["role"], re.I) else
                    "Finanzvorstand (CFO)" if re.search(r"finans|ekonomichef|cfo", x["role"], re.I) else
                    "Vorsitz" if re.search(r"ordförande", x["role"], re.I) else x["role"] or "Führungskraft")
            out.append({"t": t, "n": uni.get(t), "who": x["who"] or x["firm"], "role": role + (" · nahestehend" if x["rel"] else ""),
                        "kind": x["kind"], "d": x["d"], "val": x["val"], "cur": "EUR", "src": "FI Schweden",
                        "url": FI_PAGE.format(q=requests.utils.quote(x["firm"]))})
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
        if t and x["val"] >= 5_000:
            out.append({"t": t, "n": uni.get(t), "who": x["who"], "role": x["role"], "kind": x["kind"], "d": x["d"], "val": x["val"],
                        "cur": "EUR", "src": "SIX Schweiz", "url": SIX_PAGE})
    print(f"Insider Schweiz: {len(rows)} Geschäfte, {len(out)} zugeordnet ({sum(x['kind'] == 'buy' for x in out)} Käufe)")
    return out


def fetch(uni: dict[str, str], figi: dict, days: int = 90) -> tuple[list[dict], set]:
    """Alle zugeordneten Geschäfte beider Länder; zweites Ergebnis: Länder-Endungen, deren Quelle ausgefallen ist."""
    rows, bad = [], set()
    for suf, fn in (("ST", fetch_se), ("SW", fetch_ch)):
        try:
            rows += fn(uni, figi, days)
        except Exception as exc:
            bad.add(suf)
            print(f"Insider {suf}: Fehler {exc!r}"[:160])
    return rows, bad


def main() -> int:
    uni = {"VOLV-B.ST": "AB Volvo (publ)", "ERIC-B.ST": "Telefonaktiebolaget LM Ericsson (publ)", "INVE-B.ST": "Investor AB (publ)",
           "NESN.SW": "Nestlé S.A.", "NOVN.SW": "Novartis AG", "UBSG.SW": "UBS Group AG", "ROG.SW": "Roche Holding AG"}
    figi: dict = {}
    try:                                                   # Rohdaten zeigen (Spalten, Werte), damit die Zuordnung prüfbar ist
        raw = requests.get(FI.format(d0=(date.today() - timedelta(days=7)).isoformat(), d1=date.today().isoformat()), headers=UA, timeout=90).content
        txt = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8-sig", "replace")
        print("FI Kopf+2:", txt.splitlines()[:3])
        p = parse_fi(txt)
        print("FI geparst:", len(p), "Käufe", sum(x["kind"] == "buy" for x in p), p[:2])
        it = requests.get(SIX.format(p=0), headers=UA, timeout=30).json().get("itemList") or []
        from collections import Counter
        print("SIX Felder:", sorted(it[0]) if it else None, Counter(str(i.get("buySellIndicator")) for i in it), Counter(str(i.get("obligorFunctionCode")) for i in it))
        print("SIX Beispiele:", it[:3])
        print("FIGI:", figi_map(["SE0000115446", "CH0038863350", "CH0012005267"], {}))
    except Exception as exc:
        print("Roh-Test Fehler", repr(exc))
    rows, bad = fetch(uni, figi, days=30)
    print("Ausfälle:", bad or "keine", "· FIGI-Cache:", len(figi))
    for x in rows[:25]:
        print(x)
    return 0


if __name__ == "__main__":
    sys.exit(main())
