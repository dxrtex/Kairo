"""Schattentests schneller Mean Reversion (nur Forschung, kein Geld, keine Mitteilungen, kein Einfluss auf B60 oder Depots).

Regeln exakt wie in der Mean-Reversion-Meisterschaft (research/reversal/mrc.py, 01.11.2026):
  A5   Aktien USA/Europa: drei Verlust-Schlusskurse in Folge UND Schluss über der 200-Tage-Linie, Grundfilter (Kurs ≥ 1,
       Ø Tagesumsatz 20 Tage ≥ 5 Mio.) → Kauf zur nächsten Eröffnung, Verkauf zur Eröffnung nach dem ersten Schluss über der
       5-Tage-Linie, spätestens Schluss von Tag 10. Bei mehr Signalen als Plätzen: niedrigster RSI(2) zuerst.
  W2   wie A5, aber Kauf-Limit 0,5 ATR(14) unter dem Signal-Schluss, gilt nur am nächsten Handelstag (Welle 3, 01.11.2026:
       stärkste Variante, aber nach dreifacher Auswertung derselben Daten nur ein Hinweis). Gefüllt, wenn das Tagestief das
       Limit erreicht – zum Limit oder zur tieferen Eröffnung. Achtung: Berührung = Ausführung ist eher optimistisch.
  ETF  Sektor-ETFs (SPDR, aus dem Scan): RSI(2) < 10 UND über der 200-Tage-Linie, Ausstieg wie A5.
W2-Audit 02.11.2026: Das Depot (welche Signale belegen die 5 Plätze) rechnet jetzt backend/mrsim.py – dieselbe
ereignisorientierte Simulation wie die Forschung: Auswahl abends nach RSI(2), Kapital je Order reserviert, ein nicht gefülltes
Limit belegt seinen Platz (kein Nachrücken), drei Ausführungsmodelle (opt/kons/streng), Kosten, ganze Stücke. Vorher wählte
depot() nur unter bereits gefüllten Signalen (Vorgriff). Liquiditätsfilter jetzt in US-Dollar umgerechnet (vorher
Landeswährung – z. B. GBp-Kurse in Pence zu großzügig). Ereignisse werden nur angehängt (book["log"]), abgeschlossene
Depot-Trades eingefroren (book["closed"]). KEINE echte Orderausführung: alle Füllungen sind Modellannahmen.
Jeder Lauf rechnet offene Signale aus den Tageskerzen neu (robust gegen Ausfälle), abgeschlossene werden eingefroren.
Gezählt werden nur Signale ab dem Starttag – keine Rückrechnung. Brutto-Rendite je Trade plus Netto mit angenommenen
Kosten (normal 0,05 % je Seite, Stress 0,25 % je Seite); die echten Kosten bei Scalable misst der Journal-Kosten-Check.
"""
from __future__ import annotations

from .mrsim import RULE_VERSION

import numpy as np
import pandas as pd

FILE = "mr_shadow.json"
RULES = ("A5", "W2", "ETF", "CTRL-L")
N_CTRL = 10                          # Live-Kontrolle: je Abend 10 zufällige Aufwärtstrend-Aktien mit gleichem Limit (W2-Audit)
SLOTS = 5
COST = {"normal": 0.0005, "stress": 0.0025}
# Learning Engine für die Schattentests: vorher erkennbare Merkmale je Signal (Stand Signaltag bzw. Kauf-Eröffnung)
FEAT = {"tief": "Fall der 3 Tage größer als 2 ATR", "extrem": "RSI(2) unter 5", "unruhig": "Tagesschwankung (ATR) über 4 %",
        "markt_rot": "Markt der Region unter der 200-Tage-Linie", "luecke": "Eröffnung am Kauftag mehr als 1 % unter dem Signal-Schluss"}
INDEX = {"us": "^GSPC", "europe": "^STOXX", "eu": "^STOXX"}
MIN_N, FDR_Q = 10, 0.10
MAX_DAY = 10                         # je Tag nur die 10 stärksten Aktien-Signale speichern (Depot kauft höchstens 5)
ETFS = ("XLK", "XLF", "XLV", "XLY", "XLP", "XLE", "XLI", "XLB", "XLU", "XLRE", "XLC")


def rsi2(c: pd.Series) -> pd.Series:
    from .indicators import rsi                    # dieselbe Wilder-RSI wie Scanner und Forschung
    return rsi(c, 2)


def signal_today(df: pd.DataFrame, rule: str, cur: str = "USD") -> dict | None:
    """Signal am letzten Schluss der Kursreihe? Rückgabe mit Signaltag und Vorrang, sonst None."""
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    if len(df) < 210:
        return None
    c = df["Close"]
    i = len(c) - 1
    if not c.iloc[i] > c.iloc[i - 199:i + 1].mean():
        return None
    r2 = float(rsi2(c).iloc[i])
    adv = 0.0
    if rule in ("A5", "CTRL-L"):
        if rule == "A5" and not (c.iloc[i] < c.iloc[i - 1] < c.iloc[i - 2] < c.iloc[i - 3]):
            return None
        vol = df["Volume"] if "Volume" in df else None
        from .mrsim import FX_USD
        adv = float((vol * c).iloc[i - 19:i + 1].mean()) * FX_USD.get(cur or "USD", 1.0) if vol is not None else 0.0
        if c.iloc[i] < 1 or adv < 5e6:
            return None
    elif rule == "ETF":
        if not r2 < 10:
            return None
    from .indicators import atr
    a = float(atr(df, 14).iloc[i])
    f = {"extrem": bool(r2 < 5)}
    if np.isfinite(a) and a > 0:
        f["tief"] = bool((c.iloc[i - 3] - c.iloc[i]) > 2 * a)
        f["unruhig"] = bool(a / c.iloc[i] > 0.04)
    sma200 = float(c.iloc[i - 199:i + 1].mean())
    return {"f": f, "d": str(df.index[i].date()), "rsi2": round(r2, 2), "close": round(float(c.iloc[i]), 4),
            "atr": round(a, 4) if np.isfinite(a) else None, "sma200": round(sma200, 4),
            "adv": round(adv, 0) if rule == "A5" else None,
            "lim": round(float(c.iloc[i] - 0.5 * a), 4) if np.isfinite(a) else None}


def replay(df: pd.DataFrame, d: str, lim: float | None = None) -> dict:
    """Trade ab Signaltag d nach Regel: Kauf nächste Eröffnung, Verkauf nach Schluss > 5-Tage-Linie (nächste Eröffnung), max. Tag 10."""
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    idx = df.index
    i = int(idx.searchsorted(pd.Timestamp(d), side="right") - 1)
    o, c = df["Open"].to_numpy(float), df["Close"].to_numpy(float)
    sma5 = df["Close"].rolling(5).mean().to_numpy(float)
    if i + 1 >= len(c):
        return {"res": "signal"}
    e, k0 = o[i + 1], i + 1
    gap = {"luecke": bool(o[k0] < c[i] * 0.99)}
    if lim is not None:                                # W2: Kauf-Limit nur am Tag nach dem Signal
        if not df["Low"].iloc[i + 1] <= lim:
            return {"res": "kein_kauf", "buy": str(idx[k0].date()), "f2": gap}
        e = min(e, lim)
    for day, k in enumerate(range(k0, len(c)), start=1):
        if day >= 10:                                  # wie die Engine: Zeitausstieg zum Schluss von Tag 10 vor dem Signal-Ausstieg
            return {**_done(e, c[k], idx[k0], idx[k], day, "zeit"), "f2": gap}
        if c[k] > sma5[k]:
            if k + 1 < len(c):
                return {**_done(e, o[k + 1], idx[k0], idx[k + 1], day + 1, "sma5"), "f2": gap}
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
        currency = {r["ticker"]: r.get("currency") or "USD" for r in rows}
        red = {}
        for reg, sym in INDEX.items():
            ix = (ctx or {}).get(sym)
            try:
                ci = ix["Close"].dropna()
                red[reg] = bool(ci.iloc[-1] < ci.iloc[-200:].mean()) if len(ci) >= 200 else None
            except Exception:
                red[reg] = None
        new = []
        for t, df in data.items():
            if region.get(t) not in ("us", "europe", "eu") or df is None:
                continue
            s = signal_today(df, "A5", currency.get(t, "USD"))
            if s and s["d"] >= book["start"]:
                s.update(cur=currency.get(t, "USD"), seen=today, v=RULE_VERSION)
                if red.get(region.get(t)) is not None:
                    s["f"]["markt_rot"] = red[region.get(t)]
                new.append((t, s))
        book["signals_today"] = len(new)
        for t, s in sorted(new, key=lambda x: x[1]["rsi2"])[:MAX_DAY]:   # Rangfolge wie im Depot: niedrigster RSI(2) zuerst
            items.setdefault(f"A5|{t}|{s['d']}", {"rule": "A5", "t": t, **s})
            if s.get("lim"):
                items.setdefault(f"W2|{t}|{s['d']}", {"rule": "W2", "t": t, **s})
        # Live-Kontrolle CTRL-L: zufällige Aufwärtstrend-Aktien (Grundfilter wie W2, ohne 3 Verlusttage), gleiches Limit.
        # Zufall fest aus dem Datum → reproduzierbar; nur Signale ab Start. Vergleich W2 − CTRL-L je Signal (Audit-Kriterium L2).
        import zlib
        pool = [t for t, df in data.items() if region.get(t) in ("us", "europe", "eu") and df is not None]
        rng = np.random.default_rng(zlib.crc32(today.encode()))
        picked = 0
        for t in rng.permutation(sorted(pool)):
            if picked >= N_CTRL:
                break
            s = signal_today(data[t], "CTRL-L", currency.get(t, "USD"))
            if s and s["d"] >= book["start"] and s.get("lim"):
                s.update(cur=currency.get(t, "USD"), seen=today, v=RULE_VERSION)
                items.setdefault(f"CTRL-L|{t}|{s['d']}", {"rule": "CTRL-L", "t": t, **s})
                picked += 1
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
        if it.get("res") == "kein_kauf":
            continue
        df = (ctx or {}).get(it["t"]) if it["rule"] == "ETF" else data.get(it["t"])
        if df is None:
            continue
        try:
            it.update(replay(df, it["d"], it.get("lim") if it["rule"] in ("W2", "CTRL-L") else None))
        except Exception as exc:
            print("Schattentest:", key, repr(exc)[:80])
    try:
        depot_sim(book, data)
    except Exception as exc:
        print("Schattentest-Depot:", repr(exc)[:120])
    book["updated"] = today
    return book


def depot_sim(book: dict, data: dict) -> None:
    """Depot je Regel und Ausführungsmodell mit backend/mrsim (identisch zur Forschung); Ereignisse nur anhängen."""
    from . import mrsim as S
    items = list((book.get("items") or {}).values())
    log, closed, dep = book.setdefault("log", []), book.setdefault("closed", {}), {}
    seen = {(e.get("rule"), e.get("m"), e.get("d"), e.get("ev"), e.get("t")) for e in log}
    for rule, models in (("A5", ("opt",)), ("W2", S.FILLS)):
        xs = [x for x in items if x["rule"] == rule and x["t"] in data and data[x["t"]] is not None]
        if not xs:
            continue
        px = {}
        for t in {x["t"] for x in xs}:
            cur = next((x.get("cur") for x in xs if x["t"] == t and x.get("cur")), "USD")
            px[t] = S.make_px(S.indicators(data[t], cur))
        sig = [{"t": x["t"], "d": pd.Timestamp(x["d"]), "rsi2": x["rsi2"], "lim": x.get("lim"), "adv": x.get("adv", 1e9)} for x in xs]
        cal = pd.DatetimeIndex(sorted({d for P in px.values() for d in P.idx if d >= pd.Timestamp(book["start"])}))
        for m in models:
            r = S.simulate(sig, px, rule, m, S.COSTS["basis"], cash0=10_000.0, calendar=cal)
            dep[f"{rule}|{m}"] = {"counts": r["counts"], **S.stats(r["equity"]), "open": r["open"],
                                  "trades": [[t["t"], t["sig"], t["exit"], t["ret"], t["gross"]] for t in r["trades"]]}
            for t in r["trades"]:
                closed.setdefault(f"{rule}|{m}|{t['t']}|{t['buy']}", t)                 # einmal geschrieben, nie geändert
            if m in ("opt", "kons"):
                for e in r["events"]:
                    if e["ev"] == "kein_platz":                   # steht in den Zählern – hält das Log klein
                        continue
                    k = (rule, m, e["d"], e["ev"], e["t"])
                    if k not in seen:
                        log.append({"rule": rule, "m": m, "logged": book.get("updated") or e["d"], **e})
                        seen.add(k)
    book["depot"] = dep


def depot(items: list[dict], slots: int = SLOTS) -> list[dict]:   # VERALTET (Vorgriff: wählt nur unter gefüllten Signalen) – nur für alte Tests
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


def learn(items: list[dict]) -> dict:
    """Was haben die Verlierer gemeinsam? Je Merkmal Ø Brutto mit/ohne, Welch-p, Benjamini-Hochberg. Nie automatische Regeländerung."""
    from .tradewhy import _bh, _pvalue
    done = [x for x in items if x.get("res") == "closed"]
    rows = []
    for k, label in FEAT.items():
        w = [x["gross"] for x in done if {**(x.get("f") or {}), **(x.get("f2") or {})}.get(k) is True]
        wo = [x["gross"] for x in done if {**(x.get("f") or {}), **(x.get("f2") or {})}.get(k) is False]
        r = {"k": k, "label": label, "n_with": len(w), "n_without": len(wo),
             "with": round(float(np.mean(w)), 5) if w else None, "without": round(float(np.mean(wo)), 5) if wo else None,
             "p": _pvalue(w, wo) if len(w) >= MIN_N and len(wo) >= MIN_N else None}
        rows.append(r)
    _bh(rows)
    for r in rows:
        if r["p"] is None:
            r["status"] = "zu wenig Fälle"
        elif r.get("q", 1) <= FDR_Q:
            r["status"] = "Filter-Kandidat" if r["with"] < r["without"] else "Verstärker-Kandidat"
        else:
            r["status"] = "kein klarer Unterschied"
    losers = sorted([x for x in done if x["gross"] < 0], key=lambda x: x.get("exit") or "", reverse=True)[:8]
    why = [{"t": x["t"], "exit": x.get("exit"), "gross": x["gross"],
            "f": [FEAT[k] for k, v in {**(x.get("f") or {}), **(x.get("f2") or {})}.items() if v is True and k in FEAT]}
           for x in losers]
    return {"features": rows, "losers": why, "n": len(done),
            "note": "Kandidaten sind Hinweise: Änderung der Regel nur nach eigenem Test und Freigabe"}


def summary(book: dict) -> dict:
    out = {"start": book.get("start"), "updated": book.get("updated")}
    items = list((book.get("items") or {}).values())
    for rule in RULES:
        xs = [x for x in items if x["rule"] == rule]
        if rule in ("A5", "W2"):                       # Depot-Auswahl aus der Ereignis-Simulation (kons. für W2)
            key = f"{rule}|{'kons' if rule == 'W2' else 'opt'}"
            took = {(t[0], t[1]) for t in ((book.get("depot") or {}).get(key) or {}).get("trades", [])}
            took |= {(t, (v.get("sig") or "")) for t, v in (((book.get("depot") or {}).get(key) or {}).get("open") or {}).items()}
            sel = [x for x in xs if (x["t"], x["d"]) in took]
        else:
            sel = xs
        done = [x for x in sel if x.get("res") == "closed"]
        m = lambda k: round(float(np.mean([x[k] for x in done])), 5) if done else None
        out[rule] = {"signals": len(xs), "taken": len(sel), "open": sum(x.get("res") == "open" for x in sel), "closed": len(done),
                     "gross": m("gross"), "net_normal": m("net_normal"), "net_stress": m("net_stress"),
                     "win": round(float(np.mean([x["gross"] > 0 for x in done])), 3) if done else None,
                     "days": round(float(np.mean([x["days"] for x in done])), 1) if done else None,
                     "sum_normal": round(float(np.sum([x["net_normal"] for x in done]) / SLOTS), 4) if done and rule != "ETF" else None,
                     "no_fill": sum(x.get("res") == "kein_kauf" for x in xs)}
        if rule != "ETF":
            out[rule]["learn"] = learn(sel)
            for k, v in (book.get("depot") or {}).items():
                if k.startswith(rule + "|"):
                    out[rule].setdefault("depot", {})[k.split("|")[1]] = {kk: v.get(kk) for kk in ("counts", "cagr", "dd", "end")}
    # Signal-Ebene (alle gespeicherten Signale, ohne Depotgrenze): W2 gegen Live-Kontrolle mit gleichem Limit
    def lvl(rule):
        d = [x for x in items if x["rule"] == rule and x.get("res") == "closed"]
        nf = sum(x.get("res") == "kein_kauf" for x in items if x["rule"] == rule)
        return {"n": len(d), "no_fill": nf, "gross": round(float(np.mean([x["gross"] for x in d])), 5) if d else None,
                "net_normal": round(float(np.mean([x["net_normal"] for x in d])), 5) if d else None}
    w, k = lvl("W2"), lvl("CTRL-L")
    out["vergleich"] = {"W2": w, "CTRL-L": k, "diff_net": round(w["net_normal"] - k["net_normal"], 5)
                        if w["net_normal"] is not None and k["net_normal"] is not None else None}
    return out
