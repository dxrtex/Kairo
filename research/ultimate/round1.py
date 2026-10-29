"""Kairo Ultimate – Runde 1, Wettbewerb A (H1–H4): Varianten je Trade, im Depot und gegen Zufall.

Regeln: docs/KAIRO_ULTIMATE_RESEARCH_PLAN.md (eingefroren; Präzisierungen 9b). Treffer = unveränderter Scanner 11/11
(Signale der Schwellen-Prüfung, Variante 0). Ausstieg für alle Varianten B60: Stop, EMA20-Schluss ab Tag 10, spätestens
Tag 60. Rangfolge bei vollem Depot: schwächeres Vormomentum zuerst (wie live).

  E0  B60 wie heute (Basis 5 Kerzen ≤ 1,5 ATR, Kauf zur nächsten Eröffnung in der Basis)
  E1  Früheinstieg: ab Kerze 3, letzte 3 Kerzen ≤ 1,5 ATR, Umkehrkerze (oberes Drittel, Schluss > Vortageshoch)
  E2  Bestätigter Ausbruch: Buy-Stop über dem Basishoch (+0,05 ATR), Kurslücke höchstens +0,5 ATR
  V1  E0, aber Kauf entfällt, wenn vorher MACD < Signallinie UND RSI14 < RSI am Treffertag (gleicher Schluss)
  N1  E0, aber US-Treffer nach Quartalszahlen-Rückgang (≤ −5 % am Reaktionstag) ausgeschlossen
  C1  E0, aber nur, wenn Stress-Kosten (Kauf + Verkauf) ≤ 0,10 R

    python -m research.ultimate.round1 trades --data v1 --signals sig.parquet --variant E1 --out out [--sec sec/]
    python -m research.ultimate.round1 depot  --data v1 --signals sig.parquet --variant E1 --layout 20x025 --out out
    python -m research.ultimate.round1 null   --data v1 --signals sig.parquet --variant E1 --seed-start 0 --seed-n 5 --out out
    python -m research.ultimate.round1 report --dir DIR [--audit data_audit.json]
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from backend.indicators import macd, rsi
from research.strategy_championship import s01
from research.strategy_championship import v2_test as V
from research.strategy_championship.data import PERIODS, UNIVERSE
from research.strategy_championship.engine import Costs, Order, run

VARIANTS = ("E0", "E1", "E2", "V1", "N1", "C1")
LAYOUTS = {"5x1": (5, 0.01), "10x05": (10, 0.005), "20x025": (20, 0.0025)}
CASH = (1000, 3000, 5000, 10000, 20000)
HOLD, EMA_FROM = 60, 10
AB = ("Train", "Validierung", "Holdout")
_G = V._G
SLIP, FXFEE = 0.0005, 0.001


# ------------------------------------------------------------------ Hilfen
def arrays(t: str):
    a = _G["adj"][t]
    return (a["High"].to_numpy(float), a["Low"].to_numpy(float), a["Close"].to_numpy(float), a["f"].to_numpy(float), a.index)


def prio(m: dict) -> float:
    return -m["mom"] if np.isfinite(m.get("mom", np.nan)) else -9.0


def _order(t, k, idx, f, stop, rf, p, gid, atr, **kw) -> Order:
    fk = f[k]
    return Order(idx[k], t, stop=stop / fk, risk_frac=rf, prio=p, tag=gid, atr=atr / fk, risk_atr=s01.RISK, group=gid,
                 max_days=HOLD, exit_rule=("ema", EMA_FROM), **kw)


def ind(t: str):
    c = _G.setdefault("ind", {})
    if t not in c:
        C = _G["adj"][t]["Close"]
        m = macd(C)
        c[t] = (m["macd"].to_numpy(float), m["signal"].to_numpy(float), rsi(C).to_numpy(float))
    return c[t]


def stress_side(t: str) -> float:
    sp = _G["spread"].get(t, 0.001) * 2
    cur = _G.get("cur_real") or _G["cur"]
    return sp / 2 + SLIP + (FXFEE if cur.get(t, "EUR") != "EUR" else 0.0)


# ------------------------------------------------------------------ Varianten
def orders_E0(t, i, atr, gid, m, rf):
    return V.base_orders(t, i, atr, gid, 0, "mom", m, risk_frac=rf, hold=HOLD)


def orders_E1(t, i, atr, gid, m, rf):
    h, l, c, f, idx = arrays(t)
    if not (atr > 0):
        return []
    inv = l[max(0, i - 9): i + 1].min()
    out = []
    for j in range(s01.WAIT):
        k = i + 1 + j
        if k >= len(c) - 1:
            break
        if l[k] < inv:
            break
        if k < i + 3:
            continue
        if h[k - 2: k + 1].max() - l[k - 2: k + 1].min() > s01.CM * atr:
            continue
        rg = h[k] - l[k]
        if not (rg > 0 and c[k] >= l[k] + 2 / 3 * rg and c[k] > h[k - 1]):
            continue
        stop = l[i: k + 1].min() - s01.BUF * atr
        out.append(_order(t, k, idx, f, stop, rf, prio(m), gid, atr, entry_band=(stop / f[k], (c[k] + 0.5 * atr) / f[k])))
    return out


def orders_E2(t, i, atr, gid, m, rf):
    h, l, c, f, idx = arrays(t)
    if not (atr > 0):
        return []
    inv = l[max(0, i - 9): i + 1].min()
    k0 = None
    for j in range(s01.WAIT):
        k = i + 1 + j
        if k >= len(c) - 1 or l[k] < inv:
            break
        if j < s01.CK - 1:
            continue
        if h[k - s01.CK + 1: k + 1].max() - l[k - s01.CK + 1: k + 1].min() <= s01.CM * atr:
            k0 = k
            break
    if k0 is None:
        return []
    bh, bl = h[k0 - s01.CK + 1: k0 + 1].max(), l[k0 - s01.CK + 1: k0 + 1].min()
    trig, cap = bh + 0.05 * atr, bh + 0.5 * atr
    out = []
    for k in range(k0, min(k0 + 10, len(c) - 1)):
        if k > k0 and (l[k] < bl or h[k] >= trig):       # Basis gebrochen oder Ausbruch schon gelaufen
            break
        out.append(_order(t, k, idx, f, bl - s01.BUF * atr, rf, prio(m), gid, atr,
                          entry_stop=trig / f[k], entry_cap=cap / f[k]))
    return out


def orders_V1(t, i, atr, gid, m, rf):
    ml, ms, r = ind(t)
    idx = _G["adj"][t].index
    fail = (ml < ms) & (r < r[i])
    out = []
    for o in orders_E0(t, i, atr, gid, m, rf):
        k = idx.get_loc(o.decision_date)
        if not fail[i + 1: k + 1].any():
            out.append(o)
    return out


def orders_C1(t, i, atr, gid, m, rf):
    _h, _l, c, f, idx = arrays(t)
    cost = 2 * stress_side(t)
    out = []
    for o in orders_E0(t, i, atr, gid, m, rf):
        k = idx.get_loc(o.decision_date)
        dist = (c[k] - o.stop * f[k]) / c[k]
        if dist > 0 and cost / dist <= 0.10:
            out.append(o)
    return out


def orders_N1(t, i, atr, gid, m, rf):
    if "." not in t and news_drop(t, i):
        return []
    return orders_E0(t, i, atr, gid, m, rf)


GEN = {"E0": orders_E0, "E1": orders_E1, "E2": orders_E2, "V1": orders_V1, "N1": orders_N1, "C1": orders_C1}


# ------------------------------------------------------------------ SEC (N1)
def load_sec(d: str | None) -> None:
    _G["sec"] = {}
    if not d:
        return
    cm = pd.read_csv(Path(d) / "cik_map.csv")
    cik = dict(zip(cm["ticker"].str.upper(), cm["cik"]))
    f = pd.read_csv(Path(d) / "filings.csv.gz", dtype={"items": str}, usecols=["cik", "form", "items", "accepted"])
    f = f[(f["form"] == "8-K") & f["items"].fillna("").str.contains("2.02")]
    f["at"] = pd.to_datetime(f["accepted"], utc=True, errors="coerce").dt.tz_localize(None).dt.normalize()
    E = {c: np.sort(g["at"].dropna().to_numpy()) for c, g in f.groupby("cik")}
    _G["sec"] = {t: E[c] for t, c in cik.items() if c in E}


def news_drop(t: str, i: int) -> bool:
    """Quartalsmeldung im Rückgang (60 Handelstage bis Treffer) mit Reaktion ≤ −5 % am Reaktionstag (Annahmetag oder Folgetag –
    Meldungen nach Börsenschluss wirken erst am Folgetag; Plan 9b, ergänzt vor dem ersten Lauf)."""
    e = _G["sec"].get(t.upper())
    if e is None:
        return False
    idx = _G["adj"][t].index
    c = _G["adj"][t]["Close"].to_numpy(float)
    a, b = idx[max(0, i - 59)], idx[i]
    for d in e[(e >= np.datetime64(a)) & (e <= np.datetime64(b))]:
        j = int(np.searchsorted(idx.values, d))
        for jj in (j, j + 1):
            if 1 <= jj <= i and c[jj] / c[jj - 1] - 1 <= -0.05:
                return True
    return False


# ------------------------------------------------------------------ Kennzahlen
def metrics(e: pd.Series, trades: pd.DataFrame | None = None, invested: pd.Series | None = None) -> dict | None:
    e = e.dropna()
    if len(e) < 20 or e.iloc[0] <= 0:
        return None
    yrs = (e.index[-1] - e.index[0]).days / 365.25
    r = e.pct_change().dropna()
    dd = e / e.cummax() - 1
    cagr = float((e.iloc[-1] / e.iloc[0]) ** (1 / yrs) - 1) if e.iloc[-1] > 0 else -1.0
    down = r[r < 0].std()
    out = {"cagr": cagr, "max_dd": float(dd.min()),
           "sharpe": float(r.mean() / r.std() * np.sqrt(252)) if r.std() > 0 else None,
           "sortino": float(r.mean() / down * np.sqrt(252)) if down and down > 0 else None,
           "calmar": float(cagr / -dd.min()) if dd.min() < 0 else None,
           "worst_12m": float((e / e.shift(252) - 1).min()) if len(e) > 260 else None,
           "final": float(e.iloc[-1])}
    if invested is not None:
        iv = invested.reindex(e.index).dropna()
        out["exposure"] = float(iv.mean()) if len(iv) else None
    if trades is not None and len(trades):
        t = trades
        R = t["pnl_eur"] / t["risk_eur"].where(t["risk_eur"] > 0)
        g, lo = t.loc[t["pnl_eur"] > 0, "pnl_eur"].sum(), -t.loc[t["pnl_eur"] < 0, "pnl_eur"].sum()
        top = t["pnl_eur"].nlargest(max(1, int(len(t) * 0.01))).sum()
        out.update(trades=int(len(t)), win=float((t["pnl_eur"] > 0).mean()), R_mean=float(R.mean()), R_median=float(R.median()),
                   profit_factor=float(g / lo) if lo > 0 else None, days=float(t["days"].mean()),
                   cost_eur=float((t["fees_eur"] + t["spread_eur"]).mean()), pnl=float(t["pnl_eur"].sum()),
                   pnl_ohne_top1=float(t["pnl_eur"].sum() - top))
    return out


def segments(e, trades=None, invested=None) -> dict:
    out = {"gesamt": metrics(e, trades, invested)}
    for ab, key in zip(AB, ("train", "validation", "holdout")):
        a, b = pd.Timestamp(PERIODS[key][0]), pd.Timestamp(PERIODS[key][1])
        tt = None if trades is None or not len(trades) else trades[(trades["entry_date"] >= a) & (trades["entry_date"] <= b)]
        out[ab] = metrics(e[(e.index >= a) & (e.index <= b)], tt, invested)
    return out


# ------------------------------------------------------------------ Läufe
def setup(data, sig_path, sec=None):
    sig, meta = V._setup(data, sig_path)
    from research.strategy_championship.wave1 import spreads
    uni = pd.read_csv(UNIVERSE)
    _G["region"] = dict(zip(uni["ticker"], uni["region"]))
    _G["spread"] = spreads(_G["raw"], _G["cur"], _G["region"])
    load_sec(sec)
    return sig, meta


def build(sig, meta, variant: str, rf: float, rows=None) -> list[Order]:
    gen, out = GEN[variant], []
    it = rows if rows is not None else ((r.ticker, int(r.i), float(r.atr), f"{r.ticker}|{pd.Timestamp(r.date).date()}", m)
                                        for r, m in zip(sig.itertuples(index=False), meta))
    for t, i, atr, gid, m in it:
        out += gen(t, i, atr, gid, m, rf)
    return out


def costs(kind: str, fee: bool = True) -> Costs:
    sp = _G["spread"]
    if kind == "base":
        return Costs(fee_eur=0.99 if fee else 0.0, spread=0.001, spread_by_ticker=sp, fee_free_from=250.0 if fee else None)
    return Costs(fee_eur=1.99 if fee else 0.0, spread=0.002, slippage=SLIP, fx_fee=FXFEE, fee_free_from=250.0 if fee else None,
                 spread_by_ticker={k: 2 * v for k, v in sp.items()})


def per_trade(orders: list[Order]) -> pd.DataFrame:
    res = {}
    for kind in ("base", "stress"):
        r = run(_G["raw"], _G["cur"], _G["fx"], orders, 1e9, costs(kind, fee=False), 10 ** 6, calendar=_G["cal"], min_fill=0.0)
        res[kind] = r.trades
    t = res["stress"].copy()
    if not len(t):
        return t
    t["R_stress"] = t["pnl_eur"] / t["risk_eur"]
    b = res["base"].set_index("tag")
    t["R_base"] = t["tag"].map(b["pnl_eur"] / b["risk_eur"])
    sd = pd.to_datetime(t["tag"].str.split("|").str[1])
    t["signal_date"] = sd
    t["abschnitt"] = V.abschnitt(sd)
    t["region"] = t["ticker"].map(_G["region"]).fillna("?")
    return t


def depot(orders_by_rf, layout: str) -> dict:
    mx, rf = LAYOUTS[layout]
    out, curves = {}, {}
    for cash in CASH:
        for kind in ("base", "stress"):
            r = run(_G["raw"], _G["cur"], _G["fx"], orders_by_rf, cash, costs(kind), mx, calendar=_G["cal"], min_fill=0.5)
            key = f"{cash}_{kind}"
            out[key] = segments(r.equity, r.trades, r.invested)
            out[key]["checks"] = r.checks
            curves[key] = r.equity
    return out, pd.DataFrame(curves)


def null_rows(sig, seed: int):
    """Je Treffer ein zufälliger zulässiger Titel desselben Tags und derselben Region (gleiche Mechanik)."""
    if "pool" not in _G:
        pool, pos, atr = {}, {}, {}
        for t, A in _G["adj"].items():
            ok = s01.eligible(A, _G["cur"].get(t, "USD"))
            pos[t] = {d: k for k, d in enumerate(A.index)}
            atr[t] = s01.atr14(A).to_numpy(float)
            reg = _G["region"].get(t, "?")
            for d in A.index[ok]:
                pool.setdefault((d, reg), []).append(t)
        _G.update(pool={k: np.array(v) for k, v in pool.items()}, pos=pos, atr_all=atr)
    rng = np.random.default_rng(seed)
    rows = []
    for r in sig.itertuples(index=False):
        d = pd.Timestamp(r.date)
        cand = _G["pool"].get((d, _G["region"].get(r.ticker, "?")))
        if cand is None or not len(cand):
            continue
        t = str(rng.choice(cand))
        i = _G["pos"][t].get(d)
        if i is None:
            continue
        a = _G["atr_all"][t][i]
        if np.isfinite(a) and a > 0:
            rows.append((t, i, float(a), f"{t}|{d.date()}|z{seed}|{r.ticker}", {"mom": np.nan}))
    return rows


def summary(t: pd.DataFrame) -> dict:
    out = {}
    for ab in AB + ("Train+Val",):
        s = t[t["abschnitt"].isin(("Train", "Validierung"))] if ab == "Train+Val" else t[t["abschnitt"] == ab]
        out[ab] = {"n": int(len(s)), "R_stress": float(s["R_stress"].mean()) if len(s) else None,
                   "R_base": float(s["R_base"].mean()) if len(s) else None}
    return out


# ------------------------------------------------------------------ Bericht
def block_boot_p(x: pd.DataFrame, y: pd.DataFrame, col="R_stress", n=5000, seed=3) -> float:
    """Einseitig: P(Ø x − Ø y ≤ 0) mit Monats-Blöcken (Monate des Treffers, beide Gruppen gemeinsam gezogen)."""
    rng = np.random.default_rng(seed)
    mx = x.groupby(x["signal_date"].dt.to_period("M"))[col].agg(["sum", "count"])
    my = y.groupby(y["signal_date"].dt.to_period("M"))[col].agg(["sum", "count"])
    j = mx.join(my, lsuffix="_x", rsuffix="_y", how="outer").fillna(0.0)
    a = j.to_numpy(float)
    c = 0
    for _ in range(n):
        s = a[rng.integers(0, len(a), len(a))].sum(axis=0)
        if s[1] > 0 and s[3] > 0:
            c += (s[0] / s[1] - s[2] / s[3]) <= 0
    return (c + 1) / (n + 1)


def holm(ps: dict) -> dict:
    items = sorted(ps.items(), key=lambda kv: kv[1])
    m, out, run_max = len(items), {}, 0.0
    for k, (name, p) in enumerate(items):
        run_max = max(run_max, min(1.0, (m - k) * p))
        out[name] = run_max
    return out


def report(d: Path, audit: str | None) -> str:
    L = []
    p = lambda s="": (print(s), L.append(s))
    unsure = set(json.loads(Path(audit).read_text()).get("unsicher", [])) if audit and Path(audit).exists() else set()
    tr = {v: pd.read_csv(d / f"trades_{v}.csv", parse_dates=["signal_date", "entry_date"]) for v in VARIANTS if (d / f"trades_{v}.csv").exists()}
    if "E0" not in tr:
        p("E0 fehlt – kein Bericht."); return "\n".join(L)
    for label, excl in (("alle Titel", set()), ("ohne unsichere Titel", unsure)):
        if label != "alle Titel" and not excl:
            continue
        T = {v: t[~t["ticker"].isin(excl)] for v, t in tr.items()}
        p(f"\n## Je Trade – {label} (Ø R netto, Stress / Basis; n)\n")
        p("| Variante | " + " | ".join(AB) + " |\n|---|---|---|---|")
        for v, t in T.items():
            us = t[~t["ticker"].str.contains(r"\.")] if v == "N1" else t
            p(f"| {v} | " + " | ".join(f"{us[us.abschnitt == ab]['R_stress'].mean():+.3f} / {us[us.abschnitt == ab]['R_base'].mean():+.3f} (n {int((us.abschnitt == ab).sum())})" for ab in AB) + " |")
        e0 = T["E0"]
        pv = {}
        for v, t in T.items():
            if v == "E0":
                continue
            x, y = (t, e0) if v != "N1" else (t[~t["ticker"].str.contains(r"\.")], e0[~e0["ticker"].str.contains(r"\.")])
            tv = lambda s: s[s["abschnitt"].isin(("Train", "Validierung"))]
            pv[v] = block_boot_p(tv(x), tv(y))
        ph = holm(pv)
        p(f"\nBlock-Bootstrap (Monate) Train+Validierung, einseitig Variante > E0, Holm über {len(pv)}: " +
          ", ".join(f"{v} p {pv[v]:.3f} → {ph[v]:.3f}" for v in pv))
        _G[f"holm_{label}"] = ph
    dep = {}
    for f in sorted(d.glob("depot_*_*.json")):
        _, v, lay = f.stem.split("_", 2)
        dep[(v, lay)] = json.loads(f.read_text())
    if dep:
        p("\n## Depot – CAGR / max. Rückgang (Stress), Train · Validierung · Holdout · gesamt\n")
        for lay in LAYOUTS:
            p(f"\n**{lay}**\n\n| Variante | Kapital | Train | Validierung | Holdout | gesamt | Sharpe gesamt | Trades |\n|---|---|---|---|---|---|---|---|")
            for v in VARIANTS:
                r = dep.get((v, lay))
                if not r:
                    continue
                for cash in CASH:
                    s = r[f"{cash}_stress"]
                    c = lambda ab: f"{s[ab]['cagr']:+.1%} / {s[ab]['max_dd']:.0%}" if s.get(ab) else "–"
                    p(f"| {v} | {cash} € | {c('Train')} | {c('Validierung')} | {c('Holdout')} | {c('gesamt')} | "
                      f"{(s['gesamt'] or {}).get('sharpe') or 0:.2f} | {(s['gesamt'] or {}).get('trades', 0)} |")
    nul = {}
    for f in sorted(d.glob("null_*_*.json")):
        v = f.stem.split("_")[1]
        nul.setdefault(v, []).extend(json.loads(f.read_text()))
    conf = {}
    for f in sorted(d.glob("confirm_*.json")):
        conf[f.stem.split("_", 1)[1]] = json.loads(f.read_text())
    p("\n## Entscheidung nach Plan (§7, alle Punkte nötig)\n")
    p("| Variante | 1 ΔR ≥ +0,05 Train & Val | 2 Depot 10 k€ 20×0,25 % Stress > E0 Train & Val | 3 Holm p ≤ 0,05 | 4 Bestätigung Vorzeit & Asien | 5 > Zufall p ≤ 0,10, n ≥ 300 | Urteil |")
    p("|---|---|---|---|---|---|---|")
    e0 = tr["E0"]
    ph = _G.get("holm_alle Titel", {})
    for v, t in tr.items():
        if v == "E0":
            continue
        x, y = (t, e0) if v != "N1" else (t[~t["ticker"].str.contains(r"\.")], e0[~e0["ticker"].str.contains(r"\.")])
        dR = {ab: x[x.abschnitt == ab]["R_stress"].mean() - y[y.abschnitt == ab]["R_stress"].mean() for ab in AB}
        k1 = dR["Train"] >= 0.05 and dR["Validierung"] >= 0.05
        a, b = dep.get((v, "20x025")), dep.get(("E0", "20x025"))
        k2 = bool(a and b and all(a["10000_stress"][ab]["cagr"] > b["10000_stress"][ab]["cagr"] for ab in AB[:2]))
        k3 = ph.get(v, 1.0) <= 0.05
        c = conf.get(v, {})
        k4 = bool(c) and all(c[s] > 0 for s in c)
        z = nul.get(v, [])
        mine = summary(x)["Train+Val"]["R_stress"]
        pz = (sum(1 for s in z if s["Train+Val"]["R_stress"] is not None and s["Train+Val"]["R_stress"] >= mine) + 1) / (len(z) + 1) if z else 1.0
        k5 = pz <= 0.10 and all((x.abschnitt == ab).sum() >= 300 for ab in AB[:2])
        ok = k1 and k2 and k3 and k4 and k5
        m = lambda b: "✓" if b else "✗"
        p(f"| {v} | {m(k1)} {dR['Train']:+.3f} / {dR['Validierung']:+.3f} | {m(k2)} | {m(k3)} {ph.get(v, 1):.3f} | {m(k4)} {json.dumps({k: round(w, 3) for k, w in c.items()})} | "
          f"{m(k5)} p {pz:.2f} ({len(z)} Seeds) | {'**BESTANDEN**' if ok else 'nicht bestanden'} |")
    p(f"\nReproduktion: Commit {os.environ.get('GITHUB_SHA', '?')}, prices_v1 SHA-256 {os.environ.get('PRICES_SHA', '?')}, Regel B60 (Tag {HOLD}).")
    (d / "round1_report.md").write_text("\n".join(L), encoding="utf-8")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["trades", "depot", "null", "report"])
    ap.add_argument("--data"); ap.add_argument("--signals"); ap.add_argument("--out", default="r1_out")
    ap.add_argument("--variant", default="E0", choices=VARIANTS); ap.add_argument("--layout", default="20x025", choices=list(LAYOUTS))
    ap.add_argument("--sec"); ap.add_argument("--seed-start", type=int, default=0); ap.add_argument("--seed-n", type=int, default=5)
    ap.add_argument("--dir"); ap.add_argument("--audit")
    a = ap.parse_args(argv)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    if a.cmd == "report":
        report(Path(a.dir), a.audit); return 0
    sig, meta = setup(a.data, a.signals, a.sec)
    if a.cmd == "trades":
        t = per_trade(build(sig, meta, a.variant, 1e-5))
        t.to_csv(out / f"trades_{a.variant}.csv", index=False)
        print(a.variant, json.dumps(summary(t)), flush=True)
    elif a.cmd == "depot":
        r, curves = depot(build(sig, meta, a.variant, LAYOUTS[a.layout][1]), a.layout)
        (out / f"depot_{a.variant}_{a.layout}.json").write_text(json.dumps(r, indent=1, default=str))
        curves.to_parquet(out / f"curve_{a.variant}_{a.layout}.parquet")
        s = r["10000_stress"]
        print(a.variant, a.layout, " | ".join(f"{ab} {s[ab]['cagr']:+.1%}" for ab in AB if s.get(ab)), r["10000_stress"]["checks"], flush=True)
    else:
        res = []
        for seed in range(a.seed_start, a.seed_start + a.seed_n):
            t = per_trade(build(sig, meta, a.variant, 1e-5, rows=null_rows(sig, 1000 + seed)))
            res.append(summary(t))
            print(a.variant, "Zufall", seed, json.dumps(res[-1]["Train+Val"]), flush=True)
        (out / f"null_{a.variant}_{a.seed_start}.json").write_text(json.dumps(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
