"""Zeitpunktgenaue US-Fundamentaldaten aus SEC EDGAR (XBRL „companyfacts“, frei, ohne Schlüssel) für S19.

python -m research.strategy_championship.edgar --out DIR

Je Universum-Titel (Region us, ohne .TO): CIK über company_tickers.json, dann
- dei:EntityPublicFloat (USD, im 10-K gemeldeter Streubesitz-Wert) → Größen-Filter (≥ 10 Mrd. USD; konservativer Ersatz für
  die Marktkapitalisierung, frei von Split-Problemen),
- Jahreswerte (10-K, Geschäftsjahr) Umsatz und operatives Ergebnis (Fallback Jahresüberschuss) → operative Marge,
- SIC-Code (submissions) → Sektor-ETF.
Jeder Wert mit „filed“-Datum: verwendet wird nur, was am Handelstag bereits veröffentlicht war.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

import pandas as pd

from .data import UNIVERSE

UA = {"User-Agent": "Kairo strategy research (github.com/dxrtex/Kairo)", "Accept-Encoding": "identity"}
REV = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet",
       "RevenueFromContractWithCustomerIncludingAssessedTax", "RevenuesNetOfInterestExpense", "SalesRevenueGoodsNet"]
OPI = ["OperatingIncomeLoss"]
NET = ["NetIncomeLoss", "ProfitLoss"]


def get(url: str, tries: int = 4):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.loads(r.read())
        except Exception as e:                      # 404 = keine XBRL-Daten
            if "404" in str(e):
                return None
            time.sleep(1.5 * (k + 1))
    return None


def annual(facts: dict, tags: list[str]) -> list[dict]:
    g = facts.get("facts", {}).get("us-gaap", {})
    for t in tags:
        u = g.get(t, {}).get("units", {}).get("USD")
        if not u:
            continue
        rows = []
        for x in u:
            if x.get("form") not in ("10-K", "10-K/A") or x.get("fp") != "FY" or not x.get("start"):
                continue
            days = (pd.Timestamp(x["end"]) - pd.Timestamp(x["start"])).days
            if 330 <= days <= 400:
                rows.append({"end": x["end"], "filed": x["filed"], "val": float(x["val"]), "tag": t})
        if rows:
            return rows
    return []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="fund")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    uni = pd.read_csv(UNIVERSE)
    us = [t for t in uni.loc[uni["region"] == "us", "ticker"] if not t.endswith(".TO")]
    m = get("https://www.sec.gov/files/company_tickers.json") or {}
    cik = {v["ticker"].upper().replace(".", "-"): int(v["cik_str"]) for v in m.values()}
    rows, sic, miss = [], [], []
    for k, t in enumerate(us):
        c = cik.get(t.upper())
        if c is None:
            miss.append(t)
            continue
        f = get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{c:010d}.json")
        time.sleep(0.13)
        s = get(f"https://data.sec.gov/submissions/CIK{c:010d}.json")
        time.sleep(0.13)
        if s:
            sic.append({"ticker": t, "cik": c, "sic": s.get("sic"), "sic_desc": s.get("sicDescription")})
        if not f:
            miss.append(t)
            continue
        pf = f.get("facts", {}).get("dei", {}).get("EntityPublicFloat", {}).get("units", {}).get("USD", [])
        for x in pf:
            rows.append({"ticker": t, "kind": "float", "end": x["end"], "filed": x["filed"], "val": float(x["val"]), "tag": "EntityPublicFloat"})
        for kind, tags in (("rev", REV), ("opinc", OPI), ("netinc", NET)):
            for x in annual(f, tags):
                rows.append({"ticker": t, "kind": kind, **x})
        if k % 100 == 0:
            print(f"{k + 1}/{len(us)} {t}: {len(rows)} Werte", flush=True)
    df = pd.DataFrame(rows).drop_duplicates(["ticker", "kind", "end", "filed"])
    df.to_parquet(out / "edgar_fund_v1.parquet", index=False)
    pd.DataFrame(sic).to_csv(out / "edgar_sic_v1.csv", index=False)
    (out / "edgar_missing.txt").write_text("\n".join(miss))
    print(f"US-Titel {len(us)}, mit Daten {df['ticker'].nunique()}, ohne CIK/Daten {len(miss)}, Werte {len(df)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
