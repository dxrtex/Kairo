"""Tages-Simulation der Strategie – dieselbe Logik für den Backtest UND das Live-Modelldepot im Abendscan.

Ablauf je Handelstag t (kein Blick in die Zukunft):
  Schlusskurs t: Regime, Vorauswahl, Ranking, Exit-Prüfung, Kaufliste und Stückzahlen berechnen.
  Eröffnung t+1: zuerst Verkäufe, dann Käufe strikt absteigend nach Gesamt-Score (solange Cash, Plätze, Sektor-Cap reichen).
Endet die Kursreihe einer gehaltenen Aktie (Delisting/Übernahme), wird sie am letzten Handelstag zum Schlusskurs verkauft.
Steuer (optional): 26,375 % auf realisierte Gewinne, Verluste zuerst in den Verlustverrechnungstopf.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

from . import exit_signals, filters, market_regime, position_sizing, scoring
from .config import CFG, Config


@dataclass
class Market:
    O: pd.DataFrame
    H: pd.DataFrame
    L: pd.DataFrame
    C: pd.DataFrame
    V: pd.DataFrame
    index_close: pd.Series
    fx: pd.Series | None = None                     # 1 Einheit Kurswährung = x USD (je Ticker)
    mcap: pd.Series | pd.DataFrame | None = None    # Börsenwert in USD (fest oder je Tag)
    sectors: dict = field(default_factory=dict)
    names: dict = field(default_factory=dict)
    fund: Callable[[pd.Timestamp], pd.DataFrame | None] | None = None   # Fundamentaldaten-Snapshot mit Stichtag ≤ t
    earnings: dict = field(default_factory=dict)    # Ticker → Liste ISO-Daten der Quartalszahlen


@dataclass
class Pos:
    shares: int
    entry_date: pd.Timestamp
    entry_px: float
    basis: float                                    # Kaufbetrag inkl. Kosten (für die Steuer)
    high: float                                     # höchster Schlusskurs seit Kauf
    sector: str = "?"


FILL_DAYS = 5                                       # Börsen-Feiertage anderer Länder: Kurse bis 5 Tage vorwärts auffüllen


def prepare(m: Market, cfg: Config = CFG) -> dict:
    """Alle Indikatoren einmal vektorisiert vorab (schnell für 6.000 Aktien).
    Gemischte Börsenkalender (USA, Europa, Asien): An fremden Handelstagen fehlen Kurse – ohne Auffüllen wären SMA 100/200
    und Regression nach jedem Feiertag monatelang ungültig. Daher werden Kurse bis 5 Tage fortgeschrieben (Umsatz = 0);
    gehandelt wird nur an echten Kurstagen."""
    Cf = m.C.ffill(limit=FILL_DAYS)
    Hf, Lf = m.H.fillna(Cf), m.L.fillna(Cf)
    Vf = m.V.fillna(0.0)
    ind = filters.indicators(Cf, Vf, m.fx, cfg)
    pool = filters.pool(Cf, ind, m.mcap if not isinstance(m.mcap, pd.DataFrame) else m.mcap.ffill(limit=FILL_DAYS), cfg)
    pool &= m.C.notna()                               # nur Aktien mit echtem Kurs am Signaltag
    mom = scoring.momentum(Cf, cfg)
    atr = position_sizing.atr(Hf, Lf, Cf, cfg.atr_days)
    reg = market_regime.regime(m.index_close.ffill(), cfg).reindex(m.C.index).ffill().fillna(False)
    if not cfg.use_regime:
        reg = pd.Series(True, index=m.C.index)
    last_valid = m.C.apply(lambda s: s.last_valid_index())
    return {"ind": ind, "pool": pool, "mom": mom, "atr": atr, "reg": reg, "last": last_valid}


def _px(df, t, k):
    v = df.at[t, k] if k in df.columns else np.nan
    return float(v) if v == v else np.nan


def rank_day(m: Market, P: dict, t: pd.Timestamp, cfg: Config = CFG) -> pd.DataFrame:
    row = P["pool"].loc[t]
    cands = list(row.index[row.to_numpy()])
    if cands and m.names:
        dv = P["ind"]["dv"].loc[t]
        cands = filters.dedupe(cands, m.names, dv.to_dict())
    f = m.fund(t) if m.fund else None
    return scoring.score_day(cands, P["mom"].loc[t], f, cfg)


def run(m: Market, start, end=None, cfg: Config = CFG, tax: bool = True, capital: float | None = None, P: dict | None = None,
        log_days: bool = False) -> dict:
    P = P or prepare(m, cfg)
    dates = m.C.index[(m.C.index >= pd.Timestamp(start)) & ((m.C.index <= pd.Timestamp(end)) if end is not None else True)]
    cash = float(capital if capital is not None else cfg.start_capital)
    pos: dict[str, Pos] = {}
    pot = taxes = costs = 0.0
    trades, equity, invested = [], [], []
    pending_sell: dict[str, list[str]] = {}
    pending_buy: list[tuple[str, int, float]] = []
    last_close: dict[str, float] = {}
    day_log = []

    def sell(t, px, when, why):
        nonlocal cash, pot, taxes, costs
        p = pos.pop(t)
        gross = p.shares * px
        fee = gross * cfg.cost
        proceeds = gross - fee
        costs += fee
        gain = proceeds - p.basis
        if tax:
            if gain < 0:
                pot += -gain
            else:
                use = min(pot, gain)
                pot -= use
                tx = (gain - use) * cfg.tax
                taxes += tx
                cash -= tx
        cash += proceeds
        trades.append({"t": t, "in": p.entry_date.strftime("%Y-%m-%d"), "out": when.strftime("%Y-%m-%d"), "n": p.shares,
                       "px_in": round(p.entry_px, 4), "px_out": round(px, 4), "pnl": round(proceeds - p.basis, 2),
                       "ret": round(proceeds / p.basis - 1, 4) if p.basis else None, "why": why,
                       "days": int((when - p.entry_date).days)})

    for k, t in enumerate(dates):
        # --- Eröffnung t: Aufträge vom Vortag ausführen (erst verkaufen, dann kaufen) ---
        for tk, why in list(pending_sell.items()):
            if tk in pos:
                px = _px(m.O, t, tk)
                px = px if px == px else _px(m.C, t, tk)
                if px == px:
                    sell(tk, px, t, ",".join(why))
        pending_sell = {}
        for tk, n, _sc in pending_buy:                  # bereits absteigend nach Score sortiert
            if tk in pos or len(pos) >= cfg.max_positions:
                continue
            px = _px(m.O, t, tk)
            if not (px == px and px > 0):
                continue
            n = min(n, int(cash // (px * (1 + cfg.cost)))) if cash > 0 else 0
            if n <= 0:
                continue
            gross = n * px
            fee = gross * cfg.cost
            cash -= gross + fee
            costs += fee
            pos[tk] = Pos(n, t, px, gross + fee, px, m.sectors.get(tk) or "?")
        pending_buy = []
        # --- Schlusskurs t: Bewertung, Zwangsverkauf bei Datenende, Signale ---
        for tk in list(pos):
            c = _px(m.C, t, tk)
            if c == c:
                last_close[tk] = c
                pos[tk].high = max(pos[tk].high, c)
            lv = P["last"].get(tk)
            if lv is not None and pd.notna(lv):
                lv = pd.Timestamp(lv)
                if lv < t or (lv == t and t < m.C.index[-1]):                          # letzter Handelstag dieser Aktie
                    sell(tk, last_close.get(tk, pos[tk].entry_px), lv, "delisted")
        val = cash + sum(p.shares * last_close.get(tk, p.entry_px) for tk, p in pos.items())
        equity.append((t, val))
        invested.append(1 - cash / val if val > 0 else 0.0)
        if k == len(dates) - 1 and not log_days:
            break
        scored = rank_day(m, P, t, cfg)
        top25 = scoring.top_quantile(scored, cfg.exit_rank_pct) if len(scored) else set()
        fri = t.weekday() == 4
        sma_f = P["ind"]["sma_f"].loc[t]
        atr_t = P["atr"].loc[t]
        for tk, p in pos.items():
            c = last_close.get(tk)
            if c is None:
                continue
            why = exit_signals.exit_reasons(c, float(sma_f.get(tk, np.nan)), p.high, float(atr_t.get(tk, np.nan)), fri, tk in top25, cfg)
            if why:
                pending_sell[tk] = why
        top = scoring.select(scored, m.sectors, cfg, slots=cfg.top_n) if len(scored) else []
        buys = []
        if bool(P["reg"].get(t, False)):
            keep = {tk: p.sector for tk, p in pos.items() if tk not in pending_sell}
            free = cfg.max_positions - len(keep)
            cnt: dict[str, int] = {}
            for s in keep.values():
                cnt[s] = cnt.get(s, 0) + 1
            for tk in top:
                if free <= 0:
                    break
                if tk in keep:
                    continue
                s = m.sectors.get(tk) or "?"
                if s != "?" and cnt.get(s, 0) >= cfg.sector_cap:
                    continue
                c_t = _px(m.C, t, tk)
                n = position_sizing.shares(val, float(atr_t.get(tk, np.nan)), c_t, cfg) if cfg.sizing == "atr" else (
                    int(val / cfg.max_positions // c_t) if c_t == c_t and c_t > 0 else 0)
                if n > 0:
                    buys.append((tk, n, float(scored.at[tk, "total"])))
                    cnt[s] = cnt.get(s, 0) + 1
                    free -= 1
        pending_buy = buys
        if log_days:
            day_log.append({"t": t, "scored": scored, "top": top, "buys": buys, "sells": dict(pending_sell), "top25": top25})
    eq = pd.Series(dict(equity))
    return {"equity": eq, "invested": float(np.mean(invested)) if invested else 0.0, "cash": cash, "pos": pos, "last_close": last_close, "trades": trades, "taxes": taxes, "costs": costs,
            "pot": pot, "pending_buy": pending_buy, "pending_sell": pending_sell, "log": day_log, "P": P}


def liquidate_after_tax(res: dict, cfg: Config = CFG) -> float:
    """Depotwert nach Verkauf aller Positionen zum letzten Schlusskurs inkl. Kosten und Abgeltungsteuer (mit Verlusttopf)."""
    cash, pot = res["cash"], res["pot"]
    for tk, p in res["pos"].items():
        gross = p.shares * res["last_close"].get(tk, p.entry_px)
        proceeds = gross * (1 - cfg.cost)
        gain = proceeds - p.basis
        if gain < 0:
            pot += -gain
        else:
            use = min(pot, gain)
            pot -= use
            cash -= (gain - use) * cfg.tax
        cash += proceeds
    return cash
