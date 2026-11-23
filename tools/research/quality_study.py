"""Qualitäts-Studie (23.11.2026): Langfrist-Auswahl nach Qualität (+ Momentum) mit unseren SEC-Jahreszahlen – VORAB FESTGELEGT.

Daten: fin.json (Branch kairo-fin, SEC-Jahresabschlüsse 2014–2025 für ~1.590 US-Firmen) + Tageskurse (yfinance).
Kein Blick in die Zukunft: Ein Geschäftsjahr zählt erst 120 Tage nach seinem Ende (10-K muss vorliegen).
Achtung Überlebens-Verzerrung: nur heute gelistete Firmen. Gemessen wird sie mit der Kontrolle „alle gleich gewichtet“.

Qualitäts-Wert (Durchschnitt der Perzentil-Ränge, mind. 3 von 5 Kennzahlen):
  Kapitalrendite  operativer Gewinn / (Eigenkapital + Schulden − Cash)   (nur bei positivem eingesetztem Kapital)
  operative Marge operativer Gewinn / Umsatz
  FCF-Marge       freier Cashflow / Umsatz
  Beständigkeit   Anteil der Jahre mit Gewinn (letzte bis zu 5 Jahre)
  geringe Schulden  Schulden / operativer Gewinn (niedriger = besser; ohne Schulden = bester Rang)
Auswahl je Stichtag aus Aktien mit Ø Umsatz ≥ 5 Mio. $ am Tag und Kurs ≥ 5 $, gleich gewichtet, 20 Werte:
  Q   die 20 mit dem besten Qualitäts-Wert, jährlich umschichten
  QM  aus den 100 besten Qualitäts-Werten die 20 mit dem stärksten 12-Monats-Lauf (ohne letzten Monat), vierteljährlich
  QMj wie QM, jährlich
  M   nur Momentum (20 stärkste), vierteljährlich – Vergleich
  K   Kontrolle: alle gleich gewichtet, jährlich
Kosten 0,15 % je Umsatz, deutsche Steuer (26,375 %, Verlusttopf; ETF am Ende mit 30 % Teilfreistellung).
Lernen 2016–2020, Prüfen 2021–heute. Bestanden: nach Steuer im Lern- UND Prüfzeitraum ≥ 2 %-Punkte p. a. über dem
S&P-500-ETF UND über der Kontrolle K (sonst ist es nur Überlebens-Verzerrung) UND größter Rückgang ≤ 1,5 × ETF.

    python tools/research/quality_study.py prices SHARD SHARDS fin.json   → qpx_SHARD.pkl.gz
    python tools/research/quality_study.py study QPXDIR fin.json
"""
from __future__ import annotations

import gzip
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "research"))

LAG_DAYS = 120


def prices(shard, shards, finp):
    from backend.data_provider import YFinanceProvider
    fin = json.loads(Path(finp).read_text())["by"]
    tick = sorted(t for t, v in fin.items() if v.get("y"))[shard::shards]
    data = YFinanceProvider().history(tick, "12y")
    px = {t: df[["Close", "Volume"]].astype("float32") for t, df in data.items()}
    with gzip.open(f"qpx_{shard}.pkl.gz", "wb") as f:
        pickle.dump(px, f)
    print(f"Shard {shard}: {len(px)} von {len(tick)}")


def fy_table(fin):
    """→ Liste je Ticker: [(verfügbar_ab, kennzahlen-dict, ni-historie)]"""
    out = {}
    for t, v in fin.items():
        ys = v.get("y") or []
        if not ys:
            continue
        mm, dd = (v.get("fye") or "12-31").split("-")
        g = lambda k, i: (v.get(k) or [None] * len(ys))[i] if i < len(v.get(k) or []) else None
        rows = []
        for i, y in enumerate(ys):
            try:
                end = pd.Timestamp(int(y), int(mm), min(int(dd), 28))
            except Exception:
                continue
            rev, oi, ni, fcf, eq, debt, cash = (g(k, i) for k in ("rev", "oi", "ni", "fcf", "eq", "debt", "cash"))
            m = {}
            ic = (eq or 0) + (debt or 0) - (cash or 0)
            if oi is not None and eq is not None and ic > 0:
                m["roic"] = oi / ic
            if oi is not None and rev:
                m["opm"] = oi / rev
            if fcf is not None and rev:
                m["fcfm"] = fcf / rev
            nis = [x for x in (v.get("ni") or [])[max(0, i - 4): i + 1] if x is not None]
            if len(nis) >= 3:
                m["cons"] = sum(x > 0 for x in nis) / len(nis)
            if oi is not None:
                m["lev"] = -(debt or 0) / oi if oi > 0 else -1e9
            rows.append((end + pd.Timedelta(days=LAG_DAYS), m))
        out[t] = rows
    return out


def quality_at(d, fy, universe):
    rec = {}
    for t in universe:
        rows = fy.get(t)
        if not rows:
            continue
        av = [m for a, m in rows if a <= d]
        if av and len(av[-1]) >= 3:
            rec[t] = av[-1]
    if len(rec) < 50:
        return pd.Series(dtype=float)
    df = pd.DataFrame(rec).T
    return df.rank(pct=True).mean(axis=1, skipna=True)


def study(qdir, finp):
    from longterm_study import simulate, TAX, TFS
    from profit_study import _yf
    fin = json.loads(Path(finp).read_text())["by"]
    fy = fy_table(fin)
    px = {}
    for p in sorted(Path(qdir).glob("**/qpx_*.pkl.gz")):
        with gzip.open(p, "rb") as f:
            for t, df in pickle.load(f).items():
                df = df.copy()
                df.index = pd.to_datetime(df.index)
                if df.index.tz is not None:
                    df.index = df.index.tz_localize(None)
                px[t] = df[~df.index.normalize().duplicated(keep="last")]
    C = pd.DataFrame({t: df["Close"] for t, df in px.items() if len(df) > 300}).sort_index()
    V = pd.DataFrame({t: df["Close"] * df["Volume"] for t, df in px.items() if len(df) > 300}).sort_index()
    cm = C.resample("ME").last()
    adv = V.rolling(63, min_periods=40).mean().resample("ME").last()
    mom = cm.shift(1) / cm.shift(12) - 1
    print(f"VORAB FESTGELEGT (siehe Kopf). {C.shape[1]} US-Aktien mit Kursen, {len(fy)} mit Jahreszahlen, Monate {cm.index[0]:%m/%Y} – {cm.index[-1]:%m/%Y}", flush=True)
    liq = lambda d: list(cm.loc[d][(adv.loc[d] >= 5e6) & (cm.loc[d] >= 5)].dropna().index)
    qcache = {}

    def Q(d):
        if d not in qcache:
            qcache[d] = quality_at(d, fy, liq(d))
        return qcache[d]

    def sel_q(d):
        q = Q(d)
        return list(q.nlargest(20).index) if len(q) else None

    def sel_qm(d):
        q = Q(d)
        if not len(q):
            return None
        m = mom.loc[d, q.nlargest(100).index].dropna()
        return list(m.nlargest(20).index) if len(m) >= 20 else None

    def sel_m(d):
        m = mom.loc[d, liq(d)].dropna()
        return list(m.nlargest(20).index) if len(m) >= 50 else None

    strat = {"Q   Qualität Top 20 (jährlich)": (sel_q, 12), "QM  Qualität + Momentum (vierteljährlich)": (sel_qm, 3),
             "QMj Qualität + Momentum (jährlich)": (sel_qm, 12), "M   nur Momentum (vierteljährlich)": (sel_m, 3),
             "K   Kontrolle: alle gleich gewichtet (jährlich)": (lambda d: liq(d) or None, 12)}
    spy = _yf("SPY", "2010-01-01")["Close"].resample("ME").last()
    start = pd.Timestamp("2016-01-31")
    res = {}
    for pn, (a, b) in {"Lernen 2016–2020": (start, "2020-12-31"), "Prüfen 2021–heute": ("2021-01-01", None), "gesamt 2016–heute": (start, None)}.items():
        print(f"\n  -- {pn}")
        s0 = spy.loc[a:b]
        sp = s0 / s0.iloc[0]
        yrs = max(0.5, (len(sp) - 1) / 12)
        spt = sp.iloc[-1] - max(0, sp.iloc[-1] - 1) * TAX * (1 - TFS)
        res[("ETF", pn)] = ((spt ** (1 / yrs) - 1), float((1 - sp / sp.cummax()).max()))
        print(f"    {'S&P 500 ETF':48s} vor Steuer {(sp.iloc[-1] ** (1 / yrs) - 1) * 100:6.2f} % · nach Steuer {res[('ETF', pn)][0] * 100:6.2f} % p. a.  größter Rückgang {res[('ETF', pn)][1] * 100:5.1f} %")
        cmp = cm.loc[a:b]
        for name, (fn, every) in strat.items():
            e0 = simulate(cmp, fn, every, cmp.index[0], tax=False)
            e1 = simulate(cmp, fn, every, cmp.index[0], tax=True)
            pre = (e0.iloc[-1] / e0.iloc[0]) ** (1 / yrs) - 1
            post = (e1.iloc[-1] / e1.iloc[0]) ** (1 / yrs) - 1
            mdd = float((1 - e0 / e0.cummax()).max())
            res[(name, pn)] = (post, mdd)
            print(f"    {name:48s} vor Steuer {pre * 100:6.2f} % · nach Steuer {post * 100:6.2f} % p. a.  größter Rückgang {mdd * 100:5.1f} %", flush=True)
    print("\n  Bewertung nach den vorab festgelegten Kriterien:")
    K = "K   Kontrolle: alle gleich gewichtet (jährlich)"
    for name in list(strat)[:4]:
        ok = all(res[(name, p)][0] - res[("ETF", p)][0] >= 0.02 and res[(name, p)][0] > res[(K, p)][0]
                 and res[(name, p)][1] <= 1.5 * res[("ETF", p)][1] for p in ("Lernen 2016–2020", "Prüfen 2021–heute"))
        print(f"    {name}: {'BESTANDEN' if ok else 'nicht bestanden'}")
    d = cm.index[-1]
    print(f"\n  Heutige Auswahl QM ({d:%m/%Y}): {', '.join(sel_qm(d) or [])}")
    print(f"  Heutige Auswahl Q  ({d:%m/%Y}): {', '.join(sel_q(d) or [])}")


if __name__ == "__main__":
    if sys.argv[1] == "prices":
        prices(int(sys.argv[2]), int(sys.argv[3]), sys.argv[4])
    else:
        study(sys.argv[2], sys.argv[3])
