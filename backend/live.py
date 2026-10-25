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
# Aktuelle Kairo-Regel (Forschung v2.5, S01-B): Ausstieg ab Tag 10 bei Schluss unter EMA20 zur nächsten Eröffnung, spätestens Tag 60
RULE60 = {"hold": 60, "ema_x": 20, "ema_from": 10}
DONE = ("stop", "zeit", "ema", "nobase")


def strat(df: pd.DataFrame, idx: int, extra: dict | None = None) -> dict:
    """Ein Kairo-Treffer nach unseren Regeln: Kauf in der Seitwärtsphase (≤ 10 Tage nach dem Signal), Stop = Basistief
    − 0,25 ATR, Verkauf am Stop oder zum Schluss von Tag 20. Wie in der 10-Jahres-Studie (shortswing.simulate), netto in R.
    Ergebnis: res = wait (Basis noch offen) · nobase (keine Basis/gescheitert) · run (läuft) · stop · zeit; r = Netto-R."""
    c0 = float(df["Close"].iloc[idx])
    a = float(_atr(df).iloc[idx]) / c0 if c0 else 0
    if not a or a != a:
        return {"res": "nobase"}
    nx = lambda k: [float(x) / c0 for x in df[k].iloc[idx + 1:]]
    px = {"o": nx("Open"), "h": nx("High"), "l": nx("Low"), "c": nx("Close"), "atr": a,
          "pl": [float(x) / c0 for x in df["Low"].iloc[max(0, idx - 9):idx + 1]], "s": None,
          "e20": float(df["Close"].iloc[:idx + 1].ewm(span=20, adjust=False).mean().iloc[-1]) / c0}
    n = len(px["c"])
    if n < 2:
        return {"res": "wait"}
    rule = {**QRULE, "hold": HOLD, **(extra or {})}
    sm = simulate(px, rule)
    if sm and "skip" in sm:
        return {"res": "wait"} if sm["skip"] == "nofill" and n - 1 < rule["wait"] else {"res": "nobase", "why": sm["skip"]}
    if sm:
        return {"res": {"stop": "stop", "ema": "ema"}.get(sm["x"], "zeit"), "r": round(sm["net"], 3), "days": sm["d"],
                "e": round(sm["e"] * c0, 4), "sl": round(sm["sl"] * c0, 4)}
    for h in range(rule["hold"] - 1, 0, -1):       # läuft noch: Stand zum letzten Schluss
        sm = simulate(px, {**rule, "hold": h})
        if sm and "skip" not in sm:
            return {"res": "stop" if sm["x"] == "stop" else "run", "r": round(sm["net"], 3), "days": sm["d"],
                    "e": round(sm["e"] * c0, 4), "sl": round(sm["sl"] * c0, 4)}
    return {"res": "wait"}


TESTED = ("us", "europe")         # die Kairo-Regel ist für USA und Europa getestet (wie die Papier-Depots)
_PRIO = {"us": 0, "europe": 1, "asia": 2}


def _one_listing(sig: list[dict]) -> list[dict]:
    """Gleiche Firma an zwei Börsen (z. B. NVO und NOVO-B.CO) am selben Tag nur einmal – USA vor Europa vor Asien."""
    from .universe import company_key
    seen, out = set(), []
    for s in sorted(sig, key=lambda s: _PRIO.get(s.get("region"), 3)):
        key = company_key(s.get("n") or "")
        k = (key if len(key) > 2 else s.get("t") or id(s), s.get("k"), s.get("d"))
        if k not in seen:
            seen.add(k)
            out.append(s)
    return out


def strat_stats(sig: list[dict], key: str = "st", regions: tuple | None = TESTED) -> dict | None:
    """Live-Bilanz der Kairo-Regel. Abgeschlossene Trades allein sind anfangs zu schlecht (Stops schließen früh, Gewinner laufen
    bis zu 60 Tage) – deshalb zusätzlich die offenen Trades zum heutigen Stand („mtm“)."""
    hits = [s for s in _one_listing(sig) if s.get("k") == "hit" and (regions is None or s.get("region") in regions or not s.get("region"))]
    done = [s[key] for s in hits if (s.get(key) or {}).get("res") in ("stop", "zeit", "ema")]
    run = [s[key] for s in hits if (s.get(key) or {}).get("res") == "run" and s[key].get("r") is not None]
    if not done and not run:
        return None
    r, ro = [x["r"] for x in done], [x["r"] for x in run]
    allr = r + ro
    out = {"n": len(done), "open": len(run), "open_r": round(sum(ro) / len(ro), 3) if ro else None,
           "mtm_n": len(allr), "mtm_r": round(sum(allr) / len(allr), 3), "mtm_win": round(sum(x > 0 for x in allr) / len(allr), 3),
           "nobase": sum((s.get(key) or {}).get("res") == "nobase" for s in hits),
           "run": sum((s.get(key) or {}).get("res") in ("run", "wait") for s in hits)}
    if done:
        out.update(avg_r=round(sum(r) / len(r), 3), win=round(sum(x > 0 for x in r) / len(r), 3),
                   stop=round(sum(x["res"] == "stop" for x in done) / len(done), 3))
    else:
        out.update(avg_r=None, win=None, stop=None)
    return out


def _show(sig: list[dict]) -> list[dict]:
    """Für die App: die 80 neuesten Signale plus alle Kairo-Trades mit Einstieg (laufend oder beendet) – sonst fehlen ältere,
    noch laufende Gewinner in der Liste."""
    new = sorted(_one_listing(sig), key=lambda s: s["d"], reverse=True)
    keep = new[:80] + [s for s in new[80:] if s.get("k") == "hit" and ((s.get("st60") or s.get("st") or {}).get("res") in ("run", "stop", "ema", "zeit"))]
    return keep


def update(rows: list[dict], data: dict[str, pd.DataFrame], today: str, record: bool = True) -> dict:
    """record=False: keine neuen Signale speichern (Scan während der Börsenzeit – US-Tageskerzen noch nicht fertig);
    Ergebnisse bestehender Signale werden trotzdem nachgeführt."""
    sig = state.load("signals.json", [])
    last = state.load("last.json", {})
    prev = {"hit": set(last.get("hit", [])), "fast": set(last.get("fast", [])), "trend": set(last.get("trend", [])),
            "soft": set(last.get("soft", []))}
    known = {(s["t"], s["k"], s["d"]) for s in sig}
    from .universe import company_key
    recent, firm = {}, {}
    for s in sig:                                  # letztes Signal je Aktie/Art und je Firma/Art (Doppel-Listings)
        recent[(s["t"], s["k"])] = max(recent.get((s["t"], s["k"]), ""), s["d"])
        ck = company_key(s.get("n") or "")
        if len(ck) > 2:
            firm[(ck, s["k"])] = max(firm.get((ck, s["k"]), ""), s["d"])
    new = []
    cand = [(r, "hit" if r["passed"] else "fast" if r.get("fast_hit") else None, r.get("plan") or {}) for r in rows]
    cand += [(r, "trend", r["tr"].get("plan") or {}) for r in rows if (r.get("tr") or {}).get("ok")]   # zweites Setup
    cand += [(r, "soft", r.get("plan") or {}) for r in rows if r.get("mbi_soft")]   # 10/11 nur MBI-Abklingen fehlt → 4H-Setup
    for r, k, p in (cand if record else []):
        if not k or not p.get("stop") or not p.get("entry"):
            continue
        d = r.get("date") or today
        lastd = recent.get((r["ticker"], k))
        if (r["ticker"], k, d) in known:
            continue
        # schon beim letzten Scan dabei: nur überspringen, wenn die laufende Phase auch gespeichert ist
        # (sonst fehlte das Signal für immer – z. B. wenn ein Lauf tagsüber den Stand vorweggenommen hatte)
        if r["ticker"] in prev[k] and lastd and (pd.Timestamp(d) - pd.Timestamp(lastd)).days <= 60:
            continue
        if lastd and (pd.Timestamp(d) - pd.Timestamp(lastd)).days <= GAP + 2:
            continue
        ck = company_key(r.get("name") or "")
        fd = firm.get((ck, k)) if len(ck) > 2 else None
        if fd and (pd.Timestamp(d) - pd.Timestamp(fd)).days <= GAP + 2:   # dieselbe Firma schon über eine andere Börse
            continue
        s = {"t": r["ticker"], "n": (r.get("name") or r["ticker"])[:40], "k": k, "d": d, "score": r.get("score", 0),
             "entry": p["entry"], "stop": p["stop"], "t1": p.get("target1"), "t2": p.get("target2"), "crv": p.get("crv"),
             "region": r.get("region"), "grade": (r.get("grade") or {}).get("g"), "res": "running"}
        sn = r.get("senti") or {}                  # Analysten-Kursziel am Signaltag (für KAIROZ – später nicht mehr rekonstruierbar)
        if (sn.get("tgt") or {}).get("m"):
            s.update(tg=sn["tgt"]["m"], tup=sn["tgt"].get("up"), na=(sn.get("an") or {}).get("n"))
        if (r.get("flags") or {}).get("volatility"):
            s["vol"] = round(float(r["flags"]["volatility"]), 3)
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
        if len(ck) > 2:
            firm[(ck, k)] = d
    # Ergebnisse nachführen
    for s in sig:
        if s.get("final") and (s["k"] != "hit" or all((s.get(k) or {}).get("res") in DONE for k in ("st", "st60"))):
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
        for key, extra in (("st", None), ("st60", RULE60)):
            if s["k"] == "hit" and (s.get(key) or {}).get("res") not in DONE:
                try:
                    s[key] = strat(df, idx, extra)
                except Exception as exc:           # Bilanz darf den Scan nie stoppen
                    print("Strategie-Bilanz:", s["t"], repr(exc)[:100])
    state.save("signals.json", sig)
    if record:                                     # Läufe tagsüber nicht merken – sonst gälten deren Treffer abends als „schon bekannt“
        state.save("last.json", {"date": today, "hit": [r["ticker"] for r in rows if r["passed"]],
                                 "fast": [r["ticker"] for r in rows if r.get("fast_hit")],
                                 "trend": [r["ticker"] for r in rows if (r.get("tr") or {}).get("ok")],
                                 "soft": [r["ticker"] for r in rows if r.get("mbi_soft")],
                                 "met": {r["ticker"]: r.get("met") for r in rows}})
    try:
        bt = json.loads((ROOT / "data" / "bilanz_backtest.json").read_text(encoding="utf-8"))
    except Exception:
        bt = None
    done = [s for s in sig if s.get("res") not in (None, "running")]
    out = {"generated": today, "live": {"since": min((s["d"] for s in sig), default=today), "n": len(sig),
                                        "stats": stats(done) if done else None, "strat": strat_stats(sig), "strat60": strat_stats(sig, "st60"),
                                        "grade": {g: _agg([x for x in done if x["k"] == "hit" and x.get("grade") == g]) for g in "ABC"}},
           "signals": _show(sig), "new": [s["t"] for s in new], "backtest": bt}
    return out
