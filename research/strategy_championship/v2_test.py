"""Scanner v2 (29.10.2026): Ruhe-Filter am Kauftag, Rangfolge bei wenig Kapital, Asien als unabhängige Probe.

Anlass: Seit 28.10. gilt eine Aktie erst als Treffer, wenn die Konsolidierung AM TREFFER-TAG ruhig ist. Getestet war die Ruhe
aber am Tag vor dem KAUF (S01-B-Basis, im Schnitt ~10 Kalendertage nach dem Treffer). Am Treffer-Tag brachte sie nichts.
Live fielen dadurch ~95 % der Treffer weg (USA/Europa 70 → 4).

Vorab festgelegt (29.10.2026, vor dem Lauf):
Varianten des Einstiegs (Treffer unverändert, 11/11):
  G0  S01-B-Basis wie bisher getestet (ohne Ruhe-Filter)
  G1  wie G0, aber ein Basis-Tag zählt nur, wenn er ruhig ist: Spanne 5 Tage ≤ 1,5 × ATR14 (des Basis-Tags) UND
      Hin und Her 10 Tage ≤ 1,65 (Summe |Δ Schluss| / (Hoch − Tief) der 10 Tage). Sonst weiter warten (max. 10 Tage).
Depot wie live: 5.000 €, 1 % Risiko, max. 5 Positionen, EMA20-Ausstieg ab Tag 10, max. 60 Tage (Regel B60), Kosten PRIME+ (Basis + Stress).
Rangfolge, wenn mehr kaufbereite Aktien als freie Plätze (Tie-Break innerhalb desselben Tags):
  mom   schwächeres Vormomentum zuerst (heute live)   · vol   ruhigere Titel zuerst (ATR/Kurs klein)
  chop  wenigstes Hin und Her am Basis-Tag zuerst      · score höherer Kairo-Score zuerst   · rnd  Zufall (Kontrolle)
Entscheidungen:
  E1 Ruhe-Filter: G1 wird Live-Regel, wenn das Depot (mom, Basis-Kosten) mit G1 in Validierung UND Holdout eine höhere
     CAGR hat als mit G0. Sonst kein Ruhe-Filter (G0). Je Trade wird zusätzlich Ø R berichtet.
  E2 Rangfolge: Wechsel weg von „mom“ nur, wenn eine andere Rangfolge (mit der Regel aus E1) in Train, Validierung UND
     Holdout eine höhere CAGR hat.
  E3 Asien (nie in einem Test verwendet, Kurse 2008–2026 neu geladen): Kairo-Treffer in Asien gelten als getestet, wenn
     Ø R netto je Trade (Regel aus E1) in allen drei Abschnitten > 0 ist. Die Ruhe-Regel gilt in Asien als bestätigt, wenn
     G1-Trades je Trade besser sind als G0-Trades und gepoolt p ≤ 0,05 (Permutation, ruhig vs. unruhig).
Vorbehalt: Train/Validierung/Holdout USA/Europa wurden schon oft angeschaut; die Ruhe-Schwellen stammen aus diesen Trades.

python -m research.strategy_championship.v2_test trades --data v1 --signals S --gate 0|1 --out OUT
python -m research.strategy_championship.v2_test depot  --data v1 --signals S --gate 0|1 --prio mom --out OUT
python -m research.strategy_championship.v2_test asia   --shard K --shards N --out OUT
python -m research.strategy_championship.v2_test report --dir DIR
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import s01
from .data import PERIODS, adjusted, load
from .engine import Costs, Order, run

CALM_TIGHT, CALM_CHOP = 1.5, 1.65
HOLD = 60          # Kairo-Regel B60 (spätestens Tag 60). Erster Lauf 29.10. versehentlich mit 40 – Wiederholung mit 60.
AB = ("Train", "Validierung", "Holdout")
_G: dict = {}


def calm_arrays(adj: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """tight5 und chop10 je Tag (Kurse bis einschließlich dieses Tags) – dieselben Formeln wie backend/scanner.py."""
    h, l, c = (adj[k].to_numpy(float) for k in ("High", "Low", "Close"))
    n = len(c)
    tr = np.full(n, np.nan)
    tr[1:] = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    a14 = pd.Series(tr).rolling(14).mean().to_numpy()
    hi5, lo5 = pd.Series(h).rolling(5).max().to_numpy(), pd.Series(l).rolling(5).min().to_numpy()
    hi10, lo10 = pd.Series(h).rolling(10).max().to_numpy(), pd.Series(l).rolling(10).min().to_numpy()
    mv = pd.Series(np.abs(np.diff(c, prepend=np.nan))).rolling(10).sum().to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        tight = (hi5 - lo5) / a14
        chop = mv / (hi10 - lo10)
    return tight, chop


def base_orders(t: str, sig_i: int, atr_adj: float, gid: str, gate: int, prio_kind: str, sig_meta: dict,
                risk_frac: float = 0.01, hold: int = HOLD) -> list[Order]:
    """s01.base_orders (Variante B) + optional Ruhe-Filter am Basis-Tag + Rangfolge."""
    adj = _G["adj"][t]
    tight, chop = _G["calm"][t]
    lo_, hi_, f = adj["Low"].to_numpy(float), adj["High"].to_numpy(float), adj["f"].to_numpy(float)
    if not (atr_adj > 0):
        return []
    inv = lo_[max(0, sig_i - 9): sig_i + 1].min()
    out = []
    for j in range(s01.WAIT):
        k = sig_i + 1 + j
        if k >= len(adj) - 1:
            break
        if lo_[k] < inv:
            break
        if j < s01.CK - 1:
            continue
        hi, lo = hi_[k - s01.CK + 1: k + 1].max(), lo_[k - s01.CK + 1: k + 1].min()
        if hi - lo > s01.CM * atr_adj:
            continue
        if gate and not (tight[k] <= CALM_TIGHT and chop[k] <= CALM_CHOP):
            continue
        if prio_kind == "mom":
            p = -sig_meta["mom"] if np.isfinite(sig_meta["mom"]) else -9.0
        elif prio_kind == "vol":
            p = -(atr_adj / sig_meta["close"])
        elif prio_kind == "chop":
            p = -float(chop[k]) if np.isfinite(chop[k]) else -9.0
        elif prio_kind == "score":
            p = float(sig_meta["score"])
        else:
            p = float(sig_meta["rnd"])
        fk = f[k]
        out.append(Order(adj.index[k], t, stop=(lo - s01.BUF * atr_adj) / fk, risk_frac=risk_frac, prio=p, tag=gid,
                         entry_band=(lo / fk, hi / fk), atr=atr_adj / fk, risk_atr=s01.RISK, group=gid,
                         max_days=hold, exit_rule=("ema", 10)))
    return out


def _setup(data: str, sig_path: str, prices=None, cur=None, fx=None, start=None, end=None):
    sig = pd.read_parquet(sig_path)
    if prices is None:
        prices, cur, fx, _b, (start, end) = load(data, "full")
    prices = {t: df for t, df in prices.items() if len(s01.clean(df)) >= 300}
    adj = {t: adjusted(s01.clean(df)) for t, df in prices.items()}
    raw = {t: s01.with_ema(df) for t, df in prices.items()}
    cal = pd.DatetimeIndex(sorted(set().union(*[f.index[(f.index >= start) & (f.index <= end)] for f in raw.values()])))
    _G.update(prices=prices, adj=adj, raw=raw, cur=cur, fx=fx, cal=cal, calm={t: calm_arrays(a) for t, a in adj.items()})
    sig = sig[sig["ticker"].isin(prices)].copy()
    rng = np.random.default_rng(7)
    meta = []
    for r in sig.itertuples(index=False):
        C = adj[r.ticker]["Close"].to_numpy(float)
        i = int(r.i)
        meta.append({"mom": float(C[i - 21] / C[i - 126] - 1) if i >= 126 else np.nan, "close": float(C[i]),
                     "score": float(getattr(r, "score", 0) or 0), "rnd": float(rng.random())})
    return sig, meta


def abschnitt(d: pd.Series) -> np.ndarray:
    return np.select([d <= pd.Timestamp(PERIODS["train"][1]), d <= pd.Timestamp(PERIODS["validation"][1])],
                     ["Train", "Validierung"], "Holdout")


def per_trade(sig, meta, gate: int) -> pd.DataFrame:
    orders = []
    for r, m in zip(sig.itertuples(index=False), meta):
        orders += base_orders(r.ticker, int(r.i), float(r.atr), f"{r.ticker}|{pd.Timestamp(r.date).date()}", gate, "mom", m)
    res = run(_G["raw"], _G["cur"], _G["fx"], orders, 1e9, Costs(fee_eur=0.0, spread=0.001), 10 ** 6,
              calendar=_G["cal"], min_fill=0.0)
    t = res.trades.copy()
    if not len(t):
        return t
    t["R"] = t["pnl_eur"] / t["risk_eur"]
    t["abschnitt"] = abschnitt(pd.to_datetime(t["tag"].str.split("|").str[1]))
    stop_dist = (t["entry_px"] - t["stop"]) / t["entry_px"]
    val = 50.0 / stop_dist.clip(lower=1e-4)
    t["R_net_5000"] = t["R"] - np.where(val.clip(upper=5000) >= 250, 0.0, 0.99) * 2 / 50.0
    t["gate"] = gate
    return t


def depot(sig, meta, gate: int, prio: str, cash: float = 5000, max_open: int = 5) -> dict:
    from .d_run import stats
    from .wave1 import spreads
    from .data import UNIVERSE
    uni = pd.read_csv(UNIVERSE)
    sp = spreads(_G["raw"], _G["cur"], dict(zip(uni["ticker"], uni["region"])))
    costs = {"base": Costs(fee_eur=0.99, spread=0.001, spread_by_ticker=sp, fee_free_from=250.0),
             "stress": Costs(fee_eur=1.99, spread=0.002, slippage=0.0005, fx_fee=0.001, fee_free_from=250.0,
                             spread_by_ticker={k: 2 * v for k, v in sp.items()})}
    orders = []
    for r, m in zip(sig.itertuples(index=False), meta):
        orders += base_orders(r.ticker, int(r.i), float(r.atr), f"{r.ticker}|{pd.Timestamp(r.date).date()}", gate, prio, m)
    out = {}
    for cn, c in costs.items():
        res = run(_G["raw"], _G["cur"], _G["fx"], orders, cash, c, max_open, calendar=_G["cal"], min_fill=0.5)
        e = res.equity.dropna()
        seg = {"gesamt": stats(e)}
        for ab, key in zip(AB, ("train", "validation", "holdout")):
            a, b = PERIODS[key]
            s = e[(e.index >= pd.Timestamp(a)) & (e.index <= pd.Timestamp(b))]
            seg[ab] = stats(s) if len(s) > 20 else None
        seg["trades"] = int(len(res.trades))
        out[cn] = seg
    return out


# ------------------------------------------------------------------ Asien
def asia(a) -> None:
    """Kurse laden (eigener Shard), Treffer mit dem unveränderten Scanner, Trades G0/G1 je Trade."""
    import io
    import urllib.request
    import time
    import yfinance as yf
    uni = pd.read_csv(a.universe)
    uni = uni.sort_values("ticker")
    mine = uni.iloc[a.shard::a.shards]
    rows = []
    tick = list(mine["ticker"])
    for i in range(0, len(tick), 60):
        part = tick[i:i + 60]
        d = None
        for att in range(4):
            try:
                d = yf.download(part, start="2005-01-01", end="2026-10-17", interval="1d", auto_adjust=False, actions=False,
                                group_by="ticker", progress=False, threads=True)
                break
            except Exception as exc:
                print("Fehler", repr(exc)[:100]); time.sleep(10 * 2 ** att)
        if d is None or d.empty:
            continue
        for t in part:
            try:
                x = d[t] if isinstance(d.columns, pd.MultiIndex) else d
            except KeyError:
                continue
            x = x.dropna(subset=["Close"]).rename(columns={"Adj Close": "AdjClose"})
            if len(x) < 300 or "AdjClose" not in x:
                continue
            x = x[["Open", "High", "Low", "Close", "AdjClose", "Volume"]]
            x.index = pd.to_datetime(x.index).tz_localize(None)
            rows.append((t, x))
        print(f"  {min(i + 60, len(tick))}/{len(tick)} geladen", flush=True)
        time.sleep(2)
    curmap = dict(zip(uni["ticker"], uni["currency"].fillna("USD")))
    start, end = pd.Timestamp(PERIODS["full"][0]), pd.Timestamp(PERIODS["full"][1])
    prices = {t: x[x.index <= end] for t, x in rows}
    from multiprocessing import Pool
    with Pool() as pool:
        sigs = pool.starmap(s01.signals, [(prices[t], curmap.get(t, "USD"), start, end, t) for t in prices])
    S = pd.DataFrame([s for l in sigs for s in l])
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    print(f"Shard {a.shard}: {len(prices)} Aktien, {len(S)} Treffer", flush=True)
    if not len(S):
        return
    S.to_parquet(out / f"asia_sig_{a.shard}.parquet", index=False)
    cur = {t: "EUR" for t in prices}                        # R je Trade ist währungsfrei – keine Umrechnung nötig
    sig, meta = _setup(None, out / f"asia_sig_{a.shard}.parquet", prices, cur, {}, start, end)
    for g in (0, 1):
        t = per_trade(sig, meta, g)
        t.to_csv(out / f"asia_trades_g{g}_{a.shard}.csv", index=False)
        print(f"  G{g}: {len(t)} Trades, Ø R netto {t['R_net_5000'].mean() if len(t) else float('nan'):+.3f}", flush=True)


# ------------------------------------------------------------------ Bericht
def perm_p(x, y, n=10000, seed=1):
    rng = np.random.default_rng(seed); obs = x.mean() - y.mean(); z = np.concatenate([x, y]); k = len(x); c = 0
    for _ in range(n):
        rng.shuffle(z); c += (z[:k].mean() - z[k:].mean()) >= obs
    return (c + 1) / (n + 1)


def report(d: Path) -> None:
    L = []
    p = lambda s="": (print(s), L.append(s))
    p("## E1 Ruhe-Filter am Kauftag (USA/Europa)\n")
    tr = {g: pd.read_csv(d / f"trades_g{g}.csv") for g in (0, 1) if (d / f"trades_g{g}.csv").exists()}
    if tr:
        p("| | " + " | ".join(AB) + " |\n|---|---|---|---|")
        for g, t in tr.items():
            p(f"| G{g} je Trade | " + " | ".join(f"{t[t.abschnitt == ab]['R_net_5000'].mean():+.3f} R (n {int((t.abschnitt == ab).sum())}, Σ {t[t.abschnitt == ab]['R_net_5000'].sum():+.0f})" for ab in AB) + " |")
    dep = {}
    for f in sorted(d.glob("depot_g*_*.json")):
        g, pr = f.stem.split("_")[1:3]
        dep[(int(g[1]), pr)] = json.loads(f.read_text())
    p("\nDepot 5.000 €, max. 5 Positionen, 1 % Risiko – CAGR / max. Drawdown (Basis-Kosten; Stress in Klammern):\n")
    p("| Variante | " + " | ".join(AB) + " | gesamt | Trades |\n|---|---|---|---|---|---|")
    for (g, pr), r in sorted(dep.items()):
        b, s = r["base"], r["stress"]
        cell = lambda ab: f"{b[ab]['cagr']:+.1%} / {b[ab]['max_dd']:.0%} ({s[ab]['cagr']:+.1%})" if b.get(ab) else "–"
        p(f"| G{g} · {pr} | " + " | ".join(cell(ab) for ab in AB) + f" | {cell('gesamt')} | {b['trades']} |")
    if (0, "mom") in dep and (1, "mom") in dep:
        a0, a1 = dep[(0, "mom")]["base"], dep[(1, "mom")]["base"]
        e1 = all(a1[ab]["cagr"] > a0[ab]["cagr"] for ab in AB[1:])
        p(f"\n**E1:** G1 vs. G0 (mom, Basis): Validierung {a1['Validierung']['cagr']:+.1%} vs. {a0['Validierung']['cagr']:+.1%}, "
          f"Holdout {a1['Holdout']['cagr']:+.1%} vs. {a0['Holdout']['cagr']:+.1%} → {'BESTANDEN – Ruhe-Filter am Kauftag' if e1 else 'nicht bestanden – kein Ruhe-Filter'}")
        g = 1 if e1 else 0
        ref = dep[(g, "mom")]["base"]
        p(f"\n**E2 (Rangfolge, mit G{g}):**")
        for (gg, pr), r in sorted(dep.items()):
            if gg != g or pr == "mom":
                continue
            ok = all(r["base"][ab]["cagr"] > ref[ab]["cagr"] for ab in AB)
            p(f"- {pr}: " + ", ".join(f"{ab} {r['base'][ab]['cagr']:+.1%} vs. {ref[ab]['cagr']:+.1%}" for ab in AB) + (" → BESSER in allen drei" if ok else " → nein"))
    p("\n## E3 Asien (unabhängig)\n")
    for g in (0, 1):
        fs = sorted(d.glob(f"asia_trades_g{g}_*.csv"))
        if not fs:
            continue
        t = pd.concat([pd.read_csv(f) for f in fs])
        tr[f"a{g}"] = t
        p(f"- G{g}: " + ", ".join(f"{ab} {t[t.abschnitt == ab]['R_net_5000'].mean():+.3f} R (n {int((t.abschnitt == ab).sum())})" for ab in AB))
    if "a0" in tr and "a1" in tr:
        a0, a1 = tr["a0"], tr["a1"]
        calm_tags = set(a1["tag"])
        x = a0[a0["tag"].isin(calm_tags)]["R_net_5000"].to_numpy()
        y = a0[~a0["tag"].isin(calm_tags)]["R_net_5000"].to_numpy()
        pp = perm_p(a1["R_net_5000"].to_numpy(), y) if len(y) else float("nan")
        g_used = 1 if "BESTANDEN – Ruhe" in "\n".join(L) else 0
        tt = tr[f"a{g_used}"]
        ok3 = all(tt[tt.abschnitt == ab]["R_net_5000"].mean() > 0 for ab in AB)
        p(f"\nRuhe in Asien: G1-Trades Ø {a1['R_net_5000'].mean():+.3f} R (n {len(a1)}) vs. G0 ohne ruhigen Basis-Tag Ø {y.mean() if len(y) else float('nan'):+.3f} R (n {len(y)}), p {pp:.4f}"
          f" → {'bestätigt' if a1['R_net_5000'].mean() > a0['R_net_5000'].mean() and pp <= 0.05 else 'nicht bestätigt'}")
        p(f"Asien als getestet (G{g_used}, Ø R > 0 in allen drei Abschnitten): {'JA' if ok3 else 'NEIN'}")
    (d / "v2_report.md").write_text("\n".join(L), encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["trades", "depot", "asia", "report"])
    ap.add_argument("--data"); ap.add_argument("--signals"); ap.add_argument("--out", default="v2_out")
    ap.add_argument("--gate", type=int, default=0); ap.add_argument("--prio", default="mom")
    ap.add_argument("--shard", type=int, default=0); ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--universe", default="universe_asia.csv"); ap.add_argument("--dir")
    a = ap.parse_args(argv)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    if a.cmd == "report":
        report(Path(a.dir)); return 0
    if a.cmd == "asia":
        asia(a); return 0
    sig, meta = _setup(a.data, a.signals)
    if a.cmd == "trades":
        t = per_trade(sig, meta, a.gate)
        t.to_csv(out / f"trades_g{a.gate}.csv", index=False)
        print(f"G{a.gate}: {len(t)} Trades · " + ", ".join(f"{ab} {t[t.abschnitt == ab]['R_net_5000'].mean():+.3f}" for ab in AB))
    else:
        r = depot(sig, meta, a.gate, a.prio)
        (out / f"depot_g{a.gate}_{a.prio}.json").write_text(json.dumps(r, indent=1, default=str))
        print(f"G{a.gate} {a.prio}: " + ", ".join(f"{ab} {r['base'][ab]['cagr']:+.1%}" for ab in AB if r['base'].get(ab)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
