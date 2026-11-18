"""Backtest Marktampel (19.11.2026): Wie gut trennt jede Ampel-Variante gute von schlechten Phasen für Swing-Trades?

Je Stufe: Anteil der Tage, Rendite des Index in den nächsten 20 / 60 Handelstagen (Mittel, Anteil positiv),
größter Rückgang in den nächsten 20 Tagen, Wechsel pro Jahr. Dazu „nur investiert bei Grün/Gelb“ gegen Kaufen und Halten.
Varianten: alte Tagesampel (S&P > EMA 50 und VIX < 20), Wochen-Phase (18.11.), neues Modell mit verschiedenen Parametern.

    python tools/research/ampel_study.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend import marketlight as ML  # noqa: E402
from backend.marketphase import market_phase  # noqa: E402

TK = ["^GSPC", "^NDX", "^VIX", "^VIX3M", "HYG", "IEF", "URTH", "^GDAXI", "QQQ", "SPY"]


def load():
    h = {}
    for t in TK:
        d = yf.Ticker(t).history(period="max", interval="1d", auto_adjust=True)
        if d is None or d.empty:
            print("leer", t)
            continue
        d.index = pd.to_datetime(d.index).tz_localize(None).normalize()
        h[t] = d[d.index >= "1988-01-01"][["Close", "Volume"]]
        print(t, h[t].index[0].date(), h[t].index[-1].date(), len(h[t]))
    return h


def fwd(c: pd.Series, n: int):
    return c.shift(-n) / c - 1


def fmdd(c: pd.Series, n: int = 20):
    a = c.to_numpy()
    out = np.full(len(a), np.nan)
    for i in range(len(a) - n):
        w = a[i + 1: i + n + 1]
        out[i] = w.min() / a[i] - 1
    return pd.Series(out, index=c.index)


def evaluate(name, lv: pd.Series, c: pd.Series, start="1993-01-01"):
    lv = lv[lv.index >= start].dropna()
    c = c.reindex(lv.index)
    f20, f60, md = fwd(c, 20), fwd(c, 60), fmdd(c, 20)
    rows = []
    for k in sorted(lv.unique(), reverse=True):
        m = lv == k
        rows.append(f"  {int(k)}: Tage {m.mean() * 100:5.1f} %  20T {f20[m].mean() * 100:+5.2f} % ({(f20[m] > 0).mean() * 100:3.0f} % pos)  "
                    f"60T {f60[m].mean() * 100:+5.2f} % ({(f60[m] > 0).mean() * 100:3.0f} % pos)  maxRück20 {md[m].mean() * 100:5.2f} %  "
                    f"schlimmste 5 % {md[m].quantile(.05) * 100:6.1f} %")
    flips = (lv != lv.shift()).sum() / (len(lv) / 252)
    r = c.pct_change().shift(-1)
    res = []
    for thr in (3, 2):
        inv = (lv >= thr).astype(float)
        eq = (1 + r * inv).fillna(0).cumprod() if False else (1 + (r * inv).fillna(0)).cumprod()
        yrs = len(eq) / 252
        cagr = eq.iloc[-1] ** (1 / yrs) - 1
        mdd = (eq / eq.cummax() - 1).min()
        ex = (r * inv).dropna()
        sh = ex.mean() / ex.std() * np.sqrt(252) if ex.std() > 0 else 0
        res.append(f"≥{thr}: CAGR {cagr * 100:5.1f} %  MaxDD {mdd * 100:6.1f} %  Sharpe {sh:4.2f}  investiert {inv.mean() * 100:3.0f} %")
    bh = (1 + r.fillna(0)).cumprod()
    bhs = f"Kaufen+Halten: CAGR {(bh.iloc[-1] ** (252 / len(bh)) - 1) * 100:5.1f} %  MaxDD {(bh / bh.cummax() - 1).min() * 100:6.1f} %  Sharpe {r.mean() / r.std() * np.sqrt(252):4.2f}"
    print(f"\n== {name} ==  Wechsel/Jahr {flips:4.1f}")
    print("\n".join(rows))
    print("  " + " | ".join(res) + " | " + bhs)
    return {"name": name, "flips": flips}


def old_regime(h, t="^GSPC"):
    c = h[t]["Close"]
    e50 = c.ewm(span=50, adjust=False).mean()
    e200 = c.ewm(span=200, adjust=False).mean()
    v = h["^VIX"]["Close"].reindex(c.index).ffill()
    good = (c > e50) & (v < 20)
    bad = ((c < e50) & (c < e200)) | (v >= 28)
    return pd.Series(np.where(good, 3, np.where(bad, 0, 2)), index=c.index, dtype=float)


def weekly_phase(h, t="^GSPC", cn=2):
    out = {}
    c = h[t]
    m = {"bull": 3, "neutral": 2, "corr": 1, "bear": 0}
    p = market_phase(c, h["^VIX"] if t in ("^GSPC", "^NDX") else None, keep=100000, confirm_n=cn)
    if not p:
        return None
    s = pd.Series({pd.Timestamp(d): m[k] for d, k in p["hist"]}).sort_index()
    return s.reindex(c.index, method="ffill").shift(1)          # Wochenschluss gilt ab der Folgewoche


def main():
    h = load()
    cr = ML.credit_ratio(h.get("HYG"), h.get("IEF"))
    for t in ("^GSPC", "^NDX"):
        c = h[t]["Close"]
        print(f"\n\n######## {t} ########")
        evaluate("alt: Tagesampel EMA50 + VIX<20", old_regime(h, "^GSPC") if t == "^GSPC" else old_regime(h, "^GSPC").reindex(c.index).ffill(), c)
        wp = weekly_phase(h, t)
        if wp is not None:
            evaluate("Wochen-Phase 18.11.", wp, c)
            w1 = weekly_phase(h, t, 1)
            evaluate("Wochen-Phase ohne Bestätigung", w1, c)
            R = ML.raw_levels(h[t], h["^VIX"], h.get("^VIX3M"), cr)
            for nm, dl in [("Tag roh", R["lv"]), ("Tag geglättet 5", ML.smooth(R["lv"], 5))]:
                for wn, ww in [("W2", wp), ("W1", w1)]:
                    j = pd.concat([ww, dl], axis=1).dropna()
                    a_, d_ = j.iloc[:, 0], j.iloc[:, 1]
                    c1 = a_.where(a_ < 3, np.where(d_ >= 3, 3, 2))
                    evaluate(f"Kombi {wn} + {nm}: Grün nur ohne Tagesdruck", pd.Series(c1, index=j.index), c)
                    c2 = pd.Series(np.where(a_ < 3, a_, np.where(d_ >= 3, 3, np.where(d_ == 2, 2, 1))), index=j.index)
                    evaluate(f"Kombi {wn} + {nm}: Tageskorrektur → Orange", c2, c)
        for name, p in [("neu Standard", {})]:
            us = True
            R = ML.raw_levels(h[t], h["^VIX"] if us else None, h.get("^VIX3M") if us else None, cr if us else None, p)
            lv = ML.smooth(R["lv"], {**ML.P, **p}["up_n"])
            evaluate(name, lv, c)
    # Gesamtampel = schwächere von S&P 500 und Nasdaq 100, gemessen an beiden Indizes
    def fin(t):
        day = ML.smooth(ML.raw_levels(h[t], h["^VIX"], h.get("^VIX3M"), cr)["lv"], ML.P["up_n"])
        ws, _ = ML.week_levels(h[t], h["^VIX"])
        return ML.combine(ws.reindex(day.index, method="ffill").shift(1), day)   # ohne Vorgriff: Wochenschluss gilt ab Folgetag
    a, b = fin("^GSPC"), fin("^NDX")
    evaluate("FINAL S&P 500", a, h["^GSPC"]["Close"])
    evaluate("FINAL Nasdaq 100", b, h["^NDX"]["Close"])
    j = pd.concat([a, b], axis=1).dropna().min(axis=1)
    print("\n\n######## Gesamtampel (min S&P/Nasdaq) ########")
    evaluate("Gesamt → S&P 500", j, h["^GSPC"]["Close"])
    evaluate("Gesamt → Nasdaq 100", j, h["^NDX"]["Close"])
    print("\n\n######## Heute ########")
    lt = ML.market_lights(h)
    for k, x in (lt or {}).items():
        print(k, x["label"], "seit", x["since"], f"({x['days']} T)", "roh", x["raw"], "|", "; ".join(("✓ " if ok else "✗ ") + s for ok, s in x["why"]))
    for t in ("^GSPC", "^NDX"):
        R = ML.raw_levels(h[t], h["^VIX"], h.get("^VIX3M"), cr)
        lv = ML.smooth(R["lv"], ML.P["up_n"])
        print(t, "letzte 30 Tage:", "".join(str(int(x)) for x in lv.iloc[-30:]))
        for d in ("2018-10-10", "2018-12-24", "2020-02-24", "2020-03-23", "2020-06-08", "2021-11-22", "2022-01-05", "2022-06-16", "2022-10-13", "2023-01-20",
                  "2023-10-27", "2024-04-19", "2024-08-05", "2025-02-21", "2025-04-08", "2025-05-15"):
            ts = pd.Timestamp(d)
            if ts in lv.index:
                print("  ", d, int(lv.loc[ts]), "raw", int(R["lv"].loc[ts]))


if __name__ == "__main__":
    main()
