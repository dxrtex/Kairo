"""Meta-Labeling: Ein einfaches Modell schätzt je B60-Signal das erwartete Netto-R aus ALLEN am Signaltag bekannten Merkmalen –
und wir prüfen, ob eine darauf gestützte Rangfolge oder Auswahl das DEPOT verbessert.

Vorab festgelegt (01.11.2026):
- Merkmale: Stop-Abstand in ATR, Vormomentum, ATR in % des Kurses, Markt unter 200-Tage-Linie, Kurs/Volumen (über
  200-Tage-Linie, Rückgang vom 52-Wochen-Hoch, Kapitulations-Volumen, Wochenverlust), Insider (Kauf, Cluster, Officer,
  ≥ 100 k$), Quartalszahlen/Meldungen im Rückgang (8-K), Qualität (profitabel, Bruttogewinn/Bilanzsumme, Gewinnentwicklung,
  Eigenkapitalquote), Region. Fehlende Werte → Mittel der Lerndaten + Kennzeichen „fehlt“.
- Modell: Ridge-Regression (Strafterm α = 10, standardisierte Merkmale) auf R mit Stress-Kosten – bewusst einfach und
  nachvollziehbar (Baseline vor jedem komplexen Verfahren).
- Zeitliche Trennung (walk-forward): lernen auf Train (2008–2016) → anwenden auf Validierung (2017–2021); lernen auf
  Train+Validierung → anwenden auf Holdout (2022–2026). Im Train-Zeitraum bleibt die B60-Rangfolge (kein In-Sample-Vorteil).
- Varianten im Depot (gleiche Engine, gleiche Kosten): E0 = B60 (schwächeres Vormomentum zuerst) · M_RANK = Modell-Rangfolge
  bei vollem Depot · M_FILT = B60, aber Signale im untersten Drittel der Modell-Schätzung (Schwelle aus den Lerndaten) entfallen ·
  RND = zufällige Rangfolge (3 Seeds, Kontrollgruppe).
- Bestanden, wenn (a) die Modell-Schätzung je Trade in Validierung UND Holdout positiv mit dem echten R zusammenhängt
  (Spearman > 0, p < 0,05) UND (b) M_RANK oder M_FILT im Depot (Stress-Kosten) in Validierung UND Holdout bei 10.000 € und
  20.000 € eine höhere Jahresrendite als E0 erzielt, ohne größeren Rückgang. Bestanden heißt: Challenger für den Schattentest
  – keine Regeländerung.

    python -m research.reversal.meta --data v1 --signals sig.parquet --sec sec --insider sec/insider_buys.csv.gz --fund sec/fund_src.csv.gz --out out
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.reversal import combo as C
from research.reversal import learn as LR
from research.strategy_championship.engine import run
from research.ultimate import round1 as R

NUM = ["stop_atr", "mom", "atr_pct"]
BOOL = ["index_u200", "sma200_up", "deep_dd", "vol_spike", "drop5", "ins_buy", "ins_cluster", "ins_officer", "ins_big",
        "earn_recent", "no_news", "news_earn", "news_other", "profitable", "gp_quality", "em_pos", "low_lev"]
ALPHA = 10.0
LAYOUTS = ("5x1", "20x025")
CASH = (10000, 20000)


def design(df: pd.DataFrame, ref: pd.DataFrame | None = None) -> tuple[np.ndarray, list[str], dict]:
    """Merkmalsmatrix; Füllwerte/Skalierung aus `ref` (Lerndaten) – nie aus den Prüfdaten."""
    ref = df if ref is None else ref
    cols, X = [], []
    stats = {}
    for c in NUM:
        v = pd.to_numeric(df[c], errors="coerce").clip(*np.nanpercentile(pd.to_numeric(ref[c], errors="coerce"), [1, 99]))
        mu = float(pd.to_numeric(ref[c], errors="coerce").mean())
        X.append(v.fillna(mu).to_numpy(float)); cols.append(c)
    for c in BOOL:
        if c not in df:
            continue
        v = df[c].map(lambda x: np.nan if x is None or (isinstance(x, float) and np.isnan(x)) else float(bool(x)))
        r = ref[c].map(lambda x: np.nan if x is None or (isinstance(x, float) and np.isnan(x)) else float(bool(x)))
        X.append(v.fillna(float(r.mean()) if r.notna().any() else 0.0).to_numpy(float)); cols.append(c)
        X.append(v.isna().astype(float).to_numpy()); cols.append(c + "_fehlt")
    for reg in ("us", "eu"):
        X.append((df["region"] == reg).astype(float).to_numpy() if "region" in df else np.zeros(len(df))); cols.append("reg_" + reg)
    X = np.column_stack(X)
    return X, cols, stats


def fit(X: np.ndarray, y: np.ndarray, alpha: float = ALPHA):
    mu, sd = X.mean(0), X.std(0)
    sd[sd == 0] = 1
    Z = (X - mu) / sd
    b = np.linalg.solve(Z.T @ Z + alpha * np.eye(Z.shape[1]), Z.T @ (y - y.mean()))
    return {"mu": mu, "sd": sd, "b": b, "c": float(y.mean())}


def predict(m: dict, X: np.ndarray) -> np.ndarray:
    return m["c"] + ((X - m["mu"]) / m["sd"]) @ m["b"]


def spearman(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    """Rangkorrelation mit p-Wert (t-Näherung, zweiseitig) – ohne Zusatzbibliothek."""
    from math import erf, sqrt
    ra, rb = pd.Series(a).rank().to_numpy(), pd.Series(b).rank().to_numpy()
    rho = float(np.corrcoef(ra, rb)[0, 1]); n = len(a)
    t = rho * sqrt((n - 2) / max(1e-12, 1 - rho ** 2))
    return rho, float(2 * (1 - 0.5 * (1 + erf(abs(t) / sqrt(2)))))


def walk_forward(df: pd.DataFrame) -> tuple[pd.Series, dict]:
    """Vorhersage je Trade (Index wie df): Val aus Train-Modell, Holdout aus Train+Val-Modell; Train = NaN."""
    pred = pd.Series(np.nan, index=df.index)
    info = {}
    for test, learn in (("Validierung", ("Train",)), ("Holdout", ("Train", "Validierung"))):
        tr, te = df[df["abschnitt"].isin(learn)], df[df["abschnitt"] == test]
        Xtr, cols, _ = design(tr)
        m = fit(Xtr, tr["R_stress"].to_numpy(float))
        Xte, _, _ = design(te, tr)
        p = predict(m, Xte)
        pred.loc[te.index] = p
        thr = float(np.percentile(predict(m, Xtr), 100 / 3))
        rho, pv = spearman(p, te["R_stress"].to_numpy(float))
        q = pd.qcut(pd.Series(p, index=te.index), 3, labels=False, duplicates="drop")
        terc = {int(k): float(te.loc[q.index[q == k], "R_stress"].mean()) for k in sorted(q.dropna().unique())}
        info[test] = {"rho": rho, "p": pv, "thr": thr, "terciles": terc, "n": int(len(te)),
                      "coef": dict(sorted(zip(cols, (m["b"]).round(4)), key=lambda kv: -abs(kv[1]))[:10])}
    return pred, info


def depot_runs(sig, meta, pred_by_tag: dict, thr_by_ab: dict, layouts=LAYOUTS) -> dict:
    out = {}
    for lay in layouts:
        mx, rf = R.LAYOUTS[lay]
        variants = {"E0": None, "M_RANK": "rank", "M_FILT": "filt", "RND0": 0, "RND1": 1, "RND2": 2}
        for v, mode in variants.items():
            orders = R.build(sig, meta, "E0", rf)
            if isinstance(mode, int):
                rng = np.random.default_rng(100 + mode)
                for o in orders:
                    o.prio = float(rng.random())
            elif mode is not None:
                keep = []
                for o in orders:
                    p = pred_by_tag.get(o.tag)
                    if p is None:                                  # Train-Zeitraum oder ohne Merkmale: wie B60
                        keep.append(o); continue
                    if mode == "rank":
                        o.prio = 1e3 + p                           # Modell-Schätzung (höher = zuerst)
                        keep.append(o)
                    elif p >= thr_by_ab.get(o.tag, -9):
                        keep.append(o)
                orders = keep
            for cash in CASH:
                for kind in ("stress",):                       # Entscheidung mit Stress-Kosten (Laufzeit)
                    r = run(R._G["raw"], R._G["cur"], R._G["fx"], orders, cash, R.costs(kind), mx, calendar=R._G["cal"], min_fill=0.5)
                    seg = R.segments(r.equity, r.trades, r.invested)
                    out[f"{lay}|{v}|{cash}|{kind}"] = {ab: {k: (seg.get(ab) or {}).get(k) for k in ("cagr", "max_dd", "trades")} for ab in ("Validierung", "Holdout", "gesamt")}
            print("Depot", lay, v, flush=True)
    return out


def verdict(info: dict, dep: dict, layouts=LAYOUTS) -> tuple[bool, list[str]]:
    msg, ok_a = [], all(info[ab]["rho"] > 0 and info[ab]["p"] < 0.05 for ab in ("Validierung", "Holdout"))
    msg.append(f"(a) Schätzung hängt mit echtem R zusammen: {'ja' if ok_a else 'nein'} "
               + " · ".join(f"{ab} ρ {info[ab]['rho']:+.3f} (p {info[ab]['p']:.3f})" for ab in ("Validierung", "Holdout")))
    ok_b = False
    for lay in layouts:
        for v in ("M_RANK", "M_FILT"):
            good = True
            for cash in CASH:
                for ab in ("Validierung", "Holdout"):
                    m, e = dep[f"{lay}|{v}|{cash}|stress"][ab], dep[f"{lay}|E0|{cash}|stress"][ab]
                    if m["cagr"] is None or e["cagr"] is None or m["cagr"] <= e["cagr"] or (m["max_dd"] or 0) < (e["max_dd"] or 0) - 0.02:
                        good = False
            if good:
                ok_b = True
                msg.append(f"(b) {v} schlägt B60 im Raster {lay} in Validierung und Holdout bei 10.000 € und 20.000 €")
    if not ok_b:
        msg.append("(b) keine Modell-Variante schlägt B60 im Depot durchgängig")
    return ok_a and ok_b, msg


def report(df, info, dep, ok, msg, layouts=LAYOUTS) -> str:
    f = lambda v: "–" if v is None else f"{v:+.1%}"
    L = ["# Meta-Labeling: Modell-Rangfolge für B60-Signale (zeitlich getrennt)\n", __doc__.split("\n", 1)[1].split("    python")[0].strip(), ""]
    for ab in ("Validierung", "Holdout"):
        i = info[ab]
        L.append(f"**{ab}** ({i['n']} Trades): ρ {i['rho']:+.3f} (p {i['p']:.3f}) · Ø R Stress je Drittel der Schätzung (unten → oben): "
                 + " / ".join(f"{v:+.3f}" for v in i["terciles"].values()) + f"  \nwichtigste Gewichte: " + ", ".join(f"{k} {v:+.3f}" for k, v in i["coef"].items()))
    L.append("\n| Raster | Variante | Kapital | Val CAGR (DD) | Holdout CAGR (DD) |\n|---|---|---|---|---|")
    for lay in layouts:
        for v in ("E0", "M_RANK", "M_FILT", "RND0", "RND1", "RND2"):
            for cash in CASH:
                d = dep[f"{lay}|{v}|{cash}|stress"]
                L.append(f"| {lay} | {v} | {cash:,} € | {f(d['Validierung']['cagr'])} ({f(d['Validierung']['max_dd'])}) | {f(d['Holdout']['cagr'])} ({f(d['Holdout']['max_dd'])}) |".replace(",", "."))
    L.append("\n## Ergebnis\n")
    L += [f"- {m}" for m in msg]
    L.append("\n**" + ("Bestanden – Challenger für den Schattentest (keine Regeländerung)." if ok else "Nicht bestanden – B60 bleibt; das Modell bringt im Depot keinen belastbaren Vorteil.") + "**")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data"); ap.add_argument("--signals"); ap.add_argument("--sec"); ap.add_argument("--insider"); ap.add_argument("--fund")
    ap.add_argument("--out", default="meta_out"); ap.add_argument("--layout", default=",".join(LAYOUTS))
    ap.add_argument("--universe", default="research/strategy_championship/data/universe_frozen_2026-10-16.csv")
    a = ap.parse_args(argv)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    sig, meta = R.setup(a.data, a.signals, a.sec)
    t = R.per_trade(R.build(sig, meta, "E0", 1e-5))
    uni = pd.read_csv(a.universe)
    base = LR.features(t, R._G["adj"], dict(zip(uni["ticker"], uni["region"])), dict(zip(uni["ticker"], uni["sector"])))
    cm = Path(a.sec) / "cik_map.csv"
    cmf = pd.read_csv(cm)
    us, t2c = set(cmf["ticker"]), {tk: int(c) for tk, c in zip(cmf["ticker"], cmf["cik"])}
    df = C.features(base, C.insider_index(a.insider, str(cm)), us)
    fil = pd.read_csv(Path(a.sec) / "filings.csv.gz", dtype={"items": str}, usecols=["cik", "form", "items", "accepted"])
    tl = None
    if a.fund and Path(a.fund).exists():
        tl = pd.read_csv(a.fund)
        if "gpa" not in tl.columns:
            from research.strategy_championship.v3 import fundamentals as FU
            f = pd.read_csv(a.fund, dtype={"val": str, "start": str, "end": str, "filed": str}); f["start"] = f["start"].fillna("")
            tl = FU.build(f)
    df = C.features2(df, fil, tl, t2c)
    df["region"] = df["ticker"].map(dict(zip(uni["ticker"], uni["region"])))
    pred, info = walk_forward(df)
    df["pred"] = pred
    pred_by_tag = {tg: float(p) for tg, p in zip(df["tag"], df["pred"]) if pd.notna(p)}
    thr_by_tag = {tg: info[ab]["thr"] for tg, ab in zip(df["tag"], df["abschnitt"]) if ab in info}
    lays = tuple(a.layout.split(","))
    dep = depot_runs(sig, meta, pred_by_tag, thr_by_tag, lays)
    ok, msg = verdict(info, dep, lays)
    txt = report(df, info, dep, ok, msg, lays)
    sfx = "_".join(lays)
    (out / f"meta_report_{sfx}.md").write_text(txt, encoding="utf-8")
    (out / f"meta_result_{sfx}.json").write_text(json.dumps({"info": info, "depot": dep, "ok": ok}, indent=1, default=str), encoding="utf-8")
    print(txt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
