"""Finanzen über mehrere Jahre (18.11.2026, wie im Profi-Terminal): Umsatz, Bruttogewinn, operatives Ergebnis, Nettogewinn,
Gewinn je Aktie, Free Cashflow, Cash, Schulden und Eigenkapital der letzten Geschäftsjahre – absolute Zahlen aus den
SEC-Finanzdaten (companyfacts, kostenlos, nur US-Aktien). Nur Anzeige in der App, die Kairo-Regel nutzt sie nicht.

    python -m backend.finhist --shard 0 --shards 4      # Teil laden → fin_part_0.json
    python -m backend.finhist --combine parts           # Teile zusammenführen → site/data/fin.json
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .config import ROOT
from .earnfast import _sec_ua, ciks

YEARS = 6
# Kennzahl → mögliche XBRL-Tags (erster mit Werten gewinnt); "i" = Stichtagswert (Bilanz), sonst Jahreswert
METRICS = {
    "rev": ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "RevenueFromContractWithCustomerIncludingAssessedTax"),
    "gp": ("GrossProfit",),
    "oi": ("OperatingIncomeLoss",),
    "ni": ("NetIncomeLoss", "ProfitLoss"),
    "eps": ("EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted", "EarningsPerShareBasic"),
    "ocf": ("NetCashProvidedByUsedInOperatingActivities",),
    "capex": ("PaymentsToAcquirePropertyPlantAndEquipment",),
    "cash": ("CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"),
    "debt": ("LongTermDebt", "LongTermDebtNoncurrent"),
    "eq": ("StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
}
INSTANT = {"cash", "debt", "eq"}


def _days(a: str, b: str) -> int:
    from datetime import date
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def annual(facts: dict, tag: str, instant: bool) -> dict:
    """{Geschäftsjahr-Ende (YYYY-MM-DD): Wert} aus Jahresberichten (10-K); bei Korrekturen gilt die jüngste Meldung."""
    node = facts.get(tag) or {}
    units = node.get("units") or {}
    rows = units.get("USD") or units.get("USD/shares") or []
    best: dict = {}
    for u in rows:
        if not str(u.get("form", "")).startswith("10-K") or u.get("val") is None or not u.get("end"):
            continue
        if instant:
            if u.get("fp") not in (None, "FY"):
                continue
        else:
            if not u.get("start") or not 330 <= _days(u["start"], u["end"]) <= 380:
                continue
        k, f = u["end"], str(u.get("filed", ""))
        if k not in best or f > best[k][0]:
            best[k] = (f, float(u["val"]))
    return {k: v for k, (_, v) in best.items()}


def parse(facts: dict) -> dict | None:
    """us-gaap-Fakten → {"y": [Jahre], Kennzahl: [Werte je Jahr oder None]}. None, wenn kein Umsatz und kein Gewinn da ist."""
    series = {}
    for m, tags in METRICS.items():                # alle Tags zusammenführen: Firmen wechseln den Tag (z. B. Apple 2018 „Revenues“ → „RevenueFromContract…“)
        merged: dict = {}
        for tag in tags:
            for k, v in annual(facts, tag, m in INSTANT).items():
                merged.setdefault(k, v)
        if merged:
            series[m] = merged
    base = series.get("rev") or series.get("ni")
    if not base:
        return None
    ends = sorted(base)[-YEARS:]
    out: dict = {"y": [e[:4] for e in ends], "fye": ends[-1][5:]}

    def pick(s: dict, e: str):                   # Stichtag darf ein paar Tage abweichen (52/53-Wochen-Jahre)
        if e in s:
            return s[e]
        near = [k for k in s if abs(_days(k, e)) <= 10]
        return s[near[0]] if near else None
    for m in METRICS:
        if m == "capex" or m not in series:
            continue
        vals = [pick(series[m], e) for e in ends]
        if any(v is not None for v in vals):
            out[m] = [None if v is None else (round(v, 2) if m == "eps" else round(v)) for v in vals]
    if "ocf" in series:
        cx = series.get("capex", {})
        fcf = [(pick(series["ocf"], e) - (pick(cx, e) or 0)) if pick(series["ocf"], e) is not None else None for e in ends]
        out["fcf"] = [None if v is None else round(v) for v in fcf]
        out.pop("ocf", None)
    return out


def fetch(cik: int) -> dict | None:
    import requests
    try:
        r = requests.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json", headers=_sec_ua(), timeout=40)
        if r.status_code != 200:
            return None
        return parse(r.json().get("facts", {}).get("us-gaap", {}))
    except Exception as exc:
        print(f"Finanzen {cik}: {exc!r}")
        return None


def run_shard(shard: int, shards: int) -> dict:
    cm = ciks()
    ts = sorted(cm)[shard::shards]
    out, t0 = {}, time.time()
    for i, t in enumerate(ts):
        x = fetch(cm[t])
        if x:
            out[t] = x
        time.sleep(0.15)                           # SEC: höchstens 10 Abrufe je Sekunde
        if i % 100 == 0:
            print(f"{i}/{len(ts)} · {len(out)} mit Daten · {time.time() - t0:.0f} s")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--combine")
    ap.add_argument("--prev")
    a = ap.parse_args(argv)
    if a.combine:
        by = {}
        if a.prev and Path(a.prev).exists():
            try:
                by.update(json.loads(Path(a.prev).read_text()).get("by", {}))
            except Exception:
                pass
        for p in sorted(Path(a.combine).glob("fin_part_*.json")):
            by.update(json.loads(p.read_text()))
        dst = ROOT / "site" / "data" / "fin.json"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(json.dumps({"generated": time.strftime("%Y-%m-%d"), "n": len(by), "by": by}, separators=(",", ":")))
        print(f"fin.json: {len(by)} Aktien")
        return 0
    res = run_shard(a.shard, a.shards)
    Path(f"fin_part_{a.shard}.json").write_text(json.dumps(res, separators=(",", ":")))
    print(f"Teil {a.shard}: {len(res)} Aktien")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
