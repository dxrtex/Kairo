"""Quartalszahlen-Prognose: eigene Quoten für Europa/Asien, Absturz-Risiko, Schwankung und Marktlage (Nutzer-Auftrag 03.11.2026).

Anlass (Live-Bilanz 27.10.–02.11.2026, 203 Meldungen): USA 62 % Richtung getroffen, außerhalb der USA 51 % – die App nutzt dort
die US-Quoten. Bereits getestet und NICHT hilfreich (docs/EARNINGS_FEATURES_TEST.md): Lauf 20/60 Tage, eigenes Muster, Umsatzwachstum.

Vorab festgelegt (vor dem ersten Lauf):
- Ziel A „steigt“: Kurs am ersten Handelstag nach der Meldung höher (r1 > 0).
- Ziel B „Absturz“: r1 ≤ −5 % (für die Frage „Position vor den Zahlen verkleinern?“).
- Lernen: Meldungen bis 30.06.2024 · Prüfen: danach (zeitlich getrennt).
- A1 Regionen: Quote je Gewinn-Stufe aus der EIGENEN Region (Lernzeit, zur US-Quote hin geglättet mit 30 Pseudo-Berichten)
  gegen die US-Quote. Übernommen, wenn der Brier in der Prüfzeit der Region kleiner ist (Block-Bootstrap über Monate,
  95-%-Intervall des Unterschieds ohne Null).
- A2 Zusatzmerkmale für „steigt“ (logistisch, auf Lernzeit): Schwankung 20 T. (vol20), mittlere Reaktion der Aktie auf
  frühere Zahlen (absr), Marktlage (Index über EMA 50). Übernommen nur bei besserer LogLoss UND AUC in der Prüfzeit.
- B Absturz: Basis = Absturz-Quote je Gewinn-Stufe; Modell = logistisch mit Gewinn-Stufe, vol20, absr, run20, Marktlage.
  Gezeigt wird es nur, wenn es in der Prüfzeit besser ist (Brier, AUC) und geeicht (je Fünftel Vorhersage ≈ Wirklichkeit).

    python tools/research/earn_region.py collect <uni.csv> <region> <n_max> <out.csv>
    python tools/research/earn_region.py analyze <ordner mit csv> <out.json>
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

SPLIT = pd.Timestamp("2024-06-30")
EDGES = [-1e9, -10, -2, 2, 10, 1e9]
INDEX = {"us": "SPY", "europe": "^STOXX", "asia": "^N225"}
K_SMOOTH = 30


def _reports(tk):
    import yfinance as yf
    try:
        ed = yf.Ticker(tk).get_earnings_dates(limit=32)
    except Exception:
        return []
    out = []
    for ts, row in (ed if ed is not None else pd.DataFrame()).iterrows():
        est, rep = row.get("EPS Estimate"), row.get("Reported EPS")
        if pd.isna(rep) or pd.isna(est) or not est:
            continue
        ts = pd.Timestamp(ts)
        sur = row.get("Surprise(%)")
        if pd.isna(sur):
            sur = (rep - est) / abs(est) * 100
        out.append({"day": pd.Timestamp(ts.date()), "pre": ts.hour < 12, "s": float(sur)})
    return out


def collect(uni_csv, region, n_max, out_csv):
    import yfinance as yf
    uni = pd.read_csv(uni_csv)
    if region == "us":
        uni = uni[~uni["ticker"].astype(str).str.contains(r"\.")]
    uni = uni.sort_values("market_cap_usd", ascending=False).head(int(n_max))
    tks = list(uni["ticker"])
    idx_t = INDEX[region]
    rows = []
    for k in range(0, len(tks), 100):
        part = tks[k:k + 100]
        px = yf.download(part + [idx_t], period="8y", interval="1d", auto_adjust=True, progress=False, group_by="ticker", threads=True)
        ix = px[idx_t]["Close"].dropna()
        ixe = ix.ewm(span=50, adjust=False).mean()
        for tk in part:
            try:
                c = px[tk]["Close"].dropna()
            except Exception:
                continue
            if len(c) < 300:
                continue
            ret = c.pct_change()
            hist = []
            for r in sorted(_reports(tk), key=lambda x: x["day"]):
                i = c.index.searchsorted(r["day"]) if r["pre"] else c.index.searchsorted(r["day"], side="right")
                if i < 61 or i >= len(c):
                    continue
                d0 = c.index[i - 1]
                r1 = float(c.iloc[i] / c.iloc[i - 1] - 1)
                ixs = ix[:d0]
                up = bool(len(ixs) and ixs.iloc[-1] > ixe[:d0].iloc[-1])
                row = {"t": tk, "reg": region, "d": str(c.index[i].date()), "s": r["s"], "r1": r1,
                       "vol20": float(ret.iloc[i - 20:i].std()), "run20": float(c.iloc[i - 1] / c.iloc[i - 21] - 1),
                       "absr": float(np.mean([abs(h) for h in hist[-8:]])) if len(hist) >= 3 else np.nan, "mkt_up": int(up)}
                rows.append(row)
                hist.append(r1)
            time.sleep(0.2)
        print(f"{region}: {min(k + 100, len(tks))}/{len(tks)} Aktien · {len(rows)} Meldungen", flush=True)
    D = pd.DataFrame(rows)
    D = D[D["s"].abs() < 500] if len(D) else D
    D.to_csv(out_csv, index=False)


def _brier(p, y):
    return float(np.mean((np.asarray(p) - np.asarray(y)) ** 2))


def _boot(te, pa, pb, y=None, n=1000, seed=1):
    """95-%-Intervall des Brier-Unterschieds (b − a) per Block-Bootstrap über Monate (negativ = b besser)."""
    rng = np.random.default_rng(seed)
    m = te["dt"].dt.strftime("%Y-%m").to_numpy()
    months = np.unique(m)
    y = te["y"].to_numpy() if y is None else np.asarray(y)
    da = (np.asarray(pb) - y) ** 2 - (np.asarray(pa) - y) ** 2
    by = {mm: da[m == mm] for mm in months}
    vals = []
    for _ in range(n):
        pick = rng.choice(months, len(months))
        vals.append(np.mean(np.concatenate([by[x] for x in pick])))
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def analyze(folder, out_json):
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import log_loss, roc_auc_score
    D = pd.concat([pd.read_csv(f) for f in sorted(Path(folder).glob("*.csv"))], ignore_index=True)
    D["dt"] = pd.to_datetime(D["d"])
    D["y"] = (D["r1"] > 0).astype(int)
    D["crash"] = (D["r1"] <= -0.05).astype(int)
    D["b"] = pd.cut(D["s"], EDGES, labels=False, right=False).astype(int)
    tr, te = D[D["dt"] <= SPLIT], D[D["dt"] > SPLIT]
    out = {"n": {r: int((D["reg"] == r).sum()) for r in D["reg"].unique()}, "split": str(SPLIT.date())}
    print("Meldungen je Region:", out["n"], "· Lernen", len(tr), "· Prüfen", len(te))
    us_rate = tr[tr["reg"] == "us"].groupby("b")["y"].mean()

    # A1: eigene Quote je Region gegen US-Quote
    out["region"] = {}
    for reg in ("europe", "asia"):
        a, b_ = tr[tr["reg"] == reg], te[te["reg"] == reg]
        if len(a) < 300 or len(b_) < 200:
            print(f"{reg}: zu wenige Meldungen ({len(a)}/{len(b_)})")
            continue
        g = a.groupby("b")["y"].agg(["sum", "count"])
        own = {int(i): float((g.loc[i, "sum"] + K_SMOOTH * us_rate.get(i, .5)) / (g.loc[i, "count"] + K_SMOOTH)) for i in g.index}
        p_us, p_own = b_["b"].map(us_rate).fillna(.5).values, b_["b"].map(own).fillna(.5).values
        lo, hi = _boot(b_, p_us, p_own)
        r = {"brier_us": _brier(p_us, b_["y"]), "brier_own": _brier(p_own, b_["y"]), "hit_us": float(((p_us >= .5) == b_["y"]).mean()),
             "hit_own": float(((p_own >= .5) == b_["y"]).mean()), "diff_ci": [lo, hi], "adopt": bool(hi < 0), "up1": own,
             "n_test": int(len(b_)), "base_up": float(b_["y"].mean())}
        out["region"][reg] = r
        print(f"{reg}: Brier US {r['brier_us']:.4f} → eigen {r['brier_own']:.4f} (95 % {lo:+.4f}…{hi:+.4f}) · Treffer {r['hit_us']:.1%} → {r['hit_own']:.1%} · übernehmen: {r['adopt']}")
        print("   Quote je Gewinn-Stufe (eigen):", {k: round(v, 3) for k, v in own.items()}, "· US:", {int(k): round(v, 3) for k, v in us_rate.items()})

    # A2 / B: logistische Modelle über alle Regionen
    def feats(X, cols, ref):
        F = pd.DataFrame(index=X.index)
        for c in cols:
            m, sd = ref[c].median(), ref[c].std() or 1
            F[c] = ((X[c].fillna(m) - m) / sd).clip(-4, 4)
        return F

    def fit_eval(target, base_col, cols, label):
        rate = tr.groupby(["reg", "b"])[target].mean()
        btr = tr.set_index(["reg", "b"]).index.map(rate).astype(float)
        bte = te.set_index(["reg", "b"]).index.map(rate).astype(float)
        bte = np.where(np.isnan(bte), tr[target].mean(), bte)
        res = {"base_brier": _brier(bte, te[target]), "base_auc": float(roc_auc_score(te[target], bte)), "base_logloss": float(log_loss(te[target], np.clip(bte, 1e-3, 1 - 1e-3)))}
        if not cols:
            return res, bte
        Xtr = feats(tr, cols, tr).assign(base=np.log(np.clip(btr, 1e-3, 1) / np.clip(1 - btr, 1e-3, 1)))
        Xte = feats(te, cols, tr).assign(base=np.log(np.clip(bte, 1e-3, 1) / np.clip(1 - bte, 1e-3, 1)))
        lr = LogisticRegression(max_iter=2000).fit(Xtr, tr[target])
        p = lr.predict_proba(Xte)[:, 1]
        lo, hi = _boot(te, bte, p, te[target].to_numpy())
        res.update(brier=_brier(p, te[target]), auc=float(roc_auc_score(te[target], p)), logloss=float(log_loss(te[target], p)),
                   diff_ci=[lo, hi], coef=dict(zip(Xtr.columns, map(float, lr.coef_[0]))), icpt=float(lr.intercept_[0]),
                   scale={c: [float(tr[c].median()), float(tr[c].std() or 1)] for c in cols})
        q = pd.qcut(p, 5, labels=False, duplicates="drop")
        res["calib"] = [[float(p[q == k].mean()), float(te[target].values[q == k].mean()), int((q == k).sum())] for k in range(int(q.max()) + 1)]
        print(f"{label}: Brier {res['base_brier']:.4f} → {res['brier']:.4f} (95 % {lo:+.4f}…{hi:+.4f}) · AUC {res['base_auc']:.3f} → {res['auc']:.3f} · LogLoss {res['base_logloss']:.4f} → {res['logloss']:.4f}")
        print("   Eichung (vorhergesagt → eingetreten, n):", [(round(a, 3), round(b, 3), n) for a, b, n in res["calib"]])
        return res, p

    out["up"] = {}
    for cols in (["vol20"], ["absr"], ["mkt_up"], ["vol20", "absr", "mkt_up"]):
        r, _ = fit_eval("y", "b", cols, "steigt + " + "+".join(cols))
        r["adopt"] = bool(r["logloss"] < r["base_logloss"] and r["auc"] > r["base_auc"] and r["diff_ci"][1] < 0)
        out["up"]["+".join(cols)] = r
    r, _ = fit_eval("crash", "b", ["vol20", "absr", "run20", "mkt_up"], "Absturz ≤ −5 %")
    r["adopt"] = bool(r["brier"] < r["base_brier"] and r["auc"] > r["base_auc"] and r["diff_ci"][1] < 0)
    r["base_rate"] = float(te["crash"].mean())
    out["crash"] = r
    # B2: Absturz VOR den Zahlen – ohne Gewinn-Überraschung (die kennt man erst danach); Basis = Absturz-Quote je Region
    reg_rate = tr.groupby("reg")["crash"].mean()
    btr, bte = tr["reg"].map(reg_rate).values, te["reg"].map(reg_rate).values
    cols = ["vol20", "absr", "run20", "mkt_up"]
    lg = lambda v: np.log(np.clip(v, 1e-3, 1) / np.clip(1 - v, 1e-3, 1))
    Xtr = feats(tr, cols, tr).assign(base=lg(btr)); Xte = feats(te, cols, tr).assign(base=lg(bte))
    lr = LogisticRegression(max_iter=2000).fit(Xtr, tr["crash"])
    p = lr.predict_proba(Xte)[:, 1]
    lo, hi = _boot(te, bte, p, te["crash"].to_numpy())
    q = pd.qcut(p, 5, labels=False, duplicates="drop")
    pre = {"base_brier": _brier(bte, te["crash"]), "brier": _brier(p, te["crash"]), "base_auc": float(roc_auc_score(te["crash"], bte)),
           "auc": float(roc_auc_score(te["crash"], p)), "diff_ci": [lo, hi], "coef": dict(zip(Xtr.columns, map(float, lr.coef_[0]))),
           "icpt": float(lr.intercept_[0]), "scale": {c: [float(tr[c].median()), float(tr[c].std() or 1)] for c in cols},
           "reg_rate": {k: float(v) for k, v in reg_rate.items()},
           "calib": [[float(p[q == k].mean()), float(te["crash"].values[q == k].mean()), int((q == k).sum())] for k in range(int(q.max()) + 1)]}
    pre["adopt"] = bool(pre["brier"] < pre["base_brier"] and pre["auc"] > pre["base_auc"] + 0.02 and hi < 0)
    out["crash_pre"] = pre
    print(f"Absturz VOR den Zahlen (ohne Überraschung): Brier {pre['base_brier']:.4f} → {pre['brier']:.4f} (95 % {lo:+.4f}…{hi:+.4f}) · AUC {pre['base_auc']:.3f} → {pre['auc']:.3f} · übernehmen: {pre['adopt']}")
    print("   Eichung (vorhergesagt → eingetreten, n):", [(round(a, 3), round(b, 3), n) for a, b, n in pre["calib"]])
    print("   Gewichte:", {k: round(v, 3) for k, v in pre["coef"].items()})
    # Absturz-Quote je Fünftel „frühere Reaktion der Aktie“ (Prüfzeit, beschreibend)
    te3 = te.dropna(subset=["absr"]).assign(aq=lambda d: pd.qcut(d["absr"], 5, labels=False, duplicates="drop"))
    print("Absturz-Quote je Fünftel frühere Reaktionsstärke:", [(int(a), round(float(b), 3)) for a, b in te3.groupby("aq")["crash"].mean().items()])
    # beschreibend: Absturz-Quote je Fünftel Schwankung (Prüfzeit)
    te2 = te.assign(vq=pd.qcut(te["vol20"], 5, labels=False, duplicates="drop"))
    out["crash_by_vol"] = te2.groupby("vq")["crash"].agg(["mean", "count"]).reset_index().to_dict("records")
    print("Absturz-Quote je Fünftel Schwankung (Prüfzeit):", [(int(x["vq"]), round(x["mean"], 3), int(x["count"])) for x in out["crash_by_vol"]])
    json.dump(out, open(out_json, "w"), indent=1, default=float)


if __name__ == "__main__":
    if sys.argv[1] == "collect":
        collect(*sys.argv[2:6])
    else:
        analyze(sys.argv[2], sys.argv[3])
