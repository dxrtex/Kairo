"""Prognose-Bilanz Quartalszahlen: Wie gut lag Kairo? Wöchentlich aus dem eigenen Archiv (earn_archive.json).

Für jede Meldung mit Kursreaktion: gezeigte Wahrscheinlichkeit „steigt am Tag danach“ (p, Stand v) gegen die echte Reaktion.
Ausgabe earn_review.md (für Jonny und Claude) und earn_review.json (für die App):
- Trefferquote und Brier-Score (mittlerer quadratischer Fehler; Münzwurf = 0,25) gesamt, je Stand der Regel und je Ausblick
- Eichung: Wenn Kairo „60–70 %“ sagt – stieg die Aktie dann auch in 60–70 % der Fälle?
- größte Fehlprognosen mit Schlagzeile (Ausblick falsch erkannt?)
- Vorschläge: Gewinn-Stufe × Ausblick, deren echte Quote mit genug Fällen deutlich von der gezeigten abweicht.
Vorschläge werden nicht automatisch übernommen – jede Änderung an der Regel bekommt einen neuen Stand (earnfast.MODEL).

    python tools/earn_review.py <earn_archive.json> <site/earn_stats.json> <out_dir>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

GK = {-1: "gesenkt", 0: "bestätigt", 1: "angehoben"}
MIN_SUGGEST = 30          # so viele Fälle braucht eine Zelle, bevor eine Anpassung vorgeschlagen wird
DIFF_SUGGEST = 0.10       # … und so weit (Prozentpunkte/100) muss die echte Quote abweichen


def frame(arc: dict, stats: dict) -> pd.DataFrame:
    B = stats.get("buckets") or []
    rows = []
    for k, r in arc.items():
        if r.get("r1") is None or r.get("s") is None:
            continue
        t, d = k.split("|", 1)
        b = next((i for i, x in enumerate(B) if x["lo"] <= r["s"] * 100 < x["hi"]), None)
        rows.append({"t": t, "d": d, "s": r["s"], "r1": r["r1"], "y": float(r["r1"] > 0), "p": r.get("p"), "v": r.get("v") or "vor Aufzeichnung",
                     "g": GK.get(r.get("g"), "keine Meldung"), "gt": r.get("gt") or "", "b": b, "bn": B[b]["name"] if b is not None else "?"})
    return pd.DataFrame(rows)


def score(D: pd.DataFrame) -> dict:
    D = D[D["p"].notna()]
    if not len(D):
        return {"n": 0}
    p, y = D["p"].astype(float), D["y"]
    return {"n": int(len(D)), "hit": float(((p > .5) == (y > .5)).mean()), "brier": float(((p - y) ** 2).mean()),
            "coin": float(((0.5 - y) ** 2).mean()), "up": float(y.mean())}


def review(arc_file: str, stats_file: str, out_dir: str) -> dict:
    arc = json.loads(Path(arc_file).read_text(encoding="utf-8"))
    stats = json.loads(Path(stats_file).read_text(encoding="utf-8"))
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    D = frame(arc, stats)
    L = ["# Prognose-Bilanz Quartalszahlen\n"]
    p = L.append
    if not len(D):
        p("Noch keine Meldungen mit Kursreaktion.")
        (out / "earn_review.md").write_text("\n".join(L), encoding="utf-8")
        return {"n": 0}
    S = score(D)
    p(f"{len(D)} Meldungen mit Kursreaktion ({D['d'].min()} bis {D['d'].max()}), davon {S['n']} mit aufgezeichneter Prognose.\n")
    p("| Bereich | n | Richtung getroffen | Brier (kleiner = besser) | Münzwurf |\n|---|---|---|---|---|")
    line = lambda name, s: p(f"| {name} | {s['n']} | {s['hit']:.0%} | {s['brier']:.3f} | {s['coin']:.3f} |") if s.get("n") else None
    line("alle", S)
    for v, g in D.groupby("v"):
        line(f"Stand {v}", score(g))
    for k in ("gesenkt", "bestätigt", "angehoben", "keine Meldung"):
        line(f"Ausblick {k}", score(D[D["g"] == k]))
    P = D[D["p"].notna()].copy()
    if len(P):
        p("\n## Eichung – stimmt die gezeigte Zahl?\n")
        p("| Kairo sagte | n | tatsächlich gestiegen |\n|---|---|---|")
        P["bin"] = pd.cut(P["p"].astype(float), [0, .3, .4, .5, .6, .7, 1.0], include_lowest=True)
        for b, g in P.groupby("bin", observed=True):
            p(f"| {b.left:.0%}–{b.right:.0%} | {len(g)} | {g['y'].mean():.0%} |")
    p("\n## Gewinn × Ausblick – echte Quote (n)\n")
    p("| Gewinn | gesenkt | bestätigt | angehoben | keine Meldung |\n|---|---|---|---|---|")
    sugg = []
    B = stats.get("buckets") or []
    for b in sorted(D["b"].dropna().unique()):
        s = D[D["b"] == b]
        cells = []
        for k in ("gesenkt", "bestätigt", "angehoben", "keine Meldung"):
            x = s[s["g"] == k]
            cells.append(f"{x['y'].mean():.0%} ({len(x)})" if len(x) else "–")
            shown = x["p"].dropna().astype(float).mean() if x["p"].notna().any() else B[int(b)]["up1"]
            if len(x) >= MIN_SUGGEST and abs(x["y"].mean() - shown) >= DIFF_SUGGEST:
                sugg.append(f"{B[int(b)]['name']} + Ausblick {k}: gezeigt Ø {shown:.0%}, tatsächlich {x['y'].mean():.0%} (n {len(x)})")
        p(f"| {B[int(b)]['name']} | " + " | ".join(cells) + " |")
    p("\n## Vorschläge zur Anpassung\n")
    p("\n".join(f"- {x}" for x in sugg) if sugg else f"- keine (Zellen brauchen ≥ {MIN_SUGGEST} Fälle und ≥ {DIFF_SUGGEST:.0%} Abweichung)")
    p("\n## Größte Fehlprognosen (zum Nachprüfen der Ausblick-Erkennung)\n")
    if len(P):
        P["miss"] = (P["p"].astype(float) - P["y"]).abs() * P["r1"].abs()
        for r in P.sort_values("miss", ascending=False).head(15).itertuples():
            p(f"- {r.t} {r.d}: Kairo {float(r.p):.0%} steigt, Kurs {r.r1:+.1%} · Gewinn {r.s:+.0%} · Ausblick {r.g}" + (f" – „{r.gt}“" if r.gt else ""))
    (out / "earn_review.md").write_text("\n".join(L), encoding="utf-8")
    res = {"n": S["n"], "hit": S.get("hit"), "brier": S.get("brier"), "since": str(D["d"].min()), "suggest": sugg}
    (out / "earn_review.json").write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    return res


if __name__ == "__main__":
    print(json.dumps(review(*sys.argv[1:4]), ensure_ascii=False, indent=1))
