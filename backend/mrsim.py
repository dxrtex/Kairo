"""Ereignisorientierte Depot-Simulation für die schnellen Mean-Reversion-Regeln A5 und W2 (W2-Audit 02.11.2026).

EINE Quelle für Forschung (research/reversal/w2audit.py) und Live-Schattentest (backend/mrshadow.py): gleiche Daten und
Regeln ⇒ gleiche Entscheidungen. Regeln eingefroren (01.11.2026), hier nur die Ausführung:

  Signal   Schluss von Tag d: drei Verlust-Schlusskurse, Schluss > 200-Tage-Linie, Kurs ≥ 1, Ø Umsatz 20 T. ≥ 5 Mio. $
  Abends   Entscheidung nur mit Wissen bis Schluss d: Kandidaten nach RSI(2) aufsteigend, so viele Orders wie freie Plätze
           (Positionen, die morgen zur Eröffnung verkauft werden, geben ihren Platz frei). Kapital wird je Order reserviert
           (Depotwert / Plätze). Eine nicht gefüllte Limit-Order belegt ihren Platz für diesen Tag – KEIN Nachrücken.
  Tag d+1  A5: Kauf zur Eröffnung (Marktorder). W2: Kauf-Limit L = Schluss d − 0,5 ATR(14), nur an diesem Handelstag gültig.
  Ausstieg Schluss > 5-Tage-Linie → Verkauf zur nächsten Eröffnung; spätestens Schluss des 10. Handelstags (Kauftag = Tag 1).

Ausführungsmodelle für das Kauf-Limit (hs = halber Spread):
  opt     Berührung genügt: Tief ≤ L → Kauf zu min(Eröffnung, L)   (bisherige Forschungsannahme)
  kons    Briefkurs muss L erreichen: Eröffnung·(1+hs) ≤ L → Kauf zur Eröffnung·(1+hs); sonst Tief ≤ L·(1 − hs − 0,1 %) → L
  streng  wie kons, aber Tief ≤ L·(1 − hs − 0,5 %) (Kurs muss deutlich durch das Limit laufen – Warteschlange)
  Alles ohne Intraday-/Orderbuchdaten: MODELLRECHNUNG, keine gemessene Ausführungsquote.

Kosten: Marktorders und Verkäufe zahlen hs (+ Schlupf, + FX-Aufschlag bei Nicht-EUR), Limit-Käufe zahlen genau ihren Preis.
Gebühr je Order (Scalable PRIME+: 0,99 € unter 250 € Orderwert). Ganze Stücke (Kleinkapital!), Bewertung in EUR.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

RULE_VERSION = "A5/W2 v1 (eingefroren 01.11.2026)"
SLOTS, MAX_DAYS = 5, 10
FILLS = ("opt", "kons", "streng")
FX_USD = {"USD": 1, "EUR": 1.1, "GBp": 0.0127, "GBX": 0.0127, "GBP": 1.27, "CHF": 1.1, "CAD": 0.74, "SEK": 0.095, "NOK": 0.095,
          "DKK": 0.147, "PLN": 0.25, "JPY": 0.0075, "CNY": 0.14, "INR": 0.012, "HKD": 0.128, "TWD": 0.031, "KRW": 0.00075,
          "AUD": 0.66, "IDR": 0.000064, "THB": 0.028, "MYR": 0.22, "SGD": 0.74, "NZD": 0.6}


@dataclass
class Cost:
    """Kostenszenario. Spread nach Liquidität am Signaltag (bekannt): Ø Umsatz ≥ 20 Mio. $ → spread_liq, sonst spread_ill."""
    name: str = "basis"
    fee: float = 0.99
    fee_free_from: float | None = 250.0
    spread_liq: float = 0.0015          # volle Geld-/Brief-Spanne (gettex/LS, EUR-Kurs in US-/EU-Handelszeit, Annahme)
    spread_ill: float = 0.0030
    slip: float = 0.0
    fx: float = 0.0                     # je Seite für Nicht-EUR-Titel

    def hs(self, adv_usd: float) -> float:
        return (self.spread_liq if adv_usd >= 2e7 else self.spread_ill) / 2

    def order_fee(self, value: float) -> float:
        return 0.0 if (self.fee_free_from is not None and value >= self.fee_free_from) else self.fee


COSTS = {
    "null": Cost("null", fee=0.0, fee_free_from=None, spread_liq=0.0, spread_ill=0.0),
    "basis": Cost("basis"),
    "stress": Cost("stress", spread_liq=0.003, spread_ill=0.006, slip=0.0005, fx=0.001),
    "free": Cost("free", fee_free_from=None),          # 0,99 € auf jede Order (ohne PRIME+)
    "g199": Cost("g199", fee=1.99, fee_free_from=None),  # 1,99 € auf jede Order (gettex ab 01.09.2026 laut Presse – UNBESTÄTIGT)
}


# ------------------------------------------------------------------ Signale (identisch für Forschung und Live)
def indicators(df: pd.DataFrame, cur: str = "USD") -> pd.DataFrame:
    """Indikatoren je Tag aus Tageskerzen (nur Vergangenheit). df: Open/High/Low/Close/Volume."""
    from .indicators import atr, rsi
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    c = df["Close"]
    out = pd.DataFrame(index=df.index)
    out["o"], out["h"], out["l"], out["c"] = df["Open"], df["High"], df["Low"], c
    out["sma5"], out["sma200"] = c.rolling(5).mean(), c.rolling(200).mean()
    out["rsi2"], out["atr"] = rsi(c, 2), atr(df, 14)
    vol = df["Volume"].fillna(0) if "Volume" in df else pd.Series(0.0, index=df.index)
    out["adv"] = (vol * c).rolling(20).mean() * FX_USD.get(cur, 1.0)
    out["down3"] = (c < c.shift(1)) & (c.shift(1) < c.shift(2)) & (c.shift(2) < c.shift(3))
    out["sig"] = out["down3"] & (c > out["sma200"]) & (c >= 1) & (out["adv"] >= 5e6)
    out["lim"] = c - 0.5 * out["atr"]
    return out


def signal_rows(t: str, ind: pd.DataFrame, start=None, end=None) -> list[dict]:
    m = ind["sig"].fillna(False).to_numpy(bool).copy()
    idx = ind.index
    if start is not None:
        m &= idx >= pd.Timestamp(start)
    if end is not None:
        m &= idx <= pd.Timestamp(end)
    out = []
    for i in np.flatnonzero(m):
        lim = float(ind["lim"].iat[i])
        out.append({"t": t, "d": idx[i], "rsi2": float(ind["rsi2"].iat[i]), "lim": lim if np.isfinite(lim) and lim > 0 else None,
                    "adv": float(ind["adv"].iat[i]), "close": float(ind["c"].iat[i]), "atr": float(ind["atr"].iat[i])})
    return out


# ------------------------------------------------------------------ Einzel-Ausführung
def fill_limit(o: float, low: float, lim: float, hs: float, model: str) -> float | None:
    """Kaufkurs für ein Tages-Limit lim bei Eröffnung o und Tagestief low – oder None (nicht ausgeführt)."""
    if not (np.isfinite(o) and np.isfinite(low) and lim and lim > 0):
        return None
    if model == "opt":
        return min(o, lim) if low <= lim else None
    buf = 0.001 if model == "kons" else 0.005
    if o * (1 + hs) <= lim:
        return o * (1 + hs)
    if low <= lim * (1 - hs - buf):
        return lim
    return None


@dataclass
class Px:
    """Kurs-Arrays einer Aktie für die Simulation (bereinigte Tageskerzen + EUR-Kurs je Tag)."""
    idx: pd.DatetimeIndex
    o: np.ndarray
    h: np.ndarray
    low: np.ndarray
    c: np.ndarray
    sma5: np.ndarray
    eur: np.ndarray                     # EUR je 1 Einheit Kurswährung (1.0 bei EUR)
    cur: str = "EUR"
    pos: dict = field(default_factory=dict)

    def at(self, d) -> int | None:
        if not self.pos:
            self.pos = {v: i for i, v in enumerate(self.idx.values)}
        return self.pos.get(np.datetime64(pd.Timestamp(d), "ns"))


def make_px(ind: pd.DataFrame, cur: str = "EUR", eur: np.ndarray | None = None) -> Px:
    n = len(ind)
    return Px(ind.index, ind["o"].to_numpy(float), ind["h"].to_numpy(float), ind["l"].to_numpy(float), ind["c"].to_numpy(float),
              ind["sma5"].to_numpy(float), np.ones(n) if eur is None else eur, cur)


def trade_of(P: Px, i: int, rule: str, lim: float | None, hs: float, cost: Cost, model: str = "opt") -> dict:
    """Ergebnis EINES Signals (Signal-Index i) ohne Depotgrenzen: Kauf i+1, Verkauf nach Regel. Renditen in Kurswährung."""
    n = len(P.c)
    if i + 1 >= n:
        return {"res": "signal"}
    k0 = i + 1
    fxs = cost.fx if P.cur not in ("EUR",) else 0.0
    if rule == "W2":
        e = fill_limit(P.o[k0], P.low[k0], lim, hs, model)
        if e is None:
            return {"res": "kein_kauf", "buy": str(P.idx[k0].date())}
        e_cost = e * (1 + fxs)
    else:
        e = P.o[k0]
        if not np.isfinite(e):
            return {"res": "signal"}
        e_cost = e * (1 + hs + cost.slip + fxs)
    for day, k in enumerate(range(k0, n), start=1):
        if day >= MAX_DAYS:
            x, xd, why, nd = P.c[k], k, "zeit", day
            break
        if P.c[k] > P.sma5[k]:
            if k + 1 >= n:
                return {"res": "open", "e": round(float(e), 4), "buy": str(P.idx[k0].date()), "days": day, "exit_next": True}
            x, xd, why, nd = P.o[k + 1], k + 1, "sma5", day + 1
            break
    else:
        return {"res": "open", "e": round(float(e), 4), "buy": str(P.idx[k0].date()), "days": n - k0,
                "now": round(float(P.c[-1] / e - 1), 4)}
    x_net = x * (1 - hs - cost.slip - fxs)
    return {"res": "closed", "why": why, "e": round(float(e), 4), "x": round(float(x), 4), "buy": str(P.idx[k0].date()),
            "exit": str(P.idx[xd].date()), "days": nd, "gross": round(float(x / e - 1), 5), "net": round(float(x_net / e_cost - 1), 5)}


# ------------------------------------------------------------------ Depot
def simulate(signals: list[dict], px: dict[str, Px], rule: str, model: str = "opt", cost: Cost = COSTS["basis"],
             cash0: float = 10_000.0, slots: int = SLOTS, min_order: float | None = None, integer: bool = True,
             calendar: pd.DatetimeIndex | None = None, start=None, end=None) -> dict:
    """Ereignisorientiertes Depot. min_order (z. B. 250): nie eine Order unter diesem Wert – dann weniger Plätze.
    Rückgabe: equity (Serie in EUR), trades, events (Order-Lebenslauf), counts."""
    by_day: dict = {}
    for s in signals:
        if s["t"] in px:
            by_day.setdefault(pd.Timestamp(s["d"]), []).append(s)
    if calendar is None:
        calendar = pd.DatetimeIndex(sorted({d for P in px.values() for d in P.idx}))
    if start is not None:
        calendar = calendar[calendar >= pd.Timestamp(start)]
    if end is not None:
        calendar = calendar[calendar <= pd.Timestamp(end)]
    cash = float(cash0)
    pos: dict = {}                       # t → dict(qty, i_buy, days, e, cost_eur, sell_next)
    orders: dict = {}                    # Ausführungsdatum → [order]
    events, trades = [], []
    counts = {"signale": 0, "orders": 0, "gefuellt": 0, "nicht_gefuellt": 0, "kein_platz": 0, "zu_teuer": 0, "gebuehren": 0.0}
    eq = []
    last_eq = cash

    def fx(P, i):
        return P.eur[i] if P.eur is not None else 1.0

    def sell(t, P, i, raw, why, d):
        nonlocal cash
        p = pos.pop(t)
        hs, fxs = p["hs"], (cost.fx if P.cur != "EUR" else 0.0)
        px_net = raw * (1 - hs - cost.slip - fxs)
        val = p["qty"] * px_net * fx(P, i)
        fee = cost.order_fee(p["qty"] * raw * fx(P, i))
        cash += val - fee
        counts["gebuehren"] += fee
        pnl = val - fee - p["cost_eur"]
        trades.append({"t": t, "sig": p["sig"], "buy": str(P.idx[p["i_buy"]].date()), "exit": str(P.idx[i].date()), "why": why,
                       "days": p["days"], "e": p["e"], "x": float(raw), "qty": p["qty"], "cost_eur": round(p["cost_eur"], 4),
                       "pnl_eur": round(pnl, 4), "ret": round(pnl / p["cost_eur"], 6) if p["cost_eur"] > 0 else None,
                       "gross": round(float(raw / p["e"] - 1), 6)})
        events.append({"d": str(pd.Timestamp(d).date()), "ev": "position_geschlossen", "t": t, "why": why})

    for d in calendar:
        # 1) Eröffnung: Signal-Verkäufe
        for t in [t for t, p in pos.items() if p["sell_next"]]:
            P = px[t]
            i = P.at(d)
            if i is not None:
                sell(t, P, i, P.o[i], "sma5", d)
        # 2) Tagesorders (gestern Abend platziert)
        for od in orders.pop(d, []):
            t, P = od["t"], px[od["t"]]
            i = P.at(d)
            hs = od["hs"]
            fxs = cost.fx if P.cur != "EUR" else 0.0
            if i is None:
                events.append({"d": str(d.date()), "ev": "order_abgelaufen", "t": t, "why": "kein Handel"}); continue
            if rule == "W2":
                e = fill_limit(P.o[i], P.low[i], od["lim"], hs, model)
                unit = None if e is None else e * (1 + fxs)
            else:
                e = P.o[i] if np.isfinite(P.o[i]) else None
                unit = None if e is None else e * (1 + hs + cost.slip + fxs)
            if e is None:
                counts["nicht_gefuellt"] += 1
                events.append({"d": str(d.date()), "ev": "order_nicht_ausgefuehrt", "t": t, "lim": od["lim"]}); continue
            unit_eur = unit * fx(P, i)
            budget = min(od["budget"], cash)
            qty = math.floor((budget - cost.order_fee(budget)) / unit_eur) if integer else (budget - cost.order_fee(budget)) / unit_eur
            if integer and min_order and 0 < qty * unit_eur < min_order:      # Mindestorder: aufrunden, wenn Kasse reicht
                q2 = math.ceil(min_order / unit_eur)
                if q2 * unit_eur <= cash:
                    qty = q2
            if qty <= 0:
                counts["zu_teuer"] += 1
                events.append({"d": str(d.date()), "ev": "order_zu_klein", "t": t}); continue
            val = qty * unit_eur
            fee = cost.order_fee(qty * e * fx(P, i))
            cash -= val + fee
            counts["gebuehren"] += fee
            counts["gefuellt"] += 1
            pos[t] = {"qty": qty, "i_buy": i, "days": 0, "e": float(e), "cost_eur": val + fee, "sell_next": False, "hs": hs, "sig": od["sig"]}
            events.append({"d": str(d.date()), "ev": "order_ausgefuehrt", "t": t, "px": round(float(e), 4), "qty": qty})
        # 3) Schluss: Zeit-Ausstieg / Ausstiegssignal, Bewertung
        for t in list(pos):
            P = px[t]
            i = P.at(d)
            if i is None:
                if P.idx[-1] < d:                       # Datenende
                    sell(t, P, len(P.c) - 1, P.c[-1], "datenende", d)
                continue
            p = pos[t]
            p["days"] += 1
            if p["days"] >= MAX_DAYS:
                sell(t, P, i, P.c[i], "zeit", d); continue
            p["sell_next"] = bool(P.c[i] > P.sma5[i])
        mv = 0.0
        for t, p in pos.items():
            P = px[t]
            j = int(P.idx.searchsorted(d, side="right") - 1)
            mv += p["qty"] * P.c[max(j, 0)] * fx(P, max(j, 0))
        last_eq = cash + mv
        eq.append(last_eq)
        # 4) Abends: neue Orders für den nächsten Handelstag der jeweiligen Aktie
        cand = sorted(by_day.get(d, []), key=lambda s: s["rsi2"])
        counts["signale"] += len(cand)
        if not cand:
            continue
        n_slots = slots if min_order is None else int(max(1, min(slots, last_eq // min_order)))
        staying = sum(1 for p in pos.values() if not p["sell_next"])
        free = n_slots - staying
        size = last_eq / n_slots
        avail = cash + sum(p["qty"] * px[t].c[max(int(px[t].idx.searchsorted(d, side="right") - 1), 0)]
                           for t, p in pos.items() if p["sell_next"])
        taken = set(pos) | {o["t"] for l in orders.values() for o in l}
        for s in cand:
            if s["t"] in taken:
                continue
            if free <= 0 or avail < 1:
                counts["kein_platz"] += 1
                events.append({"d": str(d.date()), "ev": "kein_platz", "t": s["t"]}); continue
            P = px[s["t"]]
            i_sig = P.at(d)
            if i_sig is None or i_sig + 1 >= len(P.c):
                continue
            if rule == "W2" and not s.get("lim"):
                continue
            exe = P.idx[i_sig + 1]
            budget = min(size, avail)
            orders.setdefault(exe, []).append({"t": s["t"], "lim": s.get("lim"), "budget": budget, "hs": cost.hs(s.get("adv") or 0),
                                               "sig": str(d.date())})
            avail -= budget
            free -= 1
            taken.add(s["t"])
            counts["orders"] += 1
            events.append({"d": str(d.date()), "ev": "order_geplant", "t": s["t"], "lim": s.get("lim"), "budget": round(budget, 2),
                           "fuer": str(exe.date())})
    return {"equity": pd.Series(eq, index=calendar[:len(eq)]), "trades": trades, "events": events, "counts": counts,
            "open": {t: {k: v for k, v in p.items() if k in ("qty", "e", "days", "sig")} for t, p in pos.items()}}


def stats(eq: pd.Series) -> dict:
    eq = eq[eq > 0]
    if len(eq) < 20:
        return {"cagr": None, "dd": None}
    yrs = max((eq.index[-1] - eq.index[0]).days / 365.25, 1e-9)
    return {"cagr": round(float((eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1), 4), "dd": round(float((eq / eq.cummax() - 1).min()), 4),
            "end": round(float(eq.iloc[-1]), 2)}
