"""B3 – Gegenrechnung: Ledger-Engine vs. unabhängiger Alt-Simulator (backend.shortswing.simulate, QRULE).

Je Signal wird der Trade isoliert (ein Titel, keine Kosten, Einstiegs-Gruppe) in der neuen Engine gerechnet und mit
`simulate` auf denselben bereinigten Kursen verglichen: Einstiegstag, Ausstiegstag, Ausstiegsgrund und Ergebnis in R.
Abweichungen bis 0,02 R gelten als Rundung (Alt-Simulator rechnet mit auf 4 Stellen gerundeten Kursen und bereinigten,
die Engine mit unbereinigten Kursen + Dividenden-Gutschrift).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backend.shortswing import simulate

from . import s01
from .data import adjusted
from .engine import Costs, run

QRULE = dict(entry="base", ck=5, cm=1.5, lowhalf=False, wait=10, inv=10, buf=0.25, maxd=3.0, tgt=None, wkend=False,
             levs=[1], hold=20)
WHY = {"time": "zeit", "stop": "stop", "stop_gap": "stop", "data_end": None, "end": None}


def old(raw: pd.DataFrame, i: int, atr_adj: float) -> dict | None:
    raw = raw.dropna(subset=["Open", "High", "Low", "Close", "AdjClose"])
    adj = adjusted(raw[raw["Close"] > 0])
    o, h, l, c = (adj[k].to_numpy(float) for k in ("Open", "High", "Low", "Close"))
    cl, j1 = c[i], min(len(c), i + 1 + 63)
    rn = lambda a: [round(float(x / cl), 4) for x in a]
    px = {"o": rn(o[i + 1:j1]), "h": rn(h[i + 1:j1]), "l": rn(l[i + 1:j1]), "c": rn(c[i + 1:j1]),
          "pl": rn(l[max(0, i - 9):i + 1]), "atr": round(atr_adj / cl, 4), "s": 0.0, "e20": 1.0, "wd": []}
    return simulate(px, QRULE)


def new(raw: pd.DataFrame, t: str, i: int, atr_adj: float) -> dict | None:
    orders = s01.base_orders(raw, i, atr_adj, t, gid="g", variant="A", risk_frac=None)
    if not orders:
        return None
    for o in orders:
        o.weight, o.risk_frac = 0.9, None
    df = s01.with_ema(raw)
    r = run({t: df}, {t: "EUR"}, {}, orders, start_cash=1e9, costs=Costs(fee_eur=0, spread=0), max_open=1)
    if not len(r.trades):
        return {"skip": r.skipped}
    tr = r.trades.iloc[0]
    risk = tr["entry_px"] - tr["stop"]
    gross = (tr["exit_px"] - tr["entry_px"]) / risk
    divs = r.ledger.loc[r.ledger["kind"] == "DIV", "cash_flow_eur"].sum() / tr["qty"] / risk if len(r.ledger) else 0
    return {"entry_date": tr["entry_date"], "exit_date": tr["exit_date"], "why": tr["why"], "r_px": gross,
            "r_tot": gross + divs, "days": int(tr["days"])}


def compare(raw: pd.DataFrame, t: str, sig: dict) -> dict:
    a, b = old(raw, sig["i"], sig["atr"]), new(raw, t, sig["i"], sig["atr"])
    row = {"ticker": t, "date": str(pd.Timestamp(sig["date"]).date())}
    a_trade = a is not None and "r" in a
    b_trade = b is not None and "r_px" in b
    row["old"] = None if not a_trade else {"r": round(a["r"], 4), "d": a["d"], "x": a["x"], "s": a["s"]}
    row["new"] = None if not b_trade else {k: (str(v.date()) if isinstance(v, pd.Timestamp) else round(v, 4) if isinstance(v, float) else v)
                                           for k, v in b.items()}
    if not a_trade and not b_trade:
        row["match"] = True
    elif a_trade != b_trade:
        row["match"] = False
    else:
        idx = raw.dropna(subset=["Open", "High", "Low", "Close", "AdjClose"]).index
        ent = idx[sig["i"] + 1 + a["s"]]
        row["match"] = bool(ent == b["entry_date"] and a["d"] == b["days"] and WHY.get(b["why"], b["why"]) == a["x"]
                            and abs(a["r"] - b["r_tot"]) <= 0.02)
    return row
