"""Probe-Depot LF10: die Langfrist-Strategie der App (backend/langfrist.py) im echten Markt, ohne echtes Geld (Wunsch 24.11.2026).

Regel exakt wie in der App: Rangliste nach 12-1-Momentum (US-Aktien der Scan-Liste, Ø Umsatz ≥ 5 Mio. $, Kurs ≥ 5 $),
nur mit Kursen VOR dem Handelstag. Am ersten Handelstag im Januar/April/Juli/Oktober zur Eröffnung: verkaufen, wer nicht mehr
auf Platz 1–20 steht; freie Plätze mit den bestplatzierten noch nicht gehaltenen Aktien füllen, bis 10 im Depot sind
(Depotwert ÷ 10 je Aktie). Erster Lauf: das aktuelle Depot der App (Puffer-Regel über die letzten Tauschtermine) zur nächsten
Eröffnung kaufen.

Echte Bedingungen: Eröffnungskurs, ganze Stücke, halber Spread je Seite, Scalable PRIME+ (0,99 € unter 250 € Orderwert),
Abgeltungsteuer 26,375 % mit Verlusttopf beim Verkauf (Sparerpauschbetrag nicht angesetzt – vorsichtig gerechnet).
Jede Order wird am Tag der Ausführung gespeichert und nie nachträglich geändert.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from backend import langfrist as LF

from . import core

SID = "LF10"
START_CASH = 10000.0
TAX = 0.26375
RESERVE = 0.995                     # je Platz knapp unter Depotwert ÷ 10, damit Gebühren und Spread Platz haben


def universe(fallback: list[str]) -> list[str]:
    """US-Liste des Scans (Branch kairo-data, universe_us.csv) – dieselbe Auswahl wie in der App; sonst die Papier-Liste."""
    import io
    import urllib.request
    try:
        with urllib.request.urlopen("https://raw.githubusercontent.com/dxrtex/Kairo/kairo-data/universe_us.csv", timeout=60) as r:
            u = pd.read_csv(io.StringIO(r.read().decode()), dtype={"ticker": str})
        t = [x for x in u["ticker"].dropna().astype(str) if "." not in x and "^" not in x]
        if len(t) > 500:
            return t
    except Exception as e:                             # noqa: BLE001
        print("universe_us.csv nicht geladen:", repr(e)[:200])
    return [x for x in fallback if "." not in x]


def is_rebal(D: pd.Timestamp, prev: pd.Timestamp, every: int = 3) -> bool:
    """Erster Handelstag eines Tauschmonats (Jan/Apr/Jul/Okt)."""
    return D.month in set(range(1, 13, every)) and (prev.month != D.month)


def _open(mk, t: str, D: pd.Timestamp) -> float | None:
    x = mk.daily.get(t)
    if x is None or not (x.index == D).any():
        return None
    v = float(x["Open"][x.index == D].iloc[0])
    return v if v > 0 and math.isfinite(v) else None


def sell(st: dict, mk, p: dict, px: float, why: str, D: pd.Timestamp, D_prev: pd.Timestamp) -> None:
    sp, rate = mk.spread(p["t"], D_prev), mk.rate(p["t"], D_prev)
    gross = p["qty"] * px * (1 - sp / 2) / rate
    f = core.fee(gross)
    proceeds = gross - f
    gain = proceeds - p["cost_eur"]
    tax = 0.0
    if gain < 0:
        st["tax_pot"] = st.get("tax_pot", 0.0) + (-gain)
    else:
        use = min(st.get("tax_pot", 0.0), gain)
        st["tax_pot"] = st.get("tax_pot", 0.0) - use
        tax = (gain - use) * TAX
    st["cash"] += proceeds - tax
    st["taxes"] = round(st.get("taxes", 0.0) + tax, 2)
    st["fees"] = round(st.get("fees", 0.0) + f + p["qty"] * px * sp / 2 / rate, 2)
    st["trades"].append({"t": p["t"], "entry_ts": p["entry_ts"], "entry": p["entry"], "stop0": p["entry"], "qty": p["qty"], "regime": "-",
                         "exit_ts": str(D.date()), "exit": px, "why": why, "pnl_eur": round(gain, 2), "tax_eur": round(tax, 2),
                         "ret": round(gain / p["cost_eur"], 4) if p["cost_eur"] else None, "R": None, "R_net": None})
    st["positions"].remove(p)
    st["events"].append(f"{D.date()} VERKAUF {p['t']} {p['qty']} Stk @ {px:.4g} ({why}) Gewinn {gain:+.2f} €, Steuer {tax:.2f} €")


def buy(st: dict, mk, t: str, D: pd.Timestamp, D_prev: pd.Timestamp, slot: float, rk: int | None) -> str:
    op = _open(mk, t, D)
    if op is None:
        return "nokurs"
    sp, rate = mk.spread(t, D_prev), mk.rate(t, D_prev)
    if not math.isfinite(rate):
        return "nokurs"
    px = op * (1 + sp / 2)
    q = int(math.floor(min(slot, st["cash"] - core.FEE) * rate / px))
    if q <= 0:
        st["events"].append(f"{D.date()} {t}: zu wenig Cash für 1 Stück – kein Kauf")
        return "cash"
    gross = q * px / rate
    f = core.fee(gross)
    st["cash"] -= gross + f
    st["fees"] = round(st.get("fees", 0.0) + f + q * op * sp / 2 / rate, 2)
    st["positions"].append({"sid": st["sid"], "t": t, "entry_ts": str(D.date()), "entry": op, "stop": 0.0, "stop0": op, "qty": q,
                            "cost_eur": gross + f, "risk_eur": None, "regime": "-", "rk": rk})
    st["events"].append(f"{D.date()} KAUF {t} {q} Stk @ {op:.4g} (Rang {rk})")
    return "ok"


def target(data: dict, meta: dict, held: list[str], D: pd.Timestamp, cal: pd.DatetimeIndex, first: bool) -> tuple[list[str], list[str], dict]:
    """(verkaufen, kaufen, Rang je Aktie) für Handelstag D – nur mit Kursen vor D."""
    rk = LF.rank(data, meta, D)
    pos = {t: i + 1 for i, (t, _) in enumerate(rk)}
    if first:                                          # aktuelles App-Depot: Puffer-Regel über die Tauschtermine davor
        rb = [d for d in LF.rebalance_dates(cal[cal <= D]) if (d - cal[0]).days >= 380]
        start = LF.depot_path(data, meta, rb)[-1][1] if rb else [t for t, _ in rk[:LF.RULE["n"]]]
        return [], start, pos
    out, inn = LF.next_swap(held, rk)
    return out, inn, pos


def day(st: dict, mk, D: pd.Timestamp, D_prev: pd.Timestamp, cal: pd.DatetimeIndex, data: dict, meta: dict, equity) -> None:
    """Ein Handelstag (nach Börsenschluss nachgerechnet, Ausführung zur Eröffnung von D)."""
    first = not st.get("rebal")
    if first or is_rebal(D, D_prev):
        held = [p["t"] for p in st["positions"]]
        out, inn, pos = target(data, meta, held, D, cal, first)
        st["rebal"] = str(D.date())
        for p in [p for p in st["positions"] if p["t"] in out]:
            px = _open(mk, p["t"], D) or mk.last_close(p["t"], D_prev) or p["entry"]
            sell(st, mk, p, px, f"Platz {pos.get(p['t'], '–')} > {LF.RULE['hold']}", D, D_prev)
        n = LF.RULE["n"]
        slot = equity(st, mk, D_prev) * RESERVE / n
        st["slot"], st["todo"] = slot, []
        for t in inn:
            if buy(st, mk, t, D, D_prev, slot, pos.get(t)) == "nokurs":
                st["todo"].append(t)
                st["events"].append(f"{D.date()} {t}: heute kein Kurs – Kauf am nächsten Handelstag")
        st["events"].append(f"{D.date()} {'Start' if first else 'Tausch'}: Depot = {', '.join(p['t'] for p in st['positions'])}")
    elif st.get("todo"):                               # Datenlücke am Tauschtag: am nächsten Handelstag zur Eröffnung nachholen
        left = []
        for t in st["todo"]:
            if not any(p["t"] == t for p in st["positions"]) and buy(st, mk, t, D, D_prev, st.get("slot") or 0.0, None) == "nokurs":
                left.append(t)
        st["todo"] = left
    st["equity"].append({"date": str(D.date()), "eur": round(equity(st, mk, D), 2), "open": len(st["positions"])})


def bench(st: dict, daily: dict, fx_usd: pd.Series | None, mix: float = 0.3) -> dict:
    """Vergleich ab dem Start: Welt-ETF (ACWI in €, kaufen & halten) und 70 % ETF / 30 % Probe-Depot (ohne Ausgleich im 1. Jahr)."""
    eq = st.get("equity") or []
    if not eq or "ACWI" not in daily or fx_usd is None:
        return {}
    a = (daily["ACWI"]["Close"] / fx_usd.reindex(daily["ACWI"].index, method="ffill")).dropna()
    s0 = st["start_cash"]
    a = a[a.index >= pd.Timestamp(eq[0]["date"])]
    if not len(a):
        return {}
    etf = {str(i.date()): s0 * float(v / a.iloc[0]) * (1 - 0.001) for i, v in a.items()}
    m = [{"date": e["date"], "etf": round(etf[e["date"]], 2), "mix": round((1 - mix) * etf[e["date"]] + mix * e["eur"], 2)}
         for e in eq if e["date"] in etf]
    return {"series": m}


def summary(st: dict, b: dict) -> dict:
    eq = pd.Series([e["eur"] for e in st["equity"]], dtype=float)
    s0 = st["start_cash"]
    last = float(eq.iloc[-1]) if len(eq) else s0
    ser = (b or {}).get("series") or []
    return {"start": st.get("start"), "tage": len(eq), "depot_eur": round(last, 2), "rendite": last / s0 - 1,
            "max_dd": float((eq / eq.cummax() - 1).min()) if len(eq) else 0.0, "trades": len(st["trades"]),
            "offen": len(st["positions"]), "steuern": st.get("taxes", 0.0), "kosten": st.get("fees", 0.0),
            "etf": ser[-1]["etf"] / s0 - 1 if ser else None, "mix": ser[-1]["mix"] / s0 - 1 if ser else None}
