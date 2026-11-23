"""Profit-Studie (23.11.2026): Short-Trendregeln, Filter für Long-Treffer, Zeitraum der Marktampel – VORAB FESTGELEGT.

Wunsch Jonny: Long- und Short-Setups so profitabel wie möglich, Marktampel so präzise wie möglich, Sektorrotation früh
erkennen. Regel (Antwort 23.11.): testen, Ergebnisse vorlegen, live ändert sich erst nach seinem OK.

Gegen Selbsttäuschung ist ALLES unten vor dem ersten Lauf festgelegt (Parameter, Varianten, Annahmekriterien):
- Lernzeitraum: Signale vor dem 01.01.2023 · Prüfzeitraum: ab 01.01.2023 (nur zur Bestätigung, nie zum Auswählen).
- Kosten Short: 0,10 % je Seite + 0,02 % je Haltetag (Finanzierung Put-Turbo) · Depot 3.000 €, 0,99 € je Order, 5 Plätze, 1 % Risiko.
- Annahme Short-Variante: Prüfzeitraum Ø ≥ +0,15 R netto UND Lernzeitraum Ø > 0 UND n(Prüf) ≥ 100 UND Monats-Block-
  Bootstrap p < 0,05 / Zahl der Varianten UND Depot im Prüfzeitraum > 0 % p. a. UND besser als Zufalls-Short (Kontrolle).
- Annahme Long-Filter (auf Kairo-Regel B60): Prüfzeitraum Ø R mindestens 0,15 R über allen Trades desselben Zeitraums UND
  gleiche Richtung im Lernzeitraum UND n(Prüf) ≥ 50 UND Bootstrap p < 0,05 / Zahl der Filter UND Depot (Prüf) besser.
- Marktampel-Zeitraum: Auswahl nur nach Lernzeitraum 1995–2009 (Calmar = Rendite / größter Rückgang bei „investiert ab
  Gelb“), Bestätigung 2010–2026. Übernahme nur, wenn die Variante auch 2010–2026 besser ist als die heutige (5 Tage / 2 Wochen).

    python tools/research/profit_study.py prices SHARD SHARDS      → px_SHARD.pkl.gz (Kurse 10 Jahre)
    python tools/research/profit_study.py study PXDIR AKDIR         → Bericht (AKDIR = Kairo-Treffer aus ampelkairo.yml)
"""
from __future__ import annotations

import gzip
import pickle
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

SPLIT = "2023-01-01"
COST_SIDE, COST_DAY = 0.001, 0.0002
SHORT_RULES = {}          # wird unten befüllt (Name → (Signal, Ausstieg))


# ---------------------------------------------------------------- Kurse holen (Shard)
def prices(shard: int, shards: int) -> None:
    from backend.data_provider import YFinanceProvider
    from backend.universe import load as load_universe

    u = load_universe()
    tickers = list(u["ticker"])
    random.Random(11).shuffle(tickers)                 # dieselbe Auswahl wie backend/bilanz.py
    mine = tickers[:1600][shard::shards]
    data = YFinanceProvider().history(mine, "10y")
    meta = u.set_index("ticker").reindex(list(data)).reset_index()[["ticker", "sector", "region", "currency"]].to_dict("records")
    px = {t: df[["Open", "High", "Low", "Close", "Volume"]].astype("float32") for t, df in data.items()}
    with gzip.open(f"px_{shard}.pkl.gz", "wb") as f:
        pickle.dump({"px": px, "meta": meta}, f)
    print(f"Shard {shard}: {len(px)} von {len(mine)} Aktien")


# ---------------------------------------------------------------- Hilfen
def _yf(t, start="1993-01-01"):
    import yfinance as yf
    d = yf.Ticker(t).history(period="max", interval="1d", auto_adjust=True)
    d.index = pd.to_datetime(d.index).tz_localize(None).normalize()
    return d[d.index >= start][["Open", "High", "Low", "Close", "Volume"]]


def ema(x, n):
    return pd.Series(x).ewm(span=n, adjust=False).mean().to_numpy()


def rsi(c, n=14):
    s = pd.Series(c)
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return (100 - 100 / (1 + up / dn.replace(0, np.nan))).to_numpy()


def atr(h, l, c, n=14):
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    return pd.Series(tr).ewm(alpha=1 / n, adjust=False).mean().to_numpy()


def boot_p(vals, dates, base=0.0, n=2000, seed=7):
    """Einseitiger Monats-Block-Bootstrap: Anteil der Stichproben mit Mittelwert ≤ base."""
    if len(vals) < 10:
        return 1.0
    df = pd.DataFrame({"v": vals, "m": [d[:7] for d in dates]})
    g = [x.to_numpy() for _, x in df.groupby("m")["v"]]
    rng = np.random.default_rng(seed)
    hit = 0
    for _ in range(n):
        s = np.concatenate([g[i] for i in rng.integers(0, len(g), len(g))])
        hit += s.mean() - base <= 0
    return hit / n


def stat(rs):
    r = np.array([x for x in rs if x is not None and np.isfinite(x)])
    if not len(r):
        return {"n": 0}
    return {"n": int(len(r)), "r": round(float(r.mean()), 3), "win": round(float((r > 0).mean()), 3), "sum": round(float(r.sum()), 1)}


def fmt(s):
    return "n=0" if not s.get("n") else f"n={s['n']:5d}  Ø {s['r']:+.3f} R  Gewinner {s['win'] * 100:4.1f} %  Summe {s['sum']:+8.1f} R"


# ---------------------------------------------------------------- Short-Trade simulieren
def sim_short(o, h, l, c, e20, i, stop, ex):
    """Einstieg Eröffnung i+1. ex = ('ema', max_tage) Ausstieg Schluss über EMA 20 ab Tag 3 → nächste Eröffnung,
    oder ('tgt', max_tage, R) festes Ziel. Ergebnis im Format von backend.shortswing._depot_real."""
    n = len(c)
    if i + 2 >= n:
        return None
    en = o[i + 1]
    if not np.isfinite(en) or en <= 0 or en >= stop:
        return None
    risk = stop - en
    rp = risk / en
    if rp <= 0.005 or rp > 0.15:
        return None
    tgt = en - ex[2] * risk if ex[0] == "tgt" else None
    path, xp, k = [], None, i + 1
    last = min(n - 1, i + ex[1])
    while k <= last:
        if h[k] >= stop:                                       # Stop (Kurslücke: Eröffnung)
            xp = max(stop, o[k]) if k > i + 1 else max(stop, en)
        elif tgt is not None and l[k] <= tgt:
            xp = min(tgt, o[k]) if k > i + 1 else tgt
        elif ex[0] == "ema" and k - i >= 3 and c[k] > e20[k] and k + 1 < n:
            xp, k = o[k + 1], k + 1
        if xp is not None:
            path.append((en - xp) / risk)
            break
        path.append((en - c[k]) / risk)
        k += 1
    if xp is None:
        if last < i + ex[1]:                                   # Daten enden vor dem Ausstieg → nicht werten
            return None
        xp = c[last]
    days = len(path)
    gross = (en - xp) / risk
    net = gross - (2 * COST_SIDE + COST_DAY * days) / rp
    return {"d": days, "rp": float(rp), "lev": 1, "path": [float(x) for x in path], "net": float(net), "fee_r": 0.0, "orders": 2}


# ---------------------------------------------------------------- Studie
def load_px(pxdir):
    px, meta = {}, {}
    for p in sorted(Path(pxdir).glob("**/px_*.pkl.gz")):
        with gzip.open(p, "rb") as f:
            d = pickle.load(f)
        for t, df in d["px"].items():
            df = df.copy()
            df.index = pd.to_datetime(df.index)
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            df.index = df.index.normalize()
            px[t] = df[~df.index.duplicated(keep="last")]
        meta.update({m["ticker"]: m for m in d["meta"]})
    return px, meta


def market_levels():
    from backend import marketlight as ML
    h = {t: _yf(t, "1995-01-01") for t in ["^GSPC", "^NDX", "^VIX", "^VIX3M", "HYG", "IEF"]}
    cr = ML.credit_ratio(h.get("HYG"), h.get("IEF"))

    def fin(t):
        R = ML.raw_levels(h[t], h["^VIX"], h.get("^VIX3M"), cr)
        day = ML.smooth(R["lv"], ML.P["up_n"])
        ws, _ = ML.week_levels(h[t], h["^VIX"])
        return ML.combine(ws.reindex(day.index, method="ffill").shift(1), day)

    return pd.concat([fin("^GSPC"), fin("^NDX")], axis=1).dropna().min(axis=1), h


def short_study(px, meta, mlv, spy, sec):
    rules = {
        "S1 Trend-Rücksetzer (EMA-Ausstieg)": ("s1", ("ema", 40)),
        "S1 Trend-Rücksetzer (Ziel 2R, 20 T.)": ("s1", ("tgt", 20, 2.0)),
        "S2 Ausbruch nach unten (EMA-Ausstieg)": ("s2", ("ema", 40)),
        "S2 Ausbruch nach unten (Ziel 2R, 20 T.)": ("s2", ("tgt", 20, 2.0)),
        "S3 = S1 + Ampel Orange/Rot (EMA)": ("s3", ("ema", 40)),
        "S3 = S1 + Ampel Orange/Rot (Ziel 2R)": ("s3", ("tgt", 20, 2.0)),
        "S4 = S2 + Ampel Orange/Rot (EMA)": ("s4", ("ema", 40)),
        "S4 = S2 + Ampel Orange/Rot (Ziel 2R)": ("s4", ("tgt", 20, 2.0)),
        "S5 = S1 + schwacher Sektor (EMA)": ("s5", ("ema", 40)),
    }
    trades = {k: [] for k in rules}
    ctrl = []
    spy_c = spy["Close"]
    for t, df in px.items():
        df = df.dropna()
        if len(df) < 300:
            continue
        o, h, l, c, v = (df[k].to_numpy(float) for k in ("Open", "High", "Low", "Close", "Volume"))
        idx = df.index
        s50 = pd.Series(c).rolling(50).mean().to_numpy()
        s200 = pd.Series(c).rolling(200).mean().to_numpy()
        e20 = ema(c, 20)
        a = atr(h, l, c)
        r14 = rsi(c)
        adv = pd.Series(c * v).rolling(20).mean().to_numpy()
        v20 = pd.Series(v).rolling(20).mean().to_numpy()
        lo50 = pd.Series(l).rolling(50).min().shift(1).to_numpy()
        hi5 = pd.Series(h).rolling(5).max().to_numpy()
        hi10 = pd.Series(h).rolling(10).max().to_numpy()
        sp = spy_c.reindex(idx).ffill().to_numpy(float)
        rs63 = c / np.r_[np.full(63, np.nan), c[:-63]] - sp / np.r_[np.full(63, np.nan), sp[:-63]]
        ml = mlv.reindex(idx).ffill().shift(1).to_numpy(float)        # Stand am Vortag (kein Blick in die Zukunft)
        se = sec.get(meta.get(t, {}).get("sector"))
        srs = se.reindex(idx).ffill().to_numpy(float) if se is not None else np.full(len(c), np.nan)
        down = (c < s200) & (s50 < s200) & (s200 < np.r_[np.full(20, np.nan), s200[:-20]]) & (c >= 2) & (adv >= 2e6)
        s1 = down & (rs63 <= -0.10) & (h >= e20) & (c < e20) & (c < o) & (r14 >= 40) & (r14 <= 60)
        s2 = down & (c < lo50) & (v > 1.5 * v20)
        sig = {"s1": s1, "s2": s2, "s3": s1 & (ml <= 1), "s4": s2 & (ml <= 1), "s5": s1 & (srs < 0)}
        stops = {"s1": hi5 + 0.25 * a, "s2": np.minimum(hi10 + 0.25 * a, c + 3 * a)}
        stops.update(s3=stops["s1"], s4=stops["s2"], s5=stops["s1"])
        for name, (sk, ex) in rules.items():
            last = -99
            for i in np.flatnonzero(sig[sk]):
                if i < 260 or i - last <= 10:
                    continue
                sm = sim_short(o, h, l, c, e20, i, stops[sk][i], ex)
                if sm:
                    last = i
                    trades[name].append({"t": t, "sd": str(idx[i].date()), "d": str(idx[i + 1].date()), "sm": sm, "rk": 0.01,
                                         "prio": -float(a[i] / c[i]), "r1": sm["net"]})
        for i in np.flatnonzero(down)[::15]:                     # Kontrolle: Zufalls-Short im Abwärtstrend
            if i < 260:
                continue
            sm = sim_short(o, h, l, c, e20, i, hi5[i] + 0.25 * a[i], ("ema", 40))
            if sm:
                ctrl.append({"sd": str(idx[i].date()), "r1": sm["net"]})
    return trades, ctrl


def long_study(akdir, px, meta, mlv, spy, sec):
    from backend.exitstudy10 import rows_for
    from backend.volstudy import _hits
    hits = _hits(str(akdir))
    seen, hh = set(), []
    for e in hits:
        if (e["t"], e["d"]) not in seen:
            seen.add((e["t"], e["d"]))
            hh.append(e)
    rows = []
    for e in hh:
        for x in rows_for([e], {"hold": 60, "ema_x": 20, "ema_from": 10}):
            x["t"] = e["t"]
            x["f"] = e.get("f") or {}
            rows.append(x)
    spy_c = spy["Close"]
    cache = {}
    for x in rows:
        t, d = x["t"], pd.Timestamp(x["sd"])
        df = px.get(t)
        x["rs63"] = x["a200"] = x["srs"] = None
        if df is not None:
            if t not in cache:
                c = df["Close"].astype(float)
                cache[t] = (c, c.rolling(200).mean())
            c, s200 = cache[t]
            i = c.index.searchsorted(d, side="right") - 1
            if i >= 63:
                sp = spy_c.reindex(c.index).ffill()
                x["rs63"] = float(c.iloc[i] / c.iloc[i - 63] - sp.iloc[i] / sp.iloc[i - 63])
                x["a200"] = bool(c.iloc[i] > s200.iloc[i]) if np.isfinite(s200.iloc[i]) else None
        se = sec.get(meta.get(t, {}).get("sector"))
        if se is not None:
            j = se.index.searchsorted(d, side="right") - 1
            x["srs"] = float(se.iloc[j]) if j >= 0 else None
        j = mlv.index.searchsorted(d - pd.Timedelta(days=1), side="right") - 1
        x["lv"] = int(mlv.iloc[j]) if j >= 0 else None
    filters = {
        "F1 relative Stärke 3 M. > 0 (stärker als S&P 500)": lambda x: x["rs63"] is not None and x["rs63"] > 0,
        "F2 relative Stärke 3 M. < 0 (schwächer als S&P 500)": lambda x: x["rs63"] is not None and x["rs63"] < 0,
        "F3 über der 200-Tage-Linie": lambda x: x["a200"] is True,
        "F4 unter der 200-Tage-Linie": lambda x: x["a200"] is False,
        "F5 Sektor stärker als S&P 500 (13 Wochen)": lambda x: x["srs"] is not None and x["srs"] > 0,
        "F6 ruhige Aktie (ATR < 3 %)": lambda x: (x["f"].get("atrp") or 1) < 0.03,
    }
    return rows, filters


def ampel_variants(h):
    from backend import marketlight as ML
    from backend.marketphase import market_phase
    cr = ML.credit_ratio(h.get("HYG"), h.get("IEF"))
    out = {}
    raw = {t: ML.raw_levels(h[t], h["^VIX"], h.get("^VIX3M"), cr)["lv"] for t in ("^GSPC", "^NDX")}
    for cn in (1, 2, 3):
        wk = {}
        for t in ("^GSPC", "^NDX"):
            ph = market_phase(h[t], h["^VIX"], keep=100000, confirm_n=cn)
            wk[t] = pd.Series({pd.Timestamp(d): ML.WK[k] for d, k in ph["hist"]}).sort_index()
        for up in (3, 5, 10):
            lv = []
            for t in ("^GSPC", "^NDX"):
                day = ML.smooth(raw[t], up)
                lv.append(ML.combine(wk[t].reindex(day.index, method="ffill").shift(1), day))
            out[(cn, up)] = pd.concat(lv, axis=1).dropna().min(axis=1)
    return out


def ampel_eval(lv, px, a, b):
    """Investiert im Nasdaq 100 bei Ampel ≥ Gelb (Stand Vortag), sonst Cash. Rendite, Rückgang, Wechsel/Jahr,
    Ø Handelstage vom Tief eines ≥ 15-%-Rückgangs bis zur Rückkehr auf ≥ Gelb."""
    c = px["Close"].reindex(lv.index).ffill()
    c = c[(c.index >= a) & (c.index < b)]
    l = lv.reindex(c.index).shift(1)
    r = c.pct_change().fillna(0)
    inv = (l >= 2).astype(float)
    eq = (1 + r * inv).cumprod()
    yrs = max(0.5, (c.index[-1] - c.index[0]).days / 365.25)
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    mdd = float((1 - eq / eq.cummax()).max())
    flips = float((inv.diff().abs() > 0).sum() / yrs)
    dd = c / c.cummax() - 1
    lags, i, n = [], 0, len(c)
    while i < n:
        if dd.iloc[i] <= -0.15:
            j = i
            while j < n and dd.iloc[j] < 0:
                j += 1
            tr = int(np.argmin(c.iloc[i:j].to_numpy())) + i
            k = tr
            while k < n and not (l.iloc[k] >= 2):
                k += 1
            if k < n:
                lags.append(k - tr)
            i = j
        else:
            i += 1
    bh = (c.iloc[-1] / c.iloc[0]) ** (1 / yrs) - 1
    return {"cagr": round(float(cagr), 3), "mdd": round(mdd, 3), "calmar": round(float(cagr / mdd) if mdd else 0, 2),
            "flips": round(flips, 1), "lag": round(float(np.mean(lags)), 0) if lags else None, "bh": round(float(bh), 3)}


def study(pxdir, akdir):
    from backend.capstudy import run
    print("VORAB FESTGELEGT: Lernen < 2023-01-01, Prüfen ≥ 2023-01-01; Kriterien siehe Kopf der Datei.\n", flush=True)
    px, meta = load_px(pxdir)
    print(f"Kurse: {len(px)} Aktien", flush=True)
    mlv, h = market_levels()
    spy = _yf("SPY", "2010-01-01")
    from backend.analysis import SECTOR_ETF
    wk_spy = spy["Close"].resample("W-FRI").last()
    sec = {}
    for name, etf in SECTOR_ETF.items():
        try:
            w = _yf(etf, "2010-01-01")["Close"].resample("W-FRI").last()
            sec[name] = ((w / w.shift(13)) - (wk_spy / wk_spy.shift(13))).dropna()
        except Exception as e:
            print("Sektor fehlt", name, e)

    # ---- Short
    trades, ctrl = short_study(px, meta, mlv, spy, sec)
    k = len(trades)
    print(f"\n===== SHORT ({k} Varianten, Bootstrap-Schwelle {0.05 / k:.4f}) =====")
    cl, cp = [x["r1"] for x in ctrl if x["sd"] < SPLIT], [x["r1"] for x in ctrl if x["sd"] >= SPLIT]
    print(f"  Kontrolle Zufalls-Short im Abwärtstrend   Lernen {fmt(stat(cl))}\n{'':44s}Prüfen {fmt(stat(cp))}")
    ctrl_p = stat(cp).get("r", 0)
    for name, tr in trades.items():
        le = [x for x in tr if x["sd"] < SPLIT]
        pr = [x for x in tr if x["sd"] >= SPLIT]
        sl, sp_ = stat([x["r1"] for x in le]), stat([x["r1"] for x in pr])
        p = boot_p([x["r1"] for x in pr], [x["sd"] for x in pr])
        dep_all = run(tr, 3000, 0.99, 5) if len(tr) >= 20 else None
        dep_p = run(pr, 3000, 0.99, 5) if len(pr) >= 20 else None
        ok = (sp_.get("n", 0) >= 100 and sp_.get("r", -9) >= 0.15 and sl.get("r", -9) > 0 and p < 0.05 / k
              and dep_p and dep_p["cagr"] > 0 and sp_["r"] > ctrl_p)
        print(f"\n  {name}\n    Lernen {fmt(sl)}\n    Prüfen {fmt(sp_)}  p={p:.4f}")
        if dep_all:
            print(f"    Depot gesamt CAGR {dep_all['cagr']}  MaxDD {dep_all['mdd']}  Trades/Jahr {dep_all['trades_pa']}"
                  + (f" · Prüfzeitraum CAGR {dep_p['cagr']}  MaxDD {dep_p['mdd']}" if dep_p else ""))
        print(f"    → {'BESTANDEN' if ok else 'nicht bestanden'}", flush=True)

    # ---- Long
    rows, filters = long_study(akdir, px, meta, mlv, spy, sec)
    kf = len(filters)
    base_l = [x for x in rows if x["sd"] < SPLIT]
    base_p = [x for x in rows if x["sd"] >= SPLIT]
    bl, bp = stat([x["r1"] for x in base_l]), stat([x["r1"] for x in base_p])
    print(f"\n===== LONG: Kairo-Regel B60 mit Filtern ({kf} Filter, Bootstrap-Schwelle {0.05 / kf:.4f}) =====")
    print(f"  Alle Trades  Lernen {fmt(bl)}\n               Prüfen {fmt(bp)}")
    dpb = run(base_p, 3000, 0.99, 5) if len(base_p) >= 20 else None
    dab = run(rows, 3000, 0.99, 5)
    print(f"  Depot alle Trades gesamt CAGR {dab['cagr']} MaxDD {dab['mdd']}" + (f" · Prüfzeitraum CAGR {dpb['cagr']} MaxDD {dpb['mdd']}" if dpb else ""))
    for name, fn in filters.items():
        le, pr = [x for x in base_l if fn(x)], [x for x in base_p if fn(x)]
        sl, sp_ = stat([x["r1"] for x in le]), stat([x["r1"] for x in pr])
        p = boot_p([x["r1"] for x in pr], [x["sd"] for x in pr], base=bp.get("r", 0))
        dp = run(pr, 3000, 0.99, 5) if len(pr) >= 20 else None
        da = run([x for x in rows if fn(x)], 3000, 0.99, 5) if len(le) + len(pr) >= 20 else None
        ok = (sp_.get("n", 0) >= 50 and sp_.get("r", -9) - bp.get("r", 0) >= 0.15 and sl.get("r", -9) > bl.get("r", 0)
              and p < 0.05 / kf and dp and dpb and dp["cagr"] > dpb["cagr"])
        print(f"\n  {name}\n    Lernen {fmt(sl)}\n    Prüfen {fmt(sp_)}  p={p:.4f}")
        if da:
            print(f"    Depot gesamt CAGR {da['cagr']}  MaxDD {da['mdd']}" + (f" · Prüfzeitraum CAGR {dp['cagr']}  MaxDD {dp['mdd']}" if dp else ""))
        print(f"    → {'BESTANDEN' if ok else 'nicht bestanden'}", flush=True)
    print("\n  Nach Ampelfarbe (Vortag) – Lernen / Prüfen")
    for lvk, nm in ((3, "Grün"), (2, "Gelb"), (1, "Orange"), (0, "Rot")):
        print(f"    {nm:6s} {fmt(stat([x['r1'] for x in base_l if x['lv'] == lvk]))}  |  {fmt(stat([x['r1'] for x in base_p if x['lv'] == lvk]))}")

    # ---- Marktampel-Zeitraum
    print("\n===== MARKTAMPEL: Bestätigung Wochentrend × Wartezeit Heraufstufen (Nasdaq 100, investiert ab Gelb) =====")
    var = ampel_variants(h)
    res = []
    for key, lv in var.items():
        a = ampel_eval(lv, h["^NDX"], "1996-01-01", "2010-01-01")
        b = ampel_eval(lv, h["^NDX"], "2010-01-01", "2030-01-01")
        res.append((key, a, b))
    best = max(res, key=lambda x: x[1]["calmar"])
    for key, a, b in sorted(res, key=lambda x: -x[1]["calmar"]):
        tag = " ← heute" if key == (2, 5) else ""
        tag += " ← beste im Lernzeitraum" if key == best[0] else ""
        print(f"  {key[0]} Wo. / {key[1]:2d} T.  Lernen CAGR {a['cagr']:+.3f} MaxDD {a['mdd']:.3f} Calmar {a['calmar']:.2f} Wechsel/J {a['flips']:4.1f} "
              f"Rückkehr {a['lag']} T. | Prüfen CAGR {b['cagr']:+.3f} MaxDD {b['mdd']:.3f} Calmar {b['calmar']:.2f} Wechsel/J {b['flips']:4.1f} Rückkehr {b['lag']} T.{tag}")
    now = next(x for x in res if x[0] == (2, 5))
    print(f"  Kaufen und Halten Nasdaq 100: Lernen {now[1]['bh']:+.3f} p. a. · Prüfen {now[2]['bh']:+.3f} p. a.")
    better = best[0] != (2, 5) and best[2]["calmar"] > now[2]["calmar"]
    print(f"  → {'Variante ' + str(best[0]) + ' auch im Prüfzeitraum besser' if better else 'heutige Einstellung bleibt (keine Variante im Lernzeitraum und Prüfzeitraum besser)'}")


if __name__ == "__main__":
    if sys.argv[1] == "prices":
        prices(int(sys.argv[2]), int(sys.argv[3]))
    else:
        study(sys.argv[2], sys.argv[3])
