"""Extra-Geld in Raten: Wenn die ETF-Ampel nur wegen der 3-Monats-Regel grün wird (kein Rücksetzer-Signal),
das fällige Extra-Geld in Raten über einige Wochen anlegen statt auf einmal – kostet das Rendite?

Grundregel wie in der App (backend/etf.py, getestet in backend/etfextra.py): Extra-Geld monatlich; investieren,
sobald Kurs unter der EMA 100, ≥ 5 % unter dem Hoch oder VIX ≥ 25 – spätestens nach 3 Monaten.
Varianten: Bei Freigabe durch die 3-Monats-Regel wird das Geld in R gleichen Raten im Abstand von D Handelstagen
gekauft; kommt in der Zeit ein Signal, wird der Rest sofort gekauft. Wartendes Geld bekommt Geldmarktzins.

Bewertet: Endwert gegenüber „sofort“ und gegenüber der Grundregel, außerdem je Freigabe, wie oft die Raten einen
besseren Ø Preis brachten als der Einmalkauf und wie groß der Unterschied im Mittel/im schlechtesten Fall war.

    python -m backend.etfraten
"""

from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from .config import ROOT
from .etfextra import TICK, extra
from .grandtest import _closes

VARIANTS = {"Grundregel (alles auf einmal)": (1, 0), "3 Raten über 4 Wochen": (3, 10), "3 Raten über 8 Wochen": (3, 20),
            "4 Raten über 12 Wochen": (4, 20)}


def rule(px: pd.Series, vix: pd.Series) -> pd.Series:
    e100 = px.ewm(span=100, adjust=False).mean()
    dd = 1 - px / px.cummax()
    v = vix.reindex(px.index).ffill()
    return (px < e100) | (dd >= 0.05) | (v >= 25)


def run(px: pd.Series, cash: pd.Series, sig: pd.Series, n_tr: int, step: int, wait: int = 3, budget: float = 100.0) -> dict:
    idx = px.index
    me = pd.DatetimeIndex(pd.Series(idx, index=idx).groupby([idx.year, idx.month]).last().values)
    me = me[me >= idx[min(250, len(idx) - 1)]]
    me_set = set(me)
    c = cash.reindex(idx).fillna(0).to_numpy()
    p = px.to_numpy(float)
    s = sig.reindex(idx).fillna(False).to_numpy(bool)
    units, lots, pend, m, vals, events = 0.0, [], [], 0, [], []
    for i, t in enumerate(idx):
        lots = [[a * (1 + c[i]), k] for a, k in lots]
        pend = [[a * (1 + c[i]), d, ev] for a, d, ev in pend]
        if s[i] and pend:                                   # Signal während der Raten: Rest sofort
            for a, d, ev in pend:
                units += a / p[i]; ev["paid"] += a; ev["units"] += a / p[i]
            pend = []
        keep = []
        for a, d, ev in pend:
            if d <= i:
                units += a / p[i]; ev["paid"] += a; ev["units"] += a / p[i]
            else:
                keep.append([a, d, ev])
        pend = keep
        if t in me_set:
            m += 1
            lots.append([budget, m])
            if s[i]:
                for a, k in lots:
                    units += a / p[i]
                lots = []
            else:
                due = [x for x in lots if m - x[1] >= wait]
                lots = [x for x in lots if m - x[1] < wait]
                amt = sum(a for a, _ in due)
                if amt > 0:
                    ev = {"i": i, "lump": amt / p[i], "paid": 0.0, "units": 0.0, "amt": amt}
                    events.append(ev)
                    part = amt / n_tr
                    for j in range(n_tr):
                        if j == 0:
                            units += part / p[i]; ev["paid"] += part; ev["units"] += part / p[i]
                        else:
                            pend.append([part, i + j * step, ev])
        if t >= me[0]:
            vals.append(units * p[i] + sum(a for a, _ in lots) + sum(a for a, _, _ in pend))
    v = np.array(vals)
    contrib = len(me) * budget
    # je Freigabe: Ø Kaufpreis der Raten gegen den Einmalkauf (in Prozent mehr/weniger Anteile)
    rel = [ev["units"] / ev["lump"] - 1 for ev in events if ev["paid"] >= ev["amt"] * 0.999 and ev["lump"] > 0]
    return {"vielfaches": round(float(v[-1] / contrib), 4), "freigaben": len(events),
            "raten_besser": round(float(np.mean([r > 0 for r in rel])), 3) if rel else None,
            "anteile_diff_mittel": round(float(np.mean(rel)), 4) if rel else None,
            "anteile_diff_schlechtest": round(float(np.min(rel)), 4) if rel else None,
            "anteile_diff_best": round(float(np.max(rel)), 4) if rel else None}


def main(argv=None) -> int:
    t0 = time.time()
    px = _closes(TICK)
    gspc = _closes(["^GSPC"])["^GSPC"]
    cal = px["SPY"].dropna().index
    cash_all = (px["^IRX"].ffill().fillna(0) / 100 / 252).shift(1).fillna(0)
    r = px[["SPY", "EFA", "EEM"]].reindex(cal).ffill(limit=5).pct_change()
    world = (1 + (0.55 * r["SPY"] + 0.35 * r["EFA"] + 0.10 * r["EEM"]).dropna()).cumprod() * 100
    sers = {"S&P 500 ab 1990 (ohne Dividende)": gspc[gspc.index >= "1989-01-01"].dropna(),
            "Welt-Proxy ab 2003": world.dropna(), "ACWI ab 2008": px["ACWI"].dropna(), "SPYI (Euro) ab 2011": px["SPYI.DE"].dropna()}
    vix = px["^VIX"].dropna()
    rep = {"generated": time.strftime("%Y-%m-%d"), "regel": "Freigabe nach 3 Monaten ohne Signal: Raten statt Einmalkauf", "ergebnis": {}}
    for nm, ser in sers.items():
        if len(ser) < 600:
            continue
        cash = cash_all.reindex(ser.index).fillna(0)
        base = extra(ser, cash, None, 0)
        sg = rule(ser, vix)
        res = {"zeitraum": [str(ser.index[0].date()), str(ser.index[-1].date())], "sofort": base["vielfaches"]}
        g0 = None
        for vn, (n, st) in VARIANTS.items():
            x = run(ser, cash, sg, n, st)
            g0 = g0 or x["vielfaches"]
            x["vs_sofort"] = round(x["vielfaches"] / base["vielfaches"] - 1, 4)
            x["vs_grundregel"] = round(x["vielfaches"] / g0 - 1, 4)
            res[vn] = x
            print(f"{nm} · {vn}: vs sofort {x['vs_sofort']:+.2%} · vs Grundregel {x['vs_grundregel']:+.2%} · Freigaben {x['freigaben']}"
                  f" · Raten besser {x['raten_besser']} · Anteile Ø {x['anteile_diff_mittel']} (min {x['anteile_diff_schlechtest']}, max {x['anteile_diff_best']})", flush=True)
        rep["ergebnis"][nm] = res
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "etfraten.json").write_text(json.dumps(rep, ensure_ascii=False, separators=(",", ":")))
    print("===BEGIN===")
    print(json.dumps(rep, ensure_ascii=False, separators=(",", ":")))
    print("===END===")
    print(f"fertig in {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
