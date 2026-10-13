"""Kapital-Test: Wie viel bleibt von der Kairo-Strategie bei kleinem Trading-Kapital nach Gebühren?

Gleiche Treffer und Regeln wie der 10-Jahres-Test (1 % Risiko, ruhigste zuerst, kleinster passender Hebel, 20 Tage),
nur Startkapital, Gebühr je Order, Zahl der Plätze und Risiko variiert. Median aus mehreren Reihenfolgen.

    python -m backend.capstudy k1 k2
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import time

import numpy as np

from .config import ROOT
from .shortswing import QRULE, _depot_real, simulate
from .volstudy import _hits


def rows_for(hits: list[dict], rk: float) -> list[dict]:
    rows = []
    for e in hits:
        if len(e["px"]["c"]) < 30:
            continue
        var = {}
        for L in (1, 2, 3, 5, 10):
            sm = simulate(e["px"], {**QRULE, "hold": 20, "levs": [L], "kob": 1.0})
            if sm and "skip" not in sm and sm["lev"] == L:
                var[L] = sm
        if var:
            sm0 = next(iter(var.values()))
            d_in = str(dt.date.fromisoformat(e["d"]) + dt.timedelta(days=int((sm0["s"] + 1) * 7 / 5)))
            rows.append({"d": d_in, "sm": sm0, "var": var, "rk": rk, "prio": -((e.get("f") or {}).get("atrp") or 1)})
    return rows


def run(rows, start, fee, slots, seeds=7):
    res = []
    for sd in range(seeds):
        r = _depot_real(rows, start=start, max_open=slots, seed=sd, fee_eur=fee)
        if r:
            res.append(r)
    res.sort(key=lambda r: r["cagr"])
    m = res[len(res) // 2]
    return {"cagr": m["cagr"], "mdd": m["mdd_daily"], "trades": m["trades"], "ende": m["end"],
            "trades_pa": round(m["trades"] / max(1, len(m["years"])), 1)}


def main(argv=None) -> int:
    dirs = (argv if argv is not None else sys.argv[1:]) or ["k1", "k2"]
    t0 = time.time()
    hits = {d: _hits(d) for d in dirs}
    rep = {"generated": time.strftime("%Y-%m-%d"), "varianten": {}}
    for rk in (0.01, 0.02):
        rows = {d: rows_for(h, rk) for d, h in hits.items()}
        for start in (900, 1500, 3000, 10000):
            for fee in (0.99, 0.0):
                for slots in (3, 5):
                    if rk == 0.02 and start > 1500:
                        continue
                    key = f"{start} € · {'0,99 €' if fee else '0 €'} je Order · {slots} Plätze · {int(rk * 100)} % Risiko"
                    rep["varianten"][key] = {d: run(r, start, fee, slots) for d, r in rows.items()}
                    print(key, {d: (v["cagr"], v["mdd"], v["trades_pa"]) for d, v in rep["varianten"][key].items()}, flush=True)
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "capstudy.json").write_text(json.dumps(rep, ensure_ascii=False, separators=(",", ":")))
    print("===BEGIN===")
    print(json.dumps(rep, ensure_ascii=False, separators=(",", ":")))
    print("===END===")
    print(f"fertig in {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
