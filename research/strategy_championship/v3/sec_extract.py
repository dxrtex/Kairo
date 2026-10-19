"""Protokoll v3.0 – SEC-Rohdaten (über den PC des Nutzers geladen) → kompakte Tabellen für die Backtests.

python -m research.strategy_championship.v3.sec_extract --companyfacts companyfacts.zip --submissions submissions.zip \
    --form345 DIR --out OUT

Nur Python-Standardbibliothek + pandas. Ausgabe (CSV, gzip):
  cik_map.csv          Ticker (Universum) → CIK, Name, SIC, Börse, Formular-Typ der Jahresberichte
  filings.csv.gz       10-K/10-Q/20-F/40-F (+ /A) und 8-K je CIK: Formular, Einreichung, Annahmezeit (UTC), Items, Periode
  fund.csv.gz          XBRL-Werte ausgewählter Kennzahlen mit Einreichungsdatum (alle Meldungen; PIT-Logik in fundamentals.py)
  insider_buys.csv.gz  Form 4, nicht-derivative Käufe (Code P, erworben), mit Rolle des Meldenden
  coverage.json        Abdeckungs-Statistik
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent.parent
UNIVERSE = HERE / "data" / "universe_frozen_2026-10-16.csv"

CONCEPTS = {
    "us-gaap": {
        "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet", "SalesRevenueGoodsNet", "SalesRevenueServicesNet",
        "CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold", "CostOfServices", "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization",
        "GrossProfit",
        "NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic",
        "Assets", "StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        "NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
        "CommonStockSharesOutstanding", "WeightedAverageNumberOfDilutedSharesOutstanding", "EarningsPerShareDiluted",
    },
    "dei": {"EntityCommonStockSharesOutstanding", "EntityPublicFloat"},
}
FILING_FORMS = {"10-K", "10-K/A", "10-Q", "10-Q/A", "20-F", "20-F/A", "40-F", "40-F/A", "10-KT", "10-QT", "8-K"}


def norm(t: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(t).upper())


def universe_us() -> dict[str, str]:
    """normalisierter Ticker → Universums-Ticker (US ohne Toronto)."""
    u = pd.read_csv(UNIVERSE)
    u = u[(u["region"] == "us") & ~u["ticker"].str.endswith(".TO")]
    return {norm(t): t for t in u["ticker"]}


def submissions(path: Path, uni: dict[str, str]):
    z = zipfile.ZipFile(path)
    names = set(z.namelist())
    cand = defaultdict(list)                 # Universums-Ticker → [(cik, name, sic, exch, n_filings, last_filing)]
    meta = {}
    for n in names:
        if "-submissions-" in n or not n.endswith(".json"):
            continue
        d = json.loads(z.read(n))
        tick = [norm(t) for t in d.get("tickers") or []]
        hit = [uni[t] for t in tick if t in uni]
        if not hit:
            continue
        r = d["filings"]["recent"]
        last = max(r["filingDate"]) if r["filingDate"] else ""
        cik = int(d["cik"])
        meta[cik] = d
        for i, t in enumerate(tick):
            if t in uni:
                cand[uni[t]].append((cik, d.get("name"), d.get("sic"), (d.get("exchanges") or [""] * len(tick))[i] if d.get("exchanges") else "",
                                     len(r["form"]), last, i))
    rows, used = [], set()
    for t, lst in cand.items():
        # Vorrang: Ticker steht an erster Stelle der Firma, dann jüngste Einreichung
        lst.sort(key=lambda x: (x[6] != 0, x[5]), reverse=False)
        lst.sort(key=lambda x: (x[6] == 0, x[5]), reverse=True)
        cik, name, sic, ex, nf, last, _ = lst[0]
        rows.append({"ticker": t, "cik": cik, "name": name, "sic": sic, "exchange": ex, "n_candidates": len(lst)})
        used.add(cik)
    fil = []
    for cik in sorted(used):
        d = meta[cik]
        blocks = [d["filings"]["recent"]] + [json.loads(z.read(f["name"])) for f in d["filings"].get("files", []) if f["name"] in names]
        for b in blocks:
            for k, form in enumerate(b["form"]):
                if form not in FILING_FORMS:
                    continue
                items = (b.get("items") or [""] * len(b["form"]))[k] or ""
                if form == "8-K" and "2.02" not in items:
                    continue
                fil.append({"cik": cik, "form": form, "accn": b["accessionNumber"][k], "filed": b["filingDate"][k],
                            "accepted": b["acceptanceDateTime"][k], "report": b["reportDate"][k], "items": items})
    return pd.DataFrame(rows), pd.DataFrame(fil).drop_duplicates("accn")


def companyfacts(path: Path, ciks: set[int]) -> pd.DataFrame:
    z = zipfile.ZipFile(path)
    out = []
    for cik in sorted(ciks):
        n = f"CIK{cik:010d}.json"
        try:
            d = json.loads(z.read(n))
        except KeyError:
            continue
        for tax, keep in CONCEPTS.items():
            for tag, body in (d.get("facts", {}).get(tax) or {}).items():
                if tag not in keep:
                    continue
                for unit, vals in body.get("units", {}).items():
                    for v in vals:
                        out.append((cik, tag, unit, v.get("start", ""), v["end"], v["val"], v.get("fy"), v.get("fp"),
                                    v.get("form"), v["filed"], v.get("accn"), v.get("frame", "")))
    return pd.DataFrame(out, columns=["cik", "tag", "unit", "start", "end", "val", "fy", "fp", "form", "filed", "accn", "frame"])


def insider(folder: Path, ciks: set[int]) -> pd.DataFrame:
    rows = []
    for zp in sorted(folder.glob("*_form345.zip")):
        z = zipfile.ZipFile(zp)
        rd = lambda n: pd.read_csv(io.BytesIO(z.read(n)), sep="\t", dtype=str, quoting=csv.QUOTE_NONE, on_bad_lines="skip")
        sub = rd("SUBMISSION.tsv")[["ACCESSION_NUMBER", "FILING_DATE", "DOCUMENT_TYPE", "ISSUERCIK", "ISSUERTRADINGSYMBOL"]]
        sub = sub[sub["DOCUMENT_TYPE"] == "4"]
        sub["cik"] = pd.to_numeric(sub["ISSUERCIK"], errors="coerce")
        sub = sub[sub["cik"].isin(ciks)]
        if sub.empty:
            continue
        tr = rd("NONDERIV_TRANS.tsv")[["ACCESSION_NUMBER", "TRANS_DATE", "TRANS_CODE", "TRANS_SHARES", "TRANS_PRICEPERSHARE", "TRANS_ACQUIRED_DISP_CD"]]
        tr = tr[(tr["TRANS_CODE"] == "P") & (tr["TRANS_ACQUIRED_DISP_CD"] == "A")]
        own = rd("REPORTINGOWNER.tsv")[["ACCESSION_NUMBER", "RPTOWNERCIK", "RPTOWNER_RELATIONSHIP", "RPTOWNER_TITLE"]]
        m = tr.merge(sub, on="ACCESSION_NUMBER").merge(own, on="ACCESSION_NUMBER", how="left")
        m["quarter"] = zp.name[:6]
        rows.append(m)
        print(zp.name, len(m), flush=True)
    df = pd.concat(rows, ignore_index=True)
    df["filed"] = pd.to_datetime(df["FILING_DATE"], format="%d-%b-%Y", errors="coerce").dt.strftime("%Y-%m-%d")
    df["trans_date"] = pd.to_datetime(df["TRANS_DATE"], format="%d-%b-%Y", errors="coerce").dt.strftime("%Y-%m-%d")
    df["shares"] = pd.to_numeric(df["TRANS_SHARES"], errors="coerce")
    df["price"] = pd.to_numeric(df["TRANS_PRICEPERSHARE"], errors="coerce")
    return df.rename(columns={"ACCESSION_NUMBER": "accn", "RPTOWNERCIK": "owner", "RPTOWNER_RELATIONSHIP": "role",
                              "RPTOWNER_TITLE": "title", "ISSUERTRADINGSYMBOL": "symbol"})[
        ["accn", "cik", "symbol", "filed", "trans_date", "owner", "role", "title", "shares", "price", "quarter"]]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--companyfacts", required=True)
    ap.add_argument("--submissions", required=True)
    ap.add_argument("--form345", required=True)
    ap.add_argument("--out", default="sec_v3")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    uni = universe_us()
    cmap, fil = submissions(Path(a.submissions), uni)
    cmap.to_csv(out / "cik_map.csv", index=False)
    fil.to_csv(out / "filings.csv.gz", index=False)
    ciks = set(cmap["cik"])
    print(f"Universum US {len(uni)} · mit CIK {len(cmap)} · Einreichungen {len(fil)}", flush=True)
    fund = companyfacts(Path(a.companyfacts), ciks)
    fund.to_csv(out / "fund.csv.gz", index=False)
    print(f"XBRL-Werte {len(fund)}", flush=True)
    ins = insider(Path(a.form345), ciks)
    ins.to_csv(out / "insider_buys.csv.gz", index=False)
    cov = {"universe_us": len(uni), "with_cik": len(cmap), "ambiguous_ticker": int((cmap["n_candidates"] > 1).sum()),
           "filings": Counter(fil["form"]), "fund_rows": len(fund), "fund_ciks": int(fund["cik"].nunique()),
           "fund_tags": Counter(fund["tag"]), "insider_rows": len(ins), "insider_ciks": int(ins["cik"].nunique()),
           "fund_first_filed_by_year": Counter(fund.groupby("cik")["filed"].min().str[:4])}
    (out / "coverage.json").write_text(json.dumps(cov, indent=1, default=int))
    print(json.dumps(cov, default=int)[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
