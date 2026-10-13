"""Volumen-Test für Kairo-Treffer: Laufen Treffer mit hohem Volumen am Boden („Smart Money“) besser?

Für jeden vollen Treffer der beiden 10-Jahres-Stichproben (kurz-*-Artefakte) Volumen-Merkmale am Signaltag – nur
Vergangenheit – und das Ergebnis mit den aktuellen Regeln (Kauf in der Seitwärtsphase, Stop, 20 Tage; Aktie, netto, in R).
Merkmale werden in Drittel geteilt (Grenzen nur aus Stichprobe 1, Lernjahre bis 2023); ein Merkmal zählt nur, wenn
es in beiden Stichproben UND in den Prüfjahren 2024–26 in dieselbe Richtung wirkt. Zusätzlich Depot-Rechnung (1 % Risiko,
5 Plätze, ruhigste zuerst, kleinster Hebel) mit und ohne Filter.

    python -m backend.volstudy k1 k2
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .config import ROOT
from .shortswing import QRULE, _depot_real, simulate

FEATS = {"rvol": "Volumen am Signaltag ÷ Ø 50 Tage", "spike10": "höchstes Volumen der letzten 10 Tage ÷ Ø davor",
         "dnvol": "Volumen an roten ÷ grünen Tagen (10 T.)", "mfi": "Money Flow Index (14)", "climax": "Volumen-Climax mit langer Lunte (10 T.)"}


def _hits(d: str) -> list[dict]:
    seen, out = set(), []
    for p in sorted(Path(d).glob("bilanz_part_*.json")):
        for e in json.loads(p.read_text()):
            if e.get("k") == "hit" and e.get("px") and e["px"].get("wd") and (e["t"], e["d"]) not in seen:
                seen.add((e["t"], e["d"]))
                out.append(e)
    return out


def _ohlcv(tickers: list[str], batch: int = 50, pause: float = 4.0) -> dict:
    import yfinance as yf
    out, todo = {}, list(dict.fromkeys(tickers))
    for rnd in range(4):
        failed = []
        for i in range(0, len(todo), batch):
            part = todo[i:i + batch]
            try:
                d = yf.download(part, start="2015-06-01", interval="1d", auto_adjust=False, progress=False, threads=True, group_by="ticker")
                for t in part:
                    try:
                        x = d[t] if isinstance(d.columns, pd.MultiIndex) else d
                        x = x[["Open", "High", "Low", "Close", "Volume"]].dropna()
                        if len(x) > 100:
                            x.index = pd.to_datetime(x.index).tz_localize(None).normalize()
                            out[t] = x
                        else:
                            failed.append(t)
                    except Exception:
                        failed.append(t)
            except Exception as exc:
                print("Download-Fehler", repr(exc)[:120], flush=True)
                failed += part
            time.sleep(pause)
        print(f"Volumen Runde {rnd + 1}: {len(out)} geladen, {len(failed)} fehlen", flush=True)
        if not failed or (len(failed) == len(todo) and rnd > 0):
            break
        todo = failed
        time.sleep(60)
    return out


def feats(df: pd.DataFrame, d: str) -> dict | None:
    i = df.index.searchsorted(pd.Timestamp(d), side="right") - 1
    if i < 70 or str(df.index[i].date()) != d:
        return None
    o, h, l, c, v = (df[k].to_numpy(float) for k in ("Open", "High", "Low", "Close", "Volume"))
    if v[i - 60:i + 1].sum() <= 0:
        return None
    avg50 = v[i - 50:i].mean() or 1
    pre = v[i - 60:i - 10].mean() or 1
    chg = np.diff(c[i - 10:i + 1])
    vv = v[i - 9:i + 1]
    dn, up = vv[chg < 0].sum(), vv[chg > 0].sum()
    tp = (h + l + c) / 3
    mf = tp * v
    w = slice(i - 13, i + 1)
    d_tp = np.diff(tp[i - 14:i + 1])
    pos, neg = mf[w][d_tp > 0].sum(), mf[w][d_tp < 0].sum()
    clim = False
    for j in range(i - 9, i + 1):
        rng = h[j] - l[j]
        if rng > 0 and v[j] >= v[j - 19:j + 1].max() and (min(o[j], c[j]) - l[j]) >= 0.5 * rng:
            clim = True
    return {"rvol": float(v[i] / avg50), "spike10": float(vv.max() / pre), "dnvol": float(dn / up) if up > 0 else 5.0,
            "mfi": float(100 - 100 / (1 + pos / neg)) if neg > 0 else 100.0, "climax": float(clim)}


def rows_for(hits: list[dict], data: dict) -> list[dict]:
    import datetime as dt
    rows = []
    for e in hits:
        if len(e["px"]["c"]) < 30 or e["t"] not in data:
            continue
        f = feats(data[e["t"]], e["d"])
        if f is None:
            continue
        var = {}
        for L in (1, 2, 3, 5, 10):
            sm = simulate(e["px"], {**QRULE, "hold": 20, "levs": [L], "kob": 1.0})
            if sm and "skip" not in sm and sm["lev"] == L:
                var[L] = sm
        if not var:
            continue
        sm0 = var.get(1) or next(iter(var.values()))
        d_in = str(dt.date.fromisoformat(e["d"]) + dt.timedelta(days=int((sm0["s"] + 1) * 7 / 5)))
        rows.append({"d": d_in, "sd": e["d"], "sm": sm0, "var": var, "rk": 0.01, "prio": -((e.get("f") or {}).get("atrp") or 1),
                     "r1": var[1]["net"] if 1 in var else None, **f})
    return rows


def _grp(rows, key, lo, hi):
    out = []
    for name, fn in (("unteres Drittel", lambda x: x < lo), ("mittleres Drittel", lambda x: lo <= x < hi), ("oberes Drittel", lambda x: x >= hi)):
        rs = [r["r1"] for r in rows if r["r1"] is not None and fn(r[key])]
        out.append({"gruppe": name, "n": len(rs), "r": round(float(np.mean(rs)), 3) if rs else None,
                    "gewinner": round(float(np.mean([x > 0 for x in rs])), 3) if rs else None})
    return out


def depot(rows, seeds=5):
    res = []
    for sd in range(seeds):
        r = _depot_real(rows, seed=sd)
        if r:
            res.append((r["cagr"], r.get("mdd_daily")))
    if not res:
        return None
    res.sort(key=lambda x: x[0])
    c, m = res[len(res) // 2]
    return {"cagr": round(float(c), 4), "mdd": None if m is None else round(float(m), 4), "trades": len(rows), "genommen": None}


def main(argv=None) -> int:
    dirs = (argv if argv is not None else sys.argv[1:]) or ["k1", "k2"]
    t0 = time.time()
    sets = {d: _hits(d) for d in dirs}
    for d, h in sets.items():
        print(f"{d}: {len(h)} Treffer", flush=True)
    data = _ohlcv(sorted({e["t"] for h in sets.values() for e in h}))
    rows = {d: rows_for(h, data) for d, h in sets.items()}
    for d, r in rows.items():
        print(f"{d}: {len(r)} Trades mit Volumen", flush=True)
    base = [r for r in rows[dirs[0]] if r["sd"] < "2024-01-01"]
    rep = {"generated": time.strftime("%Y-%m-%d"), "merkmale": FEATS, "faktoren": {}, "depot": {}}
    cuts = {}
    for k in FEATS:
        if k == "climax":
            cuts[k] = (0.5, 0.5)
        else:
            q = np.quantile([r[k] for r in base], [1 / 3, 2 / 3])
            cuts[k] = (float(q[0]), float(q[1]))
    for k, (lo, hi) in cuts.items():
        rep["faktoren"][k] = {"grenzen": [round(lo, 3), round(hi, 3)]}
        for d, rs in rows.items():
            for per, fn in (("lern", lambda r: r["sd"] < "2024-01-01"), ("pruef", lambda r: r["sd"] >= "2024-01-01")):
                rep["faktoren"][k][f"{d}_{per}"] = _grp([r for r in rs if fn(r)], k, lo, hi)
    for d, rs in rows.items():
        dep = {"alle": depot(rs)}
        for k, (lo, hi) in cuts.items():
            if k == "climax":
                dep["nur mit Climax"] = depot([r for r in rs if r[k] >= .5])
                dep["ohne Climax"] = depot([r for r in rs if r[k] < .5])
            else:
                dep[f"{k}: oberes Drittel raus"] = depot([r for r in rs if r[k] < hi])
                dep[f"{k}: unteres Drittel raus"] = depot([r for r in rs if r[k] >= lo])
        rep["depot"][d] = dep
        print(f"Depot {d}: {dep['alle']}", flush=True)
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "volstudy.json").write_text(json.dumps(rep, ensure_ascii=False, separators=(",", ":")))
    print("===BEGIN===")
    print(json.dumps(rep, ensure_ascii=False, separators=(",", ":")))
    print("===END===")
    print(f"fertig in {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
