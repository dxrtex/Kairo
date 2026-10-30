"""Kairo Reversal Ultimate – Phase 4: vorregistrierte Varianten R1–R4 (docs/KAIRO_REVERSAL_ULTIMATE_PLAN.md).

  E0  B60 unverändert (Referenz)        E2  Ausbruchs-Einstieg (Referenz aus Runde 1)
  R1  B60 mit Stop-Mindestabstand 1 ATR (Stop = min(B60-Stop, Schluss Entscheidungstag − 1 ATR))
  R2  B60, Rangfolge nach Stop-Abstand in % (größter zuerst) – nur Depot
  R3  B60 mit Mindestorder 250 € (Aufstocken bis 2 × Risiko, sonst auslassen) – nur Depot
  R4  E2 + R1 (Stop min(E2-Stop, Buy-Stop-Kurs − 1 ATR)) + R2 + R3

    python -m research.reversal.run trades  --data v1 --signals S --variant R1 --out OUT
    python -m research.reversal.run depot   --data v1 --signals S --variant R4 --layout 5x1 --out OUT
    python -m research.reversal.run null    --data v1 --signals S --variant R1 --seed-start 0 --seed-n 5 --out OUT
    python -m research.reversal.run confirm --set pre|asia --shard K --shards N --universe U --sec SEC --out OUT
    python -m research.reversal.run report  --dir DIR [--audit A] [--ub UB_DIR]
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from research.strategy_championship.engine import run
from research.ultimate import confirm as CF
from research.ultimate import round1 as R

VARIANTS = ("E0", "E2", "R1", "R2", "R3", "R4", "X1", "X2", "X3", "Q1")
ABLATION = {"X1": "E2 + R1 (ohne Rangfolge, ohne Mindestorder)", "X2": "E2 + R1 + R2", "X3": "E2 + R1 + R3"}   # explorativ
TESTS = ("R1", "R2", "R3", "R4")
MIN_ORDER = 250.0


def _widen(orders, t, ref_of):
    """Stop auf höchstens (Referenzkurs − 1 ATR) setzen – nur weiter, nie enger."""
    _h, _l, c, f, idx = R.arrays(t)
    for o in orders:
        k = idx.get_loc(o.decision_date)
        atr = o.atr * f[k]
        ref = ref_of(o, k, c)
        o.stop = min(o.stop * f[k], ref - 1.0 * atr) / f[k]
    return orders


def orders_R1(t, i, atr, gid, m, rf):
    return _widen(R.orders_E0(t, i, atr, gid, m, rf), t, lambda o, k, c: c[k])


def orders_R4core(t, i, atr, gid, m, rf):
    return _widen(R.orders_E2(t, i, atr, gid, m, rf), t, lambda o, k, c: o.entry_stop * R.arrays(t)[3][k])


def orders_Q1(t, i, atr, gid, m, rf):
    """Ruhe-Prüfung am Basis-Tag (Tag vor dem Kauf) wie im Scanner (backend.scanner.calm_days): Spanne 5 Tage ≤ 1,5 ATR
    und Hin und Her 10 Tage ≤ 1,65. Nur B60-Trades, deren Basis-Tag ruhig ist (Frage Jonny 30.10.2026: unruhige Setups
    schlechter?)."""
    from backend.scanner import calm_days
    cache = R._G.setdefault("calm_q1", {})
    if t not in cache:
        cache[t] = calm_days(R._G["adj"][t])
    cd, idx = cache[t], R.arrays(t)[4]
    return [o for o in R.orders_E0(t, i, atr, gid, m, rf) if bool(cd[idx.get_loc(o.decision_date)])]


R.GEN.update({"R1": orders_R1, "R2": R.orders_E0, "R3": R.orders_E0, "R4": orders_R4core,
              "X1": orders_R4core, "X2": orders_R4core, "X3": orders_R4core, "Q1": orders_Q1})


def finish(variant: str, orders):
    """Depot-Bausteine: R2/R4 Rangfolge nach Stop-Abstand, R3/R4 Mindestorder."""
    if variant in ("R2", "R4", "X2"):
        for o in orders:
            t = o.ticker
            _h, _l, c, f, idx = R.arrays(t)
            k = idx.get_loc(o.decision_date)
            ref = o.entry_stop * f[k] if o.entry_stop is not None else c[k]
            o.prio = (ref - o.stop * f[k]) / ref
    if variant in ("R3", "R4", "X3"):
        for o in orders:
            o.min_value_eur, o.max_risk_mult = MIN_ORDER, 2.0
    return orders


def depot(sig, meta, variant, layout):
    mx, rf = R.LAYOUTS[layout]
    orders = finish(variant, R.build(sig, meta, variant, rf))
    out, curves = {}, {}
    for cash in R.CASH:
        for kind in ("base", "stress"):
            r = run(R._G["raw"], R._G["cur"], R._G["fx"], orders, cash, R.costs(kind), mx, calendar=R._G["cal"], min_fill=0.5)
            key = f"{cash}_{kind}"
            t = r.trades
            rk = {"risk_pct": float(t["risk_pct"].mean()) if len(t) else None,
                  "open_risk": float(r.open_risk.mean()) if r.open_risk is not None else None,
                  "exposure": float(r.invested.mean()) if r.invested is not None else None,
                  "fees_per_trade": float(t["fees_eur"].mean()) if len(t) else None,
                  "stake": float(t["cost_eur"].mean()) if len(t) else None}
            out[key] = R.segments(r.equity, r.trades, r.invested) | {"checks": r.checks, "skipped": r.skipped,
                                                                     "steuer": R.taxable_by_year(r), "risiko": rk}
            curves[key] = r.equity
    return out, pd.DataFrame(curves)


# ------------------------------------------------------------------ Bericht
def boot_curve_p(a: pd.Series, b: pd.Series, n=3000, block=63, seed=5) -> float:
    j = pd.concat([a.pct_change(), b.pct_change()], axis=1).dropna()
    d = (np.log1p(j.iloc[:, 0]) - np.log1p(j.iloc[:, 1])).to_numpy()
    if len(d) < 2 * block:
        return 1.0
    rng, c = np.random.default_rng(seed), 0
    for _ in range(n):
        ix = (rng.integers(0, len(d) - block, len(d) // block + 1)[:, None] + np.arange(block)).ravel()[:len(d)]
        c += d[ix].mean() <= 0
    return (c + 1) / (n + 1)


def report(d: Path, audit: str | None, ub: str | None) -> str:
    L = []
    p = lambda s="": (print(s), L.append(s))
    AB = R.AB
    tr = {v: pd.read_csv(d / f"trades_{v}.csv", parse_dates=["signal_date", "entry_date"]) for v in ("E0", "E2", "R1", "R4") if (d / f"trades_{v}.csv").exists()}
    unsure = set(json.loads(Path(audit).read_text()).get("unsicher", [])) if audit and Path(audit).exists() else set()
    p("# Kairo Reversal Ultimate – Ergebnisse\n")
    p("## Je Trade (Ø R netto Stress / Basis; n) – Train nur zur Information (Diagnose-Daten)\n")
    p("| Variante | Train | Validierung | Holdout | ohne beste 1 % (Val+Hold) | ohne unsichere Titel (Val / Hold) |\n|---|---|---|---|---|---|")
    for v, t in tr.items():
        vh = t[t.abschnitt.isin(("Validierung", "Holdout"))].sort_values("R_stress")
        cut = vh.iloc[: max(1, int(len(vh) * 0.99))]
        u = t[~t.ticker.isin(unsure)]
        p(f"| {v} | " + " | ".join(f"{t[t.abschnitt == ab]['R_stress'].mean():+.3f} / {t[t.abschnitt == ab]['R_base'].mean():+.3f} (n {int((t.abschnitt == ab).sum())})" for ab in AB)
          + f" | {cut['R_stress'].mean():+.3f} | {u[u.abschnitt == 'Validierung']['R_stress'].mean():+.3f} / {u[u.abschnitt == 'Holdout']['R_stress'].mean():+.3f} |")
    pv = {}
    for v in ("R1", "R4"):
        if v in tr and "E0" in tr:
            sel = lambda s: s[s.abschnitt.isin(("Validierung", "Holdout"))]
            pv[v] = R.block_boot_p(sel(tr[v]), sel(tr["E0"]))
    conf = {}
    for f in sorted(d.glob("confirm_*.json")):
        conf[f.stem.split("_", 1)[1]] = json.loads(f.read_text())
    if conf:
        p("\n## Bestätigung je Trade: Δ Ø R Stress gegenüber B60\n")
        for v, c in conf.items():
            p(f"- {v}: " + ", ".join(f"{k} {w:+.3f}" for k, w in c.items()))
    dep, cur = {}, {}
    for f in sorted(d.glob("depot_*_*.json")):
        _, v, lay = f.stem.split("_", 2)
        dep[(v, lay)] = json.loads(f.read_text())
        cp = d / f"curve_{v}_{lay}.parquet"
        if cp.exists():
            cur[(v, lay)] = pd.read_parquet(cp)
    p("\n## Depot – CAGR Stress (max. Rückgang) · Validierung | Holdout | gesamt 2008–26 | nach Steuern gesamt\n")
    from research.ultimate.compete import after_tax
    for lay in R.LAYOUTS:
        p(f"\n**{lay}**\n\n| Variante | " + " | ".join(f"{c} €" for c in R.CASH) + " |\n|---|" + "---|" * len(R.CASH))
        for v in VARIANTS:
            r = dep.get((v, lay))
            if not r:
                continue
            cells = []
            for c in R.CASH:
                s = r[f"{c}_stress"]
                cv = cur.get((v, lay))
                at = R.metrics(after_tax(cv[f"{c}_stress"].dropna(), {int(k): x for k, x in s["steuer"].items()})) if cv is not None else None
                g = lambda ab, k="cagr": f"{s[ab][k]:+.1%}" if s.get(ab) else "–"
                cells.append(f"{g('Validierung')} · {g('Holdout')} · {g('gesamt')} ({g('gesamt', 'max_dd')}) · St {at['cagr']:+.1%}" if at else "–")
            p(f"| {v} | " + " | ".join(cells) + " |")
    # Bootstrap Depot gegen B60
    for v, lay, cash in (("R1", "20x025", 10000), ("R2", "20x025", 10000), ("R3", "5x1", 1000), ("R3", "5x1", 3000), ("R3", "5x1", 5000), ("R4", "20x025", 10000)):
        a, b = cur.get((v, lay)), cur.get(("E0", lay))
        if a is not None and b is not None:
            k = f"{cash}_stress"
            vh = lambda s: s[s.index >= pd.Timestamp("2017-01-01")]
            pv[f"{v}·{lay}·{cash}"] = boot_curve_p(vh(a[k].dropna()), vh(b[k].dropna()))
    ph = R.holm(pv) if pv else {}
    p("\n## Statistik (Validierung + Holdout, einseitig besser als B60, Holm)\n")
    for k in pv:
        p(f"- {k}: p {pv[k]:.3f} → Holm {ph[k]:.3f}")
    # Entscheidung
    p("\n## Entscheidung nach Plan\n\n| Variante | Bedingungen | Urteil |\n|---|---|---|")
    def cg(v, lay, cash, ab):
        r = dep.get((v, lay))
        return r[f"{cash}_stress"][ab]["cagr"] if r and r[f"{cash}_stress"].get(ab) else np.nan
    if "R1" in tr:
        t, e = tr["R1"], tr["E0"]
        dv = t[t.abschnitt == "Validierung"]["R_stress"].mean() - e[e.abschnitt == "Validierung"]["R_stress"].mean()
        c = conf.get("R1", {})
        dep_ok = all(cg("R1", "20x025", 10000, ab) > cg("E0", "20x025", 10000, ab) for ab in ("Validierung", "Holdout"))
        ok = dv > 0 and c.get("vorzeit", -1) > 0 and c.get("asien", -1) > 0 and ph.get("R1", 1) <= 0.05 and dep_ok
        p(f"| R1 | ΔR Val {dv:+.3f}, Vorzeit {c.get('vorzeit', float('nan')):+.3f}, Asien {c.get('asien', float('nan')):+.3f}, Holm {ph.get('R1', 1):.3f}, Depot {'✓' if dep_ok else '✗'} | {'**BESTANDEN**' if ok else 'nicht bestanden'} |")
    for v, lay, cashes in (("R2", "20x025", (10000,)), ("R3", "5x1", (1000, 3000, 5000))):
        okd = all(cg(v, lay, c, ab) > cg("E0", lay, c, ab) for c in cashes for ab in ("Validierung", "Holdout"))
        okp = all(ph.get(f"{v}·{lay}·{c}", 1) <= 0.05 for c in cashes)
        p(f"| {v} | Depot {lay} {'/'.join(map(str, cashes))} € besser in Val & Hold: {'✓' if okd else '✗'}, Holm {'✓' if okp else '✗'} | {'**BESTANDEN**' if okd and okp else 'nicht bestanden'} |")
    if "R4" in tr:
        t, e = tr["R4"], tr["E0"]
        dv = t[t.abschnitt == "Validierung"]["R_stress"].mean() - e[e.abschnitt == "Validierung"]["R_stress"].mean()
        c = conf.get("R4", {})
        okd = all(cg("R4", "20x025", 10000, ab) > max(cg("E0", "20x025", 10000, ab), cg("E2", "20x025", 10000, ab)) for ab in ("Validierung", "Holdout"))
        ok = dv > 0 and c.get("vorzeit", -1) > 0 and c.get("asien", -1) > 0 and ph.get("R4", 1) <= 0.05 and okd
        p(f"| R4 | ΔR Val {dv:+.3f}, Vorzeit {c.get('vorzeit', float('nan')):+.3f}, Asien {c.get('asien', float('nan')):+.3f}, Holm {ph.get('R4', 1):.3f}, Depot > B60 & E2 {'✓' if okd else '✗'} | {'**BESTANDEN**' if ok else 'nicht bestanden'} |")
    nul = {}
    for f in sorted(d.glob("null_*_*.json")):
        nul.setdefault(f.stem.split("_")[1], []).extend(json.loads(f.read_text()))
    for v, z in nul.items():
        mine = R.summary(tr[v])["Train+Val"]["R_stress"] if v in tr else np.nan
        pz = (sum(1 for s in z if (s["Train+Val"]["R_stress"] or -9) >= mine) + 1) / (len(z) + 1)
        p(f"\nZufall {v}: {len(z)} Seeds, p {pz:.2f} (Ø R Train+Val {mine:+.3f} vs. Zufall-Median {np.median([s['Train+Val']['R_stress'] for s in z]):+.3f})")
    if "E0" in tr and "cost_R" in tr["E0"]:
        e = tr["E0"].dropna(subset=["stop_pct", "cost_R"])
        rho = e[["stop_pct", "cost_R"]].corr(method="spearman").iloc[0, 1]
        top = e.nlargest(len(e) // 5, "stop_pct").index.intersection(e.nsmallest(len(e) // 5, "cost_R").index)
        p(f"\n## R2 – Stop-Abstand vs. tatsächliche Kosten je R (ergänzend)\n\nSpearman-ρ(Stop-Abstand, Kosten/R) = {rho:+.3f}; "
          f"vom Fünftel mit dem größten Stop-Abstand liegen {len(top) / max(1, len(e) // 5):.0%} auch im Fünftel mit den kleinsten Kosten je R. "
          "R2 ist wie vorregistriert umgesetzt (Rangfolge nach Stop-Abstand in %); eine Rangfolge nach echten Kosten/R wäre eine neue Hypothese.")
    p("\n## R3 – kommt die Verbesserung aus Gebühren oder aus mehr Risiko? (5 × 1 %, Stress)\n")
    p("| Kapital | Variante | CAGR gesamt | max. Rückgang | Ø Risiko je Trade (Anteil Depot) | Ø offenes Risiko | Ø investiert | Ø Gebühr je Trade | Ø Einsatz |\n|---|---|---|---|---|---|---|---|---|")
    for c in (1000, 3000, 5000, 10000):
        for v in ("E0", "R3"):
            r = dep.get((v, "5x1"))
            if not r:
                continue
            s_, k = r[f"{c}_stress"], r[f"{c}_stress"].get("risiko") or {}
            f = lambda x, fmt: (fmt.format(x) if x is not None else "–")
            p(f"| {c} € | {v} | {f((s_.get('gesamt') or {}).get('cagr'), '{:+.1%}')} | {f((s_.get('gesamt') or {}).get('max_dd'), '{:.0%}')} | "
              f"{f(k.get('risk_pct'), '{:.2%}')} | {f(k.get('open_risk'), '{:.1%}')} | {f(k.get('exposure'), '{:.0%}')} | "
              f"{f(k.get('fees_per_trade'), '{:.2f} €')} | {f(k.get('stake'), '{:.0f} €')} |")
    p("\n## Ablation R4 (EXPLORATIV, nicht Teil der vorregistrierten Entscheidung) – 10.000 €, 20 × 0,25 %, Stress\n")
    p("| Variante | Inhalt | Validierung | Holdout | gesamt | max. Rückgang |\n|---|---|---|---|---|---|")
    for v, txt in [("E2", "Ausbruch allein"), ("X1", ABLATION["X1"]), ("X2", ABLATION["X2"]), ("X3", ABLATION["X3"]), ("R4", "E2 + R1 + R2 + R3")]:
        r = dep.get((v, "20x025"))
        if r:
            s_ = r["10000_stress"]
            g = lambda ab, k="cagr": f"{s_[ab][k]:+.1%}" if s_.get(ab) else "–"
            p(f"| {v} | {txt} | {g('Validierung')} | {g('Holdout')} | {g('gesamt')} | {g('gesamt', 'max_dd')} |")
    p(f"\nReproduktion: Commit {os.environ.get('GITHUB_SHA', '?')}, prices_v1 SHA-256 {os.environ.get('PRICES_SHA', '?')}")
    (d / "reversal_report.md").write_text("\n".join(L), encoding="utf-8")
    return "\n".join(L)


def calm_report(d: Path) -> str:
    """Ruhe-Test (vorab festgelegt 30.10.2026): Q1 besteht, wenn Ø R Stress je Trade in Validierung UND Holdout über B60
    liegt, in Asien nicht darunter, UND die Depot-CAGR (Stress) bei 5.000 € (5 × 1 %) und 10.000 € (20 × 0,25 %) in
    Validierung UND Holdout über B60 liegt. Sonst: Ruhe-Prüfung bleibt aus (wie heute)."""
    L = ["# Ruhe-Test: B60 nur mit ruhigem Basis-Tag (Q1) gegen B60 (E0)\n", calm_report.__doc__.split("\n", 1)[1].strip(), ""]
    T = {v: pd.read_csv(d / f"trades_{v}.csv") for v in ("E0", "Q1") if (d / f"trades_{v}.csv").exists()}
    ok = True
    if len(T) == 2:
        L.append("| Abschnitt | B60 Ø R (n) | nur ruhig Ø R (n) | Anteil behalten |\n|---|---|---|---|")
        for ab in ("Train", "Validierung", "Holdout"):
            a_, b_ = T["E0"][T["E0"]["abschnitt"] == ab], T["Q1"][T["Q1"]["abschnitt"] == ab]
            L.append(f"| {ab} | {a_['R_stress'].mean():+.3f} ({len(a_)}) | {b_['R_stress'].mean():+.3f} ({len(b_)}) | {len(b_) / max(1, len(a_)):.0%} |")
            if ab != "Train":
                ok &= b_["R_stress"].mean() > a_["R_stress"].mean()
        u = T["E0"][~T["E0"].set_index(["ticker", "entry_date"]).index.isin(T["Q1"].set_index(["ticker", "entry_date"]).index)]
        vh = u[u["abschnitt"].isin(("Validierung", "Holdout"))]
        L.append(f"\nDie aussortierten unruhigen Trades (Val + Holdout): Ø R {vh['R_stress'].mean():+.3f} (n {len(vh)}).")
    cf = d / "confirm.txt"
    if cf.exists():
        txt = cf.read_text()
        L.append("\nAsien 2008–26 (je Trade):\n```\n" + txt.strip() + "\n```")
        m = [ln for ln in txt.splitlines() if ln.startswith("asia Q1")]
        if m:
            ok &= float(m[0].split("Δ")[1]) >= 0
    L.append("\n| Depot (Stress) | Abschnitt | B60 | nur ruhig |\n|---|---|---|---|")
    for lay, cap in (("5x1", 5000), ("20x025", 10000), ("10x05", 10000)):
        dd = {v: json.loads((d / f"depot_{v}_{lay}.json").read_text()) for v in ("E0", "Q1") if (d / f"depot_{v}_{lay}.json").exists()}
        if len(dd) < 2:
            continue
        for ab in ("Validierung", "Holdout", "gesamt"):
            e, q = dd["E0"][f"{cap}_stress"][ab], dd["Q1"][f"{cap}_stress"][ab]
            L.append(f"| {cap} € {lay} | {ab} | {e['cagr']:+.1%} (Rückgang {e['max_dd']:.0%}) | {q['cagr']:+.1%} (Rückgang {q['max_dd']:.0%}) |")
            if lay != "10x05" and ab != "gesamt":
                ok &= q["cagr"] > e["cagr"]
    L.append(f"\n**Urteil nach Regel: {'Ruhe-Prüfung verbessert B60 – einbauen (nur mit Freigabe)' if ok else 'nicht besser – Ruhe-Prüfung bleibt aus, unruhige Setups bleiben drin'}.**")
    out = "\n".join(L)
    (d / "calm_report.md").write_text(out, encoding="utf-8")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["trades", "depot", "null", "confirm", "combine", "report", "calmreport"])
    ap.add_argument("--data"); ap.add_argument("--signals"); ap.add_argument("--out", default="rv_out")
    ap.add_argument("--variant", default="E0", choices=VARIANTS); ap.add_argument("--layout", default="20x025", choices=list(R.LAYOUTS))
    ap.add_argument("--sec"); ap.add_argument("--seed-start", type=int, default=0); ap.add_argument("--seed-n", type=int, default=5)
    ap.add_argument("--set"); ap.add_argument("--shard", type=int, default=0); ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--universe"); ap.add_argument("--dir"); ap.add_argument("--audit"); ap.add_argument("--ub")
    a = ap.parse_args(argv)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    if a.cmd == "calmreport":
        print(calm_report(Path(a.dir))); return 0
    if a.cmd == "report":
        report(Path(a.dir), a.audit, a.ub); return 0
    if a.cmd in ("confirm", "combine"):
        CF.VARS = {"pre": ("E0", "R1", "R4"), "asia": ("E0", "R1", "R4")} if not os.environ.get("CALM_TEST") else {"asia": ("E0", "Q1")}
        if a.cmd == "combine":
            CF.combine(Path(a.dir), out); return 0
        CF.run_shard(a); return 0
    sig, meta = R.setup(a.data, a.signals, a.sec)
    if a.cmd == "trades":
        t = R.per_trade(R.build(sig, meta, a.variant, 1e-5))
        sp = (t["entry_px"] - t["stop"]) / t["entry_px"]
        t["stop_pct"] = sp
        t["cost_R"] = [2 * R.stress_side(x) / s_ if s_ > 0 else np.nan for x, s_ in zip(t["ticker"], sp)]
        t.to_csv(out / f"trades_{a.variant}.csv", index=False)
        print(a.variant, json.dumps(R.summary(t)), flush=True)
    elif a.cmd == "depot":
        r, curves = depot(sig, meta, a.variant, a.layout)
        (out / f"depot_{a.variant}_{a.layout}.json").write_text(json.dumps(r, indent=1, default=str))
        curves.to_parquet(out / f"curve_{a.variant}_{a.layout}.parquet")
        print(a.variant, a.layout, {c: round(r[f"{c}_stress"]["gesamt"]["cagr"], 4) for c in R.CASH if r[f"{c}_stress"].get("gesamt")}, flush=True)
    else:
        res = []
        for seed in range(a.seed_start, a.seed_start + a.seed_n):
            t = R.per_trade(R.build(sig, meta, a.variant, 1e-5, rows=R.null_rows(sig, 1000 + seed)))
            res.append(R.summary(t))
        (out / f"null_{a.variant}_{a.seed_start}.json").write_text(json.dumps(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
