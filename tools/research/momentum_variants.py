"""Momentum-Varianten (23.11.2026): Welche Positions-Strategie bringt nach Steuern am meisten? – VORAB FESTGELEGT.

Raster (36 Varianten): Anzahl 10 / 20 / 30 · Lauf 12-1 Monate / 6-1 Monate · Tausch alle 1 / 3 / 6 Monate ·
Marktfilter aus / an (S&P 500 unter 200-Tage-Linie am Monatsende → nicht neu kaufen, Bestand in Cash).
Universum: US-Aktien aus fin.json mit Ø Umsatz ≥ 5 Mio. $ am Tag und Kurs ≥ 5 $ (Kurse aus quality.yml).
Kosten 0,15 % je Umsatz, deutsche Steuer (Verlusttopf), ETF am Ende mit 30 % Teilfreistellung.
Auswahl NUR nach Lernzeitraum 2016–2020: höchste Rendite nach Steuer mit größtem Rückgang ≤ 1,5 × ETF.
Bestätigung 2021–heute: über ETF nach Steuer. Zusätzlich je Stellschraube der Durchschnitt über alle Varianten
(robuster als die eine beste).

    python tools/research/momentum_variants.py QPXDIR
"""
from __future__ import annotations

import gzip
import itertools
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
    cm = C.resample("ME").last()
    adv = V.rolling(63, min_periods=40).mean().resample("ME").last()
    mom = {12: cm.shift(1) / cm.shift(12) - 1, 6: cm.shift(1) / cm.shift(6) - 1}
    spyd = _yf("SPY", "2010-01-01")["Close"]
    spy = spyd.resample("ME").last()
    up = (spyd > spyd.rolling(200).mean()).resample("ME").last().reindex(cm.index).ffill()
    print(f"VORAB FESTGELEGT (siehe Kopf). {C.shape[1]} US-Aktien, Monate {cm.index[0]:%m/%Y} – {cm.index[-1]:%m/%Y}", flush=True)

    def sel(n, lb, filt, ev):
        """Wird jeden Monat aufgerufen: neue Auswahl nur alle ev Monate; Marktfilter monatlich (raus in Cash / wieder rein)."""
        st = {"k": -1, "cur": None, "out": False}

        def f(d):
            st["k"] += 1
            down = filt and not bool(up.get(d, True))
            if down:
                st["out"] = True
                return []                                   # leere Liste = alles verkaufen, Cash halten
            if st["k"] % ev == 0 or st["out"] or st["cur"] is None:
                st["out"] = False
                m = mom[lb].loc[d][(adv.loc[d] >= 5e6) & (cm.loc[d] >= 5)].dropna()
                st["cur"] = list(m.nlargest(n).index) if len(m) >= 50 else None
                return st["cur"]
            return None                                     # None = nichts tun
        return f

    per = {"L": (pd.Timestamp("2016-01-31"), "2020-12-31"), "P": ("2021-01-01", None)}
    etf = {}
    for k, (a, b) in per.items():
        s0 = spy.loc[a:b]
        sp = s0 / s0.iloc[0]
        yrs = (len(sp) - 1) / 12
        etf[k] = ((sp.iloc[-1] - max(0, sp.iloc[-1] - 1) * TAX * (1 - TFS)) ** (1 / yrs) - 1, float((1 - sp / sp.cummax()).max()))
    print(f"  ETF S&P 500 nach Steuer: Lernen {etf['L'][0] * 100:.1f} % (Rückgang {etf['L'][1] * 100:.0f} %) · Prüfen {etf['P'][0] * 100:.1f} % (Rückgang {etf['P'][1] * 100:.0f} %)\n")
    rows = []
    for n, lb, ev, filt in itertools.product((10, 20, 30), (12, 6), (1, 3, 6), (False, True)):
        r = {"n": n, "lb": lb, "ev": ev, "filt": filt}
        for k, (a, b) in per.items():
            cmp = cm.loc[a:b]
            e = simulate(cmp, sel(n, lb, filt, ev), 1, cmp.index[0], tax=True)
            yrs = (len(e) - 1) / 12
            r[k] = (e.iloc[-1] / e.iloc[0]) ** (1 / yrs) - 1
            r[k + "dd"] = float((1 - e / e.cummax()).max())
        rows.append(r)
        print(f"  Top {n:2d} · Lauf {lb:2d}-1 · Tausch alle {ev} M. · Filter {'an ' if filt else 'aus'}  "
              f"Lernen {r['L'] * 100:6.1f} % (Rückg. {r['Ldd'] * 100:4.0f} %) | Prüfen {r['P'] * 100:6.1f} % (Rückg. {r['Pdd'] * 100:4.0f} %)", flush=True)
    df = pd.DataFrame(rows)
    ok = df[df["Ldd"] <= 1.5 * etf["L"][1]]
    best = ok.sort_values("L", ascending=False).iloc[0] if len(ok) else df.sort_values("L", ascending=False).iloc[0]
    print(f"\n  BESTE im Lernzeitraum: Top {best.n} · Lauf {best.lb}-1 · alle {best.ev} M. · Filter {'an' if best.filt else 'aus'}"
          f" → Prüfen {best.P * 100:.1f} % nach Steuer (ETF {etf['P'][0] * 100:.1f} %), Rückgang {best.Pdd * 100:.0f} %"
          f" → {'BESTÄTIGT' if best.P > etf['P'][0] else 'NICHT bestätigt'}")
    print(f"  Varianten über dem ETF: Lernen {int((df.L > etf['L'][0]).sum())}/36 · Prüfen {int((df.P > etf['P'][0]).sum())}/36")
    for col, nm in (("n", "Anzahl"), ("lb", "Lauf"), ("ev", "Tausch alle M."), ("filt", "Marktfilter")):
        g = df.groupby(col)[["L", "P", "Ldd", "Pdd"]].mean()
        print(f"  Ø nach {nm}: " + " · ".join(f"{i}: L {v.L * 100:.1f} % / P {v.P * 100:.1f} % (Rückg. {v.Pdd * 100:.0f} %)" for i, v in g.iterrows()))


if __name__ == "__main__":
    main(sys.argv[1])
