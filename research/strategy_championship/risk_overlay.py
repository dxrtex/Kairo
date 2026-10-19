"""Protokoll v2.9 – Risikosteuerung (Zielvolatilität) und Hebel auf den Tageskurven aus v2.8 (Stress-Kosten).

python -m research.strategy_championship.risk_overlay --curves system_mix_curves.csv --out OUT
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .kairo_depot import segs

VARS = {"ungehebelt": None, "S1 statisch 1,25": ("fix", 1.25), "S2 statisch 1,5": ("fix", 1.5),
        "V0 Zielvola 12 % max 1,0": ("vol", 0.12, 1.0), "V1 Zielvola 12 % max 1,5": ("vol", 0.12, 1.5),
        "V2 Zielvola 15 % max 1,5": ("vol", 0.15, 1.5)}
TRADE, BORROW = 0.002, 0.06


def overlay(e: pd.Series, spec) -> pd.Series:
    r = e.pct_change().fillna(0.0)
    if spec is None:
        return e / e.iloc[0]
    vol = r.rolling(21).std() * np.sqrt(252)
    L, eq, out = 1.0 if spec[0] == "vol" else spec[1], 1.0, []
    for k, (d, x) in enumerate(r.items()):
        eq *= 1 + L * x - max(L - 1, 0) * BORROW / 252
        out.append(eq)
        if d.weekday() == 4 or k == 0:                     # freitags neu festlegen, gilt ab nächstem Tag
            new = spec[1] if spec[0] == "fix" else (min(spec[2], spec[1] / vol.iloc[k]) if np.isfinite(vol.iloc[k]) and vol.iloc[k] > 0 else 1.0)
            eq *= 1 - abs(new - L) * TRADE
            L = new
    return pd.Series(out, index=r.index)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--curves", required=True)
    ap.add_argument("--out", default="ro_out")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    cv = pd.read_csv(a.curves, index_col=0, parse_dates=True)
    res = {}
    for base in ("M2 70/30 ACWI/DM · stress", "M0 100 ACWI · stress"):
        for name, spec in VARS.items():
            g = res[f"{base.split(' ·')[0]} · {name}"] = segs(overlay(cv[base].dropna(), spec))
            print(f"{base.split(' ·')[0]:18s} {name:26s}", " | ".join(f"{ab[:5]} {g[ab]['cagr']:+.1%} DD{g[ab]['max_dd']:.0%} S{g[ab]['sharpe']:.2f}"
                  for ab in ("Train", "Validierung", "Holdout", "gesamt") if g.get(ab)), flush=True)
    v1, m2, m0 = res["M2 70/30 ACWI/DM · V1 Zielvola 12 % max 1,5"], res["M2 70/30 ACWI/DM · ungehebelt"], res["M0 100 ACWI · ungehebelt"]
    crit = {"cagr_alle_drei": all(v1[ab]["cagr"] > m2[ab]["cagr"] for ab in ("Train", "Validierung", "Holdout")),
            "dd_ok": v1["gesamt"]["max_dd"] >= m0["gesamt"]["max_dd"], "sharpe_ok": v1["gesamt"]["sharpe"] >= m2["gesamt"]["sharpe"]}
    crit["kandidat"] = all(crit.values())
    res["_entscheidung"] = crit
    print(crit)
    (out / "risk_overlay.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
