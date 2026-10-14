"""Ausstieg über 10 Jahre (Tageschart): Tag 20 gegen „unter die EMA schließen“ und Verwandte.

Gegenprobe zum 4H-Ausstiegs-Test (h4study --exits, nur ~3 Jahre): dieselben Kairo-Treffer der beiden 10-Jahres-Stichproben
(kurz-*-Artefakte), Kauf in der Seitwärtsphase wie live, nur die Ausstiegsregel variiert. Netto je Trade (Aktie) in R,
getrennt nach Lernjahren (bis 2023) und Prüfjahren (2024–26), dazu das Depot wie die Strategie (3.000 €, 0,99 € je Order,
5 Plätze, 1 % Risiko, kleinster passender Hebel, ruhigste zuerst; Median aus 7 Reihenfolgen).

    python -m backend.exitstudy10 k1 k2
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import time

import numpy as np

from .capstudy import run
from .config import ROOT
from .shortswing import QRULE, simulate
from .volstudy import _hits

RULES = {"Tag 20 (heute)": {"hold": 20}, "Tag 30": {"hold": 30}, "Tag 40": {"hold": 40},
         "EMA20 ab Tag 10 · max 40": {"hold": 40, "ema_x": 20, "ema_from": 10},
         "EMA20 ab Tag 10 · max 30": {"hold": 30, "ema_x": 20, "ema_from": 10},
         "EMA20 ab Tag 5 · max 40": {"hold": 40, "ema_x": 20, "ema_from": 5},
         "EMA20 ab Tag 15 · max 40": {"hold": 40, "ema_x": 20, "ema_from": 15},
         "EMA20 ab Tag 10 · max 50": {"hold": 50, "ema_x": 20, "ema_from": 10},
         "Einstand ab +1 R · Tag 20": {"hold": 20, "be": 1.0}}
# Indikator-Ausstiege im Tageschart (--ind): sofort / ab Tag 10 / ab +1 R / ab +2 R, höchstens 20 bzw. 40 Tage
IND = {"Tag 20 (heute)": {"hold": 20}, "Tag 40": {"hold": 40}, "EMA20 ab Tag 10 · max 40": {"hold": 40, "ema_x": 20, "ema_from": 10}}
for _k, _n in (("rsi", "RSI≥70 dreht"), ("macd", "MACD kreuzt runter"), ("mbi", "rotes MBI-X"), ("2v3", "2 von 3"), ("3v3", "3 von 3")):
    for _gn, _g in (("sofort", None), ("ab Tag 10", ("day", 10)), ("ab +1R", ("R", 1.0)), ("ab +2R", ("R", 2.0))):
        for _mx in (20, 40):
            IND[f"{_n} {_gn} · max {_mx}"] = {"hold": _mx, "ind_x": _k, "ind_gate": _g}
# Googles Vorschläge (--google): Fibonacci-Ziele, altes Hoch, Extensions, Split-Ausstieg, ATR-Puffer beim Stop
GOOGLE = {"Tag 20 (heute)": {"hold": 20}, "EMA20 ab Tag 10 · max 40": {"hold": 40, "ema_x": 20, "ema_from": 10},
          "TP 61,8 % Fibonacci · sonst Tag 20": {"hold": 20, "tgt": ("fib", 0.618)},
          "TP altes Hoch (100 %) · sonst Tag 20": {"hold": 20, "tgt": ("hi",)},
          "TP 127,2 % Extension · sonst Tag 40": {"hold": 40, "tgt": ("fib", 1.272)},
          "TP 161,8 % Extension · sonst Tag 40": {"hold": 40, "tgt": ("fib", 1.618)},
          "Split: ½ am alten Hoch, Rest Einstand + Tag 20": {"hold": 20, "part": (0.5, ("hi",)), "be_after_part": True},
          "Split: ½ am alten Hoch, Rest Einstand + EMA20 (max 40)": {"hold": 40, "part": (0.5, ("hi",)), "be_after_part": True, "ema_x": 20, "ema_from": 1},
          "Split: ½ bei 61,8 %, Rest Einstand + EMA20 (max 40)": {"hold": 40, "part": (0.5, ("fib", 0.618)), "be_after_part": True, "ema_x": 20, "ema_from": 1},
          "Split: ½ am alten Hoch, Rest Einstand + EMA20 ab Tag 10": {"hold": 40, "part": (0.5, ("hi",)), "be_after_part": True, "ema_x": 20, "ema_from": 10},
          "Stop mit 1 ATR Puffer · Tag 20": {"hold": 20, "buf": 1.0, "maxd": 4.5},
          "Stop mit 1,5 ATR Puffer · Tag 20": {"hold": 20, "buf": 1.5, "maxd": 4.5},
          "Stop mit 2 ATR Puffer · Tag 20": {"hold": 20, "buf": 2.0, "maxd": 4.5}}


def rows_for(hits: list[dict], rule: dict) -> list[dict]:
    rows = []
    for e in hits:
        if len(e["px"]["c"]) < 60:                  # genug Verlauf für jede Regel (gleiche Trades überall)
            continue
        var = {}
        px = e["px"]
        dd = (e.get("f") or {}).get("dd")
        if dd and 0 < dd < 0.95 and "H" not in px:     # Hoch vor der Korrektur und Korrekturtief (relativ zum Signaltag)
            px = {**px, "H": 1 / (1 - dd), "L": min(px["pl"])}
        for L in (1, 2, 3, 5, 10):
            sm = simulate(px, {**QRULE, **rule, "levs": [L], "kob": 1.0})
            if sm and "skip" not in sm and sm["lev"] == L:
                var[L] = sm
        if var:
            sm0 = var.get(1) or next(iter(var.values()))
            d_in = str(dt.date.fromisoformat(e["d"]) + dt.timedelta(days=int((sm0["s"] + 1) * 7 / 5)))
            rows.append({"d": d_in, "sd": e["d"], "sm": sm0, "var": var, "rk": 0.01, "prio": -((e.get("f") or {}).get("atrp") or 1),
                         "r1": var[1]["net"] if 1 in var else None, "days": sm0["d"]})
    return rows


def per_trade(rows: list[dict]) -> dict:
    r = np.array([x["r1"] for x in rows if x["r1"] is not None])
    if not len(r):
        return {"n": 0}
    return {"n": int(len(r)), "r": round(float(r.mean()), 3), "gewinner": round(float((r > 0).mean()), 3),
            "tage": round(float(np.mean([x["days"] for x in rows])), 1)}


def main(argv=None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    rules = GOOGLE if "--google" in argv else IND if "--ind" in argv else RULES
    dirs = [a for a in argv if not a.startswith("--")] or ["k1", "k2"]
    t0 = time.time()
    hits = {d: _hits(d) for d in dirs}
    rep = {"generated": time.strftime("%Y-%m-%d"), "regeln": {}}
    for name, rule in rules.items():
        rep["regeln"][name] = {}
        for d, h in hits.items():
            rows = rows_for(h, rule)
            lern = [x for x in rows if x["sd"] < "2024-01-01"]
            pruef = [x for x in rows if x["sd"] >= "2024-01-01"]
            rep["regeln"][name][d] = {"alle": per_trade(rows), "lern": per_trade(lern), "pruef": per_trade(pruef),
                                      "depot": run(rows, 3000, 0.99, 5) if rows else {"cagr": None, "mdd": None}, "depot_pruef": run(pruef, 3000, 0.99, 5) if pruef else None}
        print(name, {d: (v["alle"].get("r"), v["lern"].get("r"), v["pruef"].get("r"), v["depot"]["cagr"], v["depot"]["mdd"])
                     for d, v in rep["regeln"][name].items()}, flush=True)
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "exitstudy10.json").write_text(json.dumps(rep, ensure_ascii=False, separators=(",", ":")))
    print("===BEGIN===")
    print(json.dumps(rep, ensure_ascii=False, separators=(",", ":")))
    print("===END===")
    print(f"fertig in {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
