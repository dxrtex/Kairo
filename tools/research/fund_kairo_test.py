"""Fundamentaldaten-Test für Kairo-Treffer (Plan: docs/FUND_TEST_PLAN.md).
Aufruf: python fund_kairo_test.py <scratch>   (erwartet ins/kairo_trades.csv, v1/*.parquet, fund/*)"""
import sys, numpy as np, pandas as pd

S = sys.argv[1]
AB = ("Train", "Validierung", "Holdout")
t = pd.read_csv(f"{S}/ins/kairo_trades.csv")
t = t[~t["ticker"].str.contains(r"\.", regex=True)].copy()
t["sig"] = pd.to_datetime(t["tag"].str.split("|").str[1])
t["entry_date"] = pd.to_datetime(t["entry_date"])
t = t[t["sig"] <= "2026-03-31"].reset_index(drop=True)

cm = pd.read_csv(f"{S}/fund/cik_map.csv")
cik = dict(zip(cm["ticker"].str.upper(), cm["cik"]))
ft = pd.read_csv(f"{S}/fund/fund_timeline.csv.gz", parse_dates=["avail", "shares_end"])
ft = ft.sort_values("avail")
fby = {c: g.reset_index(drop=True) for c, g in ft.groupby("cik")}
sp = pd.read_csv(f"{S}/fund/splits.csv", parse_dates=["date"])
sby = {k: g for k, g in sp.groupby("ticker")}

px = pd.read_parquet(f"{S}/v1/prices_v1.parquet", columns=["date", "Close", "AdjClose", "ticker"])
px = px[px["ticker"].isin(set(t["ticker"]) | {"SPY"})]
px["date"] = pd.to_datetime(px["date"])
pby = {k: g.set_index("date").sort_index() for k, g in px.groupby("ticker")}
bn = pd.read_parquet(f"{S}/v1/bench_v1.parquet")
bn["date"] = pd.to_datetime(bn["date"])
spy = bn[bn["ticker"] == "SPY"].set_index("date").sort_index()["AdjClose"]


def split_factor(tk, after):
    g = sby.get(tk)
    if g is None or pd.isna(after):
        return 1.0
    return float(g.loc[g["date"] > after, "ratio"].prod())


def snap(f, d):
    i = f["avail"].searchsorted(d, side="right") - 1
    return None if i < 0 else f.iloc[i]


def pe_at(tk, f, d, close):
    r = snap(f, d)
    if r is None or not (r["ni_ttm"] > 0) or not (r["shares"] > 0):
        return np.nan
    return close * r["shares"] * split_factor(tk, r["shares_end"]) / r["ni_ttm"]


Q, V, nofund = [], [], 0
for tk, d in zip(t["ticker"], t["sig"]):
    c = cik.get(tk.upper()); f = fby.get(c); p = pby.get(tk)
    if f is None or p is None:
        Q.append(np.nan); V.append(np.nan); nofund += 1; continue
    r = snap(f, d)
    if r is None:
        Q.append(np.nan); V.append(np.nan); continue
    q = (r["ni_ttm"] > 0) and (r["ocf_ttm"] > 0) and (r["gpa"] >= 0.25)
    Q.append(np.nan if pd.isna(r["ni_ttm"]) or pd.isna(r["ocf_ttm"]) or pd.isna(r["gpa"]) else bool(q))
    cl = p["Close"]
    now = cl[:d]
    if not len(now):
        V.append(np.nan); continue
    pe0 = pe_at(tk, f, d, now.iloc[-1])
    hist = []
    for m in pd.date_range(d - pd.DateOffset(years=5), d - pd.DateOffset(months=1), freq="ME"):
        w = cl[:m]
        if len(w) and (m - w.index[-1]).days < 10:
            v = pe_at(tk, f, m, w.iloc[-1])
            if v == v:
                hist.append(v)
    V.append(bool(pe0 < np.median(hist)) if len(hist) >= 36 and pe0 == pe0 else (False if len(hist) >= 36 else np.nan))
t["Q"], t["V"] = Q, V
t["QV"] = [(q is True or q == 1) and (v is True or v == 1) if (q == q and v == v) else np.nan for q, v in zip(Q, V)]


def perm_p(x, y, n=10000, seed=1):
    rng = np.random.default_rng(seed); obs = x.mean() - y.mean(); z = np.concatenate([x, y]); k = len(x); c = 0
    for _ in range(n):
        rng.shuffle(z); c += (z[:k].mean() - z[k:].mean()) >= obs
    return (c + 1) / (n + 1)


print(f"US-Trades: {len(t)} · ohne SEC-Daten: {nofund} · Q bestimmbar: {t['Q'].notna().sum()} · V bestimmbar: {t['V'].notna().sum()}")
print("\n=== Test 1: Ø R netto mit / ohne Merkmal ===")
passed = {}
for f in ("Q", "V", "QV"):
    s0 = t[t[f].notna()].copy(); s0[f] = s0[f].astype(bool)
    ok, row = True, []
    for ab in AB:
        s = s0[s0["abschnitt"] == ab]
        y, n_ = s.loc[s[f], "R_net_5000"], s.loc[~s[f], "R_net_5000"]
        row.append(f"{ab}: mit {y.mean():+.3f} (n {len(y)}, Quote {(y > 0).mean():.0%}) / ohne {n_.mean():+.3f} (n {len(n_)})")
        ok &= y.mean() > n_.mean()
    o = s0[s0["abschnitt"].isin(AB[1:])]
    p = perm_p(o.loc[o[f], "R_net_5000"].to_numpy(), o.loc[~o[f], "R_net_5000"].to_numpy())
    passed[f] = ok and p <= 0.05 / 3
    print(f"{f}: " + "\n   ".join(row) + f"\n   Richtung überall: {ok} · p gepoolt {p:.4f} → {'BESTANDEN' if passed[f] else 'nicht bestanden'}")

print("\n=== Test 2: Q-Treffer 12 Monate halten statt Kairo-Ausstieg ===")
H, COST = 252, 0.002


def hold(tk, d0, entry_px=None):
    a = pby[tk]
    w = a[a.index >= d0]
    if len(w) < 30:
        return None
    fac = w["AdjClose"].iloc[0] / w["Close"].iloc[0]
    e = (entry_px * fac) if entry_px else w["AdjClose"].iloc[0]
    j = min(H, len(w) - 1)
    r = w["AdjClose"].iloc[j] / e - 1 - COST
    s0, s1 = spy[:w.index[0]], spy[:w.index[j]]
    return r, s1.iloc[-1] / s0.iloc[-1] - 1, j


rng = np.random.default_rng(7)
q = t[t["Q"] == True].copy()
rows = []
for _, r in q.iterrows():
    h = hold(r["ticker"], r["entry_date"], r["entry_px"])
    if h is None:
        continue
    a = pby[r["ticker"]]
    cand = a.index[(a.index >= r["entry_date"] - pd.Timedelta(days=365)) & (a.index <= r["entry_date"] + pd.Timedelta(days=365))]
    rnd = [hold(r["ticker"], d) for d in rng.choice(cand, size=min(10, len(cand)), replace=False)] if len(cand) else []
    rnd = [x[0] - x[1] for x in rnd if x]
    kr = r["exit_px"] / r["entry_px"] - 1 - COST
    rows.append(dict(ab=r["abschnitt"], stop=r["why"].startswith("stop"), hold=h[0], spy=h[1], ex=h[0] - h[1],
                     rnd_ex=np.mean(rnd) if rnd else np.nan, kairo=kr, R=r["R_net_5000"], days=r["days"]))
d2 = pd.DataFrame(rows)
for ab in AB:
    s = d2[d2["ab"] == ab]
    st = s[s["stop"]]
    print(f"{ab} (n {len(s)}): 12M halten {s['hold'].mean():+.1%} · SPY gleicher Zeitraum {s['spy'].mean():+.1%} · "
          f"Mehrrendite {s['ex'].mean():+.1%} (Median {s['ex'].median():+.1%}) · zufälliges Timing Mehrrendite {s['rnd_ex'].mean():+.1%} · "
          f"Kairo-Regel {s['kairo'].mean():+.1%} in Ø {s['days'].mean():.0f} Tagen")
    print(f"   davon Stop-Trades (n {len(st)}): 12M später {st['hold'].mean():+.1%} vs SPY {st['spy'].mean():+.1%} · "
          f"Anteil über SPY {(st['ex'] > 0).mean():.0%} · Anteil über Einstieg {(st['hold'] > 0).mean():.0%}")
nq = t[t["Q"] == False]
rows = []
for _, r in nq.iterrows():
    h = hold(r["ticker"], r["entry_date"], r["entry_px"])
    if h:
        rows.append(dict(ab=r["abschnitt"], stop=r["why"].startswith("stop"), hold=h[0], ex=h[0] - h[1]))
d3 = pd.DataFrame(rows)
print("Vergleich ohne Qualität (Q=nein):")
for ab in AB:
    s = d3[d3["ab"] == ab]; st = s[s["stop"]]
    print(f"   {ab} (n {len(s)}): 12M halten Mehrrendite ggü. SPY {s['ex'].mean():+.1%} · Stop-Trades {st['ex'].mean():+.1%}")

if any(passed.values()):
    print("\n=== Test 3: Positionsgröße ===")
    for f, ok in passed.items():
        if not ok:
            continue
        s0 = t[t[f].notna()].sort_values("entry_date")
        w = np.where(s0[f].astype(bool), 1.5, 0.75)
        for ab in AB:
            m = (s0["abschnitt"] == ab).to_numpy(); r = s0["R_net_5000"].to_numpy()[m]
            eq1, eq2 = np.cumsum(r), np.cumsum(r * w[m])
            dd = lambda e: float((e - np.maximum.accumulate(np.r_[0, e])[1:]).min())
            print(f"{f} {ab}: Summe R gleich {eq1[-1]:+.0f} (DD {dd(eq1):.0f}) / gewichtet {eq2[-1]:+.0f} (DD {dd(eq2):.0f})")
else:
    print("\nTest 3 entfällt (kein Merkmal hat Test 1 bestanden).")
