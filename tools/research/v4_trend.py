"""Forschung v4: Index-Trendfolge mit Hebel (Plan docs/RESEARCH_V4_PLAN.md). Läuft auf GitHub (Yahoo erreichbar)."""
import json
import numpy as np
import pandas as pd
import yfinance as yf

PER = {"Train": ("1989-01-01", "2007-12-31"), "Validierung": ("2008-01-01", "2016-12-31"), "Holdout": ("2017-01-01", "2026-12-31"),
       "Gesamt": ("1989-01-01", "2026-12-31")}


def load():
    px = {}
    for t in ("^SP500TR", "^NDX", "^IRX"):
        d = yf.download(t, start="1985-01-01", progress=False, auto_adjust=False)
        c = d["Close"]
        px[t] = (c.iloc[:, 0] if isinstance(c, pd.DataFrame) else c).dropna()
    idx = px["^SP500TR"].index
    rf = (px["^IRX"].reindex(idx).ffill() / 100).fillna(0.03)
    return {"SP": px["^SP500TR"], "NQ": px["^NDX"].reindex(idx).ffill()}, rf


def sim(level, rf, lev, sma, div=0.0, cost=0.0025):
    r = level.pct_change().fillna(0) + div / 252
    on = (level > level.rolling(sma).mean()) if sma else pd.Series(True, index=level.index)
    pos = on.shift(2).fillna(False).astype(float)              # Signal am Schluss t, Umsetzung einen Tag später
    ter = (0.006 if lev > 1 else 0.001) / 252
    inv = lev * r - (lev - 1) * (rf + 0.005) / 252 - ter
    day = pos * inv + (1 - pos) * rf / 252 - pos.diff().abs().fillna(0) * cost
    return (1 + day).cumprod(), int(pos.diff().abs().sum())


def stats(eq, a, b):
    e = eq[(eq.index >= a) & (eq.index <= b)]
    if len(e) < 50:
        return None
    e = e / e.iloc[0]
    yrs = (e.index[-1] - e.index[0]).days / 365.25
    r = e.pct_change().dropna()
    return {"cagr": round(float(e.iloc[-1] ** (1 / yrs) - 1), 4), "max_dd": round(float((e / e.cummax() - 1).min()), 3),
            "sharpe": round(float(r.mean() / r.std() * np.sqrt(252)), 2)}


def main():
    L, rf = load()
    print("Daten:", {k: (str(v.index[0].date()), str(v.index[-1].date())) for k, v in L.items()})
    V = {"SP1": ("SP", 1, 0), "SP1F": ("SP", 1, 200), "SP2": ("SP", 2, 0), "SP2F": ("SP", 2, 200), "SP3F": ("SP", 3, 200),
         "NQ1": ("NQ", 1, 0), "NQ2F": ("NQ", 2, 200), "NQ3F": ("NQ", 3, 200)}
    res = {}
    for n, (ix, lev, sma) in V.items():
        eq, sw = sim(L[ix], rf, lev, sma, 0.01 if ix == "NQ" else 0.0)
        res[n] = {ab: stats(eq, *PER[ab]) for ab in PER}
        res[n]["wechsel"] = sw
        print(n, " | ".join(f"{ab}: {s['cagr']:+.1%} DD {s['max_dd']:.0%} S {s['sharpe']}" for ab, s in res[n].items() if isinstance(s, dict)), f"| Wechsel {sw}")
    base = res["SP1"]
    for n in V:
        if n == "SP1":
            continue
        ok1 = all(res[n][ab]["cagr"] > base[ab]["cagr"] for ab in ("Train", "Validierung", "Holdout"))
        ok2 = res[n]["Gesamt"]["max_dd"] >= base["Gesamt"]["max_dd"] - 0.15
        rob = []
        ix, lev, sma = V[n]
        if sma:
            for s2 in (100, 150, 250):
                eq, _ = sim(L[ix], rf, lev, s2, 0.01 if ix == "NQ" else 0.0)
                rob.append((s2, stats(eq, *PER["Gesamt"])["cagr"]))
        ok3 = bool(sma) and all(c > base["Gesamt"]["cagr"] for _, c in rob)
        res[n]["urteil"] = {"alle_zeitraeume": ok1, "rueckgang_ok": ok2, "robust": ok3, "robust_werte": rob, "bestanden": ok1 and ok2 and ok3}
        print(f"  {n}: alle Zeiträume besser {ok1} · Rückgang ok {ok2} · robust {ok3} {rob} → {'KANDIDAT' if ok1 and ok2 and ok3 else 'nicht bestanden'}")
    print("JSON", json.dumps(res))


if __name__ == "__main__":
    main()
