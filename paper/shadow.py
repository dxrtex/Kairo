"""Schattenbuch (nur Forschung, ohne Einfluss auf die Papier-Depots).

Protokolliert jedes S19- und S20-Tagessignal mit echten 4H-Kerzen – auch die, die in den Depots am CRV, an vollem Depot oder
an fehlendem Cash scheitern – und rechnet für jedes Signal mehrere Ausstiegsregeln parallel durch:
  S19: Einstieg „4h“ (Auslöser wie im Depot, CRV wird nur gespeichert, nicht gefiltert) und „frueh“ (Eröffnung am Tag nach
       dem Signal, Stop = Signaltag-Tief − 0,5 ATR). Ausstiege: EMA20-Ziel / nach 5 / nach 10 Handelstagen (jeweils mit Stop).
  S20: Einstieg „4h“ wie im Depot. Ausstiege: Nutzerregel (Einstand + Nachziehen) / nach 5 / nach 10 Handelstagen.
Jedes Signal wird einzeln gerechnet (keine Kapitalgrenze). R netto mit der Stückzahl eines 2.000-€-Depots bei 1 % Risiko.
Gesammelt wird mit der weitesten S19-Variante (C); welche Varianten ein Signal auch auslöst, steht in „var“.
Auswertung später: Mindest-CRV 1 / 1,5 / 2 × Ausstieg – vorab festgelegt (Protokoll v1.8), keine Regeländerung an den Depots.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import core

EXITS = {"S19": ("ema20", "t5", "t10"), "S20": ("trail", "t5", "t10")}
MAX_DAYS = 40                                      # Notausstieg für EMA20/Nachziehen
CRV_MIN = (None, 1.0, 1.5, 2.0)
RISK = 0.01


def load(d: Path) -> dict:
    p = d / "shadow.json"
    if p.exists():
        return json.loads(p.read_text())
    return {"start": None, "last_day": None, "pending": [], "open": [], "closed": []}


def save(d: Path, sb: dict) -> None:
    (d / "shadow.json").write_text(json.dumps(sb, indent=1, default=str, ensure_ascii=False))


def _ndays(cal: pd.DatetimeIndex, a, b) -> int:
    """Handelstage nach Tag a bis einschließlich Tag b."""
    return int(np.searchsorted(cal.values, np.datetime64(pd.Timestamp(b)), side="right")
               - np.searchsorted(cal.values, np.datetime64(pd.Timestamp(a)), side="right"))


def _trade(rec: dict, mode: str, stop: float | None, crv: float | None, after_ts=None, after_day=None) -> dict:
    return {"id": f"{rec['fam']}-{mode}-{rec['t']}-{rec['day']}", "fam": rec["fam"], "mode": mode, "t": rec["t"],
            "day": rec["day"], "var": rec.get("var", [rec["fam"]]), "z": rec.get("z"), "regime": rec.get("regime"),
            "crv": None if crv is None else round(float(crv), 3), "stop0": stop, "atr": rec.get("atr"),
            "after_ts": None if after_ts is None else str(after_ts), "after_day": after_day,
            "entry": None, "entry_ts": None, "exits": {}}


def collect(sb: dict, mk, D: pd.Timestamp, cal, s19_t, s20_t, bull_D: bool, fund: dict, sec3: dict) -> None:
    """Neue Tagessignale aus dem Schluss von D (gleiche Filter wie die Depots, über run.new_setups)."""
    from . import run
    for fam, sid, tick in (("S19", "S19C", s19_t), ("S20", "S20", s20_t)):
        tmp = run.load_state(Path("/nonexistent"), sid)
        run.new_setups(tmp, mk, D, cal, tick, bull_D, fund, sec3)
        busy = {q["t"] for q in sb["pending"] if q["fam"] == fam} | {x["t"] for x in sb["open"] if x["fam"] == fam}
        for q in tmp["pending"]:
            if q["t"] in busy:
                continue
            rec = {"fam": fam, **q, "regime": "bull" if bull_D else "bear"}
            if fam == "S19":
                x = mk.f(q["t"])
                i = int(x.index.get_loc(D))
                strict = core.vol_exhausted(x["Volume"].to_numpy(), i, "strict")
                rec["var"] = [v for v, (sg, vm) in core.S19_VARIANTS.items() if q["z"] <= -sg and (vm == "2of3" or strict)]
                r = x.iloc[i]
                sl, c, tp = float(r["Low"] - 0.5 * r["atr"]), float(r["Close"]), float(r["ema20"])
                sb["open"].append(_trade(rec, "frueh", sl, (tp - c) / (c - sl) if c > sl else -1, after_day=str(D.date())))
            sb["pending"].append(rec)


def _cost(mk, t, d, entry, stop):
    sp, rate = mk.spread(t, d), mk.rate(t, d)
    q = core.size(2000.0, 2000.0, RISK, entry, stop, rate, sp) if np.isfinite(rate) else 0
    return q, sp, rate


def _close(mk, x: dict, rule: str, px: float, why: str, ts) -> None:
    e, s0 = x["entry"], x["stop0"]
    R = (px - e) / (e - s0) if e > s0 else None
    rn = None
    if x.get("qty"):
        buy = e * (1 + x["sp"] / 2)
        sell = px * (1 - x["sp"] / 2)
        risk = x["qty"] * (buy - s0) / x["rate"]
        pnl = x["qty"] * (sell - buy) / x["rate"] - 2 * core.FEE
        rn = pnl / risk if risk > 0 else None
    x["exits"][rule] = {"px": round(px, 4), "why": why, "ts": str(ts), "R": None if R is None else round(R, 3),
                        "R_net": None if rn is None else round(rn, 3)}


def step_day(sb: dict, mk, D: pd.Timestamp, D_prev: pd.Timestamp, cal, bull_prev: bool) -> None:
    """Kerzen von D je Titel chronologisch: Käufe, Ausstiege je Regel, neue 4H-Auslöser; danach Zeit-Ausstiege zum Schluss."""
    tick = sorted({q["t"] for q in sb["pending"]} | {x["t"] for x in sb["open"]})
    for t in tick:
        b = mk.h4.get(t)
        if b is None or not len(b):
            continue
        for j in np.flatnonzero(((b["day"] > D_prev) & (b["day"] <= D)).to_numpy()):
            ts, bar = b.index[j], b.iloc[j]
            prev = b.iloc[j - 1] if j > 0 else None
            for x in [x for x in sb["open"] if x["t"] == t]:
                if x["entry"] is None:                     # Kauf zur Eröffnung dieser Kerze?
                    due = (x["after_ts"] is not None and ts > pd.Timestamp(x["after_ts"])) or \
                          (x["after_day"] is not None and bar["day"] > pd.Timestamp(x["after_day"]))
                    if not due:
                        continue
                    op = float(bar["Open"])
                    if x["fam"] == "S20":
                        x["stop0"] = op - 1.5 * x["atr"]
                    if op <= x["stop0"]:
                        x["exits"] = {r: {"why": "kein_kauf_unter_stop"} for r in EXITS[x["fam"]]}
                        continue
                    x["entry"], x["entry_ts"] = op, str(ts)
                    x["qty"], x["sp"], x["rate"] = _cost(mk, t, D_prev, op, x["stop0"])
                    x["pos"] = {r: {"sid": "S20" if r == "trail" else "S19", "entry": op, "stop": x["stop0"], "atr": x["atr"],
                                    "be": False} for r in EXITS[x["fam"]]}
                tp = None
                if x["fam"] == "S19":
                    f = mk.f(t)
                    v = f["ema20"][f.index < bar["day"]]
                    tp = float(v.iloc[-1]) if len(v) else None
                for r, p in x["pos"].items():
                    if r in x["exits"]:
                        continue
                    res = core.step_position(p, bar, prev if pd.Timestamp(x["entry_ts"]) < ts else None,
                                             tp if r == "ema20" else None)
                    if res:
                        _close(mk, x, r, res[0], res[1], ts)
            for q in [q for q in sb["pending"] if q["t"] == t]:
                if not (pd.Timestamp(q["day"]) < bar["day"] <= pd.Timestamp(q["expiry"])):
                    continue
                if q["fam"] == "S19":
                    lows = b["Low"][(b["day"] > pd.Timestamp(q["day"])) & (b.index <= ts)]
                    q["panic"] = min(q["panic"], float(lows.min())) if len(lows) else q["panic"]
                    if not core.s19_trigger(b, j):
                        continue
                    c, sl = float(bar["Close"]), q["panic"] - 0.5 * q["atr"]
                    f = mk.f(t)
                    v = f["ema20"][f.index < bar["day"]]
                    tp = float(v.iloc[-1]) if len(v) else float("nan")
                    sb["open"].append(_trade(q, "4h", sl, (tp - c) / (c - sl) if c > sl else -1, after_ts=ts))
                else:
                    if not bull_prev or not core.s20_trigger(b, j):
                        continue
                    sb["open"].append(_trade(q, "4h", None, None, after_ts=ts))
                sb["pending"].remove(q)
    # Zeit-Ausstiege zum Tagesschluss von D
    for x in sb["open"]:
        if x["entry"] is None or "pos" not in x:
            continue
        held = _ndays(cal, pd.Timestamp(x["entry_ts"]).normalize(), D)
        b = mk.h4.get(x["t"])
        last = b[b["day"] <= D] if b is not None else None
        if last is None or not len(last):
            continue
        px, ts = float(last["Close"].iloc[-1]), last.index[-1]
        for r in x["pos"]:
            if r in x["exits"]:
                continue
            n = {"t5": 5, "t10": 10}.get(r, MAX_DAYS)
            if held >= n:
                _close(mk, x, r, px, "zeit" if n < MAX_DAYS else "max40", ts)
    sb["pending"] = [q for q in sb["pending"] if pd.Timestamp(q["expiry"]) > D]
    done = [x for x in sb["open"] if all(r in x["exits"] for r in EXITS[x["fam"]])]
    for x in done:
        sb["open"].remove(x)
        x.pop("pos", None)
        sb["closed"].append(x)


def summary(sb: dict) -> dict:
    """Matrix je Familie/Einstieg/Variante × Mindest-CRV × Ausstieg: Anzahl, Ø R netto, Trefferquote (nur abgeschlossene)."""
    rows = []
    tr = [x for x in sb["closed"] if x.get("entry") is not None]
    combos = [("S19", "4h"), ("S19", "frueh"), ("S20", "4h")]
    for fam, mode in combos:
        for var in (core.S19_VARIANTS if fam == "S19" else ("S20",)):
            sel = [x for x in tr if x["fam"] == fam and x["mode"] == mode and var in x["var"]]
            for m in (CRV_MIN if fam == "S19" else (None,)):
                s2 = [x for x in sel if m is None or (x["crv"] is not None and x["crv"] >= m)]
                for r in EXITS[fam]:
                    v = [x["exits"][r]["R_net"] for x in s2 if x["exits"].get(r, {}).get("R_net") is not None]
                    rows.append({"fam": fam, "mode": mode, "var": var, "crv_min": m, "exit": r, "n": len(v),
                                 "avg_R_net": round(float(np.mean(v)), 3) if v else None,
                                 "win": round(float(np.mean([z > 0 for z in v])), 3) if v else None})
    return {"start": sb["start"], "stand": sb["last_day"], "wartend": len(sb["pending"]), "offen": len(sb["open"]),
            "abgeschlossen": len(sb["closed"]), "matrix": rows}
