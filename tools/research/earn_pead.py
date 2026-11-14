"""Quartalszahlen 2: Die handelbare Frage – läuft die Aktie NACH der Eröffnung weiter? (Nutzer-Auftrag 14.11.2026)

Anlass: Die bisherige Prognose (Schluss vor den Zahlen → Schluss am Tag danach) enthält die Kurslücke über Nacht, die ein
Anleger nach einer Meldung nach Börsenschluss gar nicht mitnehmen kann; ihre Trefferquote liegt live bei ~53–56 %.
Handelbar ist: Einstieg zur Eröffnung des ersten Handelstags nach den Zahlen (Überraschung UND Kurslücke sind dann
bekannt), Ausstieg zum Schluss nach 2 bzw. 5 Handelstagen – marktbereinigt (minus SPY im selben Fenster).

Vorab festgelegt (vor dem ersten Lauf, nicht nachträglich verändert):
- Daten: die N größten US-Aktien (universe_us.csv), Yahoo-Meldetermine mit Gewinn-Erwartung/-Ist seit ~2018, Tageskurse.
- Ziele: y2x = (Schluss Tag+1 / Eröffnung Tag 0) − SPY dasselbe > 0;  y5x = dasselbe bis Schluss Tag+4.
  Zum Vergleich: y1 = Schluss Tag 0 > Schluss davor (das heutige App-Ziel; enthält die Lücke, daher zur Eröffnung trivial).
- Nachtrag nach Lauf 1 (14.11.2026, große Werte: y2x/y5x ohne Signal, AUC 0,51), vor Lauf 2 festgelegt:
  y0x = Eröffnung → Schluss Tag 0, marktbereinigt (läuft die Lücke am ersten Tag weiter oder dreht sie?), und dieselbe
  Prüfung für kleinere Werte (Rang 901–2400 nach Börsenwert), wo der Nachlauf laut Forschung am ehesten überlebt.
- Merkmale (alle zur Eröffnung von Tag 0 bekannt): Gewinn-Überraschung s, Kurslücke gap, Kurslücke relativ zur üblichen
  Reaktion der Aktie (gapz), Übereinstimmung Lücke/Überraschung (agree), Lauf 20 Tage vs. SPY (run20), Schwankung
  20 Tage (vol20), übliche Reaktion (absr), Marktlage (SPY über EMA 50), Umsatzvolumen am Vortag relativ (vpre).
- Prüfung: Purged Walk-Forward – Prüfjahre 2021 … 2026 einzeln; gelernt nur mit Meldungen, die mindestens 10 Handelstage
  vor Beginn des Prüfjahrs liegen (Sperrfrist, damit sich keine 5-Tage-Fenster überlappen). Kein Zufalls-Split.
- Modelle: M0 Basisrate · M1 Quote je Gewinn-Stufe (wie die App heute) · M2 logistisch (L2) · M3 Gradient Boosting
  (sklearn HistGradientBoosting, flach und stark geglättet, Platt-Eichung auf dem jüngsten Fünftel der Lernzeit).
- Übernahme in die App nur, wenn ALLE gelten: (a) Brier besser als M1 und M0, 95-%-Block-Bootstrap (Monate) des
  Unterschieds ohne Null; (b) AUC ≥ M1 + 0,01; (c) besser als M1 in mindestens 4 der 6 Prüfjahre; (d) „Rückenwind“-Fälle
  (p ≥ 55 %) bringen nach 0,15 % Kosten je Trade im Mittel eine positive marktbereinigte Rendite, 95-%-Intervall über null.
  Bei Gleichstand gewinnt M2 (in der App nachrechenbar, weniger Überanpassung).

    python tools/research/earn_pead.py collect <universe_us.csv> <n_max> <out.csv> [überspringen]
    python tools/research/earn_pead.py analyze <in.csv> <out.json>
"""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

EDGES = [-1e9, -10, -2, 2, 10, 1e9]
YEARS = [2021, 2022, 2023, 2024, 2025, 2026]
EMBARGO = 10
COST = 0.0015
FEATS = ["s_c", "s_sig", "gap", "gapz", "agree", "run20", "vol20", "absr", "mkt_up", "vpre"]


def _reports(tk):
    import yfinance as yf
    for k in range(3):
        try:
            ed = yf.Ticker(tk).get_earnings_dates(limit=40)
            break
        except Exception:
            time.sleep(2 + 3 * k)
    else:
        return tk, []
    out = []
    for ts, row in (ed if ed is not None else pd.DataFrame()).iterrows():
        est, rep = row.get("EPS Estimate"), row.get("Reported EPS")
        if pd.isna(rep) or pd.isna(est) or not est:
            continue
        ts = pd.Timestamp(ts)
        local = ts.tz_convert("America/New_York") if ts.tzinfo else ts
        sur = row.get("Surprise(%)")
        if pd.isna(sur):
            sur = (rep - est) / abs(est) * 100
        out.append({"day": pd.Timestamp(local.date()), "pre": local.hour < 12, "s": float(sur)})
    return tk, out


def collect(uni_csv, n_max, out_csv, skip=0):
    import yfinance as yf
    uni = pd.read_csv(uni_csv)
    uni = uni[~uni["ticker"].astype(str).str.contains(r"\.")].sort_values("market_cap_usd", ascending=False).iloc[int(skip):int(skip) + int(n_max)]
    tks = list(uni["ticker"])
    spy = yf.download("SPY", period="9y", interval="1d", auto_adjust=True, progress=False)
    spy.columns = [c[0] if isinstance(c, tuple) else c for c in spy.columns]
    so, sc = spy["Open"], spy["Close"]
    sema = sc.ewm(span=50, adjust=False).mean()
    rows = []
    for k in range(0, len(tks), 100):
        part = tks[k:k + 100]
        px = yf.download(part, period="9y", interval="1d", auto_adjust=True, progress=False, group_by="ticker", threads=True)
        with ThreadPoolExecutor(6) as ex:
            reps = dict(ex.map(_reports, part))
        for tk in part:
            try:
                d = px[tk][["Open", "Close", "Volume"]].dropna()
            except Exception:
                continue
            if len(d) < 300:
                continue
            o, c, v = d["Open"], d["Close"], d["Volume"]
            ret = c.pct_change()
            hr, hg = [], []
            for r in sorted(reps.get(tk) or [], key=lambda x: x["day"]):
                i = c.index.searchsorted(r["day"]) if r["pre"] else c.index.searchsorted(r["day"], side="right")
                if i < 61 or i + 4 >= len(c):
                    continue
                d0, dm1 = c.index[i], c.index[i - 1]
                if d0 not in sc.index or c.index[i + 4] not in sc.index or dm1 not in sc.index:
                    continue
                si = sc.index.get_loc(d0)
                gap = float(o.iloc[i] / c.iloc[i - 1] - 1)
                r1 = float(c.iloc[i] / c.iloc[i - 1] - 1)
                pe2, pe5 = float(c.iloc[i + 1] / o.iloc[i] - 1), float(c.iloc[i + 4] / o.iloc[i] - 1)
                sp2, sp5 = float(sc.iloc[si + 1] / so.iloc[si] - 1), float(sc.iloc[si + 4] / so.iloc[si] - 1)
                srun = float(sc.loc[dm1] / sc.iloc[si - 21] - 1)
                vv = v.iloc[i - 21:i - 1].mean()
                rows.append({"t": tk, "d": str(d0.date()), "s": r["s"], "pre": int(r["pre"]), "gap": gap, "r1": r1,
                             "oc1": float(c.iloc[i] / o.iloc[i] - 1), "x0": float(c.iloc[i] / o.iloc[i] - 1) - float(sc.iloc[si] / so.iloc[si] - 1), "pe2": pe2, "pe5": pe5, "x2": pe2 - sp2, "x5": pe5 - sp5,
                             "vol20": float(ret.iloc[i - 20:i].std()), "run20": float(c.iloc[i - 1] / c.iloc[i - 21] - 1) - srun,
                             "absr": float(np.mean(np.abs(hr[-8:]))) if len(hr) >= 3 else np.nan,
                             "absg": float(np.mean(np.abs(hg[-8:]))) if len(hg) >= 3 else np.nan,
                             "mkt_up": int(sc.loc[dm1] > sema.loc[dm1]), "vpre": float(v.iloc[i - 1] / vv) if vv else np.nan})
                hr.append(r1)
                hg.append(gap)
        print(f"{min(k + 100, len(tks))}/{len(tks)} Aktien · {len(rows)} Meldungen", flush=True)
    D = pd.DataFrame(rows)
    D = D[D["s"].abs() < 500]
    D.to_csv(out_csv, index=False)


def prep(D):
    D = D.copy()
    D["dt"] = pd.to_datetime(D["d"])
    D["b"] = pd.cut(D["s"], EDGES, labels=False, right=False).astype(int)
    D["s_c"] = D["s"].clip(-50, 50) / 50
    D["s_sig"] = D["s"].clip(-10, 10) / 10
    D["gapz"] = (D["gap"] / D["absg"].where(D["absg"] > 0.005)).clip(-6, 6)
    D["agree"] = np.sign(D["gap"]) * np.sign(D["s"])
    D["vpre"] = np.log(D["vpre"].clip(0.05, 50))
    for y, col in (("y1", "r1"), ("y0x", "x0"), ("y2x", "x2"), ("y5x", "x5")):
        D[y] = (D[col] > 0).astype(int)
    return D.sort_values("dt").reset_index(drop=True)


def _scale(tr, X):
    out = pd.DataFrame(index=X.index)
    sc = {}
    for c in FEATS:
        m, sd = float(tr[c].median()), float(tr[c].std() or 1)
        sc[c] = [m, sd]
        out[c] = ((X[c].fillna(m) - m) / sd).clip(-4, 4)
    return out, sc


def _boot(m, a, b, y, n=1000, seed=1):
    """95-%-Intervall des mittleren Unterschieds (b − a) der quadrierten Fehler, Block-Bootstrap über Monate."""
    rng = np.random.default_rng(seed)
    da = (b - y) ** 2 - (a - y) ** 2
    months = np.unique(m)
    by = {k: da[m == k] for k in months}
    vals = [np.mean(np.concatenate([by[k] for k in rng.choice(months, len(months))])) for _ in range(n)]
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def _boot_mean(m, x, n=1000, seed=2):
    rng = np.random.default_rng(seed)
    months = np.unique(m)
    by = {k: x[m == k] for k in months}
    vals = [np.mean(np.concatenate([by[k] for k in rng.choice(months, len(months))])) for _ in range(n)]
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def run_target(D, y, ret):
    from sklearn.calibration import CalibratedClassifierCV  # noqa: F401  (nur Versionsprüfung)
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    P = {k: np.full(len(D), np.nan) for k in ("M0", "M1", "M2", "M3")}
    for yr in YEARS:
        te = (D["dt"].dt.year == yr).to_numpy()
        if te.sum() < 200:
            continue
        start = D.loc[te, "dt"].min()
        cut = start - pd.tseries.offsets.BDay(EMBARGO)
        tr = (D["dt"] < cut).to_numpy()
        if tr.sum() < 2000:
            continue
        T, E = D[tr], D[te]
        P["M0"][te] = T[y].mean()
        rate = T.groupby("b")[y].agg(["sum", "count"])
        P["M1"][te] = E["b"].map(lambda b: (rate.loc[b, "sum"] + 20 * T[y].mean()) / (rate.loc[b, "count"] + 20) if b in rate.index else T[y].mean()).to_numpy()
        Xt, _ = _scale(T, T)
        Xe, _ = _scale(T, E)
        lr = LogisticRegression(C=0.5, max_iter=3000).fit(Xt, T[y])
        P["M2"][te] = lr.predict_proba(Xe)[:, 1]
        n_cal = len(T) // 5                                          # Platt-Eichung auf dem jüngsten Fünftel der Lernzeit
        gb = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.04, max_iter=250, min_samples_leaf=300, l2_regularization=1.0, random_state=0)
        gb.fit(Xt.iloc[:-n_cal], T[y].iloc[:-n_cal])
        raw_c = gb.predict_proba(Xt.iloc[-n_cal:])[:, 1]
        pl = LogisticRegression(C=1e6).fit(np.log(np.clip(raw_c, 1e-4, 1 - 1e-4) / np.clip(1 - raw_c, 1e-4, 1)).reshape(-1, 1), T[y].iloc[-n_cal:])
        raw_e = gb.predict_proba(Xe)[:, 1]
        P["M3"][te] = pl.predict_proba(np.log(np.clip(raw_e, 1e-4, 1 - 1e-4) / np.clip(1 - raw_e, 1e-4, 1)).reshape(-1, 1))[:, 1]
    ok = ~np.isnan(P["M2"])
    E = D[ok]
    yy, mo, rr = E[y].to_numpy(), E["dt"].dt.strftime("%Y-%m").to_numpy(), E[ret].to_numpy()
    res = {"n_test": int(ok.sum()), "up": float(yy.mean())}
    for k, p in P.items():
        p = p[ok]
        r = {"brier": float(np.mean((p - yy) ** 2)), "auc": float(roc_auc_score(yy, p)) if k != "M0" else 0.5, "hit": float(((p >= .5) == yy).mean())}
        if k in ("M2", "M3"):
            r["vs_M1"] = _boot(mo, P["M1"][ok], p, yy)
            r["vs_M0"] = _boot(mo, P["M0"][ok], p, yy)
            yrs = E["dt"].dt.year.to_numpy()
            r["years_better"] = int(sum(np.mean((p[yrs == a] - yy[yrs == a]) ** 2) < np.mean((P["M1"][ok][yrs == a] - yy[yrs == a]) ** 2) for a in np.unique(yrs)))
            r["years"] = int(len(np.unique(yrs)))
            lo = p >= .55
            r["long_n"] = int(lo.sum())
            if lo.sum() >= 50:
                net = rr[lo] - COST
                r["long_ret"] = float(net.mean())
                r["long_ci"] = _boot_mean(mo[lo], net)
                r["long_hit"] = float((rr[lo] > 0).mean())
            sh = p <= .45
            r["weak_n"] = int(sh.sum())
            r["weak_ret"] = float(rr[sh].mean()) if sh.sum() else None
            q = pd.qcut(p, 10, labels=False, duplicates="drop")
            r["calib"] = [[round(float(p[q == j].mean()), 3), round(float(yy[q == j].mean()), 3), int((q == j).sum())] for j in range(int(q.max()) + 1)]
            m1 = res["M1"]
            r["adopt"] = bool(r["brier"] < m1["brier"] and r["brier"] < res["M0"]["brier"] and r["vs_M1"][1] < 0 and r["vs_M0"][1] < 0
                              and r["auc"] >= m1["auc"] + 0.01 and r["years_better"] >= 4 and r.get("long_ci", [0])[0] > 0)
        res[k] = r
    # finales Modell M2 auf allen Daten (für die App), Merkmals-Skalierung mitgeben
    from sklearn.linear_model import LogisticRegression as LR
    X, sc = _scale(D, D)
    lr = LR(C=0.5, max_iter=3000).fit(X, D[y])
    res["final_M2"] = {"f": FEATS, "coef": [round(float(v), 4) for v in lr.coef_[0]], "icpt": round(float(lr.intercept_[0]), 4), "scale": sc}
    return res


def analyze(in_csv, out_json):
    D = prep(pd.read_csv(in_csv))
    out = {"n": int(len(D)), "tickers": int(D["t"].nunique()), "von": str(D["dt"].min().date()), "bis": str(D["dt"].max().date())}
    print(f"# Quartalszahlen 2 – handelbare Frage (Forschung)\n\n{out['n']} Meldungen, {out['tickers']} US-Aktien, {out['von']} bis {out['bis']}.\n")
    print("Beschreibend: Anteil Lücke in Richtung der Überraschung", round(float((D["agree"] > 0).mean()), 3),
          "· mittlere |Lücke|", round(float(D["gap"].abs().mean()), 4), "· mittlere |Tag 0 nach Eröffnung|", round(float(D["oc1"].abs().mean()), 4))
    for y, ret, lab in (("y1", "r1", "Tag 1 inkl. Lücke (heutiges App-Ziel)"), ("y0x", "x0", "Tag 0 ab Eröffnung bis Schluss, marktbereinigt"), ("y2x", "x2", "2 Tage ab Eröffnung, marktbereinigt"), ("y5x", "x5", "5 Tage ab Eröffnung, marktbereinigt")):
        r = run_target(D, y, ret)
        out[y] = r
        print(f"\n## {lab} (n Prüfung {r['n_test']}, Anteil positiv {r['up']:.1%})\n")
        print("| Modell | Brier | AUC | Treffer | vs. M1 (95 %) | Jahre besser | Rückenwind-Fälle (p ≥ 55 %) netto | übernehmen |\n|---|---|---|---|---|---|---|---|")
        for k in ("M0", "M1", "M2", "M3"):
            m = r[k]
            extra = ""
            if k in ("M2", "M3"):
                lr_ = f"{m.get('long_n', 0)} Fälle, Ø {m['long_ret'] * 100:+.2f} % ({m['long_ci'][0] * 100:+.2f} … {m['long_ci'][1] * 100:+.2f})" if m.get("long_ret") is not None else f"{m.get('long_n', 0)} Fälle"
                extra = f" | {m['vs_M1'][0]:+.4f} … {m['vs_M1'][1]:+.4f} | {m['years_better']}/{m['years']} | {lr_} | {'ja' if m['adopt'] else 'nein'}"
            else:
                extra = " | – | – | – | –"
            print(f"| {k} | {m['brier']:.4f} | {m['auc']:.3f} | {m['hit']:.1%}{extra} |")
        for k in ("M2", "M3"):
            print(f"Eichung {k} (vorhergesagt → eingetreten, n):", r[k]["calib"])
        print("Gewichte M2 (alle Daten, standardisiert):", dict(zip(r["final_M2"]["f"], r["final_M2"]["coef"])))
    json.dump(out, open(out_json, "w"), indent=1, default=float)


if __name__ == "__main__":
    if sys.argv[1] == "collect":
        collect(*sys.argv[2:6])
    else:
        analyze(sys.argv[2], sys.argv[3])
