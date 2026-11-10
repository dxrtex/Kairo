"""Fibonacci-Zonen-Studie: Welche Rücksetzer-Tiefe bringt mit der Kairo-Regel (B60) am meisten?

Grundlage: Signal-Dateien des Bilanz-Backtests (`python -m backend.bilanz --px-base`, mit KAIRO_PX_HOLD=75), die je Signal
die Fibonacci-Messwerte am Signaltag (f.fib: Retracement, Impuls, in der Zone, Unterstützung) und den Kursverlauf danach
mitbringen. Jeder Trade wird exakt wie live gespielt (backend/rule.py, Version B60): bis zu 10 Tage auf die
Seitwärtsphase warten, Kauf zur Eröffnung, Stop = Basis-Tief − 0,25 ATR, ab Tag 10 Ausstieg bei Schluss unter der
EMA 20 (Verkauf zur nächsten Eröffnung), spätestens Tag 60. Ergebnis netto in R (nach Spread und Gebühr, Aktie ohne Hebel).

Fragen:
  1. Treffer (11/11) nach Art der Zone: nur Fibonacci, nur Unterstützung, beides.
  2. Treffer nach Rücksetzer-Tiefe (Retracement) – trägt der „Golden Pocket“ (0,706–0,79)?
  3. Fast-Treffer, denen NUR die Zone fehlte, nach Tiefe – würde eine breitere Zone (0,5 oder bis 0,886) gute Trades bringen?
  4. Zufällige Tage mit ≥ 9/11 Kriterien nach Tiefe – breite Gegenprobe.
  5. Treffer nach Impulsgröße.
Lernjahre (bis 2023) und Prüfjahre (ab 2024) getrennt; nur was in beiden hält, zählt. 90-%-Bereich per Bootstrap.
Die Scan-Regel wird hier NICHT geändert – die Studie liefert nur die Entscheidungsgrundlage.

    python -m backend.fibstudy ordner_mit_bilanz_part_*.json
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

from .config import ROOT
from .rule import KAIRO
from .shortswing import QRULE, simulate

RULE = {**QRULE, "wait": KAIRO["wait"], "ck": KAIRO["ck"], "cm": KAIRO["cm"], "inv": KAIRO["inv"], "buf": KAIRO["buf"],
        "maxd": KAIRO["risk_atr"][1], "hold": KAIRO["hold"], "ema_x": KAIRO["ema"], "ema_from": KAIRO["ema_from"], "levs": [1]}
BUCKETS = [(0.0, 0.382), (0.382, 0.5), (0.5, 0.618), (0.618, 0.706), (0.706, 0.79), (0.79, 0.886), (0.886, 1.0), (1.0, 9.0)]
IMP = [(0.15, 0.3), (0.3, 0.6), (0.6, 1.2), (1.2, 99.0)]


def load(dirs: list[str]) -> list[dict]:
    seen, out = set(), []
    for d in dirs:
        for p in sorted(Path(d).glob("bilanz_part_*.json")):
            for e in json.loads(p.read_text()):
                if e.get("px") and (e["t"], e["d"], e["k"]) not in seen:
                    seen.add((e["t"], e["d"], e["k"]))
                    out.append(e)
    return out


def trade(e: dict):
    try:
        sm = simulate(e["px"], RULE)
    except Exception:
        return None
    return None if not sm or "skip" in sm else sm


def stats(rows: list[tuple[dict, dict]], seed: int = 7) -> dict:
    if not rows:
        return {"n": 0}
    net = np.array([sm["net"] for _, sm in rows])
    wins, loss = net[net > 0], net[net <= 0]
    rng = np.random.default_rng(seed)
    bs = [float(rng.choice(net, len(net)).mean()) for _ in range(1000)] if len(net) >= 10 else []
    out = {"n": int(len(net)), "netto_R": round(float(net.mean()), 3), "median_R": round(float(np.median(net)), 3),
           "treffer_quote": round(float((net > 0).mean()), 3),
           "profit_faktor": round(float(wins.sum() / -loss.sum()), 2) if loss.sum() < 0 else None,
           "tage": round(float(np.mean([sm["d"] for _, sm in rows])), 1)}
    if bs:
        out["bereich90"] = [round(float(np.percentile(bs, 5)), 3), round(float(np.percentile(bs, 95)), 3)]
    return out


def split(rows):
    lern = [x for x in rows if x[0]["d"] < "2024-01-01"]
    pruef = [x for x in rows if x[0]["d"] >= "2024-01-01"]
    return {"alle": stats(rows), "lern_bis_2023": stats(lern), "pruef_ab_2024": stats(pruef)}


def bucket_label(lo, hi):
    f = lambda x: f"{x:.3f}".rstrip("0").rstrip(".").replace(".", ",")
    return f"{f(lo)}–{f(hi)}" if hi < 9 else f"über {f(lo)}"


def main(argv=None) -> int:
    dirs = (argv if argv is not None else sys.argv[1:]) or ["."]
    t0 = time.time()
    ev = load(dirs)
    print(f"{len(ev)} Ereignisse geladen", flush=True)
    fib = lambda e: ((e.get("f") or {}).get("fib")) or None
    rows = []
    for e in ev:
        sm = trade(e)
        if sm:
            rows.append((e, sm))
    print(f"{len(rows)} Trades nach der Regel B60 ({time.time() - t0:.0f} s)", flush=True)
    hits = [x for x in rows if x[0]["k"] == "hit"]
    fast_zone = [x for x in rows if x[0]["k"] == "fast" and x[0].get("miss") == ["zone"]]
    base9 = [x for x in rows if x[0]["k"] == "base" and ((x[0].get("f") or {}).get("met") or 0) >= 9]
    rep = {"generated": time.strftime("%Y-%m-%d"), "regel": "B60 (backend/rule.py)", "ereignisse": len(ev), "trades": len(rows),
           "zeitraum": [min((e["d"] for e in ev), default=None), max((e["d"] for e in ev), default=None)],
           "aktien": len({e["t"] for e in ev})}
    rep["1_treffer_alle"] = split(hits)
    has = lambda x: fib(x[0]) is not None
    rep["1_treffer_nach_zone"] = {
        "nur Fibonacci": split([x for x in hits if has(x) and fib(x[0])["ok"] and not fib(x[0])["sup"]]),
        "nur Unterstützung": split([x for x in hits if not (has(x) and fib(x[0])["ok"]) and (not has(x) or fib(x[0])["sup"])]),
        "beides": split([x for x in hits if has(x) and fib(x[0])["ok"] and fib(x[0])["sup"]]),
        "Golden Pocket (0,706–0,79)": split([x for x in hits if has(x) and fib(x[0])["ok"] and fib(x[0])["core"]]),
    }
    def by_ret(rs):
        out = {}
        for lo, hi in BUCKETS:
            sel = [x for x in rs if has(x) and fib(x[0])["ret"] is not None and lo <= fib(x[0])["ret"] < hi]
            if sel:
                out[bucket_label(lo, hi)] = split(sel)
        return out
    rep["2_treffer_nach_tiefe"] = by_ret(hits)
    rep["3_fast_nur_zone_fehlt_nach_tiefe"] = by_ret(fast_zone)
    rep["4_zufallstage_ab_9_nach_tiefe"] = by_ret(base9)
    rep["5_treffer_nach_impuls"] = {f"{int(lo * 100)}–{int(hi * 100)} %" if hi < 99 else f"über {int(lo * 100)} %":
                                    split([x for x in hits if has(x) and fib(x[0])["imp"] is not None and lo <= fib(x[0])["imp"] < hi])
                                    for lo, hi in IMP}
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "fibstudy.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    print("===BEGIN===")
    print(json.dumps(rep, ensure_ascii=False, separators=(",", ":")))
    print("===END===")
    print(f"fertig in {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
