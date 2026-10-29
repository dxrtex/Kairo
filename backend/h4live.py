"""4H-Top-Setup live: Kairo-Treffer (11/11) → Seitwärtsphase → 4H-Bestätigung → Kauf → Verkauf unter der EMA 20.

Genau die Regeln aus dem 4H-Test (h4study.py, Variante „HB|RMBS|zeit“, Okt. 2026: +0,39 / +0,54 R je Trade gegenüber
+0,10 / +0,11 R ohne 4H, Depot +14 % / +20 % p. a.):
  1. Kairo-Treffer am Tag d (alle 11 Kriterien, Tageschart).
  2. Seitwärtsphase wie bisher (shortswing.simulate, QRULE): innerhalb von 10 Tagen 5 Tage eng (Spanne ≤ 1,5 ATR),
     Invalidierung hält, nächste Eröffnung innerhalb der Basis. Stop = Basistief − 0,25 ATR.
  3. 4H-Bestätigung frühestens ab der letzten 4H-Kerze des Basistags, spätestens 10 Handelstage nach dem Einstiegstag:
     in derselben 4H-Kerze gleichzeitig RSI zuletzt ≤ 40 und steigend, MACD-Kreuz nach oben, grünes MBI-X (beides in den
     letzten 6 4H-Kerzen) und Strukturbruch (Schluss über dem Hoch der 6 Kerzen davor).
  4. Kauf zur Eröffnung der nächsten 4H-Kerze. Nur wenn Stop darunter und 0,4–25 % entfernt.
  5. Verkauf am Stop (auch untertags); ab Tag 10 (Einstiegstag = Tag 1) zur nächsten Eröffnung, sobald ein Tag unter der
     EMA 20 (Tagesschlusskurse) schließt; spätestens zum Schluss von Tag 40. Im Ausstiegs-Test (Okt. 2026) +0,73 / +0,63 R
     je Trade statt +0,49 / +0,67 R mit „Tag 20“, Depot +43 % / +31 % statt +20 % / +26 % p. a., kleinere Rückgänge.
     Die alte Regel läuft als Gegenprobe mit (r20 / res20), damit die Bilanz beide live vergleicht.

Nur abgeschlossene 4H-Kerzen zählen – ein Signal mitten in der Kerze kann wieder verschwinden.
Ausnahme (Okt. 2026, Feinregel-Test): Fast-Treffer, denen nur das Abklingen beim MBI fehlt (frisches grünes X, Rot noch
über 70 % der Spitze), laufen genauso durchs 4H-Setup – Kennzeichen „soft“, in der Bilanz getrennt gezählt.
Übrige Fast-Treffer und 9/11 bekommen nur den Setup-Zustand (Seitwärtsphase, 4H-Signale) zur Information – kein Handelssignal.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from .h4study import COST, to4h
from .indicators import atr as _atr
from .scanner import calm_days
from .shortswing import QRULE

NEED = ("R40", "M", "B", "S")
WINDOW = 10                                        # 4H-Fenster: bis 10 Handelstage nach dem Einstiegstag der Basis
HOLD = 40                                          # spätestens Tag 40 (Okt. 2026: EMA-Ausstieg statt Tag 20)
EMA_SPAN, EMA_FROM = 20, 10                        # ab Tag 10: Tagesschluss unter der EMA 20 → Verkauf zur nächsten Eröffnung
FLAG_DE = {"R40": "RSI", "M": "MACD", "B": "MBI", "S": "Bruch"}


# ---------------------------------------------------------------- Daten
def hourly(tickers: list[str], period: str = "180d", batch: int = 40) -> dict[str, pd.DataFrame]:
    """Stundenkerzen (wie im Test: auto_adjust, 60m). Fehlende Aktien einmal nachladen."""
    import yfinance as yf
    out, todo = {}, list(dict.fromkeys(tickers))
    for rnd in range(2):
        failed = []
        for i in range(0, len(todo), batch):
            part = todo[i:i + batch]
            try:
                d = yf.download(part, period=period, interval="60m", auto_adjust=True, progress=False, threads=True, group_by="ticker")
                for t in part:
                    try:
                        x = (d[t] if isinstance(d.columns, pd.MultiIndex) else d)[["Open", "High", "Low", "Close"]].dropna()
                        (out.__setitem__(t, x) if len(x) > 60 else failed.append(t))
                    except Exception:
                        failed.append(t)
            except Exception as exc:
                print("4H: Download-Fehler", repr(exc)[:120])
                failed += part
            time.sleep(1)
        if not failed:
            break
        todo = failed
        time.sleep(10)
    return out


def complete_only(x: pd.DataFrame, now: datetime | None = None) -> pd.DataFrame:
    """Nur abgeschlossene Stundenkerzen (Start + 80 Min. vorbei – Yahoo liefert teils 15 Min. verzögert) und nur
    vollständige 4H-Gruppen: 4 Stunden, oder der Handelstag ist zu Ende (so viele Stunden wie an normalen Tagen)."""
    if x is None or not len(x):
        return x
    now = now or datetime.now(timezone.utc)
    idx = x.index.tz_convert("UTC") if x.index.tz is not None else x.index.tz_localize("UTC")
    x = x[idx + pd.Timedelta(minutes=80) <= pd.Timestamp(now)]
    if not len(x):
        return x
    idx = x.index.tz_convert(None) if x.index.tz is not None else x.index
    day = idx.normalize()
    per_day = pd.Series(1, index=day).groupby(level=0).sum()
    full = int(per_day.iloc[:-1].tail(15).mode().max()) if len(per_day) > 1 else 99
    last = day[-1]
    n_last = int(per_day.iloc[-1])
    if n_last >= full:
        return x                                   # Handelstag vollständig
    keep = (n_last // 4) * 4                       # heute: nur volle 4er-Gruppen
    mask = np.ones(len(x), bool)
    mask[np.flatnonzero(day == last)[keep:]] = False
    return x[mask]


# ---------------------------------------------------------------- Tageschart: Seitwärtsphase
def _px(df: pd.DataFrame, idx: int) -> dict:
    c0 = float(df["Close"].iloc[idx])
    a = float(_atr(df).iloc[idx]) / c0 if c0 else 0
    nx = lambda k: [float(v) / c0 for v in df[k].iloc[idx + 1:]]
    return {"o": nx("Open"), "h": nx("High"), "l": nx("Low"), "c": nx("Close"), "atr": a, "c0": c0,
            "pl": [float(v) / c0 for v in df["Low"].iloc[max(0, idx - 9):idx + 1]],
            "calm": [bool(x) for x in calm_days(df)[idx + 1:]]}


def base_state(px: dict, r: dict = QRULE, today_open: float | None = None) -> dict:
    """Seitwärtsphase wie shortswing.simulate (entry="base"), aber auch für noch laufende Fälle:
    basis (wartet, Tag x/10) · weg (gescheitert / keine Basis) · base (Basis fertig; s = Einstiegstag, pending = morgen).
    today_open: Eröffnung des laufenden Tages (tagsüber), prüft eine gestern fertig gewordene Basis."""
    o, h, l = px["o"], px["h"], px["l"]
    atr, n = px["atr"], len(px["c"])
    if not atr or atr != atr:
        return {"st": "weg", "why": "keine Daten"}
    inv = min(px["pl"][-r["inv"]:])
    k, m, wait, buf = r["ck"], r["cm"], r["wait"], r["buf"]

    def check(e, lo):
        sl = lo - buf * atr
        if e <= sl:
            return "Eröffnung unter dem Stop"
        if e - sl > r.get("maxd", 3.0) * atr:
            return "Stop zu weit"
        if e - sl < 0.5 * atr:
            return "Stop zu eng"
        return None

    unruhig = False
    for j in range(min(wait, n)):
        if l[j] < inv:
            return {"st": "weg", "why": "Signal gescheitert (unter das Tief gefallen)"}
        if j < k - 1:
            continue
        hi, lo = max(h[j - k + 1:j + 1]), min(l[j - k + 1:j + 1])
        if hi - lo > m * atr:
            unruhig = False
            continue
        if r.get("calm") and px.get("calm") is not None and not (j < len(px["calm"]) and px["calm"][j]):
            unruhig = True                         # Seitwärtsphase da, aber noch zu unruhig → weiter warten
            continue
        unruhig = False
        if j + 1 < n:
            oj = o[j + 1]
        elif today_open is not None:
            oj = today_open
        else:
            return {"st": "base", "s": j + 1, "hi": hi, "lo": lo, "sl": lo - buf * atr, "pending": True}
        if oj > hi or oj <= lo:
            continue
        why = check(oj, lo)
        if why:
            return {"st": "weg", "why": why}
        return {"st": "base", "s": j + 1, "hi": hi, "lo": lo, "sl": lo - buf * atr, "e": oj}
    if n - 1 >= wait or (today_open is not None and n >= wait):
        return {"st": "weg", "why": "keine ruhige Seitwärtsphase in 10 Tagen"}
    return {"st": "basis", "day": n, **({"unruhig": True} if unruhig else {})}


# ---------------------------------------------------------------- 4H
def _flags_at(b: pd.DataFrame, j: int) -> dict:
    return {k: bool(b[k].iat[j]) for k in NEED}


def evaluate(df: pd.DataFrame, d: str, hx: pd.DataFrame | None, now: datetime | None = None,
             intraday: bool = False) -> dict:
    """Status eines Kairo-Treffers vom Tag d. df = Tageskerzen (abgeschlossen; tagsüber ohne den laufenden Tag),
    hx = Stundenkerzen. Rückgabe für die App und die Mitteilungen (Preise absolut)."""
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    idx = int(df.index.searchsorted(pd.Timestamp(d), side="right") - 1)
    if idx < 15 or str(df.index[idx].date()) != d:
        return {"st": "weg", "why": "keine Tageskerze am Signaltag"}
    px = _px(df, idx)
    c0 = px["c0"]
    today_open = None
    b = None
    if hx is not None and len(hx):
        hc = complete_only(hx, now)
        try:
            b = to4h(hc) if hc is not None and len(hc) > 40 else None
        except Exception:
            b = None
        if intraday:                               # Eröffnung des laufenden Tages aus den Stundenkerzen
            hi_ = hx.index.tz_convert(None) if hx.index.tz is not None else hx.index
            last_day = hi_.normalize()[-1]
            if last_day > df.index[-1].normalize():
                today_open = float(hx["Open"][hi_.normalize() == last_day].iloc[0]) / c0
    bs = base_state(px, QRULE, today_open)
    out = {"d": d, "c0": round(c0, 4), "days": len(px["c"]) + (today_open is not None)}
    if bs["st"] == "weg":
        return {**out, "st": "weg", "why": bs["why"]}
    if bs["st"] == "basis":
        return {**out, "st": "basis", "day": bs["day"], "left": QRULE["wait"] - bs["day"], **({"unruhig": True} if bs.get("unruhig") else {}),
                **({"fl": _flags_at(b, len(b) - 1), "bar": str(b.index[-1])} if b is not None and len(b) else {})}
    s, sl = bs["s"], bs["sl"] * c0
    dates = [str(x.date()) for x in df.index[idx + 1:]]
    base_day = dates[s - 1]
    entry_day = dates[s] if s < len(dates) else None
    out.update({"base": {"hi": round(bs["hi"] * c0, 4), "lo": round(bs["lo"] * c0, 4), "sl": round(sl, 4), "bd": base_day,
                         "ed": entry_day, "pending": bool(bs.get("pending"))}})
    lim_n = s + WINDOW                             # 4H-Auslöser erlaubt bis Handelstag s+10 nach dem Signal (inkl.)
    lim = dates[lim_n] if lim_n < len(dates) else None
    out["lim"] = lim
    out["lim_left"] = max(0, lim_n - (len(dates) - 1)) if lim is None else 0
    if b is None or not len(b):
        return {**out, "st": "4h", "why": "keine Stundenkerzen"}
    days = np.array([str(x.date()) for x in b["day"]])
    start = np.flatnonzero(days <= base_day)
    if not len(start):
        return {**out, "st": "4h", "why": "Stundenkerzen zu kurz"}
    j0 = max(1, int(start[-1]))
    fl = {k: b[k].to_numpy(bool) for k in NEED}
    trig = None
    for j in range(j0, len(b)):
        if lim is not None and days[j] > lim:
            break
        if all(fl[k][j] for k in NEED):
            trig = j
            break
    out["fl"], out["bar"] = _flags_at(b, len(b) - 1), str(b.index[-1])
    if trig is None:
        if lim is not None and days[-1] >= lim:
            return {**out, "st": "weg", "why": "keine 4H-Bestätigung im Fenster"}
        return {**out, "st": "4h"}
    out["trig"] = {"at": str(b.index[trig]), "fl": _flags_at(b, trig), "c": round(float(b["Close"].iat[trig]), 4)}
    if trig + 1 >= len(b):                          # bestätigt – Kauf zur Eröffnung der nächsten 4H-Kerze
        c = float(b["Close"].iat[trig])
        if not (sl < c) or (c - sl) / c > 0.25 or (c - sl) / c < 0.004:
            return {**out, "st": "weg", "why": "Kurs zu nah am / unter dem Stop"}
        return {**out, "st": "go"}
    e = float(b["Open"].iat[trig + 1])
    if not (sl < e) or (e - sl) / e > 0.25 or (e - sl) / e < 0.004:
        return {**out, "st": "weg", "why": "Einstieg zu nah am / unter dem Stop"}
    o_, l_, c_ = (b[k].to_numpy(float) for k in ("Open", "Low", "Close"))
    risk = e - sl
    cost = COST * e / risk
    R = lambda x: round((x - e) / risk - cost, 3)
    ud = list(dict.fromkeys(days[trig + 1:]))
    ema, last = _ema_daily(b)
    out["trade"] = {"e": round(e, 4), "sl": round(sl, 4), "ed": str(days[trig + 1]), "ti": str(b.index[trig + 1])}
    # Gegenprobe (Schatten): alte Regel „Verkauf an Tag 20“ auf demselben Trade
    sh = _t20(days, o_, l_, c_, trig + 1, sl, ud)
    if sh:
        out["trade"].update(r20=R(sh[0]), res20=sh[1])
    end_day = ud[HOLD - 1] if len(ud) >= HOLD else None
    out["trade"]["xd"] = end_day
    for j in range(trig + 1, len(b)):
        if end_day is not None and days[j] > end_day:
            break
        if l_[j] <= sl:
            x = min(sl, o_[j]) if j > trig + 1 else sl
            out["trade"].update(x=round(x, 4), r=R(x), res="stop", xd=str(days[j]))
            return {**out, "st": "stop"}
        dn = ud.index(days[j]) + 1                 # Handelstag des Trades (1 = Kauftag)
        if dn >= EMA_FROM and last[j] and c_[j] < ema[j] and days[j] != end_day:
            out["trade"].update(ema=round(float(ema[j]), 4), xc=round(float(c_[j]), 4), sig=str(days[j]), day=dn)
            if j + 1 < len(b):                     # Verkauf zur Eröffnung der nächsten 4H-Kerze (nächster Handelstag)
                x = o_[j + 1]
                out["trade"].update(x=round(x, 4), r=R(x), res="ema", xd=str(days[j + 1]))
                return {**out, "st": "ema"}
            out["trade"].update(now=round(float(c_[j]), 4), r=R(c_[j]))
            return {**out, "st": "sell"}
    if end_day is not None:
        jx = int(np.flatnonzero(days == end_day)[-1])
        x = c_[jx]
        out["trade"].update(x=round(x, 4), r=R(x), res="zeit")
        return {**out, "st": "zeit"}
    x = c_[-1]
    dn = len(ud)
    out["trade"].update(now=round(x, 4), r=R(x), day=dn, ema=round(float(ema[-1]), 4))
    return {**out, "st": "run"}


def _ema_daily(b: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """EMA 20 der Tagesschlusskurse (aus den 4H-Kerzen, wie im Test) je 4H-Kerze und ob die Kerze den Tag abschließt.
    Die letzte Kerze schließt den Tag nur, wenn der Tag vollständig ist (so viele 4H-Kerzen wie an normalen Tagen)."""
    dc = b.groupby("day")["Close"].last()
    ema = b["day"].map(dc.ewm(span=EMA_SPAN, adjust=False).mean()).to_numpy(float)
    last = (b["day"] != b["day"].shift(-1)).to_numpy()
    per = b.groupby("day").size()
    full = int(per.iloc[:-1].tail(15).mode().max()) if len(per) > 1 else 99
    if int(per.iloc[-1]) < full:
        last[-1] = False
    return ema, last


def _t20(days, o_, l_, c_, i0: int, sl: float, ud: list) -> tuple[float, str] | None:
    """Alte Regel: Stop oder Schluss von Tag 20 (für die Gegenprobe in der Bilanz)."""
    end = ud[19] if len(ud) >= 20 else None
    for j in range(i0, len(days)):
        if end is not None and days[j] > end:
            break
        if l_[j] <= sl:
            return (min(sl, o_[j]) if j > i0 else sl), "stop"
    if end is None:
        return None
    return c_[int(np.flatnonzero(days == end)[-1])], "zeit"


def setup_now(df: pd.DataFrame, hx: pd.DataFrame | None) -> dict | None:
    """Setup-Zustand heute (für Fast-Treffer, 9/11 und frische Treffer): Seitwärtsphase (5 Tage ≤ 1,5 ATR) und
    welche 4H-Signale an der letzten abgeschlossenen 4H-Kerze stehen. Nur Information – kein Handelssignal."""
    try:
        df = df.dropna(subset=["High", "Low", "Close"])
        a = float(_atr(df).iloc[-1])
        k = QRULE["ck"]
        rng = float(df["High"].iloc[-k:].max() - df["Low"].iloc[-k:].min())
        out = {"b": bool(a and rng <= QRULE["cm"] * a), "br": round(rng / a, 2) if a else None}
        if hx is not None and len(hx) > 40:
            b = to4h(hx)
            out["fl"] = "".join(k2[0] for k2 in NEED if bool(b[k2].iat[-1]))
        return out
    except Exception:
        return None


# ---------------------------------------------------------------- Live-Bilanz der 4H-Trades
def track(old: list[dict], items: list[dict]) -> list[dict]:
    """Bestätigte 4H-Trades getrennt merken (Zustand), Ergebnis nachführen."""
    by = {(x["t"], x["d"]): x for x in old}
    for it in items:
        tr = it.get("trade")
        if not tr:
            continue
        key = (it["t"], it["d"])
        rec = by.get(key, {"t": it["t"], "n": it.get("n"), "d": it["d"], "grp": it.get("grp") or "11",
                           **({"soft": True} if it.get("soft") else {})})
        rec.update({"e": tr["e"], "sl": tr["sl"], "ed": tr["ed"], "res": tr.get("res") or ("sell" if it["st"] == "sell" else "run"),
                    "r": tr.get("r"), "xd": tr.get("xd"), "day": tr.get("day"), "r20": tr.get("r20"), "res20": tr.get("res20")})
        by[key] = rec
    return sorted(by.values(), key=lambda x: x["ed"], reverse=True)


def _st(done: list[dict]) -> dict:
    r = [x["r"] for x in done]
    r20 = [x["r20"] for x in done if x.get("r20") is not None]   # Gegenprobe: dieselben Trades mit „Verkauf an Tag 20“
    return {"n": len(done), "avg_r": round(sum(r) / len(r), 3) if r else None,
            "win": round(sum(v > 0 for v in r) / len(r), 3) if r else None,
            "n20": len(r20), "avg_r20": round(sum(r20) / len(r20), 3) if r20 else None}


def track_stats(rec: list[dict]) -> dict | None:
    """Kennzahlen der echten Einstiege (11/11 und „MBI gelockert“) und je Stufe getrennt (by: 11, 10s, 10, 9)."""
    if not rec:
        return None
    done = [x for x in rec if x.get("res") in ("stop", "zeit", "ema") and x.get("r") is not None]
    g = lambda x: x.get("grp") or ("10s" if x.get("soft") else "11")
    real = [x for x in done if g(x) in REAL]
    rs = [x["r"] for x in real if g(x) == "10s"]
    return {**_st(real), "open": sum(x.get("res") in ("run", "sell") and g(x) in REAL for x in rec),
            "n_soft": len(rs), "avg_r_soft": round(sum(rs) / len(rs), 3) if rs else None,
            "by": {k: {**_st([x for x in done if g(x) == k]), "open": sum(x.get("res") in ("run", "sell") and g(x) == k for x in rec)}
                   for k in ("11", "10s", "10", "9")}}


GRP = {"hit": "11", "soft": "10s", "fast": "10", "near": "9"}   # 10s = 10/11, nur MBI-Abklingen fehlt (zählt wie ein Treffer)
REAL = ("11", "10s")                                            # echte Einstiege; 10/11 und 9/11 nur zur Auswahl (Info, keine Mitteilung)


def candidates(sig: list[dict], today: str, days: int = 90) -> list[dict]:
    """Kairo-Treffer, deren Status noch offen sein kann: bis 10 Tage Basis + 10 Tage 4H-Fenster
    + bis 40 Tage halten ≈ 62 Handelstage ≈ 90 Kalendertage (je Aktie nur der jüngste Treffer)."""
    cut = (pd.Timestamp(today) - timedelta(days=days)).strftime("%Y-%m-%d")
    seen, out = set(), []
    # je Aktie ein Kandidat: der jüngste echte (11/11 bzw. MBI gelockert), sonst der jüngste 10/11, sonst 9/11
    pri = {"hit": 0, "soft": 0, "fast": 1, "near": 2}
    sel = sorted((x for x in sig if x.get("k") in pri and x["d"] >= cut), key=lambda x: x["d"], reverse=True)
    for s in sorted(sel, key=lambda x: pri[x["k"]]):                     # stabil: innerhalb der Stufe der jüngste zuerst
        if s["t"] in seen:
            continue
        seen.add(s["t"])
        out.append({"t": s["t"], "n": s.get("n") or s["t"], "d": s["d"], "cur": s.get("cur"), "grp": GRP[s["k"]],
                    **({"soft": True} if s["k"] == "soft" else {})})
    return out


def build(cands: list[dict], daily: dict[str, pd.DataFrame], hx: dict[str, pd.DataFrame], now: datetime | None = None,
          intraday: bool = False) -> list[dict]:
    items = []
    for c in cands:
        df = daily.get(c["t"])
        if df is None or not len(df):
            continue
        try:
            items.append({**c, **evaluate(df, c["d"], hx.get(c["t"]), now, intraday)})
        except Exception as exc:
            print(f"4H: {c['t']} Fehler {exc!r}")
    rank = {"sell": 0, "go": 0, "4h": 1, "basis": 2, "run": 3, "stop": 4, "zeit": 4, "ema": 4, "weg": 5}
    return sorted(items, key=lambda x: (rank.get(x["st"], 9), x["d"]))
