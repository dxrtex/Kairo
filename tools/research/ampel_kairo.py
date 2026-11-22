"""Marktampel × Kairo-Treffer (19.11.2026): Laufen Kairo-Trades je nach Ampelfarbe besser oder schlechter?

Kairo-Treffer der letzten ~10 Jahre (backend/bilanz.py, Kursverlauf je Treffer), Trades exakt nach der Kairo-Regel B60
(Kauf in der Konsolidierung, Stop Basis-Tief − 0,25 ATR, Ausstieg ab Tag 10 unter der EMA 20, spätestens Tag 60),
netto in R. Ampelfarbe = Stand am Handelstag VOR dem Kauf (kein Blick in die Zukunft).
Vergleich je Farbe und als Depot (3.000 €, 0,99 € je Order, 5 Plätze, 1 % Risiko) mit Filtern:
alle Trades · ohne Rot · ohne Rot/Orange · Rot/Orange mit halbem Risiko · nur Grün.
Ampel-Varianten: neue Marktampel (S&P/Nasdaq, schwächere), nur S&P 500, alte Tagesampel, nur Wochentrend, nur Tagesdruck.

    python tools/research/ampel_kairo.py bilanz_part_*.json   (bzw. Ordner)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend import marketlight as ML  # noqa: E402
from backend.capstudy import run  # noqa: E402
from backend.exitstudy10 import rows_for  # noqa: E402
from backend.volstudy import _hits  # noqa: E402

RULE = {"hold": 60, "ema_x": 20, "ema_from": 10}
NAMES = {3: "Grün", 2: "Gelb", 1: "Orange", 0: "Rot"}


def load():
    h = {}
    for t in ["^GSPC", "^NDX", "^VIX", "^VIX3M", "HYG", "IEF"]:
        d = yf.Ticker(t).history(period="max", interval="1d", auto_adjust=True)
        d.index = pd.to_datetime(d.index).tz_localize(None).normalize()
        h[t] = d[d.index >= "1995-01-01"][["Close", "Volume"]]
    return h


def levels(h):
    cr = ML.credit_ratio(h.get("HYG"), h.get("IEF"))
    out = {}

    def fin(t):
        R = ML.raw_levels(h[t], h["^VIX"], h.get("^VIX3M"), cr)
        day = ML.smooth(R["lv"], ML.P["up_n"])
        ws, _ = ML.week_levels(h[t], h["^VIX"])
        wk = ws.reindex(day.index, method="ffill").shift(1)
        return ML.combine(wk, day), wk, day

    a, aw, ad = fin("^GSPC")
    b, bw, bd = fin("^NDX")
    out["neu: schwächere S&P/Nasdaq"] = pd.concat([a, b], axis=1).dropna().min(axis=1)
    out["neu: nur S&P 500"] = a
    out["nur Wochentrend (S&P/Nasdaq)"] = pd.concat([aw, bw], axis=1).dropna().min(axis=1)
    out["nur Tagesdruck (S&P/Nasdaq)"] = pd.concat([ad, bd], axis=1).dropna().min(axis=1)
    c = h["^GSPC"]["Close"]
    e50, e200 = c.ewm(span=50, adjust=False).mean(), c.ewm(span=200, adjust=False).mean()
    v = h["^VIX"]["Close"].reindex(c.index).ffill()
    good, bad = (c > e50) & (v < 20), ((c < e50) & (c < e200)) | (v >= 28)
    out["alt: Tagesampel"] = pd.Series(np.where(good, 3, np.where(bad, 0, 2)), index=c.index, dtype=float)
    return out


def stat(rs):
    r = np.array([x for x in rs if x is not None])
    if not len(r):
        return "n=0"
    return f"n={len(r):5d}  Ø {r.mean():+.3f} R  Median {np.median(r):+.2f} R  Gewinner {(r > 0).mean() * 100:4.1f} %  Summe {r.sum():+7.1f} R"


def main():
    args = sys.argv[1:] or ["."]
    hits = []
    for a in args:
        p = Path(a)
        if p.is_dir():
            hits += _hits(str(p))
        else:
            hits += _hits(str(p.parent)) if p.name.startswith("bilanz_part_") else []
    seen, hh = set(), []
    for e in hits:
        if (e["t"], e["d"]) not in seen:
            seen.add((e["t"], e["d"]))
            hh.append(e)
    print(f"Kairo-Treffer: {len(hh)}  ({min(e['d'] for e in hh)} – {max(e['d'] for e in hh)})", flush=True)
    rows = []
    for e in hh:
        for x in rows_for([e], RULE):
            x["t"] = e["t"]
            rows.append(x)
    print(f"Trades nach Kairo-Regel B60: {len(rows)}", flush=True)
    h = load()
    LV = levels(h)
    us = {e["t"] for e in hh if "." not in e["t"]}
    for name, lv in LV.items():
        lv = lv.dropna()
        print(f"\n===== {name} =====")
        for x in rows:
            d = pd.Timestamp(x["d"]) - pd.Timedelta(days=1)
            i = lv.index.searchsorted(d, side="right") - 1
            x["lv"] = int(lv.iloc[i]) if i >= 0 else None
        for per, sel in (("alle Jahre", lambda x: True), ("bis 2023", lambda x: x["sd"] < "2024-01-01"), ("ab 2024", lambda x: x["sd"] >= "2024-01-01")):
            print(f"  -- {per}")
            for k in (3, 2, 1, 0):
                print(f"    {NAMES[k]:6s} {stat([x['r1'] for x in rows if x['lv'] == k and sel(x)])}")
        print("  -- nur US-Aktien")
        for k in (3, 2, 1, 0):
            print(f"    {NAMES[k]:6s} {stat([x['r1'] for x in rows if x['lv'] == k and x.get('t', '') in us])}")
        base = [x for x in rows if x["lv"] is not None]
        fl = {"alle Trades": base,
              "ohne Rot": [x for x in base if x["lv"] >= 1],
              "ohne Rot/Orange": [x for x in base if x["lv"] >= 2],
              "nur Grün": [x for x in base if x["lv"] == 3],
              "Rot/Orange halbes Risiko": [{**x, "rk": 0.005} if x["lv"] <= 1 else x for x in base],
              "Rot halbes Risiko": [{**x, "rk": 0.005} if x["lv"] == 0 else x for x in base]}
        for fn, rr in fl.items():
            if len(rr) < 20:
                print(f"    Depot {fn:26s} zu wenige Trades")
                continue
            dep = run(rr, 3000, 0.99, 5)
            print(f"    Depot {fn:26s} CAGR {dep['cagr']}  MaxDD {dep['mdd']}  Trades/Jahr {dep['trades_pa']}  Ende {dep['ende']}", flush=True)


if __name__ == "__main__":
    main()
