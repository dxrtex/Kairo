"""S19 Hybride Mean Reversion und S20 Trendfolge/VCP nach Nutzer-Spezifikation (Protokoll v1.5).

H4-Auslöser als Tageskerzen-Ersatz; Fundamentaldaten aus EDGAR (nur US). Siehe 02_PROTOCOL.md, Nachtrag v1.5.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .data import adjusted
from .engine import Order
from .wave1 import fresh

SECTOR_ETF = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
WINDOW = 5
STALE = pd.Timedelta(days=548)


def sic_to_etf(sic) -> str:
    try:
        s = int(sic)
    except (TypeError, ValueError):
        return "SPY"
    if 6000 <= s <= 6799:
        return "XLF"
    if 4900 <= s <= 4999:
        return "XLU"
    if 1300 <= s <= 1399 or 2900 <= s <= 2999:
        return "XLE"
    if 2830 <= s <= 2836 or 3840 <= s <= 3851 or 8000 <= s <= 8099:
        return "XLV"
    if 3570 <= s <= 3579 or 3660 <= s <= 3679 or 7370 <= s <= 7379 or 3820 <= s <= 3829 or 4800 <= s <= 4899:
        return "XLK"
    if 2000 <= s <= 2199 or 2840 <= s <= 2844 or 5400 <= s <= 5499 or 5140 <= s <= 5149 or 5912 == s:
        return "XLP"
    if 3710 <= s <= 3716 or 5000 <= s <= 5999 or 7000 <= s <= 7299 or 7800 <= s <= 7999 or 2300 <= s <= 2399 \
            or 2500 <= s <= 2599 or 3630 <= s <= 3652 or 3940 <= s <= 3949 or 1520 <= s <= 1531 or 2700 <= s <= 2799:
        return "XLY"
    if 1000 <= s <= 1499 or 2600 <= s <= 2699 or 2800 <= s <= 2829 or 2850 <= s <= 2899 or 3200 <= s <= 3399:
        return "XLB"
    if 1500 <= s <= 1799 or 3400 <= s <= 3569 or 3580 <= s <= 3659 or 3680 <= s <= 3839 or 3852 <= s <= 3999 \
            or 4000 <= s <= 4799 or 7300 <= s <= 7369 or 7380 <= s <= 7399 or 8700 <= s <= 8799:
        return "XLI"
    return "SPY"


def quality(fund: pd.DataFrame, t: str, idx: pd.DatetimeIndex) -> pd.Series:
    """Je Handelstag: Streubesitz ≥ 10 Mrd. USD (≤ 18 Mon. alt) und operative Marge > 0 (letztes veröffentlichtes GJ)."""
    f = fund[fund["ticker"] == t]
    if f.empty:
        return pd.Series(False, index=idx)
    days = pd.DataFrame({"date": idx})
    fl = f[f["kind"] == "float"].assign(filed=lambda x: pd.to_datetime(x["filed"])).sort_values("filed")
    ok_f = pd.Series(False, index=idx)
    if len(fl):
        m = pd.merge_asof(days, fl[["filed", "val"]], left_on="date", right_on="filed", direction="backward")
        ok_f = pd.Series(((m["val"] >= 10e9) & (m["date"] - m["filed"] <= STALE)).to_numpy(), index=idx)
    an = f[f["kind"].isin(["rev", "opinc", "netinc"])].copy()
    ok_m = pd.Series(False, index=idx)
    if len(an):
        an["filed"] = pd.to_datetime(an["filed"])
        piv = an.sort_values("filed").groupby(["end", "kind"]).agg(val=("val", "first"), filed=("filed", "first")).reset_index()
        w = piv.pivot(index="end", columns="kind", values="val")
        fd = piv.groupby("end")["filed"].max()
        if "rev" in w:
            inc = w["opinc"] if "opinc" in w else pd.Series(np.nan, index=w.index)
            if "netinc" in w:
                inc = inc.fillna(w["netinc"])
            mg = (inc / w["rev"]).rename("mg")
            mm = pd.DataFrame({"filed": fd, "mg": mg}).dropna().sort_values("filed")
            if len(mm):
                m = pd.merge_asof(days, mm, left_on="date", right_on="filed", direction="backward")
                ok_m = pd.Series(((m["mg"] > 0) & (m["date"] - m["filed"] <= STALE)).to_numpy(), index=idx)
    return ok_f & ok_m


def prepare(P, bench: dict, fund: pd.DataFrame | None, sic: dict) -> None:
    g = bench["^GSPC"]["Close"]
    P.bull = (g > g.ewm(span=200, adjust=False).mean())
    sec = {e: (bench[e]["AdjClose"] / bench[e]["AdjClose"].shift(3) - 1) for e in SECTOR_ETF + ["SPY"]}
    P.G = {}
    for t, f in P.F.items():
        a = adjusted(P.raw[t])
        C, O, H, L, V = a["Close"], a["Open"], a["High"], a["Low"], a["Volume"].fillna(0)
        x = pd.DataFrame(index=a.index)
        x["C"], x["O"], x["H"], x["L"], x["V"], x["f"] = C, O, H, L, V, a["f"]
        x["atr"] = f["atr"]
        x["ema20"] = C.ewm(span=20, adjust=False).mean()
        x["std20"] = C.rolling(20).std()
        x["ema50"], x["ema200"] = f["ema50"], f["ema200"]
        mid, sd = C.rolling(20).mean(), C.rolling(20).std()
        x["bbw"] = 4 * sd / mid
        x["bbw_ma"] = x["bbw"].rolling(20).mean()
        x["h50"], x["l50"] = H.rolling(50).max(), L.rolling(50).min()
        x["vma20"] = V.rolling(20).mean()
        x["ret3"] = C / C.shift(3) - 1
        x["bull"] = P.bull.reindex(a.index, method="ffill").fillna(False).astype(bool)
        x["elig"] = f["elig"]
        us = P.region.get(t) == "us" and not t.endswith(".TO")
        x["us"] = us
        if us and fund is not None:
            x["qual"] = quality(fund, t, a.index).to_numpy()
            etf = sic_to_etf(sic.get(t))
            x["sec3"] = sec[etf].reindex(a.index, method="ffill").to_numpy()
        else:
            x["qual"] = False
            x["sec3"] = np.nan
        P.G[t] = x


# ------------------------------------------------------------------ S19
def s19_candidates(P) -> pd.DataFrame:
    rows = []
    for t, x in P.G.items():
        if not x["us"].iloc[0]:
            continue
        C, O, H, L, V = x["C"], x["O"], x["H"], x["L"], x["V"]
        down3 = (C < C.shift(1)) & (C.shift(1) < C.shift(2)) & (C.shift(2) < C.shift(3))
        vex = (V < V.shift(1)) & (V.shift(1) < V.shift(2))
        sig = x["elig"] & x["qual"] & (x["ret3"] < x["sec3"]) & (C <= x["ema20"] - 2.5 * x["std20"]) & down3 & vex
        sig = sig & (x.index >= P.start) & (x.index <= P.end)
        if not sig.any():
            continue
        red_high = H.where(C < O).ffill().shift(1)
        trig = (C > O) & (C > red_high)
        idx = x.index
        last_t = -1
        for s in np.flatnonzero(sig.to_numpy()):
            if s <= last_t:
                continue                              # Signal fällt in ein schon laufendes Auslöse-Fenster
            for k in range(s + 1, min(s + 1 + WINDOW, len(idx))):
                if idx[k] > P.end:
                    break
                if not trig.iloc[k]:
                    continue
                panic = L.iloc[s:k + 1].min()
                sl = panic - 0.5 * x["atr"].iloc[k]
                c, tp = C.iloc[k], x["ema20"].iloc[k]
                if c > sl and tp - c >= 2 * (c - sl):
                    z = (C.iloc[s] - x["ema20"].iloc[s]) / x["std20"].iloc[s]
                    rows.append({"date": idx[k], "ticker": t, "stop_adj": sl, "prio": -z, "bull": bool(x["bull"].iloc[k])})
                    last_t = k
                break
    return pd.DataFrame(rows, columns=["date", "ticker", "stop_adj", "prio", "bull"])


def s19_pool(P) -> dict:
    pool = {}
    for t, x in P.G.items():
        if not x["us"].iloc[0]:
            continue
        m = x["elig"] & x["qual"] & (x["C"] < x["ema20"]) & (x.index >= P.start) & (x.index <= P.end)
        for d in x.index[m.to_numpy()]:
            pool.setdefault(d, []).append(t)
    return {d: np.array(v) for d, v in pool.items()}


def s19_null(P, cand: pd.DataFrame, seed: int) -> pd.DataFrame:
    rng, rows = np.random.default_rng(seed), []
    for d, g in cand.groupby("date"):
        pool = P.pool19.get(d)
        if pool is None:
            continue
        got = 0
        for t in rng.permutation(pool):
            x = P.G[t]
            r = x.loc[d]
            sl = r["L"] - 0.5 * r["atr"]
            if r["C"] > sl and r["ema20"] - r["C"] >= 2 * (r["C"] - sl):
                rows.append({"date": d, "ticker": t, "stop_adj": sl, "prio": float(rng.random()), "bull": bool(r["bull"])})
                got += 1
                if got >= len(g):
                    break
    return pd.DataFrame(rows, columns=["date", "ticker", "stop_adj", "prio", "bull"])


def s19_orders(P, cand: pd.DataFrame) -> list[Order]:
    out = []
    for x in cand.itertuples(index=False):
        fac = P.G[x.ticker]["f"].get(x.date)
        if fac is None or not np.isfinite(fac):
            continue
        out.append(Order(x.date, x.ticker, stop=float(x.stop_adj) / fac, risk_frac=0.01 if x.bull else 0.005,
                         max_open_cap=None if x.bull else 2, exit_rule=("touch_ema",), prio=float(x.prio), tag="S19"))
    return out


# ------------------------------------------------------------------ S20
def s20_candidates(P) -> pd.DataFrame:
    rows = []
    for t, x in P.G.items():
        C = x["C"]
        r = x["h50"] - x["l50"]
        hi, lo = x["h50"] - 0.5 * r, x["h50"] - 0.618 * r
        near = ((C / x["ema50"] - 1).abs() <= 0.015) | ((C >= lo * 0.985) & (C <= hi * 1.015))
        setup = x["elig"] & x["bull"] & (C > x["ema50"]) & (x["ema50"] > x["ema200"]) & (x["bbw"] < x["bbw_ma"]) & near
        recent = setup.shift(1, fill_value=False).astype(int).rolling(WINDOW, min_periods=1).max().astype(bool)
        trig = (C > x["ema20"] * 1.01) & (x["V"] > x["vma20"]) & x["bull"] & x["elig"]
        ent = fresh(recent & trig) & (x.index >= P.start) & (x.index <= P.end)
        if ent.any():
            rows.append(pd.DataFrame({"date": x.index[ent.to_numpy()], "ticker": t, "atr": x["atr"][ent].to_numpy(),
                                      "prio": (x["V"] / x["vma20"])[ent].to_numpy()}))
    df = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["date", "ticker", "atr", "prio"])
    df = df.replace([np.inf, -np.inf], np.nan).dropna()
    return df.sort_values(["date", "prio"], ascending=[True, False]).groupby("date").head(20).reset_index(drop=True)


def s20_null(P, cand: pd.DataFrame, seed: int) -> pd.DataFrame:
    rng, rows = np.random.default_rng(seed), []
    for d, g in cand.groupby("date"):
        pool = P.pool.get(d)
        if pool is None:
            continue
        for t in rng.choice(pool, min(len(g), len(pool)), replace=False):
            x = P.G.get(t)
            if x is None or d not in x.index:
                continue
            rows.append({"date": d, "ticker": t, "atr": float(x.at[d, "atr"]), "prio": float(rng.random())})
    return pd.DataFrame(rows, columns=["date", "ticker", "atr", "prio"]).dropna()


def s20_orders(P, cand: pd.DataFrame) -> list[Order]:
    out = []
    for x in cand.itertuples(index=False):
        fac = P.G[x.ticker]["f"].get(x.date)
        if fac is None or not np.isfinite(fac) or not (x.atr > 0):
            continue
        a = float(x.atr) / fac
        out.append(Order(x.date, x.ticker, stop_from_fill=1.5 * a, risk_frac=0.01, trail=("be_prevlow", 2.0 * a),
                         prio=float(x.prio), tag="S20"))
    return out
