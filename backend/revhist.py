"""Umsatz-Beschleunigung zum Termin (Test 29.10.2026, docs/EARNINGS_FEATURES_TEST.md / Bloom Energy):
Wachstum zum Vorjahr im gemeldeten Quartal minus Wachstum im Vorquartal. Verlangsamt es sich um 5 Prozentpunkte
oder mehr, stiegen Aktien nach guten Zahlen deutlich seltener (54 % statt 64 %) – in beiden Testzeiträumen.
Quartalsumsätze aus den SEC-Finanzdaten (companyfacts), der aktuelle Umsatz aus der Meldung selbst.
"""
from __future__ import annotations

import os

import pandas as pd

_CACHE: dict = {}
TAGS = ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "RevenueFromContractWithCustomerIncludingAssessedTax")


def quarters(cik: int) -> dict:
    """{Quartalsende: Umsatz} (3-Monats-Werte)."""
    if cik in _CACHE:
        return _CACHE[cik]
    import requests
    c = os.environ.get("SEC_CONTACT", "").strip()
    ua = {"User-Agent": f"Kairo {c}" if c else "Mozilla/5.0 (Kairo)", "Accept-Encoding": "gzip, deflate"}
    out = {}
    try:
        g = requests.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json", headers=ua, timeout=30).json().get("facts", {}).get("us-gaap", {})
        for tag in TAGS:
            for u in g.get(tag, {}).get("units", {}).get("USD", []):
                try:
                    st, en = pd.Timestamp(u["start"]), pd.Timestamp(u["end"])
                except Exception:
                    continue
                if 80 <= (en - st).days <= 100:
                    out.setdefault(en, float(u["val"]))
    except Exception as exc:
        print(f"Umsatz-Historie {cik}: Fehler {exc!r}")
    _CACHE[cik] = out
    return out


def _near(q: dict, day: pd.Timestamp, tol: int = 20):
    c = [e for e in q if abs((e - day).days) <= tol]
    return min(c, key=lambda e: abs((e - day).days)) if c else None


def accel(q: dict, rev_a: float | None, report: pd.Timestamp) -> dict | None:
    """{"revg": Wachstum jetzt, "reva": Beschleunigung} oder None. Quartalsende = jüngstes Ende 0–100 Tage vor dem Termin
    (steht es noch nicht in den SEC-Daten, ≈ 91 Tage nach dem letzten bekannten)."""
    if not q:
        return None
    rep = report.tz_localize(None) if report.tzinfo is not None else report
    ends = sorted(q)
    cur = next((e for e in reversed(ends) if pd.Timedelta(0) < rep - e <= pd.Timedelta(days=100)), None)
    if cur is None:
        last = max(ends)
        cur = last + pd.Timedelta(days=91) if pd.Timedelta(days=60) < rep - last <= pd.Timedelta(days=190) else None
    if cur is None:
        return None
    now = rev_a if rev_a else q.get(cur)
    ly = _near(q, cur - pd.Timedelta(days=365))
    pq = _near(q, cur - pd.Timedelta(days=91))
    pqly = _near(q, cur - pd.Timedelta(days=456)) if pq else None
    if not now or not ly or not q[ly]:
        return None
    g = now / q[ly] - 1
    out = {"revg": round(g, 4)}
    if pq and pqly and q[pqly]:
        out["reva"] = round(g - (q[pq] / q[pqly] - 1), 4)
    return out
