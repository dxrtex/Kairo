"""Markt-Puls (18.11.2026, wie im Profi-Terminal) – nur Anzeige, die Kairo-Regel nutzt nichts davon:
  · social:  meistdiskutierte Aktien auf Reddit (ApeWisdom, kostenlos) mit Veränderung zu gestern
  · poly:    Wahrscheinlichkeiten aus Vorhersagemärkten (Polymarket, kostenlos) zu Zinsen, Konjunktur, Märkten
  · mk:      Zinsen, Dollar, Devisen, Rohstoffe, Bitcoin, VIX (Yahoo) – Kurs, Tagesveränderung, 1 Jahr Schlusskurse
  · mkw:     5 Jahre Wochenkurse derselben Werte (Chart je Kachel) · Faktor-ETFs (fac) für die Faktor-Analyse je Aktie
  · ev:      offene Naturereignisse von NASA EONET (Brände aus Satellitendaten, Stürme, Vulkane, Fluten) für die Weltkarte
  · macro:   Länderdaten der Weltbank (217 Länder): Wachstum, Inflation, Arbeitslosigkeit, Staatsschulden, Handel, Rüstung … (einmal je Woche)
Schreibt state/pulse.json (alle 30 Min. aus tagsueber.yml) und state/macro.json (Branch kairo-alerts).

    python -m backend.pulse [--out state]
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 (Kairo; +https://github.com)"}

MK = [("^IRX", "US-Zins 3 Monate", "rate"), ("^FVX", "US-Zins 5 Jahre", "rate"), ("^TNX", "US-Zins 10 Jahre", "rate"), ("^TYX", "US-Zins 30 Jahre", "rate"),
      ("DX-Y.NYB", "Dollar-Index", "fx"), ("EURUSD=X", "EUR/USD", "fx"), ("EURGBP=X", "EUR/GBP", "fx"), ("USDJPY=X", "USD/JPY", "fx"), ("EURCHF=X", "EUR/CHF", "fx"),
      ("GC=F", "Gold", "com"), ("SI=F", "Silber", "com"), ("CL=F", "Öl WTI", "com"), ("BZ=F", "Öl Brent", "com"), ("NG=F", "Erdgas", "com"), ("HG=F", "Kupfer", "com"),
      ("ZW=F", "Weizen", "com"), ("BTC-USD", "Bitcoin", "crypto"), ("ETH-USD", "Ethereum", "crypto"), ("^VIX", "VIX", "vol"),
      # Faktoren für die Faktor-Analyse je Aktie (18.11.2026, wie „Factor exposure“ im Profi-Terminal) – keine Kacheln in der App
      ("SPY", "Markt (S&P 500)", "fac"), ("IWM", "Nebenwerte", "fac"), ("IVE", "Value", "fac"), ("IVW", "Wachstum", "fac"),
      ("MTUM", "Momentum", "fac"), ("QUAL", "Qualität", "fac"), ("USMV", "Niedrige Schwankung", "fac")]

POLY_RX = re.compile(r"\b(fed|fomc|rate|rates|interest|inflation|cpi|recession|gdp|unemployment|jobs|payroll|tariff|s&p|nasdaq|dow|stock|bitcoin|btc|"
                     r"ethereum|oil|treasury|yield|ecb|bank of|powell|shutdown|debt|china|trade|nvidia|apple|tesla|ipo|earnings|market cap|gold)\b", re.I)

WB = {"g": "NY.GDP.MKTP.KD.ZG", "i": "FP.CPI.TOTL.ZG", "u": "SL.UEM.TOTL.ZS", "d": "GC.DOD.TOTL.GD.ZS", "ca": "BN.CAB.XOKA.GD.ZS", "gdp": "NY.GDP.MKTP.CD", "pc": "NY.GDP.PCAP.CD",
      # Handel und Rüstung für die Weltkarte (18.11.2026): Exporte/Importe in % des BIP, Handelsbilanz in $, Militärausgaben in % des BIP und in $
      "ex": "NE.EXP.GNFS.ZS", "im": "NE.IMP.GNFS.ZS", "tb": "BN.GSR.GNFS.CD", "mil": "MS.MIL.XPND.GD.ZS", "milc": "MS.MIL.XPND.CD"}
WB_V = 2                                               # Fassung der Länderdaten – neue Kennzahlen erzwingen einen frischen Abruf

EONET_CAT = {"wildfires": "fire", "severeStorms": "storm", "volcanoes": "volcano", "floods": "flood", "seaLakeIce": "ice", "earthquakes": "quake"}


def social(rows: list) -> list:
    """ApeWisdom-Zeilen → [{t, n, m, m0, r, r0}] (Erwähnungen 24 Std., vor 24 Std., Rang, Rang gestern)."""
    out = []
    for x in rows or []:
        try:
            out.append({"t": str(x["ticker"]).upper(), "n": str(x.get("name") or "")[:40].replace("&amp;", "&"), "m": int(x.get("mentions") or 0),
                        "m0": int(x.get("mentions_24h_ago") or 0), "r": int(x.get("rank") or 0), "r0": int(x.get("rank_24h_ago") or 0) or None})
        except (KeyError, TypeError, ValueError):
            continue
    return [x for x in out if x["m"] > 0][:40]


def poly(events: list, n: int = 24) -> list:
    """Polymarket-Ereignisse → [{q, u, v, o: [[antwort, wahrscheinlichkeit], …], end}] – nur Wirtschaft/Märkte, nach Volumen."""
    out = []
    for e in events or []:
        title = str(e.get("title") or "")
        if not POLY_RX.search(title):
            continue
        mk = [m for m in (e.get("markets") or []) if not m.get("closed")]
        if not mk:
            continue
        opts = []
        for m in mk:
            try:
                names, prices = json.loads(m.get("outcomes") or "[]"), [float(p) for p in json.loads(m.get("outcomePrices") or "[]")]
            except (ValueError, TypeError):
                continue
            if len(prices) == 2 and prices[0] == prices[1] == 0.5:
                continue                                   # noch nie gehandelt (Platzhalter wie „Candidate T“)
            if len(mk) == 1 and len(names) == len(prices):
                opts = [[str(a), round(b, 3)] for a, b in zip(names, prices)]
            elif prices:                                   # mehrere Märkte (z. B. „Wie viele Zinssenkungen?“): Ja-Preis je Teilmarkt
                opts.append([str(m.get("groupItemTitle") or m.get("question") or "")[:50], round(prices[0], 3)])
        opts = sorted([o for o in opts if o[0]], key=lambda o: -o[1])[:6]
        if not opts:
            continue
        out.append({"q": title[:140], "u": f"https://polymarket.com/event/{e.get('slug', '')}", "v": round(float(e.get("volume") or 0)),
                    "v24": round(float(e.get("volume24hr") or 0)), "end": str(e.get("endDate") or "")[:10], "o": opts})
    out.sort(key=lambda x: -x["v24"])
    return out[:n]


def market(hist) -> dict:
    """Yahoo-Schlusskurse (DataFrame je Symbol) → {sym: {n, k, c, d1, w1, y1, s: [1 Jahr Schlusskurse], t0}}."""
    out = {}
    for sym, name, kind in MK:
        try:
            c = hist[sym]["Close"].dropna()
        except Exception:
            continue
        if len(c) < 5:
            continue
        last = float(c.iloc[-1])
        r = lambda k: round(last / float(c.iloc[-1 - k]) - 1, 4) if len(c) > k and float(c.iloc[-1 - k]) else None
        tail = c.iloc[-260:]
        out[sym] = {"n": name, "k": kind, "c": round(last, 4), "d1": r(1), "w1": r(5), "y1": r(min(252, len(c) - 1)),
                    "t": [d.strftime("%Y-%m-%d") for d in tail.index], "s": [round(float(v), 4) for v in tail]}
    return out


def weekly(hist) -> dict:
    """Wochen-Schlusskurse über 5 Jahre (für den Devisen-/Rohstoff-Chart): {sym: [[datum, kurs], …]}."""
    out = {}
    for sym, name, kind in MK:
        if kind == "fac":
            continue
        try:
            c = hist[sym]["Close"].dropna()
        except Exception:
            continue
        if len(c) >= 20:
            out[sym] = [[d.strftime("%Y-%m-%d"), round(float(v), 4)] for d, v in c.items()]
    return out


def eonet(events: list, n: int = 500) -> list:
    """NASA EONET (kostenlos, ohne Schlüssel): offene Naturereignisse → [[art, titel, länge, breite, datum, quelle], …] neueste zuerst.
    Brände kommen aus Satelliten-Meldungen (u. a. MODIS/VIIRS), Stürme aus den Wetterdiensten."""
    out = []
    for e in events or []:
        cats = [c.get("id") for c in e.get("categories") or []]
        kind = next((EONET_CAT[c] for c in cats if c in EONET_CAT), None)
        geo = [g for g in (e.get("geometry") or []) if g.get("type") == "Point" and len(g.get("coordinates") or []) == 2]
        if not kind or not geo:
            continue
        g = max(geo, key=lambda x: str(x.get("date") or ""))
        lon, lat = g["coordinates"]
        try:
            lon, lat = round(float(lon), 2), round(float(lat), 2)
        except (TypeError, ValueError):
            continue
        src = ((e.get("sources") or [{}])[0] or {}).get("url") or e.get("link") or ""
        out.append([kind, str(e.get("title") or "")[:90], lon, lat, str(g.get("date") or "")[:10], str(src)[:200]])
    out.sort(key=lambda x: x[4], reverse=True)
    return out[:n]


def worldbank(series: dict, valid: dict | None = None) -> dict:
    """Weltbank-Antworten je Kennzahl → {iso2: {n, g, i, u, d, ca, gdp, pc, y, r}} (jeweils jüngster Wert).
    valid: {iso2: region} der echten Länder (ohne Sammelgruppen wie „Euroraum“ oder „Welt“)."""
    out: dict = {}
    for k, rows in series.items():
        for x in rows or []:
            iso = (x.get("country") or {}).get("id")
            if not iso or x.get("value") is None or not re.fullmatch(r"[A-Z]{2}", iso) or (x.get("countryiso3code") or "") == "":
                continue
            if valid is not None and iso not in valid:
                continue
            if str(x.get("date") or "0")[:4].isdigit() and int(str(x.get("date"))[:4]) < int(time.strftime("%Y")) - 6:
                continue                                   # uralte Werte (z. B. Staatsschulden 1990) weglassen
            o = out.setdefault(iso, {"n": (x.get("country") or {}).get("value", iso), **({"r": valid[iso]} if valid else {})})
            if k not in o:
                o[k] = round(float(x["value"]), 2)
                o.setdefault("y", {})[k] = x.get("date")
    return out


def fetch_all(out_dir: Path, macro_days: int = 7) -> dict:
    import requests
    import yfinance as yf
    res: dict = {"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    try:
        r = requests.get("https://apewisdom.io/api/v1.0/filter/all-stocks/page/1", headers=UA, timeout=20)
        res["social"] = social(r.json().get("results"))
    except Exception as exc:
        print(f"Reddit: {exc!r}")
    try:
        ev = []
        for off in (0, 100, 200):
            r = requests.get("https://gamma-api.polymarket.com/events", params={"closed": "false", "active": "true", "order": "volume24hr", "ascending": "false",
                                                                                 "limit": 100, "offset": off}, headers=UA, timeout=25)
            ev += r.json() if r.ok else []
        res["poly"] = poly(ev)
    except Exception as exc:
        print(f"Polymarket: {exc!r}")
    try:
        syms = [m[0] for m in MK]
        df = yf.download(syms, period="13mo", interval="1d", group_by="ticker", auto_adjust=False, progress=False, threads=True)
        res["mk"] = market({s: df[s] for s in syms if s in df.columns.get_level_values(0)})
    except Exception as exc:
        print(f"Marktdaten: {exc!r}")
    try:                                               # 5 Jahre Wochenkurse für den Chart je Kachel
        syms = [m[0] for m in MK if m[2] != "fac"]
        dw = yf.download(syms, period="5y", interval="1wk", group_by="ticker", auto_adjust=False, progress=False, threads=True)
        res["mkw"] = weekly({s: dw[s] for s in syms if s in dw.columns.get_level_values(0)})
    except Exception as exc:
        print(f"Wochenkurse: {exc!r}")
    try:
        r = requests.get("https://eonet.gsfc.nasa.gov/api/v3/events", params={"status": "open", "days": 20, "limit": 800}, headers=UA, timeout=40)
        res["ev"] = eonet(r.json().get("events"))
    except Exception as exc:
        print(f"NASA EONET: {exc!r}")
    mpath = out_dir / "macro.json"
    old = json.loads(mpath.read_text()) if mpath.exists() else {}
    if old.get("c"):                                   # gespeicherten Stand nachträglich bereinigen: Werte älter als 6 Jahre raus
        lim, changed = int(time.strftime("%Y")) - 6, False
        for o in old["c"].values():
            for k, y in list((o.get("y") or {}).items()):
                if str(y)[:4].isdigit() and int(str(y)[:4]) < lim and k in o:
                    o.pop(k); o["y"].pop(k); changed = True
        if changed:
            mpath.write_text(json.dumps(old, ensure_ascii=False, separators=(",", ":")))
    if old.get("v") != WB_V or not old.get("generated") or time.time() - time.mktime(time.strptime(old["generated"][:10], "%Y-%m-%d")) > macro_days * 86400:
        try:
            ser, valid = {}, {}
            cr = requests.get("https://api.worldbank.org/v2/country", params={"format": "json", "per_page": 400}, headers=UA, timeout=40).json()
            for x in (cr[1] if isinstance(cr, list) and len(cr) > 1 else []):
                if (x.get("region") or {}).get("id") not in (None, "", "NA"):
                    valid[x.get("iso2Code")] = (x.get("region") or {}).get("value", "").strip()
            for k, ind in WB.items():
                r = requests.get(f"https://api.worldbank.org/v2/country/all/indicator/{ind}", params={"format": "json", "mrnev": 1, "per_page": 400}, headers=UA, timeout=40)
                j = r.json()
                ser[k] = j[1] if isinstance(j, list) and len(j) > 1 else []
            c = worldbank(ser, valid or None)
            if len(c) > 100:
                mpath.write_text(json.dumps({"generated": time.strftime("%Y-%m-%d"), "v": WB_V, "c": c}, ensure_ascii=False, separators=(",", ":")))
                print(f"Weltbank: {len(c)} Länder")
        except Exception as exc:
            print(f"Weltbank: {exc!r}")
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="state")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    res = fetch_all(out)
    prev = json.loads((out / "pulse.json").read_text()) if (out / "pulse.json").exists() else {}
    for k in ("social", "poly", "mk", "mkw", "ev"):      # Ausfall einer Quelle: letzten Stand behalten
        if not res.get(k) and prev.get(k):
            res[k] = prev[k]
    (out / "pulse.json").write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")))
    print("Puls:", {k: len(v) for k, v in res.items() if isinstance(v, (list, dict))})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
