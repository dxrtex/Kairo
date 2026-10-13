"""4-Stunden-Test: Macht der 4H-RSI (und das MBI) Einstieg und Ausstieg der Kairo-Treffer genauer?

Idee (Jonny, Okt. 2026, Uber/TUI/Infineon): kaufen, wenn der 4H-RSI überverkauft ist (≈ 30–35) und dreht, verkaufen bei
4H-RSI ≈ 70 (bzw. rotes MBI-X). Yahoo liefert Stundenkerzen nur für ~2 Jahre → 4H-Kerzen daraus (je Handelstag die
Stunden in 4er-Gruppen), Zeitraum also nur ~Okt. 2024 – heute. Alle Trades netto in R (Spread + Gebühr als Kosten).

Varianten auf denselben Kairo-Treffern (beide Stichproben, kurz-*-Artefakte):
  T0  Einstieg 1. 4H-Kerze nach dem Signal, Stop = Kairo-Stop, Ausstieg Tag 20 / Stop          (Vergleich)
  E1  Einstieg erst, wenn der 4H-RSI ≤ 35 war und wieder über 35 steigt (≤ 10 Tage), Stop = Tief seit Signal − 0,25 ATR
  E2  wie E1, aber Auslöser grünes MBI-X (4H)
  X1  Einstieg wie T0, Ausstieg bei 4H-RSI ≥ 70 (sonst Tag 20 / Stop)
  X2  Einstieg wie T0, Ausstieg beim ersten roten MBI-X (4H) über dem Einstieg
  E1X1 Kombination: Einstieg E1, Ausstieg X1
Mit den VOLLSTÄNDIGEN Tagesregeln (Kairo-Treffer + 5-Tage-Seitwärtsphase ≤ 1,5 ATR wie in shortswing.QRULE):
  B0   heutige Strategie, in 4H-Kerzen nachgerechnet: Kauf zur Eröffnung nach fertiger Basis, Basis-Stop, Tag 20  (Vergleich)
  B0X1 / B0X2  wie B0, Ausstieg bei 4H-RSI ≥ 70 bzw. rotem MBI-X
  E3_35 / E3_40  Basis fertig (Tageschart) UND 4H-RSI war ≤ 35 bzw. ≤ 40 und dreht nach oben → erst dann kaufen (≤ 10 Tage)
  E3_35X1 / E3_40X1  dasselbe mit Ausstieg bei 4H-RSI ≥ 70
Dazu eigenständig auf ALLEN Aktien und Tagen (ohne Kairo-Signal):
  C1  4H-RSI kreuzt von unter 30 nach oben → Kauf, Stop = Tief der letzten 10 4H-Kerzen − 0,25 ATR, Ausstieg RSI ≥ 70 / 20 Tage
  C0  dieselben Regeln, aber Einstieg an zufälligen 4H-Kerzen (zeigt, ob RSI < 30 überhaupt etwas bringt)

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
from .indicators import rsi
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
    b["gx"], b["rx"] = m["green_x"].values, m["red_x"].values
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
    r_, rx = b["rsi"].to_numpy(float), b["rx"].to_numpy(bool)
    days = b["day"].to_numpy()
    ud = np.unique(days[i0:])
    if len(ud) <= max_days:
        return None                                      # noch offen (Ende der Daten)
    end = int(np.flatnonzero(days == ud[max_days - 1])[-1])
    for j in range(i0, end + 1):
        if l[j] <= stop:
            px = min(stop, o[j]) if j > i0 else stop
            return {"r": (px - e) / risk - COST * e / risk, "bars": j - i0 + 1, "x": "stop"}
        hit = (exit_rule == "rsi" and r_[j] >= 70) or (exit_rule == "mbi" and rx[j] and c[j] > e)
        if hit and j < end:
            px = o[j + 1]
            return {"r": (px - e) / risk - COST * e / risk, "bars": j - i0 + 2, "x": exit_rule}
    return {"r": (c[end] - e) / risk - COST * e / risk, "bars": end - i0 + 1, "x": "zeit"}


def kairo_variants(e: dict, b: pd.DataFrame) -> dict:
    d = pd.Timestamp(e["d"])
    after = np.flatnonzero(b["day"].to_numpy() > np.datetime64(d))
    sig = np.flatnonzero(b["day"].to_numpy() == np.datetime64(d))
    if not len(after) or not len(sig):
        return {}
    i_first, c0 = int(after[0]), float(b["Close"].iat[int(sig[-1])])
    px = e["px"]
    kstop = c0 * px["s"]
    atr = c0 * px["atr"]
    out = {}
    for name, rule in (("T0", "zeit"), ("X1", "rsi"), ("X2", "mbi")):
        t = _trade(b, i_first, kstop, rule)
        if t:
            out[name] = t
    # Vollständige Tagesregeln: Basis wie getestet (shortswing.simulate) → Einstiegstag; 4H nur als zusätzlicher Auslöser
    days = b["day"].to_numpy()
    ud = np.unique(days[i_first:])
    sm = simulate(px, {**QRULE, "hold": 20, "levs": [1]})
    if sm and "skip" not in sm and sm["s"] < len(ud):
        i_in = int(np.flatnonzero(days == ud[sm["s"]])[0])
        bstop = c0 * sm["sl"]
        for name, rule in (("B0", "zeit"), ("B0X1", "rsi"), ("B0X2", "mbi")):
            t = _trade(b, i_in, bstop, rule)
            if t:
                out[name] = t
        r4 = b["rsi"].to_numpy(float)
        lim = ud[min(len(ud) - 1, sm["s"] + 10)]
        for th in (35, 40):
            for j in range(max(1, i_in - 1), len(b) - 1):
                if days[j] > lim:
                    break
                if r4[j - 1] <= th < r4[j] or (min(r4[max(0, j - 6):j]) <= th and r4[j - 1] <= r4[j] and r4[j] > th and r4[j - 1] <= th + 2):
                    for nm, rule in ((f"E3_{th}", "zeit"), (f"E3_{th}X1", "rsi")):
                        t = _trade(b, j + 1, bstop, rule)
                        if t:
                            out[nm] = t
                    break
    win = after[: 10 * 2 + 1]                            # ~10 Handelstage à ~2 4H-Kerzen
    r_, gx = b["rsi"].to_numpy(float), b["gx"].to_numpy(bool)
    lo = b["Low"].to_numpy(float)
    for name, trig in (("E1", lambda j: r_[j - 1] <= 35 < r_[j] and min(r_[max(0, j - 6):j]) <= 35), ("E2", lambda j: gx[j])):
        for j in win:
            j = int(j)
            if j < 1 or not trig(j):
                continue
            stop = float(lo[i_first:j + 1].min()) - 0.25 * atr
            for nm, rule in ((name, "zeit"), (name + "X1", "rsi")):
                t = _trade(b, j + 1, stop, rule)
                if t:
                    out[nm] = t
            break
    return out


def standalone(b: pd.DataFrame, atr_pct: float, rnd: random.Random) -> tuple[list, list]:
    r_ = b["rsi"].to_numpy(float)
    lo = b["Low"].to_numpy(float)
    sig, base = [], []
    i = 30
    while i < len(b) - 2:
        if r_[i - 1] < 30 <= r_[i]:
            stop = float(lo[i - 9:i + 1].min()) - 0.25 * atr_pct * float(b["Close"].iat[i])
            t = _trade(b, i + 1, stop, "rsi")
            if t:
                sig.append(t)
                i += t["bars"]
                continue
        i += 1
    for _ in range(max(1, len(sig))):                    # gleich viele zufällige Einstiege mit denselben Regeln
        j = rnd.randrange(30, max(31, len(b) - 3))
        stop = float(lo[j - 9:j + 1].min()) - 0.25 * atr_pct * float(b["Close"].iat[j])
        t = _trade(b, j + 1, stop, "rsi")
        if t:
            base.append(t)
    return sig, base


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
                res.setdefault(k, []).append(v)
        rep["kairo"][d] = {"treffer_im_zeitraum": n, **{k: summary(v) for k, v in sorted(res.items())}}
        print(d, json.dumps(rep["kairo"][d], ensure_ascii=False), flush=True)
    rnd = random.Random(7)
    for d, hs in hits.items():
        tks = sorted({e["t"] for e in hs})
        atrp = {e["t"]: e["px"]["atr"] for e in hs}
        s_all, b_all = [], []
        for t in tks:
            if t in bars:
                s, bb = standalone(bars[t], atrp.get(t, 0.02), rnd)
                s_all += s
                b_all += bb
        rep["eigenstaendig"][d] = {"C1_rsi30": summary(s_all), "C0_zufall": summary(b_all)}
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
