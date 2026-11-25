"""Marktampel v2 (25.11.2026): Bringen Marktbreite oder eine Richtungsanzeige echten Mehrwert?

Basis = heutige Gesamtampel (backend/marketlight.py, schwächere von S&P 500 / Nasdaq 100), ohne Vorgriff.
A) Marktbreite – zwei frei verfügbare Messungen (yfinance):
   · Sektorbreite: Anteil der 9 klassischen US-Sektor-ETFs (XLB XLE XLF XLI XLK XLP XLU XLV XLY, ab Dez. 1998) über der 200-Tage-Linie
   · Gleich- gegen kapitalgewichtet: RSP/SPY (ab 2003) unter der 50-Tage-Linie und diese fällt = Rally wird schmaler
   Varianten: Grün → Gelb bei schwacher Breite; Gelb → Orange bei sehr schwacher Breite.
B) Richtung: Tagesmodell roh (ungeglättet) über / unter der angezeigten Stufe = „erholt sich“ / „verschlechtert sich“.

Gemessen am S&P 500 ab 1999: Rendite und Rückschlag der nächsten 20/60 Tage je Stufe, „investiert ab Gelb/Grün“
(CAGR, MaxDD, Sharpe), Wechsel pro Jahr – getrennt für 1999–2012 und 2013–2026 (beide Hälften müssen bestätigen).

    python tools/research/ampel_v2.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend import marketlight as ML  # noqa: E402
from tools.research import ampel_study as AS  # noqa: E402

SECT = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]


def load():
    import yfinance as yf
    AS.TK = AS.TK + SECT + ["RSP"]
    return AS.load()


def final_light(h, cr):
    def fin(t):
        R = ML.raw_levels(h[t], h["^VIX"], h.get("^VIX3M"), cr)
        day = ML.smooth(R["lv"], ML.P["up_n"])
        ws, _ = ML.week_levels(h[t], h["^VIX"])
        return ML.combine(ws.reindex(day.index, method="ffill").shift(1), day), R["lv"]
    (a, ra), (b, rb) = fin("^GSPC"), fin("^NDX")
    lv = pd.concat([a, b], axis=1).dropna().min(axis=1)
    raw = pd.concat([ra, rb], axis=1).dropna().min(axis=1).reindex(lv.index)
    return lv, raw


def stats(lv: pd.Series, c: pd.Series, a: str, b: str) -> dict:
    lv = lv[(lv.index >= a) & (lv.index <= b)].dropna()
    c = c.reindex(lv.index)
    f20, md = AS.fwd(c, 20), AS.fmdd(c, 20)
    r = c.pct_change().shift(-1)
    out = {"flips": (lv != lv.shift()).sum() / (len(lv) / 252)}
    for thr in (3, 2):
        inv = (lv >= thr).astype(float)
        eq = (1 + (r * inv).fillna(0)).cumprod()
        ex = (r * inv).dropna()
        out[f"cagr{thr}"] = eq.iloc[-1] ** (252 / len(eq)) - 1
        out[f"mdd{thr}"] = (eq / eq.cummax() - 1).min()
        out[f"sh{thr}"] = ex.mean() / ex.std() * np.sqrt(252) if ex.std() > 0 else 0
    g = lv == 3
    out["green_w5"] = md[g].quantile(.05) if g.any() else np.nan
    out["green_f20"] = f20[g].mean() if g.any() else np.nan
    out["green_days"] = g.mean()
    return out


def line(name, s):
    return (f"  {name:<44} Wechsel/J {s['flips']:4.1f} | ≥Grün CAGR {s['cagr3'] * 100:5.1f} % DD {s['mdd3'] * 100:6.1f} % Sh {s['sh3']:4.2f}"
            f" | ≥Gelb CAGR {s['cagr2'] * 100:5.1f} % DD {s['mdd2'] * 100:6.1f} % Sh {s['sh2']:4.2f}"
            f" | Grün: {s['green_days'] * 100:3.0f} % der Tage, 20T {s['green_f20'] * 100:+.2f} %, schlimmste 5 % {s['green_w5'] * 100:5.1f} %")


def main():
    h = load()
    cr = ML.credit_ratio(h.get("HYG"), h.get("IEF"))
    base, raw = final_light(h, cr)
    c = h["^GSPC"]["Close"]
    # Sektorbreite (Stand gestern → kein Vorgriff)
    above = pd.concat([(h[t]["Close"] > h[t]["Close"].rolling(200).mean()).astype(float).where(h[t]["Close"].rolling(200).mean().notna())
                       for t in SECT if t in h], axis=1)
    br = above.mean(axis=1, skipna=False).shift(1).reindex(base.index)
    ratio = (h["RSP"]["Close"] / h["SPY"]["Close"].reindex(h["RSP"].index)).dropna() if "RSP" in h else None
    narrow = ((ratio < ratio.rolling(50).mean()) & (ratio.rolling(50).mean() < ratio.rolling(50).mean().shift(10))).shift(1).reindex(base.index).fillna(False) if ratio is not None else None

    def var(weak_g=None, weak_y=None, nar=False):
        lv = base.copy()
        if weak_g is not None:
            lv[(lv == 3) & (br < weak_g)] = 2
        if weak_y is not None:
            lv[(lv == 2) & (br < weak_y)] = 1
        if nar and narrow is not None:
            lv[(lv == 3) & narrow] = 2
        return lv

    V = [("Basis (heutige Ampel)", base),
         ("Breite: Grün→Gelb unter 50 %", var(0.5)),
         ("Breite: Grün→Gelb unter 60 %", var(0.6)),
         ("Breite: Gelb→Orange unter 30 %", var(None, 0.3)),
         ("Breite: beides (50 % / 30 %)", var(0.5, 0.3)),
         ("Schmale Rally (RSP/SPY): Grün→Gelb", var(nar=True)),
         ("Breite 50 % + schmale Rally", var(0.5, None, True))]
    for a, b in (("1999-01-01", "2012-12-31"), ("2013-01-01", "2026-12-31"), ("1999-01-01", "2026-12-31")):
        print(f"\n######## {a[:4]}–{b[:4]} (S&P 500) ########")
        for nm, lv in V:
            print(line(nm, stats(lv, c, a, b)))

    # B) Richtung: roh über/unter angezeigter Stufe
    print("\n######## Richtung: Rendite der nächsten 20 / 60 Tage je Stufe ########")
    d = np.sign(raw - base)
    f20, f60 = AS.fwd(c, 20).reindex(base.index), AS.fwd(c, 60).reindex(base.index)
    for a, b in (("1993-01-01", "2009-12-31"), ("2010-01-01", "2026-12-31")):
        print(f"  {a[:4]}–{b[:4]}")
        m0 = (base.index >= a) & (base.index <= b)
        for k in (3, 2, 1, 0):
            parts = []
            for dv, nm in ((1, "erholt sich"), (0, "stabil"), (-1, "verschlechtert sich")):
                m = m0 & (base == k) & (d == dv)
                if m.sum() >= 40:
                    parts.append(f"{nm}: {m.sum():4d} T, 20T {f20[m].mean() * 100:+5.2f} %, 60T {f60[m].mean() * 100:+5.2f} %")
            print(f"    Stufe {k}: " + " | ".join(parts))
    print("\nHeute: Stufe", int(base.iloc[-1]), "roh", int(raw.iloc[-1]), "Sektorbreite", f"{br.iloc[-1] * 100:.0f} %" if br.notna().iloc[-1] else "–",
          "schmale Rally", bool(narrow.iloc[-1]) if narrow is not None else "–")


if __name__ == "__main__":
    main()
