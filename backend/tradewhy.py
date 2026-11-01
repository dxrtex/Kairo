"""Warum ist ein Kairo-Trade gescheitert – und ließe sich das vorher erkennen? Ursachensuche und Lern-Bericht.

Grundlage sind die unveränderlichen Momentaufnahmen (backend/snapshots.py). Für jeden abgeschlossenen Treffer – Verlierer
UND Gewinner, sonst ließe sich nichts vergleichen – hält dieser Schritt einmalig fest (Feld „why“):

  Vorher erkennbar (am Signaltag bekannt → mögliche Filter):
    eng          Stop enger als 1 ATR                   weit         Stop weiter als 2,5 ATR
    momentum     Vormomentum über +25 %                  unruhig      ATR über 5 % des Kurses
    markt_rot    Marktlage am Signaltag rot              index_u200   Index unter seiner 200-Tage-Linie
    sektor_u50   Sektor-ETF unter seiner 50-Tage-Linie   zahlen_bald  Quartalszahlen ≤ 20 Handelstage nach dem Signal
    spaet        Signal erst nach einem Scan-Ausfall erkannt
  Erst hinterher sichtbar (Erklärung, kein Filter):
    markt_fiel   Index in der Haltezeit ≤ −3 %           sektor_fiel  Sektor-ETF in der Haltezeit ≤ −4 %
    eigenschwach Aktie ≥ 5 Prozentpunkte schwächer als der Index
    luecke       über den Stop gerissen (R < −1,15)     schnell      Stop in den ersten 3 Tagen
    zahlen       Quartalszahlen fielen in die Haltezeit

Der Lern-Bericht (report) vergleicht je „vorher erkennbarem“ Merkmal das Ø-Ergebnis mit und ohne Merkmal. Ein Merkmal
wird erst zum Kandidaten, wenn es genug Fälle hat, deutlich schlechter ist UND in der früheren wie der späteren Hälfte
der Trades in dieselbe Richtung zeigt. Kandidaten ändern die Regel NIE automatisch: Nächster Schritt ist der Backtest über
2008–2026 (13.241 Trades) mit Zeit-Trennung, danach ein Schattentest auf künftigen Signalen – und erst dann, mit Freigabe,
der Scanner. Merkmale, die schon getestet und verworfen wurden, stehen in TESTED und werden nicht erneut vorgeschlagen.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

PRE = {"eng": "Stop enger als 1 ATR", "weit": "Stop weiter als 2,5 ATR", "momentum": "Vormomentum über +25 %",
       "unruhig": "Schwankung (ATR) über 5 % des Kurses", "markt_rot": "Marktlage am Signaltag rot",
       "index_u200": "Index unter der 200-Tage-Linie", "sektor_u50": "Sektor unter der 50-Tage-Linie",
       "zahlen_bald": "Quartalszahlen ≤ 20 Handelstage nach dem Signal", "spaet": "Signal verspätet erkannt (Scan-Ausfall)"}
POST = {"markt_fiel": "Gesamtmarkt fiel in der Haltezeit", "sektor_fiel": "Sektor fiel in der Haltezeit",
        "eigenschwach": "Aktie deutlich schwächer als der Markt", "luecke": "Kurslücke über den Stop",
        "schnell": "Stop schon in den ersten 3 Tagen", "zahlen": "Quartalszahlen in der Haltezeit"}
# Schon geprüft (Forschung 2026) – nicht erneut vorschlagen, sondern mit dem Ergebnis anzeigen
TESTED = {"unruhig": "Ruhe-Filter (Q1, 31.10.2026): je Trade besser, im Depot nicht – bleibt aus",
          "zahlen_bald": "Quartalszahlen-Filter (N1, Ultimate 10/2026): nicht bestanden",
          "momentum": "Vormomentum ist schon die Rangfolge der Regel (schwächeres zuerst)"}
INDEX = {"us": "^GSPC", "europe": "^STOXX", "asia": "^GSPC"}
SECTOR_ETF = {"Technology": "XLK", "Financial Services": "XLF", "Healthcare": "XLV", "Consumer Cyclical": "XLY",
              "Consumer Defensive": "XLP", "Energy": "XLE", "Industrials": "XLI", "Basic Materials": "XLB",
              "Utilities": "XLU", "Real Estate": "XLRE", "Communication Services": "XLC"}
MIN_N, MIN_DIFF = 10, 0.25          # Kandidat: je ≥ 10 Fälle mit/ohne, Ø-Ergebnis mindestens 0,25 R schlechter


def _close(df) -> pd.Series | None:
    if df is None or getattr(df, "empty", True) or "Close" not in df:
        return None
    c = df["Close"].dropna()
    return c if len(c) else None


def _at(c: pd.Series, d) -> int:
    return int(c.index.searchsorted(pd.Timestamp(d), side="right") - 1)


def _ret(c: pd.Series | None, a, b) -> float | None:
    if c is None:
        return None
    i, j = _at(c, a), _at(c, b)
    if i < 0 or j <= i:
        return None
    return float(c.iloc[j] / c.iloc[i] - 1)


def _below(c: pd.Series | None, d, n: int) -> bool | None:
    if c is None:
        return None
    i = _at(c, d)
    if i < n - 1:
        return None
    return bool(c.iloc[i] < c.iloc[i - n + 1: i + 1].mean())


def _bdays(a, b) -> int:
    try:
        return int(np.busday_count(pd.Timestamp(a).date(), pd.Timestamp(b).date()))
    except Exception:
        return 99


def explain(sn: dict, stock=None, ctx: dict | None = None) -> dict:
    """Ursachen eines abgeschlossenen Treffers. stock = Tageskerzen der Aktie, ctx = Index-/Sektor-Kerzen (Ticker → DataFrame)."""
    g, x, ctx = sn["sig"], sn.get("exit") or {}, ctx or {}
    d, end = sn["d"], x.get("seen") or sn["d"]
    fl = g.get("flags") or {}
    idx = _close(ctx.get(INDEX.get(g.get("region") or "us", "^GSPC")))
    sec = _close(ctx.get(SECTOR_ETF.get(g.get("sector") or "", "")))
    st = _close(stock)
    pre = {
        "eng": g.get("stop_atr") is not None and g["stop_atr"] < 1.0,
        "weit": g.get("stop_atr") is not None and g["stop_atr"] > 2.5,
        "momentum": g.get("mom") is not None and g["mom"] > 0.25,
        "unruhig": (fl.get("atr_pct") or 0) > 0.05,
        "markt_rot": (g.get("market") or {}).get("tone") == "red",
        "index_u200": _below(idx, d, 200),
        "sektor_u50": _below(sec, d, 50),
        "zahlen_bald": bool(g.get("earn")) and 0 <= _bdays(d, g["earn"]) <= 20,
        "spaet": (sn.get("late") or 0) >= 2,
    }
    ri, rs, rk = _ret(idx, d, end), _ret(sec, d, end), _ret(st, d, end)
    r = x.get("r")
    post = {
        "markt_fiel": ri is not None and ri <= -0.03,
        "sektor_fiel": rs is not None and rs <= -0.04,
        "eigenschwach": rk is not None and ri is not None and rk - ri <= -0.05,
        "luecke": x.get("res") == "stop" and r is not None and r < -1.15,
        "schnell": x.get("res") == "stop" and (x.get("days") or 99) <= 3,
        "zahlen": bool(g.get("earn")) and d <= g["earn"] <= end,
    }
    return {"pre": sorted(k for k, v in pre.items() if v), "post": sorted(k for k, v in post.items() if v),
            "unk": sorted(k for k, v in pre.items() if v is None),
            "idx": None if ri is None else round(ri, 4), "sec": None if rs is None else round(rs, 4),
            "stock": None if rk is None else round(rk, 4)}


def analyze(snaps: dict, data: dict | None = None, ctx: dict | None = None) -> int:
    """Ergänzt „why“ für abgeschlossene Treffer, die noch keine Ursachensuche haben. Rückgabe: Anzahl neu."""
    n = 0
    for sn in snaps.values():
        x = sn.get("exit") or {}
        if sn.get("k") != "hit" or x.get("r") is None or "why" in sn:
            continue
        try:
            sn["why"] = explain(sn, (data or {}).get(sn["t"]), ctx)
            n += 1
        except Exception as exc:                     # darf den Scan nie stoppen
            print("Ursachensuche Trade:", sn.get("t"), repr(exc)[:100])
    return n


def _mean(v):
    return round(float(np.mean(v)), 3) if v else None


def report(snaps: dict) -> dict:
    """Lern-Bericht: häufigste Gründe bei Verlusten und vorher erkennbare Merkmale mit/ohne – inkl. Zeit-Trennung."""
    rows = sorted([sn for sn in snaps.values() if sn.get("k") == "hit" and "why" in sn and (sn.get("exit") or {}).get("r") is not None],
                  key=lambda s: s["d"])
    n = len(rows)
    out = {"n": n, "min_n": MIN_N, "losses": sum(s["exit"]["r"] <= 0 for s in rows), "avg_r": _mean([s["exit"]["r"] for s in rows]),
           "post": [], "pre": [], "recent": []}
    loss = [s for s in rows if s["exit"]["r"] <= 0]
    win = [s for s in rows if s["exit"]["r"] > 0]
    for k, lbl in POST.items():                      # Erklärungen: bei Verlusten häufiger als bei Gewinnen?
        fl = sum(k in s["why"]["post"] for s in loss)
        fw = sum(k in s["why"]["post"] for s in win)
        if fl or fw:
            out["post"].append({"k": k, "l": lbl, "loss": fl, "loss_pct": round(fl / len(loss), 3) if loss else None,
                                "win": fw, "win_pct": round(fw / len(win), 3) if win else None})
    out["post"].sort(key=lambda p: -(p["loss_pct"] or 0))
    half = n // 2
    for k, lbl in PRE.items():
        known = [s for s in rows if k not in s["why"].get("unk", [])]
        w = [s["exit"]["r"] for s in known if k in s["why"]["pre"]]
        wo = [s["exit"]["r"] for s in known if k not in s["why"]["pre"]]
        if not w:
            continue
        diff = (np.mean(w) - np.mean(wo)) if wo else None
        halves = []
        for part in (rows[:half], rows[half:]):
            a = [s["exit"]["r"] for s in part if k in s["why"]["pre"]]
            b = [s["exit"]["r"] for s in part if k not in s["why"]["pre"] and k not in s["why"].get("unk", [])]
            halves.append(round(float(np.mean(a) - np.mean(b)), 3) if a and b else None)
        if k in TESTED:
            status = "schon getestet"
        elif len(w) < MIN_N or len(wo) < MIN_N:
            status = "zu wenig Fälle"
        elif diff is not None and diff <= -MIN_DIFF and all(h is not None and h < 0 for h in halves):
            status = "Kandidat – Backtest"
        else:
            status = "kein Hinweis"
        out["pre"].append({"k": k, "l": lbl, "n": len(w), "r": _mean(w), "r_ohne": _mean(wo),
                           "diff": None if diff is None else round(float(diff), 3), "halves": halves, "status": status,
                           "note": TESTED.get(k)})
    out["pre"].sort(key=lambda p: (p["status"] != "Kandidat – Backtest", p["diff"] if p["diff"] is not None else 9))
    out["candidates"] = [p["k"] for p in out["pre"] if p["status"] == "Kandidat – Backtest"]
    for s in sorted(loss, key=lambda s: s["exit"].get("seen") or s["d"], reverse=True)[:8]:
        out["recent"].append({"t": s["t"], "d": s["d"], "r": s["exit"]["r"], "res": s["exit"]["res"],
                              "pre": [PRE[k] for k in s["why"]["pre"]], "post": [POST[k] for k in s["why"]["post"]]})
    return out
