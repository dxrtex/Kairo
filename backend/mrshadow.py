"""Schattentests schneller Mean Reversion (nur Forschung, kein Geld, keine Mitteilungen, kein Einfluss auf B60 oder Depots).

Regeln exakt wie in der Mean-Reversion-Meisterschaft (research/reversal/mrc.py, 01.11.2026):
  A5   Aktien USA/Europa: drei Verlust-Schlusskurse in Folge UND Schluss über der 200-Tage-Linie, Grundfilter (Kurs ≥ 1,
       Ø Tagesumsatz 20 Tage ≥ 5 Mio.) → Kauf zur nächsten Eröffnung, Verkauf zur Eröffnung nach dem ersten Schluss über der
       5-Tage-Linie, spätestens Schluss von Tag 10. Bei mehr Signalen als Plätzen: niedrigster RSI(2) zuerst.
  ETF  Sektor-ETFs (SPDR, aus dem Scan): RSI(2) < 10 UND über der 200-Tage-Linie, Ausstieg wie A5.
Jeder Lauf rechnet offene Signale aus den Tageskerzen neu (robust gegen Ausfälle), abgeschlossene werden eingefroren.
Gezählt werden nur Signale ab dem Starttag – keine Rückrechnung. Brutto-Rendite je Trade plus Netto mit angenommenen
Kosten (normal 0,05 % je Seite, Stress 0,25 % je Seite); die echten Kosten bei Scalable misst der Journal-Kosten-Check.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FILE = "mr_shadow.json"
RULES = ("A5", "ETF")
SLOTS = 5
COST = {"normal": 0.0005, "stress": 0.0025}
ETFS = ("XLK", "XLF", "XLV", "XLY", "XLP", "XLE", "XLI", "XLB", "XLU", "XLRE", "XLC")


def rsi2(c: pd.Series) -> pd.Series:
    from .indicators import rsi                    # dieselbe Wilder-RSI wie Scanner und Forschung
    return rsi(c, 2)


def signal_today(df: pd.DataFrame, rule: str) -> dict | None:
    """Signal am letzten Schluss der Kursreihe? Rückgabe mit Signaltag und Vorrang, sonst None."""
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    if len(df) < 210:
        return None
    c = df["Close"]
    i = len(c) - 1
    if not c.iloc[i] > c.iloc[i - 199:i + 1].mean():
        return None
    r2 = float(rsi2(c).iloc[i])
    if rule == "A5":
        if not (c.iloc[i] < c.iloc[i - 1] < c.iloc[i - 2] < c.iloc[i - 3]):
            return None
        vol = df["Volume"] if "Volume" in df else None
        adv = float((vol * c).iloc[i - 19:i + 1].mean()) if vol is not None else 0.0
        if c.iloc[i] < 1 or adv < 5e6:
            return None
    elif rule == "ETF":
        if not r2 < 10:
            return None
    return {"d": str(df.index[i].date()), "rsi2": round(r2, 2), "close": round(float(c.iloc[i]), 4)}


def replay(df: pd.DataFrame, d: str) -> dict:
    """Trade ab Signaltag d nach Regel: Kauf nächste Eröffnung, Verkauf nach Schluss > 5-Tage-Linie (nächste Eröffnung), max. Tag 10."""
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    idx = df.index
    i = int(idx.searchsorted(pd.Timestamp(d), side="right") - 1)
    o, c = df["Open"].to_numpy(float), df["Close"].to_numpy(float)
    sma5 = df["Close"].rolling(5).mean().to_numpy(float)
    if i + 1 >= len(c):
        return {"res": "signal"}
    e, k0 = o[i + 1], i + 1
    for day, k in enumerate(range(k0, len(c)), start=1):
        if day >= 10:                                  # wie die Engine: Zeitausstieg zum Schluss von Tag 10 vor dem Signal-Ausstieg
            return _done(e, c[k], idx[k0], idx[k], day, "zeit")
        if c[k] > sma5[k]:
            if k + 1 < len(c):
                return _done(e, o[k + 1], idx[k0], idx[k + 1], day + 1, "sma5")
            return {"res": "open", "e": round(e, 4), "buy": str(idx[k0].date()), "days": day, "exit_next": True}
    k = len(c) - 1
    return {"res": "open", "e": round(e, 4), "buy": str(idx[k0].date()), "days": k - k0 + 1, "now": round(float(c[k] / e - 1), 4)}


def _done(e, x, bd, xd, days, why) -> dict:
    g = x / e - 1
    return {"res": "closed", "why": why, "e": round(float(e), 4), "x": round(float(x), 4), "buy": str(bd.date()), "exit": str(xd.date()),
            "days": days, "gross": round(float(g), 5),
            **{f"net_{k}": round(float((x * (1 - c)) / (e * (1 + c)) - 1), 5) for k, c in COST.items()}}


def step(book: dict, rows: list[dict], data: dict, ctx: dict | None, today: str, record: bool = True) -> dict:
    """Täglicher Lauf (Abendscan): neue Signale aufnehmen (nur record=True), offene Signale nachrechnen."""
    book.setdefault("start", today)
    items = book.setdefault("items", {})
    if record:
        region = {r["ticker"]: str(r.get("region") or "").lower() for r in rows}
        for t, df in data.items():
            if region.get(t) not in ("us", "europe", "eu") or df is None:
                continue
            s = signal_today(df, "A5")
            if s and s["d"] >= book["start"]:
                items.setdefault(f"A5|{t}|{s['d']}", {"rule": "A5", "t": t, **s})
        for t in ETFS:
            df = (ctx or {}).get(t)
            if df is None:
                continue
            s = signal_today(df, "ETF")
            if s and s["d"] >= book["start"]:
                items.setdefault(f"ETF|{t}|{s['d']}", {"rule": "ETF", "t": t, **s})
    for key, it in items.items():
        if it.get("res") == "closed":
            continue
        df = data.get(it["t"]) if it["rule"] == "A5" else (ctx or {}).get(it["t"])
        if df is None:
            continue
        try:
            it.update(replay(df, it["d"]))
        except Exception as exc:
            print("Schattentest:", key, repr(exc)[:80])
    book["updated"] = today
    return book


def depot(items: list[dict], slots: int = SLOTS) -> list[dict]:
    """Welche Signale ein Depot mit `slots` Plätzen gekauft hätte (je Tag niedrigster RSI(2) zuerst, belegte Plätze zählen)."""
    taken, busy = [], []
    for d in sorted({x["d"] for x in items}):
        busy = [b for b in busy if (b.get("exit") or "9999") > d]
        free = slots - len(busy)
        cand = sorted([x for x in items if x["d"] == d and x.get("res") in ("open", "closed")], key=lambda x: x["rsi2"])
        held = {b["t"] for b in busy}
        for x in cand:
            if free <= 0:
                break
            if x["t"] in held:
                continue
            taken.append(x); busy.append(x); held.add(x["t"]); free -= 1
    return taken


def summary(book: dict) -> dict:
    out = {"start": book.get("start"), "updated": book.get("updated")}
    items = list((book.get("items") or {}).values())
    for rule in RULES:
        xs = [x for x in items if x["rule"] == rule]
        sel = depot(xs) if rule == "A5" else xs
        done = [x for x in sel if x.get("res") == "closed"]
        m = lambda k: round(float(np.mean([x[k] for x in done])), 5) if done else None
        out[rule] = {"signals": len(xs), "taken": len(sel), "open": sum(x.get("res") == "open" for x in sel), "closed": len(done),
                     "gross": m("gross"), "net_normal": m("net_normal"), "net_stress": m("net_stress"),
                     "win": round(float(np.mean([x["gross"] > 0 for x in done])), 3) if done else None,
                     "days": round(float(np.mean([x["days"] for x in done])), 1) if done else None,
                     "sum_normal": round(float(np.sum([x["net_normal"] for x in done]) / SLOTS), 4) if done and rule == "A5" else None}
    return out
