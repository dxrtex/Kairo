"""Praxistest der ETF-Einstiegsampel (Reiter ETF, etfTiming in site/index.html) über Jahrzehnte.

Bildet die Ampel der App exakt nach (Punkte aus Rücksetzer vom 52-Wochen-Hoch, Nähe zu EMA 50/100/200, RSI 14,
Überhitzung über EMA 50, Monatsanstieg bis aufs Hoch, VIX) und prüft:
  1. Was folgte nach jeder Farbe? Rendite 3 / 6 / 12 Monate später (alle Tage und nur Monatsenden).
  2. Bringt es Geld? Extra-Geld kommt jeden Monat (1 Einheit). Vergleich der Endvermögen:
     sofort anlegen · nach Ampel (Grün sofort, Gelb in 3 Raten, Rot zurückhalten, spätestens nach 8 Wochen in Raten) ·
     Varianten (nur Rot zurückhalten, nur bei Grün, Rot ohne Zeitlimit).
Indizes: S&P 500 (^GSPC, mit VIX ab 1990), MSCI-Welt-ETF ACWI (ab 2008), URTH (ab 2012). Kursindizes ohne Dividenden –
für den Vergleich der Zeitpunkte unerheblich (alle Varianten investieren dieselbe Summe in denselben Index).
Ausgabe: research/etf_ampel_result.json und eine Zusammenfassung im Log.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf


def load(sym: str, start: str) -> pd.Series:
    df = yf.download(sym, start=start, auto_adjust=False, progress=False)
    s = df["Close"]
    if isinstance(s, pd.DataFrame):
        s = s.iloc[:, 0]
    return s.dropna()


def ema(a: np.ndarray, p: int) -> np.ndarray:
    k = 2 / (p + 1)
    o = np.empty_like(a)
    o[0] = a[0]
    for i in range(1, len(a)):
        o[i] = o[i - 1] + k * (a[i] - o[i - 1])
    return o


def rsi(a: np.ndarray, n: int = 14) -> np.ndarray:
    r = np.full(len(a), np.nan)
    g = l = 0.0
    for i in range(1, len(a)):
        ch = a[i] - a[i - 1]
        up, dn = max(ch, 0), max(-ch, 0)
        if i <= n:
            g += up / n
            l += dn / n
        else:
            g = (g * (n - 1) + up) / n
            l = (l * (n - 1) + dn) / n
        if i >= n:
            r[i] = 100 - 100 / (1 + g / l) if l else 100
    return r


def ampel(c: np.ndarray, vix: np.ndarray | None) -> tuple[np.ndarray, np.ndarray]:
    """Farbe je Tag wie etfTiming in der App: g / y / r (ohne Kreditmarkt-Signal, das es historisch nicht gibt)."""
    n = len(c)
    e50, e100, e200, R = ema(c, 50), ema(c, 100), ema(c, 200), rsi(c)
    lv = np.array(["y"] * n, dtype=object)
    sc = np.zeros(n)
    for i in range(260, n):
        hi = c[max(0, i - 252): i + 1].max()
        dd = 1 - c[i] / hi
        r = R[i] if not math.isnan(R[i]) else 50
        s = 0.0
        if dd >= .10: s += 3
        elif dd >= .06: s += 2
        elif dd >= .03: s += 1
        near = lambda E: c[i] <= E[i] * 1.01
        if near(e200): s += 2
        elif near(e100): s += 1.5
        elif near(e50): s += .5
        if r <= 30: s += 2
        elif r <= 40: s += 1
        elif r >= 70: s -= 2
        elif r >= 63: s -= 1
        if c[i] > e50[i] * 1.04: s -= 1
        if dd < .01 and c[i] / c[max(0, i - 20)] - 1 >= .04: s -= 1
        if vix is not None and not math.isnan(vix[i]):
            if vix[i] >= 30: s += 2
            elif vix[i] >= 25: s += 1
        sc[i] = s
        lv[i] = "g" if s >= 2.5 else "r" if s <= -1 else "y"
    return lv, sc


def forward(c: np.ndarray, lv: np.ndarray, idx: pd.DatetimeIndex) -> dict:
    out = {}
    month_end = np.array([i + 1 < len(idx) and idx[i + 1].month != idx[i].month for i in range(len(idx))])
    for h, name in ((63, "3M"), (126, "6M"), (252, "12M")):
        row = {}
        for k in ("g", "y", "r", "all"):
            sel = [i for i in range(260, len(c) - h) if k == "all" or lv[i] == k]
            sel_m = [i for i in sel if month_end[i]]
            f = np.array([c[i + h] / c[i] - 1 for i in sel])
            fm = np.array([c[i + h] / c[i] - 1 for i in sel_m])
            row[k] = {"n_tage": len(sel), "share": round(len(sel) / max(1, len(range(260, len(c) - h))), 3),
                      "avg": round(float(f.mean()), 4) if len(f) else None, "median": round(float(np.median(f)), 4) if len(f) else None,
                      "win": round(float((f > 0).mean()), 3) if len(f) else None,
                      "n_monate": len(sel_m), "avg_monat": round(float(fm.mean()), 4) if len(fm) else None}
        out[name] = row
    return out


def simulate(c: np.ndarray, lv: np.ndarray, idx: pd.DatetimeIndex, policy: str) -> dict:
    """Jeden Monatsanfang kommt 1 Einheit Extra-Geld. Policies:
    now: sofort · app: Grün alles, Gelb 1/3 des Bestands je Monat (3 Raten), Rot halten, nach 8 Wochen Gelb-Regel ·
    red_only: nur bei Rot halten (max. 8 Wochen), sonst sofort · green_only: nur bei Grün (Rest liegt) · red_nolimit: Rot halten ohne Limit."""
    cash = units = invested = 0.0
    held_since = None
    last_m = None
    pay_days = []
    for i in range(260, len(c)):
        d = idx[i]
        new_month = last_m is None or d.month != last_m
        if new_month:
            cash += 1.0
            invested += 1.0
            last_m = d.month
        col = lv[i]
        buy = 0.0
        if policy == "now":
            buy = cash
        elif policy == "app":
            if col == "r":
                held_since = held_since if held_since is not None else i
                if i - held_since >= 40 and new_month:      # spätestens nach 8 Wochen: in Raten
                    buy = cash / 3 if cash > 1.5 else cash
            else:
                held_since = None
                if col == "g":
                    buy = cash
                elif new_month:
                    buy = cash / 3 if cash > 1.5 else cash      # Gelb: höchstens 3 Raten
        elif policy == "red_only":
            if col == "r":
                held_since = held_since if held_since is not None else i
                if i - held_since >= 40:
                    buy = cash
            else:
                held_since = None
                buy = cash
        elif policy == "green_only":
            buy = cash if col == "g" else 0.0
        elif policy == "red_nolimit":
            buy = 0.0 if col == "r" else cash
        if buy > 1e-12:
            units += buy / c[i]
            cash -= buy
            pay_days.append(i)
    wealth = units * c[-1] + cash
    return {"end": round(wealth, 2), "eingezahlt": round(invested, 1), "faktor": round(wealth / invested, 4), "cash_rest": round(cash, 2)}


def run(name: str, s: pd.Series, vix: pd.Series | None) -> dict:
    idx = s.index
    c = s.values.astype(float)
    v = vix.reindex(idx).ffill().values.astype(float) if vix is not None else None
    lv, sc = ampel(c, v)
    res = {"zeitraum": f"{idx[260].date()} – {idx[-1].date()}", "forward": forward(c, lv, idx)}
    res["sim"] = {p: simulate(c, lv, idx, p) for p in ("now", "app", "red_only", "green_only", "red_nolimit")}
    # dieselbe Prüfung je Jahrzehnt / Teilzeitraum (Robustheit)
    parts = {}
    years = sorted(set(d.year for d in idx))
    for a, b in ((1990, 1999), (2000, 2009), (2010, 2019), (2020, 2026)):
        m = (idx.year >= a) & (idx.year <= b)
        if m.sum() > 400:
            sub_c = c[m]
            sub_v = v[m] if v is not None else None
            sl, _ = ampel(sub_c, sub_v)
            sub_idx = idx[m]
            parts[f"{a}-{b}"] = {p: simulate(sub_c, sl, sub_idx, p)["faktor"] for p in ("now", "app", "red_only")}
    res["teilzeitraeume"] = parts
    return res


def main() -> None:
    out = {}
    vix = load("^VIX", "1990-01-01")
    for name, sym, start, use_vix in (("S&P 500 (1990–2026, mit VIX)", "^GSPC", "1989-01-01", True),
                                      ("S&P 500 (1990–2026, ohne VIX)", "^GSPC", "1989-01-01", False),
                                      ("MSCI ACWI-ETF (2008–2026, mit VIX)", "ACWI", "2008-03-28", True),
                                      ("MSCI World-ETF URTH (2012–2026, mit VIX)", "URTH", "2012-01-12", True)):
        try:
            s = load(sym, start)
            out[name] = run(name, s, vix if use_vix else None)
            print(f"\n=== {name}: {out[name]['zeitraum']}")
            for h in ("3M", "12M"):
                f = out[name]["forward"][h]
                print(f"  {h}: " + " · ".join(f"{k}: Ø {f[k]['avg']:+.2%} (Anteil {f[k]['share']:.0%}, positiv {f[k]['win']:.0%})" for k in ("g", "y", "r", "all") if f[k]["avg"] is not None))
            print("  Endvermögen je 1 € Extra-Geld: " + " · ".join(f"{p} {v['faktor']:.4f}" for p, v in out[name]["sim"].items()))
            print("  Teilzeiträume (now/app/red_only): " + " | ".join(f"{k}: {v['now']:.3f}/{v['app']:.3f}/{v['red_only']:.3f}" for k, v in out[name]["teilzeitraeume"].items()))
        except Exception as e:
            print(name, "Fehler:", e, file=sys.stderr)
    Path("research/etf_ampel_result.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
