"""Momentum v2 (23.11.2026): Gibt es eine bessere Positions-Strategie als „Top 20 nach 12-1-Momentum“? – VORAB FESTGELEGT.

Alle Kandidaten: 20 US-Aktien, gleich gewichtet, Tausch alle 3 Monate, ohne Marktfilter, gleiches Universum (Ø Umsatz ≥ 5 Mio. $,
Kurs ≥ 5 $), 0,15 % Kosten je Umsatz, deutsche Steuer. Bekannte Varianten aus der Forschung:
  A  heutige Regel: 12-1-Momentum (Jegadeesh/Titman)
  B  risikobereinigt: 12-1-Lauf / Schwankung der Tagesrenditen 12 M. (Barroso/Santa-Clara-Idee auf Aktienebene)
  C  52-Wochen-Hoch: Kurs / 52-Wochen-Hoch, höchste Nähe (George/Hwang 2004)
  D  „Frog in the Pan“: aus den 100 stärksten 12-1 die 20 mit dem stetigsten Anstieg (Anteil positiver Tage, Da/Gurun/Warachka 2014)
  E  doppelt: Mittel der Ränge 12-1 und 6-1
  F  12-1 nur über der eigenen 200-Tage-Linie
Auswahl NUR nach Lernzeitraum 2016–2020 (Rendite nach Steuer, größter Rückgang ≤ 1,5 × ETF). Ersetzt die heutige Regel nur,
wenn der Lern-Sieger ≠ A ist UND auch im Prüfzeitraum 2021–heute besser als A ist.

    python tools/research/momentum_v2.py QPXDIR
"""
from __future__ import annotations

import gzip
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "research"))


def main(qdir):
    from longterm_study import simulate, TAX, TFS
    from profit_study import _yf
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
    R = C.pct_change()
    me = lambda x: x.resample("ME").last()
    cm = me(C)
    adv = me(V.rolling(63, min_periods=40).mean())
    m12 = cm.shift(1) / cm.shift(12) - 1
    m6 = cm.shift(1) / cm.shift(6) - 1
    vol = me(R.rolling(252, min_periods=200).std())
    hi52 = me(C / C.rolling(252, min_periods=200).max())
    pos = me((R > 0).astype(float).where(R.notna()).rolling(252, min_periods=200).mean())
    above = me(C > C.rolling(200, min_periods=180).mean())
    print(f"VORAB FESTGELEGT (siehe Kopf). {C.shape[1]} US-Aktien, {cm.index[0]:%m/%Y} – {cm.index[-1]:%m/%Y}", flush=True)

    def uni(d):
        return (adv.loc[d] >= 5e6) & (cm.loc[d] >= 5)

    def pick(score):
        def f(d):
            s = score(d)
            s = s[uni(d)].replace([np.inf, -np.inf], np.nan).dropna() if s is not None else None
            return list(s.nlargest(20).index) if s is not None and len(s) >= 50 else None
        return f

    def frog(d):
        m = m12.loc[d][uni(d)].dropna()
        if len(m) < 50:
            return None
        top = m.nlargest(100).index
        return list(pos.loc[d, top].dropna().nlargest(20).index)

    cands = {
        "A 12-1-Momentum (heute)": pick(lambda d: m12.loc[d]),
        "B risikobereinigt (Lauf/Schwankung)": pick(lambda d: m12.loc[d] / vol.loc[d]),
        "C Nähe 52-Wochen-Hoch": pick(lambda d: hi52.loc[d] + m12.loc[d] * 1e-6),
        "D Frog in the Pan (stetige Gewinner)": frog,
        "E doppelt 12-1 + 6-1": pick(lambda d: m12.loc[d].rank() + m6.loc[d].rank()),
        "F 12-1 nur über 200-Tage-Linie": pick(lambda d: m12.loc[d].where(above.loc[d].astype(bool))),
    }
    spy = _yf("SPY", "2010-01-01")["Close"].resample("ME").last()
    per = {"L": (pd.Timestamp("2016-01-31"), "2020-12-31"), "P": ("2021-01-01", None)}
    etf = {}
    for k, (a, b) in per.items():
        sp = spy.loc[a:b] / spy.loc[a:b].iloc[0]
        yrs = (len(sp) - 1) / 12
        etf[k] = ((sp.iloc[-1] - max(0, sp.iloc[-1] - 1) * TAX * (1 - TFS)) ** (1 / yrs) - 1, float((1 - sp / sp.cummax()).max()))
    print(f"  ETF nach Steuer: Lernen {etf['L'][0] * 100:.1f} % (Rückg. {etf['L'][1] * 100:.0f} %) · Prüfen {etf['P'][0] * 100:.1f} % (Rückg. {etf['P'][1] * 100:.0f} %)\n")
    res = {}
    for name, fn in cands.items():
        r = {}
        for k, (a, b) in per.items():
            cmp = cm.loc[a:b]
            e = simulate(cmp, fn, 3, cmp.index[0], tax=True)
            yrs = (len(e) - 1) / 12
            r[k] = (e.iloc[-1] / e.iloc[0]) ** (1 / yrs) - 1
            r[k + "dd"] = float((1 - e / e.cummax()).max())
            mret = e.pct_change().dropna()
            r[k + "sh"] = float(mret.mean() / mret.std() * np.sqrt(12)) if mret.std() > 0 else 0.0
        res[name] = r
        print(f"  {name:40s} Lernen {r['L'] * 100:6.1f} % (Rückg. {r['Ldd'] * 100:3.0f} %, Sharpe {r['Lsh']:.2f}) | "
              f"Prüfen {r['P'] * 100:6.1f} % (Rückg. {r['Pdd'] * 100:3.0f} %, Sharpe {r['Psh']:.2f})", flush=True)
    ok = {k: v for k, v in res.items() if v["Ldd"] <= 1.5 * etf["L"][1]} or res
    best = max(ok, key=lambda k: ok[k]["L"])
    A = "A 12-1-Momentum (heute)"
    print(f"\n  Lern-Sieger: {best}")
    if best == A:
        print("  → heutige Regel bleibt (sie ist auch im Lernzeitraum die beste)")
    elif res[best]["P"] > res[A]["P"]:
        print(f"  → ERSETZEN: {best} ist im Lern- und Prüfzeitraum besser ({res[best]['P'] * 100:.1f} % statt {res[A]['P'] * 100:.1f} %)")
    else:
        print(f"  → heutige Regel bleibt: {best} war nur im Lernzeitraum besser (Prüfen {res[best]['P'] * 100:.1f} % statt {res[A]['P'] * 100:.1f} %)")


if __name__ == "__main__":
    main(sys.argv[1])
