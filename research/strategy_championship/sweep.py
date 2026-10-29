"""Schwellen-Prüfung aller Kairo-Kriterien (Nutzer-Auftrag 28.10.2026): Sind die festgelegten Werte die besten?

Vorab festgelegt (vor dem Lauf, 28.10.2026):
- Je Kriterium werden einzelne Werte um den heutigen Wert geprüft, immer nur EIN Wert anders (alle übrigen Kriterien wie heute),
  dazu „Kriterium weglassen“. Grundlage: unveränderter Scanner auf Datensatz v1 (2008–2026), Einstieg/Ausstieg wie in allen
  bisherigen Tests (S01-B-Basis, Stop unter der Basis, EMA20-Ausstieg ab Tag 10, max. 40 T.), R netto bei 5.000 € PRIME+.
- Zielgröße: Ø R netto je Trade. Nebenbedingung: mindestens 50 % der heutigen Trade-Zahl je Abschnitt.
- Auswahl NUR mit Train (2008–16): je Kriterium der beste Wert. Übernahme-Vorschlag nur, wenn dieser Wert auch in
  Validierung (2017–21) UND Holdout (2022–26) besser ist als heute und gepoolt (Validierung+Holdout) Permutations-p ≤ 0,05/Anzahl
  Kriterien. Vorbehalt: Validierung und Holdout wurden schon in früheren Tests angeschaut – ein Bestehen ist ein gutes Zeichen,
  kein Beweis; die Live-Bilanz entscheidet.
- Ruhe-Regel (tight5/chop10) wird nicht nachjustiert (ihre Schwellen stammen schon aus diesen Trades → Zirkelschluss).

python -m research.strategy_championship.sweep signals --data DIR --shard K --shards N --out OUT
python -m research.strategy_championship.sweep analyse --signals S.parquet --trades T.csv
"""
from __future__ import annotations

import argparse
import copy
import math
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

from backend.config import CONFIG
from backend.indicators import macd, rsi
from backend.mbi import momentum_bias_index
from backend.scanner import evaluate, find_rsi_divergence
from . import s01
from .data import UNIVERSE, adjusted, load

KEYS = ["drawdown", "no_crash", "structure", "zone", "flattening", "rsi_div", "rsi_range", "macd_below0", "macd_turn", "mbi", "crv"]
# (Name, Kriterium, Wert) – Wert None = Kriterium weglassen
VARIANTS = [("heute", None, None)]
VARIANTS += [(f"drawdown {x:.0%}", "drawdown", x) for x in (0.08, 0.10, 0.15, 0.20, 0.25)]
VARIANTS += [(f"Crash-Grenze {x:.0%}", "no_crash", x) for x in (0.10, 0.15, 0.20)]
VARIANTS += [(f"Abflachung {x} ATR", "flattening", x) for x in (1.0, 1.25, 2.0, 2.5)]
VARIANTS += [(f"Fib-Impuls ≥ {x:.0%}", "zone_imp", x) for x in (0.10, 0.20, 0.30, 0.40)]
VARIANTS += [(f"Fib-Zone {a}–{b}", "zone_band", (a, b)) for a, b in ((0.5, 0.79), (0.618, 0.706), (0.706, 0.79), (0.618, 0.886), (0.5, 0.886))]
VARIANTS += [("Fib-Zone nur Support", "zone_band", "support")]
VARIANTS += [(f"Divergenz ≥ {x} Punkte", "rsi_div", x) for x in (1.0, 2.0, 4.0, 5.0, 7.0)]
VARIANTS += [("Divergenz RSI ± 2 T.", "rsi_div", "win2"), ("Divergenz nur klassisch", "rsi_div", "classic")]
VARIANTS += [(f"RSI {a}–{b}", "rsi_range", (a, b)) for a, b in ((20, 48), (25, 48), (30, 48), (28, 40), (28, 44), (28, 52), (28, 55))]
VARIANTS += [(f"MACD-Kreuz ≤ {x} T.", "macd_cross", x) for x in (3, 5, 10, 15)]
VARIANTS += [(f"MACD steigt ≥ {x} T.", "macd_rise", x) for x in (2, 3, 5, 6)]
VARIANTS += [(f"MACD ≤ {x:.0%} des Tiefs", "macd_trough", x) for x in (0.10, 0.15, 0.35, 0.50)]
VARIANTS += [(f"MBI-X ≤ {x} T.", "mbi_age", x) for x in (5, 10, 20, 25)]
VARIANTS += [(f"MBI rot ≤ {x:.0%}", "mbi_fade", x) for x in (0.5, 0.6, 0.8, 0.9)]
VARIANTS += [(f"CRV ≥ {x}", "crv", x) for x in (1.0, 1.5, 2.5, 3.0, 4.0)]
VARIANTS += [(f"ohne {k}", "drop", k) for k in KEYS]
CRIT = {"zone_imp": "zone", "zone_band": "zone", "macd_cross": "macd_turn", "macd_rise": "macd_turn", "macd_trough": "macd_turn",
        "mbi_age": "mbi", "mbi_fade": "mbi"}
_CTX = {}


def _macd_ok(mh, cross_max_age=7, rising_bars=4, trough_ratio=0.25, trough_lookback=30, fail_bars=3):
    n = len(mh)
    crosses = [i for i in range(1, n) if mh[i - 1] <= 0 < mh[i]]
    age = n - 1 - crosses[-1] if crosses else None
    a_ok = age is not None and age <= cross_max_age
    rising = all(mh[-j] > mh[-j - 1] for j in range(1, rising_bars + 1))
    trough = float(np.nanmin(mh[-trough_lookback:]))
    ratio = abs(mh[-1]) / abs(trough) if trough < 0 else None
    b_ok = mh[-1] < 0 and rising and ratio is not None and ratio <= trough_ratio
    failed = (age is not None and age <= cross_max_age + fail_bars and mh[-1] < 0
              and all(mh[-j] < mh[-j - 1] for j in range(1, fail_bars + 1)))
    return bool((a_ok or b_ok) and not failed)


def _mbi_ok(mb, x_max_age=15, max_peak_ratio=0.70):
    up_b, lo_b, bound, gx = (mb[k].to_numpy() for k in ("upper_bias", "lower_bias", "impulse_boundary", "green_x"))
    n = len(gx)
    for ix in reversed([i for i in range(max(2, n - x_max_age), n) if gx[i]]):
        peak = float(lo_b[ix - 1])
        if peak > bound[ix - 1] and (lo_b[-1] <= max_peak_ratio * peak or up_b[-1] > lo_b[-1]) and not float(np.nanmax(lo_b[ix:])) > peak:
            return True
    return False


def alt_ok(kind, val, res, w, cache):
    """Ist das betroffene Kriterium mit dem anderen Wert erfüllt?"""
    f, cfg = res.flags, CONFIG
    if kind == "drawdown":
        return f.get("raw_dd") is not None and f["raw_dd"] >= val
    if kind == "no_crash":
        return f["raw_worst"] > -val
    if kind == "flattening":
        return (f.get("raw_flat") is not None and f["raw_flat"] * cfg.correction.flat_atr_mult / val < 1) or (f.get("raw_wicks") or 0) >= cfg.correction.wick_min_count
    if kind in ("zone_imp", "zone_band"):
        fz, zb = (res.zone or {}).get("fib"), bool((res.zone or {}).get("support"))
        if val == "support":
            return zb
        if not fz:
            return zb
        H, L = res.zone["H"], fz["L"]
        rc_ = (H - float(w["Close"].iloc[-1])) / (H - L)
        rl_ = (H - float(w["Low"].tail(cfg.fib.touch_bars).min())) / (H - L)
        lo, hi = cfg.fib.zone if kind == "zone_imp" else val
        imp = val if kind == "zone_imp" else cfg.fib.min_impulse
        return bool((fz["impulse"] >= imp and (lo <= rc_ <= hi or lo <= rl_ <= hi) and rc_ <= cfg.fib.invalid_below) or zb)
    if kind == "rsi_div":
        if "r" not in cache:
            cache["r"] = rsi(w["Close"], cfg.rsi.length).to_numpy()
        rc = copy.copy(cfg.rsi)
        if val == "win2":
            rc.rsi_window = 2
        elif val != "classic":
            rc.min_rsi_diff = val
        d, _ = find_rsi_divergence(w["Low"], cache["r"], rc)
        return d is not None and (val != "classic" or d[0] == "klassisch")
    if kind == "rsi_range":
        return val[0] <= f["rsi"] <= val[1]
    if kind.startswith("macd"):
        if "mh" not in cache:
            cache["mh"] = macd(w["Close"], cfg.macd.fast, cfg.macd.slow, cfg.macd.signal)["hist"].to_numpy()
        kw = {"macd_cross": "cross_max_age", "macd_rise": "rising_bars", "macd_trough": "trough_ratio"}[kind]
        p = dict(cross_max_age=cfg.macd.cross_max_age, rising_bars=cfg.macd.rising_bars, trough_ratio=cfg.macd.trough_ratio)
        p[kw] = val
        return _macd_ok(cache["mh"], **p)
    if kind.startswith("mbi"):
        if "mb" not in cache:
            b = cfg.mbi
            cache["mb"] = momentum_bias_index(w["Close"], w["High"], w["Low"], b.momentum_length, b.bias_length,
                                              b.smooth_length, b.impulse_length, b.std_mult)
        p = dict(x_max_age=cfg.mbi.x_max_age, max_peak_ratio=cfg.mbi.max_peak_ratio)
        p["x_max_age" if kind == "mbi_age" else "max_peak_ratio"] = val
        return _mbi_ok(cache["mb"], **p)
    if kind == "crv":
        crv = (res.plan or {}).get("crv")
        return crv is not None and crv >= val
    raise ValueError(kind)


def _sig(t):
    raw, cur, (start, end) = _CTX["p"][t], _CTX["cur"].get(t, "USD"), _CTX["per"]
    raw = raw.dropna(subset=["Open", "High", "Low", "Close", "AdjClose"])
    raw = raw[raw["Close"] > 0]
    adj = adjusted(raw)
    ok = s01.eligible(adj, cur)
    idx = adj.index
    first = int(np.searchsorted(idx.values, np.datetime64(start - pd.Timedelta(days=14))))
    last = [-99] * len(VARIANTS)
    out = []
    for i in range(first, len(adj)):
        if not ok[i]:
            continue
        w = adj.iloc[max(0, i - s01.WINDOW + 1): i + 1]
        try:
            res = evaluate(w, {"currency": cur}, ticker=t)
        except Exception:
            continue
        crit = {c.key: c.ok for c in res.criteria if c.mandatory}
        fails = [k for k, v in crit.items() if not v]
        if len(fails) > 1:
            continue
        cache, hit = {}, []
        for vi, (_, kind, val) in enumerate(VARIANTS):
            if kind is None:
                p = not fails
            elif kind == "drop":
                p = all(v for k, v in crit.items() if k != val)
            else:
                ck = CRIT.get(kind, kind)
                if any(not v for k, v in crit.items() if k != ck):
                    p = False
                else:
                    try:
                        p = alt_ok(kind, val, res, w, cache)
                    except Exception:
                        p = False
            if p:
                fresh, last[vi] = i - last[vi] > s01.GAP, i
                if fresh and start <= idx[i] <= end:
                    hit.append(vi)
        if hit:
            calm = res.flags.get("calm") or {}
            out.append({"ticker": t, "date": idx[i], "i": i, "atr": float(res.flags.get("atr") or np.nan), "close": float(res.close),
                        "score": int(res.score), "v": ",".join(map(str, hit)), "calm": bool(calm.get("clean"))})
    return out


def signals(a):
    uni = sorted(pd.read_csv(UNIVERSE)["ticker"])
    mine = [t for k, t in enumerate(uni) if k % a.shards == a.shard]
    p, cur, _fx, _b, per = load(a.data, "full", mine)
    _CTX.update(p=p, cur=cur, per=per)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    acc = []
    with Pool() as pool:
        for k, o in enumerate(pool.imap_unordered(_sig, sorted(p), chunksize=1)):
            acc += o
            if k % 20 == 0:
                print(f"{k + 1}/{len(p)}: {len(acc)} Signal-Tage", flush=True)
    pd.DataFrame(acc, columns=["ticker", "date", "i", "atr", "close", "score", "v", "calm"]).to_parquet(out / f"sweep_signals_{a.shard}.parquet", index=False)
    print(f"Shard {a.shard}: {len(acc)} Signal-Tage")


def perm_p(x, y, n=10000, seed=1):
    rng = np.random.default_rng(seed); obs = x.mean() - y.mean(); z = np.concatenate([x, y]); k = len(x); c = 0
    for _ in range(n):
        rng.shuffle(z); c += (z[:k].mean() - z[k:].mean()) >= obs
    return (c + 1) / (n + 1)


def analyse(a):
    S = pd.read_parquet(a.signals)
    T = pd.read_csv(a.trades)
    S["tag"] = S["ticker"] + "|" + pd.to_datetime(S["date"]).dt.date.astype(str)
    R = T.set_index("tag")[["R_net_5000", "abschnitt"]]
    S = S.join(R, on="tag", how="inner")
    AB = ("Train", "Validierung", "Holdout")
    rows = []
    for vi, (name, kind, val) in enumerate(VARIANTS):
        m = S["v"].str.split(",").apply(lambda l: str(vi) in l)
        d = S[m]
        r = {"vi": vi, "name": name, "kind": CRIT.get(kind, kind) if kind != "drop" else "drop:" + val}
        for ab in AB:
            x = d[d["abschnitt"] == ab]["R_net_5000"]
            r[f"{ab}_R"], r[f"{ab}_n"], r[f"{ab}_sum"] = x.mean(), len(x), x.sum()
            xc = d[(d["abschnitt"] == ab) & d["calm"]]["R_net_5000"]
            r[f"{ab}_Rcalm"], r[f"{ab}_ncalm"] = xc.mean(), len(xc)
        rows.append(r)
    D = pd.DataFrame(rows)
    base = D.iloc[0]
    pd.set_option("display.width", 250, "display.max_rows", 200)
    print("Alle Varianten (Ø R netto je Trade, n; Summe R) – heute zuerst:\n")
    for _, r in D.iterrows():
        print(f"{r['name']:<28}" + "".join(f"{ab[:5]} {r[f'{ab}_R']:+.3f} (n {int(r[f'{ab}_n']):>5}, Σ {r[f'{ab}_sum']:+6.0f})  " for ab in AB)
              + " | ruhig: " + " ".join(f"{r[f'{ab}_Rcalm']:+.3f}({int(r[f'{ab}_ncalm'])})" for ab in AB))
    groups = {}
    for _, r in D.iloc[1:].iterrows():
        g = r["kind"] if not r["kind"].startswith("drop:") else r["kind"][5:]
        groups.setdefault(g, []).append(r)
    k = len(groups)
    print(f"\nVorab-Regel je Kriterium (Auswahl nur mit Train, Prüfung in Validierung und Holdout, p ≤ 0,05/{k}):")
    for g, rs in groups.items():
        ok_n = [r for r in rs if all(r[f"{ab}_n"] >= 0.5 * base[f"{ab}_n"] for ab in AB)]
        if not ok_n:
            print(f"  {g:<12} keine Variante mit genug Trades"); continue
        best = max(ok_n, key=lambda r: r["Train_R"])
        if best["Train_R"] <= base["Train_R"]:
            print(f"  {g:<12} heute ist in Train am besten (beste andere: {best['name']} {best['Train_R']:+.3f} vs. {base['Train_R']:+.3f})"); continue
        better = all(best[f"{ab}_R"] > base[f"{ab}_R"] for ab in AB[1:])
        vm = S["v"].str.split(",").apply(lambda l: str(int(best["vi"])) in l)
        b0 = S["v"].str.split(",").apply(lambda l: "0" in l)
        o = S["abschnitt"].isin(AB[1:])
        x, y = S[vm & o]["R_net_5000"].to_numpy(), S[b0 & o]["R_net_5000"].to_numpy()
        p = perm_p(x, y)
        verdict = "BESTANDEN" if better and p <= 0.05 / k else "nicht bestanden"
        print(f"  {g:<12} Train-Bester: {best['name']} · " + " / ".join(f"{best[f'{ab}_R']:+.3f} vs {base[f'{ab}_R']:+.3f}" for ab in AB)
              + f" · p {p:.4f} → {verdict}")
    D.to_csv("sweep_result.csv", index=False)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["signals", "analyse"])
    ap.add_argument("--data"); ap.add_argument("--shard", type=int, default=0); ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--out", default="out"); ap.add_argument("--signals"); ap.add_argument("--trades")
    a = ap.parse_args()
    signals(a) if a.cmd == "signals" else analyse(a)
