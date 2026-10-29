"""Kairo Ultimate – Datenprüfung vor jedem Strategietest (Phase 0b).

Frage: Sind die Kurse gut genug, dass ein Ergebnis nicht durch Datenfehler entsteht?
Prüft den eingefrorenen Datensatz prices_v1 (und Wechselkurse/Benchmarks) auf:
  1. Abdeckung: Beginn/Ende je Titel, Lücken (> 5 Handelstage ohne Kurs, solange gelistet)
  2. Plausibilität je Kerze: Kurs ≤ 0, Hoch < max(Eröffnung, Schluss), Tief > min(Eröffnung, Schluss)
  3. Ausreißer: Tagesbewegung > 40 %, die am Folgetag zu > 60 % zurückläuft (typischer Fehlkurs)
  4. Stillstand: ≥ 5 gleiche Schlusskurse hintereinander bei Volumen 0 (Kurs nicht gehandelt)
  5. Split-Reste: Schluss springt um Faktor ≈ 2/3/4/5/10 (oder Kehrwert), ohne dass AdjClose den Sprung ausgleicht
  6. Unabhängige Gegenprobe (Stichprobe): Stooq-Tageskurse vs. Yahoo – Anteil Tage mit gleicher Rendite (±1 %)
  7. Nachträgliche Änderung: frischer Yahoo-Download vs. eingefrorener Stand (Stichprobe)
  8. Wirkung auf die Strategie: Anteil der Kairo-Treffer, deren Treffer-/Haltefenster einen markierten Tag enthält

Ergebnis: JSON + Markdown. Bewertung vorab festgelegt (siehe GRENZEN): Ein Titel gilt als „unsicher“, wenn er einen
Ausreißer, einen Split-Rest, eine Plausibilitätsverletzung an mehr als 0,5 % der Tage oder eine Gegenprobe < 95 % hat.
Unsichere Titel werden in allen späteren Tests einmal mit und einmal ohne gerechnet (Sensitivität); weicht das
Ergebnis ab, zählt die Variante ohne.

    python -m research.ultimate.data_audit --data v1 --signals sig.parquet --out out [--stooq 300] [--fresh 150]
"""
from __future__ import annotations

import argparse
import io
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

GRENZEN = dict(spike=0.40, back=0.60, gap_days=5, stale=5, ohlc_share=0.005, xsrc_min=0.95, xsrc_tol=0.01)
SPLITS = np.array([2, 3, 4, 5, 10, 1 / 2, 1 / 3, 1 / 4, 1 / 5, 1 / 10])


def per_ticker(t: str, g: pd.DataFrame) -> dict:
    g = g.sort_values("date")
    d = pd.to_datetime(g["date"])
    o, h, l, c, a, v = (g[k].to_numpy(float) for k in ("Open", "High", "Low", "Close", "AdjClose", "Volume"))
    n = len(g)
    out = {"t": t, "n": n, "first": str(d.iloc[0].date()), "last": str(d.iloc[-1].date())}
    # 1 Lücken: Werktage zwischen zwei Kursen
    bd = np.busday_count(d.iloc[:-1].values.astype("datetime64[D]"), d.iloc[1:].values.astype("datetime64[D]"))
    out["gaps"] = int((bd > GRENZEN["gap_days"]).sum())
    out["max_gap"] = int(bd.max()) if len(bd) else 0
    # 2 Plausibilität
    bad = (c <= 0) | (o <= 0) | (h + 1e-9 < np.maximum(o, c)) | (l - 1e-9 > np.minimum(o, c))
    out["ohlc_bad"] = int(bad.sum())
    # 3 Ausreißer (bereinigte Kurse, damit Dividenden/Splits nicht zählen)
    r = np.diff(np.log(np.where(a > 0, a, np.nan)))
    sp = np.where((np.abs(r[:-1]) > np.log(1 + GRENZEN["spike"])) & (np.sign(r[1:]) == -np.sign(r[:-1]))
                  & (np.abs(r[1:]) > GRENZEN["back"] * np.abs(r[:-1])))[0]
    out["spikes"] = [str(d.iloc[i + 1].date()) for i in sp][:10]
    # 4 Stillstand
    same = np.r_[False, np.diff(c) == 0] & (v == 0)
    runs, k = 0, 0
    for s in same:
        k = k + 1 if s else 0
        runs += k == GRENZEN["stale"]
    out["stale_runs"] = int(runs)
    # 5 Split-Reste: Sprung im Schluss mit Split-Faktor, AdjClose springt genauso (also nicht bereinigt)
    rc, ra = c[1:] / c[:-1], a[1:] / a[:-1]
    near = np.min(np.abs(rc[:, None] / SPLITS[None, :] - 1), axis=1) < 0.05
    unadj = near & (np.abs(ra / rc - 1) < 0.02)
    out["split_rest"] = [str(d.iloc[i + 1].date()) for i in np.where(unadj)[0]][:10]
    out["zero_vol_share"] = float((v == 0).mean())
    return out


def stooq_symbol(t: str) -> str | None:
    if "." not in t:
        return t.lower().replace("-", ".") + ".us"
    base, ex = t.rsplit(".", 1)
    m = {"DE": "de", "L": "uk", "F": "de"}
    return f"{base.lower()}.{m[ex]}" if ex in m else None


def stooq(t: str) -> pd.Series | None:
    import requests
    s = stooq_symbol(t)
    if not s:
        return None
    try:
        r = requests.get(f"https://stooq.com/q/d/l/?s={s}&i=d", timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200 or not r.text.startswith("Date"):
            return None
        x = pd.read_csv(io.StringIO(r.text), parse_dates=["Date"]).set_index("Date")["Close"]
        return x[x > 0]
    except Exception:
        return None


def compare(ours: pd.Series, other: pd.Series) -> dict | None:
    j = pd.concat([ours, other], axis=1, join="inner").dropna()
    j = j[(j.index >= "2008-01-01")]
    if len(j) < 250:
        return None
    rr = j.pct_change().dropna()
    ok = (rr.iloc[:, 0] - rr.iloc[:, 1]).abs() <= GRENZEN["xsrc_tol"]
    return {"days": int(len(rr)), "match": float(ok.mean())}


def fresh(tickers: list[str]) -> dict[str, pd.Series]:
    import yfinance as yf
    out = {}
    for i in range(0, len(tickers), 50):
        part = tickers[i:i + 50]
        d = yf.download(part, start="2005-01-01", end="2026-10-17", auto_adjust=False, group_by="ticker",
                        progress=False, threads=True)
        for t in part:
            try:
                out[t] = d[t]["Adj Close"].dropna()
            except KeyError:
                pass
        time.sleep(3)
    return out


def signal_impact(sig: pd.DataFrame, flagged: dict[str, list[str]]) -> dict:
    """Treffer, deren Fenster (60 Tage vor bis 90 Tage nach dem Treffer) einen markierten Tag enthält."""
    hit = 0
    by_t = {t: pd.to_datetime(v) for t, v in flagged.items() if v}
    for t, g in sig.groupby("ticker"):
        if t not in by_t:
            continue
        days = by_t[t]
        for s in pd.to_datetime(g["date"]):
            if ((days >= s - pd.Timedelta(days=60)) & (days <= s + pd.Timedelta(days=90))).any():
                hit += 1
    return {"signals": int(len(sig)), "affected": hit, "share": hit / max(1, len(sig))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="v1")
    ap.add_argument("--signals")
    ap.add_argument("--out", default="out")
    ap.add_argument("--stooq", type=int, default=300)
    ap.add_argument("--fresh", type=int, default=150)
    a = ap.parse_args(argv)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    px = pd.read_parquet(Path(a.data) / "prices_v1.parquet")
    rows = [per_ticker(t, g) for t, g in px.groupby("ticker")]
    df = pd.DataFrame(rows).set_index("t")
    df["ohlc_share"] = df["ohlc_bad"] / df["n"]

    rng = np.random.default_rng(20261029)
    tick = sorted(df.index)
    adj = {t: g.set_index(pd.to_datetime(g["date"]))["AdjClose"] for t, g in px.groupby("ticker")}

    xs = {}
    for t in rng.choice(tick, size=min(a.stooq, len(tick)), replace=False):
        s = stooq(t)
        if s is not None:
            c = compare(adj[t], s)
            if c:
                xs[t] = c
        time.sleep(0.5)
    df["xsrc"] = pd.Series({t: v["match"] for t, v in xs.items()})

    fr = {}
    if a.fresh:
        sample = list(rng.choice(tick, size=min(a.fresh, len(tick)), replace=False))
        for t, s in fresh(sample).items():
            c = compare(adj[t], s)
            if c:
                fr[t] = c

    unsure = df[(df["spikes"].str.len() > 0) | (df["split_rest"].str.len() > 0)
                | (df["ohlc_share"] > GRENZEN["ohlc_share"]) | (df["xsrc"] < GRENZEN["xsrc_min"])]
    flagged = {t: list(r["spikes"]) + list(r["split_rest"]) for t, r in df.iterrows()}
    res = {
        "grenzen": GRENZEN,
        "titel": int(len(df)), "kerzen": int(df["n"].sum()),
        "start_vor_2008": int((df["first"] < "2008-01-01").sum()),
        "luecken_titel": int((df["gaps"] > 0).sum()), "max_luecke_werktage": int(df["max_gap"].max()),
        "ohlc_verletzt_titel": int((df["ohlc_bad"] > 0).sum()), "ohlc_verletzt_anteil": float(df["ohlc_bad"].sum() / df["n"].sum()),
        "ausreisser_titel": int((df["spikes"].str.len() > 0).sum()),
        "split_rest_titel": int((df["split_rest"].str.len() > 0).sum()),
        "stillstand_titel": int((df["stale_runs"] > 0).sum()),
        "stooq": {"geprueft": len(xs), "median_match": float(np.median([v["match"] for v in xs.values()])) if xs else None,
                  "unter_95": sorted(t for t, v in xs.items() if v["match"] < GRENZEN["xsrc_min"])},
        "yahoo_frisch": {"geprueft": len(fr), "median_match": float(np.median([v["match"] for v in fr.values()])) if fr else None,
                         "unter_99": sorted(t for t, v in fr.items() if v["match"] < 0.99)},
        "unsicher": sorted(unsure.index),
    }
    if a.signals:
        res["wirkung_auf_treffer"] = signal_impact(pd.read_parquet(a.signals), flagged)
    (out / "data_audit.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    df.drop(columns=[]).to_csv(out / "data_audit_tickers.csv")
    print(json.dumps({k: v for k, v in res.items() if k != "unsicher"}, indent=1, ensure_ascii=False))
    print("unsicher:", len(res["unsicher"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
