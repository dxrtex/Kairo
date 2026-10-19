"""Protokoll v3.0 §4 – Kandidaten K1–K4 und ihre Zufalls-Gegenstücke als Orders für engine.run.

Alle Regeln exakt wie in 27_PROTOCOL_V3.md; keine Parameter werden hier gewählt.
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

from ..engine import Order
from ..wave2 import _month_ends

N_TOP, W = 10, 0.099
HOLD = 60
EAR_MIN = 0.05
INS_MIN_OWNERS, INS_WINDOW, INS_MIN_USD, INS_GAP = 3, 30, 100_000.0, 90
PEAD_GAP = 30


# ------------------------------------------------------------------ Hilfen
def us_pool(P, d, us: set) -> list:
    pool = P.pool.get(d)
    return [t for t in pool if t in us] if pool is not None else []


def split_factor(splits: pd.DataFrame | None, ticker: str, after: pd.Timestamp, until: pd.Timestamp | None = None) -> float:
    """Produkt der Split-Verhältnisse in (after, until] – Aktienanzahl vom Stichtag `after` auf die Basis der Kursreihe.
    Kurse split-bereinigt (Yahoo-Standard): until = None (alle späteren Splits); sonst bis zum Entscheidungstag."""
    if splits is None:
        return 1.0
    s = splits[(splits["ticker"] == ticker) & (splits["date"] > after)]
    if until is not None:
        s = s[s["date"] <= until]
    return float(np.prod(s["ratio"].to_numpy())) if len(s) else 1.0


def rank(s: pd.Series) -> pd.Series:
    return s.rank(pct=True)


# ------------------------------------------------------------------ K1 / K2 (monatlich)
def month_table(P, tl: pd.DataFrame, t2c: dict, splits: pd.DataFrame | None, close_split_adjusted: bool = True) -> pd.DataFrame:
    """Je Monatsende alle zulässigen US-Titel mit PIT-Kennzahlen (≤ 200 Tage alt) und den Faktor-Rohwerten."""
    us = set(t2c)
    rows = []
    for d in _month_ends(P):
        for t in us_pool(P, d, us):
            rows.append((d, t, t2c[t]))
    q = pd.DataFrame(rows, columns=["date", "ticker", "cik"]).sort_values("date")
    m = pd.merge_asof(q, tl.sort_values("avail"), left_on="date", right_on="avail", by="cik", direction="backward")
    m = m[(m["date"] - m["filed"]).dt.days <= 200].copy()
    px, mom, sf = [], [], []
    sp_cache: dict = {}
    for r in m[["date", "ticker", "shares_end"]].itertuples(index=False):
        f = P.F[r.ticker]
        raw = P.raw[r.ticker]
        px.append(float(raw["Close"].get(r.date, np.nan)))
        mom.append(float(f["mom121"].get(r.date, np.nan)))
        if pd.isna(r.shares_end):
            sf.append(np.nan)
        else:
            k = (r.ticker, r.shares_end, None if close_split_adjusted else r.date)
            if k not in sp_cache:
                sp_cache[k] = split_factor(splits, r.ticker, r.shares_end, k[2])
            sf.append(sp_cache[k])
    m["close"], m["mom121"], m["split_f"] = px, mom, sf
    m["mcap"] = m["shares"] * m["split_f"] * m["close"]
    m.loc[~(m["mcap"] > 0), "mcap"] = np.nan
    m["ep"] = m["ni_ttm"] / m["mcap"]
    m["bp"] = np.where(m["equity"] > 0, m["equity"] / m["mcap"], -np.inf)
    m.loc[m["mcap"].isna(), "bp"] = np.nan
    m["cfp"] = m["ocf_ttm"] / m["mcap"]
    return m.replace([np.inf], np.nan)


def score_month(day: pd.DataFrame, sid: str) -> pd.DataFrame:
    day = day.copy()
    q = pd.concat([rank(day["gpa"]), rank(day["roa"])], axis=1).mean(axis=1, skipna=True)
    if sid == "K1":
        em = rank(day["em"])
        day["score"] = 0.5 * q + 0.5 * em
        day = day[q.notna() & em.notna()]
    else:
        v = pd.concat([rank(day["ep"]), rank(day["bp"]), rank(day["cfp"])], axis=1).mean(axis=1, skipna=True)
        mo = rank(day["mom121"])
        day["score"] = (q + v + mo) / 3
        day = day[q.notna() & v.notna() & mo.notna()]
    return day


def monthly_orders(mt: pd.DataFrame, sid: str, rng: np.random.Generator | None = None) -> tuple[list, dict, dict]:
    tops, info = {}, {}
    for d, day in mt.groupby("date"):
        sc = score_month(day, sid)
        if rng is None:
            pick = sc.sort_values("score", ascending=False)["ticker"].head(N_TOP).tolist()
        else:
            pool = sc["ticker"].to_numpy()          # Zufall: derselbe zulässige Pool (mit den nötigen Kennzahlen)
            pick = list(rng.choice(pool, min(N_TOP, len(pool)), replace=False)) if len(pool) else []
        tops[d] = pick
        info[d] = len(sc)
    orders, ex, prev = [], {}, []
    for d, pick in tops.items():
        for t in prev:
            if t not in pick:
                ex.setdefault(t, []).append(d)
        for k, t in enumerate(pick):
            orders.append(Order(d, t, weight=W, prio=-k, tag=sid))
        prev = pick
    return orders, ex, info


# ------------------------------------------------------------------ K3 PEAD
def pead_events(P, filings: pd.DataFrame, c2t: dict, spy: pd.Series) -> pd.DataFrame:
    """8-K Item 2.02 → Tag 0 (Annahme vor 16:00 New York = derselbe Handelstag, sonst nächster), EAR = Rendite
    Schluss Tag −1 → Schluss Tag +1 minus SPY. Entscheidung am Schluss von Tag +1."""
    f = filings[(filings["form"] == "8-K") & filings["items"].fillna("").str.contains("2.02", regex=False)].copy()
    f = f[f["cik"].isin(c2t)]
    acc = pd.to_datetime(f["accepted"], utc=True, errors="coerce").dt.tz_convert("America/New_York")
    f["acc_ny"] = acc
    out = []
    spy = spy.dropna()
    for r in f.dropna(subset=["acc_ny"]).itertuples(index=False):
        t = c2t[r.cik]
        if t not in P.F:
            continue
        idx = P.F[t].index
        day = pd.Timestamp(r.acc_ny.date())
        k = int(idx.searchsorted(day))
        if k >= len(idx):
            continue
        if idx[k] == day and r.acc_ny.hour >= 16:
            k += 1                                  # nach Börsenschluss → nächster Handelstag
        if k < 1 or k + 1 >= len(idx):
            continue
        d_m1, d0, d_p1 = idx[k - 1], idx[k], idx[k + 1]
        C = P.F[t]["C"]
        if d_m1 not in spy.index or d_p1 not in spy.index:
            continue
        ear = C.iat[k + 1] / C.iat[k - 1] - 1 - (spy[d_p1] / spy[d_m1] - 1)
        out.append({"ticker": t, "cik": r.cik, "accn": r.accn, "accepted_ny": str(r.acc_ny), "day0": d0, "decision": d_p1,
                    "ear": float(ear), "elig": bool(P.F[t]["elig"].iat[k + 1])})
    ev = pd.DataFrame(out).sort_values("decision")
    sig, last = [], {}
    for r in ev.itertuples(index=False):
        if not (r.ear >= EAR_MIN and r.elig and P.start <= r.decision <= P.end):
            continue
        if r.cik in last and (r.decision - last[r.cik]).days < PEAD_GAP:
            continue
        last[r.cik] = r.decision
        sig.append(r._asdict())
    return ev, pd.DataFrame(sig)


# ------------------------------------------------------------------ K4 Insider-Cluster
def insider_signals(P, ins: pd.DataFrame, c2t: dict) -> pd.DataFrame:
    x = ins[ins["cik"].isin(c2t)].copy()
    role = x["role"].fillna("")
    x = x[role.str.contains("Director") | role.str.contains("Officer")]
    x["value"] = x["shares"] * x["price"]
    x = x[(x["value"] > 0) & x["filed"].notna()]
    x["filed"] = pd.to_datetime(x["filed"])
    out = []
    for cik, g in x.groupby("cik"):
        t = c2t[cik]
        if t not in P.F:
            continue
        idx = P.F[t].index
        g = g.sort_values("filed")
        last = None
        for f in sorted(g["filed"].unique()):
            f = pd.Timestamp(f)
            w = g[(g["filed"] > f - timedelta(days=INS_WINDOW)) & (g["filed"] <= f)]
            n_own, val = w["owner"].nunique(), float(w["value"].sum())
            if n_own < INS_MIN_OWNERS or val < INS_MIN_USD:
                continue
            if last is not None and (f - last).days < INS_GAP:
                continue
            k = int(idx.searchsorted(f, side="right")) - 1     # letzter Handelstag ≤ Einreichungstag
            if k < 0:
                continue
            d = idx[k]
            last = f
            out.append({"ticker": t, "cik": cik, "filed": f, "decision": d, "owners": int(n_own), "value_usd": val,
                        "elig": bool(P.F[t]["elig"].iat[k])})
    s = pd.DataFrame(out)
    return s[s["elig"] & (s["decision"] >= P.start) & (s["decision"] <= P.end)].reset_index(drop=True)


def event_orders(sig: pd.DataFrame, sid: str, prio_col: str) -> list:
    return [Order(r["decision"], r["ticker"], weight=W, max_days=HOLD, prio=float(r[prio_col]), tag=sid)
            for _, r in sig.iterrows()]


def event_null(P, sig: pd.DataFrame, us: set, rng: np.random.Generator, sid: str) -> list:
    orders = []
    for d, n in sig.groupby("decision").size().items():
        pool = us_pool(P, d, us)
        if not pool:
            continue
        for t in rng.choice(pool, min(int(n), len(pool)), replace=False):
            orders.append(Order(d, t, weight=W, max_days=HOLD, prio=float(rng.random()), tag=f"{sid}-null"))
    return orders
