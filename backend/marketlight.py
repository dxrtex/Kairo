"""Marktampel für Swing-Trades (Haltedauer Wochen bis wenige Monate) – 19.11.2026.

Anlass: Die Wochen-Phase vom 18.11. zeigte „Aufwärtstrend“, obwohl S&P 500 und Nasdaq 100 unter der 50-Tage-Linie lagen,
der VIX bei 25 und invertiert war und es 6–7 Verteilungstage gab. Backtest tools/research/ampel_study.py (S&P 500 ab 1993,
Nasdaq 100 ab 1993, Rendite und Rückschläge der nächsten 20/60 Handelstage):
  · Ein reines Tagesmodell wechselt 13–27× im Jahr und meldet normale Rücksetzer als „Korrektur“ – genau nach solchen
    Tagen waren die Folgerenditen im Schnitt sogar überdurchschnittlich. Als Warnsignal ungeeignet.
  · Die Wochen-Phase trennt die wirklich gefährliche Lage: im Abwärtstrend Nasdaq 100 nur +0,6 % in 60 Tagen, schlimmste 5 %
    der Fälle −21 % in 20 Tagen. Nur investiert, wenn nicht Abwärtstrend/Korrektur: 12,5 % pro Jahr bei max. −32 %
    (Kaufen und Halten 13,7 % bei −83 %), 3–4 Wechsel im Jahr.
  · Bester Mix: Wochen-Phase für den Trend + Tagesdruck nur, um Grün zu Gelb abzustufen. Gelb hatte deutlich größere
    Rückschläge (schlimmste 5 %: −10 % statt −8 % beim Nasdaq) → kleinere Positionen. ~8 Wechsel im Jahr.
Stufen:  3 grün Aufwärtstrend · 2 gelb Unter Druck (Trend intakt, kurzfristig Stress) bzw. Seitwärts · 1 orange Korrektur ·
0 rot Abwärtstrend. Gesamtampel = die schwächere von S&P 500 und Nasdaq 100.
Reine Anzeige: Kairo-Regel, Scan und Strategie nutzen die Ampel nicht.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

LV = {3: ("bull", "Aufwärtstrend", "green"), 2: ("press", "Unter Druck", "yellow"), 1: ("corr", "Korrektur", "orange"), 0: ("bear", "Abwärtstrend", "red")}
DO = {3: "Rückenwind – Swing-Trades mit normaler Positionsgröße.",
      2: "Trend intakt, aber kurzfristig Stress: nur die besten Setups, kleinere Positionen, Stops konsequent.",
      1: "Korrektur: höchstens halbe Positionsgröße und nur sehr starke Aktien – oder abwarten.",
      0: "Abwärtstrend: keine neuen Swing-Trades. Historisch kaum Ertrag bei großen Rückschlägen – Kapital schützen."}
WK = {"bull": 3, "neutral": 2, "corr": 1, "bear": 0}
P = dict(up_n=5, buf=0.0, dd_p=-0.05, dd_c=-0.10, dd_b=-0.20, dist_n=5, vix_p=22.0, vix_c=30.0, use_dist=True, use_vix=True, use_credit=True)


def _s(df, col="Close"):
    if df is None or col not in df:
        return None
    s = df[col].astype(float)
    s = s[~s.index.duplicated(keep="last")].dropna()
    return s if len(s) else None


def raw_levels(df: pd.DataFrame, vix=None, vix3m=None, credit=None, p: dict | None = None) -> pd.DataFrame:
    """Tageskurse eines Index → je Tag rohe Stufe 0–3 und die Gründe als Spalten."""
    p = {**P, **(p or {})}
    c = _s(df)
    v = _s(df, "Volume")
    s50, s200 = c.rolling(50).mean(), c.rolling(200).mean()
    sl50, sl200 = s50 / s50.shift(20) - 1, s200 / s200.shift(20) - 1
    dd = c / c.rolling(252, min_periods=200).max() - 1
    r1 = c.pct_change()
    if v is not None and p["use_dist"] and (v.reindex(c.index).fillna(0) > 0).mean() > 0.9:
        vv = v.reindex(c.index)
        dist = ((r1 <= -0.002) & (vv > vv.shift(1))).astype(int).rolling(25).sum()
    else:
        dist = pd.Series(0, index=c.index)
    vx = _s(vix).reindex(c.index).ffill() if vix is not None and p["use_vix"] else pd.Series(np.nan, index=c.index)
    vx3 = _s(vix3m).reindex(c.index).ffill() if vix3m is not None and p["use_vix"] else pd.Series(np.nan, index=c.index)
    inv = (vx / vx3) > 1.0
    if credit is not None and p["use_credit"]:
        cr = credit.reindex(c.index).ffill()
        coff = (cr < cr.rolling(50).mean()) & (cr.rolling(50).mean() < cr.rolling(50).mean().shift(10))
    else:
        coff = pd.Series(False, index=c.index)
    b = 1 - p["buf"]
    bear = (dd <= p["dd_b"]) | ((c < s200 * b) & (s50 < s200) & (sl200 < 0))
    corr = (c < s200 * b) | (dd <= p["dd_c"]) | ((c < s50) & (sl50 < 0)) | (inv & (c < s50)) | (vx >= p["vix_c"])
    press = (c < s50) | (dd <= p["dd_p"]) | (dist >= p["dist_n"]) | (vx >= p["vix_p"]) | coff
    lv = pd.Series(3, index=c.index)
    lv[press] = 2
    lv[corr] = 1
    lv[bear] = 0
    ok = s200.notna() & dd.notna()
    return pd.DataFrame({"lv": lv.where(ok), "c": c, "s50": s50, "s200": s200, "sl50": sl50, "dd": dd, "dist": dist, "vix": vx, "inv": inv, "coff": coff})


def smooth(raw: pd.Series, up_n: int) -> pd.Series:
    """Herabstufen sofort, Heraufstufen erst nach up_n Tagen in Folge auf mindestens der besseren Stufe."""
    out, st = [], None
    vals = raw.to_numpy()
    for i, r in enumerate(vals):
        if np.isnan(r):
            out.append(np.nan)
            continue
        r = int(r)
        if st is None or r < st:
            st = r
        elif r > st:
            w = vals[max(0, i - up_n + 1): i + 1]
            if len(w) >= up_n and not np.isnan(w).any():
                st = max(st, int(w.min()))
        out.append(st)
    return pd.Series(out, index=raw.index)


def combine(week: pd.Series, day: pd.Series) -> pd.Series:
    """Wochen-Stufe bestimmt den Trend; bei Wochen-Aufwärtstrend stuft Tagesdruck (geglättet) Grün auf Gelb ab."""
    j = pd.concat([week, day], axis=1).dropna()
    w, d = j.iloc[:, 0], j.iloc[:, 1]
    return pd.Series(np.where(w < 3, w, np.where(d >= 3, 3, 2)), index=j.index, dtype=float)


def week_levels(df, vix=None) -> pd.Series | None:
    from .marketphase import market_phase
    ph = market_phase(df, vix, keep=100000)
    if not ph:
        return None
    s = pd.Series({pd.Timestamp(d): WK[k] for d, k in ph["hist"]}).sort_index()
    return s, ph


def light(df, vix=None, vix3m=None, credit=None, p: dict | None = None, keep: int = 260) -> dict | None:
    """Ampel eines Index für die App: Stufe, seit wann, Gründe, Verlauf (Tage)."""
    if df is None or _s(df) is None or len(_s(df)) < 260:
        return None
    p = {**P, **(p or {})}
    R = raw_levels(df, vix, vix3m, credit, p)
    day = smooth(R["lv"], p["up_n"]).dropna()
    wk = week_levels(df, vix)
    if day.empty or not wk:
        return None
    ws, ph = wk
    week_d = ws.reindex(day.index, method="bfill").fillna(float(ws.iloc[-1]))   # Wochenschluss gilt für die Tage seiner Woche
    lv = combine(week_d, day).dropna()
    if lv.empty:
        return None
    k = int(lv.iloc[-1])
    chg = lv[lv != k]
    since = lv.index[0] if chg.empty else lv[lv.index > chg.index[-1]].index[0]
    x = R.iloc[-1]
    raw_now = int(R["lv"].iloc[-1])
    pct = lambda a: f"{a * 100:+.1f} %".replace(".", ",")
    why = [
        [bool(x.c >= x.s50), f"{'über' if x.c >= x.s50 else 'unter'} der 50-Tage-Linie ({pct(x.c / x.s50 - 1)})"],
        [bool(x.c >= x.s200), f"{'über' if x.c >= x.s200 else 'unter'} der 200-Tage-Linie ({pct(x.c / x.s200 - 1)})"],
        [bool(x.sl50 >= 0), f"50-Tage-Linie {'steigt' if x.sl50 >= 0 else 'fällt'}"],
        [bool(x.dd > -0.05), "nahe am 52-Wochen-Hoch" if x.dd > -0.02 else f"{abs(x.dd) * 100:.1f} % unter dem 52-Wochen-Hoch".replace(".", ",")],
    ]
    if R["dist"].iloc[-1] > 0 or p["use_dist"]:
        n = int(R["dist"].iloc[-1])
        why.append([n < p["dist_n"], f"{n} Verteilungstage in 25 Tagen (Verkäufe mit steigendem Volumen{', ab 5 kritisch' if n >= 3 else ''})"])
    if not np.isnan(x.vix):
        why.append([bool(x.vix < p["vix_p"]), f"VIX {x.vix:.0f}{' – Terminkurve invertiert (akuter Stress)' if bool(x.inv) else ''}".replace(".", ",")])
    if bool(x.coff):
        why.append([False, "Kreditmarkt nervös (Hochzinsanleihen schwächer als Staatsanleihen)"])
    wk_now = WK[ph["k"]]
    why.insert(0, [wk_now >= 3, f"Wochentrend: {ph['label']} seit {ph['weeks']} Wochen (40-Wochen-Linie, Abstand zum Hoch)"])
    key, label, tone = LV[k]
    if k == 2 and wk_now == 2:
        key, label = "side", "Seitwärts"
    hist = [[d.strftime("%Y-%m-%d"), int(v)] for d, v in lv.iloc[-keep:].items()]
    return {"lv": k, "k": key, "label": label, "tone": tone, "do": DO[k], "since": since.strftime("%Y-%m-%d"),
            "days": int((lv.index >= since).sum()), "raw": raw_now, "week": ph["k"], "day": int(day.iloc[-1]), "why": why, "dd": round(float(x.dd), 4), "hist": hist}


def credit_ratio(hyg, ief):
    a, b = _s(hyg), _s(ief)
    if a is None or b is None:
        return None
    j = pd.concat([a, b], axis=1, join="inner").dropna()
    return j.iloc[:, 0] / j.iloc[:, 1] if len(j) > 60 else None


def market_lights(h: dict) -> dict | None:
    """Alle Ampeln aus dem Scan-Kontext (yfinance-Historie je Kürzel) + Gesamtampel."""
    g = lambda t: h.get(t)
    cr = credit_ratio(g("HYG"), g("IEF"))
    out = {}
    for t in ("^GSPC", "^NDX", "URTH", "^GDAXI"):
        us = t in ("^GSPC", "^NDX")
        x = light(g(t), g("^VIX") if us else None, g("^VIX3M") if us else None, cr if us else None)
        if x:
            out[t] = x
    us = [out[t] for t in ("^GSPC", "^NDX") if t in out]
    if not us:
        return None
    w = min(us, key=lambda x: x["lv"])
    out["all"] = {**w, "src": "^GSPC" if w is out.get("^GSPC") else "^NDX"}
    return out
