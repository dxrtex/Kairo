"""Kairo Langfrist (23.11.2026): Momentum-Depot für langfristiges Investieren neben dem Welt-ETF.

Regel aus der Studie tools/research/momentum_variants.py (Auswahl nur im Lernzeitraum 2016–2020, bestätigt 2021–2026):
Zu jedem Tauschtermin die RULE["n"] US-Aktien mit dem stärksten Kursanstieg der letzten RULE["lb"] Monate ohne den
letzten Monat (12-1-Momentum), gleich gewichtet; Universum wie im Backtest: Ø Umsatz ≥ 5 Mio. $ am Tag, Kurs ≥ 5 $.
Tauschtermine: erster Handelstag im Januar/April/Juli/Oktober (bei RULE["every"] = 3).
Ohne Zustand: Das aktuelle Depot wird bei jedem Scan aus den Kursen bis zum letzten Tauschtermin neu bestimmt.
Reine Analyse/Anzeige – keine Orders.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

RULE = {"n": 20, "lb": 12, "every": 3, "filter": False}
MIN_ADV, MIN_PX = 5e6, 5.0
TOP_N = 60                     # so viele Plätze der Rangliste zeigt der Scanner (Top 20 = Depot, 21–60 = Nachrücker)
# Studie momentum_variants.py (23.11.2026, 1.586 US-Aktien, deutsche Steuer, 0,15 % Kosten je Umsatz):
# Lernen 2016–2020 37,3 % p. a. nach Steuer · Prüfen 2021–2026 25,2 % (S&P-500-ETF 11,7 %) · größter Rückgang bis 44 % (ETF 24 %)
# 35/36 Varianten im Lernzeitraum, 20/36 im Prüfzeitraum über dem ETF; Marktfilter schadet (Ø 7,5 % statt 23,8 %).
BACKTEST = {"period": "2016–2026", "learn": 0.373, "test": 0.252, "etf_test": 0.117, "mdd": 0.44, "etf_mdd": 0.24}


def _is_us(t: str, m: dict | None) -> bool:
    return "." not in t and "^" not in t and (not m or (m.get("currency") or "USD") == "USD")


def rebalance_dates(idx: pd.DatetimeIndex, every: int = 3) -> list[pd.Timestamp]:
    """Erster Handelstag jedes Tauschmonats (Jan/Apr/Jul/Okt bei every=3) im Index."""
    months = set(range(1, 13, every))
    s = pd.Series(idx, index=idx)
    firsts = s.groupby([idx.year, idx.month]).first()
    return [d for (y, m), d in firsts.items() if m in months]


def _score(df: pd.DataFrame, upto: pd.Timestamp, lb: int) -> tuple[float, float] | None:
    """12-1-Momentum (ohne letzten Monat) und Ø Umsatz 63 Tage, nur mit Kursen VOR dem Stichtag."""
    d = df[df.index < upto]
    c = d["Close"].dropna()
    if len(c) < lb * 21 + 5:
        return None
    a, b = float(c.iloc[-21]), float(c.iloc[-(lb * 21)])
    if not (a > 0 and b > 0) or float(c.iloc[-1]) < MIN_PX:
        return None
    adv = float((d["Close"] * d["Volume"]).tail(63).mean()) if "Volume" in d else 0.0
    if not np.isfinite(adv) or adv < MIN_ADV:
        return None
    return a / b - 1, adv


def rank(data: dict, meta: dict, upto: pd.Timestamp, rule: dict | None = None) -> list[tuple[str, float]]:
    r = {**RULE, **(rule or {})}
    sc = []
    for t, df in data.items():
        if not _is_us(t, meta.get(t)):
            continue
        try:
            s = _score(df, upto, r["lb"])
        except Exception:
            s = None
        if s:
            sc.append((t, s[0]))
    sc.sort(key=lambda x: -x[1])
    return sc


# ---------------------------------------------------------------- Watchlist: 8 Einstiegskriterien je Aktie (Auftrag 23.11.2026)
CHECKS = ("liq", "trend", "stab", "mom", "qual", "val", "sector", "earn")
WATCH_MIN, WATCH_MAX = 6, 40
CK = {"min_dv": 10e6, "min_mc": 2e9, "gap": -0.15, "earn_days": 5, "sector_cap": 3}


def load_fund() -> dict:
    """fund.json (Branch kairo-fund): ROE, Schulden, Cash, EV/EBITDA, PEG, Forward-KGV, Jahres-EPS, Monatskurse."""
    import json
    import subprocess
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    p = root / "site" / "data" / "fund.json"
    try:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8")).get("by") or {}
        subprocess.run(["git", "fetch", "-q", "origin", "kairo-fund"], cwd=root, capture_output=True, timeout=120)
        out = subprocess.run(["git", "show", "origin/kairo-fund:fund.json"], cwd=root, capture_output=True, timeout=120, check=True).stdout
        return json.loads(out).get("by") or {}
    except Exception as exc:
        print(f"Langfrist: fund.json nicht geladen ({exc!r}) – Quality/Value neutral")
        return {}


def pe_5y_avg(f: dict) -> float | None:
    """Ø KGV der letzten bis zu 5 Geschäftsjahre (Ø Monatskurs im Geschäftsjahr / EPS), plausibel ggü. aktuellem KGV."""
    fa, pxm = f.get("fa") or {}, f.get("pxm") or {}
    ys, eps, c = fa.get("y") or [], fa.get("eps") or [], pxm.get("c") or []
    if not ys or not c or not pxm.get("m0"):
        return None
    m0 = pd.Period(pxm["m0"], "M")
    mon = pd.Series(c, index=[(m0 + i).strftime("%Y-%m") for i in range(len(c))], dtype=float)
    mm = int((fa.get("fye") or "12-31").split("-")[0])
    pes = []
    for y, e in zip(ys, eps):
        if not e or e <= 0:
            continue
        end = pd.Period(f"{y}-{mm:02d}", "M")
        px = mon.reindex([(end - k).strftime("%Y-%m") for k in range(12)]).dropna()
        if len(px) >= 6:
            pes.append(float(px.mean()) / e)
    if not pes:
        return None
    avg = float(np.mean(pes[-5:]))
    pe = f.get("pe")
    if pe and pe > 0 and not (0.2 < avg / pe < 5):
        return None
    return avg if 0 < avg < 500 else None


def _fund_row(f: dict) -> dict:
    roe = f.get("roe")
    mc, debt, cash, evm = f.get("mc"), f.get("debt"), f.get("cash"), f.get("ev")
    nde = None
    if mc and evm and evm > 0 and debt is not None and cash is not None:
        ebitda = (mc + debt - cash) / evm
        nd = debt - cash
        nde = nd / ebitda if ebitda > 0 else (np.inf if nd > 0 else -1.0)
    peg = f.get("peg")
    fpe, p5 = f.get("fpe"), pe_5y_avg(f) if f else None
    rel = fpe / p5 if fpe and fpe > 0 and p5 else None
    peg = np.inf if peg is not None and peg <= 0 else peg            # PEG ≤ 0 (Gewinnrückgang) = schlechtester Wert
    return {"roe": roe, "nde": nde, "peg": peg, "rel": rel}


def _pct(vals: dict, higher_better: bool = True) -> dict:
    """Perzentil 0–100 innerhalb der Auswahl (fehlend bleibt fehlend)."""
    s = pd.Series({k: v for k, v in vals.items() if v is not None and v == v}, dtype=float)
    if not len(s):
        return {}
    if len(s) == 1:
        return {s.index[0]: 50.0}
    r = (s if higher_better else -s).rank(method="average")
    return ((r - 1) / (len(s) - 1) * 100.0).to_dict()


def _earn_soon(d, asof: pd.Timestamp, days: int) -> bool:
    if not d:
        return False
    try:
        e = pd.Timestamp(str(d)[:10])
    except Exception:
        return False
    return asof < e <= asof + pd.offsets.BDay(days)


def checks(data: dict, meta: dict, now: list[tuple[str, float]], depot: set, fund: dict, asof: pd.Timestamp) -> dict:
    """Je Aktie der Langfrist-Auswahl die 8 Kriterien (1 = erfüllt):
    Liquidität (Ø Umsatz 50 T. ≥ 10 Mio. $ und Börsenwert ≥ 2 Mrd. $) · Trend (Schluss > SMA 100 > SMA 200, SMA 200 steigt
    über 20 T.) · Stabilität (kein Tagesverlust unter −15 % in 90 T.) · Momentum / Quality (ROE, Nettoverschuldung/EBITDA) /
    Value (PEG, Forward-KGV ÷ 5-J.-KGV): Perzentil ≥ 50 in der Auswahl, fehlende Daten = neutral 50 · Sektor-Cap (höchstens 3
    Depot-Aktien im selben Sektor, Depot-Aktien selbst erfüllt) · Earnings-frei (keine Quartalszahlen in 5 Börsentagen).
    Reine Zusatzinfo – das Kaufsignal der Regel bleibt Top 20 nach 12-1-Momentum am Tauschtermin."""
    tick = [t for t, _ in now]
    mom = _pct(dict(now))
    F = {t: _fund_row(fund.get(t) or {}) for t in tick}
    q1, q2 = _pct({t: F[t]["roe"] for t in tick}), _pct({t: F[t]["nde"] for t in tick}, False)
    v1, v2 = _pct({t: F[t]["peg"] for t in tick}, False), _pct({t: F[t]["rel"] for t in tick}, False)
    sec = {t: (fund.get(t) or {}).get("sec") or (meta.get(t) or {}).get("sector") or "?" for t in tick}
    cnt: dict[str, int] = {}
    for t in depot:
        s = (fund.get(t) or {}).get("sec") or (meta.get(t) or {}).get("sector") or "?"
        cnt[s] = cnt.get(s, 0) + 1
    out = {}
    for t in tick:
        df = data.get(t)
        if df is None or "Close" not in df:
            continue
        c = df["Close"].dropna()
        if len(c) < 221:
            continue
        v = df["Volume"].reindex(c.index).fillna(0) if "Volume" in df else c * 0
        s100, s200 = c.rolling(100).mean(), c.rolling(200).mean()
        dv = float((c * v).tail(50).mean())
        mc = (meta.get(t) or {}).get("market_cap_usd")
        gap = float(c.pct_change().tail(90).min())
        part = lambda a, b: float(np.mean([x for x in (a.get(t), b.get(t)) if x is not None])) if (a.get(t) is not None or b.get(t) is not None) else 50.0
        qu, va = part(q1, q2), part(v1, v2)
        s = sec[t]
        ck = {"liq": dv >= CK["min_dv"] and bool(mc) and mc >= CK["min_mc"],
              "trend": c.iloc[-1] > s100.iloc[-1] > s200.iloc[-1] > s200.iloc[-21],
              "stab": gap > CK["gap"], "mom": mom.get(t, 50.0) >= 50, "qual": qu >= 50, "val": va >= 50,
              "sector": t in depot or s == "?" or cnt.get(s, 0) < CK["sector_cap"],
              "earn": not _earn_soon((meta.get(t) or {}).get("earnings_date"), asof, CK["earn_days"])}
        out[t] = {"chk": [int(bool(ck[k])) for k in CHECKS], "q": round(qu), "v": round(va), "mp": round(mom.get(t, 50.0)),
                  "edate": str((meta.get(t) or {}).get("earnings_date") or "")[:10] or None}
        out[t]["nchk"] = sum(out[t]["chk"])
    return out


def _px_on(df, d):
    c = df["Close"].dropna()
    i = c.index.searchsorted(d)
    return float(c.iloc[min(i, len(c) - 1)]) if len(c) else None


def build(data: dict, meta: dict, bench: pd.DataFrame | None = None, rule: dict | None = None, fund: dict | None = None) -> dict | None:
    """Aktuelles Langfrist-Depot, Entwicklung seit dem letzten Tausch, Vorschau auf den nächsten Tausch."""
    r = {**RULE, **(rule or {})}
    ref = bench if bench is not None and len(bench) else next((df for t, df in data.items() if _is_us(t, meta.get(t)) and len(df) > 300), None)
    if ref is None:
        return None
    idx = pd.DatetimeIndex(ref.index)
    rb = [d for d in rebalance_dates(idx, r["every"]) if d <= idx[-1]]
    if not rb:
        return None
    since = rb[-1]
    held = rank(data, meta, since, r)[: r["n"]]
    prev = {t for t, _ in rank(data, meta, rb[-2], r)[: r["n"]]} if len(rb) >= 2 else set()   # Depot des vorigen Quartals
    now = rank(data, meta, idx[-1] + pd.Timedelta(days=1), r)
    pos_now = {t: i + 1 for i, (t, _) in enumerate(now)}
    top_now = [t for t, _ in now[: r["n"]]]
    hold, rets = [], []
    for t, m0 in held:
        df = data[t]
        p0, p1 = _px_on(df, since), float(df["Close"].dropna().iloc[-1])
        ret = p1 / p0 - 1 if p0 else None
        rets.append(ret)
        hold.append({"t": t, "n": (meta.get(t) or {}).get("name") or t, "sec": (meta.get(t) or {}).get("sector"),
                     "m": round(m0, 4), "p0": round(p0, 4) if p0 else None, "p": round(p1, 4),
                     "ret": round(ret, 4) if ret is not None else None, "rk": pos_now.get(t)})
    port = float(np.nanmean([x for x in rets if x is not None])) if rets else None
    bret = None
    if bench is not None and len(bench):
        b0, b1 = _px_on(bench, since), float(bench["Close"].dropna().iloc[-1])
        bret = b1 / b0 - 1 if b0 else None
    y, m = since.year, since.month + r["every"]
    if m > 12:
        y, m = y + 1, m - 12
    nxt = pd.Timestamp(y, m, 1)
    while nxt.weekday() >= 5:
        nxt += pd.Timedelta(days=1)
    held_t = {x["t"] for x in hold}
    top = [{"t": t, "n": (meta.get(t) or {}).get("name") or t, "sec": (meta.get(t) or {}).get("sector"), "m": round(v, 4), "rk": i + 1,
            "p": round(float(data[t]["Close"].dropna().iloc[-1]), 4), "in": t in held_t} for i, (t, v) in enumerate(now[:TOP_N])]
    try:
        ck = checks(data, meta, now, held_t, load_fund() if fund is None else fund, idx[-1])
    except Exception as exc:                                        # Watchlist ist Zusatzinfo – Depot nie daran scheitern lassen
        print(f"Langfrist: Kriterien-Fehler {exc!r}")
        ck = {}
    for x in hold + top:
        if x["t"] in ck:
            x.update(chk=ck[x["t"]]["chk"], nchk=ck[x["t"]]["nchk"])
    top_set = set(top_now)
    rk_now = {t: i + 1 for i, (t, _) in enumerate(now)}
    w = sorted((t for t, v in ck.items() if v["nchk"] >= WATCH_MIN and t not in held_t and t not in top_set),
               key=lambda t: (-ck[t]["nchk"], rk_now[t]))[:WATCH_MAX]
    mo = dict(now)
    watch = [{"t": t, "n": (meta.get(t) or {}).get("name") or t, "sec": (meta.get(t) or {}).get("sector"), "rk": rk_now[t],
              "m": round(mo[t], 4), "p": round(float(data[t]["Close"].dropna().iloc[-1]), 4), **ck[t],
              "miss": [k for k, v in zip(CHECKS, ck[t]["chk"]) if not v]} for t in w]
    # Rang, Lauf und Kriterien für ALLE Aktien der Auswahl (Scanner „Meine“, Aktienkarte) – run_scan schreibt sie in search.json
    ranks = {t: [rk_now[t], round(mo[t], 4), ck[t]["nchk"] if t in ck else None,
                 sum(b << i for i, b in enumerate(ck[t]["chk"])) if t in ck else None] for t in rk_now}
    return {"rule": r, "since": since.strftime("%Y-%m-%d"), "watch": watch, "checks": list(CHECKS), "ranks": ranks, "next": nxt.strftime("%Y-%m-%d"), "asof": idx[-1].strftime("%Y-%m-%d"),
            "hold": hold, "ret": round(port, 4) if port is not None else None, "bench": round(bret, 4) if bret is not None else None,
            "out": [t for t in held_t if t not in top_now], "inn": [t for t in top_now if t not in held_t], "top": top,
            "chg": {"out": sorted(prev - held_t), "inn": sorted(held_t - prev)} if prev else None,   # Tausch am letzten Termin
            "univ": len(now), "bt": BACKTEST}
