"""Marktampel für Swing-Trades (Haltedauer Wochen bis wenige Monate) – 19.11.2026, ersetzt die Wochen-Marktphase vom 18.11.

Warum neu: Die Wochen-Phase zeigte am 18.11.2026 „Aufwärtstrend“, obwohl der S&P 500 6 % unter dem Hoch, unter der
50-Tage-Linie und an der 200-Tage-Linie stand, der VIX bei 25 lag und Wachstums-/Momentum-Aktien 12–23 % gefallen waren.
Fehler: nur der S&P 500, nur Wochenschlüsse, Herabstufung erst nach zwei Wochen.

Jetzt (so arbeiten auch IBD „Market Pulse“, Minervini, O'Neil): vier Stufen je Index, aus Tageskursen.
  3 grün   Aufwärtstrend           Kurs über 50- und 200-Tage-Linie, nahe am Hoch, Angst niedrig → normal handeln
  2 gelb   Aufwärtstrend unter Druck  unter der 50-Tage-Linie, ≥ 5 % unter dem Hoch, Verteilungstage, VIX erhöht,
                                    Kreditmarkt nervös → nur die besten Setups, kleiner
  1 orange Korrektur               unter der 200-Tage-Linie, ≥ 10 % unter dem Hoch, fallende 50-Tage-Linie, VIX-Kurve
                                    invertiert → keine neuen Swing-Trades
  0 rot    Abwärtstrend            ≥ 20 % unter dem Hoch oder 50 < 200 bei fallender 200-Tage-Linie → Cash
Asymmetrisch wie im Risikomanagement üblich: Herabstufen sofort am Tagesschluss, Heraufstufen erst, wenn die bessere
Stufe UP_N Handelstage in Folge vorliegt (keine Fehlsignale nach einem Erholungstag).
Gesamtampel = die schwächere von S&P 500 und Nasdaq 100 (US-Aktien und Tech tragen die meisten Swing-Trades).
Reine Anzeige: Kairo-Regel, Scan und Strategie nutzen die Ampel nicht.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

LV = {3: ("bull", "Aufwärtstrend", "green"), 2: ("press", "Unter Druck", "yellow"), 1: ("corr", "Korrektur", "orange"), 0: ("bear", "Abwärtstrend", "red")}
DO = {3: "Normal handeln – Rückenwind für Swing-Trades.", 2: "Nur die besten Setups, kleinere Positionen, Stops eng nachziehen.",
      1: "Keine neuen Swing-Trades – bestehende absichern, Cash ist eine Position.", 0: "Kapital schützen – keine neuen Käufe, abwarten."}
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


def light(df, vix=None, vix3m=None, credit=None, p: dict | None = None, keep: int = 260) -> dict | None:
    """Ampel eines Index für die App: Stufe, seit wann, Gründe, Verlauf (Tage)."""
    if df is None or _s(df) is None or len(_s(df)) < 260:
        return None
    p = {**P, **(p or {})}
    R = raw_levels(df, vix, vix3m, credit, p)
    lv = smooth(R["lv"], p["up_n"]).dropna()
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
    key, label, tone = LV[k]
    hist = [[d.strftime("%Y-%m-%d"), int(v)] for d, v in lv.iloc[-keep:].items()]
    return {"lv": k, "k": key, "label": label, "tone": tone, "do": DO[k], "since": since.strftime("%Y-%m-%d"),
            "days": int((lv.index >= since).sum()), "raw": raw_now, "why": why, "dd": round(float(x.dd), 4), "hist": hist}


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
