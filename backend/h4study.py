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


def _hits(d: str) -> list[dict]:
    seen, out = set(), []
    for p in sorted(Path(d).glob("bilanz_part_*.json")):
        for e in json.loads(p.read_text()):
            if e.get("k") == "hit" and e.get("px") and (e["t"], e["d"]) not in seen:
                seen.add((e["t"], e["d"]))
                out.append(e)
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
    rec = lambda x: pd.Series(x, index=b.index).astype(float).rolling(6, min_periods=1).max().to_numpy() > 0
    rmin = b["rsi"].rolling(6, min_periods=1).min()
    rising = (b["rsi"] > b["rsi"].shift(1)).to_numpy()
    b["R35"] = (rmin <= 35).to_numpy() & rising
    b["R40"] = (rmin <= 40).to_numpy() & rising
    b["M"], b["M0"], b["B"] = rec(b["mcu"]), rec(b["mcu0"]), rec(b["gx"])
    b["xr"] = (b["rsi"].rolling(6, min_periods=1).max() >= 70).to_numpy()
    b["xm"], b["xb"] = rec(b["mcd"]), rec(b["rx"])
    return b


def _trade(b: pd.DataFrame, i0: int, stop: float, exit_rule: str, max_days: int = 20) -> dict | None:
    """Kauf zur Eröffnung der Kerze i0; Stop (auch untertags), Ausstieg nach Regel oder am Schluss von Handelstag max_days."""
    if i0 >= len(b) - 1:
        return None
    e = float(b["Open"].iat[i0])
    if not (stop < e) or (e - stop) / e > 0.25:
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
            return {"r": (px - e) / risk - COST * e / risk, "bars": j - i0 + 1, "x": "stop", "ti": str(b.index[i0]), "to": str(b.index[j])}
        hit = ((exit_rule == "rsi" and r_[j] >= 70) or (exit_rule == "mbi" and rx[j]) or (exit_rule == "macd" and mcd[j])
               or (exit_rule == "2v3" and two[j]) or (exit_rule == "3v3" and three[j]))
        if hit and j < end:
            px = o[j + 1]
            return {"r": (px - e) / risk - COST * e / risk, "bars": j - i0 + 2, "x": exit_rule, "ti": str(b.index[i0]), "to": str(b.index[j + 1])}
    return {"r": (c[end] - e) / risk - COST * e / risk, "bars": end - i0 + 1, "x": "zeit", "ti": str(b.index[i0]), "to": str(b.index[end])}


TRIG = {"R35": ["R35"], "R40": ["R40"], "M": ["M"], "M0": ["M0"], "B": ["B"], "RM": ["R40", "M"], "RB": ["R40", "B"],
        "MB": ["M", "B"], "RMB": ["R40", "M", "B"]}
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
    flags = {k: b[k].to_numpy(bool) for k in ("R35", "R40", "M", "M0", "B")}
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


def main(argv=None) -> int:
    dirs = (argv if argv is not None else sys.argv[1:]) or ["k1", "k2"]
    t0 = time.time()
    hits = {d: _hits(d) for d in dirs}
    tick = sorted({e["t"] for h in hits.values() for e in h})
    print(f"Treffer: {[len(h) for h in hits.values()]}, Aktien: {len(tick)}", flush=True)
    raw = _hourly(tick)
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
