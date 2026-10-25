import sys, numpy as np, pandas as pd
S = sys.argv[1]
t = pd.read_csv(f"{S}/ins/kairo_trades.csv")
t["ticker_n"] = t["ticker"]
t = t[~t["ticker"].str.contains(r"\.", regex=True)].copy()            # nur US
t["sig"] = pd.to_datetime(t["tag"].str.split("|").str[1])
t = t[t["sig"] <= "2026-03-31"]
ib = pd.read_csv(f"{S}/ins/insider_buys.csv.gz", parse_dates=["filed", "trans_date"])
ib = ib[(ib["shares"] * ib["price"]) >= 10_000].dropna(subset=["symbol"])
ib["sym"] = ib["symbol"].str.upper().str.replace(".", "-", regex=False)
# Routine: Käufe desselben Insiders im selben Kalendermonat in beiden Vorjahren
ib["ym"] = ib["trans_date"].dt.to_period("M")
months = ib.groupby("owner")["ym"].apply(set).to_dict()
ib["opp"] = [not ((ym - 12) in months[o] and (ym - 24) in months[o]) for o, ym in zip(ib["owner"], ib["ym"])]
by = {s: g for s, g in ib.groupby("sym")}
A = B = C = None
fa, fb, fc = [], [], []
for tk, d in zip(t["ticker"], t["sig"]):
    g = by.get(tk.upper())
    if g is None:
        fa.append(False); fb.append(False); fc.append(False); continue
    w = g[(g["filed"] <= d) & (g["trans_date"] >= d - pd.Timedelta(days=90)) & (g["trans_date"] <= d)]
    fb.append(len(w) > 0); fa.append(bool(w["opp"].any())); fc.append(w["owner"].nunique() >= 2)
t["A"], t["B"], t["C"] = fa, fb, fc
def perm_p(x, y, n=10000, seed=1):
    rng = np.random.default_rng(seed); obs = x.mean() - y.mean(); z = np.concatenate([x, y]); k = len(x); c = 0
    for _ in range(n):
        rng.shuffle(z); c += (z[:k].mean() - z[k:].mean()) >= obs
    return (c + 1) / (n + 1)
print("US-Trades:", len(t), {ab: int((t["abschnitt"] == ab).sum()) for ab in ("Train", "Validierung", "Holdout")})
for f in "ABC":
    row = []
    ok = True
    for ab in ("Train", "Validierung", "Holdout"):
        s = t[t["abschnitt"] == ab]
        y, n_ = s.loc[s[f], "R_net_5000"], s.loc[~s[f], "R_net_5000"]
        row.append(f"{ab}: mit {y.mean():+.3f} (n {len(y)}) / ohne {n_.mean():+.3f} (n {len(n_)})")
        ok &= y.mean() > n_.mean()
    o = t[t["abschnitt"].isin(["Validierung", "Holdout"])]
    p = perm_p(o.loc[o[f], "R_net_5000"].to_numpy(), o.loc[~o[f], "R_net_5000"].to_numpy())
    win = {ab: (round(float((t[(t.abschnitt == ab) & t[f]]["R_net_5000"] > 0).mean()), 3)) for ab in ("Train", "Validierung", "Holdout")}
    print(f"\n{f}: " + " | ".join(row) + f"\n   Richtung in allen: {ok} · p gepoolt {p:.4f} · Trefferquote mit Merkmal {win} → {'BESTANDEN' if ok and p <= 0.05 / 3 else 'nicht bestanden'}")
