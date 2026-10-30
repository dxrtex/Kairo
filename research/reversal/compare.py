"""Alt-gegen-Neu-Vergleich der Depot-Läufe nach den Engine-Korrekturen (Code-Review 30.10.2026).

Liest depot_<Variante>_<Raster>.json aus zwei Verzeichnissen (alte Engine / korrigierte Engine) und schreibt eine Tabelle
mit CAGR und max. Rückgang je Abschnitt sowie die Rangfolge der Varianten vorher/nachher.

    python -m research.reversal.compare --old OLD --new NEW --title "..." --out vergleich.md
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ABS = ("Validierung", "Holdout", "gesamt")


def load(d: Path) -> dict:
    out = {}
    for f in sorted(d.glob("depot_*_*.json")):
        _, v, lay = f.stem.split("_", 2)
        out[(v, lay)] = json.loads(f.read_text())
    return out


def val(r: dict | None, key: str, ab: str, k: str = "cagr"):
    s = (r or {}).get(key, {}).get(ab) or {}
    return s.get(k)


def fmt(x, f="{:+.1%}"):
    return f.format(x) if x is not None else "–"


def compare(old: dict, new: dict, title: str) -> str:
    L = [f"# {title}\n", "Stress-Kosten. Δ = neu − alt in Prozentpunkten CAGR.\n"]
    keys = sorted(set(old) & set(new), key=lambda k: (k[1], k[0]))
    caps = sorted({int(k.split("_")[0]) for r in new.values() for k in r if k.endswith("_stress")})
    for lay in sorted({k[1] for k in keys}):
        L.append(f"\n## Raster {lay}\n")
        L.append("| Kapital | Variante | " + " | ".join(f"{ab} alt | {ab} neu | Δ" for ab in ABS) + " | max. Rückgang alt / neu |")
        L.append("|---|---|" + "---|---|---|" * len(ABS) + "---|")
        for c in caps:
            for v, _ in [k for k in keys if k[1] == lay]:
                o, n, key = old[(v, lay)], new[(v, lay)], f"{c}_stress"
                cells = []
                for ab in ABS:
                    a, b = val(o, key, ab), val(n, key, ab)
                    cells += [fmt(a), fmt(b), f"{(b - a) * 100:+.2f}" if a is not None and b is not None else "–"]
                L.append(f"| {c} € | {v} | " + " | ".join(cells) + f" | {fmt(val(o, key, 'gesamt', 'max_dd'), '{:.0%}')} / "
                         f"{fmt(val(n, key, 'gesamt', 'max_dd'), '{:.0%}')} |")
        L.append("\nRangfolge (CAGR gesamt, Stress) alt → neu:\n")
        for c in caps:
            vs = [k[0] for k in keys if k[1] == lay]
            rk = lambda D: sorted(vs, key=lambda v: -(val(D[(v, lay)], f"{c}_stress", "gesamt") or -9))
            ro, rn = rk(old), rk(new)
            L.append(f"- {c} €: {' > '.join(ro)}  →  {' > '.join(rn)}" + ("" if ro == rn else "  **(geändert)**"))
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old"); ap.add_argument("--new"); ap.add_argument("--title", default="Alt gegen neu"); ap.add_argument("--out")
    a = ap.parse_args(argv)
    txt = compare(load(Path(a.old)), load(Path(a.new)), a.title)
    if a.out:
        Path(a.out).write_text(txt)
    print(txt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
