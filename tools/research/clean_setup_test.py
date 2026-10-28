"""Saubere Setups messbar machen: Merkmale der Seitwärtsphase bzw. des Abverkaufs am Kauftag vs. Ergebnis (R netto).

Vorab festgelegt (28.10.2026): Ein Merkmal besteht, wenn das „sauberste“ Fünftel in Train, Validierung UND Holdout ein
höheres Ø R hat als die übrigen vier Fünftel und gepoolt (Validierung+Holdout) Permutations-p ≤ 0,05/Anzahl Merkmale.
Merkmale (am Tag vor dem Kauf, ohne Blick in die Zukunft):
  tight   Spanne der letzten 5 Kerzen / ATR14 (klein = enge Konsolidierung)
  chop    Hin und Her der letzten 10 Kerzen: Summe |Schlusskurs-Änderungen| / (Hoch−Tief) (klein = ruhig)
  hug     Ø Abstand der Schlusskurse der letzten 5 Tage zum Tief der Phase in ATR (klein = schmiegt sich an die Unterstützung)
  wicks   Anteil Kerzen mit langer unterer Lunte (≥ 50 % der Spanne) der letzten 5 Tage (groß = Käufer fangen ab)
  selloff Abverkauf vor der Phase: Rückgang vom 20-Tage-Hoch bis zum Tief der Phase in ATR (groß = starker Abverkauf)
  speed   selloff je Tag (groß = schneller, kräftiger Abverkauf)
  vdry    Volumen der Phase / Ø Volumen der 20 Tage davor (klein = Verkaufsdruck trocknet aus)
Aufruf: python clean_setup_test.py <scratch>   (ins/kairo_trades.csv, v1/prices_v1.parquet)
"""
import sys
import numpy as np
import pandas as pd

S = sys.argv[1]
AB = ("Train", "Validierung", "Holdout")
t = pd.read_csv(f"{S}/ins/kairo_trades.csv", parse_dates=["entry_date"])
px = pd.read_parquet(f"{S}/v1/prices_v1.parquet", columns=["date", "Open", "High", "Low", "Close", "Volume", "ticker"])
px["date"] = pd.to_datetime(px["date"])
px = px[px["ticker"].isin(set(t["ticker"]))]
P = {k: g.set_index("date").sort_index() for k, g in px.groupby("ticker")}


def feats(tk, d):
    x = P.get(tk)
    if x is None:
        return None
    w = x[x.index < d]
    if len(w) < 40:
        return None
    h, l, c, v = w["High"].to_numpy(), w["Low"].to_numpy(), w["Close"].to_numpy(), w["Volume"].to_numpy()
    tr = np.maximum(h[1:] - l[1:], np.maximum(abs(h[1:] - c[:-1]), abs(l[1:] - c[:-1])))
    atr = tr[-14:].mean()
    if not atr > 0:
        return None
    b_lo, b_hi = l[-5:].min(), h[-5:].max()
    c10 = c[-11:]
    rng10 = h[-10:].max() - l[-10:].min()
    hi20 = h[-25:-5].max()
    lowpos = int(np.argmin(l[-25:]))
    body_lo = np.minimum(w["Open"].to_numpy()[-5:], c[-5:])
    spans = (h[-5:] - l[-5:])
    wick = np.where(spans > 0, (body_lo - l[-5:]) / np.where(spans > 0, spans, 1), 0)
    v20 = v[-25:-5].mean()
    sell = (hi20 - b_lo) / atr
    days = max(1, 25 - lowpos)
    return {"tight": (b_hi - b_lo) / atr, "chop": np.abs(np.diff(c10)).sum() / rng10 if rng10 > 0 else np.nan,
            "hug": np.mean(c[-5:] - b_lo) / atr, "wicks": float((wick >= 0.5).mean()), "selloff": sell,
            "speed": sell / days, "vdry": v[-5:].mean() / v20 if v20 > 0 else np.nan}


rows = []
for r in t.itertuples():
    f = feats(r.ticker, r.entry_date)
    if f:
        rows.append({**f, "R": r.R_net_5000, "ab": r.abschnitt, "d": r.entry_date})
D = pd.DataFrame(rows)
print(f"Trades mit Merkmalen: {len(D)} von {len(t)}")
CLEAN = {"tight": "low", "chop": "low", "hug": "low", "wicks": "high", "selloff": "high", "speed": "high", "vdry": "low"}


def perm_p(x, y, n=5000, seed=1):
    rng = np.random.default_rng(seed); obs = x.mean() - y.mean(); z = np.concatenate([x, y]); k = len(x); c = 0
    for _ in range(n):
        rng.shuffle(z); c += (z[:k].mean() - z[k:].mean()) >= obs
    return (c + 1) / (n + 1)


res = {}
for f, side in CLEAN.items():
    d = D.dropna(subset=[f]).copy()
    out, ok = [], True
    for ab in AB:
        s = d[d["ab"] == ab]
        q = s[f].quantile(0.2 if side == "low" else 0.8)
        top = s[s[f] <= q] if side == "low" else s[s[f] >= q]
        rest = s.drop(top.index)
        out.append(f"{ab}: sauber {top['R'].mean():+.3f} (n {len(top)}, Quote {(top['R'] > 0).mean():.0%}) / Rest {rest['R'].mean():+.3f}")
        ok &= top["R"].mean() > rest["R"].mean()
    o = d[d["ab"].isin(AB[1:])]
    qq = {ab: o[o["ab"] == ab][f].quantile(0.2 if side == "low" else 0.8) for ab in AB[1:]}
    m = o.apply(lambda r: r[f] <= qq[r["ab"]] if side == "low" else r[f] >= qq[r["ab"]], axis=1)
    p = perm_p(o.loc[m, "R"].to_numpy(), o.loc[~m, "R"].to_numpy())
    res[f] = ok and p <= 0.05 / len(CLEAN)
    print(f"\n{f} ({'klein' if side == 'low' else 'groß'} = sauber):\n  " + "\n  ".join(out) + f"\n  überall besser: {ok} · p {p:.4f} → {'BESTANDEN' if res[f] else 'nicht bestanden'}")

# Kombination der bestandenen Merkmale (Rangsumme) – nur zur Beschreibung, nicht vorab getestet
good = [f for f, v in res.items() if v]
if good:
    D2 = D.dropna(subset=good).copy()
    for f in good:
        D2[f + "_r"] = D2.groupby("ab")[f].rank(pct=True, ascending=CLEAN[f] == "low")
    D2["score"] = D2[[f + "_r" for f in good]].mean(axis=1)
    print("\nKombination (beschreibend):", good)
    for ab in AB:
        s = D2[D2["ab"] == ab]
        for qq in (0.5, 0.75, 0.9):
            top = s[s["score"] >= s["score"].quantile(qq)]
            print(f"  {ab} oberste {int((1 - qq) * 100)} %: Ø R {top['R'].mean():+.3f} (n {len(top)}, Quote {(top['R'] > 0).mean():.0%}) · alle {s['R'].mean():+.3f}")

# Nachträglich (NICHT vorab festgelegt, nur beschreibend): tight + chop zusammen
D3 = D.dropna(subset=["tight", "chop"]).copy()
for f in ("tight", "chop"):
    D3[f + "_r"] = D3.groupby("ab")[f].rank(pct=True, ascending=False)   # 1 = am saubersten
D3["ruhe"] = (D3["tight_r"] + D3["chop_r"]) / 2
print("\nNachträglich, beschreibend: Ruhe-Score aus tight + chop")
for ab in AB:
    s = D3[D3["ab"] == ab]
    parts = []
    for qq in (0.5, 0.8, 0.9):
        top = s[s["ruhe"] >= s["ruhe"].quantile(qq)]
        parts.append(f"oberste {int(round((1 - qq) * 100))} %: {top['R'].mean():+.3f} R (n {len(top)}, Quote {(top['R'] > 0).mean():.0%})")
    bot = s[s["ruhe"] <= s["ruhe"].quantile(0.5)]
    print(f"  {ab}: alle {s['R'].mean():+.3f} · untere Hälfte {bot['R'].mean():+.3f} · " + " · ".join(parts))
