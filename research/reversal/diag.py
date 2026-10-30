"""Kairo Reversal Ultimate – Phase 2: Diagnose der B60-Trades (EXPLORATIV, nur zur Hypothesenbildung).

Regel: Merkmals-Auswertungen nur im Train 2008–2016. Validierung, Holdout, Vorzeit 1999–2007 und Asien bleiben für die
späteren, vorab festgelegten Tests. Beschreibende Gesamtzahlen (woher kommt der Gewinn, Kosten, Kapital) über alle Jahre.
Alle Merkmale nur mit Kursen bis zum Entscheidungstag (Abend vor dem Kauf).

    python -m research.reversal.diag --data v1 --signals sig.parquet --sec sec --sectors sectors_v1.csv --out out
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.strategy_championship.data import PERIODS, load
from research.strategy_championship.engine import run
from research.ultimate import round1 as R

SECTOR_ETF = {"Technology": "XLK", "Financial Services": "XLF", "Energy": "XLE", "Healthcare": "XLV", "Industrials": "XLI",
              "Consumer Cyclical": "XLY", "Consumer Defensive": "XLP", "Utilities": "XLU", "Basic Materials": "XLB"}
TRAIN_END = pd.Timestamp(PERIODS["train"][1])


def series(df, col="AdjClose"):
    return df[col].astype(float)


def features(t: str, i: int, k: int, entry: float, stop: float, bench: dict, sector: dict) -> dict:
    a = R._G["adj"][t]
    H, L, C, V = (a[c].to_numpy(float) for c in ("High", "Low", "Close", "Volume"))
    idx = a.index
    reg = R._G["region"].get(t, "us")
    mk = series(bench["SPY" if reg != "eu" else "^STOXX"]).reindex(idx).ffill().to_numpy()
    sec_t = SECTOR_ETF.get(sector.get(t, ""))
    sx = series(bench[sec_t]).reindex(idx).ffill().to_numpy() if sec_t and sec_t in bench else None
    tr = np.maximum(H[1:] - L[1:], np.maximum(abs(H[1:] - C[:-1]), abs(L[1:] - C[:-1])))
    atr = pd.Series(np.r_[np.nan, tr]).rolling(14).mean().to_numpy()
    p = max(0, i - 120) + int(np.argmax(C[max(0, i - 120): i + 1]))           # Hoch vor dem Rückgang
    p0 = max(0, p - 252)
    out = {}
    lr = np.diff(np.log(C[p0: p + 1])) if p - p0 > 20 else np.array([])
    out["prior_run"] = C[p] / C[p0: p + 1].min() - 1 if p - p0 > 20 else np.nan
    out["prior_rs"] = (C[p] / C[p0] - 1) - (mk[p] / mk[p0] - 1) if p - p0 > 20 else np.nan
    out["prior_top5"] = np.sort(lr)[-5:].sum() / lr.sum() if len(lr) > 20 and lr.sum() > 0 else np.nan
    out["decline"] = C[i] / C[p] - 1
    out["decline_days"] = i - p
    mret = mk[i] / mk[p] - 1
    out["mkt_decline"] = mret
    if p - 252 >= 1:
        rs, rm = np.diff(np.log(C[p - 252: p + 1])), np.diff(np.log(mk[p - 252: p + 1]))
        ok = np.isfinite(rs) & np.isfinite(rm)
        beta = np.cov(rs[ok], rm[ok])[0, 1] / np.var(rm[ok]) if ok.sum() > 100 and np.var(rm[ok]) > 0 else 1.0
    else:
        beta = 1.0
    out["idio_decline"] = out["decline"] - beta * mret
    out["sector_decline"] = (sx[i] / sx[p] - 1) if sx is not None and np.isfinite(sx[p]) and sx[p] > 0 else np.nan
    out["idio_share"] = out["idio_decline"] / out["decline"] if out["decline"] < 0 else np.nan
    b0 = i + 1
    base = slice(b0, k + 1)
    out["rs_base"] = (C[k] / C[i] - 1) - (mk[k] / mk[i] - 1)
    out["rs10"] = (C[k] / C[k - 10] - 1) - (mk[k] / mk[k - 10] - 1)
    sig_low = L[max(0, i - 9): i + 1].min()
    out["higher_low_atr"] = (L[base].min() - sig_low) / atr[i] if atr[i] > 0 else np.nan
    dn_dec = [j for j in range(p + 1, i + 1) if C[j] < C[j - 1]]
    dn_base = [j for j in range(b0, k + 1) if C[j] < C[j - 1]]
    up_base = [j for j in range(b0, k + 1) if C[j] > C[j - 1]]
    vd = np.nanmean(V[dn_dec]) if dn_dec else np.nan
    out["vol_dry"] = np.nanmean(V[dn_base]) / vd if dn_base and vd and vd > 0 else np.nan
    out["vol_up_down"] = np.nanmean(V[up_base]) / np.nanmean(V[dn_base]) if up_base and dn_base else np.nan
    out["atr_contract"] = atr[k] / atr[i] if atr[i] > 0 else np.nan
    rg = H[base] - L[base]
    out["close_loc"] = float(np.nanmean(np.where(rg > 0, (C[base] - L[base]) / rg, 0.5)))
    out["down_size"] = float(np.nanmean([abs(C[j] / C[j - 1] - 1) for j in dn_base])) / (atr[k] / C[k]) if dn_base and atr[k] > 0 else np.nan
    out["stop_pct"] = (entry - stop) / entry
    side = R.stress_side(t)
    out["cost_R"] = 2 * side / out["stop_pct"] if out["stop_pct"] > 0 else np.nan
    adv = pd.Series(C * V).rolling(20).mean().to_numpy()
    out["log_adv"] = np.log10(adv[k]) if adv[k] > 0 else np.nan
    out["mom61"] = C[i - 21] / C[i - 126] - 1 if i >= 126 else np.nan
    m200 = pd.Series(mk).rolling(200).mean().to_numpy()
    out["mkt_up"] = float(mk[k] > m200[k]) if np.isfinite(m200[k]) else np.nan
    out["mkt_dd"] = mk[k] / np.nanmax(mk[max(0, k - 252): k + 1]) - 1
    out["base_days"] = k - i
    e = R._G["sec"].get(t.upper())
    if e is not None:
        prev = e[e <= np.datetime64(idx[k])]
        out["days_since_earn"] = (idx[k] - pd.Timestamp(prev[-1])).days if len(prev) else np.nan
        out["news_drop"] = float(R.news_drop(t, i))
    else:
        out["days_since_earn"], out["news_drop"] = np.nan, np.nan
    return out


def paths(t: str, entry_date, exit_date, entry_px: float, stop: float) -> dict:
    """Verlauf in R (Schlusskurse, ohne Kosten): Tag 5/10/20, höchster Stand (MFE), tiefster (MAE), und Tag 60→120 danach."""
    raw = R._G["raw"][t]
    c, h, l = raw["Close"].to_numpy(float), raw["High"].to_numpy(float), raw["Low"].to_numpy(float)
    j0 = raw.index.get_indexer([pd.Timestamp(entry_date)])[0]
    j1 = raw.index.get_indexer([pd.Timestamp(exit_date)])[0]
    risk = entry_px - stop
    if j0 < 0 or j1 < 0 or risk <= 0:
        return {}
    r = lambda x: (x - entry_px) / risk
    out = {f"R_d{d}": r(c[j0 + d - 1]) if j0 + d - 1 <= j1 else np.nan for d in (5, 10, 20)}
    out["MFE"] = r(h[j0: j1 + 1].max())
    out["MAE"] = r(l[j0: j1 + 1].min())
    out["after60"] = (c[min(len(c) - 1, j1 + 60)] / c[j1] - 1) if j1 + 1 < len(c) else np.nan
    return out


def qtable(df: pd.DataFrame, col: str, y: str = "R_stress", q: int = 5) -> list[str]:
    d = df[[col, y]].dropna()
    if len(d) < 200 or d[col].nunique() < 3:
        return []
    try:
        d["q"] = pd.qcut(d[col], q, labels=False, duplicates="drop")
    except ValueError:
        return []
    g = d.groupby("q").agg(lo=(col, "min"), hi=(col, "max"), n=(y, "size"), R=(y, "mean"), win=(y, lambda s: (s > 0).mean()))
    rho = d[[col, y]].corr(method="spearman").iloc[0, 1]
    rows = [f"| {col} | " + " | ".join(f"{r.lo:.3g}…{r.hi:.3g}: {r.R:+.3f} ({r.win:.0%}, n {r.n})" for r in g.itertuples()) + f" | {rho:+.3f} |"]
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data"); ap.add_argument("--signals"); ap.add_argument("--sec"); ap.add_argument("--sectors")
    ap.add_argument("--out", default="diag_out")
    a = ap.parse_args(argv)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    sig, meta = R.setup(a.data, a.signals, a.sec)
    _, _, _, bench, _ = load(a.data, "full", tickers=["__keine__"])
    sector = {}
    if a.sectors and Path(a.sectors).exists():
        sc = pd.read_csv(a.sectors)
        col = next((c for c in sc.columns if "sector" in c.lower()), None)
        if col:
            sector = dict(sc[["ticker", col]].dropna().values)
    t = R.per_trade(R.build(sig, meta, "E0", 1e-5))
    rows = []
    for x in t.itertuples(index=False):
        tk, sd = x.ticker, pd.Timestamp(x.signal_date)
        idx = R._G["adj"][tk].index
        i = idx.get_indexer([sd])[0]
        k = idx.get_indexer([pd.Timestamp(x.entry_date)])[0] - 1
        if i < 130 or k <= i:
            continue
        f = features(tk, i, k, x.entry_px, x.stop, bench, sector) | paths(tk, x.entry_date, x.exit_date, x.entry_px, x.stop)
        rows.append({"tag": x.tag, **f})
    F = t.merge(pd.DataFrame(rows), on="tag", how="inner")
    F.to_csv(out / "diag_trades.csv.gz", index=False)
    L = []
    p = lambda s="": (print(s), L.append(s))
    p("# Diagnose B60 (EXPLORATIV)\n")
    p(f"Trades mit Merkmalen: {len(F)} (alle Abschnitte). Merkmals-Tabellen nur Train 2008–2016.\n")
    # 1 Woher kommt der Gewinn
    for ab in ("Train", "Validierung", "Holdout"):
        s = F[F.abschnitt == ab].sort_values("R_stress", ascending=False)
        tot = s["R_stress"].sum()
        top = lambda f: s["R_stress"].head(max(1, int(len(s) * f))).sum()
        p(f"**{ab}** n {len(s)} · Σ R Stress {tot:+.0f} · Σ Basis {s['R_base'].sum():+.0f} · Ø {s['R_stress'].mean():+.3f} · Median {s['R_stress'].median():+.2f} · "
          f"Trefferquote {(s['R_stress'] > 0).mean():.0%} · Σ beste 1 % {top(.01):+.0f} · beste 5 % {top(.05):+.0f} · beste 10 % {top(.10):+.0f} · "
          f"Ø Tage {s['days'].mean():.0f}")
    p("\n## Ausstiegsgründe (alle Abschnitte)\n\n| Grund | Anteil | Ø R Stress | Σ R | Ø Tage |\n|---|---|---|---|---|")
    for why, g in F.groupby("why"):
        p(f"| {why} | {len(g) / len(F):.0%} | {g['R_stress'].mean():+.2f} | {g['R_stress'].sum():+.0f} | {g['days'].mean():.0f} |")
    p("\n## Kosten (alle Abschnitte): Basis − Stress je Trade nach Stop-Abstand\n\n| Stop-Abstand | n | Ø R Basis | Ø R Stress | Kosten Stress in R |\n|---|---|---|---|---|")
    F["sp_bin"] = pd.cut(F["stop_pct"], [0, 0.02, 0.03, 0.05, 0.08, 1])
    for b, g in F.groupby("sp_bin", observed=True):
        p(f"| {b} | {len(g)} | {g['R_base'].mean():+.3f} | {g['R_stress'].mean():+.3f} | {g['cost_R'].mean():.3f} |")
    # Gruppen (Train)
    T = F[F.abschnitt == "Train"].copy()
    T["gruppe"] = np.select([T.R_stress >= 3, T.R_stress <= -1.5, (T.R_stress.abs() < 0.3) & (T.days >= 40), T.R_stress < 0],
                            ["große Gewinner (≥ 3 R)", "extreme Verluste (≤ −1,5 R)", "totes Kapital (|R| < 0,3, ≥ 40 T.)", "normale Verlierer"],
                            "kleine/mittlere Gewinner")
    cols = ["prior_run", "prior_rs", "prior_top5", "decline", "decline_days", "mkt_decline", "idio_decline", "idio_share",
            "sector_decline", "rs_base", "rs10", "higher_low_atr", "vol_dry", "vol_up_down", "atr_contract", "close_loc",
            "down_size", "stop_pct", "cost_R", "log_adv", "mom61", "mkt_up", "mkt_dd", "base_days", "days_since_earn", "news_drop"]
    p("\n## Gruppen im Train – Median der Merkmale\n")
    p("| Merkmal | " + " | ".join(f"{g} (n {n})" for g, n in T.gruppe.value_counts().items()) + " |")
    p("|---|" + "---|" * T.gruppe.nunique())
    for c in cols:
        p(f"| {c} | " + " | ".join(f"{T.loc[T.gruppe == g, c].median():.3g}" for g in T.gruppe.value_counts().index) + " |")
    p("\n## Merkmal-Fünftel im Train – Ø R Stress (Trefferquote, n) · Spearman-ρ\n\n| Merkmal | Q1 | Q2 | Q3 | Q4 | Q5 | ρ |\n|---|---|---|---|---|---|---|")
    for c in cols:
        for r in qtable(T, c):
            p(r)
    # Verlauf
    p("\n## Verlauf im Train: Endergebnis nach Stand an Tag 10\n\n| R am Schluss von Tag 10 | n | Ø Endergebnis R Stress | Anteil ≥ 3 R |\n|---|---|---|---|")
    T["d10_bin"] = pd.cut(T["R_d10"], [-9, -0.5, 0, 0.5, 1, 99])
    for b, g in T.groupby("d10_bin", observed=True):
        p(f"| {b} | {len(g)} | {g['R_stress'].mean():+.3f} | {(g['R_stress'] >= 3).mean():.1%} |")
    p(f"\nMFE: Verlierer (R < 0) mit zwischendurch ≥ +1 R: {((T.R_stress < 0) & (T.MFE >= 1)).sum() / max(1, (T.R_stress < 0).sum()):.0%}. "
      f"Gewinner ≥ 3 R: Ø Tage {T.loc[T.R_stress >= 3, 'days'].mean():.0f}. Nach Verkauf Tag 60 (Zeit-Ausstieg): Ø weitere 60 Tage "
      f"{T.loc[T.why == 'time', 'after60'].mean():+.1%} (n {(T.why == 'time').sum()}).")
    # Kapital
    import os
    mx, rf = R.LAYOUTS["20x025"]
    for cash in (5000, 10000):
        r = run(R._G["raw"], R._G["cur"], R._G["fx"], R.build(sig, meta, "E0", rf), cash, R.costs("stress"), mx, calendar=R._G["cal"], min_fill=0.5)
        p(f"\nDepot {cash} € 20 × 0,25 % Stress: Trades {len(r.trades)}, nicht gekauft (voll) {r.skipped['full']}, zu wenig Kasse {r.skipped['no_cash']}, "
          f"zu klein {r.skipped['small']}, Ø investiert {r.invested.mean():.0%}, Ø Gebühren je Trade {r.trades['fees_eur'].mean():.2f} €, "
          f"Ø Spanne je Trade {r.trades['spread_eur'].mean():.2f} €, Ø Einsatz {(r.trades['cost_eur']).mean():.0f} €")
    p(f"\nReproduktion: Commit {os.environ.get('GITHUB_SHA', '?')}, prices_v1 SHA-256 {os.environ.get('PRICES_SHA', '?')}")
    (out / "diag_report.md").write_text("\n".join(L), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
