"""Live-Bilanz: Signale des täglichen Scans speichern und ihr Ergebnis nachverfolgen (siehe bilanz.py)."""

from __future__ import annotations

import json

import pandas as pd

from . import state
from .bilanz import GAP, _agg, outcome, stats
from .config import ROOT
from .indicators import atr as _atr
from .shortswing import QRULE, simulate

HOLD = 20                                          # Strategie: 20 Handelstage halten, kein Gewinnziel


def strat(df: pd.DataFrame, idx: int) -> dict:
    """Ein Kairo-Treffer nach unseren Regeln: Kauf in der Seitwärtsphase (≤ 10 Tage nach dem Signal), Stop = Basistief
    − 0,25 ATR, Verkauf am Stop oder zum Schluss von Tag 20. Wie in der 10-Jahres-Studie (shortswing.simulate), netto in R.
    Ergebnis: res = wait (Basis noch offen) · nobase (keine Basis/gescheitert) · run (läuft) · stop · zeit; r = Netto-R."""
    c0 = float(df["Close"].iloc[idx])
    a = float(_atr(df).iloc[idx]) / c0 if c0 else 0
    if not a or a != a:
        return {"res": "nobase"}
    nx = lambda k: [float(x) / c0 for x in df[k].iloc[idx + 1:]]
    px = {"o": nx("Open"), "h": nx("High"), "l": nx("Low"), "c": nx("Close"), "atr": a,
          "pl": [float(x) / c0 for x in df["Low"].iloc[max(0, idx - 9):idx + 1]], "s": None}
    n = len(px["c"])
    if n < 2:
        return {"res": "wait"}
    rule = {**QRULE, "hold": HOLD}
    sm = simulate(px, rule)
    if sm and "skip" in sm:
        return {"res": "wait"} if sm["skip"] == "nofill" and n - 1 < rule["wait"] else {"res": "nobase", "why": sm["skip"]}
    if sm:
        return {"res": "stop" if sm["x"] == "stop" else "zeit", "r": round(sm["net"], 3), "days": sm["d"],
                "e": round(sm["e"] * c0, 4), "sl": round(sm["sl"] * c0, 4)}
    for h in range(HOLD - 1, 0, -1):               # läuft noch: Stand zum letzten Schluss
        sm = simulate(px, {**rule, "hold": h})
        if sm and "skip" not in sm:
            return {"res": "stop" if sm["x"] == "stop" else "run", "r": round(sm["net"], 3), "days": sm["d"],
                    "e": round(sm["e"] * c0, 4), "sl": round(sm["sl"] * c0, 4)}
    return {"res": "wait"}


def strat_stats(sig: list[dict]) -> dict | None:
    done = [s["st"] for s in sig if s.get("k") == "hit" and (s.get("st") or {}).get("res") in ("stop", "zeit")]
    if not done:
        return None
    r = [x["r"] for x in done]
    return {"n": len(done), "avg_r": round(sum(r) / len(r), 3), "win": round(sum(x > 0 for x in r) / len(r), 3),
            "stop": round(sum(x["res"] == "stop" for x in done) / len(done), 3),
            "nobase": sum((s.get("st") or {}).get("res") == "nobase" for s in sig if s.get("k") == "hit"),
            "run": sum((s.get("st") or {}).get("res") in ("run", "wait") for s in sig if s.get("k") == "hit")}


def update(rows: list[dict], data: dict[str, pd.DataFrame], today: str) -> dict:
    sig = state.load("signals.json", [])
    last = state.load("last.json", {})
    prev = {"hit": set(last.get("hit", [])), "fast": set(last.get("fast", [])), "trend": set(last.get("trend", []))}
    known = {(s["t"], s["k"], s["d"]) for s in sig}
    recent = {}
    for s in sig:                                  # letztes Signal je Aktie/Art
        recent[(s["t"], s["k"])] = max(recent.get((s["t"], s["k"]), ""), s["d"])
    new = []
    cand = [(r, "hit" if r["passed"] else "fast" if r.get("fast_hit") else None, r.get("plan") or {}) for r in rows]
    cand += [(r, "trend", r["tr"].get("plan") or {}) for r in rows if (r.get("tr") or {}).get("ok")]   # zweites Setup
    for r, k, p in cand:
        if not k or not p.get("stop") or not p.get("entry"):
            continue
        d = r.get("date") or today
        if r["ticker"] in prev[k] or (r["ticker"], k, d) in known:
            continue
        lastd = recent.get((r["ticker"], k))
        if lastd and (pd.Timestamp(d) - pd.Timestamp(lastd)).days <= GAP + 2:
            continue
        s = {"t": r["ticker"], "n": (r.get("name") or r["ticker"])[:40], "k": k, "d": d, "score": r.get("score", 0),
             "entry": p["entry"], "stop": p["stop"], "t1": p.get("target1"), "t2": p.get("target2"), "crv": p.get("crv"),
             "region": r.get("region"), "grade": (r.get("grade") or {}).get("g"), "res": "running"}
        chk = (r.get("tr") or {}).get("chk") if k == "trend" else None
        if chk:                                    # Rücksetzer-Check am Signaltag – für die spätere Live-Prüfung
            s.update(chk=chk["p"], f50=chk.get("fib50"), hi=chk.get("hi"))
        try:                                       # TP 1 = nächstes relevantes Hoch (Hoch-Treppe wie im Depot)
            from .analysis import swing_levels
            dfx = data.get(r["ticker"])
            lv = swing_levels(dfx, float(dfx["Close"].iloc[-1]), (r.get("flags") or {}).get("atr") or 0) if dfx is not None else []
            s["tp1"] = lv[0]["p"] if lv else None
        except Exception:
            s["tp1"] = None
        sig.append(s)
        new.append(s)
    # Ergebnisse nachführen
    for s in sig:
        if s.get("final") and (s["k"] != "hit" or (s.get("st") or {}).get("res") in ("stop", "zeit", "nobase")):
            continue
        df = data.get(s["t"])
        if df is None:
            continue
        df = df.dropna(subset=["Open", "High", "Low", "Close"])
        idx = int(df.index.searchsorted(pd.Timestamp(s["d"]), side="right") - 1)
        if idx < 0:
            continue
        o, h, l, c = (df[k].to_numpy(float) for k in ("Open", "High", "Low", "Close"))
        oc = outcome(o, h, l, c, idx, s["entry"], s["stop"], s.get("t1"), s.get("t2"), s.get("tp1"))
        if oc:
            s.update(oc)
            s["now"] = round(float(c[-1] / s["entry"] - 1), 4)
        if s["k"] == "hit" and (s.get("st") or {}).get("res") not in ("stop", "zeit", "nobase"):
            try:
                s["st"] = strat(df, idx)
            except Exception as exc:               # Bilanz darf den Scan nie stoppen
                print("Strategie-Bilanz:", s["t"], repr(exc)[:100])
    state.save("signals.json", sig)
    state.save("last.json", {"date": today, "hit": [r["ticker"] for r in rows if r["passed"]],
                             "fast": [r["ticker"] for r in rows if r.get("fast_hit")],
                             "trend": [r["ticker"] for r in rows if (r.get("tr") or {}).get("ok")],
                             "met": {r["ticker"]: r.get("met") for r in rows}})
    try:
        bt = json.loads((ROOT / "data" / "bilanz_backtest.json").read_text(encoding="utf-8"))
    except Exception:
        bt = None
    done = [s for s in sig if s.get("res") not in (None, "running")]
    out = {"generated": today, "live": {"since": min((s["d"] for s in sig), default=today), "n": len(sig),
                                        "stats": stats(done) if done else None, "strat": strat_stats(sig),
                                        "grade": {g: _agg([x for x in done if x["k"] == "hit" and x.get("grade") == g]) for g in "ABC"}},
           "signals": sorted(sig, key=lambda s: s["d"], reverse=True)[:80], "new": [s["t"] for s in new], "backtest": bt}
    return out
