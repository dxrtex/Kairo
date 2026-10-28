"""Fib-Tiefe der Konsolidierung vs. Ergebnis (R netto) der Kairo-Trades.

Vorab festgelegt (28.10.2026): Für jeden Trade wird mit dem echten Scanner (Daten bis zum Tag vor dem Kauf) der Impuls
L→H bestimmt. Tiefe = (H − Tief der letzten 5 Kerzen) / (H − L). Eimer: < 0,618 · 0,618–0,706 · 0,706–0,79 · 0,79–0,886 · ≥ 0,886.
Eine Level-Regel besteht, wenn ein Eimer in Train, Validierung UND Holdout ein höheres Ø R hat als alle übrigen Trades
und gepoolt (Validierung+Holdout) Permutations-p ≤ 0,05/5.
Aufruf: python fib_level_test.py <scratch>   (ins/kairo_trades.csv, v1/prices_v1.parquet)
"""
import sys
import numpy as np
import pandas as pd
from backend.scanner import evaluate

S = sys.argv[1]
AB = ("Train", "Validierung", "Holdout")
t = pd.read_csv(f"{S}/ins/kairo_trades.csv", parse_dates=["entry_date"])
px = pd.read_parquet(f"{S}/v1/prices_v1.parquet", columns=["date", "Open", "High", "Low", "Close", "Volume", "ticker"])
px["date"] = pd.to_datetime(px["date"])
px = px[px["ticker"].isin(set(t["ticker"]))]
P = {k: g.drop(columns="ticker").set_index("date").sort_index() for k, g in px.groupby("ticker")}
EDGES = [-np.inf, 0.618, 0.706, 0.79, 0.886, np.inf]
NAMES = ["< 0,618", "0,618–0,706", "0,706–0,79", "0,79–0,886", "≥ 0,886"]

rows = []
for k, r in enumerate(t.itertuples()):
    x = P.get(r.ticker)
    if x is None:
        continue
    w = x[x.index < r.entry_date].tail(400)
    if len(w) < 260:
        continue
    try:
        res = evaluate(w, {}, ticker=r.ticker)
    except Exception:
        continue
    fz = res.zone.get("fib") if res.zone else None
    if not fz:
        continue
    H, L = res.zone["H"], fz["L"]
    low5 = float(w["Low"].tail(5).min())
    rows.append({"depth": (H - low5) / (H - L), "close_depth": (H - float(w["Close"].iloc[-1])) / (H - L),
                 "impulse": fz["impulse"], "fib_ok": bool(fz["ok"]), "R": r.R_net_5000, "ab": r.abschnitt})
    if k % 2000 == 0:
        print("…", k, flush=True)
D = pd.DataFrame(rows)
D["b"] = pd.cut(D["depth"], EDGES, labels=NAMES, right=False)
print(f"\nTrades mit Fib-Impuls: {len(D)} von {len(t)}")


def perm_p(a, b, n=5000, seed=1):
    rng = np.random.default_rng(seed); obs = a.mean() - b.mean(); z = np.concatenate([a, b]); m = len(a); c = 0
    for _ in range(n):
        rng.shuffle(z); c += (z[:m].mean() - z[m:].mean()) >= obs
    return (c + 1) / (n + 1)


print("\nØ R netto je Eimer (n, Gewinnquote):")
print(f"{'Eimer':<14}" + "".join(f"{ab:>28}" for ab in AB))
for nm in NAMES:
    line = f"{nm:<14}"
    for ab in AB:
        s = D[(D["b"] == nm) & (D["ab"] == ab)]
        line += f"{s['R'].mean():+.3f} R (n {len(s):>4}, {(s['R'] > 0).mean():>4.0%})".rjust(28) if len(s) else "–".rjust(28)
    print(line)
line = f"{'alle':<14}"
for ab in AB:
    s = D[D["ab"] == ab]
    line += f"{s['R'].mean():+.3f} R (n {len(s):>4}, {(s['R'] > 0).mean():>4.0%})".rjust(28)
print(line)

print("\nVorab-Regel je Eimer:")
for nm in NAMES:
    ok = all(D[(D["b"] == nm) & (D["ab"] == ab)]["R"].mean() > D[(D["b"] != nm) & (D["ab"] == ab)]["R"].mean() for ab in AB)
    o = D[D["ab"].isin(AB[1:])]
    a, b = o[o["b"] == nm]["R"].to_numpy(), o[o["b"] != nm]["R"].to_numpy()
    p = perm_p(a, b) if len(a) > 20 else 1.0
    print(f"  {nm:<14} überall besser: {ok} · p {p:.4f} → {'BESTANDEN' if ok and p <= 0.01 else 'nicht bestanden'}")

# beschreibend: Golden Pocket (0,706–0,79) vs. Rest der Fib-Zone, und Kombination mit Ruhe-Regel nicht möglich ohne Merkmale
print("\nBeschreibend – nur Trades mit gültiger Fib-Zone (fib_ok):")
for ab in AB:
    s = D[(D["ab"] == ab) & D["fib_ok"]]
    print(f"  {ab}: " + " · ".join(f"{nm} {s[s['b'] == nm]['R'].mean():+.3f} (n {(s['b'] == nm).sum()})" for nm in NAMES[1:4]))
print("\nBeschreibend – Tiefe nach Schlusskurs statt 5-Tage-Tief:")
D["cb"] = pd.cut(D["close_depth"], EDGES, labels=NAMES, right=False)
for ab in AB:
    s = D[D["ab"] == ab]
    print(f"  {ab}: " + " · ".join(f"{nm} {s[s['cb'] == nm]['R'].mean():+.3f} (n {(s['cb'] == nm).sum()})" for nm in NAMES))
D.to_csv(f"{S}/fib_levels.csv", index=False)
