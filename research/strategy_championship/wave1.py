"""Phase C, Welle 1 – Signale der vorregistrierten Strategien (Protokoll v1.1, §5) und ihre Zufalls-Gegenstücke.

Alle Indikatoren je Titel auf dessen eigenen Handelstagen aus auto_adjust-Kursen; Querschnitts-Ränge (Terzile/Dezile)
je Kalendertag über die an diesem Tag zulässigen Titel (Grundfilter wie der Scanner: Ø-Dollarvolumen ≥ 5 Mio. USD,
Kurs ≥ 1, ≥ 300 Kerzen). Stops werden in bereinigten Kursen berechnet und mit dem Faktor des Entscheidungstags in
Handelskurse umgerechnet. Ereignis-Signale gelten nur „frisch“ (an den 5 Vortagen keine Bedingung erfüllt, wie S01).

Umsetzungsdetails (vorab festgelegt, für alle Varianten und ihre Null gleich):
- Je Tag und Strategie höchstens CAP = 20 Kandidaten (nach Ranking); nur freie Plätze werden gefüllt.
- Stop „n ATR“ = Schluss am Signaltag − n × ATR14 (Kauf erst am Folgetag).
- S13-Stock: täglich die (bis zu) 20 momentumstärksten Titel im Trend als Kandidaten.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backend.scanner import FX_USD

from . import s01
from .data import adjusted
from .engine import Order

CAP = 20
GAP = 5


def _rma(x: pd.Series, n: int) -> pd.Series:
    return x.ewm(alpha=1 / n, adjust=False).mean()


def _rsi(c: pd.Series, n: int) -> pd.Series:
    d = c.diff()
    up, dn = _rma(d.clip(lower=0), n), _rma(-d.clip(upper=0), n)
    rs = up / dn.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).where(dn > 0, 100.0)


def features(raw: pd.DataFrame, cur: str) -> pd.DataFrame:
    """Merkmale je Handelstag (bereinigte Kurse; f = Faktor für Handelskurse = bereinigt / f)."""
    c0 = s01.clean(raw)
    a = adjusted(c0)
    C, H, L, V = a["Close"], a["High"], a["Low"], a["Volume"].fillna(0)
    tr = pd.concat([H - L, (H - C.shift()).abs(), (L - C.shift()).abs()], axis=1).max(axis=1)
    out = pd.DataFrame(index=a.index)
    out["f"] = a["f"]
    out["C"] = C
    out["atr"] = _rma(tr, 14)
    out["ema200"] = C.ewm(span=200, adjust=False).mean()
    out["ema50"] = C.ewm(span=50, adjust=False).mean()
    out["rsi14"] = _rsi(C, 14)
    out["rsi2"] = _rsi(C, 2)
    out["sma5"] = C.rolling(5).mean()
    out["mom121"] = C.shift(21) / C.shift(252) - 1
    out["mom61"] = C.shift(21) / C.shift(126) - 1
    out["vol1y"] = np.log(C).diff().rolling(252).std() * np.sqrt(252)
    out["hi60"] = H.rolling(60).max()
    out["low10"] = L.rolling(10).min()
    out["rsi_min10"] = out["rsi14"].rolling(10).min()
    out["cmax55"] = C.rolling(55).max()
    out["cmax20"] = C.rolling(20).max()
    out["vratio"] = V / V.shift(1).rolling(50).mean()
    out["low20p"] = L.shift(1).rolling(20).min()
    out["ret5"] = C / C.shift(5) - 1
    out["elig"] = s01.eligible(a, cur)
    out.loc[out.index[:251], ["mom121", "vol1y"]] = np.nan
    return out


def fresh(cond: pd.Series) -> pd.Series:
    c = cond.fillna(False).astype(bool)
    prev = c.shift(1, fill_value=False).astype(int).rolling(GAP, min_periods=1).max().astype(bool)
    return c & ~prev


class Panel:
    """Merkmale aller Titel + Querschnitts-Ränge je Kalendertag."""

    def __init__(self, prices: dict, cur: dict, region: dict, bench: dict, start, end):
        self.F = {}
        for t, df in prices.items():
            if len(s01.clean(df)) >= 300:
                self.F[t] = features(df, cur.get(t, "USD"))
        self.start, self.end, self.region = start, end, region
        self.raw = {t: s01.clean(prices[t]) for t in self.F}
        long = pd.concat({t: f[["elig", "mom121", "mom61", "vol1y", "ret5"]] for t, f in self.F.items()}, names=["ticker", "date"])
        long = long.reset_index()
        long = long[long["elig"] & (long["date"] >= start - pd.Timedelta(days=10)) & (long["date"] <= end)]
        # Markt-Rendite 5 Tage: SPY (US-Region) bzw. STOXX 600 (EU)
        mk = []
        for reg, b in (("us", "SPY"), ("eu", "^STOXX")):
            s = bench[b]["AdjClose"]
            mk.append(pd.DataFrame({"date": s.index, "reg": reg, "mkt5": (s / s.shift(5) - 1).to_numpy()}))
        long["reg"] = long["ticker"].map(lambda t: "eu" if region.get(t) == "eu" else "us")
        long = long.merge(pd.concat(mk), on=["date", "reg"], how="left")
        long["rel5"] = long["ret5"] - long["mkt5"]
        g = long.groupby("date")
        long["mom_pct"] = g["mom121"].rank(pct=True)
        long["vol_pct"] = g["vol1y"].rank(pct=True)
        long["rel_pct"] = g["rel5"].rank(pct=True)
        self.X = long.set_index(["ticker", "date"]).sort_index()
        self.pool = {d: v["ticker"].to_numpy() for d, v in long.groupby("date")}

    # ---------------------------------------------------------- Strategien
    def _cs(self, t: str, col: str) -> pd.Series:
        try:
            return self.X.loc[t, col]
        except KeyError:
            return pd.Series(dtype=float)

    def candidates(self, sid: str) -> pd.DataFrame:
        """→ DataFrame [date, ticker, stop_adj, prio, max_days] (Ereignis-Strategien) im Zeitraum."""
        rows = []
        for t, f in self.F.items():
            e = f["elig"]
            if sid in ("S02-A", "S02-B"):
                cond = e & (f["C"] >= 1.15 * f["ema200"]) & (f["C"] / f["ema50"] - 1).between(-0.08, 0) & f["rsi14"].between(35, 50)
                if sid == "S02-A":
                    cond &= self._cs(t, "mom_pct").reindex(f.index).fillna(0) >= 2 / 3
                stop = np.minimum(f["low10"] - 0.25 * f["atr"], f["C"] - f["atr"])
                prio, md = f["mom121"], 20
            elif sid == "S03-P":
                mp = self._cs(t, "mom_pct").reindex(f.index).fillna(0)
                vp = self._cs(t, "vol_pct").reindex(f.index).fillna(1)
                cond = e & (mp >= 2 / 3) & (vp <= 1 / 3) & (f["C"] <= 0.88 * f["hi60"]) & (f["rsi_min10"] < 35) & (f["rsi14"] > f["rsi14"].shift())
                stop, prio, md = f["low10"] - 0.25 * f["atr"], -f["vol1y"], 20
            elif sid == "S04-M":
                rp = self._cs(t, "rel_pct").reindex(f.index).fillna(1)
                cond = e & (rp <= 0.10) & (f["C"] > f["ema200"])
                stop, prio, md = f["C"] - 3 * f["atr"], -rp, 5
            elif sid in ("S08-A", "S08-B"):
                hi = f["cmax55"] if sid == "S08-A" else f["cmax20"]
                cond = e & (f["C"] >= hi) & (f["vratio"] > 1.5) & (f["C"] > f["ema200"])
                stop, prio, md = f["C"] - 2 * f["atr"], f["vratio"], 60
            elif sid in ("S11-A", "S11-B"):
                lim = 10 if sid == "S11-A" else 5
                cond = e & (f["rsi2"] < lim) & (f["C"] > f["ema200"])
                stop, prio, md = f["C"] - 3 * f["atr"], -f["rsi2"], 10
            elif sid == "S13-S":
                cond = e & (f["C"] > f["ema200"]) & (f["ema50"] > f["ema200"])
                stop, prio, md = pd.Series(np.nan, index=f.index), f["mom121"], None
            else:
                raise KeyError(sid)
            if sid != "S13-S":
                cond = fresh(cond)
            m = cond & (f.index >= self.start) & (f.index <= self.end)
            if m.any():
                rows.append(pd.DataFrame({"date": f.index[m], "ticker": t, "stop_adj": stop[m].to_numpy(),
                                          "prio": prio[m].to_numpy(), "max_days": md}))
        df = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["date", "ticker", "stop_adj", "prio", "max_days"])
        df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=["prio"])
        return df.sort_values(["date", "prio"], ascending=[True, False]).groupby("date").head(CAP).reset_index(drop=True)

    def exits(self, sid: str, tickers) -> dict:
        """Signal-Ausstiege (Entscheidung nach Schluss → nächste Eröffnung) je Titel als Datumsliste."""
        out = {}
        for t in tickers:
            f = self.F.get(t)
            if f is None:
                continue
            if sid.startswith("S08"):
                c = f["C"] < f["low20p"]
            elif sid.startswith("S11"):
                c = f["C"] > f["sma5"]
            elif sid == "S13-S":
                c = f["C"] < f["ema200"]
            else:
                continue
            out[t] = f.index[c.fillna(False).to_numpy() & (f.index <= self.end)]
        return out

    def monthly(self, sid: str, rng: np.random.Generator | None = None) -> tuple[list, dict]:
        """S05: am letzten Handelstag jedes Monats Top 10 nach 12-1 (A) bzw. 6-1 (B); Null: 10 zufällige zulässige."""
        col = "mom121" if sid == "S05-A" else "mom61"
        X = self.X.reset_index()
        X = X[(X["date"] >= self.start) & (X["date"] <= self.end)]
        me = X.groupby(X["date"].dt.to_period("M"))["date"].max()
        tops = {}
        for d in me:
            day = X[X["date"] == d].dropna(subset=[col])
            if rng is None:
                pick = day.nlargest(10, col)["ticker"].tolist()
            else:
                pick = list(rng.choice(day["ticker"].to_numpy(), min(10, len(day)), replace=False)) if len(day) else []
            tops[d] = pick
        orders, ex = [], {}
        prev = []
        for d, pick in tops.items():
            for t in prev:
                if t not in pick:
                    ex.setdefault(t, []).append(d)
            for k, t in enumerate(pick):
                orders.append(Order(d, t, weight=0.099, prio=-k, tag=sid))
            prev = pick
        return orders, ex

    # ---------------------------------------------------------- Orders
    def orders(self, cand: pd.DataFrame, sid: str, risk: float | None, max_open: int) -> list[Order]:
        out = []
        for x in cand.itertuples(index=False):
            f = self.F[x.ticker]
            fac = f["f"].get(x.date)
            if fac is None or not np.isfinite(fac):
                continue
            if sid == "S13-S":
                out.append(Order(x.date, x.ticker, weight=0.99 / max_open, prio=float(x.prio), tag=sid))
            else:
                st = float(x.stop_adj) / fac
                if not np.isfinite(st) or st <= 0:
                    continue
                out.append(Order(x.date, x.ticker, stop=st, risk_frac=risk, prio=float(x.prio), tag=sid,
                                 max_days=None if pd.isna(x.max_days) else int(x.max_days)))
        return out

    def null_candidates(self, cand: pd.DataFrame, sid: str, seed: int) -> pd.DataFrame:
        """Gleich viele Kandidaten je Tag, zufällige zulässige Titel desselben Tages, Stop/Ausstieg nach derselben Regel."""
        rng = np.random.default_rng(seed)
        rows = []
        n_by_day = cand.groupby("date").size()
        for d, n in n_by_day.items():
            pool = self.pool.get(d)
            if pool is None or not len(pool):
                continue
            for k, t in enumerate(rng.choice(pool, min(n, len(pool)), replace=False)):
                f = self.F[t]
                if d not in f.index:
                    continue
                r = f.loc[d]
                if sid in ("S02-A", "S02-B"):
                    st = min(r["low10"] - 0.25 * r["atr"], r["C"] - r["atr"])
                elif sid == "S03-P":
                    st = r["low10"] - 0.25 * r["atr"]
                elif sid in ("S04-M", "S11-A", "S11-B"):
                    st = r["C"] - 3 * r["atr"]
                elif sid.startswith("S08"):
                    st = r["C"] - 2 * r["atr"]
                else:
                    st = np.nan
                md = {"S04-M": 5, "S11-A": 10, "S11-B": 10, "S08-A": 60, "S08-B": 60}.get(sid, 20 if sid != "S13-S" else None)
                rows.append({"date": d, "ticker": t, "stop_adj": st, "prio": float(rng.random()), "max_days": md})
        return pd.DataFrame(rows)


def spreads(prices: dict, cur: dict, region: dict) -> dict:
    out = {}
    for t, df in prices.items():
        adv = np.nanmedian((df["Close"] * df["Volume"]).rolling(20).mean().to_numpy()) if len(df) > 20 else np.nan
        adv = float(adv) * FX_USD.get(cur.get(t, "USD"), 1.0) if np.isfinite(adv) else 0.0
        out[t] = 0.003 if adv < 20e6 else (0.0015 if region.get(t) == "eu" else 0.001)
    return out
