"""Deutsche Insider-Geschäfte: Eigengeschäfte von Führungskräften (Directors' Dealings, Art. 19 MAR) aus der
offiziellen BaFin-Datenbank – frei abrufbar, als CSV-Export.

Nur Emittenten mit Sitz in Deutschland melden an die BaFin (Airbus, Novo Nordisk, BYD & Co. melden woanders).

    python -m backend.bafin           # Test: Watchlist-Werte + alle Meldungen der letzten 30 Tage
"""

from __future__ import annotations

import csv
import io
import time
from datetime import date, timedelta

import requests

BASE = "https://portal.mvp.bafin.de/database/DealingsInfo/sucheForm.do"
# ISIN je Yahoo-Ticker (deutsche Werte der Watchlist)
ISIN = {"ALV.DE": "DE0008404005", "BAYN.DE": "DE000BAY0017", "CBK.DE": "DE000CBK1001", "DBK.DE": "DE0005140008",
        "LHA.DE": "DE0008232125", "DTE.DE": "DE0005557508", "DEZ.DE": "DE0006305006", "HAG.DE": "DE000HAG0005",
        "IFX.DE": "DE0006231004", "NDX1.DE": "DE000A0D6554", "R3NK.DE": "DE000RENK730", "RHM.DE": "DE0007030009",
        "SAP.DE": "DE0007164600", "SIE.DE": "DE0007236101", "ENR.DE": "DE000ENER6Y0", "TUI1.DE": "DE000TUAG505",
        "VOW3.DE": "DE0007664039"}
FORM = {"meldepflichtigerName": "", "emittentName": "", "emittentIsin": "", "zeitraum": "0", "zeitraumVon": "", "zeitraumBis": "",
        "emittentButton": "Suche Emittent", "d-4000784-e": "1", "6578706f7274": "1"}      # displaytag-Export: 1 = CSV


def _num(x: str) -> float:
    try:
        return float(x.split()[0].replace(".", "").replace(",", ".")) if x and x.strip() else 0.0
    except ValueError:
        return 0.0


def _iso(d: str) -> str:
    try:
        dd, mm, yy = d.strip()[:10].split(".")
        return f"{yy}-{mm}-{dd}"
    except ValueError:
        return ""


def parse_csv(text: str, ticker: str | None = None) -> list[dict]:
    """BaFin-CSV → Käufe/Verkäufe (andere Geschäftsarten wie Zuteilung oder Schenkung werden ausgelassen)."""
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿")), delimiter=";"))
    if not rows:
        return []
    head = [h.strip().lower() for h in rows[0]]
    col = lambda *n: next((i for i, h in enumerate(head) if any(h.startswith(x) for x in n)), None)
    ix = {"n": col("emittent"), "isin": col("isin"), "who": col("meldepflichtiger"), "role": col("position"), "inst": col("art des instr"),
          "type": col("art des gesch"), "px": col("durchschnittspreis"), "val": col("aggregiertes volumen"), "d": col("datum des gesch"),
          "md": col("mitteilungsdatum"), "venue": col("ort")}
    if ix["type"] is None or ix["val"] is None:
        return []
    out = []
    for r in rows[1:]:
        g = lambda k: r[ix[k]].strip() if ix[k] is not None and ix[k] < len(r) else ""
        typ = g("type").lower()
        kind = "buy" if typ.startswith("kauf") else "sell" if typ.startswith("verkauf") else None
        val, px = _num(g("val")), _num(g("px"))
        cur = (g("val").split() + ["EUR"])[1] if g("val") else "EUR"
        if not kind or val <= 0 or cur != "EUR":
            continue
        out.append({"t": ticker, "n": g("n"), "isin": g("isin"), "who": g("who"), "role": g("role"), "inst": g("inst"), "kind": kind,
                    "d": _iso(g("d")) or _iso(g("md")), "px": round(px, 2), "sh": round(val / px) if px else None, "val": round(val),
                    "cur": "EUR", "venue": g("venue")})
    return out


def _get(s: requests.Session, **kw) -> str:
    r = s.get(BASE, params={**FORM, **kw}, timeout=40)
    r.encoding = "utf-8"
    return r.text if r.ok and "text/csv" in r.headers.get("content-type", "") else ""


def fetch(watch: dict[str, str], days: int = 180, budget_s: float = 90) -> dict:
    """Directors' Dealings der deutschen Watchlist-Werte (6 Monate) – Käufe ab 10.000 €, Verkäufe ab 250.000 €."""
    s, t0, rows, done = requests.Session(), time.time(), [], 0
    s.headers["User-Agent"] = "Mozilla/5.0 (Kairo Scanner)"
    since = (date.today() - timedelta(days=days)).isoformat()
    for t, name in watch.items():
        isin = ISIN.get(t)
        if not isin or time.time() - t0 > budget_s:
            continue
        try:
            got = [x for x in parse_csv(_get(s, emittentIsin=isin), t) if x["d"] >= since]
            done += 1
            rows += [{**x, "n": name} for x in got if x["val"] >= (10_000 if x["kind"] == "buy" else 250_000)]
            time.sleep(0.5)
        except Exception as exc:
            print(f"BaFin {t}: {exc!r}"[:140])
    buys = sorted([x for x in rows if x["kind"] == "buy"], key=lambda x: -x["val"])
    sells = sorted([x for x in rows if x["kind"] == "sell"], key=lambda x: -x["val"])[:40]
    print(f"BaFin Watchlist: {done} deutsche Aktien geprüft, {len(buys)} Käufe, {len(sells)} Verkäufe")
    return {"rows": buys[:80] + sells, "n": done}


def main() -> int:
    from .run_scan import load_watchlist
    res = fetch(load_watchlist())
    for x in res["rows"][:25]:
        print(x)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
