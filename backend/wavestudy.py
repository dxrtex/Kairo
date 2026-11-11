"""Wellenstudie: Welche Grenze für den „fast vollen Rücksetzer“ bestimmt die kleine Fibonacci-Welle am besten?

Hintergrund (Jonny, TSMC 11/2026): Kairo beginnt die kleine Welle an dem Tief, vor dem ein Rücksetzer von mindestens
78,6 % lag – ein flacherer Rücksetzer gilt als Zwischentief. Getestet werden die Grenzen 0,5 / 0,618 / 0,706 / 0,786
(heute) / 0,886, jeweils mit der ECHTEN Chart-Logik aus site/index.html (tools/wave_js.mjs), für jede Aktie gleich.

Messung ohne Blick in die Zukunft: An Stichtagen (alle 10 Handelstage) wird die Welle nur aus den Kursen bis zum Stichtag
bestimmt. Danach wird das tatsächliche Korrekturtief gesucht (tiefster Kurs nach dem Hoch, bis der Kurs die Hälfte des
Welle (ein Viertel ihrer Höhe) zurückholt oder ein neues Hoch macht) und als Rücksetzer-Tiefe r der jeweiligen Welle ausgedrückt.
Gute Welle = der Markt dreht auffällig oft im Golden Pocket (0,706–0,79):
  - Dichte-Faktor: Anteil der Wenden im Golden Pocket je 0,01 Tiefe ÷ dasselbe in den Nachbarbereichen (0,618–0,706, 0,79–0,886).
    1,0 = Zufall, > 1 = der Markt respektiert die Zone.
  - Haltequote: Wenn der Kurs den Golden Pocket erreicht (r ≥ 0,706) – wie oft hält er dort (r ≤ 0,79) bzw. über 0,886?
  - Paarvergleich: nur Fälle, in denen die Grenze eine ANDERE Welle liefert als heute – welche trifft öfter?
Lernjahre (bis 2023) und Prüfjahre (ab 2024) getrennt. Ändert nichts an Scan, Signalen oder App.

    python -m backend.wavestudy --shard 0 --shards 40      # Teil rechnen (lädt Kurse)
    python -m backend.wavestudy --report ordner             # Auswertung aller wave_part_*.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from .config import CONFIG, ROOT
from .indicators import pivot_highs, pivot_lows

THRS = [0.5, 0.618, 0.706, 0.786, 0.886]
BASE = THRS.index(0.786)
MODE = "cls"   # „big“: große Welle, heute (0) gegen Variante „nächste ungebrochene ältere Welle“ (1)
EVERY, START, WIN, FWD = 10, 300, 420, 250
BANDS = [(0.0, 0.5), (0.5, 0.618), (0.618, 0.706), (0.706, 0.79), (0.79, 0.886), (0.886, 1.0), (1.0, 99.0)]


def scan_wave(h: np.ndarray, l: np.ndarray, i: int):
    """Swing-High H und Fib-Tief L wie im Scanner (backend/scanner.py 2.2/2.3), nur mit Kursen bis Index i."""
    cc, fz, pl = CONFIG.correction, CONFIG.fib, CONFIG.pivots.pivot_len
    lo = max(0, i + 1 - WIN)
    hh, ll = h[lo:i + 1], l[lo:i + 1]
    m = len(hh)
    import pandas as pd
    ph = pivot_highs(pd.Series(hh), pl)
    cand = [k for k in ph if cc.swing_high_min_age <= m - 1 - k <= cc.swing_high_max_age]
    if not cand:
        return None
    hI = max(cand, key=lambda k: hh[k])
    pv = pivot_lows(pd.Series(ll), pl)
    before = [k for k in pv if hI - fz.impulse_lookback <= k < hI]
    if not before:
        return None
    lI = min(before, key=lambda k: ll[k])
    return hI + lo, lI + lo


def outcome(h, l, c, iL: int, iH: int, i: int) -> float | None:
    """Rücksetzer-Tiefe r des tatsächlichen Korrekturtiefs nach dem Hoch (None = noch offen/ungeeignet)."""
    H, L = h[iH], l[iL]
    if not (H > L) or iH > i - 3:
        return None
    if MODE != "big" and c[i] < H - 0.5 * (H - L):   # klassisch: Korrektur am Stichtag noch nicht über 50 %
        return None
    m0 = float(np.nanmin(l[iH + 1:i + 1])) if i > iH else np.inf
    m = m0
    for k in range(i + 1, min(len(c), i + 1 + FWD)):
        if np.isnan(l[k]):
            continue
        m = min(m, l[k])
        if h[k] > H or c[k] >= m + 0.25 * (H - L):   # echte Wende: Rückprall ≥ ¼ der Welle oder neues Hoch
            # große Welle: das Wendetief muss NACH dem Stichtag liegen (sonst wäre es schon bekannt)
            return None if MODE == "big" and not m < m0 else float((H - m) / (H - L))
    return None


def run_shard(shard: int, shards: int, n_max: int, period: str) -> int:
    from .data_provider import YFinanceProvider
    from .universe import load as load_universe
    tickers = list(load_universe()["ticker"])[:n_max][shard::shards]
    data = YFinanceProvider().history(tickers, period)
    print(f"Shard {shard}: {len(data)} von {len(tickers)} Aktien geladen", flush=True)
    rows, t0 = [], time.time()
    for tk, df in data.items():
        if len(df) < START + 60:
            continue
        T = [str(d.date()) for d in df.index]
        o, h, l, c = (df[k].to_numpy(dtype=float) for k in ("Open", "High", "Low", "Close"))
        samples = []
        for i in range(START, len(df) - 1, EVERY):
            sw = scan_wave(h, l, i)
            if sw:
                samples.append({"i": i, "H": T[sw[0]], "L": T[sw[1]]})
        if not samples:
            continue
        clean = lambda a: [None if np.isnan(x) else round(float(x), 4) for x in a]
        inp = {"t": T, "o": clean(o), "h": clean(h), "l": clean(l), "c": clean(c), "samples": samples, "thrs": THRS, "mode": MODE}
        try:
            res = json.loads(subprocess.run(["node", str(ROOT / "tools" / "wave_js.mjs")], input=json.dumps(inp),
                                            capture_output=True, text=True, timeout=600, check=True).stdout)
        except Exception as e:
            print(f"{tk}: Fehler {e}", flush=True)
            continue
        for s, ws in zip(samples, res):
            w = []
            for x in ws:
                w.append(None if x is None else [T[x[0]], T[x[1]], outcome(h, l, c, x[0], x[1], s["i"]),
                                                 round(float((h[x[1]] - l[x[0]]) / l[x[0]]), 3)])
            rows.append({"tk": tk, "d": T[s["i"]], "w": w})
    print(f"Shard {shard}: {len(rows)} Stichtage in {time.time() - t0:.0f} s", flush=True)
    Path(f"wave_part_{shard}.json").write_text(json.dumps(rows, separators=(",", ":")))
    return 0


def _metrics(rs: list[float], seed: int = 7) -> dict:
    if not rs:
        return {"n": 0}
    r = np.array(rs)
    share = lambda a, b: float(((r >= a) & (r < b)).mean())
    gp, nb = share(0.706, 0.79), share(0.618, 0.706) + share(0.79, 0.886)
    reach = r >= 0.706
    out = {"n": int(len(r)),
           "baender": {f"{a:g}–{b:g}" if b < 99 else f"über {a:g}": round(share(a, b), 3) for a, b in BANDS},
           "golden_pocket": round(gp, 3),
           "dichte_faktor": round((gp / 0.084) / (nb / 0.184), 2) if nb > 0 else None,
           "erreicht_gp": round(float(reach.mean()), 3),
           "haelt_im_gp": round(float((r[reach] <= 0.79).mean()), 3) if reach.any() else None,
           "haelt_ueber_0886": round(float((r[reach] <= 0.886).mean()), 3) if reach.any() else None}
    if len(r) >= 30:
        rng = np.random.default_rng(seed)
        bs = [float(((x >= 0.706) & (x < 0.79)).mean()) for x in (rng.choice(r, len(r)) for _ in range(500))]
        out["gp_bereich90"] = [round(float(np.percentile(bs, 5)), 3), round(float(np.percentile(bs, 95)), 3)]
    return out


def _split(items: list[tuple[str, float]]) -> dict:
    return {"alle": _metrics([r for _, r in items]),
            "lern_bis_2023": _metrics([r for d, r in items if d < "2024-01-01"]),
            "pruef_ab_2024": _metrics([r for d, r in items if d >= "2024-01-01"])}


def report(dirs: list[str]) -> int:
    rows = []
    for d in dirs:
        for p in sorted(Path(d).glob("wave_part_*.json")):
            rows += json.loads(p.read_text())
    rep = {"generated": time.strftime("%Y-%m-%d"), "stichtage": len(rows), "aktien": len({r["tk"] for r in rows}),
           "zeitraum": [min((r["d"] for r in rows), default=None), max((r["d"] for r in rows), default=None)],
           "grenzen": {}, "paarvergleich_zu_0786": {}}
    for k, thr in enumerate(THRS):
        seen, items = set(), []
        for r in rows:
            w = r["w"][k] if len(r["w"]) > k else None
            if not w or w[2] is None or (r["tk"], w[0], w[1]) in seen:
                continue
            seen.add((r["tk"], w[0], w[1]))
            items.append((r["d"], w[2]))
        rep["grenzen"][f"{thr:g}"] = {"wellen": len(items), **_split(items)}
        if k == BASE:
            continue
        seen, a, b = set(), [], []
        for r in rows:
            w0, w1 = r["w"][BASE], r["w"][k]
            if not w0 or not w1 or w0[2] is None or w1[2] is None or w0[:2] == w1[:2]:
                continue
            key = (r["tk"], *w0[:2], *w1[:2])
            if key in seen:
                continue
            seen.add(key)
            a.append((r["d"], w0[2]))
            b.append((r["d"], w1[2]))
        gp = lambda xs: round(float(np.mean([0.706 <= x < 0.79 for _, x in xs])), 3) if xs else None
        rep["paarvergleich_zu_0786"][f"{thr:g}"] = {
            "abweichende_faelle": len(a), "gp_treffer_heute_0786": gp(a), f"gp_treffer_{thr:g}": gp(b),
            "heute_0786": _split(a), f"grenze_{thr:g}": _split(b)}
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "wavestudy.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    print("===BEGIN===")
    print(json.dumps(rep, ensure_ascii=False, separators=(",", ":")))
    print("===END===")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--n", type=int, default=1600)
    ap.add_argument("--period", default="10y")
    ap.add_argument("--report", nargs="*")
    ap.add_argument("--mode", default="cls")
    a = ap.parse_args(argv)
    global MODE, THRS, BASE
    MODE = a.mode
    if MODE in ("big", "clsab"):
        THRS, BASE = [0, 1], 0
    if a.report is not None:
        return report(a.report or ["."])
    return run_shard(a.shard, a.shards, a.n, a.period)


if __name__ == "__main__":
    sys.exit(main())
