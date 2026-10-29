"""Protokoll v3.0 §6 – deutsches Steuerszenario (Abgeltungsteuer) auf Engine-Ergebnisse.

26,375 % (25 % + 5,5 % Soli), keine Kirchensteuer, kein Sparerpauschbetrag. Aktien: Gewinne bei Verkauf, Verluste nur mit
Aktiengewinnen (Aktientopf, Vortrag). ETFs: Teilfreistellung 30 % (Aktien-ETF) bzw. 0 % (Anleihe-ETF) auf Gewinne,
Ausschüttungen und Vorabpauschale; ETF-Verluste und Dividenden im allgemeinen Topf (verrechenbar mit allem).
Vorabpauschale ab 2018 (Basiszins laut Protokoll), vorher vereinfacht 0. Steuer am Jahresende als anteilige Entnahme.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

RATE = 0.26375
BASISZINS = {2018: 0.0087, 2019: 0.0052, 2020: 0.0007, 2021: 0.0, 2022: 0.0, 2023: 0.0255, 2024: 0.0229, 2025: 0.0253, 2026: 0.0320}
ETF_EQ = {"ACWI", "SPY", "EFA", "QQQ", "IWDA.AS", "EUNL.DE", "VT", "IEFA", "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"}
ETF_BOND = {"SHY", "BIL", "IEF", "TLT", "AGG", "BND"}


def cls(t: str) -> str:
    return "etf_eq" if t in ETF_EQ else "etf_bond" if t in ETF_BOND else "stock"


def tf(c: str) -> float:
    return 0.3 if c == "etf_eq" else 0.0


def yearly_from_engine(res, prices: dict, fx_rate) -> dict:
    """Engine-Result → je Jahr {stock_gain, etf_gain (nach TF), div (nach TF), vap (nach TF)}.
    prices: Kursrahmen je Ticker (Close in Handelswährung), fx_rate(cur, date) → Einheiten je EUR (USD-ETFs)."""
    yrs: dict = {}
    g = lambda y: yrs.setdefault(y, {"stock_gain": 0.0, "etf_gain": 0.0, "div": 0.0, "vap": 0.0})
    vap_lot: dict = {}
    t = res.trades
    # Vorabpauschale je ETF-Position und Jahresende, an dem sie gehalten wurde
    if len(t):
        for k, r in t.iterrows():
            c = cls(r["ticker"])
            if c == "stock":
                continue
            px = prices[r["ticker"]]["Close"]
            ent, ex = pd.Timestamp(r["entry_date"]), pd.Timestamp(r["exit_date"])
            acc = 0.0
            for y in range(ent.year, ex.year + 1):
                bz = BASISZINS.get(y, 0.0)
                ye = pd.Timestamp(f"{y}-12-31")
                if bz <= 0 or ex <= ye:
                    continue
                p0 = px[px.index < pd.Timestamp(f"{y}-01-01")]
                p1 = px[px.index <= ye]
                if not len(p0) or not len(p1):
                    continue
                f0, f1 = fx_rate("USD", p0.index[-1]), fx_rate("USD", p1.index[-1])
                v0, v1 = r["qty"] * p0.iloc[-1] / f0, r["qty"] * p1.iloc[-1] / f1
                months = 12 - (ent.month - 1) if ent.year == y else 12
                vap = max(0.0, min(v0 * bz * 0.7 * months / 12, v1 - v0))
                acc += vap
                g(y)["vap"] += vap * (1 - tf(c))
            vap_lot[k] = acc
        for k, r in t.iterrows():
            c = cls(r["ticker"])
            y = pd.Timestamp(r["exit_date"]).year
            if c == "stock":
                g(y)["stock_gain"] += float(r["pnl_eur"])
            else:
                g(y)["etf_gain"] += (float(r["pnl_eur"]) - vap_lot.get(k, 0.0)) * (1 - tf(c))
    led = res.ledger
    if len(led):
        dv = led[led["kind"] == "DIV"]
        for r in dv.itertuples(index=False):
            c = cls(r.ticker)
            g(pd.Timestamp(r.date).year)["div"] += float(r.cash_flow_eur) * (1 - tf(c))
    return yrs


def taxes(yrs: dict) -> dict:
    """Jahreswerte → Steuer je Jahr mit Verlusttöpfen (Aktien / allgemein) und Vortrag."""
    stock_c, gen_c, out = 0.0, 0.0, {}
    for y in sorted(yrs):
        v = yrs[y]
        s = v["stock_gain"] + stock_c
        stock_c = min(0.0, s)
        s = max(0.0, s)
        gsum = v["etf_gain"] + v["div"] + v["vap"] + gen_c
        if gsum < 0:
            use = min(s, -gsum)
            s -= use
            gsum += use
        gen_c = min(0.0, gsum)
        out[y] = RATE * (s + max(0.0, gsum))
    return out


def after_tax(equity: pd.Series, tax_by_year: dict) -> dict:
    """Steuer am Jahresende (bzw. am letzten Tag) als anteilige Entnahme → Kurve und CAGR nach Steuern (nach Liquidation)."""
    e = equity.dropna()
    fac = pd.Series(1.0, index=e.index)
    mult = 1.0
    for y in sorted(tax_by_year):
        ye = e[e.index.year == y]
        if not len(ye) or tax_by_year[y] <= 0:
            continue
        d = ye.index[-1]
        mult *= max(0.0, 1 - tax_by_year[y] / float(e[d]))
        fac[fac.index >= d] = mult
    ea = e * fac
    yrs = (e.index[-1] - e.index[0]).days / 365.25
    cagr = (ea.iloc[-1] / e.iloc[0]) ** (1 / yrs) - 1 if yrs > 0 and ea.iloc[-1] > 0 else -1.0
    return {"cagr_after_tax": float(cagr), "final_after_tax": float(ea.iloc[-1]), "tax_total_eur": float(sum(tax_by_year.values())),
            "tax_by_year": {int(k): round(float(v), 2) for k, v in tax_by_year.items()}}
