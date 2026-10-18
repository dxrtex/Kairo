"""B2 – Baselines im Entwicklungszeitraum (Train 2008–2016): S01-A/B, Zufalls-Null (200 Seeds), S13-ETF, ACWI B&H.

python -m research.strategy_championship.b2_baselines --data DIR --signals DIR --out OUT [--seeds 200]

Validierung und Holdout werden nicht geladen (data.load schneidet am Periodenende ab).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import zlib
from datetime import datetime, timezone
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

from backend.scanner import FX_USD

from . import s01
from .data import UNIVERSE, adjusted, load
from .engine import Costs, Order, run

SLEEVES = {1000: 5, 5000: 5, 20000: 10}
RISKS = (0.01, 0.005)
_G: dict = {}


# ---------------------------------------------------------------- Kennzahlen
def metrics(res, bench_ret: pd.Series | None = None, start_cash: float = 0.0) -> dict:
    e = res.equity
    e = e[e.index >= e.index[0]]
    yrs = (e.index[-1] - e.index[0]).days / 365.25
    r = e.pct_change().dropna()
    dd = e / e.cummax() - 1
    under, longest, cur = (dd < 0).to_numpy(), 0, 0
    for u in under:
        cur = cur + 1 if u else 0
        longest = max(longest, cur)
    cagr = (e.iloc[-1] / e.iloc[0]) ** (1 / yrs) - 1 if yrs > 0 and e.iloc[-1] > 0 else -1.0
    sd, dn = r.std(), r[r < 0].std()
    out = {"start": str(e.index[0].date()), "end": str(e.index[-1].date()), "final_eur": round(float(e.iloc[-1]), 2),
           "cagr": cagr, "total": float(e.iloc[-1] / e.iloc[0] - 1), "max_dd": float(dd.min()), "dd_days": int(longest),
           "sharpe": float(r.mean() / sd * np.sqrt(252)) if sd > 0 else None,
           "sortino": float(r.mean() / dn * np.sqrt(252)) if dn and dn > 0 else None,
           "calmar": float(cagr / -dd.min()) if dd.min() < 0 else None}
    t = res.trades
    if len(t):
        net_r = t["pnl_eur"] / t["risk_eur"].where(t["risk_eur"] > 0)
        pos, neg = t.loc[t["pnl_eur"] > 0, "pnl_eur"].sum(), -t.loc[t["pnl_eur"] < 0, "pnl_eur"].sum()
        buys = res.ledger.loc[res.ledger["kind"] == "BUY", "cash_flow_eur"].abs().sum()
        cost = t["fees_eur"].sum() + t["spread_eur"].sum()
        gross = t["pnl_eur"].sum() + cost
        out.update(trades=int(len(t)), win_rate=float((t["pnl_eur"] > 0).mean()),
                   profit_factor=float(pos / neg) if neg > 0 else None,
                   avg_r_net=float(net_r.mean()) if net_r.notna().any() else None,
                   avg_days=float(t["days"].mean()), exits=t["why"].value_counts().to_dict(),
                   turnover_pa=float(buys / e.mean() / yrs) if yrs > 0 else None,
                   costs_eur=round(float(cost), 2), cost_share_of_gross=float(cost / gross) if gross > 0 else None)
    else:
        out.update(trades=0)
    if res.invested is not None and len(res.invested):
        out["exposure"] = float(res.invested.mean())
        out["days_in_market"] = float((res.invested > 0).mean())
    if bench_ret is not None:
        j = pd.concat([r, bench_ret], axis=1, join="inner").dropna()
        if len(j) > 50 and j.iloc[:, 1].std() > 0:
            c = np.cov(j.iloc[:, 0], j.iloc[:, 1])
            out["beta_acwi"] = float(c[0, 1] / c[1, 1])
            out["corr_acwi"] = float(j.corr().iloc[0, 1])
    out["skipped"] = res.skipped
    out["checks"] = res.checks
    return out


def bootstrap(res, n: int = 1000, seed: int = 7) -> dict:
    """Block-Bootstrap über Kalendermonate: CAGR aus gezogenen Monatsrenditen, Ø-R aus den Trades gezogener Monate."""
    rng = np.random.default_rng(seed)
    m = res.equity.resample("ME").last().pct_change().dropna().to_numpy()
    if len(m) < 12:
        return {}
    cg = [(np.prod(1 + rng.choice(m, len(m))) ** (12 / len(m)) - 1) for _ in range(n)]
    out = {"cagr_ci90": [float(np.percentile(cg, 5)), float(np.percentile(cg, 95))]}
    t = res.trades
    if len(t) > 20:
        t = t.assign(m=t["exit_date"].dt.to_period("M"), R=t["pnl_eur"] / t["risk_eur"].where(t["risk_eur"] > 0))
        g = {k: v["R"].dropna().to_numpy() for k, v in t.groupby("m")}
        keys = list(g)
        rs = []
        for _ in range(n):
            pick = rng.choice(len(keys), len(keys))
            arr = np.concatenate([g[keys[k]] for k in pick])
            rs.append(arr.mean() if len(arr) else np.nan)
        out["avg_r_ci90"] = [float(np.nanpercentile(rs, 5)), float(np.nanpercentile(rs, 95))]
    return out


# ---------------------------------------------------------------- Aufbau
def spreads(prices: dict, cur: dict, region: dict) -> dict:
    out = {}
    for t, df in prices.items():
        adv = float(np.nanmedian((df["Close"] * df["Volume"]).rolling(20).mean())) * FX_USD.get(cur.get(t, "USD"), 1.0)
        out[t] = 0.003 if not (adv >= 20e6) else (0.0015 if region.get(t) == "eu" else 0.001)
    return out


def s01_orders(sig: pd.DataFrame, variant: str, risk: float) -> list[Order]:
    orders = []
    for x in sig.itertuples(index=False):
        if x.ticker not in _G["frames"]:
            continue
        orders += s01.base_orders(_G["frames"][x.ticker], int(x.i), float(x.atr), x.ticker, f"{x.ticker}|{x.date}", variant,
                                  risk, prio=-float(x.atr) / float(x.close), adj=_G["adj"][x.ticker])
    return orders


def null_signals(sig: pd.DataFrame, seed: int) -> pd.DataFrame:
    """Gleiche Anzahl Signale je Tag, zufällige zulässige Aktien desselben Tages (Grundfilter wie der Scanner)."""
    rng = np.random.default_rng(seed)
    rows = []
    for d, g in sig.groupby("date"):
        pool = _G["pool"].get(pd.Timestamp(d))
        if pool is None or not len(pool):
            continue
        pick = rng.choice(pool, min(len(g), len(pool)), replace=False)
        for t in pick:
            i = int(_G["pos"][t].get(pd.Timestamp(d), -1))
            if i < 0:
                continue
            a = float(_G["atr"][t][i])
            rows.append({"ticker": t, "date": pd.Timestamp(d), "i": i, "atr": a, "close": float(_G["adj"][t]["Close"].iloc[i])})
    return pd.DataFrame(rows)


def _null_run(args):
    seed, risk = args
    ns = null_signals(_G["sig"], seed)
    orders = s01_orders(ns, "A", risk)
    for o in orders:                                # Ranking „zufällig“ (Protokoll)
        o.prio = float(np.random.default_rng(zlib.crc32(f"{seed}|{o.group}".encode())).random())
    res = run(_G["frames"], _G["cur"], _G["fx"], orders, 5000, _G["costs"], 5, calendar=_G["cal"])
    m = metrics(res)
    return seed, risk, {k: m.get(k) for k in ("cagr", "max_dd", "sharpe", "avg_r_net", "trades", "win_rate", "final_eur")}


def s13_orders(acwi: pd.DataFrame, fx_usd: pd.Series) -> tuple[list[Order], set]:
    """Monatsschluss ACWI (gesamt, in EUR) > SMA der letzten 10 Monatsschlüsse → investiert, sonst Cash."""
    px = (acwi["AdjClose"] / fx_usd.reindex(acwi.index, method="ffill")).dropna()
    me = px.groupby(px.index.to_period("M")).tail(1)
    sma = me.rolling(10).mean()
    orders, exits, on = [], set(), False
    for d, v in me.items():
        s = sma.loc[d]
        if not np.isfinite(s):
            continue
        want = v > s
        if want and not on:
            orders.append(Order(d, "ACWI", weight=0.995, tag="S13-ETF"))
        if on and not want:
            exits.add((d, "ACWI"))
        on = want
    return orders, exits


# ---------------------------------------------------------------- Lauf
def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--signals", required=True)
    ap.add_argument("--out", default="b2_out")
    ap.add_argument("--seeds", type=int, default=200)
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    prices, cur, fx, bench, (start, end) = load(a.data, "train")
    sig = pd.concat([pd.read_parquet(p) for p in sorted(Path(a.signals).glob("s01_signals_*.parquet"))], ignore_index=True)
    sig["date"] = pd.to_datetime(sig["date"])
    sig = sig[(sig["date"] >= start) & (sig["date"] <= end)].sort_values(["date", "ticker"]).reset_index(drop=True)
    uni = pd.read_csv(UNIVERSE)
    region = dict(zip(uni["ticker"], uni["region"]))
    frames, adj, atr, pos, pool = {}, {}, {}, {}, {}
    for t, df in prices.items():
        c = s01.clean(df)
        if len(c) < 30:
            continue
        frames[t] = s01.with_ema(c)
        adj[t] = adjusted(c)
        atr[t] = s01.atr14(c).to_numpy(float)
        pos[t] = pd.Series(np.arange(len(c)), index=c.index)
        ok = s01.eligible(adj[t], cur.get(t, "USD"))
        for d in c.index[ok & (c.index >= start)]:
            pool.setdefault(d, []).append(t)
    pool = {d: np.array(sorted(v)) for d, v in pool.items()}
    cal = pd.DatetimeIndex(sorted(set().union(*[f.index[(f.index >= start) & (f.index <= end)] for f in frames.values()])))
    sp = spreads(prices, cur, region)
    base = Costs(fee_eur=0.99, spread=0.001, spread_by_ticker=sp)
    stress = Costs(fee_eur=1.99, spread=0.002, slippage=0.0005, fx_fee=0.001, spread_by_ticker={k: 2 * v for k, v in sp.items()})
    _G.update(frames=frames, adj=adj, atr=atr, pos=pos, pool=pool, cal=cal, cur=cur, fx=fx, sig=sig, costs=base)
    acwi = bench["ACWI"]
    acwi_r = (acwi["AdjClose"] / fx["USD"].reindex(acwi.index, method="ffill")).pct_change()
    frames_b = {"ACWI": acwi[["Open", "High", "Low", "Close", "AdjClose"]]}
    cur_b = {"ACWI": "USD"}
    data_sha = json.loads((Path(a.data) / "MANIFEST_v1.json").read_text()) if (Path(a.data) / "MANIFEST_v1.json").exists() else {}
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        commit = None
    results, log = {}, []

    def record(name, res, cfg):
        m = metrics(res, acwi_r)
        m.update(bootstrap(res))
        results[name] = {"config": cfg, "metrics": m}
        log.append({"id": f"B2-{len(log) + 1:03d}", "name": name, "period": "train", "config": cfg, "commit": commit,
                    "data": hashlib.sha256(json.dumps(data_sha, sort_keys=True).encode()).hexdigest()[:16],
                    "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "cagr": m.get("cagr"), "max_dd": m.get("max_dd"), "trades": m.get("trades")})
        print(f"{name}: CAGR {m.get('cagr', 0):+.2%} · MaxDD {m.get('max_dd', 0):.1%} · Trades {m.get('trades')} · "
              f"Ø R {m.get('avg_r_net')} · Prüfungen {m['checks']}", flush=True)
        return res

    print(f"Signale: {len(sig)} · Titel: {len(frames)} · Kalender {cal[0].date()}–{cal[-1].date()}", flush=True)
    for variant in ("A", "B"):
        for risk in RISKS:
            orders = s01_orders(sig, variant, risk)
            for cash, mo in SLEEVES.items():
                res = run(frames, cur, fx, orders, cash, base, mo, calendar=cal)
                record(f"S01-{variant} · {cash} € · Risiko {risk:.1%}", res, {"variant": variant, "risk": risk, "cash": cash, "max_open": mo,
                                                                            "costs": "base"})
                if cash == 5000:
                    res.trades.to_csv(out / f"trades_S01-{variant}_{risk}.csv", index=False)
            res = run(frames, cur, fx, orders, 5000, stress, 5, calendar=cal)
            record(f"S01-{variant} · 5000 € · Risiko {risk:.1%} · Kostenstress", res,
                   {"variant": variant, "risk": risk, "cash": 5000, "max_open": 5, "costs": "stress"})
    # Benchmarks
    s13, s13x = s13_orders(acwi, fx["USD"])
    for cash in SLEEVES:
        record(f"S13-ETF · {cash} €", run(frames_b, cur_b, fx, s13, cash, base, 1, exit_signals=s13x, calendar=cal),
               {"cash": cash, "costs": "base"})
        bh = [Order(acwi.index[0], "ACWI", weight=0.995, tag="Bench")]
        record(f"ACWI B&H · {cash} €", run(frames_b, cur_b, fx, bh, cash, base, 1, calendar=cal), {"cash": cash, "costs": "base"})
    # Null
    jobs = [(s, r) for r in RISKS for s in range(a.seeds)]
    with Pool() as p:
        nulls = p.map(_null_run, jobs, chunksize=4)
    null = {}
    for s, r, m in nulls:
        null.setdefault(f"{r}", []).append({"seed": s, **m})
    for r in RISKS:
        ref = results[f"S01-A · 5000 € · Risiko {r:.1%}"]["metrics"]
        arr = pd.DataFrame(null[f"{r}"])
        summ = {"n": int(len(arr)), "cagr_median": float(arr["cagr"].median()),
                "cagr_p05_p95": [float(arr["cagr"].quantile(.05)), float(arr["cagr"].quantile(.95))],
                "avg_r_median": float(arr["avg_r_net"].median()), "trades_median": float(arr["trades"].median()),
                "max_dd_median": float(arr["max_dd"].median()),
                "p_cagr": float((arr["cagr"] >= ref["cagr"]).mean()),
                "p_avg_r": float((arr["avg_r_net"] >= (ref.get("avg_r_net") or -9)).mean())}
        results[f"Null (200 Seeds) · 5000 € · Risiko {r:.1%}"] = {"config": {"seeds": a.seeds, "risk": r}, "summary": summ}
        log.append({"id": f"B2-{len(log) + 1:03d}", "name": f"Null · Risiko {r}", "period": "train", "seeds": a.seeds,
                    "commit": commit, "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **summ})
        arr.to_csv(out / f"null_{r}.csv", index=False)
        print(f"Null {r}: {summ}", flush=True)
    (out / "b2_results.json").write_text(json.dumps(results, indent=1, default=str, ensure_ascii=False))
    (out / "b2_experiments.jsonl").write_text("\n".join(json.dumps(x, default=str, ensure_ascii=False) for x in log) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
