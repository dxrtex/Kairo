"""E2-Schattentest (nur Forschung): dieselben Kairo-Treffer wie B60, aber Einstieg per Buy-Stop über dem Basishoch.

Stand: Grundlage, NICHT aktiv. Er beeinflusst weder Scanner, App, Live-Bilanz noch die Papier-Depots (eigene Datei
e2_shadow.json). Gestartet wird er erst mit Freigabe – und zählt dann nur Signale ab dem Starttag (keine Rückrechnung).

Regel E2 (eingefroren wie in research/ultimate/round1.py, Variante E2):
- Signal = Kairo-Treffer 11/11 (signals.json, k = "hit", Region USA/Europa) – exakt dieselben Signale wie B60.
- Basis: in den 10 Handelstagen nach dem Signal die ersten 5 Kerzen mit Spanne ≤ 1,5 ATR (ATR 14 am Signaltag);
  das Tief der 10 Tage bis zum Signal darf nicht unterschritten werden (sonst „Basis gebrochen“).
- Ab dem Tag nach der fertigen Basis liegt ein Buy-Stop bei Basishoch + 0,05 ATR, höchstens 10 Handelstage gültig.
  Kauf, sobald das Tageshoch den Stop-Kurs erreicht (zum Stop-Kurs oder zur höheren Eröffnung). Eröffnung über
  Basishoch + 0,5 ATR → verfällt (Kurslücke). Tief unter der Basis vor dem Auslösen → verfällt.
- Stop = Basistief − 0,25 ATR; Risiko Kauf–Stop muss 0,5–3 ATR sein. Tief am Kauftag unter dem Stop = ausgestoppt.
- Ausstieg wie B60: Stop (Eröffnung darunter → zur Eröffnung), ab Tag 10 Schluss unter EMA 20 → nächste Eröffnung,
  spätestens Schluss Tag 60.
- Auch NICHT ausgelöste Orders werden mit Grund festgehalten (nobase, basis_gebrochen, nicht_ausgelöst, kurslücke,
  risiko_atr) – sonst wäre der Vergleich mit B60 geschönt.
- R brutto, mit Basis-Kosten (halber Spread 0,1 % je Seite = 0,05 %) und Stress-Kosten (doppelter Spread + 0,05 % Schlupf
  = 0,15 % je Seite) wie in der Forschungs-Engine; Fremdwährungsgebühr und 0,99 € unter 250 € hängen von der Ordergröße ab
  und sind nicht enthalten. Geschätzte Kosten, kein gemessener Spread.
- Parität (geprüft 01.11.2026) mit research/ultimate/round1.py orders_E2 + strategy_championship/engine.py: Basis-Suche,
  Invalidierung über das 10-Tage-Tief, Buy-Stop-Kurs, Verfall bei Kurslücke über Basishoch + 0,5 ATR, Abbruch bei Bruch der
  Basis, 0,5–3-ATR-Risiko, Stop am Kauftag (Tief unter Stop = ausgestoppt, vorsichtig), EMA-20-Ausstieg ab Tag 10 zur
  nächsten Eröffnung, Zeitausstieg zum Schluss von Tag 60. Bei unklarer Reihenfolge von Hoch und Tief am Kauftag gilt
  immer die ungünstige Annahme (erst Kauf, dann Stop).

Jeder Lauf rechnet offene Signale aus den Tageskerzen neu (robust gegen ausgefallene oder doppelte Läufe);
abgeschlossene Einträge werden eingefroren und nie mehr verändert.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from backend.indicators import atr as _atr
from backend.rule import KAIRO

RULE = {"version": "E2-schatten-1", "wait": KAIRO["wait"], "ck": KAIRO["ck"], "cm": KAIRO["cm"], "inv": KAIRO["inv"],
        "buf": KAIRO["buf"], "risk_atr": KAIRO["risk_atr"], "trig": 0.05, "cap": 0.5, "valid": 10,
        "hold": KAIRO["hold"], "ema": KAIRO["ema"], "ema_from": KAIRO["ema_from"]}
COST_SIDE, COST_STRESS = 0.0005, 0.0015
REGIONS = ("us", "europe")
FILE = "e2_shadow.json"
FINAL = ("stop", "ema", "zeit", "nobase", "basis_gebrochen", "nicht_ausgelöst", "kurslücke", "risiko_atr")


def load(d: Path) -> dict:
    p = d / FILE
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"rule": RULE, "start": None, "items": {}}


def save(d: Path, book: dict) -> None:
    (d / FILE).write_text(json.dumps(book, indent=1, ensure_ascii=False, default=str), encoding="utf-8")


def simulate(df: pd.DataFrame, d: str, rule: dict = RULE) -> dict:
    """Ein Signal vom Signaltag d bis zur letzten Kerze. Rückgabe: res (wait/armed/open/… oder ein FINAL-Grund) + Details."""
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    idx = df.index
    i = int(idx.searchsorted(pd.Timestamp(d), side="right") - 1)
    if i < 20:
        return {"res": "nobase", "why": "zu wenig Kursdaten"}
    o, h, l, c = (df[k].to_numpy(float) for k in ("Open", "High", "Low", "Close"))
    a = float(_atr(df).iloc[i])
    if not a > 0:
        return {"res": "nobase", "why": "ATR fehlt"}
    inv = l[max(0, i - rule["inv"] + 1): i + 1].min()
    n, ck = len(c), rule["ck"]
    k0 = None
    for j in range(rule["wait"]):
        k = i + 1 + j
        if k >= n:
            return {"res": "wait", "atr": round(a, 4)}
        if l[k] < inv:
            return {"res": "basis_gebrochen", "day": str(idx[k].date())}
        if j < ck - 1:
            continue
        if h[k - ck + 1: k + 1].max() - l[k - ck + 1: k + 1].min() <= rule["cm"] * a:
            k0 = k
            break
    if k0 is None:
        return {"res": "nobase", "why": "keine Seitwärtsphase in 10 Tagen"}
    bh, bl = float(h[k0 - ck + 1: k0 + 1].max()), float(l[k0 - ck + 1: k0 + 1].min())
    trig, cap, stop = bh + rule["trig"] * a, bh + rule["cap"] * a, bl - rule["buf"] * a
    base = {"atr": round(a, 4), "base_day": str(idx[k0].date()), "trig": round(trig, 4), "cap": round(cap, 4), "sl": round(stop, 4)}
    e = ek = None
    for k in range(k0 + 1, k0 + 1 + rule["valid"]):
        if k >= n:
            return {"res": "armed", **base}
        if o[k] > cap:
            return {"res": "kurslücke", "day": str(idx[k].date()), **base}
        if h[k] >= trig:
            e, ek = max(o[k], trig), k
            break
        if l[k] < bl:
            return {"res": "basis_gebrochen", "day": str(idx[k].date()), **base}
    if e is None:
        return {"res": "nicht_ausgelöst", **base}
    risk = e - stop
    if not (rule["risk_atr"][0] * a <= risk <= rule["risk_atr"][1] * a):
        return {"res": "risiko_atr", "e": round(e, 4), **base}
    ema = pd.Series(c).ewm(span=rule["ema"], adjust=False).mean().to_numpy()
    buy = {"buy_day": str(idx[ek].date()), "e": round(e, 4)}
    R = lambda x, day, k: {"x": round(x, 4), "exit_day": str(idx[k].date()), "days": day,
                           "r": round((x - e) / risk, 3), "r_net": round((x * (1 - COST_SIDE) - e * (1 + COST_SIDE)) / risk, 3),
                           "r_stress": round((x * (1 - COST_STRESS) - e * (1 + COST_STRESS)) / risk, 3)}
    for day, k in enumerate(range(ek, n), start=1):
        if day > 1 and o[k] <= stop:
            return {"res": "stop", **base, **buy, **R(o[k], day, k)}
        if l[k] <= stop:
            return {"res": "stop", **base, **buy, **R(stop, day, k)}
        if day >= rule["ema_from"] and c[k] < ema[k] and k + 1 < n:
            return {"res": "ema", **base, **buy, **R(o[k + 1], day + 1, k + 1)}
        if day >= rule["hold"]:
            return {"res": "zeit", **base, **buy, **R(c[k], day, k)}
    k = n - 1
    return {"res": "open", **base, **buy, "now": round(float(c[k]), 4), "days": n - ek, "r": round((c[k] - e) / risk, 3)}


def step(book: dict, signals: list[dict], prices: dict[str, pd.DataFrame], today: str) -> dict:
    """Täglicher Lauf. Beim ersten Lauf wird der Starttag gesetzt; nur Treffer ab diesem Tag zählen."""
    if not book.get("start"):
        book["start"] = today
    items = book.setdefault("items", {})
    for s in signals:
        if s.get("k") != "hit" or s.get("region") not in REGIONS or s["d"] < book["start"]:
            continue
        key = f"{s['t']}|{s['d']}"
        cur = items.get(key)
        if cur and cur.get("res") in FINAL:
            continue                                   # eingefroren
        df = prices.get(s["t"])
        if df is None or df.empty:
            items.setdefault(key, {"t": s["t"], "d": s["d"], "res": "wait", "why": "keine Kurse"})
            continue
        try:
            r = simulate(df, s["d"])
        except Exception as exc:                       # ein Fehler bei einer Aktie stoppt den Lauf nicht
            r = {"res": (cur or {}).get("res", "wait"), "err": repr(exc)[:100]}
        items[key] = {"t": s["t"], "d": s["d"], "b60": (s.get("st60") or {}).get("res"), **r, "upd": today}
    book["updated"] = today
    return book


def summary(book: dict) -> dict:
    """Vergleichstabelle: Anzahl je Ergebnis, Kaufquote, Ø R (brutto/netto) der abgeschlossenen Käufe."""
    it = list((book.get("items") or {}).values())
    done = [x for x in it if x.get("res") in ("stop", "ema", "zeit")]
    cnt: dict = {}
    for x in it:
        cnt[x.get("res")] = cnt.get(x.get("res"), 0) + 1
    out = {"start": book.get("start"), "n": len(it), "status": cnt, "closed": len(done)}
    if done:
        out.update(r=round(float(np.mean([x["r"] for x in done])), 3), r_net=round(float(np.mean([x["r_net"] for x in done])), 3),
                   r_stress=round(float(np.mean([x.get("r_stress", x["r_net"]) for x in done])), 3),
                   win=round(float(np.mean([x["r"] > 0 for x in done])), 3),
                   days=round(float(np.mean([x["days"] for x in done])), 1))
    filled = [x for x in it if x.get("res") in ("open", "stop", "ema", "zeit")]
    decided = [x for x in it if x.get("res") not in ("wait", "armed")]
    out["fill_rate"] = round(len(filled) / len(decided), 3) if decided else None       # Kaufquote: gekauft / entschieden
    b60 = [x for x in it if x.get("b60") in ("stop", "ema", "zeit", "run")]
    out["b60_filled"] = len(b60)                                                       # dieselben Signale: B60 hatte Einstieg
    return out
