"""Kairo Ultimate – Wettbewerb B: beste Strategie für den Trading-Topf (Plan §4–§7, eingefroren).

Alle Teilnehmer mit ihren schon festgelegten Regeln, in derselben Engine, 2008–2026, Kapital 1.000–20.000 €, Kosten PRIME+
Basis und Stress, deutsche Steuer vereinfacht:
  ACWI     Welt-ETF halten (Vergleich)
  S13-ETF  ACWI nur, wenn Monatsschluss (EUR) > SMA 10 Monate, sonst Kasse
  S16-B    Dual Momentum SPY/EFA/QQQ (12 Monate) gegen BIL, sonst SHY
  S07-B    Momentum 6-1 / Vol 6 M., Top 10, monatlich (Einzelaktien)
  SP1F     SPY, solange SPY-Schluss > SMA 200 Tage, sonst BIL
  SP2F     wie SP1F mit 2-fach gehebeltem S&P 500 (täglich 2 × Rendite − Finanzierung T-Bill + 0,5 % − 0,6 % TER)
  B60 und bester Rücksetzer aus Wettbewerb A: Depotkurven aus Runde 1 (--r1)
  K1       50 % S16-B + 50 % Rücksetzer (20 × 0,25 %), jährlich neu gewichtet
Zufall: S16-B mit zufälligem ETF (100 Seeds), S07-B mit 10 zufälligen zulässigen Titeln (40 Seeds).
Risikostufen: Anteil investiert w ≤ 1 (Rest Geldmarkt, T-Bill) so, dass der größte Rückgang im Train das Ziel
10/20/30 % nicht überschreitet; danach unverändert. Hebel nur für Strategien, die ungehebelt bestehen.

    python -m research.ultimate.compete run  --data v1 --out out [--r1 DIR] [--best E0]
    python -m research.ultimate.compete pre  --out out            (ETF-Strategien 2003–2007, frisch geladen)
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from research.strategy_championship import wave2
from research.strategy_championship.data import UNIVERSE, load
from research.strategy_championship.engine import Costs, Order, run
from research.strategy_championship.v_run import s13_orders
from research.strategy_championship.wave1 import Panel, spreads

from .round1 import AB, CASH, metrics, segments

RATE = 0.26375                     # Abgeltungsteuer + Soli, ohne Kirchensteuer, ohne Sparerpauschbetrag (vorsichtig)
TF_EQUITY = 0.30                   # Teilfreistellung Aktien-ETF
EQUITY_ETF = {"ACWI", "SPY", "EFA", "QQQ", "SPY2X"}
TARGETS = (0.10, 0.20, 0.30)
COSTS = {"base": Costs(fee_eur=0.99, spread=0.001, fee_free_from=250.0),
         "stress": Costs(fee_eur=1.99, spread=0.002, slippage=0.0005, fx_fee=0.001, fee_free_from=250.0)}


# ------------------------------------------------------------------ ETF-Bausteine
def tbill_daily(bench: dict) -> pd.Series:
    irx = bench["^IRX"]["Close"].astype(float).clip(lower=0) / 100
    return irx / 252


def synth(level: pd.Series) -> pd.DataFrame:
    level = level.dropna()
    return pd.DataFrame({"Open": level, "High": level, "Low": level, "Close": level, "AdjClose": level})


def spy2x(bench: dict) -> pd.DataFrame:
    a = bench["SPY"]["AdjClose"].astype(float)
    r = a.pct_change()
    fin = (tbill_daily(bench).reindex(a.index).ffill() + 0.005 / 252)
    r2 = 2 * r - fin - 0.006 / 252
    return synth(100 * (1 + r2.fillna(0)).cumprod())


def bil_proxy(bench: dict, idx) -> pd.DataFrame:
    return synth(100 * (1 + tbill_daily(bench).reindex(idx).ffill().fillna(0)).cumprod())


def sma_switch(sig: pd.Series, risk: str, safe: str, start, end, n: int = 200):
    """Schluss > SMA n → risk, sonst safe; Wechsel zur nächsten Eröffnung."""
    s = sig.dropna()
    on = (s > s.rolling(n).mean()).where(s.rolling(n).count() >= n)
    orders, ex, state = [], {}, None
    for d, v in on.items():
        if d < start or d > end or pd.isna(v):
            continue
        want = risk if v else safe
        if want != state:
            if state is not None:
                ex.setdefault(state, []).append(d)
            orders.append(Order(d, want, weight=0.99, tag=want))
            state = want
    return orders, ex


def etf_strategy(sid: str, bench, fx, start, end, cal, rng=None):
    if sid == "ACWI":
        return [Order(cal[0], "ACWI", weight=0.995, tag="ACWI")], {}, 1
    if sid == "S13-ETF":
        o, ex = s13_orders(bench["ACWI"], fx["USD"], start, end)
        return o, ex, 1
    if sid == "S16-B":
        o, ex, _ = wave2.etf_rotation(bench, "S16-B", start, end, rng=rng)
        return o, ex, 3
    if sid == "SP1F":
        o, ex = sma_switch(bench["SPY"]["AdjClose"], "SPY", "BIL", start, end)
        return o, ex, 1
    if sid == "SP2F":
        o, ex = sma_switch(bench["SPY"]["AdjClose"], "SPY2X", "BIL", start, end)
        return o, ex, 1
    raise KeyError(sid)


# ------------------------------------------------------------------ Steuer
def taxable_from_run(r, stocks: bool) -> dict:
    out = {}
    t = r.trades
    if len(t):
        for row in t.itertuples(index=False):
            y = pd.Timestamp(row.exit_date).year
            d = out.setdefault(y, {"aktien": 0.0, "allgemein": 0.0})
            if stocks:
                d["aktien"] += row.pnl_eur
            else:
                d["allgemein"] += row.pnl_eur * ((1 - TF_EQUITY) if row.ticker in EQUITY_ETF else 1.0)
    led = r.ledger
    if len(led):
        for row in led[led["kind"] == "DIV"].itertuples(index=False):
            y = pd.Timestamp(row.date).year
            f = (1 - TF_EQUITY) if (not stocks and row.ticker in EQUITY_ETF) else 1.0
            out.setdefault(y, {"aktien": 0.0, "allgemein": 0.0})["allgemein"] += row.cash_flow_eur * f
    return out


def after_tax(e: pd.Series, tax: dict) -> pd.Series:
    """Steuer je Jahr (Aktien-Verluste nur gegen Aktien-Gewinne, allgemeine Verluste auch gegen Aktien-Gewinne, Vortrag)
    am letzten Handelstag des Jahres als Anteil des Depotwerts abgezogen. Vorabpauschale nicht modelliert."""
    e = e.dropna()
    ca, cg, factor, out = 0.0, 0.0, 1.0, []
    years = e.index.year
    last = {y: e.index[years == y][-1] for y in np.unique(years)}
    for d, v in e.items():
        out.append(v * factor)
        if d == last[d.year]:
            x = tax.get(d.year, tax.get(str(d.year), {"aktien": 0.0, "allgemein": 0.0}))
            a, g = x["aktien"] + ca, x["allgemein"] + cg
            if g < 0 and a > 0:
                a, g = a + g, 0.0
                if a < 0:
                    g, a = a, 0.0
            ca, cg = min(a, 0.0), min(g, 0.0)
            t = RATE * (max(a, 0.0) + max(g, 0.0))
            if v > 0 and t > 0:
                factor *= max(0.0, 1 - t / v)
                out[-1] = v * factor
    return pd.Series(out, index=e.index)


# ------------------------------------------------------------------ Mischungen
def with_cash(e: pd.Series, w: float, cash_r: pd.Series) -> pd.Series:
    r = e.pct_change().fillna(0)
    c = cash_r.reindex(r.index).ffill().fillna(0)
    return (1 + w * r + (1 - w) * c).cumprod() * e.iloc[0]


def mix2(a: pd.Series, b: pd.Series, wa: float, cost: float) -> pd.Series:
    j = pd.concat([a, b], axis=1).ffill().dropna()
    r = j.pct_change().fillna(0).to_numpy()
    w0 = np.array([wa, 1 - wa]); h, out, year = w0.copy(), [], None
    for d, rr in zip(j.index, r):
        if year is not None and d.year != year:
            eq = h.sum(); cur = h / eq
            eq *= 1 - cost * np.abs(cur - w0).sum(); h = w0 * eq
        year = d.year
        h = h * (1 + rr)
        out.append(h.sum())
    return pd.Series(out, index=j.index) * a.dropna().iloc[0]


def boot_p(ra: pd.Series, rb: pd.Series, n: int = 3000, block: int = 63, seed: int = 11) -> float:
    """Einseitig P(Ø log-Rendite a − b ≤ 0), Block-Bootstrap mit 3-Monats-Blöcken."""
    j = pd.concat([ra, rb], axis=1).dropna()
    dlt = (np.log1p(j.iloc[:, 0]) - np.log1p(j.iloc[:, 1])).to_numpy()
    T, rng, c = len(dlt), np.random.default_rng(seed), 0
    for _ in range(n):
        idx = (rng.integers(0, T - block, T // block + 1)[:, None] + np.arange(block)).ravel()[:T]
        c += dlt[idx].mean() <= 0
    return (c + 1) / (n + 1)


def risk_scale(e: pd.Series, cash_r: pd.Series, target: float) -> float:
    """Größter Anteil w ∈ {0,05 … 1,0}, bei dem der Rückgang im Train (bis 2016) höchstens das Ziel erreicht."""
    tr = e[e.index <= pd.Timestamp("2016-12-31")]
    best = 0.0
    for w in np.arange(0.05, 1.0001, 0.05):
        m = metrics(with_cash(tr, w, cash_r))
        if m and m["max_dd"] >= -target:
            best = float(round(w, 2))
    return best


# ------------------------------------------------------------------ Lauf
def main_run(a) -> None:
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    prices, cur, fx, bench, (start, end) = load(a.data, "full")
    cal = bench["SPY"].index[(bench["SPY"].index >= start) & (bench["SPY"].index <= end)]
    frames = {t: bench[t][["Open", "High", "Low", "Close", "AdjClose"]] for t in ("SPY", "EFA", "QQQ", "SHY", "BIL", "ACWI")}
    frames["SPY2X"] = spy2x(bench)
    etf_cur = {t: "USD" for t in frames}
    cash_r = tbill_daily(bench)
    res, curves, taxc = {}, {}, {}

    def record(name, cap, cn, r=None, e=None, tax=None):
        e = r.equity if r is not None else e
        k = f"{name}|{cap}|{cn}"
        res[k] = segments(e, r.trades if r is not None else None, r.invested if r is not None else None)
        if r is not None:
            res[k]["checks"] = r.checks
        curves[k] = e
        if tax is not None:
            ea = after_tax(e, tax)
            taxc[k] = ea
            res[k]["nach_steuern"] = metrics(ea)

    for sid in ("ACWI", "S13-ETF", "S16-B", "SP1F", "SP2F"):
        o, ex, mx = etf_strategy(sid, bench, fx, start, end, cal)
        for cap in CASH:
            for cn, co in COSTS.items():
                r = run(frames, etf_cur, fx, o, cap, co, mx, calendar=cal, exit_when=ex, min_fill=0.5)
                record(sid, cap, cn, r, tax=taxable_from_run(r, stocks=False))
        print(sid, {c: round(res[f"{sid}|10000|stress"][ab]["cagr"], 4) for ab in AB + ("gesamt",) if res[f"{sid}|10000|stress"].get(ab)}, flush=True)
    uni = pd.read_csv(UNIVERSE)
    region = dict(zip(uni["ticker"], uni["region"]))
    P = Panel(prices, cur, region, bench, start, end)
    wave2.extra(P)
    sp = spreads(P.raw, cur, region)
    scost = {"base": Costs(fee_eur=0.99, spread=0.001, spread_by_ticker=sp, fee_free_from=250.0),
             "stress": Costs(fee_eur=1.99, spread=0.002, slippage=0.0005, fx_fee=0.001, fee_free_from=250.0,
                             spread_by_ticker={k: 2 * v for k, v in sp.items()})}
    scal = pd.DatetimeIndex(sorted(set().union(*[f.index[(f.index >= start) & (f.index <= end)] for f in P.raw.values()])))
    o, ex = wave2.monthly_stock(P, "S07-B", bench)
    for cap in CASH:
        for cn, co in scost.items():
            r = run(P.raw, cur, fx, o, cap, co, 10, calendar=scal, exit_when=ex, min_fill=0.5)
            record("S07-B", cap, cn, r, tax=taxable_from_run(r, stocks=True))
    print("S07-B", res["S07-B|10000|stress"]["gesamt"], flush=True)

    # Zufall
    null = {"S16-B": [], "S07-B": []}
    for seed in range(100):
        o_, ex_, _ = wave2.etf_rotation(bench, "S16-B", start, end, rng=np.random.default_rng(seed))
        null["S16-B"].append(segments(run(frames, etf_cur, fx, o_, 10000, COSTS["stress"], 3, calendar=cal, exit_when=ex_, min_fill=0.5).equity))
    for seed in range(40):
        o_, ex_ = wave2.monthly_stock(P, "S07-B", bench, rng=np.random.default_rng(seed))
        null["S07-B"].append(segments(run(P.raw, cur, fx, o_, 10000, scost["stress"], 10, calendar=scal, exit_when=ex_, min_fill=0.5).equity))
    print("Zufall fertig", flush=True)

    # Rücksetzer aus Runde 1
    if a.r1:
        d = Path(a.r1)
        for v in sorted({"E0", a.best}):
            for lay in ("20x025", "10x05", "5x1"):
                f = d / f"curve_{v}_{lay}.parquet"
                j = d / f"depot_{v}_{lay}.json"
                if not f.exists():
                    continue
                cv, info = pd.read_parquet(f), json.loads(j.read_text())
                for cap in CASH:
                    for cn in COSTS:
                        record(f"{v}-{lay}", cap, cn, e=cv[f"{cap}_{cn}"].dropna(), tax=info[f"{cap}_{cn}"]["steuer"])
        for cap in CASH:
            for cn, cost in (("base", 0.001), ("stress", 0.002)):
                ka, kb = f"S16-B|{cap}|{cn}", f"{a.best}-20x025|{cap}|{cn}"
                if kb in curves:
                    e = mix2(taxc[ka], taxc[kb], 0.5, cost)
                    k = f"K1|{cap}|{cn}"
                    res[k] = segments(mix2(curves[ka], curves[kb], 0.5, cost))
                    res[k]["nach_steuern"] = metrics(e)
                    curves[k] = mix2(curves[ka], curves[kb], 0.5, cost)

    # Vergleiche (10.000 €, Stress): p gegen ACWI und gegen Zufall, Risikostufen
    acwi = curves["ACWI|10000|stress"].pct_change()
    cmp_, stages = {}, {}
    names = sorted({k.split("|")[0] for k in curves})
    for n in names:
        k = f"{n}|10000|stress"
        if k not in curves:
            continue
        e = curves[k]
        cmp_[n] = {"p_vs_acwi": boot_p(e.pct_change(), acwi)}
        if n in null:
            z = [s["gesamt"]["cagr"] for s in null[n] if s.get("gesamt")]
            cmp_[n]["p_vs_zufall"] = (sum(x >= res[k]["gesamt"]["cagr"] for x in z) + 1) / (len(z) + 1)
            cmp_[n]["zufall_median"] = float(np.median(z))
        stages[n] = {}
        for tg in TARGETS:
            w = risk_scale(e, cash_r, tg)
            stages[n][f"{int(tg * 100)}%"] = {"w": w, **({ab: metrics(s) for ab, s in (("gesamt", with_cash(e, w, cash_r)),)} if w > 0 else {})}
    rows = {k: {kk: vv for kk, vv in v.items()} for k, v in res.items()}
    meta = {"commit": os.environ.get("GITHUB_SHA"), "prices_sha": os.environ.get("PRICES_SHA"), "best": a.best,
            "steuer": "26,375 % ohne Pauschbetrag, Aktien-Topf getrennt, ETF-Teilfreistellung 30 %, ohne Vorabpauschale"}
    (out / "compete.json").write_text(json.dumps({"meta": meta, "res": rows, "cmp": cmp_, "stages": stages}, indent=1, default=str))
    pd.DataFrame({k: v for k, v in curves.items() if "|10000|" in k or "|5000|" in k}).to_parquet(out / "compete_curves.parquet")
    print(json.dumps(cmp_, indent=1))


def main_pre(a) -> None:
    """ETF-Strategien 2003–2007 (vor dem bisherigen Train, nie benutzt), Basis-Kosten, 10.000 €, Vergleich SPY halten."""
    import yfinance as yf
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    tick = ["SPY", "EFA", "QQQ", "SHY", "^IRX"]
    d = yf.download(tick, start="2000-01-01", end="2008-01-01", auto_adjust=False, group_by="ticker", progress=False)
    bench = {}
    for t in tick:
        x = d[t].dropna(subset=["Close"]).rename(columns={"Adj Close": "AdjClose"})
        x.index = pd.to_datetime(x.index).tz_localize(None)
        bench[t] = x
    idx = bench["SPY"].index
    bench["BIL"] = bil_proxy(bench, idx)
    start, end = pd.Timestamp("2003-01-01"), pd.Timestamp("2007-12-31")
    cal = idx[(idx >= start) & (idx <= end)]
    frames = {t: bench[t][["Open", "High", "Low", "Close", "AdjClose"]] for t in ("SPY", "EFA", "QQQ", "SHY", "BIL")}
    frames["SPY2X"] = spy2x(bench)
    fx = {"USD": pd.Series(1.0, index=idx)}
    cur = {t: "EUR" for t in frames}                        # Vergleich in USD (Wechselkurs neutral)
    res = {}
    for sid in ("S16-B", "SP1F", "SP2F"):
        o, ex, mx = etf_strategy(sid, bench, fx, start, end, cal)
        r = run(frames, cur, fx, o, 10000, COSTS["base"], mx, calendar=cal, exit_when=ex, min_fill=0.5)
        res[sid] = metrics(r.equity, r.trades)
    r = run(frames, cur, fx, [Order(cal[0], "SPY", weight=0.995)], 10000, COSTS["base"], 1, calendar=cal)
    res["SPY halten"] = metrics(r.equity)
    (out / "compete_pre.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "pre"])
    ap.add_argument("--data"); ap.add_argument("--out", default="cp_out"); ap.add_argument("--r1"); ap.add_argument("--best", default="E0")
    a = ap.parse_args(argv)
    (main_run if a.cmd == "run" else main_pre)(a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
