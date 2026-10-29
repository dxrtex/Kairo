"""Studie Kurzfrist-Reversal (Phase 1b): Lohnt sich die erste Gegenbewegung nach einer Korrektur – und mit welchen Regeln?

Eingabe: die Signal-Dateien des Bilanz-Backtests (`python -m backend.bilanz --px-base …`). Jedes Ereignis bringt den
Kursverlauf ab dem Tag nach dem Signal mit (relativ zum Schlusskurs am Signaltag = 1,0), die Tiefs der 10 Tage davor,
ATR, EMA 20, Widerstände und Wochentage. Signale: Kairo-Treffer (hit), Fast-Treffer (fast), Trend-Rücksetzer (trend)
und zufällige Vergleichstage derselben Aktien (base).

Regeln – nur Wissen bis zum Signaltag, Tageskerzen, vorsichtig gerechnet:
- Einstieg „open“: Eröffnung am nächsten Handelstag. Kein Trade, wenn sie schon unter dem Stop liegt oder mehr als
  `late` ATR über dem Signal-Schluss (zu spät, Gegenbewegung schon gelaufen). „buystop“: Kauf, sobald das Hoch des
  Signaltags überschritten wird (innerhalb von 2 Tagen), zur Eröffnung, falls sie schon darüber liegt.
- Invalidierung = tiefstes Tief der letzten k Tage bis einschließlich Signaltag; Stop = Invalidierung − Puffer × ATR.
  Trade abgelehnt, wenn der Stop-Abstand größer als `maxd` ATR ist oder kleiner als 0,5 ATR.
- Stop: Eröffnet die Aktie darunter, wird zur Eröffnung verkauft (Kurslücke), sonst zum Stop. Stop und Ziel am selben
  Tag = Stop. Stop-Anpassungen (Break-even, Trailing) gelten erst ab dem Folgetag und nur nach oben.
- Ziele: R-Vielfache, EMA 20 vom Signaltag oder nächstes Hoch (Widerstand); Eröffnung darüber → Verkauf zur Eröffnung.
- Zeit: Verkauf zum Schluss des N-ten Handelstags. Wochenend-Regel: Verkauf zum Schluss des letzten Handelstags der Woche.
- Turbo: K.-o. = Einstieg × (1 − 1/Hebel); nur zulässig, wenn K.-o. ≤ Stop − `kob` ATR (sonst kleinerer Hebel).
  Eröffnet die Aktie unter dem K.-o., ist der Einsatz verloren.
- Kosten (netto): Ordergebühr 0,99 € je Order bei 2.000 € Basiswert-Exposure, Spread (Aktie 0,05 %, Turbo 0,15 %
  auf den Basiswert, je Runde), Finanzierung 5 % p. a. auf den finanzierten Teil je Kalendertag.

Ergebnis in R (Gewinn ÷ geplantes Risiko Einstieg − Stop). Lernen bis 2023, Prüfen 2024, echter Test ab 2025:
Parameter werden NUR im Lern-Zeitraum gewählt. Unsicherheit per Bootstrap über Handelstage (Signale häufen sich in
Ausverkäufen und sind dann korreliert).

    python -m backend.shortswing bilanz_part_*.json
"""

from __future__ import annotations

import itertools
import json
import os
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

from .config import ROOT

OUT = ROOT / "data" / "shortswing_study.json"
TRAIN_END, VAL_END = "2024-01-01", "2025-01-01"
EXPOSURE, FEE = 2000.0, 0.99
SPREAD = {"stock": 0.0005, "turbo": 0.0015}
FIN_PA = 0.05
MAX_BASE = 25000


def _period(d: str) -> str:
    return "train" if d < TRAIN_END else "val" if d < VAL_END else "test"


def _last_of_week(wd: list[int], j: int) -> bool:
    """Ist Tag j (Index in wd, wd[0] = Signaltag) der letzte Handelstag seiner Woche? Ohne Folgetag: unbekannt → nein."""
    return j + 1 < len(wd) and wd[j + 1] <= wd[j]


def _lvl(px: dict, spec: tuple, entry: float, atr: float) -> float | None:
    """Kursziel aus der Korrektur: ("hi",) = Hoch vor der Korrektur, ("fib", k) = Tief + k × (Hoch − Tief)
    (0,618 Retracement, 1,0 altes Hoch, 1,272 / 1,618 Extension). Nur wenn es mindestens 0,25 ATR über dem Kauf liegt."""
    H, L = px.get("H"), px.get("L")
    if not H or not L or H <= L:
        return None
    t = H if spec[0] == "hi" else L + spec[1] * (H - L)
    return t if t > entry + 0.25 * atr else None


def _ind_sig(px: dict, j: int, kind: str) -> bool:
    """Ausstiegssignale im Tageschart am Tag j (nur bis dahin bekannte Werte): RSI war ≥ 70 und dreht nach unten,
    MACD kreuzt die Signallinie nach unten (Histogramm wird negativ), rotes MBI-X; 2v3/3v3 = so viele davon in den letzten 3 Tagen."""
    rs, mh, rx = px.get("rsi") or [], px.get("mh") or [], px.get("rx") or []
    if j >= len(rs) or j >= len(mh) or j >= len(rx):
        return False
    def r_(k):
        return k >= 1 and max(rs[max(0, k - 5):k + 1]) >= 70 and rs[k] < rs[k - 1]
    def m_(k):
        prev = mh[k - 1] if k >= 1 else px.get("mh0", 0)
        return mh[k] < 0 <= prev
    def b_(k):
        return bool(rx[k])
    if kind == "rsi":
        return r_(j)
    if kind == "macd":
        return m_(j)
    if kind == "mbi":
        return b_(j)
    ks = range(max(0, j - 2), j + 1)
    n = any(r_(k) for k in ks) + any(m_(k) for k in ks) + any(b_(k) for k in ks)
    return n >= (2 if kind == "2v3" else 3)


def simulate(px: dict, r: dict) -> dict | None:
    o, h, l, c = px["o"], px["h"], px["l"], px["c"]
    wd = px.get("wd") or []
    atr = px["atr"]
    if not o or not atr:
        return None
    pl = px["pl"]
    inv = min(pl[-r["inv"]:]) if r["inv"] != "zone" else px["s"]
    stop0 = inv - r["buf"] * atr
    # Einstieg
    start = 0
    mode = r.get("entry", "open")
    if mode == "base":
        # Kauf IN der Seitwärtsphase (vor dem Ausbruch): sobald ck Tage eng laufen (Spanne ≤ cm × ATR) und die
        # Invalidierung hält, Kauf zur Eröffnung am Folgetag. lowhalf: nur wenn diese Eröffnung in der unteren Hälfte
        # der Basis liegt (nahe der Unterstützung). Stop = Tief der Basis − Puffer.
        k, m, wait = r.get("ck", 3), r.get("cm", 2.0), r.get("wait", 10)
        entry = None
        for j in range(min(wait, len(c) - 1)):
            if l[j] < inv:
                return {"skip": "failed"}
            if j < k - 1:
                continue
            hi, lo = max(h[j - k + 1:j + 1]), min(l[j - k + 1:j + 1])
            if r.get("calm") and px.get("calm") is not None and not (j < len(px["calm"]) and px["calm"][j]):
                continue                           # Basis noch unruhig → weiter warten
            if hi - lo <= m * atr:
                oj = o[j + 1]
                if oj > hi or oj <= lo:            # schon ausgebrochen bzw. durch die Basis gefallen
                    continue
                if r.get("lowhalf") and oj > (hi + lo) / 2:
                    continue
                entry, start, stop0 = oj, j + 1, lo - r["buf"] * atr
                break
        if entry is None:
            return {"skip": "nofill"}
    elif mode == "cons":
        # „Gummiband mit Bestätigung“: nach dem Signal abwarten, bis der Kurs ck Tage eng seitwärts läuft
        # (Spanne ≤ cm × ATR, kein Bruch der Invalidierung), dann Kauf beim Ausbruch über das Hoch dieser Phase
        # am Folgetag. Stop = Tief der Seitwärtsphase − Puffer. Jede Entscheidung nur mit Kursen bis zu diesem Tag.
        k, m, wait = r.get("ck", 3), r.get("cm", 2.0), r.get("wait", 10)
        entry = None
        for j in range(min(wait, len(c) - 1)):
            if l[j] < inv:                         # Signal gescheitert, bevor sich eine Basis gebildet hat
                return {"skip": "failed"}
            if j < k - 1:
                continue
            hi, lo = max(h[j - k + 1:j + 1]), min(l[j - k + 1:j + 1])
            if hi - lo <= m * atr and h[j + 1] >= hi:
                if o[j + 1] > hi + 0.5 * atr:      # Kurslücke weit über den Ausbruch – zu spät
                    return {"skip": "late"}
                entry, start, stop0 = max(o[j + 1], hi), j + 1, lo - r["buf"] * atr
                break
        if entry is None:
            return {"skip": "nofill"}
    elif mode == "open":
        entry = o[0]
        if entry > 1 + r.get("late", 0.5) * atr:
            return {"skip": "late"}
    else:                                          # Bestätigung: über das Hoch des Signaltags
        trig, entry = px["h0"], None
        for j in range(min(2, len(o))):
            if h[j] >= trig:
                entry, start = max(o[j], trig), j
                break
        if entry is None:
            return {"skip": "nofill"}
    if entry <= stop0:
        return {"skip": "below"}
    risk = entry - stop0
    if risk > r.get("maxd", 3.0) * atr:
        return {"skip": "wide"}
    if risk < 0.5 * atr:
        return {"skip": "tight"}
    R = lambda x: (x - entry) / risk
    tgt_kind = r.get("tgt")
    target = None
    if tgt_kind:
        if tgt_kind[0] == "R":
            target = entry + tgt_kind[1] * risk
        elif tgt_kind[0] == "ema20":
            target = px["e20"] if px["e20"] > entry + 0.25 * atr else None
        elif tgt_kind[0] == "tp1":
            tp = [x for x in (px.get("tp") or []) if x > entry + 0.25 * atr]
            target = tp[0] if tp and tp[0] <= entry + 4 * atr else entry + 1.5 * risk
        elif tgt_kind[0] in ("fib", "hi"):
            target = _lvl(px, tgt_kind, entry, atr)
    part = r.get("part")                           # (Anteil, R-Vielfaches) oder (Anteil, ("fib", k) / ("hi",))
    if part and isinstance(part[1], tuple):
        ptarget = _lvl(px, part[1], entry, atr)
    else:
        ptarget = entry + part[1] * risk if part else None
    # Hebel / K.-o.
    lev, ko = 1, None
    for L in sorted(r.get("levs", [1]), reverse=True):
        k = entry * (1 - 1 / L) if L > 1 else None
        if k is None or k <= stop0 - r.get("kob", 1.0) * atr:
            lev, ko = L, k
            break
    stop, pos, real, maxh, mfe, mae, orders = stop0, 1.0, 0.0, entry, 0.0, 0.0, 2
    path = []                                      # Stand in R zum Schluss jedes gehaltenen Tags (für den täglichen Depotwert)
    be_cost = (SPREAD["turbo" if lev > 1 else "stock"] + 2 * FEE / EXPOSURE) * entry
    hold = r["hold"]
    exit_, day, why = None, None, None
    if r.get("ema_x"):                             # EMA ab dem Signaltag fortschreiben (e20 = EMA 20 am Signaltag; andere Längen angenähert)
        ema_v = px.get("e20") or c[0]
        for jj in range(start):
            ema_v = ema_v + (c[jj] - ema_v) * 2 / (r["ema_x"] + 1)
    for j in range(start, len(c)):
        oj = o[j] if j > start else entry
        n_held = j - start + 1
        if ko is not None and oj <= ko:            # Kurslücke unter den K.-o.: Einsatz verloren
            exit_, day, why = "ko", n_held, "ko"
            break
        if oj <= stop:
            exit_, day, why = oj, n_held, "stop" if stop < entry else "be/trail"
            break
        if l[j] <= stop:
            exit_, day, why = stop, n_held, "stop" if stop < entry else "be/trail"
            mae = min(mae, R(l[j]))
            break
        mae = min(mae, R(l[j]))
        if ptarget and pos == 1.0 and h[j] >= ptarget:
            real += part[0] * R(max(oj, ptarget))
            pos -= part[0]
            orders += 1
            if r.get("be_after_part"):
                stop = max(stop, entry + be_cost)
        if target and h[j] >= target:
            exit_, day, why = max(oj, target), n_held, "ziel"
            break
        maxh = max(maxh, h[j])
        mfe = max(mfe, R(maxh))
        path.append(real + pos * R(c[j]))
        if n_held >= hold:
            exit_, day, why = c[j], n_held, "zeit"
            break
        if r.get("ind_x") and j + 1 < len(c):      # Indikator-Ausstieg im Tageschart (RSI/MACD/MBI), erst wenn der Trade „reif“ ist
            g = r.get("ind_gate")
            if (g is None or (g[0] == "day" and n_held >= g[1]) or (g[0] == "R" and mfe >= g[1])) and _ind_sig(px, j, r["ind_x"]):
                exit_, day, why = o[j + 1], n_held + 1, "ind"
                break
        if r.get("ema_x"):                         # Ausstieg: ab Tag ema_from Tagesschluss unter der EMA → Verkauf zur nächsten Eröffnung
            ema_v = ema_v + (c[j] - ema_v) * 2 / (r["ema_x"] + 1)
            if n_held >= r.get("ema_from", 10) and c[j] < ema_v and j + 1 < len(c):
                exit_, day, why = o[j + 1], n_held + 1, "ema"
                break
        if r.get("d5") is not None and n_held == r.get("d5_day", 5) and R(c[j]) < r["d5"]:   # keine Anschlussbewegung → raus
            exit_, day, why = c[j], n_held, "tag5"
            break
        if r.get("wkend") and _last_of_week(wd, j + 1):              # wd[0] = Signaltag → Tag j ist wd[j + 1]
            exit_, day, why = c[j], n_held, "wochenende"
            break
        # Anpassungen ab dem Folgetag (nur nach oben)
        if r.get("be") is not None and mfe >= r["be"]:
            stop = max(stop, entry + be_cost)
        if r.get("trail") and mfe >= r.get("trail_from", 1.0):
            stop = max(stop, maxh - r["trail"] * atr)
    if exit_ is None:
        return None                                # Verlauf zu kurz
    rp = risk / entry                              # Risiko in % des Einstiegs
    if exit_ == "ko":
        gross = -(1 / lev) / rp                    # ganzer Einsatz (Exposure / Hebel) verloren
    else:
        gross = real + pos * R(exit_)
    cal_days = day * 7 / 5
    cost = (SPREAD["turbo" if lev > 1 else "stock"] + orders * FEE / EXPOSURE
            + (FIN_PA * (1 - 1 / lev) * cal_days / 365 if lev > 1 else 0)) / rp
    path = path[:day - 1] + [gross]
    return {"r": gross, "net": gross - cost, "d": day, "x": why, "lev": lev, "mfe": mfe, "mae": mae, "rp": rp, "s": start,
            "e": entry, "sl": stop0, "path": [round(x, 3) for x in path], "orders": orders,
            "fee_r": orders * FEE / EXPOSURE / rp}


def _summ(rows: list[dict]) -> dict:
    if not rows:
        return {"n": 0}
    net = np.array([x["net"] for x in rows])
    gross = np.array([x["r"] for x in rows])
    d = np.array([x["d"] for x in rows])
    wins, losses = net[net > 0], net[net <= 0]
    xs = defaultdict(int)
    for x in rows:
        xs[x["x"]] += 1
    return {"n": len(rows), "net": round(float(net.mean()), 3), "gross": round(float(gross.mean()), 3),
            "win": round(float((net > 0).mean()), 3), "avg_win": round(float(wins.mean()), 2) if len(wins) else None,
            "avg_loss": round(float(losses.mean()), 2) if len(losses) else None,
            "pf": round(float(wins.sum() / -losses.sum()), 2) if len(losses) and losses.sum() < 0 else None,
            "days": round(float(d.mean()), 1), "per_day": round(float(net.mean() / d.mean()), 4),
            "mfe": round(float(np.mean([x["mfe"] for x in rows])), 2), "mae": round(float(np.mean([x["mae"] for x in rows])), 2),
            "exits": {k: round(v / len(rows), 3) for k, v in sorted(xs.items())},
            "rp": round(float(np.median([x["rp"] for x in rows])), 4)}


def _boot(rows: list[tuple[str, float]], n: int = 400, seed: int = 3) -> list[float] | None:
    """95-%-Intervall des mittleren Netto-R, Bootstrap über Handelstage (Cluster)."""
    if len(rows) < 30:
        return None
    by = defaultdict(list)
    for d, v in rows:
        by[d].append(v)
    days = list(by)
    rnd = random.Random(seed)
    means = []
    for _ in range(n):
        s = c = 0.0
        for _ in range(len(days)):
            v = by[days[rnd.randrange(len(days))]]
            s += sum(v)
            c += len(v)
        means.append(s / c)
    return [round(float(np.percentile(means, 2.5)), 3), round(float(np.percentile(means, 97.5)), 3)]


def _portfolio(trades: list[tuple[str, float, int, float]], risk: float = 0.005, heat: float = 0.03) -> dict:
    """Depot-Simulation: je Trade `risk` des Depots, höchstens `heat` offenes Risiko; chronologisch, Ergebnis netto."""
    if not trades:
        return {}
    eq, peak, mdd, open_ = 1.0, 1.0, 0.0, []
    taken = 0
    import datetime as dt
    # Reihenfolge innerhalb eines Tages zufällig (fest gesät) – NICHT nach Ergebnis sortieren (sonst Verzerrung)
    rnd = random.Random(7)
    trades = sorted(trades, key=lambda t: (t[0], rnd.random()))
    for d, net, days, _ in trades:
        t0 = dt.date.fromisoformat(d)
        still = []
        for end, pnl in open_:
            if end <= t0:
                eq *= 1 + pnl
                peak = max(peak, eq)
                mdd = max(mdd, 1 - eq / peak)
            else:
                still.append((end, pnl))
        open_ = still
        if len(open_) * risk + risk > heat:
            continue
        taken += 1
        open_.append((t0 + dt.timedelta(days=int(days * 7 / 5) + 1), risk * net))
    for _, pnl in open_:
        eq *= 1 + pnl
        peak = max(peak, eq)
        mdd = max(mdd, 1 - eq / peak)
    years = max(0.5, (dt.date.fromisoformat(max(t[0] for t in trades)) - dt.date.fromisoformat(min(t[0] for t in trades))).days / 365)
    return {"trades": taken, "end": round(eq, 3), "cagr": round(eq ** (1 / years) - 1, 3), "mdd": round(mdd, 3)}


def run_rule(events: list[dict], rule: dict, ci: bool = True) -> dict:
    out = {"skip": defaultdict(int)}
    rows = defaultdict(list)
    for e in events:
        if len(e["px"]["c"]) < rule["hold"] + (rule.get("wait", 10) if rule.get("entry") in ("cons", "base") else 0):      # Zeitfenster noch nicht vollständig (jüngste Signale) – sonst Verzerrung
            continue
        s = simulate(e["px"], rule)
        if s is None:
            continue
        if "skip" in s:
            out["skip"][s["skip"]] += 1
            continue
        s["date"] = e["d"]
        rows[_period(e["d"])].append(s)
    res = {p: _summ(v) for p, v in rows.items()}
    res["all"] = _summ([x for v in rows.values() for x in v])
    if ci:
        res["ci_test"] = _boot([(x["date"], x["net"]) for x in rows.get("test", [])])
        res["ci_all"] = _boot([(x["date"], x["net"]) for v in rows.values() for x in v])
    res["skip"] = dict(out["skip"])
    res["_rows"] = rows
    return res


def _key(rule: dict) -> str:
    return json.dumps({k: v for k, v in rule.items() if k != "levs"}, sort_keys=True)


def stage(events: list[dict], rules: list[dict], min_n: int = 100) -> list[tuple[dict, dict]]:
    out = []
    for r in rules:
        res = run_rule(events, r, ci=False)
        if (res.get("train") or {}).get("n", 0) >= min_n:
            out.append((r, res))
    out.sort(key=lambda x: -x[1]["train"]["net"])
    for r, res in out[:8]:                         # Unsicherheit nur für die besten (Rechenzeit)
        res["ci_test"] = _boot([(x["date"], x["net"]) for x in res["_rows"].get("test", [])])
        res["ci_all"] = _boot([(x["date"], x["net"]) for v in res["_rows"].values() for x in v])
    return out


def _strip(res: dict) -> dict:
    return {k: v for k, v in res.items() if k != "_rows"}


def _market() -> dict:
    """Marktlage je Handelstag – mit Wiederholung (Yahoo/SQLite-Cache gelegentlich gesperrt)."""
    import time
    for attempt in range(4):
        out = _market_once()
        if out:
            return out
        time.sleep(5 * (attempt + 1))
    raise SystemExit("Marktdaten (S&P 500/VIX) nicht ladbar – Auswertung ohne Marktlage wäre wertlos")


def _market_once() -> dict:
    """Marktlage je Handelstag: S&P 500 über EMA 200 / EMA 50, VIX. Leer, wenn keine Daten."""
    try:
        from .data_provider import YFinanceProvider
        from .indicators import ema
        h = YFinanceProvider().history(["^GSPC", "^VIX"], "12y")
        spx, vix = h["^GSPC"]["Close"], h["^VIX"]["Close"]
        e200, e50 = ema(spx, 200), ema(spx, 50)
        out = {}
        for d in spx.index:
            v = vix.get(d)
            out[str(d.date())] = {"a200": bool(spx[d] > e200[d]) if e200[d] == e200[d] else None,
                                  "a50": bool(spx[d] > e50[d]) if e50[d] == e50[d] else None,
                                  "vix": float(v) if v is not None and v == v else None}
        return out
    except Exception as exc:                       # Studie läuft auch ohne Marktdaten
        print("Marktdaten fehlen:", repr(exc)[:120])
        return {}


# calm: ein Basis-Tag zählt nur, wenn er ruhig ist (px["calm"], scanner.calm_days) – Forschung 28./29.10.2026
QRULE = dict(entry="base", ck=5, cm=1.5, lowhalf=False, wait=10, inv=10, buf=0.25, maxd=3.0, tgt=None, wkend=False, levs=[1], calm=True)


def _quality(sets: dict) -> dict:
    mk = _market()
    out = {"market_days": len(mk)}
    for k in ("hit", "fast"):
        es = sets.get(k) or []
        res_k = {}
        for hold in (7, 10, 20):
            rule = {**QRULE, "hold": hold}
            rows = []
            for e in es:
                if len(e["px"]["c"]) < hold + 10:
                    continue
                sm = simulate(e["px"], rule)
                if sm and "skip" not in sm:
                    rows.append((e, sm))
            train = [(e, sm) for e, sm in rows if _period(e["d"]) == "train"]
            feats = {
                "markt_sp500_ueber_ema200": lambda e: (mk.get(e["d"]) or {}).get("a200"),
                "markt_sp500_ueber_ema50": lambda e: (mk.get(e["d"]) or {}).get("a50"),
                "vix": lambda e: None if (mk.get(e["d"]) or {}).get("vix") is None else
                       ("< 18" if mk[e["d"]]["vix"] < 18 else "18–25" if mk[e["d"]]["vix"] < 25 else "≥ 25"),
                "score": lambda e: None if k != "hit" else ("80+" if e.get("score", 0) >= 80 else "70–79" if e["score"] >= 70
                                                           else "60–69" if e["score"] >= 60 else "< 60"),
                "divergenz": lambda e: e.get("div") or "keine",
                "zone": lambda e: e.get("zone"),
                "earnings_5T": lambda e: bool(e.get("earn")),
                "kriterien": lambda e: (e.get("f") or {}).get("met"),
                "crv": lambda e: None if not e.get("crv") else ("≥ 3" if e["crv"] >= 3 else "2–3" if e["crv"] >= 2 else "< 2"),
            }
            for name in ("dd", "atrp", "vol", "rsi", "e200", "e50"):        # Quintile (Grenzen nur aus dem Lern-Zeitraum)
                vals = sorted(x for x in ((e.get("f") or {}).get(name) for e, _ in train) if x is not None)
                if len(vals) >= 50:
                    qs = [vals[int(len(vals) * q)] for q in (0.2, 0.4, 0.6, 0.8)]
                    feats[name] = (lambda nm, qs: lambda e: None if (e.get("f") or {}).get(nm) is None else
                                   f"Q{1 + sum(e['f'][nm] > q for q in qs)} ({'≤' if True else ''}{qs[min(3, sum(e['f'][nm] > q for q in qs))]:.3g})")(name, qs)
            tab = {}
            for name, fn in feats.items():
                groups = defaultdict(lambda: defaultdict(list))
                for e, sm in rows:
                    try:
                        g = fn(e)
                    except Exception:
                        g = None
                    if g is None:
                        continue
                    groups[str(g)][_period(e["d"])].append(sm["net"])
                tab[name] = {g: {p: {"n": len(v), "net": round(float(np.mean(v)), 3)} for p, v in sorted(per.items())}
                             for g, per in sorted(groups.items())}
            res_k[hold] = {"n": len(rows), "all": round(float(np.mean([sm["net"] for _, sm in rows])), 3) if rows else None, "by": tab}
        out[k] = res_k
    return out


def _regime(mk: dict, d: str) -> str | None:
    """Marktampel wie in der App: weak = S&P 500 unter EMA 200 oder VIX ≥ 25; mixed = unter EMA 50 oder VIX ≥ 20; sonst strong."""
    m = mk.get(d)
    if not m or m.get("a200") is None:
        return None
    v = m.get("vix")
    if not m["a200"] or (v is not None and v >= 25):
        return "weak"
    if not m.get("a50") or (v is not None and v >= 20):
        return "mixed"
    return "strong"


def _depot(trades: list[tuple], start: float = 3000.0, max_open: int = 3, seed: int = 11) -> dict:
    """Depot mit Startkapital, höchstens max_open Trades gleichzeitig, Risiko je Trade in % des aktuellen Depots.

    trades: (Kaufdatum ISO, Netto-R, Handelstage gehalten, Risiko-Anteil). Reihenfolge innerhalb eines Tages zufällig
    (fest gesät), nie nach Ergebnis. Gewinne/Verluste werden beim Verkauf gebucht.
    """
    import datetime as dt
    if not trades:
        return {}
    rnd = random.Random(seed)
    trades = sorted(trades, key=lambda t: (t[0], -(t[4] if len(t) > 4 else 0), rnd.random()))
    eq, peak, mdd, open_, taken, by_year, eq_year = start, start, 0.0, [], 0, {}, {}
    def close_until(t0):
        nonlocal eq, peak, mdd, open_
        keep = []
        for end, amt in sorted(open_):
            if end <= t0:
                eq = max(0.0, eq + amt)                 # Totalverlust: Konto bei 0, keine neuen Trades mehr
                peak = max(peak, eq)
                mdd = max(mdd, 1 - eq / peak)
            else:
                keep.append((end, amt))
        open_ = keep
    for d, net, days, rk, *_ in trades:
        t0 = dt.date.fromisoformat(d)
        close_until(t0)
        y = d[:4]
        eq_year.setdefault(y, eq)
        if len(open_) >= max_open or eq <= 0:
            continue
        taken += 1
        by_year[y] = by_year.get(y, 0) + 1
        open_.append((t0 + dt.timedelta(days=int(days * 7 / 5) + 1), eq * rk * net))
    close_until(dt.date(2100, 1, 1))
    ys = sorted(eq_year)
    yr = {y: round((eq_year[ys[i + 1]] if i + 1 < len(ys) else eq) / eq_year[y] - 1, 3) if eq_year[y] > 0 else -1.0
          for i, y in enumerate(ys)}
    span = max(0.5, (dt.date.fromisoformat(trades[-1][0]) - dt.date.fromisoformat(trades[0][0])).days / 365)
    return {"trades": taken, "end_eur": round(eq), "cagr": round((eq / start) ** (1 / span) - 1, 3) if eq > 0 else -1.0, "mdd": round(mdd, 3),
            "years": yr, "per_year": by_year}


def _combo(sets: dict) -> dict:
    """Welche Kombination aus Setup, Haltedauer, Marktlage und Risiko bringt am meisten – als ein Depot mit 3.000 €."""
    import datetime as dt
    mk = _market()
    out = {"market_days": len(mk)}
    sims = {}                                       # (Setup, Haltedauer) → Liste (Event, Ergebnis)
    for k in ("hit", "fast", "trend", "top"):
        for hold in (5, 10, 20):
            rule = {**QRULE, "hold": hold, **({"ck": 3, "cm": 2.5} if k in ("trend", "top") else {})}
            rows = []
            for e in sets.get(k) or []:
                if len(e["px"]["c"]) < hold + 10:
                    continue
                sm = simulate(e["px"], rule)
                if sm and "skip" not in sm:
                    d0 = dt.date.fromisoformat(e["d"])
                    rows.append((e, sm, str(d0 + dt.timedelta(days=int((sm.get("s", 0) + 1) * 7 / 5)))))
            sims[(k, hold)] = rows
    # 1) Ergebnis je Trade nach Marktlage (Netto-R) – vor allem: wie laufen Trend-Rücksetzer im gesunden Markt?
    tab = {}
    for (k, hold), rows in sims.items():
        g = defaultdict(lambda: defaultdict(list))
        for e, sm, _ in rows:
            rg = _regime(mk, e["d"])
            if rg:
                g[rg][_period(e["d"])].append(sm["net"])
        tab[f"{k} {hold}T"] = {rg: {p: {"n": len(v), "net": round(float(np.mean(v)), 3)} for p, v in sorted(per.items())}
                               for rg, per in sorted(g.items())}
    out["by_regime"] = tab
    # 2) Strategien als Depot. plan: Marktlage → Liste (Setup, Haltedauer, Risiko)
    def depot(plan, seeds=25):
        tr = []
        for rg_key, legs in plan.items():
            for k, hold, rk in legs:
                for e, sm, d_in in sims[(k, hold)]:
                    rg = _regime(mk, e["d"])
                    if rg is None or (rg_key != "all" and rg != rg_key):
                        continue
                    tr.append((d_in, sm["net"], sm["d"], rk))
        runs = [_depot(tr, seed=sd) for sd in range(seeds)]
        cg = sorted(x["cagr"] for x in runs)
        md = sorted(x["mdd"] for x in runs)
        ys = sorted({y for x in runs for y in x["years"]})
        return {"cagr_median": cg[len(cg) // 2], "cagr_p10": cg[len(cg) // 10], "cagr_p90": cg[len(cg) * 9 // 10],
                "mdd_median": md[len(md) // 2], "mdd_p90": md[len(md) * 9 // 10],
                "end_median": sorted(x["end_eur"] for x in runs)[len(runs) // 2], "trades": runs[0]["trades"],
                "years_median": {y: sorted(x["years"].get(y, 0) for x in runs)[len(runs) // 2] for y in ys}}
    hf = lambda h, rk: [("hit", h, rk), ("fast", h, rk)]
    strategies = {
        "A jetzt: Treffer+Fast, 10 T, 1 %": {"all": hf(10, 0.01)},
        "B Treffer+Fast, 20 T, 1 %": {"all": hf(20, 0.01)},
        "C nur Treffer, 20 T, 1 %": {"all": [("hit", 20, 0.01)]},
        "D Trend-Rücksetzer, 20 T, 1 %": {"all": [("trend", 20, 0.01)]},
        "E Trend-Rücksetzer, 10 T, 1 %": {"all": [("trend", 10, 0.01)]},
        "F Ampel: Ausverkauf Treffer+Fast 20 T 1,5 % · sonst Trend 20 T 1 %":
            {"weak": hf(20, 0.015), "mixed": [("trend", 20, 0.01)], "strong": [("trend", 20, 0.01)]},
        "G Ampel: Ausverkauf Treffer+Fast 20 T 1,5 % · gelb Treffer 20 T 1 % · grau Trend 20 T 1 %":
            {"weak": hf(20, 0.015), "mixed": [("hit", 20, 0.01)], "strong": [("trend", 20, 0.01)]},
        "H Ampel: Ausverkauf Treffer+Fast 20 T 1,5 % · sonst Trend 10 T 1 %":
            {"weak": hf(20, 0.015), "mixed": [("trend", 10, 0.01)], "strong": [("trend", 10, 0.01)]},
        "I Ampel: nur im Ausverkauf Treffer+Fast 20 T 1,5 %, sonst Pause": {"weak": hf(20, 0.015)},
        "J Ampel wie F, aber überall + Trend 20 T": {"weak": hf(20, 0.015) + [("trend", 20, 0.01)],
                                                    "mixed": [("trend", 20, 0.01)] + hf(20, 0.0075), "strong": [("trend", 20, 0.01)]},
        "K wie F mit 1 % im Ausverkauf": {"weak": hf(20, 0.01), "mixed": [("trend", 20, 0.01)], "strong": [("trend", 20, 0.01)]},
        "L Ausverkauf Treffer+Fast 20 T 1,5 % · gelb Pause · grau Trend 20 T 1 %": {"weak": hf(20, 0.015), "strong": [("trend", 20, 0.01)]},
        "M Ausverkauf nur Treffer 20 T 1,5 % · sonst Trend 20 T 1 %": {"weak": [("hit", 20, 0.015)], "mixed": [("trend", 20, 0.01)], "strong": [("trend", 20, 0.01)]},
        "N Treffer 20 T + Trend 20 T, überall 1 %": {"all": [("hit", 20, 0.01), ("trend", 20, 0.01)]},
        "P nur Treffer 20 T: Ausverkauf 1,5 %, sonst 1 %": {"weak": [("hit", 20, 0.015)], "mixed": [("hit", 20, 0.01)], "strong": [("hit", 20, 0.01)]},
        "Q nur Treffer 20 T: Ausverkauf 1,5 %, sonst 0,5 %": {"weak": [("hit", 20, 0.015)], "mixed": [("hit", 20, 0.005)], "strong": [("hit", 20, 0.005)]},
        "R nur Treffer 20 T: Ausverkauf 2 %, sonst 1 %": {"weak": [("hit", 20, 0.02)], "mixed": [("hit", 20, 0.01)], "strong": [("hit", 20, 0.01)]},
        "S nur Treffer 20 T: Ausverkauf + grau 1 %, gelb Pause": {"weak": [("hit", 20, 0.01)], "strong": [("hit", 20, 0.01)]},
        "T nur Treffer 10 T, 1 %": {"all": [("hit", 10, 0.01)]},
        "O Ausverkauf Treffer+Fast+Trend 20 T 1,5 % · sonst Trend 20 T 1 %": {"weak": hf(20, 0.015) + [("trend", 20, 0.015)], "mixed": [("trend", 20, 0.01)], "strong": [("trend", 20, 0.01)]},
    }
    out["depot"] = {name: depot(plan) for name, plan in strategies.items()}
    # 3) Haltedauer 20/30/40 × gleichzeitige Trades 3/4/5 – nur Kairo-Treffer, Risiko 2 % im Ausverkauf, sonst 1 %.
    #    Fair: dieselben Signale für alle Haltedauern (nur solche mit ≥ 50 Kerzen Verlauf).
    fair = [e for e in sets.get("hit") or [] if len(e["px"]["c"]) >= 50]
    hs = {}
    for hold in (20, 30, 40):
        rule = {**QRULE, "hold": hold}
        rows = []
        for e in fair:
            sm = simulate(e["px"], rule)
            if sm and "skip" not in sm:
                d0 = dt.date.fromisoformat(e["d"])
                rows.append((e, sm, str(d0 + dt.timedelta(days=int((sm.get("s", 0) + 1) * 7 / 5)))))
        hs[hold] = rows
    per_trade, grid = {}, {}
    for hold, rows in hs.items():
        g = defaultdict(lambda: defaultdict(list))
        for e, sm, _ in rows:
            g[_regime(mk, e["d"]) or "?"][_period(e["d"])].append(sm["net"])
        per_trade[f"{hold}T"] = {rg: {p: {"n": len(v), "net": round(float(np.mean(v)), 3)} for p, v in sorted(per.items())}
                                 for rg, per in sorted(g.items())}
        tr = [(d_in, sm["net"], sm["d"], 0.02 if _regime(mk, e["d"]) == "weak" else 0.01)
              for e, sm, d_in in rows if _regime(mk, e["d"])]
        for mo in (3, 4, 5):
            runs = [_depot(tr, max_open=mo, seed=sd) for sd in range(25)]
            cg, md = sorted(x["cagr"] for x in runs), sorted(x["mdd"] for x in runs)
            grid[f"{hold}T · {mo} gleichzeitig"] = {"cagr_median": cg[12], "cagr_p10": cg[2], "cagr_p90": cg[22],
                                                    "mdd_median": md[12], "mdd_p90": md[22], "end_median": sorted(x["end_eur"] for x in runs)[12],
                                                    "trades": runs[0]["trades"]}
    out["hold_slots"] = {"signals": len(fair), "per_trade": per_trade, "depot": grid}
    # 4) Feinschliff der Siegerstrategie (nur Treffer, 20 T): Risiko im Ausverkauf, Plätze, Auswahl bei zu vielen Signalen
    rows20 = hs.get(20) or []
    prios = {
        "zufällig": lambda e: 0,
        "klassische Divergenz zuerst": lambda e: 1 if e.get("div") == "klassisch" else 0,
        "höchster Score zuerst": lambda e: e.get("score") or 0,
        "geringste Schwankung zuerst": lambda e: -((e.get("f") or {}).get("atrp") or 1),
        "tiefster Rücksetzer zuerst": lambda e: (e.get("f") or {}).get("dd") or 0,
        "Support-Zone zuerst": lambda e: 1 if e.get("zone") == "Support" else 0,
    }
    fine = {}
    def run(weak_rk, other_rk, slots, prio, hold=20, keep=lambda e: True):
        tr = [(d_in, sm["net"], sm["d"], weak_rk if _regime(mk, e["d"]) == "weak" else other_rk, prio(e))
              for e, sm, d_in in (hs.get(hold) or []) if _regime(mk, e["d"]) and keep(e)]
        runs = [_depot(tr, max_open=slots, seed=sd) for sd in range(25)]
        cg, md = sorted(x["cagr"] for x in runs), sorted(x["mdd"] for x in runs)
        return {"cagr_median": cg[12], "cagr_p10": cg[2], "cagr_p90": cg[22], "mdd_median": md[12], "mdd_p90": md[22],
                "end_median": sorted(x["end_eur"] for x in runs)[12], "trades": runs[0]["trades"],
                "years_median": {y: sorted(x["years"].get(y, 0) for x in runs)[12] for y in sorted({y for x in runs for y in x["years"]})}}
    for wr in (0.015, 0.02, 0.025, 0.03):
        fine[f"Risiko Ausverkauf {wr:.1%} · 5 Plätze"] = run(wr, 0.01, 5, prios["zufällig"])
    for sl in (5, 6, 8):
        fine[f"2 % / 1 % · {sl} Plätze"] = run(0.02, 0.01, sl, prios["zufällig"])
    for name, pr in prios.items():
        fine[f"2 % / 1 % · 5 Plätze · {name}"] = run(0.02, 0.01, 5, pr)
    # 5) Kombinationen mit der Siegerregel „ruhigste zuerst“: Haltedauer × Plätze × Risiko, nur ruhige Treffer
    calm = prios["geringste Schwankung zuerst"]
    atrp = lambda e: (e.get("f") or {}).get("atrp") or 1
    for hold in (20, 30, 40):
        for sl in (4, 5, 6, 8):
            fine[f"ruhigste zuerst · {hold} T · {sl} Plätze · 2 %/1 %"] = run(0.02, 0.01, sl, calm, hold)
    for wr in (0.015, 0.025, 0.03):
        fine[f"ruhigste zuerst · 20 T · 5 Plätze · {wr:.1%}/1 %"] = run(wr, 0.01, 5, calm)
    for cap in (0.025, 0.03, 0.035, 0.04):
        fine[f"ruhigste zuerst · 20 T · 5 Plätze · nur ATR < {cap:.1%}"] = run(0.02, 0.01, 5, calm, 20, lambda e, c=cap: atrp(e) < c)
    out["fine"] = fine
    return out



def _pnl(p: dict, fee_eur: float | None) -> float:
    """Ergebnis eines Trades in Euro. fee_eur None = alte Rechnung (Gebühr anteilig auf 2.000 € Position, steckt in net)."""
    sm = p["sm"]
    return p["amt"] * sm["net"] if fee_eur is None else p["amt"] * (sm["net"] + sm["fee_r"]) - sm["orders"] * fee_eur


def _depot_real(trades: list[dict], start: float = 3000.0, max_open: int = 5, seed: int = 11, fee_eur: float = 0.99,
                mtm: bool = True, series: dict | None = None) -> dict:
    """Depot wie in der App, aber ehrlicher gerechnet:
    - Gebühr in Euro je Order (statt anteilig auf 2.000 € Position): bei kleinem Depot ein großer Teil des Risikos.
    - Depotwert TÄGLICH inklusive Buchverlusten offener Trades (größter Rückgang nicht nur bei Verkäufen).
    trades: {"d": Kaufdatum, "sm": simulate-Ergebnis, "rk": Risiko-Anteil, "prio": Auswahl (größer = zuerst)}."""
    import datetime as dt
    if not trades:
        return {}
    rnd = random.Random(seed)
    trades = sorted(trades, key=lambda t: (t["d"], -t.get("prio", 0), rnd.random()))
    by_day = defaultdict(list)
    for t in trades:
        by_day[t["d"]].append(t)
    day = dt.date.fromisoformat(trades[0]["d"])
    end = dt.date.fromisoformat(trades[-1]["d"]) + dt.timedelta(days=60)
    eq, peak, mdd, mdd_real, peak_real, open_, taken = start, start, 0.0, 0.0, start, [], 0
    year0, years = {}, {}
    while day <= end:
        ds = day.isoformat()
        keep = []
        for p in open_:                                      # Verkäufe buchen
            if p["end"] <= day:
                eq = max(0.0, eq + _pnl(p, fee_eur))
                peak_real = max(peak_real, eq)
                mdd_real = max(mdd_real, 1 - eq / peak_real if peak_real else 0)
            else:
                keep.append(p)
        open_ = keep
        year0.setdefault(ds[:4], eq)
        for t in by_day.get(ds, []):                        # Käufe
            if len(open_) >= max_open or eq <= 0:
                continue
            amt, sm = eq * t["rk"], t["sm"]
            if t.get("var"):                                 # kleinster Hebel, dessen Einsatz ins freie Kapital passt
                free = eq - sum(p["stake"] for p in open_)
                sm = None
                for L in sorted(t["var"]):
                    cand = t["var"][L]
                    if amt / cand["rp"] / cand["lev"] <= free:
                        sm = cand
                        break
                if sm is None:
                    continue
            taken += 1
            n = sm["d"]
            open_.append({"start": day, "end": day + dt.timedelta(days=int(n * 7 / 5) + 1), "amt": amt, "sm": sm,
                          "stake": amt / sm["rp"] / sm["lev"]})
        if mtm and day.weekday() < 5:                        # täglicher Depotwert mit offenen Trades
            val = eq
            for p in open_:
                k = min(len(p["sm"]["path"]) - 1, int((day - p["start"]).days * 5 / 7))
                val += p["amt"] * p["sm"]["path"][max(0, k)]
            peak = max(peak, val)
            mdd = max(mdd, 1 - val / peak if peak else 0)
            if series is not None:
                series[ds] = round(val, 2)
        day += dt.timedelta(days=1)
    for p in open_:
        eq = max(0.0, eq + _pnl(p, fee_eur))
    ys = sorted(year0)
    for i, y in enumerate(ys):
        nxt = year0[ys[i + 1]] if i + 1 < len(ys) else eq
        years[y] = round(nxt / year0[y] - 1, 3) if year0[y] > 0 else -1.0
    span = max(0.5, (dt.date.fromisoformat(trades[-1]["d"]) - dt.date.fromisoformat(trades[0]["d"])).days / 365)
    return {"trades": taken, "end": round(eq), "cagr": round((eq / start) ** (1 / span) - 1, 3) if eq > 0 else -1.0,
            "mdd_daily": round(mdd, 3), "mdd_closed": round(mdd_real, 3), "years": years}


def _truth(sets: dict) -> dict:
    """Wahrheits-Test der Strategie (Phase 1): Wie viel vom Backtest-Ergebnis ist echt?
    1) Bringen Kairo-Treffer mehr als ZUFALLSTAGE derselben Aktien mit exakt denselben Regeln?
    2) Echte Kosten: Gebühr je Order in Euro, Turbo mit Finanzierung/Spread/K.-o. bei Kurslücken.
    3) Größter Rückgang mit täglichem Depotwert (inkl. Buchverluste).
    4) Walk-forward: Auswahlregel/Haltedauer/Plätze nur auf 2017–2023 wählen, unverändert auf 2024–2026 prüfen.
    5) Robustheit: Ergebnis ohne das beste Jahr."""
    import datetime as dt
    mk = _market()
    out = {"market_days": len(mk)}
    rules = {"aktie": {**QRULE, "levs": [1]}, "turbo": {**QRULE, "levs": [10, 5, 3, 1], "kob": 1.0}}
    sims = {}
    for k in ("hit", "fast", "base"):
        for prod, rule0 in rules.items():
            for hold in (10, 20, 30):
                rule = {**rule0, "hold": hold}
                rows = []
                for e in sets.get(k) or []:
                    if len(e["px"]["c"]) < hold + rule["wait"]:
                        continue
                    sm = simulate(e["px"], rule)
                    if sm and "skip" not in sm:
                        d0 = dt.date.fromisoformat(e["d"])
                        rows.append({"e": e, "sm": sm, "d": str(d0 + dt.timedelta(days=int((sm["s"] + 1) * 7 / 5))),
                                     "rg": _regime(mk, e["d"])})
                sims[(k, prod, hold)] = rows
    print("Wahrheits-Test: Simulationen fertig", {f"{a}/{b}/{c}": len(v) for (a, b, c), v in sims.items()}, flush=True)
    # 1) Je Trade: Treffer gegen Zufallstage, gleiche Regeln (netto in R, Studien-Kosten)
    per = {}
    for (k, prod, hold), rows in sims.items():
        g = defaultdict(lambda: defaultdict(list))
        for x in rows:
            g[x["rg"] or "?"][_period(x["e"]["d"])].append(x["sm"]["net"])
            g["alle"][_period(x["e"]["d"])].append(x["sm"]["net"])
            g["alle"]["all"].append(x["sm"]["net"])
        per[f"{k} {prod} {hold}T"] = {rg: {p: {"n": len(v), "net": round(float(np.mean(v)), 3),
                                               "win": round(float(np.mean([z > 0 for z in v])), 3)} for p, v in sorted(pp.items())}
                                      for rg, pp in sorted(g.items())}
        allr = [(x["e"]["d"], x["sm"]["net"]) for x in rows]
        per[f"{k} {prod} {hold}T"]["ci_all"] = _boot(allr)
    out["per_trade"] = per
    calm = lambda e: -((e.get("f") or {}).get("atrp") or 1)
    prios = {"ruhigste zuerst": calm, "zufällig": lambda e: 0, "höchster Score": lambda e: e.get("score") or 0,
             "tiefster Rücksetzer": lambda e: (e.get("f") or {}).get("dd") or 0}
    def trades(k, prod, hold, prio, weak=0.02, other=0.01, mixed=None, lo=None, hi=None):
        tr = []
        for x in sims.get((k, prod, hold)) or []:
            if not x["rg"] or (lo and x["d"] < lo) or (hi and x["d"] >= hi):
                continue
            rk = weak if x["rg"] == "weak" else (mixed if (mixed is not None and x["rg"] == "mixed") else other)
            if rk <= 0:
                continue
            tr.append({"d": x["d"], "sm": x["sm"], "rk": rk, "prio": prio(x["e"])})
        return tr
    def run(tr, slots=5, fee=0.99, mtm=True, seeds=15):
        rs = [_depot_real(tr, max_open=slots, seed=sd, fee_eur=fee, mtm=mtm) for sd in range(seeds)]
        rs = [r for r in rs if r]
        if not rs:
            return None
        med = lambda key: sorted(r[key] for r in rs)[len(rs) // 2]
        ys = sorted({y for r in rs for y in r["years"]})
        yrs = {y: sorted(r["years"].get(y, 0) for r in rs)[len(rs) // 2] for y in ys}
        best = max(yrs, key=yrs.get) if yrs else None
        g = 1.0
        for y, v in yrs.items():
            if y != best:
                g *= 1 + v
        nyr = max(1, len(yrs) - 1)
        return {"cagr": med("cagr"), "cagr_p10": sorted(r["cagr"] for r in rs)[len(rs) // 10], "mdd_daily": med("mdd_daily"),
                "mdd_closed": med("mdd_closed"), "end": med("end"), "trades": rs[0]["trades"], "years": yrs,
                "ohne_bestes_jahr": round(g ** (1 / nyr) - 1, 3), "bestes_jahr": best}
    # 2) Schritt für Schritt von der alten Rechnung zur ehrlichen
    steps = {}
    R = prios["ruhigste zuerst"]
    steps["1 wie bisher (Aktie, Gebühr anteilig, Rückgang nur bei Verkauf)"] = run(trades("hit", "aktie", 20, R), fee=None, mtm=False)
    steps["2 + Gebühr 0,99 € je Order"] = run(trades("hit", "aktie", 20, R), fee=0.99, mtm=False)
    steps["3 + Turbo (Finanzierung, Spread, K.-o. bei Kurslücken)"] = run(trades("hit", "turbo", 20, R), fee=0.99, mtm=False)
    steps["4 + täglicher Depotwert (= ehrliche Rechnung)"] = run(trades("hit", "turbo", 20, R), fee=0.99, mtm=True)
    out["steps"] = steps
    # 3) Kernfrage: Treffer gegen Zufallstage (gleiche Regeln, gleiches Depot)
    out["vs_random"] = {f"{k} · {pn}": run(trades(k, "turbo", 20, pf)) for k in ("hit", "fast", "base")
                        for pn, pf in (("ruhigste zuerst", R), ("zufällig", prios["zufällig"]))}
    # 4) Risiko-Varianten (ehrlich gerechnet)
    out["risk"] = {
        "2 % Ausverkauf / 1 % sonst": run(trades("hit", "turbo", 20, R)),
        "1 % immer": run(trades("hit", "turbo", 20, R, weak=0.01)),
        "2 % Ausverkauf / gelb Pause / 1 % grau": run(trades("hit", "turbo", 20, R, mixed=0.0)),
        "1 % Ausverkauf / gelb Pause / 0,5 % grau": run(trades("hit", "turbo", 20, R, weak=0.01, mixed=0.0, other=0.005)),
        "nur im Ausverkauf 2 %": run(trades("hit", "turbo", 20, R, other=0.0, mixed=0.0)),
    }
    # 4b) Hebel: so wenig wie das Kapital verlangt (Einsatz aller Trades ≤ Depot) statt immer bis 10×
    lev_sims = {}
    for L in (1, 2, 3, 5, 10):
        rule = {**QRULE, "hold": 20, "levs": [L], "kob": 1.0}
        for x in sims.get(("hit", "aktie", 20)) or []:
            sm = simulate(x["e"]["px"], rule)
            if sm and "skip" not in sm and sm["lev"] == L:
                lev_sims.setdefault(id(x), {})[L] = sm
    def ltrades(allowed, weak=0.02, other=0.01, mixed=None):
        tr = []
        for x in sims.get(("hit", "aktie", 20)) or []:
            var = {L: v for L, v in (lev_sims.get(id(x)) or {}).items() if L in allowed}
            if not x["rg"] or not var:
                continue
            rk = weak if x["rg"] == "weak" else (mixed if (mixed is not None and x["rg"] == "mixed") else other)
            if rk > 0:
                tr.append({"d": x["d"], "sm": next(iter(var.values())), "var": var, "rk": rk, "prio": R(x["e"])})
        return tr
    out["leverage"] = {
        "immer höchster Hebel bis 10× (jetzt)": run(trades("hit", "turbo", 20, R)),
        "kleinster passender Hebel 1–10×": run(ltrades((1, 2, 3, 5, 10))),
        "kleinster passender Hebel 1–5×": run(ltrades((1, 2, 3, 5))),
        "kleinster passender Hebel 2–10×": run(ltrades((2, 3, 5, 10))),
        "nur Ausverkauf 2 %, kleinster Hebel 1–10×": run(ltrades((1, 2, 3, 5, 10), other=0.0, mixed=0.0)),
        "nur Ausverkauf 3 %, kleinster Hebel 1–10×": run(ltrades((1, 2, 3, 5, 10), weak=0.03, other=0.0, mixed=0.0)),
    }
    # Walk-forward der Hebel-Regel: Lernzeit / Prüfzeit getrennt
    def split(tr):
        a = run([t for t in tr if t["d"] < TRAIN_END], seeds=7)
        b = run([t for t in tr if t["d"] >= TRAIN_END], seeds=7)
        return {"lernen": a and {"cagr": a["cagr"], "mdd": a["mdd_daily"]}, "pruefen": b and {"cagr": b["cagr"], "mdd": b["mdd_daily"]}}
    out["leverage_wf"] = {"jetzt (bis 10×, 2 %/1 %)": split(trades("hit", "turbo", 20, R)),
                          "kleinster Hebel, 2 %/1 %": split(ltrades((1, 2, 3, 5, 10))),
                          "kleinster Hebel, nur Ausverkauf 2 %": split(ltrades((1, 2, 3, 5, 10), other=0.0, mixed=0.0))}
    # 4c) Ausstieg an Tag 5 ohne Anschlussbewegung (ChatGPT-Vorschlag) und kleinere Risiken
    def xtrades(rule_extra, weak=0.02, other=0.01, mixed=None):
        tr = []
        rule = {**QRULE, "hold": 20, "levs": [10, 5, 3, 1], "kob": 1.0, **rule_extra}
        for x in sims.get(("hit", "turbo", 20)) or []:
            if not x["rg"]:
                continue
            sm = simulate(x["e"]["px"], rule)
            rk = weak if x["rg"] == "weak" else (mixed if (mixed is not None and x["rg"] == "mixed") else other)
            if sm and "skip" not in sm and rk > 0:
                tr.append({"d": x["d"], "sm": sm, "rk": rk, "prio": R(x["e"])})
        return tr
    out["exit_risk"] = {
        "Tag 5: raus wenn im Minus": run(xtrades({"d5": 0.0})),
        "Tag 5: raus wenn unter −0,5 R": run(xtrades({"d5": -0.5})),
        "Tag 3: raus wenn im Minus": run(xtrades({"d5": 0.0, "d5_day": 3})),
        "Risiko 1 % Ausverkauf / 0,5 % sonst": run(trades("hit", "turbo", 20, R, weak=0.01, other=0.005)),
        "Risiko 1,5 % Ausverkauf / 0,5 % sonst": run(trades("hit", "turbo", 20, R, weak=0.015, other=0.005)),
        "Risiko 2 % Ausverkauf / 0,5 % sonst": run(trades("hit", "turbo", 20, R, weak=0.02, other=0.005)),
        "3 Plätze, 2 %/1 %": run(trades("hit", "turbo", 20, R), slots=3),
    }
    # 6) Finale Kandidaten – alle mit kleinstem passendem Hebel, jeweils 10 Jahre / Lernzeit / Prüfzeit
    def lsims(k, extra=None):
        res = []
        for x in sims.get((k, "aktie", 20)) or []:
            var = {}
            for L in (1, 2, 3, 5, 10):
                sm = simulate(x["e"]["px"], {**QRULE, "hold": 20, "levs": [L], "kob": 1.0, **(extra or {})})
                if sm and "skip" not in sm and sm["lev"] == L:
                    var[L] = sm
            if var and x["rg"]:
                res.append((x, var))
        return res
    def ctr(rows, weak, other, mixed=None, prio=R):
        tr = []
        for x, var in rows:
            rk = weak if x["rg"] == "weak" else (mixed if (mixed is not None and x["rg"] == "mixed") else other)
            if rk > 0:
                tr.append({"d": x["d"], "sm": next(iter(var.values())), "var": var, "rk": rk, "prio": prio(x["e"])})
        return tr
    def full_split(tr, slots=5):
        a, b, c = run(tr, slots=slots, seeds=9), run([t for t in tr if t["d"] < TRAIN_END], slots=slots, seeds=7), \
            run([t for t in tr if t["d"] >= TRAIN_END], slots=slots, seeds=7)
        pick = lambda z: z and {"cagr": z["cagr"], "mdd": z["mdd_daily"], "years": z.get("years"), "ohne_bestes_jahr": z.get("ohne_bestes_jahr")}
        return {"zehn_jahre": pick(a), "lernen": pick(b), "pruefen": pick(c)}
    hit_l, hit_d5 = lsims("hit"), lsims("hit", {"d5": 0.0})
    base_l = lsims("base")
    out["final"] = {
        "A 2 %/1 % (Risiko wie jetzt)": full_split(ctr(hit_l, 0.02, 0.01)),
        "B 1 % immer": full_split(ctr(hit_l, 0.01, 0.01)),
        "C 1,5 %/0,75 %": full_split(ctr(hit_l, 0.015, 0.0075)),
        "D 2 %/0,5 %": full_split(ctr(hit_l, 0.02, 0.005)),
        "E wie A + Tag-5-Ausstieg": full_split(ctr(hit_d5, 0.02, 0.01)),
        "F wie A, 4 Plätze": full_split(ctr(hit_l, 0.02, 0.01), slots=4),
        "Z Zufallstage mit Regeln A": full_split(ctr(base_l, 0.02, 0.01)),
        "Z2 Zufallstage, zufällig gewählt": full_split(ctr(base_l, 0.02, 0.01, prio=lambda e: 0)),
    }
    # 5) Walk-forward: auf 2017–2023 wählen, auf 2024–2026 prüfen (getrennte Depots mit je 3.000 €)
    wf = {}
    for pn, pf in prios.items():
        for hold in (10, 20, 30):
            for slots in (4, 5, 6):
                tr = run(trades("hit", "turbo", hold, pf, hi=TRAIN_END), slots=slots, seeds=7)
                te = run(trades("hit", "turbo", hold, pf, lo=TRAIN_END), slots=slots, seeds=7)
                if tr and te:
                    wf[f"{pn} · {hold} T · {slots} Plätze"] = {"lernen": {"cagr": tr["cagr"], "mdd": tr["mdd_daily"]},
                                                                "pruefen": {"cagr": te["cagr"], "mdd": te["mdd_daily"]}}
    ranked = sorted(wf.items(), key=lambda kv: -kv[1]["lernen"]["cagr"])
    out["walk_forward"] = {"gewaehlt_auf_lernzeit": ranked[0][0] if ranked else None,
                           "dessen_pruefzeit": ranked[0][1]["pruefen"] if ranked else None,
                           "rang_unserer_strategie_lernzeit": next((i + 1 for i, (k2, _) in enumerate(ranked) if k2 == "ruhigste zuerst · 20 T · 5 Plätze"), None),
                           "alle": dict(ranked)}
    return out


TP_TARGETS = (None, ("R", 1.0), ("R", 1.5), ("R", 2.0), ("R", 2.5), ("R", 3.0), ("R", 4.0), ("R", 5.0), ("tp1",), ("ema20",))


def _tp_study(sets: dict) -> dict:
    """Ein festes Kursziel (Verkauf, sobald erreicht) gegen reinen Zeit-Ausstieg – Kauf in der Basis wie im Trade-Plan."""
    out = {}
    for k in ("hit", "fast"):
        es = sets.get(k) or []
        rows = {}
        for hold in tuple(int(x) for x in os.environ.get("SS_HOLDS", "10,20").split(",")):
            for tgt in TP_TARGETS:
                rule = {**QRULE, "hold": hold, "tgt": tgt}
                x = run_rule(es, rule, ci=False)
                rows[f"{hold}T {'kein Ziel' if not tgt else ' '.join(map(str, tgt))}"] = {p: _strip(x).get(p) for p in ("train", "val", "test", "all")}
        out[k] = rows
    return out


def main(argv=None) -> int:
    paths = (argv or sys.argv[1:])
    t0 = time.time()
    ev = []
    seen = set()
    for p in paths:
        for e in json.loads(Path(p).read_text()):
            if not e.get("px") or not e["px"].get("wd"):
                continue
            key = (e["t"], e["d"], e["k"])
            if key in seen:
                continue
            seen.add(key)
            ev.append(e)
    sets = defaultdict(list)
    for e in ev:
        sets[e["k"]].append(e)
    if len(sets["base"]) > MAX_BASE:
        random.Random(5).shuffle(sets["base"])
        sets["base"] = sets["base"][:MAX_BASE]
    # Trend-Rücksetzer wie im Live-Scanner (aufgezeichnet wird weiter gefasst)
    sets["trend"] = [e for e in sets["trend"] if (e.get("f") or {}).get("e200") is not None and e["f"]["e200"] >= 0.15
                     and -0.08 <= (e["f"].get("e50") or 1) <= 0 and 35 <= (e["f"].get("rsi") or 0) <= 50]
    sets["top"] = [e for e in sets["trend"] if (e.get("f") or {}).get("dd") is not None
                   and e["f"]["dd"] < 0.15 and (e["f"].get("atrp") or 1) < 0.045 and 0.15 <= (e["f"].get("e200") or 0) < 0.30]
    print("Ereignisse:", {k: len(v) for k, v in sets.items()}, f"{time.time() - t0:.0f} s", flush=True)
    report = {"generated": time.strftime("%Y-%m-%d"), "n": {k: len(v) for k, v in sets.items()},
              "range": [min(e["d"] for e in ev), max(e["d"] for e in ev)],
              "split": {"train": f"bis {TRAIN_END}", "val": f"{TRAIN_END} – {VAL_END}", "test": f"ab {VAL_END}"}}

    if os.environ.get("SS_ONLY") == "combo":               # Strategie-Vergleich als durchgehendes Depot
        report["combo"] = _combo(sets)
        print("===BEGIN===")
        print(json.dumps(report, ensure_ascii=False, separators=(",", ":"), default=str))
        print("===END===")
        return 0
    if os.environ.get("SS_ONLY") == "truth":             # Wahrheits-Test (Phase 1)
        report["truth"] = _truth(sets)
        OUT.write_text(json.dumps(report, ensure_ascii=False, separators=(",", ":"), default=str))
        print("===BEGIN===")
        print(json.dumps(report, ensure_ascii=False, separators=(",", ":"), default=str))
        print("===END===")
        return 0
    if os.environ.get("SS_ONLY") == "tp":                  # nur der Kursziel-Vergleich (schneller Lauf)
        report["tp"] = _tp_study(sets)
        print("===BEGIN===")
        print(json.dumps(report, ensure_ascii=False, separators=(",", ":"), default=str))
        print("===END===")
        return 0

    # 1) Rohe Vorwärtsrenditen ab Eröffnung des Folgetags (ohne Regeln): gibt es überhaupt einen Vorsprung?
    fwd = {}
    for k, es in sets.items():
        row = {}
        for nday in (1, 2, 3, 5, 7, 10, 15, 20):
            vals = defaultdict(list)
            for e in es:
                px = e["px"]
                if len(px["c"]) >= nday and px["o"]:
                    vals[_period(e["d"])].append((e["d"], px["c"][nday - 1] / px["o"][0] - 1))
            row[nday] = {p: {"n": len(v), "mean": round(float(np.mean([x for _, x in v])), 4),
                             "win": round(float(np.mean([x > 0 for _, x in v])), 3)} for p, v in vals.items() if v}
            allv = [x for v in vals.values() for x in v]
            if allv:
                ci = _boot([(d, x * 100) for d, x in allv], n=300)
                row[nday]["all"] = {"n": len(allv), "mean": round(float(np.mean([x for _, x in allv])), 4), "ci_pct": ci}
        fwd[k] = row
    report["forward"] = fwd
    print("Vorwärtsrenditen fertig", f"{time.time() - t0:.0f} s", flush=True)

    # 2) Stufe 1 – Haltedauer × Invalidierung × Puffer × Ziel × Wochenende (voller Verkauf, Hebel 1)
    grid1 = [dict(entry="open", late=0.5, inv=inv, buf=buf, maxd=3.0, hold=hold, tgt=tgt, wkend=wk, levs=[1])
             for inv, buf, hold, tgt, wk in itertools.product((3, 10), (0.25, 0.5, 1.0, 1.5), (2, 3, 5, 7, 10, 15, 20, 30),
                                                              (None, ("R", 1.5), ("ema20",), ("tp1",)), (False, True))]
    report["stage1"] = {}
    best1 = {}
    for k in ("hit", "fast", "trend", "top", "base"):
        es = sets.get(k) or []
        if not es:
            continue
        res = stage(es, [g for g in grid1 if k != "base" or g["hold"] <= 20])   # Vergleichstage: 20 Tage Verlauf
        best1[k] = res[0][0] if res else None
        # kompakt: Haltedauer-Kurve beim besten Rest (im Lern-Zeitraum gewählt)
        curve = {}
        if res:
            b = res[0][0]
            for hold in (2, 3, 5, 7, 10, 15, 20, 30):
                rr = next((x for x in res if _key(x[0]) == _key({**b, "hold": hold})), None)
                if rr:
                    curve[hold] = {p: _strip(rr[1]).get(p) for p in ("train", "val", "test")}
            bufc = {}
            for buf in (0.25, 0.5, 1.0, 1.5):
                rr = next((x for x in res if _key(x[0]) == _key({**b, "buf": buf})), None)
                if rr:
                    bufc[buf] = {p: _strip(rr[1]).get(p) for p in ("train", "val", "test")}
            wk = next((x for x in res if _key(x[0]) == _key({**b, "wkend": not b["wkend"]})), None)
        report["stage1"][k] = {"best": b if res else None, "best_res": _strip(res[0][1]) if res else None,
                               "top5": [{"rule": r, "train": x["train"], "val": x.get("val"), "test": x.get("test"), "ci_test": x.get("ci_test")} for r, x in res[:5]],
                               "hold_curve": curve, "buffer_curve": bufc if res else {},
                               "weekend_flip": {"rule": wk[0], "res": {p: _strip(wk[1]).get(p) for p in ("train", "val", "test")}} if res and wk else None}
        print(f"Stufe 1 {k}: {len(res)} Regeln", f"{time.time() - t0:.0f} s", flush=True)

    # 3) Dein Vorschlag wörtlich + bisherige Logik als Vergleich
    user = dict(entry="open", late=0.5, inv=10, buf=1.0, maxd=4.0, hold=5, tgt=None, wkend=True,
                part=(0.5, 1.5), be=1.0, be_after_part=True, trail=2.0, trail_from=1.5, levs=[1])
    old_kairo = dict(entry="open", late=9, inv="zone", buf=0.0, maxd=99, hold=63, tgt=("tp1",), wkend=False, levs=[1])
    report["proposal"] = {}
    for k in ("hit", "fast", "trend", "top", "base"):
        es = sets.get(k) or []
        if es:
            report["proposal"][k] = {"dein_vorschlag": _strip(run_rule(es, user)),
                                     "bisher_63T": _strip(run_rule(es, old_kairo)) if k in ("hit", "fast") else None,
                                     "bisher_20T": _strip(run_rule(es, {**old_kairo, "hold": 20}))}
    print("Vorschlag/bisher fertig", f"{time.time() - t0:.0f} s", flush=True)

    # 4) Stufe 2 – Ausstieg: Teilverkauf, Break-even, Trailing, Momentum (auf dem besten Stufe-1-Gerüst je Setup)
    report["stage2"] = {}
    for k in ("hit", "fast", "trend", "top"):
        b = best1.get(k)
        es = sets.get(k) or []
        if not b or not es:
            continue
        rules = []
        for part, be, trail in itertools.product((None, (0.3, 1.5), (0.5, 1.5), (0.5, 2.0)), (None, 1.0, 1.25, 1.5), (None, 1.5, 2.0, 3.0)):
            rules.append({**b, "part": part, "be": be, "be_after_part": bool(part), "trail": trail, "trail_from": 1.0,
                          "hold": max(b["hold"], 5)})
        res = stage(es, rules)
        report["stage2"][k] = [{"rule": r, "train": x["train"], "val": x.get("val"), "test": x.get("test"), "ci_test": x.get("ci_test")}
                               for r, x in res[:8]]
        print(f"Stufe 2 {k}", f"{time.time() - t0:.0f} s", flush=True)

    # 5) Stufe 3 – Einstiegsart, Hebel und K.-o.-Puffer (bestes Gerüst, Hebel automatisch bis max.)
    report["stage3"] = {}
    for k in ("hit", "trend", "top"):
        b = best1.get(k)
        es = sets.get(k) or []
        if not b or not es:
            continue
        rows = []
        for entry, maxlev, kob in itertools.product(("open", "buystop"), (1, 3, 5, 10), (0.5, 1.0, 1.5)):
            if maxlev == 1 and kob != 1.0:
                continue
            levs = [x for x in (1, 3, 5, 10) if x <= maxlev]
            r = {**b, "entry": entry, "levs": levs, "kob": kob}
            x = run_rule(es, r)
            allr = [s for v in x["_rows"].values() for s in v]
            dist = defaultdict(int)
            for s in allr:
                dist[s["lev"]] += 1
            pf = _portfolio([(s["date"], s["net"], s["d"], s["rp"]) for s in allr])
            rows.append({"entry": entry, "max_lev": maxlev, "ko_buf": kob, "train": x.get("train"), "test": x.get("test"),
                         "all": x.get("all"), "lev_dist": {str(k2): v for k2, v in sorted(dist.items())},
                         "portfolio_05pct": pf, "skip": x["skip"]})
        report["stage3"][k] = rows
        print(f"Stufe 3 {k}", f"{time.time() - t0:.0f} s", flush=True)

    # 5c) Stufe 6 – Was zeichnet die besten Reversals aus? Marktlage und Signalmerkmale (feste Regel „Kauf in der Basis“)
    report["stage6"] = _quality(sets)
    print("Stufe 6 fertig", f"{time.time() - t0:.0f} s", flush=True)

    # 5b) Stufe 5 – Kauf IN der Basis (vor dem Ausbruch) – deine Vorgehensweise
    report["stage5"] = {}
    for k in ("hit", "fast", "trend", "base"):
        es = sets.get(k) or []
        if not es:
            continue
        holds = (2, 3, 5, 7, 10) if k == "base" else (2, 3, 5, 7, 10, 20)
        grid = [dict(entry="base", ck=ck, cm=cm, lowhalf=lh, wait=10, inv=10, buf=buf, maxd=3.0, hold=hold, tgt=tgt, wkend=False, levs=[1])
                for ck, cm, lh, buf, hold, tgt in itertools.product((3, 5), (1.5, 2.5), (False, True), (0.25, 0.5), holds,
                                                                   (None, ("R", 1.5), ("tp1",)))]
        res = stage(es, grid)
        if not res:
            continue
        b = res[0][0]
        curve = {}
        for hold in holds:
            rr = next((x for x in res if _key(x[0]) == _key({**b, "hold": hold})), None)
            if rr:
                curve[hold] = {p: _strip(rr[1]).get(p) for p in ("train", "val", "test", "all")}
        # gleiche Basis-Definition, festes Raster (für den fairen Vergleich mit Zufall): 5 Tage, ≤ 1,5 ATR, untere Hälfte
        fixed = {}
        for lh in (False, True):
            for hold in holds:
                x = run_rule(es, dict(entry="base", ck=5, cm=1.5, lowhalf=lh, wait=10, inv=10, buf=0.25, maxd=3.0, hold=hold,
                                      tgt=None, wkend=False, levs=[1]), ci=False)
                fixed[f"{'unten' if lh else 'alle'}_{hold}"] = {p: _strip(x).get(p) for p in ("train", "val", "test", "all")}
        report["stage5"][k] = {"best": b, "best_res": _strip(res[0][1]), "hold_curve": curve, "fixed": fixed,
                               "top5": [{"rule": r, "train": x["train"], "val": x.get("val"), "test": x.get("test"), "ci_test": x.get("ci_test")}
                                        for r, x in res[:5]]}
        print(f"Stufe 5 {k}", f"{time.time() - t0:.0f} s", flush=True)

    # 6) Stufe 4 – Abwarten + Ausbruch aus der Seitwärtsphase (deine manuelle Vorgehensweise, objektiv nachgebildet)
    report["stage4"] = {}
    for k in ("hit", "fast", "trend", "top", "base"):
        es = sets.get(k) or []
        if not es:
            continue
        holds = (2, 3, 5, 7, 10) if k == "base" else (2, 3, 5, 7, 10, 20)
        grid = [dict(entry="cons", ck=ck, cm=cm, wait=10, inv=10, buf=buf, maxd=3.0, hold=hold, tgt=tgt, wkend=False, levs=[1])
                for ck, cm, buf, hold, tgt in itertools.product((3, 5), (1.5, 2.0, 2.5), (0.25, 0.5), holds, (None, ("R", 1.5), ("tp1",)))]
        res = stage(es, grid)
        if not res:
            continue
        b = res[0][0]
        curve = {}
        for hold in holds:
            rr = next((x for x in res if _key(x[0]) == _key({**b, "hold": hold})), None)
            if rr:
                curve[hold] = {p: _strip(rr[1]).get(p) for p in ("train", "val", "test", "all")}
        report["stage4"][k] = {"best": b, "best_res": _strip(res[0][1]), "hold_curve": curve,
                               "top5": [{"rule": r, "train": x["train"], "val": x.get("val"), "test": x.get("test"), "ci_test": x.get("ci_test")}
                                        for r, x in res[:5]]}
        print(f"Stufe 4 {k}", f"{time.time() - t0:.0f} s", flush=True)

    OUT.write_text(json.dumps(report, ensure_ascii=False, separators=(",", ":"), default=str))
    print("===BEGIN===")
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":"), default=str))
    print("===END===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def kairo_series(sets: dict, seeds: int = 9) -> dict:
    """Täglicher Depotwert (3.000 € Start) der aktuellen Kairo-Strategie für den großen Strategie-Vergleich:
    volle Treffer, Kauf in der Seitwärtsphase, 20 Tage, 1 % Risiko, ruhigste zuerst, 5 Plätze, kleinster passender Hebel.
    Von mehreren Reihenfolgen (gleicher Tag) wird die mit dem mittleren Ergebnis genommen."""
    import datetime as dt
    rows = []
    for e in sets.get("hit") or []:
        if len(e["px"]["c"]) < 30:
            continue
        var = {}
        for L in (1, 2, 3, 5, 10):
            sm = simulate(e["px"], {**QRULE, "hold": 20, "levs": [L], "kob": 1.0})
            if sm and "skip" not in sm and sm["lev"] == L:
                var[L] = sm
        if var:
            sm0 = next(iter(var.values()))
            d_in = str(dt.date.fromisoformat(e["d"]) + dt.timedelta(days=int((sm0["s"] + 1) * 7 / 5)))
            rows.append({"d": d_in, "sm": sm0, "var": var, "rk": 0.01, "prio": -((e.get("f") or {}).get("atrp") or 1)})
    runs = []
    for sd in range(seeds):
        ser = {}
        r = _depot_real(rows, seed=sd, series=ser)
        if r:
            runs.append((r["cagr"], ser))
    runs.sort(key=lambda x: x[0])
    return runs[len(runs) // 2][1] if runs else {}
