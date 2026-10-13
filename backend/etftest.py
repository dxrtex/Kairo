"""ETF-Ampel und Trading-Bereich: Was bringt wirklich etwas?

1) Sparplan-Regeln für einen Welt-ETF (gleicher Geldeinsatz je Monat, nur der Zeitpunkt unterscheidet sich):
   S0 jeden Monat gleich viel · S1 Reserve am Hoch, Nachkauf bei −10/−20 % · S2 Nachkauf nahe/unter der 200-Tage-Linie ·
   S3 Trendfilter (über der 200-Tage-Linie investiert, sonst Geldmarkt) · S4 nur unter der 200-Tage-Linie kaufen.
2) Statistik: Was passierte in den 12 Monaten nach einem Allzeithoch bzw. nach Rücksetzern?
3) Trading-Bereich: Kairo-Swing allein gegen Mischungen mit 2× Welt/S&P 500 mit Trendfilter.

Welt-Proxy ab 2003: 55 % S&P 500 + 35 % EFA (Industrieländer ohne USA) + 10 % EEM (Schwellenländer), täglich gemischt;
Kontrolle mit dem echten ACWI (ab 2008) und dem SPDR ACWI IMI an der Xetra (SPYI.DE, Euro).

    python -m backend.etftest [--kairo Ordner1 Ordner2]
"""

from __future__ import annotations

import argparse
import json
import time

import numpy as np
import pandas as pd

from .config import ROOT
from .grandtest import _closes, load_kairo, stats

TICK = ["SPY", "EFA", "EEM", "ACWI", "SPYI.DE", "^IRX"]


def savings(px: pd.Series, cash: pd.Series, rule: str, budget: float = 100.0) -> dict:
    """Monatlicher Sparplan nach Regel; Reserve verzinst mit Geldmarkt. Ergebnis: Endwert, Einzahlungen, Rückgang."""
    px = px.dropna()
    sma = px.rolling(200).mean()
    hi = px.cummax()
    idx = px.index
    me = pd.DatetimeIndex(pd.Series(idx, index=idx).groupby([idx.year, idx.month]).last().values)
    me = me[me >= idx[200]]
    units, reserve, paid, vals, cashpos = 0.0, 0.0, 0.0, {}, 0.0
    c = cash.reindex(idx).fillna(0)
    invested_flag = True
    me_set = set(me)
    for i, t in enumerate(idx):
        reserve *= 1 + c.iloc[i]
        cashpos *= 1 + c.iloc[i]
        if t in me_set:
            p, s, dd = px.iloc[i], sma.iloc[i], 1 - px.iloc[i] / hi.iloc[i]
            paid += budget
            buy, keep = budget, 0.0
            if rule == "S1":
                if dd < 0.05:
                    buy, keep = 0.75 * budget, 0.25 * budget
                elif dd >= 0.2:
                    buy += reserve; reserve = 0.0
                elif dd >= 0.1:
                    buy += reserve / 2; reserve /= 2
            elif rule == "S2":
                if p <= s * 1.02:
                    buy += reserve; reserve = 0.0
                else:
                    buy, keep = 0.75 * budget, 0.25 * budget
            elif rule == "S4":
                if p < s:
                    buy += reserve; reserve = 0.0
                else:
                    buy, keep = 0.0, budget
            reserve += keep
            if rule == "S3":
                tot_cash = cashpos + buy
                if p > s:
                    units += tot_cash / p; cashpos = 0.0
                else:
                    cashpos = tot_cash + units * p; units = 0.0
            else:
                units += buy / p
        vals[t] = units * px.iloc[i] + reserve + cashpos
    v = pd.Series(vals)
    v = v[v.index >= me[0]]
    contrib = len(me) * budget
    dd = 1 - v / v.cummax()
    return {"endwert": round(float(v.iloc[-1])), "eingezahlt": round(contrib), "vielfaches": round(float(v.iloc[-1] / contrib), 3),
            "mdd": round(float(dd.max()), 3), "reserve_end": round(reserve)}


def forward_stats(px: pd.Series) -> dict:
    px = px.dropna()
    hi = px.cummax()
    dd = 1 - px / hi
    sma = px.rolling(200).mean()
    f12 = px.shift(-252) / px - 1
    fmin = px[::-1].rolling(252, min_periods=200).min()[::-1].shift(-1) / px - 1
    df = pd.DataFrame({"dd": dd, "up": px > sma, "f12": f12, "fmin": fmin}).dropna()
    df = df[df.index >= df.index[0] + pd.Timedelta(days=300)]
    buckets = [("am Allzeithoch (< 2 % darunter)", 0, 0.02), ("2–5 % unter Hoch", 0.02, 0.05), ("5–10 % unter Hoch", 0.05, 0.10),
               ("10–20 % unter Hoch", 0.10, 0.20), ("mehr als 20 % unter Hoch", 0.20, 1.0)]
    out = {}
    for name, a, b in buckets:
        x = df[(df.dd >= a) & (df.dd < b)]
        if len(x) > 50:
            out[name] = {"tage": int(len(x)), "f12_mittel": round(float(x.f12.mean()), 4), "f12_median": round(float(x.f12.median()), 4),
                         "p_minus12m": round(float((x.f12 < 0).mean()), 3), "p_10pct_rueckgang": round(float((x.fmin <= -0.10).mean()), 3)}
    for name, flag in (("über der 200-Tage-Linie", True), ("unter der 200-Tage-Linie", False)):
        x = df[df.up == flag]
        out[name] = {"tage": int(len(x)), "f12_mittel": round(float(x.f12.mean()), 4), "f12_median": round(float(x.f12.median()), 4),
                     "p_minus12m": round(float((x.f12 < 0).mean()), 3), "p_10pct_rueckgang": round(float((x.fmin <= -0.10).mean()), 3)}
    return out


def trend_series(r: pd.Series, px: pd.Series, cash: pd.Series, lev: float) -> pd.Series:
    """Täglicher Wert: lev× Index über der 200-Tage-Linie (Monatsende-Entscheidung), sonst Geldmarkt; mit Kosten."""
    sma = px.rolling(200).mean()
    idx = px.index
    me = pd.Series(idx, index=idx).groupby([idx.year, idx.month]).last()
    sig = pd.Series(np.nan, index=idx)
    for t in me.values:
        t = pd.Timestamp(t)
        sig.loc[t] = float(px.loc[t] > sma.loc[t]) if np.isfinite(sma.loc[t]) else 1.0
    sig = sig.ffill().shift(1).fillna(1.0)
    c = cash.reindex(idx).fillna(0)
    lr = lev * r - (lev - 1) * (c + 0.005 / 252) - (0.009 / 252 if lev > 1 else 0.0)
    daily = sig * lr + (1 - sig) * c
    sw = sig.diff().abs().fillna(0) * 0.002                     # Spread + Gebühren je Wechsel (grob)
    return (1 + daily - sw).cumprod() * 3000


def mix(series: dict, weights: dict) -> pd.Series:
    rr = pd.concat({k: s.pct_change() for k, s in series.items()}, axis=1).dropna()
    val, out = {k: 3000 * w for k, w in weights.items()}, {}
    last = None
    for t, row in rr.iterrows():
        for k in val:
            val[k] *= 1 + row[k]
        if last is not None and t.month != last:
            tot = sum(val.values()) - 2 * 0.99
            val = {k: tot * w for k, w in weights.items()}
        last = t.month
        out[t] = sum(val.values())
    return pd.Series(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kairo", nargs="*", default=[])
    a = ap.parse_args(argv)
    t0 = time.time()
    px = _closes(TICK)
    cal = px["SPY"].dropna().index
    px = px.reindex(cal).ffill(limit=5)
    cash = (px["^IRX"].ffill().fillna(0) / 100 / 252).shift(1).fillna(0)
    r = px[["SPY", "EFA", "EEM"]].pct_change()
    wr = (0.55 * r["SPY"] + 0.35 * r["EFA"] + 0.10 * r["EEM"]).dropna()
    world = (1 + wr).cumprod() * 100
    print("Daten:", {c: str(px[c].first_valid_index().date()) for c in px.columns if px[c].notna().any()}, flush=True)
    rep = {"generated": time.strftime("%Y-%m-%d"), "proxy": "55 % SPY + 35 % EFA + 10 % EEM"}
    # 1) Sparplan-Regeln
    sp = {}
    for nm, ser in (("Welt-Proxy ab 2003", world), ("ACWI ab 2008", px["ACWI"]), ("SPDR ACWI IMI (SPYI, Euro) ab 2011", px["SPYI.DE"])):
        ser = ser.dropna()
        if len(ser) < 600:
            continue
        sp[nm] = {k: savings(ser, cash, k) for k in ("S0", "S1", "S2", "S3", "S4")}
        sp[nm]["zeitraum"] = [str(ser.index[0].date()), str(ser.index[-1].date())]
    rep["sparplan"] = sp
    rep["regeln"] = {"S0": "jeden Monat gleich viel", "S1": "am Hoch 25 % zurückhalten, bei −10 % die Hälfte, ab −20 % alles der Reserve nachkaufen",
                     "S2": "über der 200-Tage-Linie 25 % zurückhalten, nahe/unter ihr (≤ +2 %) alles nachkaufen",
                     "S3": "Trendfilter: über der 200-Tage-Linie investiert, darunter alles im Geldmarkt",
                     "S4": "nur kaufen, wenn unter der 200-Tage-Linie"}
    # 2) Was folgt auf Hochs und Rücksetzer?
    rep["vorwaerts"] = {"Welt-Proxy ab 2003": forward_stats(world), "ACWI ab 2008": forward_stats(px["ACWI"])}
    # 3) Trading-Bereich
    sers = {}
    wpx = world.reindex(cal).ffill()
    sers["2× Welt mit Trendfilter"] = trend_series(wr.reindex(cal).fillna(0), wpx, cash, 2.0)
    sers["1× Welt mit Trendfilter"] = trend_series(wr.reindex(cal).fillna(0), wpx, cash, 1.0)
    sers["2× S&P 500 mit Trendfilter"] = trend_series(r["SPY"].fillna(0), px["SPY"], cash, 2.0)
    sers["Welt-Proxy halten"] = (1 + wr.reindex(cal).fillna(0)).cumprod() * 3000
    ks = load_kairo(a.kairo)
    out3 = {}
    if ks:
        kr = pd.concat([k.reindex(cal).ffill().pct_change() for k in ks], axis=1).dropna().mean(axis=1)
        sers["Kairo-Swing"] = (1 + kr).cumprod() * 3000
        k0 = sers["Kairo-Swing"].index[0]
        cand = {"Kairo-Swing allein": sers["Kairo-Swing"],
                "2× Welt mit Trendfilter": sers["2× Welt mit Trendfilter"],
                "2× S&P 500 mit Trendfilter": sers["2× S&P 500 mit Trendfilter"],
                "Welt-Proxy halten": sers["Welt-Proxy halten"]}
        for w in (0.5, 0.7):
            cand[f"{int(w * 100)} % Kairo + {int((1 - w) * 100)} % 2× Welt-Trend"] = mix({"k": sers["Kairo-Swing"], "t": sers["2× Welt mit Trendfilter"]}, {"k": w, "t": 1 - w})
            cand[f"{int(w * 100)} % Kairo + {int((1 - w) * 100)} % 2× S&P-Trend"] = mix({"k": sers["Kairo-Swing"], "t": sers["2× S&P 500 mit Trendfilter"]}, {"k": w, "t": 1 - w})
        for nm, s in cand.items():
            s = s[s.index >= k0]
            out3[nm] = stats(s, "active", 1.0)
    for nm in ("2× Welt mit Trendfilter", "1× Welt mit Trendfilter", "2× S&P 500 mit Trendfilter", "Welt-Proxy halten"):
        s = sers[nm]
        out3[nm + " (ab 2003)"] = stats(s[s.index >= "2003-06-01"], "active", 1.0)
    rep["trading_bereich"] = out3
    (ROOT / "data" / "etftest.json").write_text(json.dumps(rep, ensure_ascii=False, separators=(",", ":")))
    print("===BEGIN===")
    print(json.dumps(rep, ensure_ascii=False, separators=(",", ":")))
    print("===END===")
    print(f"fertig in {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
