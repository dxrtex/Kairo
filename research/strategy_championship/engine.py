"""B3 – Ledger-basierte Depot-Simulation (Long-only, Aktien direkt, ohne Hebel).

Unabhängig vom bisherigen shortswing-Simulator geschrieben. Grundsätze:
- Entscheidungen fallen nach Handelsschluss von Tag t (Order mit `decision_date` = t) und werden frühestens zur
  Eröffnung des nächsten Handelstags DES JEWEILIGEN WERTPAPIERS ausgeführt.
- Kurse: unbereinigte Open/High/Low/Close (wie gehandelt, Splits von Yahoo bereits eingerechnet); Dividenden werden aus
  dem Verhältnis AdjClose/Close abgeleitet und am Ex-Tag als Cash gebucht.
- Stop: Eröffnung ≤ Stop → Verkauf zur Eröffnung (Kurslücke), sonst Tief ≤ Stop → Verkauf zum Stop. Stop und Ziel am
  selben Tag → Stop (vorsichtig). Zeit-Ausstieg zum Schluss des N-ten Handelstags (Einstiegstag = Tag 1).
- Bedingte Einstiege: `entry_band` (nur kaufen, wenn die Eröffnung in (lo, hi] liegt), `risk_atr` (Abstand Kauf–Stop
  muss in [min, max] × ATR liegen) – sonst verfällt die Order. Mehrere Orders derselben `group`: höchstens ein Kauf.
- Ausstiegsregel „ema“: ab Tag `from` Schluss unter der EMA (Spalte EMA im Kursrahmen) → Verkauf zur nächsten Eröffnung.
- Kosten: feste Gebühr je Order in EUR + halber Spread je Seite (auf den Ausführungskurs) + optional Slippage.
- Währung: alle Buchungen in EUR mit dem Tageskurs (EURxxx = xxx je 1 EUR); GBp = Pence.
- Equity = Cash + Σ Stück × letzter Schluss × FX (täglich); Datenende eines Titels (Delisting/Lücke) → Zwangsverkauf zum
  letzten Schluss („data_end“); Simulationsende → Verkauf zum letzten Schluss („end“).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class Costs:
    fee_eur: float = 0.99           # je Order (Scalable Free Broker, Annahme)
    spread: float = 0.001           # volle Geld-/Brief-Spanne; je Seite die Hälfte (Standard, falls kein Titel-Wert)
    slippage: float = 0.0           # zusätzlich je Seite (Anteil)
    fx_fee: float = 0.0             # zusätzlich je Seite für Nicht-EUR-Titel
    spread_by_ticker: dict = field(default_factory=dict)

    def side(self, t: str, cur: str) -> float:
        return self.spread_by_ticker.get(t, self.spread) / 2 + self.slippage + (self.fx_fee if cur not in ("EUR",) else 0.0)


@dataclass
class Order:
    decision_date: pd.Timestamp     # Information bis einschließlich Schluss dieses Tages
    ticker: str
    stop: float | None = None       # Stop-Kurs in Wertpapierwährung (None = kein Stop)
    max_days: int | None = None     # Zeit-Ausstieg zum Schluss von Tag N
    target: float | None = None     # Limit-Verkauf (optional)
    risk_frac: float | None = None  # Risiko je Trade als Anteil des Depotwerts (Stop nötig)
    weight: float | None = None     # alternativ: Zielgewicht des Depotwerts
    prio: float = 0.0               # höher = zuerst
    tag: str = ""
    entry_band: tuple | None = None # (lo, hi): nur kaufen, wenn lo < Eröffnung ≤ hi
    atr: float | None = None
    risk_atr: tuple | None = None   # (min, max) × ATR für Kauf − Stop
    group: str | None = None
    exit_rule: tuple | None = None  # ("ema", from_day)
    valid_days: int = 1             # so viele Eröffnungen des Titels bleibt die Order gültig


@dataclass
class Result:
    equity: pd.Series
    ledger: pd.DataFrame
    trades: pd.DataFrame
    skipped: dict
    checks: dict = field(default_factory=dict)
    invested: pd.Series | None = None


class _Px:
    """Kursreihe eines Titels als Arrays (schneller Zugriff je Datum)."""
    __slots__ = ("dates", "o", "h", "l", "c", "div", "ema", "pos", "last")

    def __init__(self, df: pd.DataFrame):
        self.dates = df.index.values.astype("datetime64[ns]")
        self.o, self.h, self.l, self.c = (df[k].to_numpy(float) for k in ("Open", "High", "Low", "Close"))
        self.div = dividends(df).to_numpy(float) if "AdjClose" in df else np.zeros(len(df))
        self.ema = df["EMA"].to_numpy(float) if "EMA" in df else None
        self.last = self.dates[-1] if len(self.dates) else None

    def idx(self, d: np.datetime64) -> int | None:
        i = int(np.searchsorted(self.dates, d))
        return i if i < len(self.dates) and self.dates[i] == d else None

    def asof(self, d: np.datetime64) -> int | None:
        i = int(np.searchsorted(self.dates, d, side="right")) - 1
        return i if i >= 0 else None


def dividends(df: pd.DataFrame) -> pd.Series:
    """Dividende je Aktie am Ex-Tag aus AdjClose/Close: D_t = C_{t-1} × (1 − f_{t-1}/f_t)."""
    f = (df["AdjClose"] / df["Close"]).astype(float)
    d = df["Close"].shift(1) * (1 - f.shift(1) / f)
    return d.where(d > 1e-9, 0.0).fillna(0.0)


class FX:
    def __init__(self, fx: dict[str, pd.Series]):
        self.s = {k: (v.index.values.astype("datetime64[ns]"), v.to_numpy(float)) for k, v in fx.items()}

    def rate(self, cur: str, d: np.datetime64) -> float:
        """Einheiten der Währung je 1 EUR (letzter bekannter Kurs bis d)."""
        if cur in ("EUR", None, ""):
            return 1.0
        scale = 100.0 if cur in ("GBp", "GBX") else 1.0
        base = "GBP" if cur in ("GBp", "GBX") else cur
        if base not in self.s:
            raise KeyError(f"FX fehlt: {base}")
        ds, vs = self.s[base]
        i = int(np.searchsorted(ds, d, side="right")) - 1
        if i < 0 or not np.isfinite(vs[i]):
            raise KeyError(f"FX {base} vor {d} unbekannt")
        return float(vs[i]) * scale


@dataclass
class _Pos:
    ticker: str
    qty: int
    entry_date: np.datetime64
    entry_px: float
    stop: float | None
    target: float | None
    max_days: int | None
    exit_rule: tuple | None
    tag: str
    cost_eur: float
    risk_eur: float = 0.0
    spread_eur: float = 0.0
    days: int = 0


def run(prices: dict[str, pd.DataFrame], currency: dict[str, str], fx: dict[str, pd.Series], orders: list[Order],
        start_cash: float = 5000.0, costs: Costs = Costs(), max_open: int = 5, exit_signals: set | None = None,
        calendar: pd.DatetimeIndex | None = None) -> Result:
    """prices[t]: DataFrame (Index Datum; Open/High/Low/Close, optional AdjClose, EMA). exit_signals: {(Datum, Ticker)} →
    Verkauf zur nächsten Eröffnung (Entscheidung nach Schluss dieses Tages)."""
    need = {o.ticker for o in orders}
    px = {t: _Px(prices[t]) for t in need if t in prices}
    fxo = FX(fx)
    if calendar is None:
        calendar = pd.DatetimeIndex(sorted(set().union(*[df.index for df in prices.values()]))) if prices else pd.DatetimeIndex([])
    cal = calendar.values.astype("datetime64[ns]")
    exit_sig = {}
    for (sd, t) in (exit_signals or set()):
        exit_sig.setdefault(np.datetime64(pd.Timestamp(sd), "ns"), set()).add(t)
    pending: dict[np.datetime64, list[Order]] = {}
    for o in orders:
        pending.setdefault(np.datetime64(pd.Timestamp(o.decision_date), "ns"), []).append(o)
    queue: list[list] = []                      # [Order, verbleibende Eröffnungen]
    sell_next: set[str] = set()
    filled_groups: set[str] = set()
    cash, pos = float(start_cash), {}
    led, trades, eq, inv = [], [], {}, {}
    skipped = {"no_data": 0, "open_below_stop": 0, "band": 0, "risk_atr": 0, "full": 0, "held": 0, "no_cash": 0, "group": 0}

    def close_of(t, d):
        p = px[t]
        i = p.asof(d)
        return p.c[i]

    def book(d, kind, t, qty, price, fee, note=""):
        nonlocal cash
        cur = currency.get(t, "EUR")
        rate = fxo.rate(cur, d)
        amt = (-qty * price / rate if kind == "BUY" else qty * price / rate) - fee
        cash += amt
        led.append({"date": pd.Timestamp(d), "kind": kind, "ticker": t, "qty": qty, "px": price, "cur": cur, "fx": rate,
                    "fee": fee, "cash_flow_eur": amt, "cash_after": cash, "note": note})
        return amt

    def sell(d, p: _Pos, raw_px, why):
        cur = currency.get(p.ticker, "EUR")
        price = raw_px * (1 - costs.side(p.ticker, cur))
        flow = book(d, "SELL", p.ticker, p.qty, price, costs.fee_eur, why)
        spread_out = p.qty * (raw_px - price) / fxo.rate(cur, d)
        trades.append({"ticker": p.ticker, "tag": p.tag, "entry_date": pd.Timestamp(p.entry_date), "exit_date": pd.Timestamp(d),
                       "entry_px": p.entry_px, "exit_px": price, "qty": p.qty, "days": p.days, "why": why,
                       "pnl_eur": flow - p.cost_eur, "stop": p.stop, "cost_eur": p.cost_eur, "risk_eur": p.risk_eur,
                       "fees_eur": 2 * costs.fee_eur, "spread_eur": p.spread_eur + spread_out})
        del pos[p.ticker]

    def equity(d):
        return cash + sum(q.qty * close_of(q.ticker, d) / fxo.rate(currency.get(q.ticker, "EUR"), d) for q in pos.values())

    for d in cal:
        # 1) Eröffnung: Signal-Verkäufe, dann Käufe
        for t in sorted(sell_next):
            p = pos.get(t)
            i = px[t].idx(d) if p else None
            if p is not None and i is not None:
                sell(d, p, px[t].o[i], "signal")
                sell_next.discard(t)
        todo, queue = sorted(queue, key=lambda x: -x[0].prio), []
        for item in todo:
            o, left = item
            p_ = px.get(o.ticker)
            if p_ is None:
                skipped["no_data"] += 1
                continue
            i = p_.idx(d)
            if i is None:
                if p_.last is not None and p_.last > d:
                    queue.append(item)              # Titel handelt heute nicht → warten
                else:
                    skipped["no_data"] += 1
                continue
            retry = left > 1
            if o.group is not None and o.group in filled_groups:
                skipped["group"] += 1
                continue
            if o.ticker in pos:
                skipped["held"] += 1
                continue
            if len(pos) >= max_open:
                skipped["full"] += 1
                continue
            op = p_.o[i]
            if not np.isfinite(op) or op <= 0 or (o.stop is not None and op <= o.stop):
                skipped["open_below_stop"] += 1
                continue
            if o.entry_band is not None and not (o.entry_band[0] < op <= o.entry_band[1]):
                skipped["band"] += 1
                if retry:
                    queue.append([o, left - 1])
                continue
            if o.risk_atr is not None and o.atr and o.stop is not None:
                rr = (op - o.stop) / o.atr
                if not (o.risk_atr[0] <= rr <= o.risk_atr[1]):
                    skipped["risk_atr"] += 1
                    if o.group is not None:             # wie im Original: Signal verworfen, kein späterer Versuch
                        filled_groups.add(o.group)
                    continue
            cur = currency.get(o.ticker, "EUR")
            rate = fxo.rate(cur, d)
            price = op * (1 + costs.side(o.ticker, cur))
            eq_now = equity(d)
            if o.risk_frac is not None and o.stop is not None:
                per = (price - o.stop) / rate
                qty = int(math.floor(eq_now * o.risk_frac / per)) if per > 0 else 0
            elif o.weight is not None:
                qty = int(math.floor(eq_now * o.weight / (price / rate)))
            else:
                qty = 0
            qty = min(qty, int(math.floor(max(0.0, cash - costs.fee_eur) / (price / rate))))
            if qty <= 0:
                skipped["no_cash"] += 1
                continue
            flow = book(d, "BUY", o.ticker, qty, price, costs.fee_eur, o.tag)
            pos[o.ticker] = _Pos(o.ticker, qty, d, price, o.stop, o.target, o.max_days, o.exit_rule, o.tag, -flow,
                                 risk_eur=qty * (price - o.stop) / rate if o.stop is not None else 0.0,
                                 spread_eur=qty * (price - op) / rate)
            if o.group is not None:
                filled_groups.add(o.group)
        # 2) Tagesverlauf: Dividende, Stop, Ziel, Zeit; Ausstiegsregel EMA → nächste Eröffnung
        for t in list(pos):
            p, P = pos[t], px[t]
            i = P.idx(d)
            if i is None:
                continue
            o_, h_, l_, c_ = P.o[i], P.h[i], P.l[i], P.c[i]
            p.days += 1
            if P.div[i] > 0 and p.days > 1:
                book(d, "DIV", t, p.qty, P.div[i], 0.0, "dividende")
            if p.stop is not None and p.days > 1 and o_ <= p.stop:
                sell(d, p, o_, "stop_gap"); continue
            if p.stop is not None and l_ <= p.stop:
                sell(d, p, p.stop, "stop"); continue
            if p.target is not None and h_ >= p.target:
                sell(d, p, max(p.target, o_) if p.days > 1 else p.target, "target"); continue
            if p.max_days is not None and p.days >= p.max_days:
                sell(d, p, c_, "time"); continue
            if p.exit_rule and p.exit_rule[0] == "ema" and P.ema is not None and p.days >= p.exit_rule[1] and c_ < P.ema[i]:
                sell_next.add(t)
        for t in list(pos):                         # Datenende des Titels
            if px[t].last < d:
                sell(d, pos[t], close_of(t, d), "data_end")
        # 3) Entscheidungen nach Schluss
        for o in pending.get(d, []):
            queue.append([o, max(1, o.valid_days)])
        for t in exit_sig.get(d, ()):
            if t in pos:
                sell_next.add(t)
        e_ = equity(d)
        eq[pd.Timestamp(d)] = e_
        inv[pd.Timestamp(d)] = (e_ - cash) / e_ if e_ > 0 else 0.0
    for t in list(pos):
        sell(cal[-1], pos[t], close_of(t, cal[-1]), "end")
    if len(cal):
        eq[pd.Timestamp(cal[-1])] = cash
    res = Result(pd.Series(eq, name="equity"), pd.DataFrame(led), pd.DataFrame(trades), skipped,
                 invested=pd.Series(inv, name="invested"))
    res.checks = audit(res, start_cash)
    return res


def audit(res: Result, start_cash: float) -> dict:
    """Bilanzprüfung: Σ Cashflows = Endcash − Startcash; kein negativer Kassenstand; Σ Trade-PnL + Dividenden = Equity-Änderung."""
    led, out = res.ledger, {}
    if len(led):
        out["cash_consistent"] = bool(abs(start_cash + led["cash_flow_eur"].sum() - led["cash_after"].iloc[-1]) < 1e-6)
        out["min_cash"] = float(led["cash_after"].min())
        out["no_negative_cash"] = bool(out["min_cash"] > -1e-6)
        div = led.loc[led["kind"] == "DIV", "cash_flow_eur"].sum()
        tp = res.trades["pnl_eur"].sum() if len(res.trades) else 0.0
        out["pnl_matches_equity"] = bool(abs(tp + div - (res.equity.iloc[-1] - start_cash)) < 1e-4)
    return out
