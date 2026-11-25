"""Kairo-Strategie unter Realbedingungen bei Scalable Capital PRIME+ (Wunsch 25.11.2026).

Regel unverändert (backend/langfrist.py): am ersten Handelstag im Jan/Apr/Jul/Okt die Top 10 nach 12-1-Momentum
(US-Aktien, Ø Umsatz 63 T. ≥ 5 Mio. $, Kurs ≥ 5 $), behalten solange in den Top 20, gleich gewichtet, Rangliste mit Kursen
bis zum Vortag, Ausführung zur Eröffnung des Tauschtags.

Realbedingungen eines deutschen Privatanlegers:
- alles in EURO: Kauf/Verkauf in € (gettex), Depotwert in €, Steuer auf €-Gewinne (Währungsgewinne/-verluste zählen mit)
- Spread gettex je nach Liquidität (halber Spread je Seite, inkl. Währungsaufschlag des Market Makers):
  Ø Umsatz ≥ 200 Mio. $ 0,05 % · ≥ 50 Mio. 0,10 % · ≥ 20 Mio. 0,20 % · darunter 0,40 %  (Szenarien ×0,5 / ×1 / ×2)
- PRIME+: 0 € Ordergebühr ab 250 € Orderwert, sonst 0,99 €; Abo 4,99 € / Monat (wahlweise mitgerechnet)
- Abgeltungsteuer 26,375 % (ohne Kirchensteuer) beim Verkauf, Aktien-Verlusttopf, Sparerpauschbetrag 1.000 € je Kalenderjahr
- am Ende: alles verkaufen und versteuern (vergleichbar mit dem ETF, der ebenfalls am Ende versteuert wird)
Vergleich: Welt-ETF (ACWI in €, Sparplan-Kauf ohne Gebühr, 0,1 % Spread), am Ende verkauft, Teilfreistellung 30 %.

    python -m backend.position.real PXDIR
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from . import engine
from .backtest import _yf, load_market, metrics
from .config import CFG, Config

TAX = 0.26375
TIERS = ((200e6, 0.0005), (50e6, 0.0010), (20e6, 0.0020), (0, 0.0040))


def half_spread(adv_usd: float, mult: float) -> float:
    for lim, s in TIERS:
        if adv_usd >= lim:
            return s * mult
    return TIERS[-1][1] * mult


def run_real(m: engine.Market, eurusd: pd.Series, start: str, cap: float, mult: float = 1.0, sub: float = 0.0,
             allow: float = 1000.0, fee_fix: float = 0.99, fee_free: float = 250.0, n: int = 10, hold: int = 20,
             end: str | None = None) -> dict:
    Cf = m.C.ffill(limit=engine.FILL_DAYS)
    mom = Cf.shift(21) / Cf.shift(12 * 21) - 1
    adv = (m.C * m.V.fillna(0)).rolling(63, min_periods=40).mean()
    last_valid = m.C.apply(lambda s: s.last_valid_index())
    idx = m.C.index
    fx = eurusd.reindex(idx).ffill().bfill()                     # USD je EUR
    dates = idx[(idx >= pd.Timestamp(start)) & (idx <= pd.Timestamp(end or idx[-1]))]
    first = pd.Series(idx, index=idx).groupby([idx.year, idx.month]).transform("first")
    reb = {d for d in dates if first[d] == d and d.month in (1, 4, 7, 10)} | {dates[0]}
    cash, pos, pot = float(cap), {}, 0.0
    used = {}                                                     # genutzter Sparerpauschbetrag je Jahr
    st = {"tax": 0.0, "fee": 0.0, "spread": 0.0, "sub": 0.0, "sells": 0, "buys": 0, "small": 0}
    eq, last = [], {}
    fee = lambda v: fee_fix if v < fee_free else 0.0

    def tax_on(gain: float, year: int) -> float:
        nonlocal pot
        if gain < 0:
            pot += -gain
            return 0.0
        use = min(pot, gain)
        pot -= use
        g = gain - use
        a = min(max(0.0, allow - used.get(year, 0.0)), g)
        used[year] = used.get(year, 0.0) + a
        return (g - a) * TAX

    def sell(tk, px_usd, t):
        nonlocal cash
        p = pos.pop(tk)
        hs = half_spread(float(adv.at[t, tk]) if tk in adv.columns and adv.at[t, tk] == adv.at[t, tk] else 0.0, mult)
        gross = p["n"] * px_usd / fx[t]
        f0 = fee(gross)
        proceeds = gross * (1 - hs) - f0
        tx = tax_on(proceeds - p["basis"], t.year)
        cash += proceeds - tx
        st["tax"] += tx; st["fee"] += f0; st["spread"] += gross * hs; st["sells"] += 1

    month = None
    for t in dates:
        k = idx.get_loc(t)
        if sub and (t.year, t.month) != month:
            month = (t.year, t.month)
            cash -= sub; st["sub"] += sub
        if t in reb and k > 0:
            y = idx[k - 1]
            ok = (mom.loc[y] > -1) & (adv.loc[y] >= 5e6) & (Cf.loc[y] >= 5.0) & m.O.loc[t].notna()
            ranked = list(mom.loc[y][ok].sort_values(ascending=False).index)
            keep = set(ranked[:hold])
            for tk in [x for x in pos if x not in keep]:
                px = engine._px(m.O, t, tk)
                sell(tk, px if px == px else last.get(tk, pos[tk]["px"]), t)
            val = cash + sum(p["n"] * (engine._px(m.O, t, tk) if engine._px(m.O, t, tk) == engine._px(m.O, t, tk) else last.get(tk, p["px"])) / fx[t]
                             for tk, p in pos.items())
            for tk in ranked:
                if len(pos) >= n:
                    break
                if tk in pos:
                    continue
                px = engine._px(m.O, t, tk)
                if not (px == px and px > 0):
                    continue
                hs = half_spread(float(adv.at[y, tk]), mult)
                pe = px / fx[t] * (1 + hs)                          # Kaufkurs in € inkl. halbem Spread
                budget = min(val / n, cash)
                q = int(budget // pe)
                if q > 0 and q * pe + fee(q * pe) > cash:
                    q = int((cash - fee_fix) // pe)
                if q <= 0:
                    continue
                f0 = fee(q * pe)
                cash -= q * pe + f0
                st["fee"] += f0; st["spread"] += q * px / fx[t] * hs; st["buys"] += 1; st["small"] += f0 > 0
                pos[tk] = {"n": q, "px": px, "basis": q * pe + f0, "in": t}
        for tk in list(pos):
            c = engine._px(m.C, t, tk)
            if c == c:
                last[tk] = c
            lv = last_valid.get(tk)
            if lv is not None and pd.notna(lv) and (pd.Timestamp(lv) < t or (pd.Timestamp(lv) == t and t < idx[-1])):
                sell(tk, last.get(tk, pos[tk]["px"]), pd.Timestamp(lv) if pd.Timestamp(lv) in fx.index else t)
        eq.append((t, cash + sum(p["n"] * last.get(tk, p["px"]) / fx[t] for tk, p in pos.items())))
    E = pd.Series(dict(eq))
    # Ende: alles verkaufen und versteuern
    t = dates[-1]
    liq = cash
    for tk, p in pos.items():
        hs = half_spread(float(adv.at[t, tk]) if adv.at[t, tk] == adv.at[t, tk] else 0.0, mult)
        gross = p["n"] * last.get(tk, p["px"]) / fx[t]
        pr = gross * (1 - hs) - fee(gross)
        liq += pr - tax_on(pr - p["basis"], t.year + 1)
    yrs = (dates[-1] - dates[0]).days / 365.25
    return {"eq": E, "end": float(E.iloc[-1]), "liq": liq, "cagr_net": (liq / cap) ** (1 / yrs) - 1, "m": metrics(E), "st": st, "yrs": yrs}


def etf_real(eurusd: pd.Series, start: str, cap: float, end: str | None = None) -> dict:
    a = _yf("ACWI")["Close"]
    a = a[(a.index >= start) & (a.index <= pd.Timestamp(end or a.index[-1]))]
    e = (a / eurusd.reindex(a.index).ffill().bfill()).dropna()
    units = cap * (1 - 0.001) / e.iloc[0]
    E = units * e
    gain = E.iloc[-1] * (1 - 0.001) - cap
    tax = max(0.0, gain * 0.7 - 1000.0) * TAX                        # Teilfreistellung 30 %, einmal Pauschbetrag
    liq = E.iloc[-1] * (1 - 0.001) - tax
    yrs = (e.index[-1] - e.index[0]).days / 365.25
    return {"eq": E, "liq": liq, "cagr_net": (liq / cap) ** (1 / yrs) - 1, "m": metrics(E), "yrs": yrs}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("pxdir")
    ap.add_argument("--start", default="2016-01-04")
    ap.add_argument("--out", default="")
    x = ap.parse_args(argv)
    m, meta = load_market(x.pxdir, "us", Config())
    eurusd = _yf("EURUSD=X", "2009-01-01")["Close"]
    p = lambda v: f"{v * 100:6.1f} %"
    rows = []

    def line(label, r, cap):
        s = r["st"]
        print(f"  {label:<46} Ende brutto {r['end']:>10,.0f} €  nach Verkauf+Steuer {r['liq']:>10,.0f} €  → {p(r['cagr_net'])} p. a.  "
              f"(vor Steuer {p(r['m']['cagr'])}) · MaxDD {p(-r['m']['mdd'])} · Steuer {s['tax']:>8,.0f} € · Spread {s['spread']:>7,.0f} € · "
              f"Gebühren {s['fee']:>5,.0f} € ({s['small']} Orders < 250 €) · Abo {s['sub']:>4,.0f} € · Orders {s['buys'] + s['sells']}")
        rows.append({"label": label, "cap": cap, "liq": r["liq"], "cagr_net": r["cagr_net"], "cagr_gross": r["m"]["cagr"], "mdd": r["m"]["mdd"],
                     **{k: v for k, v in s.items()}})

    print(f"\n######## Kairo Top 10 / Puffer 20 · Scalable PRIME+ · {x.start} bis heute · alles in € ########")
    print("  Referenz alter Backtest (100.000 $, 0,1 % Kosten pauschal, in $, ohne Pauschbetrag): siehe BACKTEST in backend/langfrist.py (32,4 %)")
    for cap in (3000, 5000, 10000, 30000):
        for mult, nm in ((0.5, "Spread günstig"), (1.0, "Spread realistisch"), (2.0, "Spread ungünstig")):
            line(f"{cap:>6,} € · {nm}", run_real(m, eurusd, x.start, cap, mult), cap)
        line(f"{cap:>6,} € · realistisch + Abo 4,99 €/Monat", run_real(m, eurusd, x.start, cap, 1.0, sub=4.99), cap)
    print("\n  Welt-ETF (ACWI in €, kaufen & halten, am Ende versteuert):")
    for cap in (3000, 10000):
        r = etf_real(eurusd, x.start, cap)
        print(f"  {cap:>6,} € → {r['liq']:>10,.0f} € nach Steuer · {p(r['cagr_net'])} p. a. · MaxDD {p(-r['m']['mdd'])}")
        rows.append({"label": f"ETF {cap}", "cap": cap, "liq": r["liq"], "cagr_net": r["cagr_net"], "mdd": r["m"]["mdd"]})
    print("\n  Zeiträume einzeln (10.000 €, realistisch):")
    for a, b in (("2016-01-04", "2020-12-31"), ("2021-01-04", "2026-12-31")):
        r = run_real(m, eurusd, a, 10000, 1.0, end=b)
        e = etf_real(eurusd, a, 10000, end=b)
        print(f"  {a[:4]}–{b[:4]}: Strategie {p(r['cagr_net'])} p. a. nach Steuer (MaxDD {p(-r['m']['mdd'])}) · Welt-ETF {p(e['cagr_net'])} (MaxDD {p(-e['m']['mdd'])})")
    print("\n  Nicht enthalten: Kirchensteuer, Quellensteuer auf Dividenden (Kurse sind dividendenbereinigt, Momentum-Aktien zahlen wenig),"
          " Überlebens-Verzerrung (nur heute gelistete Aktien – Pleiten fehlen, echte Renditen liegen darunter).")
    if x.out:
        Path(x.out).write_text(json.dumps(rows, ensure_ascii=False, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())
