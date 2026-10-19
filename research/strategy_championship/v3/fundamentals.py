"""Protokoll v3.0 – zeitpunktgenaue (PIT) Kennzahlen je Firma aus SEC-XBRL (`fund.csv.gz` von sec_extract.py).

Für jedes Einreichungsdatum eines 10-K/10-Q (und Varianten) wird der Wissensstand **an diesem Tag** rekonstruiert: je
(Kennzahl, Periode) der zuletzt bis dahin gemeldete Wert (zuerst gemeldet, Korrekturen erst ab ihrem eigenen Datum).
Daraus: TTM-Werte (Summe der letzten vier Quartale; Quartale aus 3-Monats-Werten oder Differenzen kumulierter Werte),
letzte Bilanzwerte, Earnings-Momentum (Quartal − Vorjahresquartal), Aktienanzahl.
Verwendbar ab dem Tag **nach** dem Einreichungsdatum (`avail`).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

import numpy as np
import pandas as pd

FLOW = {
    "ni": ["NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"],
    "rev": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "RevenueFromContractWithCustomerIncludingAssessedTax",
            "SalesRevenueNet", "SalesRevenueGoodsNet"],
    "cogs": ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold",
             "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization", "CostOfServices"],
    "gp": ["GrossProfit"],
    "ocf": ["NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
}
INSTANT = {
    "assets": ["Assets"],
    "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "shares": ["EntityCommonStockSharesOutstanding", "CommonStockSharesOutstanding"],
}
REPORTS = {"10-K", "10-Q", "10-K/A", "10-Q/A", "10-KT", "10-QT"}
D = lambda s: date.fromisoformat(s)


def _near(keys: list[date], target: date, tol: int = 20) -> date | None:
    best = None
    for k in keys:
        if abs((k - target).days) <= tol and (best is None or abs((k - target).days) < abs((best - target).days)):
            best = k
    return best


def quarters(vals: dict) -> tuple[dict, dict]:
    """vals {(start, end): value} → (Quartale {Ende: Wert}, Geschäftsjahre {Ende: Wert})."""
    q, annual, cum = {}, {}, defaultdict(list)
    for (s, e), v in vals.items():
        if s is None:
            continue
        n = (e - s).days
        if 80 <= n <= 100:
            q[e] = v
        if 350 <= n <= 380:
            annual[e] = v
        if 80 <= n <= 380:
            cum[s].append((e, v))
    for s, lst in cum.items():                       # Differenzen kumulierter Werte (YTD) → fehlende Quartale
        lst.sort()
        for (e0, v0), (e1, v1) in zip(lst, lst[1:]):
            if 80 <= (e1 - e0).days <= 100 and e1 not in q:
                q[e1] = v1 - v0
    return q, annual


def ttm(q: dict, annual: dict, asof: date) -> tuple[float | None, date | None]:
    if q:
        E = max(q)
        ends = sorted(q)
        parts = [E] + [_near(ends, E - timedelta(days=91 * k)) for k in (1, 2, 3)]
        if all(p is not None for p in parts) and len(set(parts)) == 4:
            return float(sum(q[p] for p in parts)), E
        a = _near(sorted(annual), E, 10)
        if a is not None:
            return float(annual[a]), E
    if annual:
        a = max(annual)
        if (asof - a).days <= 460:
            return float(annual[a]), a
    return None, None


def firm_timeline(rows: pd.DataFrame) -> list[dict]:
    """rows: alle XBRL-Zeilen einer Firma. → eine Zeile je Einreichungsdatum eines Berichts."""
    rows = rows.sort_values("filed")
    tags = set(sum(FLOW.values(), [])) | set(sum(INSTANT.values(), []))
    rows = rows[rows["tag"].isin(tags)]
    ev = sorted(set(rows.loc[rows["form"].isin(REPORTS), "filed"]))
    if not ev:
        return []
    state: dict[str, dict] = defaultdict(dict)
    recs = list(rows[["tag", "unit", "start", "end", "val", "filed"]].itertuples(index=False, name=None))
    out, k = [], 0
    for fd in ev:
        while k < len(recs) and recs[k][5] <= fd:
            tag, unit, s, e, v, _ = recs[k]
            k += 1
            if tag in INSTANT["shares"]:
                if unit != "shares":
                    continue
            elif unit != "USD":
                continue
            try:
                v = float(v)
            except (TypeError, ValueError):
                continue
            state[tag][(D(s) if isinstance(s, str) and s else None, D(e))] = v
        asof = D(fd)
        r = {"filed": fd}
        qs = {}
        for c, tl in FLOW.items():
            best = None
            for pri, tag in enumerate(tl):
                if tag not in state:
                    continue
                q, a = quarters(state[tag])
                val, E = ttm(q, a, asof)
                if val is None:
                    continue
                key = (E, -pri)
                if best is None or key > best[0]:
                    best = (key, val, E, q)
            if best is not None:
                r[f"{c}_ttm"], r[f"{c}_end"] = best[1], best[2]
                qs[c] = best[3]
        if qs.get("ni"):                                # Earnings Momentum: Quartal − Vorjahresquartal
            q = qs["ni"]
            E = max(q)
            p = _near(sorted(q), E - timedelta(days=364))
            r["ni_q"], r["ni_q_prev"], r["ni_q_end"] = q[E], (q[p] if p else None), E
        for c, tl in INSTANT.items():
            best = None
            for pri, tag in enumerate(tl):
                for (s, e), v in state.get(tag, {}).items():
                    if s is None and e <= asof + timedelta(days=5):
                        key = (e, -pri)
                        if best is None or key > best[0]:
                            best = (key, v, e)
            if best is not None:
                r[c], r[f"{c}_end"] = best[1], best[2]
        out.append(r)
    return out


def build(fund: pd.DataFrame) -> pd.DataFrame:
    out = []
    for cik, g in fund.groupby("cik", sort=True):
        for r in firm_timeline(g):
            r["cik"] = int(cik)
            out.append(r)
    df = pd.DataFrame(out)
    df["filed"] = pd.to_datetime(df["filed"])
    df["avail"] = df["filed"] + pd.Timedelta(days=1)      # Uhrzeit unbekannt → erst ab dem Folgetag
    for c in [c for c in df.columns if c.endswith("_end")]:
        df[c] = pd.to_datetime(df[c])
    # abgeleitete Kennzahlen (Bilanzsumme als Nenner; Bruttogewinn ersatzweise Umsatz − Herstellkosten)
    gp = df.get("gp_ttm").where(df.get("gp_ttm").notna(), df.get("rev_ttm") - df.get("cogs_ttm"))
    A = df["assets"].where(df["assets"] > 0)
    df["gpa"] = gp / A
    df["roa"] = df["ni_ttm"] / A
    df["em"] = (df["ni_q"] - df["ni_q_prev"]) / A
    return df.sort_values(["cik", "avail"]).reset_index(drop=True)


def asof(tl: pd.DataFrame, cik: int, d: pd.Timestamp, max_age_days: int = 200) -> pd.Series | None:
    """Letzter Wissensstand einer Firma am Entscheidungstag d (nur Einreichungen mit avail ≤ d, höchstens 200 Tage alt)."""
    g = tl[tl["cik"] == cik]
    g = g[g["avail"] <= d]
    if g.empty or (d - g["filed"].iloc[-1]).days > max_age_days:
        return None
    return g.iloc[-1]


def panel_asof(tl: pd.DataFrame, dates: list, ciks: list, max_age_days: int = 200) -> pd.DataFrame:
    """Kennzahlen für alle (Datum, CIK) – merge_asof, veraltete (> 200 Tage) verworfen."""
    q = pd.DataFrame([(pd.Timestamp(d), int(c)) for d in dates for c in ciks], columns=["date", "cik"]).sort_values("date")
    t = tl.sort_values("avail")
    m = pd.merge_asof(q, t, left_on="date", right_on="avail", by="cik", direction="backward")
    m = m[(m["date"] - m["filed"]).dt.days <= max_age_days]
    return m
