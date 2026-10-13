"""Fast-Treffer-Test: Sind Setups mit 9/11 oder 10/11 Kairo-Kriterien genauso gut wie volle Treffer (11/11)?

10-Jahres-Stichproben (kurz-*-Artefakte): volle Treffer, Fast-Treffer (genau ein Kriterium fehlt, mit Angabe welches)
und zufällige Vergleichstage mit Anzahl erfüllter Kriterien (≥ 9/11, ≤ 8/11). Alle mit denselben Regeln wie die
Strategie (Kauf in der 5-Tage-Seitwärtsphase, Stop, 20 Tage), netto in R; Depot wie die Studie (1 % Risiko, 5 Plätze,
kleinster Hebel, ruhigste zuerst). Lernjahre bis 2023 und Prüfjahre 2024–26 getrennt.

    python -m backend.nearstudy k1 k2
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

from .capstudy import rows_for, run
from .config import ROOT


def load(d: str) -> list[dict]:
    seen, out = set(), []
    for p in sorted(Path(d).glob("bilanz_part_*.json")):
        for e in json.loads(p.read_text()):
            if e.get("px") and e["px"].get("wd") and (e["t"], e["d"], e["k"]) not in seen:
                seen.add((e["t"], e["d"], e["k"]))
                out.append(e)
    return out


def groups(es: list[dict]) -> dict:
    met = lambda e: (e.get("f") or {}).get("met")
    g = {"11/11 voll": [e for e in es if e["k"] == "hit"],
         "10/11 Fast-Treffer": [e for e in es if e["k"] == "fast"],
         "10–11/11 zufällige Tage": [e for e in es if e["k"] == "base" and (met(e) or 0) >= 10],
         "9/11 zufällige Tage": [e for e in es if e["k"] == "base" and met(e) == 9],
         "8/11 zufällige Tage": [e for e in es if e["k"] == "base" and met(e) == 8],
         "≤ 7/11 zufällige Tage": [e for e in es if e["k"] == "base" and met(e) is not None and met(e) <= 7]}
    for e in es:                                       # Fast-Treffer nach fehlendem Kriterium
        if e["k"] == "fast" and e.get("miss"):
            g.setdefault(f"10/11 ohne „{e['miss'][0]}“", []).append(e)
    return g


def per_trade(rows: list[dict]) -> dict:
    r = np.array([x["var"][1]["net"] for x in rows if 1 in x["var"]])
    if not len(r):
        return {"n": 0}
    return {"n": int(len(r)), "r": round(float(r.mean()), 3), "gewinner": round(float((r > 0).mean()), 3),
            "top5_anteil": round(float(np.sort(r)[-5:].sum() / r[r > 0].sum()), 3) if (r > 0).any() else None}


def main(argv=None) -> int:
    dirs = (argv if argv is not None else sys.argv[1:]) or ["k1", "k2"]
    t0 = time.time()
    rep = {"generated": time.strftime("%Y-%m-%d"), "gruppen": {}}
    for d in dirs:
        es = load(d)
        print(d, len(es), "Einträge", flush=True)
        out = {}
        for name, g in groups(es).items():
            if len(g) < 40:
                continue
            rows = rows_for(g, 0.01)
            lern = [x for x in rows if x["d"] < "2024-01-01"]
            pruef = [x for x in rows if x["d"] >= "2024-01-01"]
            out[name] = {"signale": len(g), "trade": per_trade(rows), "lern": per_trade(lern), "pruef": per_trade(pruef),
                         "depot": run(rows, 3000, 0.99, 5, seeds=5) if len(rows) >= 100 and not name.endswith("Tage") else None}
            print(d, name, json.dumps(out[name], ensure_ascii=False), flush=True)
        rep["gruppen"][d] = out
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "nearstudy.json").write_text(json.dumps(rep, ensure_ascii=False, separators=(",", ":")))
    print("===BEGIN===")
    print(json.dumps(rep, ensure_ascii=False, separators=(",", ":")))
    print("===END===")
    print(f"fertig in {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
