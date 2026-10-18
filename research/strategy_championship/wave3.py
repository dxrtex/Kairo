"""S19 Hybride Mean Reversion und S20 Trendfolge/VCP nach Nutzer-Spezifikation (Protokoll v1.5/v1.6).

H4-Auslöser als Tageskerzen-Ersatz; Größe zeitpunktgenau über Liquidität bzw. heutige Marktkapitalisierung (nur US).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .data import adjusted
from .engine import Order
from .wave1 import fresh

SECTOR_ETF = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
WINDOW = 5


YAHOO_ETF = {"Technology": "XLK", "Financial Services": "XLF", "Healthcare": "XLV", "Consumer Cyclical": "XLY",
             "Consumer Defensive": "XLP", "Energy": "XLE", "Industrials": "XLI", "Basic Materials": "XLB",
             "Utilities": "XLU", "Real Estate": "XLF", "Communication Services": "XLK"}   # XLRE/XLC gab es 2008 noch nicht


def prepare(P, bench: dict, sectors: dict | None = None, qmode: str = "pit", mcap: dict | None = None) -> None:
    """qmode „pit“: Größe zeitpunktgenau über Ø-Dollarvolumen 20 T. ≥ 100 Mio. USD; „today“: heutige Marktkapitalisierung
    ≥ 10 Mrd. USD (Rückschaufehler). Operative Marge: mit Gratisdaten nicht zeitpunktgenau verfügbar → nicht geprüft."""
    from backend.scanner import FX_USD
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
        if us:
            if qmode == "today":
                x["qual"] = bool((mcap or {}).get(t, 0) >= 10e9)
            else:
                dv = (C * V).rolling(20).mean() * FX_USD.get("USD", 1.0)
                x["qual"] = (dv >= 100e6).to_numpy()
            etf = YAHOO_ETF.get((sectors or {}).get(t), "SPY")
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


# ------------------------------------------------------------------ S19-Varianten (Protokoll v1.7)
def s19_variant(P, sigma: float = 2.5, vol: str = "strict", entry: str = "trigger") -> tuple[pd.DataFrame, dict]:
    """Wie s19_candidates, aber mit Schwelle `sigma`, Volumen „strict“ (V_t<V_t−1<V_t−2) oder „2of3“ (mind. 2 der letzten 3
    Tagesvergleiche sinkend) und Einstieg „trigger“ (Tageskerzen-Ersatz H4, wie v1.5) oder „open“ (nächste Eröffnung, CRV am
    Signaltag mit Stop = Signaltag-Tief − 0,5 ATR). → Kandidaten + Zähler (Signale, Auslöser, CRV ok)."""
    rows, n = [], {"signale": 0, "ausloeser": 0, "crv_ok": 0}
    for t, x in P.G.items():
        if not x["us"].iloc[0]:
            continue
        C, O, H, L, V = x["C"], x["O"], x["H"], x["L"], x["V"]
        down3 = (C < C.shift(1)) & (C.shift(1) < C.shift(2)) & (C.shift(2) < C.shift(3))
        if vol == "strict":
            vex = (V < V.shift(1)) & (V.shift(1) < V.shift(2))
        else:
            vex = ((V < V.shift(1)).astype(int) + (V.shift(1) < V.shift(2)).astype(int) + (V.shift(2) < V.shift(3)).astype(int)) >= 2
        sig = x["elig"] & x["qual"] & (x["ret3"] < x["sec3"]) & (C <= x["ema20"] - sigma * x["std20"]) & down3 & vex
        sig = sig & (x.index >= P.start) & (x.index <= P.end)
        if not sig.any():
            continue
        red_high = H.where(C < O).ffill().shift(1)
        trig = (C > O) & (C > red_high)
        idx, last_t = x.index, -1
        for s in np.flatnonzero(sig.to_numpy()):
            if s <= last_t:
                continue
            n["signale"] += 1
            z = (C.iloc[s] - x["ema20"].iloc[s]) / x["std20"].iloc[s]
            if entry == "open":
                sl = L.iloc[s] - 0.5 * x["atr"].iloc[s]
                c, tp = C.iloc[s], x["ema20"].iloc[s]
                n["ausloeser"] += 1
                if c > sl and tp - c >= 2 * (c - sl) and s + 1 < len(idx) and idx[s] <= P.end:
                    n["crv_ok"] += 1
                    rows.append({"date": idx[s], "ticker": t, "stop_adj": sl, "prio": -z, "bull": bool(x["bull"].iloc[s])})
                    last_t = s + WINDOW
                continue
            for k in range(s + 1, min(s + 1 + WINDOW, len(idx))):
                if idx[k] > P.end:
                    break
                if not trig.iloc[k]:
                    continue
                n["ausloeser"] += 1
                sl = L.iloc[s:k + 1].min() - 0.5 * x["atr"].iloc[k]
                c, tp = C.iloc[k], x["ema20"].iloc[k]
                if c > sl and tp - c >= 2 * (c - sl):
                    n["crv_ok"] += 1
                    rows.append({"date": idx[k], "ticker": t, "stop_adj": sl, "prio": -z, "bull": bool(x["bull"].iloc[k])})
                last_t = k
                break
    return pd.DataFrame(rows, columns=["date", "ticker", "stop_adj", "prio", "bull"]), n
