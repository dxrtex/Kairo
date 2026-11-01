"""Mean-Reversion-Meisterschaft: Welche Mean-Reversion-Strategie ist im Depot mit realistischen Kosten die beste?

Vorab festgelegt (01./02.11.2026, vor dem ersten Lauf). Gleiche Bedingungen für alle: korrigierte Engine
(research/strategy_championship/engine.py), Universum USA + Europa (eingefroren 16.10.2026, Grundfilter des Scanners:
≥ 5 Mio. $ Tagesumsatz, Kurs ≥ 1, ≥ 300 Tage Historie), Kauf zur nächsten Eröffnung nach dem Signal, Kosten „normal“
(Scalable PRIME+) und „Stress“ (doppelter Spread, Schlupf, FX), Kapital 10.000 € und 20.000 €, Zeiträume Train 2008–2016,
Validierung 2017–2021, Holdout 2022–2026. Kein Parameter wird nach dem Lauf angepasst.

Familie A – klassische kurzfristige Mean Reversion (Gewicht je Position 1/N, kein Stop, Zeitlimit):
  A1 RSI2-10   RSI(2) < 10 und Schluss über 200-Tage-Linie · Ausstieg Schluss über 5-Tage-Linie · max. 10 Tage
  A2 RSI2-5    wie A1, RSI(2) < 5
  A3 RSI2-OHNE RSI(2) < 10 ohne Trendfilter
  A4 IBS       Schluss im unteren 15 % der Tagesspanne, über 200-Tage-Linie · Ausstieg Schluss über Vortageshoch · max. 10 T.
  A5 3TAGE     drei Verlust-Schlusskurse in Folge, über 200-Tage-Linie · Ausstieg Schluss über 5-Tage-Linie · max. 10 T.
  A6 ZSCORE    (Schluss − 20-Tage-Schnitt)/Schwankung < −2, über 200-Tage-Linie · Ausstieg Schluss über 20-Tage-Schnitt · max. 15 T.
  A7 WOCHE     jeden Freitag die 10 schwächsten Aktien der Woche (≤ −5 %) · 5 Tage halten (Short-Term-Reversal)
  A8 RSI2-LIQ  wie A1, nur Aktien mit ≥ 50 Mio. $ Tagesumsatz (kleinere Spreads)
  A9 RSI2-STOP wie A1, mit Stop 2,5 ATR unter Kauf und Positionsgröße nach Risiko (1 % je Trade)
  Rangfolge bei mehr Signalen als Plätzen: stärkster Ausschlag zuerst (niedrigster RSI/IBS/Z, schwächste Woche).
Familie B – B60 mit anderen Ausstiegen/Aufbau (gleiche Treffer und Einstiege wie B60):
  B0 B60       unverändert (Referenz)
  B1 SMA5      Ausstieg Schluss über 5-Tage-Linie (Stop bleibt), max. 10 Tage
  B2 VORHOCH   Ausstieg erster Schluss über dem Vortageshoch (Stop bleibt), max. 10 Tage
  B3 TAG10     Zeitausstieg Schluss Tag 10 (Stop bleibt)
  B4 GROSS     nur Treffer mit ≥ 50 Mio. $ Tagesumsatz
  B5 PANIK     doppeltes Risiko, wenn der Markt der Region unter seiner 200-Tage-Linie liegt
  B6–B11       Robustheit der Basis: 3 / 7 Kerzen, Spanne 1,0 / 2,0 ATR, Wartezeit 5 / 15 Tage (je ein Parameter)
Familie C – ETF-Mean-Reversion (kleinste Kosten): C1 RSI2-ETF – A1-Regel auf den Index-ETFs des Datensatzes.

Raster: Familie A/C mit 5 und 10 Plätzen (Gewicht 20 % bzw. 10 %; A9: 5 × 1 % bzw. 10 × 0,5 % Risiko), Familie B mit 5 × 1 % und
20 × 0,25 % Risiko (wie B60).

Entscheidungsregel: Ein Herausforderer „schlägt B60“, wenn er mit Stress-Kosten in Validierung UND Holdout bei 10.000 € UND
20.000 € (jeweils bestes eigenes Raster gegen bestes B60-Raster, Raster vorab je Familie festgelegt = das mit der höheren
Train-Rendite) eine höhere Jahresrendite hat, der größte Rückgang nicht mehr als 5 Prozentpunkte schlechter ist und der
einseitige Block-Bootstrap der Monatsrenditen (Validierung + Holdout, Holm über alle Herausforderer) p < 0,10 ergibt.
Zusätzlich wird jede Variante gegen den Welt-ETF (ACWI) gezeigt. Gewinner = Schattentest, keine Regeländerung.

WELLE 2 (vorab festgelegt 02.11.2026 nach Welle 1, vor dem eigenen Lauf – klar getrennt berichtet):
Welle 1 zeigte: Schnelle Mean Reversion hat mit normalen Kosten einen großen Vorteil, mit Stress-Kosten Totalverlust.
Darum je Variante ein Kostenraster (Spread × 1 / 1,5 / 2, Schlupf 0 / 0,05 %, FX-Aufschlag 0 / 0,05 / 0,1 % je Seite;
Gebühr 0,99 € unter 250 €), die Kostenschwelle (höchste geprüfte Kosten, bei denen Validierung UND Holdout den Welt-ETF
schlagen) und der Brutto-Ertrag je Trade (ohne Kosten). Neue liquide Varianten (≥ 100 Mio. $ Tagesumsatz):
  A5L 3 Verlusttage + Trend, liquide · A7L Wochen-Verlierer, liquide · A1L RSI(2) < 10 + Trend, liquide · A6L Z-Score, liquide

    python -m research.reversal.mrc --data v1 --signals sig.parquet --sec sec --variant A1 --out out
    python -m research.reversal.mrc costs --data v1 --signals sig.parquet --sec sec --variant A5 --out out
    python -m research.reversal.mrc report --dir DIR
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from backend.indicators import atr as _atr, rsi as _rsi
from research.strategy_championship import s01
from research.strategy_championship.data import PERIODS
from research.strategy_championship.engine import Order, run
from research.ultimate import round1 as R

VARIANTS = ("A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "B0", "B1", "B2", "B3", "B4", "B5",
            "B6", "B7", "B8", "B9", "B10", "B11", "C1", "A5L", "A7L", "A1L", "A6L")
NAMES = {"A1": "RSI(2) < 10 + Trend", "A2": "RSI(2) < 5 + Trend", "A3": "RSI(2) < 10 ohne Trend", "A4": "IBS < 0,15 + Trend",
         "A5": "3 Verlusttage + Trend", "A6": "Z-Score < −2 + Trend", "A7": "Wochen-Verlierer (Reversal)", "A8": "RSI(2) nur liquide",
         "A9": "RSI(2) mit Stop", "B0": "B60 (Referenz)", "B1": "B60, Ausstieg 5-Tage-Linie", "B2": "B60, Ausstieg Vortageshoch",
         "B3": "B60, Ausstieg Tag 10", "B4": "B60 nur liquide", "B5": "B60, doppeltes Risiko im Ausverkauf",
         "B6": "B60 Basis 3 Kerzen", "B7": "B60 Basis 7 Kerzen", "B8": "B60 Spanne 1,0 ATR", "B9": "B60 Spanne 2,0 ATR",
         "B10": "B60 Wartezeit 5", "B11": "B60 Wartezeit 15", "C1": "RSI(2) auf Index-ETFs",
         "A5L": "3 Verlusttage + Trend, liquide", "A7L": "Wochen-Verlierer, liquide", "A1L": "RSI(2) + Trend, liquide", "A6L": "Z-Score, liquide"}
WAVE2 = ("A5L", "A7L", "A1L", "A6L")
LIQ2 = 1e8
CASH = (10000, 20000)
AB = ("Train", "Validierung", "Holdout")
REGIONS = ("us", "eu", "europe")
PATCH = {"B6": ("CK", 3), "B7": ("CK", 7), "B8": ("CM", 1.0), "B9": ("CM", 2.0), "B10": ("WAIT", 5), "B11": ("WAIT", 15)}


# ------------------------------------------------------------------ Indikatoren (nur Daten bis zum Signaltag)
def ind(t: str) -> dict:
    c = R._G.setdefault("mrc_ind", {})
    if t in c:
        return c[t]
    a = R._G["adj"][t]
    C, H, L = a["Close"], a["High"], a["Low"]
    rng = (H - L).replace(0, np.nan)
    sma20, sd20 = C.rolling(20).mean(), C.rolling(20).std()
    cur = R._G["cur"].get(t, "USD")
    out = {"C": C.to_numpy(float), "sma200": C.rolling(200).mean().to_numpy(float), "sma5": C.rolling(5).mean().to_numpy(float),
           "sma20": sma20.to_numpy(float), "z": ((C - sma20) / sd20).to_numpy(float), "rsi2": _rsi(C, 2).to_numpy(float),
           "ibs": ((C - L) / rng).to_numpy(float), "down3": ((C < C.shift(1)) & (C.shift(1) < C.shift(2)) & (C.shift(2) < C.shift(3))).to_numpy(),
           "ret5": (C / C.shift(5) - 1).to_numpy(float), "abovehi": (C > H.shift(1)).to_numpy(),
           "atr": _atr(a, 14).to_numpy(float), "ok": s01.eligible(a, cur),
           "adv": (a["Volume"].fillna(0) * C).rolling(20, min_periods=1).mean().to_numpy(float) * s01.FX_USD.get(cur, 1.0),
           "idx": a.index, "f": a["f"].to_numpy(float)}
    c[t] = out
    return out


def universe(us_eu_only=True) -> list[str]:
    reg = R._G.get("region", {})
    return [t for t in R._G["adj"] if not us_eu_only or str(reg.get(t, "")).lower() in REGIONS]


def exit_dates(x: dict, kind: str) -> pd.DatetimeIndex:
    C = x["C"]
    m = {"sma5": C > x["sma5"], "sma20": C > x["sma20"], "vorhoch": x["abovehi"]}[kind]
    return x["idx"][np.nan_to_num(m.astype(float)) > 0]


# ------------------------------------------------------------------ Familie A / C
def family_a(v: str, slots: int, tickers=None) -> tuple[list[Order], dict]:
    orders, exits = [], {}
    w = 1.0 / slots
    start = pd.Timestamp(PERIODS["train"][0])
    for t in tickers or universe():
        x = ind(t)
        C, ok = x["C"], x["ok"]
        trend = C > x["sma200"]
        base = v[:-1] if v in WAVE2 else v
        if base in ("A1", "A8", "A9", "C1"):
            sig, prio, ex, md = (x["rsi2"] < 10) & trend, -x["rsi2"], "sma5", 10
        elif base == "A2":
            sig, prio, ex, md = (x["rsi2"] < 5) & trend, -x["rsi2"], "sma5", 10
        elif base == "A3":
            sig, prio, ex, md = (x["rsi2"] < 10), -x["rsi2"], "sma5", 10
        elif base == "A4":
            sig, prio, ex, md = (x["ibs"] < 0.15) & trend, -x["ibs"], "vorhoch", 10
        elif base == "A5":
            sig, prio, ex, md = x["down3"] & trend, -x["rsi2"], "sma5", 10
        elif base == "A6":
            sig, prio, ex, md = (x["z"] < -2) & trend, -x["z"], "sma20", 15
        else:
            raise ValueError(v)
        if v == "A8":
            sig = sig & (x["adv"] >= 5e7)
        if v in WAVE2:
            sig = sig & (x["adv"] >= LIQ2)
        sig = np.nan_to_num(sig.astype(float)) > 0
        if v != "C1":
            sig &= ok
        idx = x["idx"]
        ks = np.where(sig)[0]
        ks = ks[(idx[ks] >= start) & (ks < len(idx) - 1)]
        if not len(ks):
            continue
        exits[t] = exit_dates(x, ex)
        for k in ks:
            p = float(prio[k]) if np.isfinite(prio[k]) else -999.0
            if v == "A9":
                a = x["atr"][k] / x["f"][k]
                cr = x["C"][k] / x["f"][k]
                if not (a > 0):
                    continue
                orders.append(Order(idx[k], t, stop_from_fill=2.5 * a, stop=cr - 2.5 * a, risk_frac=0.01 if slots == 5 else 0.005,
                                    prio=p, tag=f"{v}|{t}|{idx[k].date()}", max_days=md, group=f"{t}|{idx[k].date()}"))
            else:
                orders.append(Order(idx[k], t, weight=w, prio=p, tag=f"{v}|{t}|{idx[k].date()}", max_days=md, group=f"{t}|{idx[k].date()}"))
    return orders, exits


def family_week(slots: int, min_adv: float = 0.0) -> tuple[list[Order], dict]:
    """A7: an jedem letzten Handelstag der Woche die schwächsten 10 der Woche (≤ −5 %), 5 Tage halten."""
    start = pd.Timestamp(PERIODS["train"][0])
    rows = []
    for t in universe():
        x = ind(t)
        idx = x["idx"]
        last_of_week = np.r_[idx[1:].isocalendar().week.to_numpy() != idx[:-1].isocalendar().week.to_numpy(), False]
        m = last_of_week & x["ok"] & (np.nan_to_num(x["ret5"], nan=0) <= -0.05) & (idx >= start) & (x["adv"] >= min_adv)
        for k in np.where(m)[0]:
            if k < len(idx) - 1:
                rows.append((idx[k], t, float(x["ret5"][k])))
    df = pd.DataFrame(rows, columns=["d", "t", "r"])
    orders = []
    for d, g in df.groupby("d"):
        for r in g.nsmallest(10, "r").itertuples(index=False):
            orders.append(Order(d, r.t, weight=1.0 / slots, prio=-r.r, tag=f"A7|{r.t}|{d.date()}", max_days=5, group=f"{r.t}|{d.date()}"))
    return orders, {}


# ------------------------------------------------------------------ Familie B
def family_b(v: str, sig, meta, layout: str) -> tuple[list[Order], dict]:
    mx, rf = R.LAYOUTS[layout]
    patch = PATCH.get(v)
    old = getattr(s01, patch[0]) if patch else None
    if patch:
        setattr(s01, patch[0], patch[1])
    try:
        orders = R.build(sig, meta, "E0", rf)
    finally:
        if patch:
            setattr(s01, patch[0], old)
    exits = {}
    if v in ("B1", "B2", "B3"):
        for o in orders:
            o.exit_rule, o.max_days = None, 10
            if v != "B3" and o.ticker not in exits:
                exits[o.ticker] = exit_dates(ind(o.ticker), "sma5" if v == "B1" else "vorhoch")
    elif v == "B4":
        keep = []
        for o in orders:
            x = ind(o.ticker)
            k = int(x["idx"].searchsorted(o.decision_date))
            if k < len(x["adv"]) and x["adv"][k] >= 5e7:
                keep.append(o)
        orders = keep
    elif v == "B5":
        px = market_proxy()
        for o in orders:
            s = px.get(str(R._G["region"].get(o.ticker, "")).lower())
            if s is not None:
                i = int(s.index.searchsorted(o.decision_date, side="right") - 1)
                if i >= 199 and s.iloc[i] < s.iloc[i - 199:i + 1].mean():
                    o.risk_frac = 2 * o.risk_frac
    return orders, exits


def market_proxy() -> dict:
    if "mrc_mkt" not in R._G:
        from research.reversal.learn import proxies
        R._G["mrc_mkt"] = proxies(R._G["adj"], {t: str(r).lower() for t, r in R._G["region"].items()})
    return R._G["mrc_mkt"]


def add_etfs(data: str) -> list[str]:
    from research.strategy_championship.data import load
    _p, _c, _f, bench, _r = load(data, "full")
    out = []
    for t, df in bench.items():
        if t in ("SHY", "BIL", "^VIX", "TLT", "IEF", "AGG", "GLD") or not {"Open", "High", "Low", "Close", "AdjClose"} <= set(df.columns):
            continue
        df = df.dropna(subset=["Open", "High", "Low", "Close", "AdjClose"])
        if len(df) < 400:
            continue
        df = df.assign(Volume=df.get("Volume", pd.Series(1e9, index=df.index)))
        R._G["raw"][t] = s01.with_ema(df)
        from research.strategy_championship.data import adjusted
        R._G["adj"][t] = adjusted(s01.clean(df))
        R._G["cur"][t] = "USD"
        R._G["region"][t] = "etf"
        R._G["spread"][t] = 0.0002
        out.append(t)
    return out


# ------------------------------------------------------------------ Depot
def build_orders(v: str, lay: str, sig, meta, etfs=None):
    if v.startswith("B"):
        o, e = family_b(v, sig, meta, lay)
        return o, e, R.LAYOUTS[lay][0]
    if v in ("A7", "A7L"):
        o, e = family_week(int(lay), LIQ2 if v == "A7L" else 0.0)
        return o, e, int(lay)
    o, e = family_a(v, int(lay), etfs)
    return o, e, int(lay)


def run_costs(v: str, sig, meta, data: str) -> dict:
    """Welle 2: Kostenraster je Variante (bestes Raster nach Train mit normalen Kosten wird aus beiden ermittelt)."""
    from research.strategy_championship.engine import Costs
    sp = R._G["spread"]
    etfs = add_etfs(data) if v == "C1" else None
    out = {}
    for lay in layouts_for(v):
        orders, exits, mx = build_orders(v, lay, sig, meta, etfs)
        orders = top_per_day(orders, 4 * mx)
        zero = run(R._G["raw"], R._G["cur"], R._G["fx"], orders, 10000, Costs(fee_eur=0.0, spread=0.0), mx, calendar=R._G["cal"], exit_when=exits, min_fill=0.5)
        t = zero.trades
        gross = float((t["pnl_eur"] / t["cost_eur"]).mean()) if len(t) else None
        out[f"{lay}|gross"] = {"ret_trade": gross, "trades": int(len(t)), "days": float(t["days"].mean()) if len(t) else None}
        for m in (1.0, 1.5, 2.0):
            for sl in (0.0, 0.0005):
                for fx in (0.0, 0.0005, 0.001):
                    c = Costs(fee_eur=0.99, spread=0.001 * m, slippage=sl, fx_fee=fx, fee_free_from=250.0, spread_by_ticker={k: m * v_ for k, v_ in sp.items()})
                    r = run(R._G["raw"], R._G["cur"], R._G["fx"], orders, 10000, c, mx, calendar=R._G["cal"], exit_when=exits, min_fill=0.5)
                    seg = R.segments(r.equity, r.trades, r.invested)
                    side = float(np.mean([c.side(tk, R._G["cur"].get(tk, "USD")) for tk in r.trades["ticker"]])) if len(r.trades) else None
                    out[f"{lay}|{m}|{sl}|{fx}"] = {"side": side, **{ab: {k: (seg.get(ab) or {}).get(k) for k in ("cagr", "max_dd")} for ab in AB + ("gesamt",)}}
        print("Kosten", v, lay, flush=True)
    return out


def layouts_for(v: str) -> tuple:
    return ("5x1", "20x025") if v.startswith("B") else ("5", "10")


def run_variant(v: str, sig, meta, data: str) -> dict:
    out, curves = {}, {}
    etfs = add_etfs(data) if v == "C1" else None
    for lay in layouts_for(v):
        orders, exits, mx = build_orders(v, lay, sig, meta, etfs)
        orders = top_per_day(orders, 4 * mx)
        print(f"{v} {lay}: {len(orders)} Orders", flush=True)
        for cash in CASH:
            for kind in ("base", "stress"):
                r = run(R._G["raw"], R._G["cur"], R._G["fx"], orders, cash, R.costs(kind), mx, calendar=R._G["cal"],
                        exit_when=exits, min_fill=0.5)
                seg = R.segments(r.equity, r.trades, r.invested)
                key = f"{lay}|{cash}|{kind}"
                out[key] = {ab: {k: (seg.get(ab) or {}).get(k) for k in ("cagr", "max_dd", "sharpe", "trades", "win", "R_mean")}
                            for ab in AB + ("gesamt",)}
                out[key]["checks"] = r.checks
                curves[key] = r.equity
    return out, pd.DataFrame(curves)


def top_per_day(orders: list[Order], k: int) -> list[Order]:
    """Je Entscheidungstag nur die k Orders mit höchstem Vorrang – mehr kann ein Depot mit N Plätzen nie kaufen
    (Engine nimmt ohnehin die höchsten zuerst). Hält die Laufzeit bei häufigen Signalen (RSI2) beherrschbar."""
    by = {}
    for o in orders:
        by.setdefault(o.decision_date, []).append(o)
    out = []
    for d, l in by.items():
        out += sorted(l, key=lambda o: -o.prio)[:k] if len(l) > k else l
    return out


# ------------------------------------------------------------------ Bericht
def monthly(e: pd.Series) -> pd.Series:
    return e.resample("ME").last().pct_change().dropna()


def boot_p(a: pd.Series, b: pd.Series, n=4000, block=6, seed=11) -> float:
    d = (a - b).dropna().to_numpy()
    if len(d) < 24:
        return 1.0
    rng, m = np.random.default_rng(seed), len(d)
    hits = 0
    for _ in range(n):
        st = rng.integers(0, m, size=m // block + 1)
        s = np.concatenate([d[(i + np.arange(block)) % m] for i in st])[:m]
        hits += (s.mean() - d.mean()) >= d.mean()            # zentrierter Bootstrap, einseitig > 0
    return hits / n


def report(d: Path) -> str:
    res, cur = {}, {}
    for v in VARIANTS:
        f = d / f"mrc_{v}.json"
        if f.exists():
            res[v] = json.loads(f.read_text())
            p = d / f"mrc_curve_{v}.parquet"
            if p.exists():
                cur[v] = pd.read_parquet(p)
    acwi = None
    if (d / "acwi.parquet").exists():
        acwi = pd.read_parquet(d / "acwi.parquet")["AdjClose"]
    def best_lay(v):                                         # Raster vorab: höhere Train-Rendite (10.000 €, Stress)
        lays = layouts_for(v)
        return max(lays, key=lambda l: (res[v].get(f"{l}|10000|stress", {}).get("Train", {}).get("cagr") or -9))
    seg = lambda v, cash, ab, kind="stress", k="cagr": (res[v].get(f"{best_lay(v)}|{cash}|{kind}", {}).get(ab) or {}).get(k)
    P = lambda x: "–" if x is None else f"{x:+.1%}"
    L = ["# Mean-Reversion-Meisterschaft – Ergebnis\n", __doc__.split("\n", 1)[1].split("    python")[0].strip(), ""]
    if acwi is not None:
        def cg(a, b):
            s = acwi[(acwi.index >= a) & (acwi.index <= b)]
            y = (s.index[-1] - s.index[0]).days / 365.25
            return (s.iloc[-1] / s.iloc[0]) ** (1 / y) - 1
        L.append("**Welt-ETF (ACWI, ohne Kosten):** " + " · ".join(f"{ab} {P(cg(*PERIODS[k][:2]))}" for ab, k in zip(AB, ("train", "validation", "holdout"))) + "\n")
    L.append("| Variante | Raster | Train | Validierung | Holdout | gesamt (größter Rückgang) | Sharpe gesamt | Trades | normal: Val / Hold |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for v in res:
        L.append(f"| {v} {NAMES[v]} | {best_lay(v)} | {P(seg(v, 10000, 'Train'))} | {P(seg(v, 10000, 'Validierung'))} | {P(seg(v, 10000, 'Holdout'))} | "
                 f"{P(seg(v, 10000, 'gesamt'))} ({P(seg(v, 10000, 'gesamt', k='max_dd'))}) | {seg(v, 10000, 'gesamt', k='sharpe') or 0:.2f} | "
                 f"{seg(v, 10000, 'gesamt', k='trades') or 0} | {P(seg(v, 10000, 'Validierung', 'base'))} / {P(seg(v, 10000, 'Holdout', 'base'))} |")
    L.append("\n*Werte: 10.000 €, Stress-Kosten, Jahresrendite (CAGR). Raster je Variante vorab nach Train gewählt.*\n")
    # Entscheidung
    ps, beat = {}, {}
    for v in res:
        if v == "B0" or "B0" not in res:
            continue
        ok = True
        for cash in CASH:
            for ab in ("Validierung", "Holdout"):
                a, b = seg(v, cash, ab), seg("B0", cash, ab)
                da, db = seg(v, cash, ab, k="max_dd"), seg("B0", cash, ab, k="max_dd")
                if a is None or b is None or a <= b or (da is not None and db is not None and da < db - 0.05):
                    ok = False
        beat[v] = ok
        try:
            ca, cb = cur[v][f"{best_lay(v)}|10000|stress"], cur["B0"][f"{best_lay('B0')}|10000|stress"]
            va = pd.Timestamp(PERIODS["validation"][0])
            ps[v] = boot_p(monthly(ca[ca.index >= va]), monthly(cb[cb.index >= va]))
        except Exception:
            ps[v] = 1.0
    order = sorted(ps, key=ps.get)
    holm, m = {}, len(order)
    prev = 0.0
    for i, v in enumerate(order):
        prev = max(prev, min(1.0, ps[v] * (m - i)))
        holm[v] = prev
    L.append("## Entscheidung (gegen B60, Stress-Kosten, 10.000 € und 20.000 €, Validierung und Holdout)\n")
    L.append("| Variante | schlägt B60 in allen 4 Prüfungen | Bootstrap p | Holm p | Ergebnis |\n|---|---|---|---|---|")
    winners = []
    for v in order:
        w = beat.get(v) and holm[v] < 0.10
        if w:
            winners.append(v)
        L.append(f"| {v} {NAMES[v]} | {'ja' if beat.get(v) else 'nein'} | {ps[v]:.3f} | {holm[v]:.3f} | {'**bestanden**' if w else 'nicht bestanden'} |")
    L.append("\n## Fazit\n")
    if winners:
        best = max(winners, key=lambda v: (seg(v, 10000, "Validierung") or 0) + (seg(v, 10000, "Holdout") or 0))
        L.append(f"**Gewinner: {best} – {NAMES[best]}.** Schlägt B60 in Validierung und Holdout bei beiden Kapitalgrößen mit Stress-Kosten, "
                 f"statistisch abgesichert (Holm p {holm[best]:.3f}). Nächster Schritt: Schattentest – B60 bleibt bis zur Freigabe Champion.")
    else:
        L.append("**Kein Herausforderer schlägt B60 durchgängig und statistisch abgesichert.** Die Tabelle zeigt trotzdem, welche Variante "
                 "in welchem Zeitraum vorn lag.")
    L += costs_section(d, acwi)
    txt = "\n".join(L) + "\n"
    (d / "mrc_report.md").write_text(txt, encoding="utf-8")
    return txt


def costs_section(d: Path, acwi) -> list[str]:
    """Welle 2: Brutto-Ertrag je Trade und Kostenschwelle gegen den Welt-ETF."""
    files = sorted(d.glob("mrc_costs_*.json"))
    if not files:
        return []
    P = lambda x: "–" if x is None else f"{x:+.1%}"
    bench = {}
    if acwi is not None:
        for ab, k in zip(AB, ("train", "validation", "holdout")):
            a, b = PERIODS[k][:2]
            s = acwi[(acwi.index >= a) & (acwi.index <= b)]
            y = (s.index[-1] - s.index[0]).days / 365.25
            bench[ab] = (s.iloc[-1] / s.iloc[0]) ** (1 / y) - 1
    L = ["\n## Welle 2 – Kosten entscheiden: Brutto-Ertrag und Kostenschwelle (10.000 €)\n",
         "Kostenschwelle = höchste geprüfte Kosten je Seite (Spread-Hälfte + Schlupf + FX), bei denen die Variante in Validierung UND "
         "Holdout den Welt-ETF schlägt. Je höher, desto robuster gegen echte Handelskosten.\n",
         "| Variante | Raster | Brutto je Trade | Trades | Ø Tage | normal Val / Hold | Kostenschwelle je Seite | dort Val / Hold | ×2 Spread+0,05 % Schlupf+0,1 % FX: Val / Hold |",
         "|---|---|---|---|---|---|---|---|---|"]
    for f in files:
        v = f.stem.replace("mrc_costs_", "")
        r = json.loads(f.read_text())
        lays = sorted({k.split("|")[0] for k in r})
        lay = max(lays, key=lambda l: ((r.get(f"{l}|1.0|0.0|0.0") or {}).get("Train") or {}).get("cagr") or -9)
        g = r.get(f"{lay}|gross") or {}
        grid = [(k, x) for k, x in r.items() if k.startswith(lay + "|") and not k.endswith("gross")]
        ok = [(x["side"], k, x) for k, x in grid if x.get("side") is not None and bench and all(
            (x.get(ab) or {}).get("cagr") is not None and x[ab]["cagr"] > bench[ab] for ab in ("Validierung", "Holdout"))]
        best = max(ok) if ok else None
        n = r.get(f"{lay}|1.0|0.0|0.0") or {}
        w = r.get(f"{lay}|2.0|0.0005|0.001") or {}
        L.append(f"| {v} {NAMES.get(v, v)} | {lay} | {P(g.get('ret_trade'))} | {g.get('trades')} | {g.get('days') or 0:.1f} | "
                 f"{P((n.get('Validierung') or {}).get('cagr'))} / {P((n.get('Holdout') or {}).get('cagr'))} | "
                 + (f"{best[0]:.2%} | {P(best[2]['Validierung']['cagr'])} / {P(best[2]['Holdout']['cagr'])}" if best else "schlägt ETF bei keinen geprüften Kosten | –")
                 + f" | {P((w.get('Validierung') or {}).get('cagr'))} / {P((w.get('Holdout') or {}).get('cagr'))} |")
    if bench:
        L.append(f"\n*Welt-ETF zum Vergleich: Validierung {P(bench['Validierung'])}, Holdout {P(bench['Holdout'])}.*")
    return L


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="run", choices=["run", "report", "costs"])
    ap.add_argument("--data"); ap.add_argument("--signals"); ap.add_argument("--sec"); ap.add_argument("--variant", choices=VARIANTS)
    ap.add_argument("--out", default="mrc_out"); ap.add_argument("--dir")
    a = ap.parse_args(argv)
    if a.cmd == "report":
        print(report(Path(a.dir))); return 0
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    sig, meta = R.setup(a.data, a.signals, a.sec)
    if a.cmd == "costs":
        res = run_costs(a.variant, sig, meta, a.data)
        (out / f"mrc_costs_{a.variant}.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
        print(json.dumps({k: v for k, v in res.items() if k.endswith("gross")}, indent=1, default=str))
        return 0
    res, curves = run_variant(a.variant, sig, meta, a.data)
    (out / f"mrc_{a.variant}.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    curves.to_parquet(out / f"mrc_curve_{a.variant}.parquet")
    if a.variant == "B0":
        from research.strategy_championship.data import load
        bench = load(a.data, "full")[3]
        if "ACWI" in bench:
            bench["ACWI"][["AdjClose"]].to_parquet(out / "acwi.parquet")
    print(json.dumps({k: v.get("gesamt") for k, v in res.items()}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
