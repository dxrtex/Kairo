"""Gesamtlage für die ETF-Ampel: Welche Faktoren sagen die nächsten 12 Monate wirklich voraus?

Monatsende-Stichproben (wenig Überlappung), zwei getrennte Zeiträume (1990–2007 / 2008–heute), S&P 500 lang und
Welt-Proxy (55 % SPY + 35 % EFA + 10 % EEM) ab 2003. Je Faktor: Ø Rendite 12 Monate später, Anteil im Minus, Anteil
mit zwischenzeitlich −10 %. Ein Faktor zählt nur, wenn er in BEIDEN Zeiträumen in dieselbe Richtung zeigt.

    python -m backend.etffactors
"""

from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from .config import ROOT
from .grandtest import _closes

TICK = ["^GSPC", "^VIX", "^TNX", "^IRX", "HYG", "IEF", "SPY", "EFA", "EEM"]


def features(px: pd.Series, d: pd.DataFrame) -> pd.DataFrame:
    hi = px.cummax()
    sma = px.rolling(200).mean()
    f = pd.DataFrame(index=px.index)
    f["dd"] = 1 - px / hi
    f["unter_sma200"] = px < sma
    f["mom12"] = px / px.shift(252) - 1
    f["vix"] = d["^VIX"].reindex(px.index).ffill(limit=5)
    f["kurve"] = (d["^TNX"] - d["^IRX"]).reindex(px.index).ffill(limit=5)
    cr = (d["HYG"] / d["IEF"]).reindex(px.index).ffill(limit=5)
    f["kredit_schwach"] = (cr < cr.rolling(200).mean()).where(cr.rolling(200).mean().notna())
    f["f12"] = px.shift(-252) / px - 1
    fmin = px[::-1].rolling(252, min_periods=200).min()[::-1].shift(-1) / px - 1
    f["dd12"] = fmin
    return f


def buckets(f: pd.DataFrame) -> dict:
    return {
        "Abstand zum Hoch": [("am Hoch (< 3 %)", f.dd < .03), ("3–10 % darunter", (f.dd >= .03) & (f.dd < .10)),
                             ("10–20 % darunter", (f.dd >= .10) & (f.dd < .20)), ("≥ 20 % darunter", f.dd >= .20)],
        "200-Tage-Linie": [("darüber", f.unter_sma200 == False), ("darunter", f.unter_sma200 == True)],
        "12-Monats-Trend": [("> +15 %", f.mom12 > .15), ("0 bis +15 %", (f.mom12 >= 0) & (f.mom12 <= .15)), ("im Minus", f.mom12 < 0)],
        "VIX (Angst)": [("< 14 sehr ruhig/Euphorie", f.vix < 14), ("14–20 normal", (f.vix >= 14) & (f.vix < 20)),
                        ("20–30 nervös", (f.vix >= 20) & (f.vix < 30)), ("≥ 30 Panik", f.vix >= 30)],
        "Zinskurve 10J − 3M": [("normal (> 1 %)", f.kurve > 1), ("flach (0–1 %)", (f.kurve >= 0) & (f.kurve <= 1)), ("invertiert (< 0)", f.kurve < 0)],
        "Kreditmarkt (HYG/IEF)": [("stabil", f.kredit_schwach == False), ("schwächelt", f.kredit_schwach == True)],
    }


def table(f: pd.DataFrame) -> dict:
    out = {}
    f = f.dropna(subset=["f12"])
    for name, bs in buckets(f).items():
        rows = []
        for lbl, m in bs:
            x = f[m.fillna(False).astype(bool)]
            if len(x) >= 6:
                rows.append({"lage": lbl, "n": int(len(x)), "f12": round(float(x.f12.mean()), 4), "median": round(float(x.f12.median()), 4),
                             "minus": round(float((x.f12 < 0).mean()), 3), "rueckgang10": round(float((x.dd12 <= -.10).mean()), 3)})
        out[name] = rows
    out["_alle"] = {"n": int(len(f)), "f12": round(float(f.f12.mean()), 4), "minus": round(float((f.f12 < 0).mean()), 3),
                    "rueckgang10": round(float((f.dd12 <= -.10).mean()), 3)}
    return out


def month_ends(f: pd.DataFrame) -> pd.DataFrame:
    idx = f.index
    me = pd.Series(idx, index=idx).groupby([idx.year, idx.month]).last().values
    return f.loc[pd.DatetimeIndex(me)]


def main(argv=None) -> int:
    t0 = time.time()
    d = _closes(TICK)
    d = d.reindex(d["^GSPC"].dropna().index).ffill(limit=5)
    print("Daten:", {c: str(d[c].first_valid_index().date()) for c in d.columns if d[c].notna().any()}, flush=True)
    rep = {"generated": time.strftime("%Y-%m-%d")}
    spx = d["^GSPC"].dropna()
    fs = month_ends(features(spx, d))
    fs = fs[fs.index >= "1990-06-01"]
    rep["S&P 500 · 1990–2007"] = table(fs[fs.index < "2008-01-01"])
    rep["S&P 500 · 2008–heute"] = table(fs[fs.index >= "2008-01-01"])
    r = d[["SPY", "EFA", "EEM"]].pct_change()
    w = (1 + (0.55 * r["SPY"] + 0.35 * r["EFA"] + 0.10 * r["EEM"]).dropna()).cumprod()
    fw = month_ends(features(w, d))
    rep["Welt-Proxy · 2004–heute"] = table(fw[fw.index >= "2004-04-01"])
    # Aktueller Stand jedes Faktors (für die App)
    last = features(spx, d).iloc[-1]
    rep["jetzt"] = {k: (None if pd.isna(v) else (bool(v) if isinstance(v, (bool, np.bool_)) else round(float(v), 4))) for k, v in last.items() if k not in ("f12", "dd12")}
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "etffactors.json").write_text(json.dumps(rep, ensure_ascii=False, separators=(",", ":")))
    print("===BEGIN===")
    print(json.dumps(rep, ensure_ascii=False, separators=(",", ":")))
    print("===END===")
    print(f"fertig in {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
