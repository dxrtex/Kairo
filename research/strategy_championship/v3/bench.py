"""Protokoll v3.0 §5 – Benchmark 70 % ACWI / 30 % Nasdaq-100 (QQQ) mit jährlichem Rebalancing, Kosten und Steuern.

Eigene kleine Simulation (die Engine kann nur ganze Positionen kaufen/verkaufen): Kauf zur Eröffnung des ersten Tages,
Rebalancing zur Eröffnung des ersten Handelstags jedes Jahres (nur die Differenz wird gehandelt), Dividenden als Cash
(beim nächsten Rebalancing angelegt). Kosten je Handel: halber Spread + Slippage + FX-Aufschlag (wie Costs.side) + Gebühr
nach PRIME+. Steuern: Durchschnittskosten je ETF, Teilfreistellung 30 %, Vorabpauschale wie tax.py.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ..engine import FX, Costs, dividends
from . import tax as T

W = {"ACWI": 0.7, "QQQ": 0.3}


def run_7030(etf: dict, fx: dict, start, end, cash0: float, costs: Costs) -> dict:
    fxo = FX(fx)
    df = {t: etf[t][(etf[t].index >= start) & (etf[t].index <= end)] for t in W}
    cal = df["ACWI"].index.intersection(df["QQQ"].index)
    div = {t: dividends(etf[t]).reindex(cal).fillna(0.0) for t in W}
    sh = {t: 0 for t in W}
    basis = {t: 0.0 for t in W}                    # Anschaffungskosten EUR (Durchschnitt)
    vap_acc = {t: 0.0 for t in W}
    cash, eq, yrs = float(cash0), {}, {}
    g = lambda y: yrs.setdefault(y, {"stock_gain": 0.0, "etf_gain": 0.0, "div": 0.0, "vap": 0.0})
    year, jan_val = None, {}
    for d in cal:
        r = fxo.rate("USD", d.to_datetime64())
        if year != d.year:                          # Rebalancing zur Eröffnung
            if year is not None:                    # Vorabpauschale des abgelaufenen Jahres (Bestand am 31.12.)
                bz = T.BASISZINS.get(year, 0.0)
                for t in W:
                    if bz > 0 and sh[t] > 0 and t in jan_val:
                        v1 = sh[t] * float(df[t]["Close"][df[t].index < d].iloc[-1]) / fxo.rate("USD", prev.to_datetime64())
                        vap = max(0.0, min(jan_val[t] * bz * 0.7, v1 - jan_val[t]))
                        vap_acc[t] += vap
                        g(year)["vap"] += vap * 0.7
            year = d.year
            op = {t: float(df[t]["Open"][d]) for t in W}
            tot = cash + sum(sh[t] * op[t] / r for t in W)
            for t in sorted(W, key=lambda x: sh[x] * op[x] / r - W[x] * tot, reverse=True):   # erst verkaufen, dann kaufen
                target = int(math.floor(W[t] * tot * 0.995 / (op[t] / r)))
                dq = target - sh[t]
                if dq == 0:
                    continue
                side = costs.side(t, "USD")
                if dq < 0:
                    px = op[t] * (1 - side)
                    val = -dq * px / r
                    fee = costs.fee(val)
                    cost_part = basis[t] * (-dq / sh[t])
                    vap_part = vap_acc[t] * (-dq / sh[t])
                    g(year)["etf_gain"] += (val - fee - cost_part - vap_part) * 0.7
                    basis[t] -= cost_part
                    vap_acc[t] -= vap_part
                    cash += val - fee
                else:
                    px = op[t] * (1 + side)
                    dq = min(dq, int(math.floor(max(0.0, cash - costs.fee_eur) / (px / r))))
                    if dq <= 0:
                        continue
                    val = dq * px / r
                    fee = costs.fee(val)
                    basis[t] += val + fee
                    cash -= val + fee
                sh[t] += dq
            jan_val = {t: sh[t] * op[t] / r for t in W}
        for t in W:
            if div[t][d] > 0 and sh[t] > 0:
                amt = sh[t] * div[t][d] / r
                cash += amt
                g(d.year)["div"] += amt * 0.7
        eq[d] = cash + sum(sh[t] * float(df[t]["Close"][d]) / r for t in W)
        prev = d
    # Liquidation am Ende
    d = cal[-1]
    r = fxo.rate("USD", d.to_datetime64())
    for t in W:
        if sh[t] > 0:
            px = float(df[t]["Close"][d]) * (1 - costs.side(t, "USD"))
            val = sh[t] * px / r
            fee = costs.fee(val)
            g(d.year)["etf_gain"] += (val - fee - basis[t] - vap_acc[t]) * 0.7
            cash += val - fee
            sh[t] = 0
    e = pd.Series(eq)
    e.iloc[-1] = cash
    return {"equity": e, "years": yrs}
