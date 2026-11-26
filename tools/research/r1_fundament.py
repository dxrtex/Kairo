"""Runde 1 „Fundament“ (26.11.2026): Wie belastbar ist die Langfrist-Regel wirklich?

Regel wie in der App (backend/langfrist.py): 12-1-Momentum, Kurs ≥ 5 $, Ø Umsatz 63 Tage ≥ 5 Mio. $, Top 10 kaufen,
behalten bis Platz 20, gleich gewichtet, Tausch am ersten Handelstag im Jan/Apr/Jul/Okt, Kauf zum Schlusskurs des Tauschtags.

Prüfungen (nur Analyse, keine Änderung an der App):
  1. Langer Zeitraum ab 2000 statt 2016 – inklusive Dotcom-Crash, 2008/09, 2020, 2022
  2. Überlebens-Verzerrung: heutige Aktienliste (≥ 2 Mrd. $ heute) gegen S&P-500-Mitglieder zum jeweiligen Zeitpunkt
  3. Glück beim Tauschtermin: andere Monate und gestaffelt (je ein Drittel)
  4. Stabilität: Raster Anzahl × Puffer × Momentum-Zeitraum
  5. Walk-forward: jedes Jahr die im Vorlauf (6 Jahre) beste Einstellung, gegen die feste Regel
  6. Bootstrap: Bandbreite über 10 Jahre (Blöcke von 12 Monaten), Wahrscheinlichkeit, den S&P 500 zu schlagen
  7. Nach Kosten und Abgeltungsteuer (26,375 %, Verlustverrechnung, Steuer jährlich)

Aufruf:  python tools/research/r1_fundament.py download --out px      (Kurse von Yahoo, einmalig)
         python tools/research/r1_fundament.py analyze  --px px --out r1.json
"""
from __future__ import annotations

import argparse
import io
import json
import math
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
START = "1998-01-01"
COST = 0.001                      # 0,10 % je Kauf/Verkauf (Spread + Gebühr, wie früherer Backtest)
TAX = 0.26375                     # Abgeltungsteuer + Soli
MIN_ADV, MIN_PX = 5e6, 5.0
LIVE = {"n": 10, "hold": 20, "lb": 12, "off": 0}
CRISES = [("Dotcom 2000–02", "2000-03-24", "2002-10-09"), ("Finanzkrise 2007–09", "2007-10-09", "2009-03-09"),
          ("Corona 2020", "2020-02-19", "2020-03-23"), ("Zinsen 2022", "2022-01-03", "2022-10-12"), ("Momentum-Crash 2009", "2009-03-09", "2009-06-30")]


# ---------------------------------------------------------------- Daten
def sp500_history() -> list:
    """S&P-500-Mitglieder zu jedem Stichtag seit 1996 (öffentlicher Datensatz github.com/fja05680/sp500), Yahoo-Ticker-Format.
    Liefert [(Datum, Menge der Ticker)] aufsteigend. Ticker verschwundener Firmen tragen dort oft ein Suffix „-JJJJMM“ – entfernt."""
    import re, requests
    h = {"User-Agent": "research-script", "Accept": "application/vnd.github+json"}
    lst = requests.get("https://api.github.com/repos/fja05680/sp500/contents", headers=h, timeout=30).json()
    files = sorted([f for f in lst if isinstance(f, dict) and f.get("name", "").startswith("S&P 500 Historical Components") and f["name"].endswith(".csv")], key=lambda f: f["name"])
    if not files:
        raise RuntimeError("Datensatz nicht gefunden")
    f = files[-1]
    print("S&P-500-Datensatz:", f["name"], flush=True)
    df = pd.read_csv(io.StringIO(requests.get(f["download_url"], headers={"User-Agent": "research-script"}, timeout=60).text))
    fix = lambda t: re.sub(r"-\d{6}$", "", t.strip()).replace(".", "-")
    snaps = [(pd.Timestamp(r["date"]), {fix(t) for t in str(r["tickers"]).split(",") if t.strip()}) for _, r in df.iterrows()]
    snaps.sort(key=lambda x: x[0])
    return snaps


def members_at(snaps: list, d: pd.Timestamp) -> set:
    lo, hi = 0, len(snaps) - 1
    if not snaps or d < snaps[0][0]:
        return set()
    while lo < hi:                          # letzter Stand am oder vor d
        mid = (lo + hi + 1) // 2
        if snaps[mid][0] <= d:
            lo = mid
        else:
            hi = mid - 1
    return snaps[lo][1]


def download(out: Path) -> None:
    import yfinance as yf
    out.mkdir(parents=True, exist_ok=True)
    uni = pd.read_csv(ROOT / "data" / "universe_us.csv", dtype={"ticker": str})
    today = sorted({t for t in uni["ticker"] if isinstance(t, str) and "." not in t and "^" not in t})
    try:
        snaps = sp500_history()
    except Exception as e:                       # ohne Datensatz: nur die heutige Liste (Prüfung 2 entfällt dann)
        print("S&P-500-Historie nicht verfügbar:", repr(e), flush=True)
        snaps = []
    hist = set().union(*[m for _, m in snaps]) if snaps else set()
    tickers = sorted(set(today) | hist | {"SPY", "ACWI", "URTH"})
    print(f"heutige US-Liste {len(today)} · S&P 500 jemals Mitglied {len(hist)} · zusammen {len(tickers)}", flush=True)
    C, V = {}, {}
    for i in range(0, len(tickers), 150):
        batch = tickers[i:i + 150]
        for att in range(3):
            try:
                df = yf.download(batch, start=START, interval="1d", group_by="ticker", auto_adjust=True, threads=True, progress=False)
                break
            except Exception as e:
                print("  Wiederholung", e, flush=True)
                time.sleep(5)
        else:
            continue
        for t in batch:
            try:
                sub = df[t] if isinstance(df.columns, pd.MultiIndex) else df
                c = sub["Close"].dropna()
                if len(c) > 260:
                    C[t] = c
                    V[t] = sub["Volume"].reindex(c.index)
            except Exception:
                pass
        print(f"  {min(i + 150, len(tickers))}/{len(tickers)} geladen, mit Kursen {len(C)}", flush=True)
    close = pd.DataFrame(C).sort_index()
    vol = pd.DataFrame(V).reindex(close.index)
    pickle.dump({"close": close, "vol": vol, "today": today, "snaps": snaps}, open(out / "px.pkl", "wb"))
    print("gespeichert:", close.shape, flush=True)


# ---------------------------------------------------------------- Rechenkern
class Engine:
    def __init__(self, close: pd.DataFrame, vol: pd.DataFrame, spy: pd.Series):
        idx = spy.dropna().index
        self.C = close.reindex(idx).ffill(limit=5)          # Kurse an US-Handelstagen; nach Ende der Notierung bleiben Lücken
        self.Craw = close.reindex(idx)
        dv = (close * vol).reindex(idx)
        self.ADV = dv.rolling(63, min_periods=40).mean()
        self.idx = idx
        self.cnt = self.Craw.notna().cumsum()
        self.spy = spy.reindex(idx).ffill()
        self._rk = {}

    def dates(self, off: int, start: str, end: str | None = None) -> list[pd.Timestamp]:
        months = {((m - 1 + off) % 12) + 1 for m in (1, 4, 7, 10)}
        s = pd.Series(self.idx, index=self.idx)
        firsts = s.groupby([self.idx.year, self.idx.month]).first()
        e = pd.Timestamp(end) if end else self.idx[-1]
        return [d for (y, m), d in firsts.items() if m in months and pd.Timestamp(start) <= d <= e]

    def ranking(self, d: pd.Timestamp, lb: int, elig: set | None, key: str) -> list[str]:
        k = (d, lb, key)
        if k in self._rk:
            return self._rk[k]
        p = self.idx.get_loc(d)
        if p < lb * 21 + 5:
            self._rk[k] = []
            return []
        last, a, b = self.C.iloc[p - 1], self.C.iloc[p - 21], self.C.iloc[p - lb * 21]
        ok = (self.cnt.iloc[p - 1] >= lb * 21 + 5) & (last >= MIN_PX) & (a > 0) & (b > 0) & (self.ADV.iloc[p - 1] >= MIN_ADV)
        ok &= self.Craw.iloc[p - 1].notna()                 # am Vortag noch notiert
        mom = (a / b - 1)[ok].dropna()
        if elig is not None:
            mom = mom[mom.index.isin(elig)]
        order = list(mom.sort_values(ascending=False).index)
        self._rk[k] = order
        return order

    def path(self, n: int, hold: int, lb: int, off: int, start: str, end: str | None, elig_fn=None, key: str = "all") -> list:
        held, out = [], []
        for d in self.dates(off, start, end):
            order = self.ranking(d, lb, elig_fn(d) if elig_fn else None, key)
            keep = set(order[:max(hold, n)])
            held = [t for t in held if t in keep]
            for t in order:
                if len(held) >= n:
                    break
                if t not in held:
                    held.append(t)
            out.append((d, list(held)))
        return out

    def curve(self, path: list, cost: float = COST) -> pd.Series:
        """Tägliche Wertentwicklung, gleich gewichtet je Periode, Kosten auf den Umschlag."""
        vals, v0, prev = [], 1.0, {}
        for k, (d, held) in enumerate(path):
            end = path[k + 1][0] if k + 1 < len(path) else self.idx[-1]
            days = self.idx[(self.idx >= d) & (self.idx <= end)]
            if not held:
                seg = pd.Series(v0, index=days)
            else:
                w = 1 / len(held)
                tgt = {t: w for t in held}
                turn = sum(abs(tgt.get(t, 0) - prev.get(t, 0)) for t in set(tgt) | set(prev))
                v0 *= (1 - cost * turn)
                px = self.C.loc[days, held]
                rel = px / px.iloc[0]
                rel = rel.ffill().fillna(1.0)
                seg = rel.mean(axis=1) * v0
                last = rel.iloc[-1]
                tot = float(last.sum())
                prev = {t: float(last[t]) / tot for t in held} if tot > 0 else {}
            vals.append(seg if not vals else seg.iloc[1:])
            v0 = float(seg.iloc[-1])
        return pd.concat(vals) if vals else pd.Series(dtype=float)


# ---------------------------------------------------------------- Steuer (Stückzahlen, Einstandskurse, Verlusttopf, Steuer jährlich)
def after_tax(eng: Engine, path: list, start_val: float = 10_000.0) -> dict:
    cash, units, basis, pot, taxpaid, gains_y = start_val, {}, {}, 0.0, 0.0, 0.0
    vals = []
    yr = None
    for k, (d, held) in enumerate(path):
        px = eng.C.loc[d]
        if yr is not None and d.year != yr:            # Jahressteuer
            tx = max(0.0, gains_y + pot)
            pot = min(0.0, gains_y + pot)
            t = tx * TAX
            cash -= t
            taxpaid += t
            gains_y = 0.0
        yr = d.year
        val = cash + sum(units[t] * (px.get(t) if pd.notna(px.get(t)) else basis[t] / max(units[t], 1e-12)) for t in units)
        w = val / len(held) if held else 0
        # verkaufen/abbauen
        for t in list(units):
            p = px.get(t)
            if pd.isna(p):
                p = float(eng.C[t].loc[:d].dropna().iloc[-1]) if eng.C[t].loc[:d].notna().any() else 0.0
            tgt_u = (w / p) if (t in held and p > 0) else 0.0
            if units[t] > tgt_u + 1e-12:
                q = units[t] - tgt_u
                proceeds = q * p * (1 - COST)
                cb = basis[t] * q / units[t]
                gains_y += proceeds - cb
                basis[t] -= cb
                units[t] = tgt_u
                cash += proceeds
                if units[t] <= 1e-12:
                    units.pop(t); basis.pop(t)
        for t in held:
            p = px.get(t)
            if pd.isna(p) or p <= 0:
                continue
            cur = units.get(t, 0.0)
            tgt_u = w / p
            if tgt_u > cur + 1e-12:
                spend = min(cash, (tgt_u - cur) * p)
                q = spend * (1 - COST) / p
                units[t] = cur + q
                basis[t] = basis.get(t, 0.0) + spend
                cash -= spend
        end = path[k + 1][0] if k + 1 < len(path) else eng.idx[-1]
        days = eng.idx[(eng.idx >= d) & (eng.idx < end)] if k + 1 < len(path) else eng.idx[eng.idx >= d]
        if len(units):
            pv = eng.C.loc[days, list(units)].ffill().fillna(0) @ pd.Series(units)
        else:
            pv = pd.Series(0.0, index=days)
        vals.append(pv + cash)
    s = pd.concat(vals)
    # am Ende alles verkaufen und versteuern
    fin = float(s.iloc[-1])
    unreal = sum(units[t] * float(eng.C[t].dropna().iloc[-1]) - basis[t] for t in units)
    tx = max(0.0, gains_y + pot + unreal) * TAX
    fin_net = fin - tx
    yrs = (s.index[-1] - s.index[0]).days / 365.25
    return {"end": round(fin_net), "cagr": round((fin_net / start_val) ** (1 / yrs) - 1, 4), "tax": round(taxpaid + tx), "series": s}


# ---------------------------------------------------------------- Kennzahlen
def stats(s: pd.Series) -> dict:
    s = s.dropna()
    if len(s) < 30:
        return {}
    yrs = (s.index[-1] - s.index[0]).days / 365.25
    r = s.pct_change().dropna()
    cagr = (s.iloc[-1] / s.iloc[0]) ** (1 / yrs) - 1
    dd = (s / s.cummax() - 1).min()
    vol = r.std() * math.sqrt(252)
    down = r[r < 0].std() * math.sqrt(252)
    yr = s.resample("YE").last().pct_change().dropna()
    first_y = s.resample("YE").last().iloc[0] / s.iloc[0] - 1
    yr = pd.concat([pd.Series([first_y], index=[s.resample("YE").last().index[0]]), yr])
    roll = (s / s.shift(252) - 1).dropna()
    # längste Zeit unter dem alten Hoch
    under = s < s.cummax()
    longest, cur, start = 0, 0, None
    for v in under:
        cur = cur + 1 if v else 0
        longest = max(longest, cur)
    return {"cagr": round(cagr, 4), "vol": round(vol, 4), "sharpe": round(cagr / vol, 3) if vol else None, "sortino": round(cagr / down, 3) if down else None,
            "mdd": round(dd, 4), "worst_y": round(float(yr.min()), 4), "best_y": round(float(yr.max()), 4), "worst_12m": round(float(roll.min()), 4) if len(roll) else None,
            "uw_days": int(longest), "years": round(yrs, 1)}


def mix(a: pd.Series, b: pd.Series, w: float = 0.3) -> pd.Series:
    """w Strategie, 1−w ETF, Ausgleich jährlich (erster Handelstag im Jahr)."""
    idx = a.index.intersection(b.index)
    ra, rb = a.reindex(idx).pct_change().fillna(0), b.reindex(idx).pct_change().fillna(0)
    v, wa, out, y = 1.0, w, [], None
    for d in idx:
        if y is not None and d.year != y:
            wa = w
        y = d.year
        g = wa * (1 + ra[d]) + (1 - wa) * (1 + rb[d])
        wa = wa * (1 + ra[d]) / g if g else w
        v *= g
        out.append(v)
    return pd.Series(out, index=idx)


def fmt(st: dict) -> str:
    if not st:
        return "–"
    return (f"CAGR {st['cagr']*100:6.1f} %  Sharpe {st['sharpe']:.2f}  MaxDD {st['mdd']*100:6.1f} %  schlechtestes Jahr {st['worst_y']*100:6.1f} %  "
            f"schlechteste 12 M {st['worst_12m']*100:6.1f} %  längste Zeit unter Hoch {st['uw_days']} T.")


# ---------------------------------------------------------------- Auswertung
def analyze(px: Path, out: Path) -> None:
    D = pickle.load(open(px / "px.pkl", "rb"))
    close, vol = D["close"], D["vol"]
    spy = close["SPY"].dropna()
    eng = Engine(close, vol, spy)
    today = set(D["today"]) & set(close.columns)
    snaps = D.get("snaps") or []
    cur = bool(snaps)
    R = {"meta": {}}
    first_change = snaps[0][0] if snaps else None
    hist = set().union(*[m for _, m in snaps]) if snaps else set()
    have = hist & set(close.columns)
    R["meta"] = {"today_universe": len(today), "sp500_ever": len(hist), "sp500_with_prices": len(have), "sp500_missing": len(hist - have),
                 "changes_from": str(first_change.date()) if first_change is not None else None, "price_cols": int(close.shape[1]),
                 "first_day": str(eng.idx[0].date()), "last_day": str(eng.idx[-1].date())}
    print("Daten:", json.dumps(R["meta"], ensure_ascii=False), flush=True)
    elig_today = lambda d: today
    mem_cache = {}
    def elig_pit(d):
        k = d.strftime("%Y-%m")
        if k not in mem_cache:
            mem_cache[k] = members_at(snaps, d)
        return mem_cache[k]
    spy_c = eng.spy
    UNIS = [("today", elig_today)] + ([("sp500pit", elig_pit)] if cur else [])
    acwi = close["ACWI"].dropna() if "ACWI" in close else None

    def run(n=10, hold=20, lb=12, off=0, start="2000-01-01", end=None, el=elig_today, key="today", cost=COST):
        p = eng.path(n, hold, lb, off, start, end, el, key)
        return p, eng.curve(p, cost)

    # 1) langer Zeitraum, beide Universen
    print("\n===== 1) Regel wie in der App, lange Historie =====", flush=True)
    R["long"] = {}
    for key, el in UNIS:
        for st0 in ("2000-01-01", "2008-01-01", "2016-01-01"):
            p, s = run(start=st0, el=el, key=key)
            b = spy_c.reindex(s.index)
            m = mix(s, b, .3)
            row = {"strat": stats(s), "spy": stats(b), "mix70_30_spy": stats(m)}
            R["long"][f"{key}|{st0[:4]}"] = row
            print(f"  {key:9s} ab {st0[:4]}  Strategie {fmt(row['strat'])}", flush=True)
            print(f"  {'':9s}          S&P 500   {fmt(row['spy'])}", flush=True)
            print(f"  {'':9s}          70/30     {fmt(row['mix70_30_spy'])}", flush=True)
    # 2) Krisen
    print("\n===== 2) Krisen (Regel, heutige Liste und S&P-500-Mitglieder) =====", flush=True)
    R["crises"] = {}
    for key, el in UNIS:
        p, s = run(start="2000-01-01", el=el, key=key)
        for nm, a, b_ in CRISES:
            ss, bb = s.loc[a:b_], spy_c.loc[a:b_]
            if len(ss) < 5:
                continue
            r = {"strat": round(float(ss.iloc[-1] / ss.iloc[0] - 1), 4), "spy": round(float(bb.iloc[-1] / bb.iloc[0] - 1), 4),
                 "strat_mdd": round(float((ss / ss.cummax() - 1).min()), 4)}
            R["crises"][f"{key}|{nm}"] = r
            print(f"  {key:9s} {nm:22s} Strategie {r['strat']*100:7.1f} %  (tiefster Punkt {r['strat_mdd']*100:6.1f} %)  S&P 500 {r['spy']*100:7.1f} %", flush=True)
    # 3) Tauschtermin-Glück
    print("\n===== 3) Tauschtermin: andere Monate und gestaffelt =====", flush=True)
    R["timing"] = {}
    for key, el in UNIS:
        ss = []
        for off, lbl in ((0, "Jan/Apr/Jul/Okt"), (1, "Feb/Mai/Aug/Nov"), (2, "Mär/Jun/Sep/Dez")):
            p, s = run(off=off, start="2000-01-01", el=el, key=key)
            ss.append(s)
            R["timing"][f"{key}|{lbl}"] = stats(s)
            print(f"  {key:9s} {lbl:16s} {fmt(stats(s))}", flush=True)
        idx = ss[0].index.intersection(ss[1].index).intersection(ss[2].index)
        stag = sum(x.reindex(idx) / x.reindex(idx).iloc[0] for x in ss) / 3
        R["timing"][f"{key}|gestaffelt"] = stats(stag)
        print(f"  {key:9s} {'gestaffelt (⅓)':16s} {fmt(stats(stag))}", flush=True)
    # 4) Stabilität – Raster (heutige Liste und S&P-500-Mitglieder, ab 2000, vor Steuer)
    print("\n===== 4) Raster Anzahl × Puffer × Momentum (Sharpe / CAGR / MaxDD) =====", flush=True)
    R["grid"] = {}
    for key, el in UNIS:
        for lb in (6, 9, 12):
            for n in (5, 10, 15, 20, 30):
                cells = []
                for hold in (n, 2 * n, 3 * n):
                    p, s = run(n=n, hold=hold, lb=lb, start="2000-01-01", el=el, key=key)
                    st_ = stats(s)
                    R["grid"][f"{key}|lb{lb}|n{n}|h{hold}"] = st_
                    cells.append(f"h{hold:<3d} {st_['sharpe']:.2f}/{st_['cagr']*100:5.1f}%/{st_['mdd']*100:5.0f}%")
                print(f"  {key:9s} lb {lb:2d} n {n:2d}  " + "   ".join(cells), flush=True)
    # 5) Walk-forward (jedes Jahr beste Einstellung der letzten 6 Jahre)
    print("\n===== 5) Walk-forward =====", flush=True)
    R["wf"] = {}
    configs = [(n, h, lb) for lb in (6, 9, 12) for n in (5, 10, 15, 20) for h in (n, 2 * n, 3 * n)]
    for key, el in UNIS:
        curves = {}
        for c in configs:
            p, s = run(n=c[0], hold=c[1], lb=c[2], start="2000-01-01", el=el, key=key)
            curves[c] = s
        rets = pd.DataFrame({c: s.pct_change() for c, s in curves.items()}).fillna(0)
        live = (LIVE["n"], LIVE["hold"], LIVE["lb"])
        wf, picks = [], []
        for y in range(2007, eng.idx[-1].year + 1):
            tr = rets.loc[f"{y-6}-01-01":f"{y-1}-12-31"]
            if len(tr) < 500:
                continue
            sh = tr.mean() / tr.std()
            best = sh.idxmax()
            picks.append((y, best))
            wf.append(rets.loc[f"{y}-01-01":f"{y}-12-31", best])
        wfr = pd.concat(wf)
        wfs = (1 + wfr).cumprod()
        lv = (1 + rets[live].loc[wfr.index]).cumprod()
        sp = spy_c.reindex(wfr.index)
        R["wf"][key] = {"walkforward": stats(wfs), "fixed_live": stats(lv), "spy": stats(sp), "picks": [(y, list(c)) for y, c in picks]}
        print(f"  {key:9s} Walk-forward   {fmt(stats(wfs))}", flush=True)
        print(f"  {key:9s} feste Regel    {fmt(stats(lv))}", flush=True)
        print(f"  {key:9s} S&P 500        {fmt(stats(sp))}", flush=True)
        print(f"  {key:9s} gewählt: " + ", ".join(f"{y}: Top {c[0]}/Puffer {c[1]}/{c[2]} M." for y, c in picks), flush=True)
    # 6) Bootstrap über 10 Jahre (12-Monats-Blöcke, gleiche Monate für Strategie und S&P 500)
    print("\n===== 6) Bootstrap 10 Jahre =====", flush=True)
    R["boot"] = {}
    rng = np.random.default_rng(7)
    for key, el in UNIS:
        p, s = run(start="2000-01-01", el=el, key=key)
        ms = s.resample("ME").last().pct_change().dropna()
        mb = spy_c.reindex(s.index).resample("ME").last().pct_change().reindex(ms.index).fillna(0)
        mm = 0.3 * ms + 0.7 * mb
        N, B, H = len(ms), 12, 120
        res = {"cagr": [], "mdd": [], "beat": [], "mix_cagr": [], "mix_mdd": [], "spy_cagr": []}
        for _ in range(5000):
            starts = rng.integers(0, N - B, H // B)
            ii = np.concatenate([np.arange(s0, s0 + B) for s0 in starts])
            a, b, c = ms.values[ii], mb.values[ii], mm.values[ii]
            va, vb, vc = np.cumprod(1 + a), np.cumprod(1 + b), np.cumprod(1 + c)
            res["cagr"].append(va[-1] ** (1 / 10) - 1); res["spy_cagr"].append(vb[-1] ** (1 / 10) - 1); res["mix_cagr"].append(vc[-1] ** (1 / 10) - 1)
            res["mdd"].append(float((va / np.maximum.accumulate(va) - 1).min())); res["mix_mdd"].append(float((vc / np.maximum.accumulate(vc) - 1).min()))
            res["beat"].append(va[-1] > vb[-1])
        q = lambda x, p_: round(float(np.percentile(x, p_)), 4)
        R["boot"][key] = {"cagr_p10": q(res["cagr"], 10), "cagr_p50": q(res["cagr"], 50), "cagr_p90": q(res["cagr"], 90),
                          "mdd_p50": q(res["mdd"], 50), "mdd_p10": q(res["mdd"], 10), "p_beat_spy": round(float(np.mean(res["beat"])), 3),
                          "mix_cagr_p10": q(res["mix_cagr"], 10), "mix_cagr_p50": q(res["mix_cagr"], 50), "mix_mdd_p10": q(res["mix_mdd"], 10),
                          "spy_cagr_p50": q(res["spy_cagr"], 50)}
        b_ = R["boot"][key]
        print(f"  {key:9s} Strategie 10 J.: CAGR 10 %-Fall {b_['cagr_p10']*100:.1f} % · Median {b_['cagr_p50']*100:.1f} % · 90 %-Fall {b_['cagr_p90']*100:.1f} % · "
              f"MaxDD Median {b_['mdd_p50']*100:.0f} % (schlimmer Fall {b_['mdd_p10']*100:.0f} %) · schlägt S&P 500 in {b_['p_beat_spy']*100:.0f} % der Fälle", flush=True)
        print(f"  {key:9s} 70/30 10 J.:     CAGR 10 %-Fall {b_['mix_cagr_p10']*100:.1f} % · Median {b_['mix_cagr_p50']*100:.1f} % · MaxDD schlimmer Fall {b_['mix_mdd_p10']*100:.0f} % · S&P 500 Median {b_['spy_cagr_p50']*100:.1f} %", flush=True)
    # 7) nach Kosten und Steuer (Regel wie in der App)
    print("\n===== 7) Nach Kosten und Abgeltungsteuer (10.000 €, Regel wie in der App) =====", flush=True)
    R["tax"] = {}
    for key, el in UNIS:
        for st0 in ("2000-01-01", "2016-01-01"):
            p = eng.path(10, 20, 12, 0, st0, None, el, key)
            at = after_tax(eng, p)
            pre = stats(eng.curve(p))
            spy_net = spy_c.loc[at["series"].index[0]:]
            g = float(spy_net.iloc[-1] / spy_net.iloc[0])
            yrs = (spy_net.index[-1] - spy_net.index[0]).days / 365.25
            spy_after = ((1 + (g - 1) * (1 - TAX)) ** (1 / yrs) - 1)
            R["tax"][f"{key}|{st0[:4]}"] = {"pre_tax_cagr": pre.get("cagr"), "after_tax_cagr": at["cagr"], "tax": at["tax"], "end": at["end"], "spy_after_tax_cagr": round(spy_after, 4)}
            print(f"  {key:9s} ab {st0[:4]}: vor Steuer {pre.get('cagr', 0)*100:.1f} % p. a. · nach Steuer {at['cagr']*100:.1f} % p. a. · Steuer gesamt {at['tax']:,} € · "
                  f"S&P 500 kaufen & halten nach Steuer {spy_after*100:.1f} %", flush=True)
    out.write_text(json.dumps(R, ensure_ascii=False, indent=1, default=str))
    print("\nfertig →", out, flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["download", "analyze"])
    ap.add_argument("--out", default="r1")
    ap.add_argument("--px", default="px")
    a = ap.parse_args()
    if a.cmd == "download":
        download(Path(a.out))
    else:
        analyze(Path(a.px), Path(a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
