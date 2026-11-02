"""W2-Audit P1 – korrigierte historische Prüfung (vorab festgelegt 02.11.2026, VOR dem ersten Lauf).

Alles läuft über backend/mrsim.py (dieselbe Simulation wie der Live-Schattentest): Auswahl abends nach RSI(2), je Tag
höchstens die 10 stärksten Signale (wie live), Kapitalreservierung je Order, kein Nachrücken, ganze Stücke, Gebühr unter
250 €, Spread nach Liquidität, Bewertung in EUR (USA/Europa mit echten Wechselkursen; Vorzeit/Asien in Landeswährung).

Ausführungsmodelle: opt (Berührung), kons (Briefkurs muss Limit erreichen, Tief ≤ L·(1−hs−0,1 %)), streng (… −0,5 %).
Kosten: null, basis (PRIME+: 0,99 € < 250 €, Spread 0,15 %/0,30 %), free (0,99 € je Order), stress (Spread ×2, 0,05 %
Schlupf, 0,1 % FX je Seite).

Kontrollen (gleiche Überlebens-Verzerrung): CTRL-L = zufälliger Tag im Aufwärtstrend mit gleichem Limit, CTRL = mit
Kauf zur Eröffnung. Gleich häufig wie das Signal (Zufall mit festem Startwert).

VORAB FESTGELEGTE PRÜFKRITERIEN (Status im Abschlussbericht nur danach):
  K1 Signal-Vorteil: Ø Netto-Ertrag je Trade (basis) W2 − CTRL-L > 0 im Modell kons, Block-Bootstrap (Monate) p < 0,05,
     in USA/Europa gesamt UND in Vorzeit UND in Asien.
  K2 Depot umsetzbar: Depot W2 (10.000 €, kons, basis, 5 Plätze) mit positiver Jahresrendite in Train, Validierung UND
     Holdout und über dem Depot CTRL-L (gleiche Regeln).
  K3 Kostenfestigkeit: Depot W2 (kons) mit Kosten „stress“ über 0 % p. a. gesamt.
  K4 Mehrwert im Gesamtportfolio: 90 % Welt-ETF + 10 % W2 (kons, basis, monatlich ausgeglichen) mit höherer Rendite
     als 100 % Welt-ETF bei nicht mehr als 2 Prozentpunkten größerem Rückgang (2008–2026).
  K5 Kleinkapital: mit 3.000 € Tradingkapital (Mindestorder-Regel 250 €) Depot W2 (kons, basis) > 0 % p. a.
  Status „Historisch interessant, Umsetzung offen“, wenn K1 und K2 erfüllt; „Prospektiv und nach Kosten belastbar
  bestätigt“ nur mit Live-Schattentest (Kriterien in docs/W2_FINAL_VERDICT.md) – historisch NICHT erreichbar;
  sonst „Nicht ausreichend bestätigt oder widerlegt“.

Zusätzlich (beschreibend, keine Entscheidung): Vorteil je Kalenderjahr (Überlebens-Verzerrung: wächst der Vorteil mit dem
Abstand zum Einfrierdatum 2026?), nach Region, nach VIX, Verlustserien, Kapitalszenarien 500–20.000 €, Vergleich mit B60,
Dual Momentum (S16-B-Näherung) und Welt-ETF.

    python -m research.reversal.w2audit run --set main --data v1 --out OUT [--b60 mrc_curve_B0.parquet]
    python -m research.reversal.w2audit run --set pre|asia --px DIR --universe U.csv --out OUT
    python -m research.reversal.w2audit report --dir OUT
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from backend import mrsim as S

PERIODS = {"Train": ("2008-01-01", "2016-12-31"), "Validierung": ("2017-01-01", "2021-12-31"), "Holdout": ("2022-01-01", "2026-10-16")}
SETS = {"main": ("2008-01-01", "2026-10-16"), "pre": ("1999-01-01", "2007-12-31"), "asia": ("2008-01-01", "2026-10-16")}
UNIVERSE = "research/strategy_championship/data/universe_frozen_2026-10-16.csv"
FX_T = {"USD": "EURUSD=X", "GBP": "EURGBP=X", "CHF": "EURCHF=X", "SEK": "EURSEK=X", "NOK": "EURNOK=X", "DKK": "EURDKK=X",
        "PLN": "EURPLN=X", "CAD": "EURCAD=X", "JPY": "EURJPY=X"}
CAPS = (500, 1000, 3000, 5000, 10000, 20000)
SEED = 20261102
TOP = 10


def _adjust(g: pd.DataFrame) -> pd.DataFrame:
    g = g.sort_index()
    g = g[~g.index.duplicated()].dropna(subset=["Open", "High", "Low", "Close"])
    g = g[g["Close"] > 0]
    f = (g["AdjClose"] / g["Close"]).where(lambda s: np.isfinite(s) & (s > 0)).ffill().fillna(1.0) if "AdjClose" in g else 1.0
    out = g[["Open", "High", "Low", "Close"]].mul(f, axis=0)
    out["Volume"] = g["Volume"] * 1.0 if "Volume" in g else 0.0
    return out


def load(a) -> tuple[dict, dict, dict, dict]:
    """→ (ind {t: DataFrame}, cur {t}, region {t}, eur {t: np.ndarray})"""
    uni = pd.read_csv(a.universe or UNIVERSE)
    cur = dict(zip(uni["ticker"], uni["currency"].fillna("USD")))
    region = dict(zip(uni["ticker"], uni.get("region", pd.Series(["asia"] * len(uni))).fillna("?")))
    if a.set == "main":
        raw = pd.read_parquet(Path(a.data) / "prices_v1.parquet")
        fxr = pd.read_parquet(Path(a.data) / "fx_v1.parquet")
        fxr["date"] = pd.to_datetime(fxr["date"])
        fx = {}
        for c, t in FX_T.items():
            z = fxr[fxr["ticker"] == t].set_index("date")["Close"].sort_index()
            fx[c] = z[~z.index.duplicated()]
    else:
        raw = pd.concat([pd.read_parquet(f) for f in sorted(Path(a.px).glob("px_*.parquet"))])
        fx = {}
    raw["date"] = pd.to_datetime(raw["date"])
    ind, eur = {}, {}
    for t, g in raw.groupby("ticker"):
        c = cur.get(t, "USD")
        if a.set == "main" and str(region.get(t, "")).lower() not in ("us", "eu", "europe"):
            continue
        if c not in S.FX_USD:
            continue
        d = _adjust(g.set_index("date"))
        if len(d) < 260:
            continue
        x = S.indicators(d, c)
        ind[t] = x
        if a.set == "main" and c != "EUR":
            base, scale = ("GBP", 100.0) if c in ("GBp", "GBX") else (c, 1.0)
            r = fx.get(base)
            eur[t] = (1.0 / (r.reindex(x.index, method="ffill").bfill().to_numpy(float) * scale)) if r is not None else None
        else:
            eur[t] = None
    return ind, cur, region, eur


def candidates(ind: dict, s0, s1, rng) -> tuple[list, list]:
    sig, base_n = [], 0
    for t, x in ind.items():
        sig += S.signal_rows(t, x, s0, s1)
    for t, x in ind.items():
        m = ((x["c"] > x["sma200"]) & (x["c"] >= 1) & (x["adv"] >= 5e6)).to_numpy() & (x.index >= s0) & (x.index <= s1)
        base_n += int(m.sum())
    p = min(1.0, len(sig) / max(base_n, 1))
    ctrl = []
    for t, x in ind.items():
        m = ((x["c"] > x["sma200"]) & (x["c"] >= 1) & (x["adv"] >= 5e6)).to_numpy() & (x.index >= s0) & (x.index <= s1)
        pick = np.flatnonzero(m & (rng.random(len(x)) < p))
        for i in pick:
            lim = float(x["lim"].iat[i])
            ctrl.append({"t": t, "d": x.index[i], "rsi2": float(rng.random() * 100), "lim": lim if lim > 0 else None,
                         "adv": float(x["adv"].iat[i])})
    return sig, ctrl


def top_per_day(sig: list, k: int = TOP) -> list:
    by = {}
    for s in sig:
        by.setdefault(s["d"], []).append(s)
    out = []
    for d, l in by.items():
        out += sorted(l, key=lambda s: s["rsi2"])[:k]
    return out


def per_trade(sig: list, px: dict, rule: str, model: str, vix: pd.Series | None, region: dict) -> pd.DataFrame:
    rows = []
    cb, cs = S.COSTS["basis"], S.COSTS["stress"]
    for s in sig:
        P = px[s["t"]]
        i = P.at(s["d"])
        if i is None:
            continue
        hs = cb.hs(s["adv"])
        r = S.trade_of(P, i, rule, s.get("lim"), hs, cb, model)
        if r["res"] not in ("closed", "kein_kauf"):
            continue
        row = {"t": s["t"], "sig": pd.Timestamp(s["d"]), "fill": r["res"] == "closed", "region": region.get(s["t"], "?")}
        if r["res"] == "closed":
            rs = S.trade_of(P, i, rule, s.get("lim"), cs.hs(s["adv"]), cs, model)
            row.update(g=np.clip(r["gross"], -0.9, 3), n=np.clip(r["net"], -0.9, 3),
                       ns=np.clip(rs["net"], -0.9, 3) if rs["res"] == "closed" else np.nan, days=r["days"])
        if vix is not None:
            j = vix.index.searchsorted(row["sig"], side="right") - 1
            row["vix"] = float(vix.iloc[j]) if j >= 0 else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def boot(a: pd.Series, ad: pd.Series, b: pd.Series, bd: pd.Series, n=2000, seed=SEED) -> dict:
    """Einseitiger Block-Bootstrap (Monate, gemeinsam gezogen) für Ø(a) − Ø(b); dazu 95-%-Intervall."""
    A = pd.DataFrame({"m": ad.dt.to_period("M"), "v": a}).groupby("m")["v"].agg(["sum", "count"])
    B = pd.DataFrame({"m": bd.dt.to_period("M"), "v": b}).groupby("m")["v"].agg(["sum", "count"])
    M = A.join(B, lsuffix="_a", rsuffix="_b", how="outer").fillna(0).to_numpy(float)
    if len(M) < 6:
        return {"diff": None}
    diff = M[:, 0].sum() / max(M[:, 1].sum(), 1) - M[:, 2].sum() / max(M[:, 3].sum(), 1)
    rng = np.random.default_rng(seed)
    ds = []
    for _ in range(n):
        s = M[rng.integers(0, len(M), len(M))]
        ds.append(s[:, 0].sum() / max(s[:, 1].sum(), 1) - s[:, 2].sum() / max(s[:, 3].sum(), 1))
    ds = np.array(ds)
    return {"diff": round(float(diff), 5), "p": round(float((np.sum(ds - diff >= diff) + 1) / (n + 1)), 4),
            "ci": [round(float(np.percentile(ds, 2.5)), 5), round(float(np.percentile(ds, 97.5)), 5)]}


def trade_stats(T: pd.DataFrame) -> dict:
    f = T[T["fill"]] if len(T) else T
    if not len(f):
        return {"n": int(len(T)), "filled": 0}
    return {"n": int(len(T)), "filled": int(len(f)), "fill_rate": round(len(f) / len(T), 3), "gross": round(float(f["g"].mean()), 5),
            "net": round(float(f["n"].mean()), 5), "net_stress": round(float(f["ns"].mean()), 5), "win": round(float((f["g"] > 0).mean()), 3),
            "days": round(float(f["days"].mean()), 2)}


def monthly(eq: pd.Series) -> pd.Series:
    return eq.resample("ME").last().pct_change().dropna()


def blend(etf_m: pd.Series, strat_m: pd.Series | None, w: float, start_cap=10_000.0, contrib=200.0) -> dict:
    """Monatlich ausgeglichen, gleiche Einzahlungen (Start + monatlich). Rendite als zeitgewichtete Jahresrendite + Endwert."""
    df = pd.DataFrame({"e": etf_m}).join(pd.DataFrame({"s": strat_m}) if strat_m is not None else None, how="inner") \
        if strat_m is not None else pd.DataFrame({"e": etf_m})
    df = df.dropna()
    if len(df) < 12:
        return {}
    r = (1 - w) * df["e"] + (w * df["s"] if strat_m is not None else 0)
    e = (1 + r).cumprod()
    val = start_cap
    for x in r:
        val = val * (1 + x) + contrib
    return {"cagr": round(float(e.iloc[-1] ** (12 / len(r)) - 1), 4), "dd": round(float((e / e.cummax() - 1).min()), 4),
            "end_value": round(val, 0), "paid": round(start_cap + contrib * len(r), 0), "months": int(len(r))}


def dual_momentum(bench: dict, eur_usd: pd.Series) -> pd.Series | None:
    """S16-B-Näherung: Monatsende, 12-Monats-Rendite SPY/EFA/QQQ, Bester; unter BIL → SHY. Monatsrenditen in EUR."""
    need = ("SPY", "EFA", "QQQ", "BIL", "SHY")
    if not all(k in bench for k in need):
        return None
    m = pd.DataFrame({k: bench[k]["AdjClose"].resample("ME").last() for k in need}).dropna()
    fx = (1 / eur_usd).resample("ME").last().reindex(m.index, method="ffill")          # EUR je USD
    m_eur = m.mul(fx, axis=0)
    ret = m_eur.pct_change()
    mom = m.pct_change(12)
    out = []
    for i in range(12, len(m) - 1):
        row = mom.iloc[i]
        best = row[["SPY", "EFA", "QQQ"]].idxmax()
        pick = best if row[best] > row["BIL"] else "SHY"
        out.append((m.index[i + 1], ret[pick].iloc[i + 1]))
    return pd.Series(dict(out)).sort_index()


def run(a) -> None:
    s0, s1 = (pd.Timestamp(x) for x in SETS[a.set])
    ind, cur, region, eur = load(a)
    print(f"{a.set}: {len(ind)} Aktien", flush=True)
    px = {t: S.make_px(x, cur.get(t, "EUR") if a.set == "main" else "EUR", eur.get(t)) for t, x in ind.items()}
    rng = np.random.default_rng(SEED)
    sig, ctrl = candidates(ind, s0, s1, rng)
    sig_top, ctrl_top = top_per_day(sig), top_per_day(ctrl)
    print(f"Signale {len(sig)} (Top/Tag {len(sig_top)}), Kontrolle {len(ctrl)}", flush=True)
    bench, vix, eur_usd = {}, None, None
    if a.set == "main":
        b = pd.read_parquet(Path(a.data) / "bench_v1.parquet")
        b["date"] = pd.to_datetime(b["date"])
        bench = {t: g.set_index("date").sort_index() for t, g in b.groupby("ticker")}
        vix = bench["^VIX"]["Close"] if "^VIX" in bench else None
        fxr = pd.read_parquet(Path(a.data) / "fx_v1.parquet")
        fxr["date"] = pd.to_datetime(fxr["date"])
        eur_usd = fxr[fxr["ticker"] == "EURUSD=X"].set_index("date")["Close"].sort_index()
    res = {"set": a.set, "n_stocks": len(ind), "n_signals": len(sig), "n_top": len(sig_top), "trade": {}, "edge": {}, "depot": {},
           "years": {}, "caps": {}, "blend": {}, "vix": {}, "region": {}}
    parts = PERIODS if a.set == "main" else {"gesamt": SETS[a.set]}
    T = {}
    for model in S.FILLS:
        T[("W2", model)] = per_trade(sig, px, "W2", model, vix, region)
        T[("CTRL-L", model)] = per_trade(ctrl, px, "W2", model, vix, region)
    T[("A5", "opt")] = per_trade(sig, px, "A5", "opt", vix, region)
    T[("CTRL", "opt")] = per_trade(ctrl, px, "A5", "opt", vix, region)
    for (rule, model), X in T.items():
        for pn, (p0, p1) in {**parts, "alle": SETS[a.set]}.items():
            Y = X[(X["sig"] >= p0) & (X["sig"] <= p1)] if len(X) else X
            res["trade"][f"{rule}|{model}|{pn}"] = trade_stats(Y)
    for model in S.FILLS:
        for pn, (p0, p1) in {**parts, "alle": SETS[a.set]}.items():
            A = T[("W2", model)]; B = T[("CTRL-L", model)]
            A = A[A["fill"] & (A["sig"] >= p0) & (A["sig"] <= p1)]; B = B[B["fill"] & (B["sig"] >= p0) & (B["sig"] <= p1)]
            res["edge"][f"W2-CTRL-L|{model}|{pn}|net"] = boot(A["n"], A["sig"], B["n"], B["sig"])
            res["edge"][f"W2-CTRL-L|{model}|{pn}|gross"] = boot(A["g"], A["sig"], B["g"], B["sig"])
        A = T[("W2", model)]; B = T[("CTRL-L", model)]
        A, B = A[A["fill"]], B[B["fill"]]
        for y in sorted(set(A["sig"].dt.year)):
            ay, by = A[A["sig"].dt.year == y], B[B["sig"].dt.year == y]
            if len(ay) >= 20 and len(by) >= 20:
                res["years"][f"{model}|{y}"] = [round(float(ay["g"].mean() - by["g"].mean()), 5), int(len(ay)), round(float(ay["n"].mean()), 5)]
    A5, C = T[("A5", "opt")], T[("CTRL", "opt")]
    res["edge"]["A5-CTRL|opt|alle|net"] = boot(A5[A5["fill"]]["n"], A5[A5["fill"]]["sig"], C[C["fill"]]["n"], C[C["fill"]]["sig"])
    if vix is not None:
        for model in ("opt", "kons"):
            X = T[("W2", model)]; X = X[X["fill"]]
            for lab, m in (("VIX < 20", X["vix"] < 20), ("VIX 20–30", (X["vix"] >= 20) & (X["vix"] < 30)), ("VIX ≥ 30", X["vix"] >= 30)):
                res["vix"][f"{model}|{lab}"] = trade_stats(X[m].assign(fill=True))
    for model in ("opt", "kons"):
        X = T[("W2", model)]
        for rg in sorted(set(X["region"])):
            res["region"][f"{model}|{rg}"] = trade_stats(X[X["region"] == rg])
    # Depot: Ausführungsmodell × Kosten (10.000 €), Kontrolle, Zeitabschnitte
    cal = pd.DatetimeIndex(sorted({d for P in px.values() for d in P.idx if s0 <= d <= s1 + pd.Timedelta(days=30)}))
    curves = {}
    for model in S.FILLS:
        for cn in ("null", "basis", "free", "g199", "stress"):
            r = S.simulate(sig_top, px, "W2", model, S.COSTS[cn], 10_000.0, calendar=cal)
            curves[f"W2|{model}|{cn}"] = r["equity"]
            res["depot"][f"W2|{model}|{cn}"] = {"counts": r["counts"], "alle": S.stats(r["equity"]),
                                                **{pn: S.stats(r["equity"][(r["equity"].index >= p0) & (r["equity"].index <= p1)])
                                                   for pn, (p0, p1) in parts.items()},
                                                "trades": len(r["trades"]), "streak": _streak(r["trades"]),
                                                "worst12m": _worst12(r["equity"])}
            print("Depot", model, cn, res["depot"][f"W2|{model}|{cn}"]["alle"], flush=True)
        r = S.simulate(ctrl_top, px, "W2", model, S.COSTS["basis"], 10_000.0, calendar=cal)
        res["depot"][f"CTRL-L|{model}|basis"] = {"counts": r["counts"], "alle": S.stats(r["equity"]),
                                                 **{pn: S.stats(r["equity"][(r["equity"].index >= p0) & (r["equity"].index <= p1)])
                                                    for pn, (p0, p1) in parts.items()}}
    for cn in ("basis", "stress"):
        r = S.simulate(sig_top, px, "A5", "opt", S.COSTS[cn], 10_000.0, calendar=cal)
        curves[f"A5|opt|{cn}"] = r["equity"]
        res["depot"][f"A5|opt|{cn}"] = {"counts": r["counts"], "alle": S.stats(r["equity"]),
                                         **{pn: S.stats(r["equity"][(r["equity"].index >= p0) & (r["equity"].index <= p1)])
                                            for pn, (p0, p1) in parts.items()}}
    # Kapitalszenarien (nur Hauptdatensatz – EUR-Bewertung)
    if a.set == "main":
        for cap in CAPS:
            for rule250 in (False, True):
                for model in ("opt", "kons"):
                    for cn in ("basis", "g199"):
                        r = S.simulate(sig_top, px, "W2", model, S.COSTS[cn], float(cap), min_order=250.0 if rule250 else None, calendar=cal)
                        res["caps"][f"{cap}|{'min250' if rule250 else '5plaetze'}|{model}|{cn}"] = {
                            "alle": S.stats(r["equity"]), "fees": round(r["counts"]["gebuehren"], 2), "trades": len(r["trades"]),
                            "zu_teuer": r["counts"]["zu_teuer"], "ruin50": bool((r["equity"] < 0.5 * cap).any())}
            print("Kapital", cap, flush=True)
        # Gesamtportfolio 90/10
        acwi = bench.get("ACWI")
        if acwi is not None and eur_usd is not None:
            fx = (1 / eur_usd).reindex(acwi.index, method="ffill")
            etf_m = monthly((acwi["AdjClose"] * fx).dropna())
            strat = {"W2 kons": monthly(curves["W2|kons|basis"]), "W2 opt": monthly(curves["W2|opt|basis"]),
                     "W2 kons Stress": monthly(curves["W2|kons|stress"]), "A5": monthly(curves["A5|opt|basis"])}
            dm = dual_momentum(bench, eur_usd)
            if dm is not None:
                strat["Dual Momentum (S16-B-Näherung)"] = dm
            if a.b60 and Path(a.b60).exists():
                b60 = pd.read_parquet(a.b60)
                col = next((c for c in b60.columns if c.startswith("5x1|10000|base")), None)
                if col:
                    strat["B60 (5×1 %, Forschungskosten)"] = monthly(b60[col].dropna())
            res["blend"]["100 % Welt-ETF"] = blend(etf_m, None, 0.0)
            res["blend"]["100 % Welt-ETF"]["alone"] = None
            for k, sm in strat.items():
                res["blend"][f"90/10 {k}"] = blend(etf_m, sm, 0.10)
                res["blend"][f"90/10 {k}"]["alone"] = blend(sm, None, 0.0).get("cagr")
                res["blend"][f"90/10 {k}"]["alone_dd"] = blend(sm, None, 0.0).get("dd")
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / f"w2audit_{a.set}.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps({k: v for k, v in res.items() if k in ("edge",)}, default=str)[:3000])


def _streak(trades: list) -> int:
    best = cur = 0
    for t in trades:
        cur = cur + 1 if (t.get("pnl_eur") or 0) < 0 else 0
        best = max(best, cur)
    return best


def _worst12(eq: pd.Series) -> float | None:
    m = eq.resample("ME").last()
    if len(m) < 13:
        return None
    return round(float((m / m.shift(12) - 1).min()), 4)


# ---------------------------------------------------------------- Bericht
def P(x, d=1):
    return "–" if x is None else f"{x * 100:+.{d}f} %"


def report(d: Path) -> None:
    R = {s: json.loads((d / f"w2audit_{s}.json").read_text()) for s in SETS if (d / f"w2audit_{s}.json").exists()}
    L = ["# W2-Audit – korrigierte historische Prüfung (Rohbericht)", "", "Vorab festgelegt: research/reversal/w2audit.py. "
         "Alle Werte aus backend/mrsim.py (Reservierung, kein Nachrücken, ganze Stücke, EUR).", ""]
    for s, r in R.items():
        L += [f"## {s} ({r['n_stocks']} Aktien, {r['n_signals']} Signale, davon Top-10/Tag {r['n_top']})", "",
              "### Je Trade (alle Signale, ohne Depotgrenze)", "",
              "| Regel | Modell | Abschnitt | Signale | ausgeführt | Brutto | Netto basis | Netto stress | im Plus |", "|---|---|---|---|---|---|---|---|---|"]
        for k, v in r["trade"].items():
            rule, model, pn = k.split("|")
            if not v.get("filled"):
                continue
            L.append(f"| {rule} | {model} | {pn} | {v['n']} | {v.get('fill_rate', 0) * 100:.0f} % | {P(v['gross'], 2)} | {P(v['net'], 2)} | "
                     f"{P(v['net_stress'], 2)} | {v['win'] * 100:.0f} % |")
        L += ["", "### Vorsprung gegenüber Zufallskauf mit gleichem Limit (CTRL-L), Block-Bootstrap", "",
              "| Vergleich | Δ je Trade | 95-%-Intervall | p |", "|---|---|---|---|"]
        for k, v in r["edge"].items():
            if v.get("diff") is None:
                continue
            L.append(f"| {k} | {v['diff'] * 100:+.2f} Pkt. | {v['ci'][0] * 100:+.2f} … {v['ci'][1] * 100:+.2f} | {v['p']} |")
        L += ["", "### Depot (10.000 €, 5 Plätze, Reservierung, ganze Stücke)", "",
              "| Depot | Train | Validierung | Holdout | gesamt (Rückgang) | Orders | ausgeführt | nicht ausgeführt | ohne Platz | Gebühren | längste Verlustserie | schlechteste 12 Monate |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for k, v in r["depot"].items():
            c = v["counts"]
            g = lambda p: P((v.get(p) or {}).get("cagr"))
            L.append(f"| {k} | {g('Train')} | {g('Validierung')} | {g('Holdout')} | {P(v['alle'].get('cagr'))} ({P(v['alle'].get('dd'), 0)}) | "
                     f"{c['orders']} | {c['gefuellt']} | {c['nicht_gefuellt']} | {c['kein_platz']} | {c['gebuehren']:.0f} € | "
                     f"{v.get('streak', '–')} | {P(v.get('worst12m'), 0)} |")
        if r.get("caps"):
            L += ["", "### Kapitalszenarien (gesamt 2008–2026, W2)", "", "| Kapital | Platzregel | Modell | Kosten | Rendite p. a. | Rückgang | Gebühren gesamt | Trades | zu teuer | je < 50 % |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
            for k, v in r["caps"].items():
                cap, rule, model, cn = k.split("|")
                L.append(f"| {cap} € | {rule} | {model} | {cn} | {P(v['alle'].get('cagr'))} | {P(v['alle'].get('dd'), 0)} | {v['fees']:.0f} € | "
                         f"{v['trades']} | {v['zu_teuer']} | {'ja' if v['ruin50'] else 'nein'} |")
        if r.get("blend"):
            L += ["", "### Gesamtportfolio (EUR, Start 10.000 € + 200 €/Monat, monatlich ausgeglichen)", "",
                  "| Portfolio | Rendite p. a. | größter Rückgang | Endwert | eingezahlt | Strategie allein p. a. (Rückgang) |", "|---|---|---|---|---|---|"]
            for k, v in r["blend"].items():
                if not v:
                    continue
                L.append(f"| {k} | {P(v.get('cagr'))} | {P(v.get('dd'), 0)} | {v.get('end_value', 0):,.0f} € | {v.get('paid', 0):,.0f} € | "
                         f"{P(v.get('alone'))} ({P(v.get('alone_dd'), 0)}) |")
        if r.get("years"):
            L += ["", "### Vorsprung W2 − CTRL-L je Kalenderjahr (brutto je Trade)", "", "| Jahr | opt | kons | streng |", "|---|---|---|---|"]
            ys = sorted({k.split("|")[1] for k in r["years"]})
            for y in ys:
                L.append(f"| {y} | " + " | ".join(
                    (f"{r['years'][f'{m}|{y}'][0] * 100:+.2f}" if f"{m}|{y}" in r["years"] else "–") for m in S.FILLS) + " |")
        for key, title in (("vix", "Nach Marktangst (VIX am Signaltag)"), ("region", "Nach Region")):
            if r.get(key):
                L += ["", f"### {title}", "", "| Gruppe | ausgeführt | Brutto | Netto basis | Netto stress |", "|---|---|---|---|---|"]
                for k, v in r[key].items():
                    if v.get("filled"):
                        L.append(f"| {k} | {v['filled']} | {P(v['gross'], 2)} | {P(v['net'], 2)} | {P(v['net_stress'], 2)} |")
        L.append("")
    (d / "w2audit_report.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "report"])
    ap.add_argument("--set", choices=list(SETS)); ap.add_argument("--data"); ap.add_argument("--px"); ap.add_argument("--universe")
    ap.add_argument("--out"); ap.add_argument("--dir"); ap.add_argument("--b60")
    a = ap.parse_args(argv)
    if a.cmd == "report":
        report(Path(a.dir)); return 0
    run(a); return 0


if __name__ == "__main__":
    raise SystemExit(main())
