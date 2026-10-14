"""4-Stunden-Test: Machen 4H-RSI, 4H-MACD und 4H-MBI – zusammen mit den Tageschart-Kriterien – Einstieg und Ausstieg genauer?

These (Jonny, Okt. 2026, Uber/TUI/Infineon): Erst die Kombination aus Tageschart (Kairo-Kriterien) und 4H-Indikatoren macht
das Setup stark. Yahoo liefert Stundenkerzen nur für ~2 Jahre → 4H-Kerzen (je Handelstag die Stunden in 4er-Gruppen),
Zeitraum ~Okt. 2024 – heute. Alle Trades netto in R (Spread + Gebühren als Kosten), beide Stichproben getrennt.

Tageschart-Kontext (immer Pflicht):
  H   Kairo-Treffer (alle 11 Kriterien), Einstiegsfenster 10 Tage, Stop = Tief seit Signal − 0,25 ATR
  HB  Kairo-Treffer + 5-Tage-Seitwärtsphase ≤ 1,5 ATR (= heutige Strategie), Fenster 10 Tage ab fertiger Basis, Basis-Stop
4H-Auslöser beim Einstieg (jeweils „zuletzt passiert“ = in den letzten 6 4H-Kerzen, ≈ 3 Tage):
  –    kein 4H-Filter (Vergleich: H = Kauf nach dem Signal, HB = heutige Strategie)
  R35/R40  RSI war ≤ 35 bzw. ≤ 40 und steigt wieder
  M    MACD kreuzt die Signallinie nach oben;  M0  dasselbe unterhalb der Nulllinie
  B    grünes MBI-X
  RM, RB, MB, RMB  Kombinationen (alle Bedingungen zuletzt erfüllt)
  S    Strukturbruch: 4H-Schluss über dem Hoch der 6 Kerzen davor;  RS, MS, BS, RMBS  mit den Indikatoren kombiniert
4H-Ausstieg: zeit (Tag 20 / Stop) · rsi (RSI ≥ 70) · macd (MACD kreuzt nach unten) · mbi (rotes MBI-X) · 2v3 (zwei der drei zuletzt) · 3v3 (alle drei zuletzt – Jonnys Ausstieg)
Gegenprobe ohne Tageschart: C_R30 (RSI kreuzt 30 nach oben) und C_RMB (alle drei) gegen zufällige Einstiege mit denselben Regeln.
Vorsicht: Viele Varianten → einzelne sehen zufällig gut aus. Zählt nur, was in BEIDEN Stichproben besser ist als der Vergleich.

    python -m backend.h4study k1 k2
"""

from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .config import ROOT
from .indicators import macd, rsi
from .mbi import momentum_bias_index
from .shortswing import QRULE, simulate

COST = 0.0015 + 2 * 0.99 / 2000          # Spread Turbo + 2 Orders auf ~2.000 € Position (wie die 10-Jahres-Studie)


def _grp(e: dict) -> str | None:
    """Gruppe nach erfüllten Kairo-Kriterien (Tageschart): 11/11 Treffer, 10/11 Fast-Treffer, 9/11 (zufällige Vergleichstage)."""
    met = (e.get("f") or {}).get("met")
    return "11" if e.get("k") == "hit" else "10" if e.get("k") == "fast" else "9" if e.get("k") == "base" and met == 9 else None


def _hits(d: str, near: bool = False) -> list[dict]:
    seen, out = set(), []
    for p in sorted(Path(d).glob("bilanz_part_*.json")):
        for e in json.loads(p.read_text()):
            g = _grp(e)
            if g and (near or g == "11") and e.get("px") and (e["t"], e["d"], g) not in seen:
                seen.add((e["t"], e["d"], g))
                out.append({**e, "grp": g})
    return out


def _hourly(tickers: list[str], batch: int = 40, pause: float = 5.0) -> dict:
    import yfinance as yf
    out, todo = {}, list(dict.fromkeys(tickers))
    for rnd in range(4):
        failed = []
        for i in range(0, len(todo), batch):
            part = todo[i:i + batch]
            try:
                d = yf.download(part, period="730d", interval="60m", auto_adjust=True, progress=False, threads=True, group_by="ticker")
                for t in part:
                    try:
                        x = (d[t] if isinstance(d.columns, pd.MultiIndex) else d)[["Open", "High", "Low", "Close"]].dropna()
                        if len(x) > 300:
                            out[t] = x
                        else:
                            failed.append(t)
                    except Exception:
                        failed.append(t)
            except Exception as exc:
                print("Download-Fehler", repr(exc)[:120], flush=True)
                failed += part
            time.sleep(pause)
        print(f"Stundenkerzen Runde {rnd + 1}: {len(out)} geladen, {len(failed)} fehlen", flush=True)
        if not failed or (len(failed) == len(todo) and rnd > 0):
            break
        todo = failed
        time.sleep(60)
    return out


W, L = 6, 6                                # „zuletzt“-Fenster und Strukturbruch-Rückblick (4H-Kerzen) – Robustheitstest variiert beides


def _bear_div(hi: np.ndarray, r: np.ndarray) -> np.ndarray:
    """Bärische RSI-Divergenz (Googles Ausstieg): jüngstes Hoch (letzte 10 Kerzen) mindestens so hoch wie das frühere
    (10–30 Kerzen zurück), der RSI dort aber mindestens 3 Punkte tiefer; das frühere Hoch mit RSI ≥ 60. Nur Vergangenheit."""
    out = np.zeros(len(hi), bool)
    for j in range(30, len(hi)):
        a, b2 = j - 30 + int(np.argmax(hi[j - 30:j - 9])), j - 9 + int(np.argmax(hi[j - 9:j + 1]))
        if b2 == j and hi[b2] >= hi[a] * 0.995 and r[b2] <= r[a] - 3 and r[a] >= 60:
            out[j] = True
    return out


def _bull_div(lo: np.ndarray, r: np.ndarray) -> np.ndarray:
    """Bullische RSI-Divergenz im 4H-Chart: jüngstes Tief (letzte 10 Kerzen) höchstens 1 % über dem früheren Tief
    (10–30 Kerzen zurück) oder tiefer, der RSI dort aber mindestens 3 Punkte höher. Nur Vergangenheit."""
    out = np.zeros(len(lo), bool)
    for j in range(30, len(lo)):
        a, b2 = j - 30 + int(np.argmin(lo[j - 30:j - 9])), j - 9 + int(np.argmin(lo[j - 9:j + 1]))
        if lo[b2] <= lo[a] * 1.01 and r[b2] >= r[a] + 3 and r[a] < 45:
            out[j] = True
    return out


def to4h(x: pd.DataFrame) -> pd.DataFrame:
    """Je Handelstag die Stundenkerzen in 4er-Gruppen (wie TradingView 4H in der Börsenzeit)."""
    idx = x.index.tz_convert(None) if x.index.tz is not None else x.index
    x = x.copy()
    x.index = idx
    day = x.index.normalize()
    k = x.groupby(day).cumcount() // 4
    g = x.groupby([day, k])
    b = pd.DataFrame({"Open": g["Open"].first(), "High": g["High"].max(), "Low": g["Low"].min(), "Close": g["Close"].last(),
                      "t": g.apply(lambda z: z.index[-1])})
    b.index = pd.DatetimeIndex(b["t"].values)
    b["day"] = b.index.normalize()
    b = b.drop(columns="t")
    b["rsi"] = rsi(b["Close"], 14)
    m = momentum_bias_index(b["Close"], b["High"], b["Low"])
    b["gx"], b["rx"] = m["green_x"].values.astype(bool), m["red_x"].values.astype(bool)
    md = macd(b["Close"])
    up = (md["macd"] > md["signal"]) & (md["macd"].shift(1) <= md["signal"].shift(1))
    dn = (md["macd"] < md["signal"]) & (md["macd"].shift(1) >= md["signal"].shift(1))
    b["mcu"], b["mcd"], b["mcu0"] = up.values, dn.values, (up & (md["macd"] < 0)).values
    rec = lambda x: pd.Series(x, index=b.index).astype(float).rolling(W, min_periods=1).max().to_numpy() > 0
    rmin = b["rsi"].rolling(W, min_periods=1).min()
    rising = (b["rsi"] > b["rsi"].shift(1)).to_numpy()
    b["R35"] = (rmin <= 35).to_numpy() & rising
    b["R40"] = (rmin <= 40).to_numpy() & rising
    b["R30"] = (rmin <= 30).to_numpy() & rising            # nur für den Kriterien-Test (--variants)
    b["R45"] = (rmin <= 45).to_numpy() & rising
    b["D"] = rec(_bull_div(b["Low"].to_numpy(float), b["rsi"].to_numpy(float))) & rising   # 4H-RSI-Divergenz, RSI steigt
    b["RD"] = b["R40"].to_numpy() | b["D"].to_numpy()
    b["M"], b["M0"], b["B"] = rec(b["mcu"]), rec(b["mcu0"]), rec(b["gx"])
    # Strukturbruch: Schluss über dem höchsten Hoch der 6 4H-Kerzen davor (≈ letztes 4H-Zwischenhoch, ~3 Tage)
    b["S"] = (b["Close"] > b["High"].shift(1).rolling(L, min_periods=L).max()).to_numpy()
    b["xr"] = (b["rsi"].rolling(6, min_periods=1).max() >= 70).to_numpy()
    b["xm"], b["xb"] = rec(b["mcd"]), rec(b["rx"])
    return b


def _trade(b: pd.DataFrame, i0: int, stop: float, exit_rule: str, max_days: int = 20) -> dict | None:
    """Kauf zur Eröffnung der Kerze i0; Stop (auch untertags), Ausstieg nach Regel oder am Schluss von Handelstag max_days."""
    if i0 >= len(b) - 1:
        return None
    e = float(b["Open"].iat[i0])
    if not (stop < e) or (e - stop) / e > 0.25 or (e - stop) / e < 0.004:     # Stop zu weit / so eng, dass Kosten das Risiko übersteigen
        return None
    risk = e - stop
    o, h, l, c = (b[k].to_numpy(float) for k in ("Open", "High", "Low", "Close"))
    r_, rx, mcd = b["rsi"].to_numpy(float), b["rx"].to_numpy(bool), b["mcd"].to_numpy(bool)
    cnt = b["xr"].to_numpy(int) + b["xm"].to_numpy(int) + b["xb"].to_numpy(int)
    two, three = cnt >= 2, cnt >= 3
    days = b["day"].to_numpy()
    ud = np.unique(days[i0:])
    if len(ud) <= max_days:
        return None                                      # noch offen (Ende der Daten)
    end = int(np.flatnonzero(days == ud[max_days - 1])[-1])
    for j in range(i0, end + 1):
        if l[j] <= stop:
            px = min(stop, o[j]) if j > i0 else stop
            return {"r": (px - e) / risk - COST * e / risk, "bars": j - i0 + 1, "x": "stop", "ti": str(b.index[i0]), "to": str(b.index[j]), "sl": stop}
        hit = ((exit_rule == "rsi" and r_[j] >= 70) or (exit_rule == "mbi" and rx[j]) or (exit_rule == "macd" and mcd[j])
               or (exit_rule == "2v3" and two[j]) or (exit_rule == "3v3" and three[j]))
        if hit and j < end:
            px = o[j + 1]
            return {"r": (px - e) / risk - COST * e / risk, "bars": j - i0 + 2, "x": exit_rule, "ti": str(b.index[i0]), "to": str(b.index[j + 1]), "sl": stop}
    return {"r": (c[end] - e) / risk - COST * e / risk, "bars": end - i0 + 1, "x": "zeit", "ti": str(b.index[i0]), "to": str(b.index[end]), "sl": stop}


TRIG = {"R35": ["R35"], "R40": ["R40"], "M": ["M"], "M0": ["M0"], "B": ["B"], "RM": ["R40", "M"], "RB": ["R40", "B"],
        "MB": ["M", "B"], "RMB": ["R40", "M", "B"],
        "S": ["S"], "RS": ["R40", "S"], "MS": ["M", "S"], "BS": ["B", "S"], "RMBS": ["R40", "M", "B", "S"]}
EXITS = ("zeit", "rsi", "macd", "mbi", "2v3", "3v3")


def kairo_variants(e: dict, b: pd.DataFrame) -> dict:
    d = pd.Timestamp(e["d"])
    days = b["day"].to_numpy()
    after = np.flatnonzero(days > np.datetime64(d))
    sig = np.flatnonzero(days == np.datetime64(d))
    if not len(after) or not len(sig):
        return {}
    i_first, c0, px = int(after[0]), float(b["Close"].iat[int(sig[-1])]), e["px"]
    atr, lo = c0 * px["atr"], b["Low"].to_numpy(float)
    ud = np.unique(days[i_first:])
    ctx = {"H": (i_first, None, ud[min(len(ud) - 1, 10)])}
    sm = simulate(px, {**QRULE, "hold": 20, "levs": [1]})
    if sm and "skip" not in sm and sm["s"] < len(ud):
        i_in = int(np.flatnonzero(days == ud[sm["s"]])[0])
        ctx["HB"] = (i_in, c0 * sm["sl"], ud[min(len(ud) - 1, sm["s"] + 10)])
    flags = {k: b[k].to_numpy(bool) for k in {f for need in TRIG.values() for f in need}}
    out = {}
    for cn, (i0, stop0, lim) in ctx.items():
        s0 = int(sig[0])
        stop_at = (lambda j: float(lo[s0:j + 1].min()) - 0.25 * atr) if stop0 is None else (lambda j: stop0)
        entries = {"–": (i0, px["s"] * c0 if stop0 is None else stop0)}
        for tn, need in TRIG.items():
            for j in range(max(1, i0 - 1), len(b) - 1):
                if days[j] > lim:
                    break
                if all(flags[k][j] for k in need):
                    entries[tn] = (j + 1, stop_at(j))
                    break
        for tn, (ie, st) in entries.items():
            for ex in EXITS:
                t = _trade(b, ie, st, ex)
                if t:
                    out[f"{cn}|{tn}|{ex}"] = t
    return out


def standalone(b: pd.DataFrame, atr_pct: float, rnd: random.Random) -> dict:
    """Ohne Tageschart: Einstieg beim 4H-Auslöser, Stop = Tief der letzten 10 Kerzen − 0,25 ATR, Ausstieg RSI ≥ 70 / Tag 20."""
    r_, lo, cl = b["rsi"].to_numpy(float), b["Low"].to_numpy(float), b["Close"].to_numpy(float)
    rmb = b["R40"].to_numpy(bool) & b["M"].to_numpy(bool) & b["B"].to_numpy(bool)
    trig = {"C_R30": lambda i: r_[i - 1] < 30 <= r_[i], "C_RMB": lambda i: rmb[i]}   # Gegenprobe ohne Tageschart
    out = {k: [] for k in ("C_R30", "C_RMB", "C0_zufall")}
    for k, f in trig.items():
        i = 30
        while i < len(b) - 2:
            if f(i):
                t = _trade(b, i + 1, float(lo[i - 9:i + 1].min()) - 0.25 * atr_pct * cl[i], "rsi")
                if t:
                    out[k].append(t)
                    i += t["bars"]
                    continue
            i += 1
    for _ in range(max(1, len(out["C_R30"]))):
        j = rnd.randrange(30, max(31, len(b) - 3))
        t = _trade(b, j + 1, float(lo[j - 9:j + 1].min()) - 0.25 * atr_pct * cl[j], "rsi")
        if t:
            out["C0_zufall"].append(t)
    return out


def depot(ts: list[dict], slots: int = 5, risk: float = 0.01, start: float = 10000.0) -> dict | None:
    """Depot wie die Strategie: 1 % Risiko vom Kapital je Trade, höchstens `slots` gleichzeitig, ruhigste zuerst bei
    gleichzeitigen Einstiegen; Gebühren stecken schon in r. Kapital nur bei Verkäufen gebucht (größter Rückgang daher eher zu klein)."""
    if not ts:
        return None
    ev = sorted(ts, key=lambda t: (t["ti"], t.get("atrp", 1)))
    eq, peak, mdd, open_, taken = start, start, 0.0, [], 0
    for t in ev:
        keep = []
        for o in sorted(open_, key=lambda o: o["to"]):
            if o["to"] <= t["ti"]:
                eq += o["amt"] * o["r"]
                peak = max(peak, eq)
                mdd = max(mdd, 1 - eq / peak)
            else:
                keep.append(o)
        open_ = keep
        if len(open_) >= slots or any(o["tk"] == t["tk"] for o in open_):
            continue
        open_.append({**t, "amt": eq * risk})
        taken += 1
    for o in sorted(open_, key=lambda o: o["to"]):
        eq += o["amt"] * o["r"]
        peak = max(peak, eq)
        mdd = max(mdd, 1 - eq / peak)
    yrs = max(0.25, (pd.Timestamp(ev[-1]["to"]) - pd.Timestamp(ev[0]["ti"])).days / 365.25)
    return {"trades": taken, "cagr": round(float((eq / start) ** (1 / yrs) - 1), 4) if eq > 0 else -1.0, "mdd": round(float(mdd), 3)}


def summary(ts: list[dict]) -> dict:
    if not ts:
        return {"n": 0}
    r = np.array([t["r"] for t in ts])
    return {"n": int(len(r)), "r": round(float(r.mean()), 3), "median": round(float(np.median(r)), 3), "gewinner": round(float((r > 0).mean()), 3),
            "kerzen": round(float(np.mean([t["bars"] for t in ts])), 1), "summe_r": round(float(r.sum()), 1),
            "top5_anteil": round(float(np.sort(r)[-5:].sum() / r[r > 0].sum()), 3) if (r > 0).any() else None}


def robust(hits: dict, raw: dict) -> dict:
    """Stufe 3: Hält das beste Setup (Tageschart + Seitwärtsphase + RSI/MACD/MBI + Strukturbruch), wenn man die
    Fenster ändert? Ein echter Effekt darf nicht nur bei genau 6/6 Kerzen funktionieren."""
    global W, L
    out = {}
    for w in (4, 6, 8):
        for lb in (4, 6, 10):
            W, L = w, lb
            bars = {}
            for t, x in raw.items():
                try:
                    b = to4h(x)
                    if len(b) > 100:
                        bars[t] = b
                except Exception:
                    pass
            for d, hs in hits.items():
                res: dict[str, list] = {}
                for e in hs:
                    b = bars.get(e["t"])
                    if b is None or pd.Timestamp(e["d"]) < b["day"].iat[0] + pd.Timedelta(days=20):
                        continue
                    for k, v in kairo_variants(e, b).items():
                        if k.endswith("|zeit") and k.split("|")[1] in ("–", "RMBS", "RMB", "RS"):
                            res.setdefault(k, []).append({**v, "tk": e["t"], "atrp": e["px"]["atr"]})
                out[f"W{w}_L{lb}_{d}"] = {k: {**summary(v), "depot": depot(v)} for k, v in sorted(res.items())}
                print(f"W{w} L{lb} {d}", {k: (v["n"], v.get("r")) for k, v in out[f"W{w}_L{lb}_{d}"].items()}, flush=True)
    W, L = 6, 6
    return out


# Ausstiegs-Test (--exits): gleiche Einstiege (Treffer + Seitwärtsphase + 4H RMBS), verschiedene Ausstiege.
# T = Verkauf zum Schluss von Tag n · BE = Stop auf Einstand ab +1 R · TR = Nachlauf-Stop (höchstes Hoch − k R) ·
# EMA = ab Tag 10 raus, wenn der Tagesschluss unter der EMA 20 (Tageschart) liegt · EXT = Tag 20, aber ab +1 R mit
# Nachlauf-Stop weiterlaufen lassen (höchstens 40 Tage) · TP = Hälfte am Kursziel (+2/+3 R), Rest Tag 20.
EXIT_RULES = {"T10": {"T": 10}, "T15": {"T": 15}, "T20 (heute)": {"T": 20}, "T30": {"T": 30}, "T40": {"T": 40},
              "BE1·T20": {"T": 20, "be": 1}, "TR2·T40": {"T": 40, "tr": 2}, "TR3·T60": {"T": 60, "tr": 3}, "TR2·T20": {"T": 20, "tr": 2},
              "EMA20·T40": {"T": 40, "ema": 20}, "EXT2·T40": {"T": 40, "ext": 2}, "EXT3·T60": {"T": 60, "ext": 3},
              "TP2 halb·T20": {"T": 20, "tp": 2}, "TP3 halb·T20": {"T": 20, "tp": 3}}


def _exit_sim(b: pd.DataFrame, i0: int, stop: float, rule: dict, ema20: np.ndarray, lastbar: np.ndarray) -> dict | None:
    """Ein Trade mit Ausstiegsregel; Stop/Nachlauf-Stop gelten ab der Kerze danach (kein Blick in die Zukunft)."""
    e = float(b["Open"].iat[i0])
    risk = e - stop
    o, h, l, c = (b[k].to_numpy(float) for k in ("Open", "High", "Low", "Close"))
    days = b["day"].to_numpy()
    ud = np.unique(days[i0:])
    T = rule["T"]
    if len(ud) <= T:
        return None
    end = int(np.flatnonzero(days == ud[T - 1])[-1])
    end20 = int(np.flatnonzero(days == ud[19])[-1]) if len(ud) > 20 else end
    st, hh, half, done = stop, e, None, 0.0
    sig = b[f"x_{rule['sig']}"].to_numpy(bool) if rule.get("sig") else None
    cost = COST * e / risk
    for j in range(i0, end + 1):
        if l[j] <= st:                                   # Stop / Nachlauf-Stop
            px = min(st, o[j]) if j > i0 else st
            r = (px - e) / risk
            return {"r": (0.5 * half + 0.5 * r if half is not None else r) - cost, "to": str(b.index[j])}
        if rule.get("tp") and half is None and h[j] >= e + rule["tp"] * risk:
            half = float(rule["tp"])
        hh = max(hh, h[j])
        dn = int(np.searchsorted(ud, days[j])) + 1       # Handelstag des Trades (1 = Kauftag)
        if rule.get("be") and hh >= e + rule["be"] * risk:
            st = max(st, e)
        if rule.get("tr") and hh >= e + risk:
            st = max(st, hh - rule["tr"] * risk)
        if rule.get("ext") and j >= end20:
            if j == end20 and c[j] < e + risk:           # an Tag 20 unter +1 R → wie bisher verkaufen
                r = (c[j] - e) / risk
                return {"r": (0.5 * half + 0.5 * r if half is not None else r) - cost, "to": str(b.index[j])}
            st = max(st, hh - rule["ext"] * risk)
        if rule.get("ema") and dn >= rule.get("from", 10) and lastbar[j] and c[j] < ema20[j] and j < end:
            r = (o[j + 1] - e) / risk
            return {"r": r - cost, "to": str(b.index[j + 1])}
        if sig is not None and sig[j] and j < end:       # Indikator-Ausstieg (erst wenn der Trade „reif“ ist)
            g = rule.get("gate")
            if g is None or (g[0] == "day" and dn >= g[1]) or (g[0] == "R" and hh >= e + g[1] * risk):
                r = (o[j + 1] - e) / risk
                return {"r": r - cost, "to": str(b.index[j + 1])}
        if rule.get("tp") and j == end20 and T == 20:
            break
    r = (c[end] - e) / risk
    return {"r": (0.5 * half + 0.5 * r if half is not None else r) - cost, "to": str(b.index[end])}


def exits_report(hits: dict, raw: dict, fine: bool = False, ind: bool = False) -> int:
    """Gibt es einen besseren Ausstieg als Tag 20? Alle Regeln auf denselben Einstiegen (nur Trades, bei denen jede
    Regel zu Ende laufen konnte), beide Stichproben und beide Zeithälften getrennt, Depot wie die Strategie."""
    global TRIG, EXITS
    global EXIT_RULES
    TRIG, EXITS = {"RMBS": ["R40", "M", "B", "S"]}, ("zeit",)
    if ind:                                              # Indikator-Ausstiege mit „Reife“-Bedingung, alle bis höchstens Tag 20 bzw. 40
        EXIT_RULES = {"T20 (heute)": {"T": 20}, "T40": {"T": 40}, "EMA20 ab T10·T40": {"T": 40, "ema": 20, "from": 10}}
        for sg, sn in (("rsi", "RSI≥70 dreht"), ("macd", "MACD kreuzt runter"), ("mbi", "rotes MBI-X"), ("2v3", "2 von 3"),
                       ("3v3", "3 von 3"), ("bdiv", "bär. Divergenz"), ("bdiv_mbi", "Divergenz oder MBI-X am Hoch")):
            for gn, g in (("sofort", None), ("ab Tag 10", ("day", 10)), ("ab +1R", ("R", 1)), ("ab +2R", ("R", 2))):
                for mx in (20, 40):
                    EXIT_RULES[f"{sn} {gn}·T{mx}"] = {"T": mx, "sig": sg, "gate": g}
    if fine:                             # Feinprüfung des EMA-Ausstiegs: Nachbar-Einstellungen
        EXIT_RULES = {"T20 (heute)": {"T": 20}, **{f"EMA{sp} ab T{fr}·T{mx}": {"T": mx, "ema": sp, "from": fr}
                      for sp in (10, 20, 30, 50) for fr in (5, 10, 15) for mx in (30, 40, 60)}}
    rep = {"generated": time.strftime("%Y-%m-%d"), "exits": {}}
    bars = {}
    for t, x in raw.items():
        try:
            b = to4h(x)
            if len(b) > 100:
                dc = b.groupby("day")["Close"].last()
                rs = b["rsi"].to_numpy(float)
                b["x_rsi"] = (b["rsi"].rolling(6, min_periods=1).max() >= 70).to_numpy() & (rs < np.roll(rs, 1))   # war ≥ 70, dreht nach unten
                b["x_macd"], b["x_mbi"] = b["mcd"].to_numpy(bool), b["rx"].to_numpy(bool)
                cnt = b["xr"].to_numpy(int) + b["xm"].to_numpy(int) + b["xb"].to_numpy(int)
                b["x_2v3"], b["x_3v3"] = cnt >= 2, cnt >= 3
                b["x_bdiv"] = _bear_div(b["High"].to_numpy(float), rs)
                b["x_bdiv_mbi"] = b["x_bdiv"].to_numpy() | (b["x_mbi"].to_numpy() & (b["rsi"].rolling(6, min_periods=1).max() >= 65).to_numpy())
                for sp in (10, 20, 30, 50):
                    b[f"ema{sp}d"] = b["day"].map(dc.ewm(span=sp, adjust=False).mean()).to_numpy()
                b["lastbar"] = (b["day"] != b["day"].shift(-1)).to_numpy()
                bars[t] = b
        except Exception:
            pass
    for d, hs in hits.items():
        res: dict[str, list] = {}
        for e in hs:
            b = bars.get(e["t"])
            if e["grp"] != "11" or b is None or pd.Timestamp(e["d"]) < b["day"].iat[0] + pd.Timedelta(days=20):
                continue
            v = kairo_variants(e, b).get("HB|RMBS|zeit")
            if not v:
                continue
            i0 = int(b.index.get_loc(pd.Timestamp(v["ti"])))
            outs = {k: _exit_sim(b, i0, v["sl"], rl, b[f"ema{rl.get('ema', 20)}d"].to_numpy(float), b["lastbar"].to_numpy(bool))
                    for k, rl in EXIT_RULES.items()}
            if any(x is None for x in outs.values()):
                continue                                 # gleiche Stichprobe für alle Regeln
            half = "a" if v["ti"] < "2025-04-01" else "b"
            for k, x in outs.items():
                tr = {"r": x["r"], "bars": 1, "ti": v["ti"], "to": x["to"], "tk": e["t"], "atrp": e["px"]["atr"]}
                for g in (k, f"{k} [{half}]"):
                    res.setdefault(g, []).append(tr)
        rep["exits"][d] = {g: {**summary(v), **({"depot": depot(v)} if "[" not in g else {})} for g, v in res.items()}
        for g, v in rep["exits"][d].items():
            print(d, g, (v["n"], v.get("r"), v.get("gewinner"), (v.get("depot") or {}).get("cagr"), (v.get("depot") or {}).get("mdd")), flush=True)
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "h4study.json").write_text(json.dumps(rep, ensure_ascii=False, separators=(",", ":")))
    print("===BEGIN===")
    print(json.dumps(rep, ensure_ascii=False, separators=(",", ":")))
    print("===END===")
    return 0


VARIANTS = {   # Kairo live = RMBS (RSI ≤ 40, MACD, MBI, Strukturbruch). Gegenproben: RSI-Schwelle, 4H-Divergenz, je ein Baustein weniger
    "RMBS": ["R40", "M", "B", "S"], "R30·MBS": ["R30", "M", "B", "S"], "R35·MBS": ["R35", "M", "B", "S"], "R45·MBS": ["R45", "M", "B", "S"],
    "Div·MBS": ["D", "M", "B", "S"], "(R40 oder Div)·MBS": ["RD", "M", "B", "S"], "R40·Div·MBS": ["R40", "D", "M", "B", "S"],
    "ohne RSI: MBS": ["M", "B", "S"], "ohne MACD: RBS": ["R40", "B", "S"], "ohne MBI: RMS": ["R40", "M", "S"], "ohne Bruch: RMB": ["R40", "M", "B"],
    "MACD unter 0: R·M0·BS": ["R40", "M0", "B", "S"], "ohne 4H": []}


def variants_report(hits: dict, raw: dict) -> int:
    """Gegenprobe der 4H-Kriterien: jede Variante mit Seitwärtsphase (HB), Verkauf an Tag 20, beide Stichproben und
    beide Zeithälften getrennt. Zählt nur, was überall besser ist – sonst bleibt es bei RMBS."""
    global TRIG, EXITS
    bars = {}
    for t, x in raw.items():
        try:
            b = to4h(x)
            if len(b) > 100:
                bars[t] = b
        except Exception:
            pass
    TRIG, EXITS = {k: v for k, v in VARIANTS.items() if v}, ("zeit",)
    rep = {"generated": time.strftime("%Y-%m-%d"), "variants": {}}
    for d, hs in hits.items():
        res: dict[str, list] = {}
        for e in hs:
            b = bars.get(e["t"])
            if e["grp"] != "11" or b is None or pd.Timestamp(e["d"]) < b["day"].iat[0] + pd.Timedelta(days=20):
                continue
            for k, v in kairo_variants(e, b).items():
                c, tn, ex = k.split("|")
                if c != "HB" or ex != "zeit":
                    continue
                name = "ohne 4H" if tn == "–" else tn
                half = "a" if v["ti"] < "2025-04-01" else "b"
                for g in (name, f"{name} [{half}]"):
                    res.setdefault(g, []).append({**v, "tk": e["t"], "atrp": e["px"]["atr"]})
        rep["variants"][d] = {g: {**summary(v), **({"depot": depot(v)} if "[" not in g else {})} for g, v in sorted(res.items())}
        for g, v in sorted(rep["variants"][d].items()):
            print(d, g, (v["n"], v.get("r"), (v.get("depot") or {}).get("cagr")), flush=True)
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "h4study.json").write_text(json.dumps(rep, ensure_ascii=False, separators=(",", ":")))
    print("===BEGIN===")
    print(json.dumps(rep, ensure_ascii=False, separators=(",", ":")))
    print("===END===")
    return 0


def miss_report(hits: dict, raw: dict) -> int:
    """Gibt es Fast-Treffer (10/11) oder 9/11, die mit sauberem Einstieg (Seitwärtsphase + 4H) so gut sind wie volle Treffer?
    Aufteilung nach fehlendem Kriterium, beide Stichproben und zwei Zeithälften getrennt (9/11 aus Stichprobe 1 ist
    beschädigt → nur Stichprobe 2 zählt dort)."""
    bars = {}
    for t, x in raw.items():
        try:
            b = to4h(x)
            if len(b) > 100:
                bars[t] = b
        except Exception:
            pass
    keep = ("HB|–|zeit", "HB|RS|zeit", "HB|RMB|zeit", "HB|RMBS|zeit")
    rep = {"generated": time.strftime("%Y-%m-%d"), "miss": {}}
    for d, hs in hits.items():
        res: dict[str, dict[str, list]] = {}
        for e in hs:
            b = bars.get(e["t"])
            if b is None or pd.Timestamp(e["d"]) < b["day"].iat[0] + pd.Timedelta(days=20):
                continue
            miss = [m for m in (e.get("miss") or []) if m not in ("cap", "liquidity", "price", "history")]
            if e["grp"] != "11" and len(miss) != {"10": 1, "9": 2}[e["grp"]]:
                continue                                 # Grundfilter fehlte – kein echter Fast-Treffer
            groups = ["11/11"] if e["grp"] == "11" else [f"{e['grp']}/11", *[f"{e['grp']}/11 ohne {m}" for m in miss]]
            for k, v in kairo_variants(e, b).items():
                if k in keep:
                    half = "a" if v["ti"] < "2025-04-01" else "b"
                    for g in groups:
                        for gg in (g, f"{g} [{half}]"):
                            res.setdefault(gg, {}).setdefault(k, []).append({**v, "tk": e["t"], "atrp": e["px"]["atr"]})
        rep["miss"][d] = {g: {k: {**summary(v), **({"depot": depot(v)} if "[" not in g else {})} for k, v in sorted(r.items())}
                          for g, r in sorted(res.items())}
        for g, r in sorted(rep["miss"][d].items()):
            print(d, g, {k: (v["n"], v.get("r")) for k, v in r.items()}, flush=True)
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "h4study.json").write_text(json.dumps(rep, ensure_ascii=False, separators=(",", ":")))
    print("===BEGIN===")
    print(json.dumps(rep, ensure_ascii=False, separators=(",", ":")))
    print("===END===")
    return 0


def main(argv=None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    mode = ("robust" if "--robust" in argv else "miss" if "--miss" in argv else "variants" if "--variants" in argv
            else "exits" if "--exits" in argv else "near" if "--near" in argv else "full")
    dirs = [a for a in argv if not a.startswith("--")] or ["k1", "k2"]
    t0 = time.time()
    hits = {d: _hits(d, near=mode in ("near", "miss")) for d in dirs}
    tick = sorted({e["t"] for h in hits.values() for e in h})
    print(f"Treffer: {[len(h) for h in hits.values()]}, Aktien: {len(tick)}", flush=True)
    raw = _hourly(tick)
    if mode == "near":                                   # 11/11 gegen 10/11 und 9/11 – jeweils ohne und mit 4H-Bestätigung
        bars = {}
        for t, x in raw.items():
            try:
                b = to4h(x)
                if len(b) > 100:
                    bars[t] = b
            except Exception:
                pass
        rep = {"generated": time.strftime("%Y-%m-%d"), "near": {}}
        for d, hs in hits.items():
            for g in ("11", "10", "9"):
                res: dict[str, list] = {}
                for e in hs:
                    b = bars.get(e["t"])
                    if e["grp"] != g or b is None or pd.Timestamp(e["d"]) < b["day"].iat[0] + pd.Timedelta(days=20):
                        continue
                    for k, v in kairo_variants(e, b).items():
                        if k.endswith("|zeit") and k.split("|")[1] in ("–", "RMBS", "RS", "RMB"):
                            res.setdefault(k, []).append({**v, "tk": e["t"], "atrp": e["px"]["atr"]})
                rep["near"][f"{g}/11_{d}"] = {k: {**summary(v), "depot": depot(v)} for k, v in sorted(res.items())}
                print(f"{g}/11 {d}", {k: (v["n"], v.get("r")) for k, v in rep["near"][f"{g}/11_{d}"].items()}, flush=True)
        (ROOT / "data").mkdir(exist_ok=True)
        (ROOT / "data" / "h4study.json").write_text(json.dumps(rep, ensure_ascii=False, separators=(",", ":")))
        print("===BEGIN===")
        print(json.dumps(rep, ensure_ascii=False, separators=(",", ":")))
        print("===END===")
        return 0
    if mode == "exits":                                  # Gibt es einen besseren Ausstieg als Tag 20?
        return exits_report(hits, raw, fine="--fine" in argv, ind="--ind" in argv)
    if mode == "variants":                               # Sind die 4H-Kriterien richtig gewählt? (nur volle Treffer)
        return variants_report(hits, raw)
    if mode == "miss":                                   # 10/11 und 9/11 nach fehlendem Kriterium, ohne und mit 4H-Bestätigung
        return miss_report(hits, raw)
    if mode == "robust":
        rep = {"generated": time.strftime("%Y-%m-%d"), "robust": robust(hits, raw)}
        (ROOT / "data").mkdir(exist_ok=True)
        (ROOT / "data" / "h4study.json").write_text(json.dumps(rep, ensure_ascii=False, separators=(",", ":")))
        print("===BEGIN===")
        print(json.dumps(rep, ensure_ascii=False, separators=(",", ":")))
        print("===END===")
        return 0
    bars, start = {}, None
    for t, x in raw.items():
        try:
            b = to4h(x)
            if len(b) > 100:
                bars[t] = b
                start = b.index[0] if start is None else min(start, b.index[0])
        except Exception as exc:
            print(t, "4H-Fehler", repr(exc)[:80])
    print(f"4H-Kerzen für {len(bars)} Aktien, ab {start}", flush=True)
    rep = {"generated": time.strftime("%Y-%m-%d"), "ab": str(start)[:10], "kosten_je_trade": COST, "kairo": {}, "eigenstaendig": {}}
    for d, hs in hits.items():
        res: dict[str, list] = {}
        n = 0
        for e in hs:
            b = bars.get(e["t"])
            if b is None or pd.Timestamp(e["d"]) < b["day"].iat[0] + pd.Timedelta(days=20):
                continue
            n += 1
            for k, v in kairo_variants(e, b).items():
                res.setdefault(k, []).append({**v, "tk": e["t"], "atrp": e["px"]["atr"]})
        rep["kairo"][d] = {"treffer_im_zeitraum": n, **{k: {**summary(v), "depot": depot(v)} for k, v in sorted(res.items())}}
        print(d, json.dumps(rep["kairo"][d], ensure_ascii=False), flush=True)
    rnd = random.Random(7)
    for d, hs in hits.items():
        tks = sorted({e["t"] for e in hs})
        atrp = {e["t"]: e["px"]["atr"] for e in hs}
        acc: dict[str, list] = {}
        for t in tks:
            if t in bars:
                for k, v in standalone(bars[t], atrp.get(t, 0.02), rnd).items():
                    acc.setdefault(k, []).extend(v)
        rep["eigenstaendig"][d] = {k: summary(v) for k, v in acc.items()}
        print(d, json.dumps(rep["eigenstaendig"][d], ensure_ascii=False), flush=True)
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "h4study.json").write_text(json.dumps(rep, ensure_ascii=False, separators=(",", ":")))
    print("===BEGIN===")
    print(json.dumps(rep, ensure_ascii=False, separators=(",", ":")))
    print("===END===")
    print(f"fertig in {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
