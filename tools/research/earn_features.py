"""Bessere Quartalszahlen-Prognose? Test zusätzlicher Merkmale (Nutzer-Auftrag 28./29.10.2026).

Vorab festgelegt: Ziel = Kurs am ersten Handelstag nach der Meldung höher (r1 > 0). Basis = heutiges App-Modell
(Steig-Quote je Gewinn-Überraschungs-Gruppe). Kandidaten (nur Wissen bis zur Meldung, kein Blick nach vorn):
  run20   Lauf der Aktie 20 Handelstage vor der Meldung minus S&P 500 (SPY)
  run60   dasselbe über 60 Tage
  own     Anteil der früheren Meldungen DIESER Aktie (mind. 4), nach denen sie stieg
  ownbeat dasselbe nur für frühere Meldungen über Erwartung
  revg    Umsatzwachstum zum Vorjahresquartal (SEC-Finanzdaten, gemeldetes Quartal)
  reva    Beschleunigung: revg minus revg des Vorquartals
Lernen: Meldungen bis 30.06.2024 · Prüfen: danach. Ein Merkmal kommt in die App, wenn ein Modell mit ihm im Prüfzeitraum
eine bessere Log-Loss UND eine bessere AUC hat als das Basismodell (logistische Regression, auf Lernzeitraum geschätzt).
    python tools/research/earn_features.py <universe_us.csv> <sec_cik.json> <out.json> [max_aktien]
"""
from __future__ import annotations

import json
import sys
import time

import numpy as np
import pandas as pd

SPLIT = pd.Timestamp("2024-06-30")
UA = {"User-Agent": "Mozilla/5.0 (Kairo)"}


def reports(tk):
    import yfinance as yf
    try:
        ed = yf.Ticker(tk).get_earnings_dates(limit=28)
    except Exception:
        return []
    out = []
    for ts, row in (ed if ed is not None else pd.DataFrame()).iterrows():
        est, rep = row.get("EPS Estimate"), row.get("Reported EPS")
        if pd.isna(rep) or pd.isna(est):
            continue
        ts = pd.Timestamp(ts)
        local = ts.tz_convert("America/New_York") if ts.tzinfo else ts
        sur = row.get("Surprise(%)")
        if pd.isna(sur):
            sur = (rep - est) / abs(est) * 100 if est else np.nan
        out.append({"day": pd.Timestamp(local.date()), "pre": local.hour < 12, "s": float(sur)})
    return out


def revenue(cik):
    """Quartalsumsätze (3 Monate) aus SEC companyfacts: {Quartalsende: Umsatz}."""
    import requests
    try:
        j = requests.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json", headers=UA, timeout=30).json()
    except Exception:
        return {}
    g = j.get("facts", {}).get("us-gaap", {})
    best = {}
    for tag in ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "RevenueFromContractWithCustomerIncludingAssessedTax"):
        for u in (g.get(tag, {}).get("units", {}).get("USD", [])):
            try:
                st, en = pd.Timestamp(u["start"]), pd.Timestamp(u["end"])
            except Exception:
                continue
            if 80 <= (en - st).days <= 100:
                best.setdefault(en, u["val"])
    return best


def main(uni_csv, cik_json, out_json, n_max=600):
    import yfinance as yf
    uni = pd.read_csv(uni_csv)
    uni = uni[~uni["ticker"].astype(str).str.contains(r"\.")].sort_values("market_cap_usd", ascending=False).head(n_max)
    cik = json.load(open(cik_json))["cik"]
    tks = list(uni["ticker"])
    px = yf.download(tks + ["SPY"], period="8y", interval="1d", auto_adjust=True, progress=False, group_by="ticker", threads=True)
    spy = px["SPY"]["Close"].dropna()
    rows = []
    for k, tk in enumerate(tks):
        try:
            c = px[tk]["Close"].dropna()
        except Exception:
            continue
        if len(c) < 300:
            continue
        rv = revenue(cik[tk]) if tk in cik else {}
        q = sorted(rv)
        hist = []
        for r in sorted(reports(tk), key=lambda x: x["day"]):
            idx = c.index
            i = idx.searchsorted(r["day"]) if r["pre"] else idx.searchsorted(r["day"], side="right")
            if i < 61 or i >= len(idx):
                continue
            r1 = float(c.iloc[i] / c.iloc[i - 1] - 1)
            d0 = idx[i - 1]
            sp = spy.reindex(idx).ffill()
            run20 = float(c.iloc[i - 1] / c.iloc[i - 21] - 1 - (sp.iloc[i - 1] / sp.iloc[i - 21] - 1))
            run60 = float(c.iloc[i - 1] / c.iloc[i - 61] - 1 - (sp.iloc[i - 1] / sp.iloc[i - 61] - 1))
            past = [h for h in hist]
            own = np.mean([h["r1"] > 0 for h in past]) if len(past) >= 4 else np.nan
            pb = [h for h in past if h["s"] > 2]
            ownbeat = np.mean([h["r1"] > 0 for h in pb]) if len(pb) >= 3 else np.nan
            revg = reva = np.nan
            qe = [e for e in q if pd.Timedelta(days=0) < r["day"] - e <= pd.Timedelta(days=100)]
            if qe:
                e = qe[-1]
                ly = [x for x in q if abs((e - x).days - 365) <= 20]
                pq = [x for x in q if 70 <= (e - x).days <= 110]
                if ly and rv[ly[-1]]:
                    revg = rv[e] / rv[ly[-1]] - 1
                    if pq:
                        lpy = [x for x in q if abs((pq[-1] - x).days - 365) <= 20]
                        if lpy and rv[lpy[-1]]:
                            reva = revg - (rv[pq[-1]] / rv[lpy[-1]] - 1)
            row = {"t": tk, "d": str(idx[i].date()), "s": r["s"], "r1": r1, "run20": run20, "run60": run60, "own": own,
                   "ownbeat": ownbeat, "revg": revg, "reva": reva}
            rows.append(row)
            hist.append(row)
        if k % 50 == 0:
            print(f"{k}/{len(tks)} · {len(rows)} Meldungen", flush=True)
        time.sleep(0.25)
    D = pd.DataFrame(rows)
    D = D[D["s"].abs() < 500].copy()
    D.to_csv("earn_features.csv", index=False)
    analyse(D, out_json)


def analyse(D, out_json):
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import log_loss, roc_auc_score
    D = D.copy()
    D["dt"] = pd.to_datetime(D["d"])
    D["y"] = (D["r1"] > 0).astype(int)
    edges = [-1e9, -10, -2, 2, 10, 1e9]
    D["b"] = pd.cut(D["s"], edges, labels=False, right=False)
    tr, te = D[D["dt"] <= SPLIT], D[D["dt"] > SPLIT]
    rate = tr.groupby("b")["y"].mean()
    print(f"Meldungen: {len(D)} · Lernen {len(tr)} · Prüfen {len(te)}")
    res = {}

    def evaluate(name, cols):
        Xtr = pd.DataFrame({"base": tr["b"].map(rate)})
        Xte = pd.DataFrame({"base": te["b"].map(rate)})
        for ccol in cols:
            m, sd = tr[ccol].median(), tr[ccol].std() or 1
            Xtr[ccol] = ((tr[ccol].fillna(m) - m) / sd).clip(-4, 4)
            Xte[ccol] = ((te[ccol].fillna(m) - m) / sd).clip(-4, 4)
            Xtr[ccol + "_na"] = tr[ccol].isna().astype(int)
            Xte[ccol + "_na"] = te[ccol].isna().astype(int)
        lr = LogisticRegression(max_iter=1000, C=1.0).fit(Xtr, tr["y"])
        p = lr.predict_proba(Xte)[:, 1]
        conf = (p >= .58) | (p <= .42)
        acc = float(((p >= .5) == te["y"].astype(bool))[conf].mean()) if conf.any() else float("nan")
        r = {"logloss": float(log_loss(te["y"], p)), "auc": float(roc_auc_score(te["y"], p)), "acc_all": float(((p >= .5) == te["y"].astype(bool)).mean()),
             "share_conf": float(conf.mean()), "acc_conf": acc, "coef": dict(zip(Xtr.columns, map(float, lr.coef_[0])))}
        res[name] = r
        print(f"{name:<28} LogLoss {r['logloss']:.4f} · AUC {r['auc']:.3f} · Treffer gesamt {r['acc_all']:.1%} · sicher (≥58/≤42 %) {r['share_conf']:.0%} der Fälle, davon richtig {acc:.1%}")
        return r

    base = evaluate("Basis (Gewinn-Überraschung)", [])
    keep = []
    for f in ("run20", "run60", "own", "ownbeat", "revg", "reva"):
        r = evaluate(f"+ {f}", [f])
        if r["logloss"] < base["logloss"] and r["auc"] > base["auc"]:
            keep.append(f)
    print("Bestanden (einzeln):", keep or "keins")
    final = evaluate("Kombination bestandener", keep) if keep else base
    # einfache Tabellen für die App: Steig-Quote je Gruppe × Lauf davor (nur beschreibend)
    D["runq"] = pd.qcut(D["run20"], 3, labels=["schwach", "normal", "stark"])
    tab = D.groupby(["b", "runq"], observed=True)["y"].agg(["mean", "count"]).reset_index()
    print("\nSteig-Quote je Überraschung × Lauf 20 T. davor:")
    print(tab.to_string(index=False))
    json.dump({"n": int(len(D)), "split": str(SPLIT.date()), "results": res, "keep": keep, "final": final}, open(out_json, "w"), indent=1, default=float)


if __name__ == "__main__":
    if sys.argv[1] == "--analyse":
        analyse(pd.read_csv(sys.argv[2]), sys.argv[3])
    else:
        main(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 600)
