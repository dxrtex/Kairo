"""Protokoll v3.1 (29_PROTOCOL_V3_1.md) – S19 / S19-B / S19-C / S20 mit echten 4H-Kerzen (Dukascopy) und SEC-Daten.

Die Positionsführung und der Tagesablauf kommen unverändert aus dem Papier-Handel (paper/run.process_day, paper/core):
Backtest und Live-Test sind dieselbe Regel. Hier wird nur die Vergangenheit Tag für Tag durchgespielt; die Tagessignale
werden vorab je Titel berechnet (gleiche Formeln wie paper/core.s19_signal / s20_setup, zeitpunktgenaue Fundamentaldaten).

python -m research.strategy_championship.v3.s19s20 main --data V1 --sec SECDIR --duka DUKADIR --period test --out OUT
python -m research.strategy_championship.v3.s19s20 null --data V1 --sec SECDIR --duka DUKADIR --sid S19 --seed-start 0 --seed-n 25 --out OUT
python -m research.strategy_championship.v3.s19s20 combine --inp DIR --out OUT
"""

from __future__ import annotations

import argparse
import json
import os
import zipfile
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

from paper import core
from paper import run as PR

from ..data import UNIVERSE, adjusted
from ..s01 import clean
from . import h4_side as H
from . import strategies as S
from . import tax as T

SIDS = ["S19", "S19B", "S19C", "S20"]
PERIODS = {"test": ("2017-01-01", "2021-12-31"), "hinweis": ("2022-01-01", "2026-09-30")}
CAPS = (2000, 5000, 20000)
COSTS = {"prime": {"spread_mult": 1.0, "fee": 0.99, "slip": 0.0, "fx": 0.0},
         "prime_stress": {"spread_mult": 2.0, "fee": 1.99, "slip": 0.0005, "fx": 0.001}}   # wie v3.0
FX_T = {"USD": "EURUSD=X", "GBP": "EURGBP=X", "CHF": "EURCHF=X", "SEK": "EURSEK=X", "NOK": "EURNOK=X", "DKK": "EURDKK=X"}
# SIC → Sektor-Name (paper/core.SECTOR_ETF); Immobilien → Finanzen (XLF), Telekom/Medien → Technologie (XLK), Rest → SPY
SIC = [((100, 999), "Consumer Defensive"), ((1000, 1499), "Basic Materials"), ((1300, 1399), "Energy"), ((1500, 1799), "Industrials"),
       ((2000, 2199), "Consumer Defensive"), ((2200, 2399), "Consumer Cyclical"), ((2400, 2699), "Basic Materials"),
       ((2700, 2799), "Technology"), ((2800, 2829), "Basic Materials"), ((2830, 2836), "Healthcare"), ((2840, 2899), "Consumer Defensive"),
       ((2900, 2999), "Energy"), ((3000, 3399), "Basic Materials"), ((3400, 3569), "Industrials"), ((3570, 3579), "Technology"),
       ((3580, 3659), "Industrials"), ((3660, 3699), "Technology"), ((3700, 3799), "Consumer Cyclical"), ((3800, 3829), "Industrials"),
       ((3830, 3851), "Healthcare"), ((3852, 3999), "Consumer Cyclical"), ((4000, 4799), "Industrials"), ((4800, 4899), "Technology"),
       ((4900, 4999), "Utilities"), ((5000, 5199), "Industrials"), ((5200, 5999), "Consumer Cyclical"), ((6000, 6799), "Financial Services"),
       ((7000, 7369), "Consumer Cyclical"), ((7370, 7379), "Technology"), ((7380, 7999), "Consumer Cyclical"), ((8000, 8099), "Healthcare"),
       ((8100, 8999), "Industrials")]
_G: dict = {}


def sic_sector(sic) -> str | None:
    try:
        s = int(sic)
    except (TypeError, ValueError):
        return None
    hit = None
    for (a, b), name in SIC:                         # spätere, engere Bereiche überschreiben (Energie in Rohstoffe)
        if a <= s <= b:
            hit = name
    return hit


# ------------------------------------------------------------------ Daten
def load(a):
    px = pd.read_parquet(Path(a.data) / "prices_v1.parquet")
    bench = pd.read_parquet(Path(a.data) / "bench_v1.parquet")
    fxr = pd.read_parquet(Path(a.data) / "fx_v1.parquet")
    uni = pd.read_csv(UNIVERSE)
    files = {}
    for z in sorted(Path(a.duka).glob("*.zip")):
        with zipfile.ZipFile(z) as zz:
            for n in zz.namelist():
                if n.endswith(".bi5"):
                    files[n] = zz.read(n)
    syms = sorted({n.split("/")[1] for n in files})
    tick = {t: H.duka_symbol(t) for t in uni["ticker"]}
    tick = {t: m for t, m in tick.items() if m and m[0] in syms}
    daily, h4, info = {}, {}, {"dukascopy_symbole": len(syms), "titel": len(tick), "ausgeschlossen": []}
    for t, g in px[px["ticker"].isin(tick)].groupby("ticker"):
        g = g.drop(columns="ticker").set_index("date").sort_index()
        g.index = pd.to_datetime(g.index)
        d = adjusted(clean(g))[["Open", "High", "Low", "Close", "Volume"]]   # wie yfinance auto_adjust (Papier-Handel)
        hx = H.read_hourly_v(files, tick[t][0])
        if hx is None:
            info["ausgeschlossen"].append((t, "keine Stunden"))
            continue
        hs = H.session(hx, tick[t][1])
        sc, dev = H.scale_to_daily(hs[["Open", "High", "Low", "Close"]], d)
        if sc is None or not dev <= 0.02:
            info["ausgeschlossen"].append((t, f"Preisabgleich {dev}"))
            continue
        sc["Volume"] = hs["Volume"].reindex(sc.index)
        daily[t], h4[t] = d, core.to_h4(sc)
    fx = {}
    for c, yt in FX_T.items():
        s = fxr[fxr["ticker"] == yt].set_index("date")["Close"].sort_index()
        s.index = pd.to_datetime(s.index)
        fx[c] = s[s > 0]
    b = {t: g.drop(columns="ticker").set_index("date").sort_index() for t, g in bench.groupby("ticker")}
    for v in b.values():
        v.index = pd.to_datetime(v.index)
    return uni, daily, h4, fx, b, info


def fund_daily(sec: Path, daily: dict, splits: pd.DataFrame | None) -> dict:
    """Je US-Titel tägliche Reihe: Börsenwert (USD) und operative Marge (letztes GJ), zeitpunktgenau. + Sektor (SIC)."""
    cmap = pd.read_csv(sec / "cik_map.csv")
    t2c, t2s = dict(zip(cmap["ticker"], cmap["cik"])), dict(zip(cmap["ticker"], cmap["sic"]))
    tl = pd.read_csv(sec / "fund_timeline.csv.gz", parse_dates=["filed", "avail", "shares_end"])
    tl["avail"] = tl["avail"].astype("datetime64[ns]")
    out = {}
    for t, d in daily.items():
        if t not in t2c:
            continue
        g = tl[tl["cik"] == int(t2c[t])].sort_values("avail")
        if g.empty:
            continue
        q = pd.DataFrame({"date": d.index.astype("datetime64[ns]")})
        m = pd.merge_asof(q, g, left_on="date", right_on="avail", direction="backward").set_index("date")
        sf = np.array([S.split_factor(splits, t, s) if pd.notna(s) else np.nan for s in m["shares_end"]])
        raw_close = d["Close"]                                    # bereinigt; Split-Basis = heutige (wie v3.0)
        mcap = m["shares"].to_numpy() * sf * raw_close.to_numpy()
        out[t] = {"mcap": pd.Series(mcap, index=d.index), "opm": pd.Series(m["opm_fy"].to_numpy(), index=d.index),
                  "sector": sic_sector(t2s.get(t))}
    return out


def signals(mk, fund: dict, sec3: dict, bull: pd.Series, sid: str, start, end) -> dict:
    """{Datum: [Signal-dict]} – Formeln wie paper/core.s19_signal / s20_setup + Filter aus paper/run.new_setups."""
    out: dict = {}
    for t, d in mk.daily.items():
        x = mk.f(t)
        idx = x.index
        C, V = x["Close"].to_numpy(), x["Volume"].to_numpy()
        usd = 1.0 if mk.cur.get(t, "USD") == "USD" else None
        for i in np.flatnonzero((idx >= start) & (idx <= end)):
            if i < 210:
                continue
            D = idx[i]
            r = x.iloc[i]
            u = usd if usd is not None else mk.rate("SPY", D) / mk.rate(t, D)
            if not (r["adv"] * u >= 5e6 and r["Close"] * u >= 1.0):
                continue
            if sid.startswith("S19"):
                fd = fund.get(t)
                if fd is None or not (fd["mcap"].get(D, np.nan) >= 10e9 and fd["opm"].get(D, np.nan) > 0):
                    continue
                etf = core.SECTOR_ETF.get(fd["sector"], "SPY")
                sr = sec3.get(etf, {}).get(D)
                sg, vm = core.S19_VARIANTS[sid]
                s = core.s19_signal(x, i, sr, sg, vm)
            else:
                if not bool(bull.get(D, False)):
                    continue
                s = core.s20_setup(x, i)
                if s:
                    s["vr"] = float(r["Volume"] / x["Volume"].rolling(20).mean().iloc[i])
            if s:
                out.setdefault(D, []).append({"t": t, **s})
    return out


def pools(mk, fund: dict, bull: pd.Series, sid: str, days) -> dict:
    """Zufalls-Pool je Tag: S19 = Qualitäts-Pool (Börsenwert ≥ 10 Mrd., Marge > 0, liquide) unter der EMA20;
    S20 = alle liquiden Titel bei positivem Regime."""
    out = {}
    for D in days:
        p = []
        for t in mk.daily:
            x = mk.f(t)
            if D not in x.index:
                continue
            i = x.index.get_loc(D)
            if i < 210:
                continue
            r = x.iloc[i]
            if not (r["adv"] >= 5e6 and r["Close"] >= 1.0):
                continue
            if sid.startswith("S19"):
                fd = fund.get(t)
                if fd is None or not (fd["mcap"].get(D, np.nan) >= 10e9 and fd["opm"].get(D, np.nan) > 0 and r["Close"] < r["ema20"]):
                    continue
            p.append((t, float(r["Low"]), float(r["atr"])))
        out[D] = p
    return out


# ------------------------------------------------------------------ Simulation (Tagesablauf des Papier-Handels)
def simulate(sid: str, cash: float, cn: str, sig: dict, start, end, max_open: int) -> dict:
    mk, cal, bull = _G["mk"], _G["cal"], _G["bull"]
    c = COSTS[cn]
    mk.cost = c
    core.FEE = c["fee"]
    PR.MAX_OPEN = max_open
    st = {"sid": sid, "start": str(start.date()), "start_cash": cash, "cash": cash, "positions": [], "pending": [], "armed": [],
          "trades": [], "equity": [], "events": [], "last_day": None}
    days = cal[(cal >= start) & (cal <= end)]
    for k, D in enumerate(days):
        prev = cal[cal < D][-1]
        PR.process_day(st, mk, D, prev, cal, bool(bull.get(prev, False)))
        st["events"] = st["events"][-50:]
        busy = {p["t"] for p in st["positions"]} | {q["t"] for q in st["pending"]} | {a["t"] for a in st["armed"]}
        kk = int(np.searchsorted(cal.values, np.datetime64(D)))
        expiry = cal[min(kk + core.WINDOW, len(cal) - 1)]
        for s in sig.get(D, []):
            if s["t"] in busy or s["t"] not in mk.h4:
                continue
            st["pending"].append({**s, "day": str(D.date()), "expiry": str(expiry.date())})
            busy.add(s["t"])
    for p in list(st["positions"]):                                  # Ende: Verkauf zum letzten Schluss
        PR.close_pos(st, mk, p, mk.last_close(p["t"], days[-1]) or p["entry"], "ende", str(days[-1]))
    eq = pd.Series([e["eur"] for e in st["equity"]], index=pd.to_datetime([e["date"] for e in st["equity"]]))
    eq.iloc[-1] = st["cash"]
    return {"equity": eq, "trades": pd.DataFrame(st["trades"])}


def metrics(eq: pd.Series, tr: pd.DataFrame) -> dict:
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    r = eq.pct_change().dropna()
    dd = eq / eq.cummax() - 1
    out = {"cagr": float((eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1) if eq.iloc[-1] > 0 else -1.0, "max_dd": float(dd.min()),
           "sharpe": float(r.mean() / r.std() * np.sqrt(252)) if r.std() > 0 else None, "final": float(eq.iloc[-1]),
           "trades": int(len(tr))}
    if len(tr):
        out.update(win_rate=float((tr["pnl_eur"] > 0).mean()),
                   avg_r_net=float(tr["R_net"].dropna().mean()) if "R_net" in tr and tr["R_net"].notna().any() else None,
                   exits=tr["why"].value_counts().to_dict(), trades_pa=float(len(tr) / yrs))
    yr = {}
    for x in tr.itertuples(index=False) if len(tr) else []:
        y = pd.Timestamp(x.exit_ts).year
        yr.setdefault(y, {"stock_gain": 0.0, "etf_gain": 0.0, "div": 0.0, "vap": 0.0})["stock_gain"] += float(x.pnl_eur)
    out.update(T.after_tax(eq, T.taxes(yr)))
    return out


def setup(a) -> None:
    uni, daily, h4, fx, bench, info = load(a)
    mk = PR.Market(uni, daily, fx)
    mk.h4 = h4
    mk.cost = COSTS["prime"]
    base_spread = PR.Market.spread

    def spread(t, d, _m=mk):                       # volle Spanne; Stress: ×2 + 2 × (Slippage + FX-Aufschlag je Seite)
        c = _m.cost
        return base_spread(_m, t, d) * c["spread_mult"] + 2 * (c["slip"] + (c["fx"] if _m.cur.get(t, "USD") != "EUR" else 0.0))
    mk.spread = spread
    mk.cur["SPY"] = "USD"
    g = bench["^GSPC"]["Close"]
    bull = g > g.ewm(span=200, adjust=False).mean()
    cal = pd.DatetimeIndex(g.index[(g.index >= "2016-01-01") & (g.index <= "2026-10-16")])
    sec3 = {e: (bench[e]["Close"] / bench[e]["Close"].shift(3) - 1).to_dict() for e in set(core.SECTOR_ETF.values()) | {"SPY"} if e in bench}
    splits = pd.read_csv(a.splits, parse_dates=["date"]) if a.splits and Path(a.splits).exists() else None
    fund = fund_daily(Path(a.sec), daily, splits)
    _G.update(mk=mk, cal=cal, bull=bull, sec3=sec3, fund=fund, info=info, bench=bench, fx=fx)
    print(f"Setup: {len(daily)} Titel mit Stundenkerzen, Fundamentaldaten für {len(fund)} US-Titel", flush=True)


def _main_job(args):
    sid, per, cash, cn = args
    s, e = (pd.Timestamp(x) for x in PERIODS[per])
    r = simulate(sid, cash, cn, _G["sig"][(sid, per)], s, e, 10 if cash >= 20000 else 5)
    m = metrics(r["equity"], r["trades"])
    return (sid, per, cash, cn), m, r["equity"]


def cmd_main(a) -> int:
    setup(a)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sig, cnt = {}, {}
    for sid in SIDS:
        for per, (s, e) in PERIODS.items():
            sig[(sid, per)] = signals(_G["mk"], _G["fund"], _G["sec3"], _G["bull"], sid, pd.Timestamp(s), pd.Timestamp(e))
            cnt[f"{sid} · {per}"] = int(sum(len(v) for v in sig[(sid, per)].values()))
    _G["sig"] = sig
    print("Tagessignale:", cnt, flush=True)
    from ..engine import Costs, Order, run as erun
    e = {"ACWI": _G["bench"]["ACWI"][["Open", "High", "Low", "Close", "AdjClose"]].dropna()}
    s0, e0 = (pd.Timestamp(x) for x in PERIODS["test"])
    ecal = e["ACWI"].index[(e["ACWI"].index >= s0) & (e["ACWI"].index <= e0)]
    acw = {}
    for cn, co in (("prime", Costs(fee_eur=0.99, spread=0.001, fee_free_from=250.0)),
                   ("prime_stress", Costs(fee_eur=1.99, spread=0.002, slippage=0.0005, fx_fee=0.001, fee_free_from=250.0))):
        rr = erun(e, {"ACWI": "USD"}, _G["fx"], [Order(ecal[0], "ACWI", weight=0.995)], 5000, co, 1, calendar=ecal)
        fxr = lambda c, d: float(_G["fx"]["USD"][_G["fx"]["USD"].index <= pd.Timestamp(d)].iloc[-1])
        m = {"cagr": float((rr.equity.iloc[-1] / rr.equity.iloc[0]) ** (365.25 / (rr.equity.index[-1] - rr.equity.index[0]).days) - 1)}
        m.update(T.after_tax(rr.equity, T.taxes(T.yearly_from_engine(rr, e, fxr))))
        acw[cn] = m
    json.dump(acw, open(out / "acwi_test.json", "w"), indent=1)
    print("ACWI 2017–21:", acw, flush=True)
    jobs = [(sid, per, c, cn) for sid in SIDS for per in PERIODS for c in CAPS for cn in COSTS]
    with Pool(int(os.environ.get("NPROC", os.cpu_count() or 2))) as pool:
        rr = pool.map(_main_job, jobs, chunksize=1)
    res = {f"{k[0]} · {k[1]} · {k[2]} € · {k[3]}": m for k, m, _ in rr}
    pd.DataFrame({f"{k[0]} · {k[1]} · {k[2]} · {k[3]}": eq for k, _, eq in rr}).to_csv(out / "s1920_curves.csv.gz")
    json.dump({"info": _G["info"], "signale": cnt, "results": res}, open(out / "s1920_main.json", "w"), indent=1, default=str,
              ensure_ascii=False)
    for sid in SIDS:
        b, st = res[f"{sid} · test · 5000 € · prime"], res[f"{sid} · test · 5000 € · prime_stress"]
        print(f"{sid:5s} test 5k CAGR {b['cagr']:+.1%} Stress {st['cagr']:+.1%} DD {b['max_dd']:.0%} Trades {b['trades']} "
              f"nachSt {st['cagr_after_tax']:+.1%}", flush=True)
    return 0


def _null_job(args):
    sid, seed = args
    rng = np.random.default_rng(31_000 + 1000 * SIDS.index(sid) + seed)
    s, e = (pd.Timestamp(x) for x in PERIODS["test"])
    real, pool = _G["sig"], _G["pool"]
    sig = {}
    for D, lst in real.items():
        p = pool.get(D, [])
        if not p:
            continue
        for k in rng.choice(len(p), min(len(lst), len(p)), replace=False):
            t, low, atr = p[k]
            sig.setdefault(D, []).append({"t": t, "panic": low, "atr": atr, "z": -float(rng.random()), "vr": float(rng.random())})
    r = simulate(sid, 5000, "prime", sig, s, e, 5)
    eq = r["equity"]
    return sid, seed, float((eq.iloc[-1] / eq.iloc[0]) ** (365.25 / (eq.index[-1] - eq.index[0]).days) - 1)


def cmd_null(a) -> int:
    setup(a)
    s, e = (pd.Timestamp(x) for x in PERIODS["test"])
    _G["sig"] = signals(_G["mk"], _G["fund"], _G["sec3"], _G["bull"], a.sid, s, e)
    _G["pool"] = pools(_G["mk"], _G["fund"], _G["bull"], a.sid, sorted(_G["sig"]))
    with Pool(int(os.environ.get("NPROC", os.cpu_count() or 2))) as pool:
        rr = pool.map(_null_job, [(a.sid, k) for k in range(a.seed_start, a.seed_start + a.seed_n)], chunksize=1)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    json.dump({a.sid: {k: c for _, k, c in rr}}, open(out / f"s1920_null_{a.sid}_{a.seed_start}.json", "w"))
    print(a.sid, "Zufall Median", float(np.median([c for *_, c in rr])))
    return 0


def cmd_combine(a) -> int:
    inp, out = Path(a.inp), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    main = json.load(open(inp / "s1920_main.json"))
    acwi = json.load(open(inp / "acwi_test.json")) if (inp / "acwi_test.json").exists() else None
    null: dict = {}
    for f in inp.glob("s1920_null_*.json"):
        for sid, v in json.load(open(f)).items():
            null.setdefault(sid, {}).update(v)
    dec = {}
    R = main["results"]
    for sid in SIDS:
        b, st = R[f"{sid} · test · 5000 € · prime"], R[f"{sid} · test · 5000 € · prime_stress"]
        ns = np.array(list(null.get(sid, {}).values()))
        p = float(((ns >= b["cagr"]).sum() + 1) / (len(ns) + 1)) if len(ns) else None
        d = {"1_stress_pos": st["cagr"] > 0, "p_vs_zufall": p, "3_ok": p is not None and p <= 0.0125,
             "zufall_median": float(np.median(ns)) if len(ns) else None, "zufall_n": int(len(ns)), "5_trades": b["trades"],
             "5_ok": b["trades"] >= 30}
        if acwi:
            d["2_gt_acwi"] = st["cagr"] > acwi["prime_stress"]["cagr"]
            d["4_after_tax_gt_acwi"] = st["cagr_after_tax"] > acwi["prime_stress"]["cagr_after_tax"]
        d["bestanden"] = bool(d["1_stress_pos"] and d.get("2_gt_acwi") and d["3_ok"] and d.get("4_after_tax_gt_acwi") and d["5_ok"])
        dec[sid] = d
    json.dump({"entscheidung": dec, "main": main, "acwi_test": acwi}, open(out / "s1920_results.json", "w"), indent=1, default=str,
              ensure_ascii=False)
    print(json.dumps(dec, indent=1, default=str))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["main", "null", "combine"])
    ap.add_argument("--data")
    ap.add_argument("--sec")
    ap.add_argument("--duka")
    ap.add_argument("--splits", default=None)
    ap.add_argument("--sid", default="S19", choices=SIDS)
    ap.add_argument("--seed-start", type=int, default=0)
    ap.add_argument("--seed-n", type=int, default=25)
    ap.add_argument("--out", default="s1920_out")
    ap.add_argument("--inp", default="s1920_out")
    a = ap.parse_args(argv)
    return {"main": cmd_main, "null": cmd_null, "combine": cmd_combine}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
