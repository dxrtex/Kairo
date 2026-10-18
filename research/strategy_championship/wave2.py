"""Phase C, Welle 2 – vorregistrierte Strategien (Protokoll v1.2) auf dem Panel aus Welle 1.

S06-P  Residual-Momentum (Proxy: nur Marktfaktor SPY bzw. STOXX 600, keine Fama-French-Faktoren), Top 10 monatlich
S07    Risikobereinigtes Momentum, Top 10 monatlich (A: 12-1 / Vol 1 J., B: 6-1 / Vol 6 M.)
S09    Ausbruch aus enger Basis (A: 20-T.-Spanne ≤ 10 %, B: ATR10/ATR50 < 0,6), Schluss > 20-T.-Hoch, Volumen > 1,5×, > EMA200
S14    US-Sektorrotation mit 9 Select-Sector-ETFs, Top 3 monatlich (A: 6-M.-Rendite, B: 12-1)
S16    Dual Momentum (A: SPY/EFA, absolut gegen BIL, sonst SHY; B: SPY/EFA/QQQ Top 1, sonst SHY)

Monatsende = letzter Handelstag des Monats im Panel; Kauf zur nächsten Eröffnung; Verkauf bei Ausscheiden (nächste Eröffnung).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .data import adjusted
from .engine import Order
from .wave1 import GAP, fresh

SECTORS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]


def extra(P) -> None:
    """Zusätzliche Merkmale je Titel (in P.F ergänzt)."""
    for t, f in P.F.items():
        a = adjusted(P.raw[t])
        H, L, C = a["High"], a["Low"], a["Close"]
        tr = pd.concat([H - L, (H - C.shift()).abs(), (L - C.shift()).abs()], axis=1).max(axis=1)
        f["vol6m"] = np.log(C).diff().rolling(126).std() * np.sqrt(252)
        f["hmax20p"] = H.shift(1).rolling(20).max()
        f["lmin20p"] = L.shift(1).rolling(20).min()
        f["range20p"] = (f["hmax20p"] - f["lmin20p"]) / C.shift(1)
        f["atr_ratio"] = (tr.ewm(alpha=1 / 10, adjust=False).mean() / tr.ewm(alpha=1 / 50, adjust=False).mean()).shift(1)


def _month_ends(P) -> list:
    X = P.X.reset_index()
    X = X[(X["date"] >= P.start) & (X["date"] <= P.end)]
    return list(X.groupby(X["date"].dt.to_period("M"))["date"].max())


def _resid_scores(P, bench) -> dict:
    """S06-P: je Titel und Monatsende Summe der Residuen (Monat −12 … −2) / Std der Residuen (36 Mon.)."""
    mk = {}
    for reg, b in (("us", "SPY"), ("eu", "^STOXX")):
        s = bench[b]["AdjClose"]
        mk[reg] = s.groupby(s.index.to_period("M")).last().pct_change()
    out = {}
    for t, f in P.F.items():
        m = f["C"].groupby(f.index.to_period("M")).last().pct_change()
        mkt = mk["eu" if P.region.get(t) == "eu" else "us"].reindex(m.index)
        df = pd.DataFrame({"r": m, "m": mkt}).dropna()
        if len(df) < 37:
            continue
        r, x = df["r"].to_numpy(), df["m"].to_numpy()
        sc = {}
        for k in range(36, len(df) + 1):
            rr, xx = r[k - 36:k], x[k - 36:k]          # 36 Monate bis einschließlich Bewertungsmonat df.index[k-1]
            v = xx.var()
            if v <= 0:
                continue
            b = np.cov(rr, xx, bias=True)[0, 1] / v
            a = rr.mean() - b * xx.mean()
            res = rr - a - b * xx
            sd = res.std()
            if sd > 0:
                sc[df.index[k - 1]] = res[-12:-1].sum() / sd   # Monate −12 … −2 relativ zum Bewertungsmonat
        out[t] = pd.Series(sc)
    return out


def monthly_stock(P, sid: str, bench=None, rng=None, n: int = 10, regime=None) -> tuple[list, dict]:
    """S06-P, S07-A/B: Top 10 je Monatsende unter den zulässigen Titeln; Null: 10 zufällige zulässige.
    regime: Menge der Monatsenden, an denen investiert werden darf (sonst alles verkaufen) – Phase D, S07-B-T."""
    if sid == "S06-P" and not hasattr(P, "_resid"):
        P._resid = _resid_scores(P, bench)
    tops, prev, orders, ex = {}, [], [], {}
    for d in _month_ends(P):
        pool = P.pool.get(d)
        if pool is None or not len(pool):
            continue
        if regime is not None and d not in regime:
            tops[d] = []
            continue
        if rng is not None:
            tops[d] = list(rng.choice(pool, min(n, len(pool)), replace=False))
            continue
        sc = {}
        per = pd.Timestamp(d).to_period("M")
        for t in pool:
            f = P.F[t]
            if sid == "S06-P":
                s = P._resid.get(t)
                v = s.get(per) if s is not None else None              # Residuen Monat −11 … −1, Regression 36 Mon. bis „per“
            else:
                r = f.loc[d] if d in f.index else None
                if r is None:
                    continue
                v = r["mom121"] / r["vol1y"] if sid == "S07-A" else r["mom61"] / r["vol6m"]
            if v is not None and np.isfinite(v):
                sc[t] = v
        tops[d] = [t for t, _ in sorted(sc.items(), key=lambda x: -x[1])[:n]]
    for d, pick in tops.items():
        for t in prev:
            if t not in pick:
                ex.setdefault(t, []).append(d)
        for k, t in enumerate(pick):
            orders.append(Order(d, t, weight=0.99 / n, prio=-k, tag=sid))
        prev = pick
    return orders, ex


def s09_candidates(P, sid: str) -> pd.DataFrame:
    rows = []
    for t, f in P.F.items():
        base = (f["range20p"] <= 0.10) if sid == "S09-A" else (f["atr_ratio"] < 0.6)
        cond = f["elig"] & base & (f["C"] > f["hmax20p"]) & (f["vratio"] > 1.5) & (f["C"] > f["ema200"])
        cond = fresh(cond)
        m = cond & (f.index >= P.start) & (f.index <= P.end)
        if m.any():
            rows.append(pd.DataFrame({"date": f.index[m], "ticker": t,
                                      "stop_adj": (f["lmin20p"] - 0.25 * f["atr"])[m].to_numpy(),
                                      "prio": f["vratio"][m].to_numpy(), "max_days": 60}))
    df = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["date", "ticker", "stop_adj", "prio", "max_days"])
    df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=["prio", "stop_adj"])
    return df.sort_values(["date", "prio"], ascending=[True, False]).groupby("date").head(20).reset_index(drop=True)


def s09_null(P, cand: pd.DataFrame, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for d, n in cand.groupby("date").size().items():
        pool = P.pool.get(d)
        if pool is None or not len(pool):
            continue
        for t in rng.choice(pool, min(n, len(pool)), replace=False):
            f = P.F[t]
            if d not in f.index:
                continue
            r = f.loc[d]
            rows.append({"date": d, "ticker": t, "stop_adj": r["lmin20p"] - 0.25 * r["atr"], "prio": float(rng.random()),
                         "max_days": 60})
    return pd.DataFrame(rows).dropna(subset=["stop_adj"])


def etf_rotation(bench: dict, sid: str, start, end, rng=None) -> tuple[list, dict, list]:
    """S14/S16 auf US-ETFs (Gesamtrendite aus AdjClose). → Orders, Ausstiege, beteiligte Ticker."""
    if sid.startswith("S14"):
        uni = SECTORS
    elif sid == "S16-A":
        uni = ["SPY", "EFA", "SHY"]
    else:
        uni = ["SPY", "EFA", "QQQ", "SHY"]
    adj = pd.DataFrame({t: bench[t]["AdjClose"] for t in uni + ["BIL"] if t in bench}).sort_index()
    adj = adj[adj.index <= end]
    me = adj.groupby(adj.index.to_period("M")).tail(1)
    me = me[me.index >= start]
    full = adj.groupby(adj.index.to_period("M")).tail(1)
    tops, orders, ex, prev = {}, [], {}, []
    for d in me.index:
        k = full.index.get_loc(d)
        def ret(t, m, skip=0):
            if k - m < 0 or not np.isfinite(full[t].iloc[k - m]) or not np.isfinite(full[t].iloc[k - skip]):
                return np.nan
            return full[t].iloc[k - skip] / full[t].iloc[k - m] - 1
        if rng is not None:
            n = 3 if sid.startswith("S14") else 1
            pool = [t for t in uni if np.isfinite(full[t].iloc[k])]
            pick = list(rng.choice(pool, min(n, len(pool)), replace=False))
        elif sid.startswith("S14"):
            sc = {t: (ret(t, 6) if sid == "S14-A" else ret(t, 12, 1)) for t in SECTORS}
            pick = [t for t, v in sorted(sc.items(), key=lambda x: -x[1]) if np.isfinite(v)][:3]
        else:
            risky = ["SPY", "EFA"] if sid == "S16-A" else ["SPY", "EFA", "QQQ"]
            sc = {t: ret(t, 12) for t in risky}
            best = max(sc, key=lambda t: sc[t] if np.isfinite(sc[t]) else -9)
            bil = ret("BIL", 12)
            if not np.isfinite(sc[best]) or not np.isfinite(bil):
                pick = []                                # noch keine 12 Monate Historie → Cash
            else:
                pick = [best] if sc[best] > bil else ["SHY"]
        tops[d] = pick
    for d, pick in tops.items():
        for t in prev:
            if t not in pick:
                ex.setdefault(t, []).append(d)
        w = 0.99 / max(1, len(pick))
        for j, t in enumerate(pick):
            orders.append(Order(d, t, weight=w, prio=-j, tag=sid))
        prev = pick
    return orders, ex, uni
