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
    part = r.get("part")                           # (Anteil, R-Vielfaches)
    ptarget = entry + part[1] * risk if part else None
    # Hebel / K.-o.
    lev, ko = 1, None
    for L in sorted(r.get("levs", [1]), reverse=True):
        k = entry * (1 - 1 / L) if L > 1 else None
        if k is None or k <= stop0 - r.get("kob", 1.0) * atr:
            lev, ko = L, k
            break
    stop, pos, real, maxh, mfe, mae, orders = stop0, 1.0, 0.0, entry, 0.0, 0.0, 2
    be_cost = (SPREAD["turbo" if lev > 1 else "stock"] + 2 * FEE / EXPOSURE) * entry
    hold = r["hold"]
    exit_, day, why = None, None, None
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
        if n_held >= hold:
            exit_, day, why = c[j], n_held, "zeit"
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
    return {"r": gross, "net": gross - cost, "d": day, "x": why, "lev": lev, "mfe": mfe, "mae": mae, "rp": rp, "s": start}


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
    """Marktlage je Handelstag: S&P 500 über EMA 200 / EMA 50, VIX. Leer, wenn keine Daten."""
    try:
        from .data_provider import YFinanceProvider
        from .indicators import ema
        h = YFinanceProvider().history(["^GSPC", "^VIX"], "8y")
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


QRULE = dict(entry="base", ck=5, cm=1.5, lowhalf=False, wait=10, inv=10, buf=0.25, maxd=3.0, tgt=None, wkend=False, levs=[1])


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
    trades = sorted(trades, key=lambda t: (t[0], rnd.random()))
    eq, peak, mdd, open_, taken, by_year, eq_year = start, start, 0.0, [], 0, {}, {}
    def close_until(t0):
        nonlocal eq, peak, mdd, open_
        keep = []
        for end, amt in sorted(open_):
            if end <= t0:
                eq += amt
                peak = max(peak, eq)
                mdd = max(mdd, 1 - eq / peak)
            else:
                keep.append((end, amt))
        open_ = keep
    for d, net, days, rk in trades:
        t0 = dt.date.fromisoformat(d)
        close_until(t0)
        y = d[:4]
        eq_year.setdefault(y, eq)
        if len(open_) >= max_open:
            continue
        taken += 1
        by_year[y] = by_year.get(y, 0) + 1
        open_.append((t0 + dt.timedelta(days=int(days * 7 / 5) + 1), eq * rk * net))
    close_until(dt.date(2100, 1, 1))
    ys = sorted(eq_year)
    yr = {y: round((eq_year[ys[i + 1]] if i + 1 < len(ys) else eq) / eq_year[y] - 1, 3) for i, y in enumerate(ys)}
    span = max(0.5, (dt.date.fromisoformat(trades[-1][0]) - dt.date.fromisoformat(trades[0][0])).days / 365)
    return {"trades": taken, "end_eur": round(eq), "cagr": round((eq / start) ** (1 / span) - 1, 3), "mdd": round(mdd, 3),
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
    return out


TP_TARGETS = (None, ("R", 1.0), ("R", 1.5), ("R", 2.0), ("R", 2.5), ("R", 3.0), ("R", 4.0), ("R", 5.0), ("tp1",), ("ema20",))


def _tp_study(sets: dict) -> dict:
    """Ein festes Kursziel (Verkauf, sobald erreicht) gegen reinen Zeit-Ausstieg – Kauf in der Basis wie im Trade-Plan."""
    out = {}
    for k in ("hit", "fast"):
        es = sets.get(k) or []
        rows = {}
        for hold in (10, 20):
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
