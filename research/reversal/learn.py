"""Lern-Test historisch: Schaden die „vorher erkennbaren“ Merkmale der Ursachensuche (backend/tradewhy.py) den B60-Trades?

Statt Monate auf genug Live-Trades zu warten, prüft dieser Lauf dieselben Merkmale an allen B60-Trades 2008–2026
(Treffer 11/11, korrigierte Engine, je Trade ohne Kapitalgrenze, R mit Basis- und Stress-Kosten):

  eng         Stop näher als 1 ATR am Kauf          weit       Stop weiter als 2,5 ATR
  momentum    Vormomentum (Monat −6…−1) über +25 %   unruhig    ATR über 5 % des Kurses
  index_u200  Markt der Region unter 200-Tage-Linie  sektor_u50 Sektor unter 50-Tage-Linie
  (Markt/Sektor = gleichgewichteter Index aus allen Aktien der Region bzw. des Sektors im Universum – ohne Zukunftsdaten)
  Erklärung hinterher (kein Filter): markt_fiel = Markt der Region fiel von Kauf bis Verkauf um ≥ 3 %.

Vorab festgelegte Entscheidungsregel (vor dem Lauf, 01.11.2026): Ein Merkmal wird „Kandidat für den Depot-Test“, wenn
mit Stress-Kosten das Ø-R der Trades MIT Merkmal in Train, Validierung UND Holdout jeweils um mindestens 0,05 R unter dem
Ø-R ohne Merkmal liegt und das 95-%-Bootstrap-Intervall des Unterschieds (gesamt) unter 0 liegt. Kein Kandidat ändert die
Regel: Nächster Schritt wäre der Depot-Test (Filter weglassen vs. B60, alle Raster), danach Schattentest und Freigabe.

    python -m research.reversal.learn --data v1 --signals sig.parquet --sec sec --out out
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from backend.indicators import atr as _atr
from research.ultimate import round1 as R

FEATS = {"eng": "Stop näher als 1 ATR", "weit": "Stop weiter als 2,5 ATR", "momentum": "Vormomentum über +25 %",
         "unruhig": "ATR über 5 % des Kurses", "index_u200": "Markt der Region unter 200-Tage-Linie",
         "sektor_u50": "Sektor unter 50-Tage-Linie"}
AB = ("Train", "Validierung", "Holdout")
MIN_DIFF = 0.05


def proxies(adj: dict, groups: dict) -> dict[str, pd.Series]:
    """Gleichgewichteter Index je Gruppe (Median der Tagesrenditen) – nur Vergangenheitswerte je Tag."""
    closes = pd.DataFrame({t: a["Close"] for t, a in adj.items()})
    ret = closes.pct_change(fill_method=None).clip(-0.5, 0.5)
    out = {}
    for g in sorted({v for v in groups.values() if isinstance(v, str) and v}):
        cols = [t for t in closes.columns if groups.get(t) == g]
        if len(cols) >= 10:
            out[g] = (1 + ret[cols].median(axis=1).fillna(0)).cumprod()
    return out


def _below(s: pd.Series | None, d, n: int):
    if s is None:
        return None
    i = int(s.index.searchsorted(d, side="right") - 1)
    if i < n - 1:
        return None
    return bool(s.iloc[i] < s.iloc[i - n + 1: i + 1].mean())


def _ret(s: pd.Series | None, a, b):
    if s is None:
        return None
    i, j = int(s.index.searchsorted(a, side="right") - 1), int(s.index.searchsorted(b, side="right") - 1)
    return float(s.iloc[j] / s.iloc[i] - 1) if 0 <= i < j else None


def features(t: pd.DataFrame, adj: dict, region: dict, sector: dict) -> pd.DataFrame:
    px_r, px_s = proxies(adj, region), proxies(adj, sector)
    atr_c = {}
    rows = []
    for x in t.itertuples(index=False):
        a = adj[x.ticker]
        if x.ticker not in atr_c:
            atr_c[x.ticker] = _atr(a).to_numpy(float)
        idx, c, f = a.index, a["Close"].to_numpy(float), a["f"].to_numpy(float)
        sd, ed = pd.Timestamp(x.signal_date), pd.Timestamp(x.entry_date)
        i, k = int(idx.searchsorted(sd, side="right") - 1), int(idx.searchsorted(ed, side="right") - 1)
        av = atr_c[x.ticker][i]
        e_adj, s_adj = x.entry_px * f[k], x.stop * f[k]
        rg, sc = region.get(x.ticker), sector.get(x.ticker)
        rows.append({"stop_atr": (e_adj - s_adj) / av if av > 0 else np.nan,
                     "mom": c[i - 21] / c[i - 126] - 1 if i >= 126 else np.nan,
                     "atr_pct": av / c[i] if c[i] > 0 else np.nan,
                     "index_u200": _below(px_r.get(rg), sd, 200), "sektor_u50": _below(px_s.get(sc), sd, 50),
                     "mkt_hold": _ret(px_r.get(rg), ed, pd.Timestamp(x.exit_date))})
    f = pd.DataFrame(rows, index=t.index)
    out = t.join(f)
    out["eng"] = out["stop_atr"] < 1.0
    out["weit"] = out["stop_atr"] > 2.5
    out["momentum"] = out["mom"] > 0.25
    out["unruhig"] = out["atr_pct"] > 0.05
    out["markt_fiel"] = out["mkt_hold"] <= -0.03
    return out


def _boot(a: np.ndarray, b: np.ndarray, n=2000, seed=7) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    d = [rng.choice(a, len(a)).mean() - rng.choice(b, len(b)).mean() for _ in range(n)]
    return float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def evaluate(df: pd.DataFrame) -> dict:
    res = {}
    for k, lbl in FEATS.items():
        known = df[df[k].notna()] if df[k].dtype == object else df
        m = known[k].astype(bool)
        row = {"l": lbl, "n": int(m.sum()), "share": float(m.mean()) if len(m) else None, "ab": {}}
        for col in ("R_base", "R_stress"):
            row[col] = {"mit": float(known.loc[m, col].mean()) if m.any() else None,
                        "ohne": float(known.loc[~m, col].mean()) if (~m).any() else None}
        for ab in AB:
            s = known[known["abschnitt"] == ab]
            ms = s[k].astype(bool)
            row["ab"][ab] = {"n": int(ms.sum()),
                             "diff": float(s.loc[ms, "R_stress"].mean() - s.loc[~ms, "R_stress"].mean()) if ms.any() and (~ms).any() else None}
        if m.sum() >= 30 and (~m).sum() >= 30:
            row["ci"] = _boot(known.loc[m, "R_stress"].to_numpy(), known.loc[~m, "R_stress"].to_numpy())
        else:
            row["ci"] = None
        ok = all(v["diff"] is not None and v["diff"] <= -MIN_DIFF for v in row["ab"].values()) and row["ci"] is not None and row["ci"][1] < 0
        row["status"] = "Kandidat für den Depot-Test" if ok else "kein beständiger Schaden"
        res[k] = row
    return res


def report(df: pd.DataFrame, res: dict) -> str:
    f = lambda v: "–" if v is None or v != v else f"{v:+.3f}"
    L = ["# Lern-Test historisch: Was macht B60-Trades schlechter?\n", __doc__.split("\n", 1)[1].split("    python")[0].strip(), "",
         f"**{len(df):,} B60-Trades** · Ø R Basis {df['R_base'].mean():+.3f} · Stress {df['R_stress'].mean():+.3f} · "
         f"Gewinnquote {(df['R_stress'] > 0).mean():.0%}\n".replace(",", "."),
         "| Merkmal | Anteil | Ø R Stress mit | ohne | Δ Train | Δ Validierung | Δ Holdout | 95-%-Intervall Δ | Ergebnis |",
         "|---|---|---|---|---|---|---|---|---|"]
    for k, r in res.items():
        ci = "–" if not r["ci"] else f"{r['ci'][0]:+.3f} … {r['ci'][1]:+.3f}"
        L.append(f"| {r['l']} | {r['share']:.0%} ({r['n']}) | {f(r['R_stress']['mit'])} | {f(r['R_stress']['ohne'])} | "
                 + " | ".join(f"{f(r['ab'][ab]['diff'])} ({r['ab'][ab]['n']})" for ab in AB) + f" | {ci} | **{r['status']}** |")
    L.append("\n## Erklärung hinterher: Markt der Region fiel in der Haltezeit (≥ 3 %)\n")
    mf = df["markt_fiel"].astype(bool)
    lo = df["R_stress"] <= 0
    L.append(f"Bei Verlusten {mf[lo].mean():.0%}, bei Gewinnen {mf[~lo].mean():.0%}. Ø R mit fallendem Markt {df.loc[mf, 'R_stress'].mean():+.3f}, "
             f"sonst {df.loc[~mf, 'R_stress'].mean():+.3f}. Das ist nicht vorher erkennbar – erklärt aber, wie viel der Verluste der Markt verursacht.")
    L.append("\n## Fünftel der stetigen Merkmale (Ø R Stress)\n")
    for col, lbl in (("stop_atr", "Stop-Abstand in ATR"), ("mom", "Vormomentum"), ("atr_pct", "ATR in % des Kurses")):
        s = df[[col, "R_stress"]].dropna()
        if len(s) > 50:
            q = pd.qcut(s[col], 5, duplicates="drop")
            g = s.groupby(q, observed=True)["R_stress"].agg(["mean", "count"])
            L.append(f"- **{lbl}:** " + " · ".join(f"{iv.left:.2f}–{iv.right:.2f}: {m:+.3f} ({int(n)})" for iv, (m, n) in g.iterrows()))
    cand = [k for k, r in res.items() if r["status"].startswith("Kandidat")]
    L.append("\n## Ergebnis\n")
    L.append(f"Kandidaten für den Depot-Test: **{', '.join(FEATS[k] for k in cand)}**." if cand else
             "**Kein Merkmal schadet beständig** in allen drei Zeiträumen – kein Filter, B60 bleibt unverändert.")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data"); ap.add_argument("--signals"); ap.add_argument("--sec"); ap.add_argument("--out", default="learn_out")
    ap.add_argument("--universe", default="research/strategy_championship/data/universe_frozen_2026-10-16.csv")
    a = ap.parse_args(argv)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    sig, meta = R.setup(a.data, a.signals, a.sec)
    t = R.per_trade(R.build(sig, meta, "E0", 1e-5))
    uni = pd.read_csv(a.universe)
    df = features(t, R._G["adj"], dict(zip(uni["ticker"], uni["region"])), dict(zip(uni["ticker"], uni["sector"])))
    res = evaluate(df)
    (out / "learn_report.md").write_text(report(df, res), encoding="utf-8")
    (out / "learn_result.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    df.to_csv(out / "learn_trades.csv.gz", index=False)
    print(report(df, res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
