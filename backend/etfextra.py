"""Extra-Geld für den ETF: sofort investieren oder auf einen besseren Zeitpunkt warten?

Jeden Monat kommt der gleiche Betrag Extra-Geld dazu (z. B. Bonus, Rücklage). Regel E0 investiert sofort. Die anderen
Regeln warten, bis ein Kaufsignal kommt (Kurs unter der EMA 100 / EMA 200, x % unter dem Hoch, VIX hoch …), und
investieren dann die ganze Reserve. Damit Geld nicht ewig herumliegt: nach höchstens N Monaten Wartezeit wird es
trotzdem investiert. Die Reserve bekommt solange Geldmarktzins. Bewertet wird der Endwert gegenüber „sofort“.

Zeiträume getrennt: S&P 500 ab 1990 (Kursindex + Dividende ≈ SPY ab 1993), Welt-Proxy ab 2003, ACWI ab 2008, SPYI ab 2011.

    python -m backend.etfextra
"""

from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from .config import ROOT
from .grandtest import _closes

TICK = ["SPY", "EFA", "EEM", "ACWI", "SPYI.DE", "^IRX", "^VIX"]
WAITS = (3, 6, 12, 999)


def signals(px: pd.Series, vix: pd.Series) -> dict[str, pd.Series]:
    e100 = px.ewm(span=100, adjust=False).mean()
    e200 = px.ewm(span=200, adjust=False).mean()
    dd = 1 - px / px.cummax()
    v = vix.reindex(px.index).ffill()
    return {
        "unter EMA 200": px < e200,
        "unter EMA 100": px < e100,
        "unter EMA 100 oder 200": (px < e100) | (px < e200),
        "≥ 5 % unter dem Hoch": dd >= 0.05,
        "≥ 10 % unter dem Hoch": dd >= 0.10,
        "VIX ≥ 25": v >= 25,
        "VIX ≥ 30": v >= 30,
        "unter EMA 100 oder ≥ 5 % unter Hoch oder VIX ≥ 25": (px < e100) | (dd >= 0.05) | (v >= 25),
    }


def extra(px: pd.Series, cash: pd.Series, sig: pd.Series | None, wait: int, budget: float = 100.0) -> dict:
    """Monatsende: Extra-Geld kommt dazu. Ohne Signal (sig None) sofort investieren, sonst Reserve bis zum Signal
    oder bis sie `wait` Monate alt ist."""
    idx = px.index
    me = pd.DatetimeIndex(pd.Series(idx, index=idx).groupby([idx.year, idx.month]).last().values)
    me = me[me >= idx[min(250, len(idx) - 1)]]
    me_set = set(me)
    c = cash.reindex(idx).fillna(0).to_numpy()
    p = px.to_numpy(float)
    s = sig.reindex(idx).fillna(False).to_numpy(bool) if sig is not None else None
    units, lots, waited, n_buy_sig = 0.0, [], [], 0
    m = 0
    vals = []
    for i, t in enumerate(idx):
        lots = [[a * (1 + c[i]), k] for a, k in lots]
        if t in me_set:
            m += 1
            lots.append([budget, m])
            if s is None or s[i]:
                if s is not None and len(lots):
                    n_buy_sig += 1
                for a, k in lots:
                    units += a / p[i]
                    waited.append(m - k)
                lots = []
            else:
                keep = []
                for a, k in lots:
                    if m - k >= wait:
                        units += a / p[i]
                        waited.append(m - k)
                    else:
                        keep.append([a, k])
                lots = keep
        if t >= me[0]:
            vals.append(units * p[i] + sum(a for a, _ in lots))
    v = np.array(vals)
    contrib = len(me) * budget
    return {"vielfaches": round(float(v[-1] / contrib), 4), "warte_monate": round(float(np.mean(waited)), 2) if waited else 0,
            "monate_gruen": round(float(np.mean([bool(s[px.index.get_loc(t)]) for t in me])), 3) if s is not None else 1.0,
            "rest_reserve": round(sum(a for a, _ in lots))}


def main(argv=None) -> int:
    t0 = time.time()
    px = _closes(TICK)
    gspc = _closes(["^GSPC"])["^GSPC"]
    cal = px["SPY"].dropna().index
    cash_all = (pd.concat([px["^IRX"]], axis=1).iloc[:, 0].ffill().fillna(0) / 100 / 252).shift(1).fillna(0)
    r = px[["SPY", "EFA", "EEM"]].reindex(cal).ffill(limit=5).pct_change()
    world = (1 + (0.55 * r["SPY"] + 0.35 * r["EFA"] + 0.10 * r["EEM"]).dropna()).cumprod() * 100
    sers = {"S&P 500 ab 1990 (ohne Dividende)": gspc[gspc.index >= "1989-01-01"].dropna(),
            "SPY ab 1993": px["SPY"].dropna(), "Welt-Proxy ab 2003": world.dropna(), "ACWI ab 2008": px["ACWI"].dropna(),
            "SPYI (Euro) ab 2011": px["SPYI.DE"].dropna()}
    vix = px["^VIX"].dropna()
    rep = {"generated": time.strftime("%Y-%m-%d"), "regel": "Extra-Geld monatlich; warten bis Signal, spätestens N Monate", "ergebnis": {}}
    for nm, ser in sers.items():
        if len(ser) < 600:
            continue
        cash = cash_all.reindex(ser.index).fillna(0)
        base = extra(ser, cash, None, 0)
        res = {"sofort": base, "zeitraum": [str(ser.index[0].date()), str(ser.index[-1].date())]}
        for sn, sg in signals(ser, vix).items():
            for w in WAITS:
                x = extra(ser, cash, sg, w)
                x["vs_sofort"] = round(x["vielfaches"] / base["vielfaches"] - 1, 4)
                res[f"{sn} · max {w if w < 999 else '∞'} M"] = x
        rep["ergebnis"][nm] = res
        print(nm, "sofort", base["vielfaches"], flush=True)
        for k, x in res.items():
            if k not in ("sofort", "zeitraum"):
                print(f"  {k}: {x['vs_sofort']:+.2%} · grün {x['monate_gruen']:.0%} · Ø warten {x['warte_monate']} M", flush=True)
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "etfextra.json").write_text(json.dumps(rep, ensure_ascii=False, separators=(",", ":")))
    print("===BEGIN===")
    print(json.dumps(rep, ensure_ascii=False, separators=(",", ":")))
    print("===END===")
    print(f"fertig in {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
