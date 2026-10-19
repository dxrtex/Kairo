"""Protokoll v3.0 §8 – Nebenanalyse N1: 4H-Einstieg für Kairo-Signale mit Dukascopy-Stundenkerzen (ab 2017).

python -m research.strategy_championship.v3.h4_side --data V1DIR --signals s01_signals_full.parquet --duka DIR --out OUT

A (Referenz) Tages-Einstieg: Basis-Regel (h4live.base_state) – Kauf zur Eröffnung in der Basis, Stop = Basistief − 0,25 ATR.
B (4H): exakt h4live.evaluate („HB|RMBS“) – gleiche Basis/gleicher Stop, 4H-Auslöser, Kauf zur Eröffnung der nächsten 4H-Kerze.
Ausstieg für beide gleich: Stop; ab Tag 10 Schluss < EMA20 (Tagesschluss) → nächste Eröffnung; spätestens Schluss Tag 40.
Kosten in R: voller Spread (US 0,10 %, DE 0,15 %) × Einstieg ÷ Risiko; Stress: 2 × Spread + 2 × 0,1 % Slippage.
"""

from __future__ import annotations

import argparse
import json
import lzma
import re
import struct
import zipfile
from datetime import datetime, timezone
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

from backend import h4live as HL
from backend.shortswing import QRULE

from ..data import UNIVERSE, adjusted
from ..s01 import clean

SPREAD = {"us": 0.001, "de": 0.0015}
SLIP = 0.001
SECTIONS = {"2017–2021": ("2017-01-01", "2021-12-31"), "2022–2026 (Hinweis)": ("2022-01-01", "2026-10-16")}
TZ = {"us": ("America/New_York", 9, 15), "de": ("Europe/Berlin", 9, 17)}   # Stundenkerzen mit Beginn in [von, bis] Ortszeit
NOW = datetime(2030, 1, 1, tzinfo=timezone.utc)
PRE, POST = 90, 100        # Stundenkerzen je Signal: 90 Tage Vorlauf (Indikatoren), 100 Tage danach (Basis + 4H-Fenster + max. 40 Tage)
_G: dict = {}


def duka_symbol(t: str) -> tuple[str, str] | None:
    if t.endswith(".DE"):
        return re.sub(r"[-.]", "", t[:-3]).upper() + "DEEUR", "de"
    if "." not in t:
        return re.sub(r"[-.]", "", t).upper() + "USUSD", "us"
    return None


def read_hourly(files: dict, sym: str) -> pd.DataFrame | None:
    """files: {'h1/SYM/YYYY-MM.bi5': bytes}. → Stundenkerzen (UTC) mit Open/High/Low/Close."""
    rows = []
    for k in sorted(x for x in files if x.startswith(f"h1/{sym}/") and x.endswith(".bi5")):
        y, m = map(int, Path(k).stem.split("-"))
        t0 = int(datetime(y, m + 1, 1, tzinfo=timezone.utc).timestamp())
        raw = lzma.decompress(files[k], format=lzma.FORMAT_ALONE)
        for ts, o, c, lo, hi, v in struct.iter_unpack(">5if", raw):
            rows.append((t0 + ts, o, hi, lo, c, v))
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["ts", "Open", "High", "Low", "Close", "Volume"]).drop_duplicates("ts")
    df.index = pd.to_datetime(df["ts"], unit="s", utc=True)
    df = df[df["Volume"] > 0]                       # Dukascopy liefert außerhalb der Handelszeit flache Kerzen ohne Umsatz
    return df[["Open", "High", "Low", "Close"]].astype(float)


def read_hourly_v(files: dict, sym: str) -> pd.DataFrame | None:
    """Wie read_hourly, mit Volumen (für S20-Auslöser: 4H-Volumen gegen eigenen Schnitt)."""
    rows = []
    for k in sorted(x for x in files if x.startswith(f"h1/{sym}/") and x.endswith(".bi5")):
        y, m = map(int, Path(k).stem.split("-"))
        t0 = int(datetime(y, m + 1, 1, tzinfo=timezone.utc).timestamp())
        raw = lzma.decompress(files[k], format=lzma.FORMAT_ALONE)
        for ts, o, c, lo, hi, v in struct.iter_unpack(">5if", raw):
            rows.append((t0 + ts, o, hi, lo, c, v))
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["ts", "Open", "High", "Low", "Close", "Volume"]).drop_duplicates("ts")
    df.index = pd.to_datetime(df["ts"], unit="s", utc=True)
    df = df[df["Volume"] > 0]
    return df[["Open", "High", "Low", "Close", "Volume"]].astype(float)


def session(hx: pd.DataFrame, reg: str) -> pd.DataFrame:
    tz, h0, h1 = TZ[reg]
    loc = hx.index.tz_convert(tz)
    keep = (loc.hour >= h0) & (loc.hour <= h1) & (loc.dayofweek < 5)
    out = hx[keep].copy()
    out.index = loc[keep].tz_localize(None)         # Ortszeit ohne Zeitzone (wie to4h erwartet)
    return out


def scale_to_daily(hx: pd.DataFrame, daily: pd.DataFrame) -> tuple[pd.DataFrame | None, float]:
    """Preisniveau je Tag auf die (bereinigten) Yahoo-Tageskerzen: Faktor = Tagesschluss Yahoo ÷ letzter Stundenschluss,
    geglättet (Median 5 Tage). Rückgabe (skalierte Kerzen, Median-Abweichung des Rohfaktors)."""
    last = hx.groupby(hx.index.normalize())["Close"].last()
    r = (daily["Close"].reindex(last.index) / last).dropna()
    if len(r) < 50:
        return None, np.nan
    lr = np.log(r)
    dev = float((lr - lr.rolling(5, center=True, min_periods=1).median()).abs().median())
    f = np.exp(lr.rolling(5, center=True, min_periods=1).median())
    fac = pd.Series(hx.index.normalize(), index=hx.index).map(f)
    ok = fac.notna().to_numpy()
    out = hx[ok].mul(fac[ok].to_numpy(), axis=0)
    return out, dev


def daily_trade(df: pd.DataFrame, idx: int, bs: dict, c0: float) -> dict | None:
    """Referenz A auf Tageskerzen: Einstieg Eröffnung Basis-Folgetag, Stop, EMA20 ab Tag 10, max. 40."""
    s = bs["s"]
    k0 = idx + 1 + s                                # Einstiegstag (Index im Tagesrahmen)
    if "e" not in bs or k0 >= len(df):
        return None
    e, sl = bs["e"] * c0, bs["sl"] * c0
    if not (sl < e) or (e - sl) / e > 0.25 or (e - sl) / e < 0.004:
        return None
    o, lo, c = (df[k].to_numpy(float) for k in ("Open", "Low", "Close"))
    ema = df["Close"].ewm(span=20, adjust=False).mean().to_numpy(float)
    for j in range(k0, min(len(df), k0 + HL.HOLD)):
        day = j - k0 + 1
        if lo[j] <= sl:
            x = min(sl, o[j]) if j > k0 else sl
            return {"e": e, "sl": sl, "x": x, "res": "stop", "ed": str(df.index[k0].date()), "days": day}
        if day >= HL.EMA_FROM and c[j] < ema[j] and day < HL.HOLD:
            if j + 1 < len(df):
                return {"e": e, "sl": sl, "x": o[j + 1], "res": "ema", "ed": str(df.index[k0].date()), "days": day + 1}
            return None
        if day == HL.HOLD:
            return {"e": e, "sl": sl, "x": c[j], "res": "zeit", "ed": str(df.index[k0].date()), "days": day}
    return None


def _one(args):
    t, d = args
    df, hx, reg = _G["daily"][t], _G["hx"][t], _G["reg"][t]
    D = pd.Timestamp(d)
    i = int(df.index.searchsorted(D))
    if i >= len(df) or df.index[i] != D:
        return None
    sub = hx[(hx.index >= D - pd.Timedelta(days=PRE)) & (hx.index <= D + pd.Timedelta(days=POST))]
    if len(sub) < 200:
        return {"t": t, "d": d, "skip": "zu wenig Stundenkerzen"}
    dfw = df.iloc[: min(len(df), i + 80)]
    ev = HL.evaluate(dfw, d, sub, NOW)
    out = {"t": t, "d": d, "reg": reg, "st": ev.get("st")}
    if ev.get("base") is None:
        return out
    px = HL._px(dfw, i)
    bs = HL.base_state(px, QRULE)
    if bs.get("st") == "base":
        a = daily_trade(dfw, i, bs, px["c0"])
        if a:
            out["A"] = a
    tr = ev.get("trade")
    if tr and "x" in tr:
        out["B"] = {"e": tr["e"], "sl": tr["sl"], "x": tr["x"], "res": tr.get("res"), "ed": tr.get("ed")}
    return out


def r_net(tr: dict, reg: str, stress: bool) -> float:
    e, sl, x = tr["e"], tr["sl"], tr["x"]
    risk = e - sl
    sp = SPREAD[reg] * (2 if stress else 1) + (2 * SLIP if stress else 0.0)
    return (x - e) / risk - sp * e / risk


def perm_p(b: np.ndarray, a: np.ndarray, n: int = 10_000, seed: int = 7) -> float:
    if not len(a) or not len(b):
        return float("nan")
    obs = b.mean() - a.mean()
    pool = np.concatenate([b, a])
    rng, cnt = np.random.default_rng(seed), 0
    for _ in range(n):
        rng.shuffle(pool)
        cnt += pool[: len(b)].mean() - pool[len(b):].mean() >= obs
    return float((cnt + 1) / (n + 1))


def needed_months(signals: str, out: str) -> int:
    """Liste der Dukascopy-Monatsdateien rund um jeden Kairo-Treffer ab 2017 (Monat 0-basiert wie im Datafeed)."""
    sig = pd.read_parquet(signals, columns=["ticker", "date"])
    sig["date"] = pd.to_datetime(sig["date"])
    sig = sig[sig["date"] >= "2017-01-01"]
    keys = set()
    for t, d in sig.itertuples(index=False):
        m = duka_symbol(t)
        if not m:
            continue
        for p in pd.period_range(d - pd.Timedelta(days=PRE), d + pd.Timedelta(days=POST), freq="M"):
            if p <= pd.Period("2026-09", "M"):
                keys.add(f"h1/{m[0]}/{p.year}-{p.month - 1:02d}.bi5")
    Path(out).write_text("\n".join(sorted(keys)))
    print(len(sig), "Signale →", len(keys), "Monatsdateien")
    return 0


def main(argv=None) -> int:
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "liste":
        return needed_months(sys.argv[2], sys.argv[3])
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--signals", required=True)
    ap.add_argument("--duka", required=True, help="Ordner mit dukascopy_h1*.zip")
    ap.add_argument("--out", default="h4_out")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    files = {}
    for z in sorted(Path(a.duka).glob("*.zip")):
        with zipfile.ZipFile(z) as zz:
            for n in zz.namelist():
                files[n] = zz.read(n)
    syms = sorted({n.split("/")[1] for n in files if n.startswith("h1/") and n.count("/") == 2})
    uni = pd.read_csv(UNIVERSE)
    tick = {}
    for t in uni["ticker"]:
        m = duka_symbol(t)
        if m and m[0] in syms:
            tick[t] = m
    sig = pd.read_parquet(a.signals)
    sig = sig[sig["ticker"].isin(tick)].copy()
    sig["date"] = pd.to_datetime(sig["date"])
    sig = sig[sig["date"] >= "2017-01-01"]
    px = pd.read_parquet(Path(a.data) / "prices_v1.parquet", filters=[("ticker", "in", sorted(sig["ticker"].unique()))])
    daily, hxd, reg, cover = {}, {}, {}, {"symbole_dukascopy": len(syms), "titel_mit_signalen": int(sig["ticker"].nunique())}
    excl = []
    for t, g in px.groupby("ticker"):
        dfa = adjusted(clean(g.drop(columns="ticker").set_index("date").sort_index()))
        dfa.index = pd.to_datetime(dfa.index)
        sym, rg = tick[t]
        h = read_hourly(files, sym)
        if h is None:
            excl.append((t, "keine Stundenkerzen"))
            continue
        h = session(h, rg)
        hs, dev = scale_to_daily(h, dfa)
        if hs is None or not (dev <= 0.02):
            excl.append((t, f"Preisabgleich unplausibel ({dev:.3f})" if hs is not None else "zu wenige gemeinsame Tage"))
            continue
        daily[t], hxd[t], reg[t] = dfa[["Open", "High", "Low", "Close"]], hs, rg
    cover["titel_verwendet"], cover["ausgeschlossen"] = len(daily), excl
    sig = sig[sig["ticker"].isin(daily)]
    _G.update(daily=daily, hx=hxd, reg=reg)
    jobs = [(r.ticker, str(r.date.date())) for r in sig.drop_duplicates(["ticker", "date"]).itertuples(index=False)]
    with Pool() as pool:
        res = [r for r in pool.map(_one, jobs, chunksize=20) if r]
    rows = []
    for r in res:
        for v in ("A", "B"):
            if v in r:
                tr = r[v]
                rows.append({"ticker": r["t"], "signal": r["d"], "reg": r["reg"], "v": v, "entry_day": tr["ed"], "res": tr["res"],
                             "R_basis": r_net(tr, r["reg"], False), "R_stress": r_net(tr, r["reg"], True)})
    T = pd.DataFrame(rows)
    T.to_csv(out / "h4_trades.csv", index=False)
    summ = {"coverage": cover, "signale": len(jobs), "status": pd.Series([r.get("st") for r in res]).value_counts().to_dict(), "abschnitte": {}}
    for name, (s, e) in SECTIONS.items():
        x = T[(T["signal"] >= s) & (T["signal"] <= e)]
        A, Bv = x[x["v"] == "A"], x[x["v"] == "B"]
        yrs = (pd.Timestamp(e) - pd.Timestamp(s)).days / 365.25
        sec = {}
        for col in ("R_basis", "R_stress"):
            sec[col] = {"A_n": int(len(A)), "B_n": int(len(Bv)), "A_mean": float(A[col].mean()) if len(A) else None,
                        "B_mean": float(Bv[col].mean()) if len(Bv) else None,
                        "A_R_pro_Jahr": float(A[col].sum() / yrs), "B_R_pro_Jahr": float(Bv[col].sum() / yrs),
                        "A_treffer": float((A[col] > 0).mean()) if len(A) else None,
                        "B_treffer": float((Bv[col] > 0).mean()) if len(Bv) else None,
                        "p_perm_B_gt_A": perm_p(Bv[col].to_numpy(), A[col].to_numpy())}
        summ["abschnitte"][name] = sec
    s = summ["abschnitte"]["2017–2021"]["R_stress"]
    summ["entscheidung"] = {"B_besser": bool(s["B_n"] >= 30 and s["B_mean"] is not None and s["A_mean"] is not None
                                             and s["B_mean"] > s["A_mean"] and s["p_perm_B_gt_A"] <= 0.05),
                            "regel": "Ø R netto (Stress) B > A und Permutations-p ≤ 0,05 auf 2017–2021, mind. 30 B-Trades"}
    (out / "h4_result.json").write_text(json.dumps(summ, indent=1, ensure_ascii=False, default=str))
    print(json.dumps({k: v for k, v in summ.items() if k != "coverage"}, indent=1, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
