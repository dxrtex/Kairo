"""Wie reagieren Aktien auf Quartalszahlen? Echte Statistik statt Bauchgefühl.

Für die größten US-Aktien (Liste vom letzten Scan) die letzten ~6 Jahre Quartalszahlen von Yahoo: EPS-Schätzung, Ergebnis,
Überraschung. Reaktion = Schlusskurs des ersten Handelstags nach der Meldung gegen den Schluss davor (vor Börsenbeginn
gemeldet → derselbe Tag). Ausgabe: earn_stats.json mit Quoten je Überraschungs-Stufe und je Aktie (für die App).

    python tools/research/earn_stats.py <universe_us.csv> <out.json> [max_aktien]
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

BUCKETS = [(-1e9, -10, "deutlich unter Erwartung (< −10 %)"), (-10, -2, "unter Erwartung (−10 bis −2 %)"),
           (-2, 2, "im Rahmen (±2 %)"), (2, 10, "über Erwartung (+2 bis +10 %)"), (10, 1e9, "deutlich über Erwartung (> +10 %)")]


def reactions(tk: str, px: pd.Series) -> list[dict]:
    import yfinance as yf
    try:
        ed = yf.Ticker(tk).get_earnings_dates(limit=28)
    except Exception:
        return []
    if ed is None or not len(ed):
        return []
    out = []
    idx = px.index
    for ts, row in ed.iterrows():
        est, rep = row.get("EPS Estimate"), row.get("Reported EPS")
        if pd.isna(rep) or pd.isna(est):
            continue
        ts = pd.Timestamp(ts)
        local = ts.tz_convert("America/New_York") if ts.tzinfo else ts
        day = pd.Timestamp(local.date())
        pre = local.hour < 12                                   # vor Börsenbeginn gemeldet
        i = idx.searchsorted(day) if pre else idx.searchsorted(day, side="right")
        if i <= 0 or i >= len(idx):
            continue
        r1 = float(px.iloc[i] / px.iloc[i - 1] - 1)
        r5 = float(px.iloc[min(i + 4, len(idx) - 1)] / px.iloc[i - 1] - 1)
        sur = row.get("Surprise(%)")
        if pd.isna(sur):
            sur = (rep - est) / abs(est) * 100 if est else np.nan
        out.append({"t": tk, "d": str(idx[i].date()), "s": None if pd.isna(sur) else float(sur), "r1": r1, "r5": r5})
    return out


def main(uni_csv: str, out_json: str, n_max: int = 600) -> None:
    import yfinance as yf
    uni = pd.read_csv(uni_csv)
    uni = uni[~uni["ticker"].astype(str).str.contains(r"\.")].sort_values("market_cap_usd", ascending=False).head(n_max)
    tks = list(uni["ticker"])
    px = yf.download(tks, period="7y", interval="1d", auto_adjust=True, progress=False, group_by="ticker", threads=True)
    rows = []
    for k, tk in enumerate(tks):
        try:
            c = px[tk]["Close"].dropna()
        except Exception:
            continue
        if len(c) < 200:
            continue
        rows += reactions(tk, c)
        if k % 50 == 0:
            print(f"{k}/{len(tks)} · {len(rows)} Meldungen")
        time.sleep(0.3)
    D = pd.DataFrame(rows).dropna(subset=["s"])
    D = D[D["s"].abs() < 500]
    print(f"Meldungen gesamt: {len(D)} aus {D['t'].nunique()} Aktien")
    buckets = []
    for lo, hi, name in BUCKETS:
        s = D[(D["s"] >= lo) & (D["s"] < hi)]
        if len(s) < 30:
            continue
        buckets.append({"lo": lo, "hi": hi, "name": name, "n": int(len(s)), "up1": round(float((s["r1"] > 0).mean()), 3),
                        "med1": round(float(s["r1"].median()), 4), "up5": round(float((s["r5"] > 0).mean()), 3),
                        "med5": round(float(s["r5"].median()), 4), "big_down": round(float((s["r1"] < -0.05).mean()), 3)})
        print(f"{name}: n {len(s)} · am Folgetag hoch {buckets[-1]['up1']:.0%} · Median {buckets[-1]['med1']:+.2%} · nach 5 Tagen hoch {buckets[-1]['up5']:.0%} · Absturz >5 % {buckets[-1]['big_down']:.0%}")
    beat = D[D["s"] > 2]
    print(f"Über Erwartung (> +2 %) und trotzdem gefallen: {(beat['r1'] < 0).mean():.0%} · um mehr als 5 %: {(beat['r1'] < -0.05).mean():.0%}")
    per = {}
    for tk, g in D.sort_values("d").groupby("t"):
        g = g.tail(12)
        per[tk] = {"n": int(len(g)), "up": int((g["r1"] > 0).sum()), "move": round(float(g["r1"].abs().median()), 4),
                   "beat_up": round(float((g[g["s"] > 2]["r1"] > 0).mean()), 3) if (g["s"] > 2).sum() >= 3 else None,
                   "last": [{"d": r.d, "s": round(r.s, 1), "r1": round(r.r1, 4)} for r in g.tail(8).itertuples()]}
    json.dump({"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "n": int(len(D)), "stocks": int(D["t"].nunique()),
               "since": str(D["d"].min()), "buckets": buckets,
               "beat_down": round(float((beat["r1"] < 0).mean()), 3), "per": per}, open(out_json, "w"), ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 600)
