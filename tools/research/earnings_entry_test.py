"""Kauf kurz vor Quartalszahlen: schlechter? (vorab festgelegt 28.10.2026)

US-Kairo-Trades; Quartalszahlen = SEC-8-K mit Punkt 2.02 (Results of Operations), Zeitpunkt der Annahme.
Gruppe „vor Zahlen“: Zahlen 0–10 Kalendertage nach dem Kauftag. Bestanden (→ Regel „nicht kurz vor Zahlen kaufen“), wenn
diese Trades in Train, Validierung UND Holdout ein schlechteres Ø R haben und gepoolt (Val+Holdout) p ≤ 0,05.
Aufruf: python earnings_entry_test.py <scratch>
"""
import sys
import numpy as np
import pandas as pd

S = sys.argv[1]
AB = ("Train", "Validierung", "Holdout")
t = pd.read_csv(f"{S}/ins/kairo_trades.csv", parse_dates=["entry_date"])
t = t[~t["ticker"].str.contains(r"\.", regex=True)].copy()
cm = pd.read_csv(f"{S}/fund/cik_map.csv")
cik = dict(zip(cm["ticker"].str.upper(), cm["cik"]))
f = pd.read_csv(f"{S}/fund/filings.csv.gz", dtype={"items": str})
f = f[(f["form"] == "8-K") & f["items"].fillna("").str.contains("2.02")]
f["at"] = pd.to_datetime(f["accepted"], utc=True).dt.tz_localize(None).dt.normalize()
E = {c: np.sort(g["at"].to_numpy()) for c, g in f.groupby("cik")}
pre, has = [], []
for tk, d in zip(t["ticker"], t["entry_date"]):
    e = E.get(cik.get(tk.upper()))
    if e is None:
        pre.append(np.nan); continue
    i = np.searchsorted(e, np.datetime64(d))
    nxt = e[i] if i < len(e) else None
    pre.append(bool(nxt is not None and (nxt - np.datetime64(d)) <= np.timedelta64(10, "D")))
t["pre"] = pre
t = t.dropna(subset=["pre"])
t["pre"] = t["pre"].astype(bool)
print(f"US-Trades mit SEC-Terminen: {len(t)} · davon Kauf ≤ 10 Tage vor Zahlen: {t['pre'].mean():.0%}")


def perm_p(x, y, n=10000, seed=1):
    rng = np.random.default_rng(seed); obs = y.mean() - x.mean(); z = np.concatenate([x, y]); k = len(x); c = 0
    for _ in range(n):
        rng.shuffle(z); c += (z[k:].mean() - z[:k].mean()) >= obs
    return (c + 1) / (n + 1)


ok = True
for ab in AB:
    s = t[t["abschnitt"] == ab]
    a, b = s[s["pre"]]["R_net_5000"], s[~s["pre"]]["R_net_5000"]
    ok &= a.mean() < b.mean()
    print(f"{ab}: vor Zahlen {a.mean():+.3f} R (n {len(a)}, Quote {(a > 0).mean():.0%}, Stop-Anteil {(s[s['pre']]['why'].str.startswith('stop')).mean():.0%}) · sonst {b.mean():+.3f} R (n {len(b)})")
o = t[t["abschnitt"].isin(AB[1:])]
p = perm_p(o[o["pre"]]["R_net_5000"].to_numpy(), o[~o["pre"]]["R_net_5000"].to_numpy())
print(f"überall schlechter: {ok} · p {p:.4f} → {'BESTANDEN: nicht kurz vor Zahlen kaufen' if ok and p <= 0.05 else 'nicht bestanden'}")
