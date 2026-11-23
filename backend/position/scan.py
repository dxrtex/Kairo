"""Täglicher Lauf im Abendscan: Ranking über alle Aktien, Kaufliste (Top 15), Exit-Signale und Live-Modelldepot.

Das Modelldepot ist die Strategie selbst (engine.run) – gestartet am ersten Handelstag des Jahres (bzw. sobald 2 Jahre Kurse
genug Vorlauf für SMA 200 + Steigung haben), mit 100.000 € und denselben Regeln wie im Backtest. Daraus kommen Einstiegsdatum,
Trailing-Stop und Exit-Signale je Position. Fundamentaldaten: heutiger Stand (fund.json), fehlt etwas → neutral 50.
"""
from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from . import engine, exit_signals, scoring
from .config import CFG, Config

ROOT = Path(__file__).resolve().parents[2]
WARMUP = CFG.sma_slow + CFG.slope_lag + 1


def load_fund() -> dict:
    """fund.json (Branch kairo-fund) – im Abendscan liegt sie noch nicht in site/data."""
    p = ROOT / "site" / "data" / "fund.json"
    try:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8")).get("by") or {}
        subprocess.run(["git", "fetch", "-q", "origin", "kairo-fund"], cwd=ROOT, capture_output=True, timeout=120)
        out = subprocess.run(["git", "show", "origin/kairo-fund:fund.json"], cwd=ROOT, capture_output=True, timeout=120, check=True).stdout
        return json.loads(out).get("by") or {}
    except Exception as exc:
        print(f"Position: fund.json nicht geladen ({exc!r}) – Qualität/Value neutral 50")
        return {}


def pe_5y_avg(f: dict) -> float | None:
    """Ø KGV der letzten bis zu 5 Geschäftsjahre: Ø Monatskurs im Geschäftsjahr / Gewinn je Aktie (nur positive Gewinne).
    Plausibilitätsprüfung gegen das aktuelle KGV (Splits/Währungen können die Reihen verfälschen)."""
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
        win = [(end - k).strftime("%Y-%m") for k in range(12)]
        px = mon.reindex(win).dropna()
        if len(px) >= 6:
            pes.append(float(px.mean()) / e)
    pes = pes[-5:]
    if not pes:
        return None
    avg = float(np.mean(pes))
    pe = f.get("pe")
    if pe and pe > 0 and not (0.2 < avg / pe < 5):
        return None
    return avg if 0 < avg < 500 else None


def fund_frame(fund: dict, tickers) -> tuple[pd.DataFrame, dict]:
    """roe, nde (Nettoverschuldung/EBITDA), peg, fpe_rel (Forward-KGV / 5-J.-KGV) je Ticker + Abdeckung je Feld."""
    rows = {}
    for t in tickers:
        f = fund.get(t) or {}
        roe = f.get("roe")
        mc, debt, cash, evm = f.get("mc"), f.get("debt"), f.get("cash"), f.get("ev")
        nde = None
        if mc and evm and evm > 0 and debt is not None and cash is not None:
            ebitda = (mc + debt - cash) / evm
            nd = debt - cash
            nde = nd / ebitda if ebitda > 0 else (math.inf if nd > 0 else -1.0)
        peg = f.get("peg")
        fpe, p5 = f.get("fpe"), pe_5y_avg(f) if f else None
        rel = fpe / p5 if fpe and fpe > 0 and p5 else None
        rows[t] = {"roe": roe, "nde": nde, "peg": peg, "fpe_rel": rel}
    df = pd.DataFrame(rows).T.astype(float) if rows else pd.DataFrame(columns=["roe", "nde", "peg", "fpe_rel"])
    cov = {k: round(float(df[k].notna().mean()), 3) if len(df) else 0.0 for k in ("roe", "nde", "peg", "fpe_rel")}
    return df, cov


def _panels(data: dict, tickers: list[str]) -> dict[str, pd.DataFrame]:
    out = {}
    for k in ("Open", "High", "Low", "Close", "Volume"):
        out[k] = pd.DataFrame({t: data[t][k] for t in tickers if k in data[t]}).sort_index()
    idx = out["Close"].index
    return {k: v.reindex(idx) for k, v in out.items()}


def _earn_flag(d: str | None, asof: pd.Timestamp, days: int) -> bool:
    if not d:
        return False
    try:
        e = pd.Timestamp(str(d)[:10])
    except Exception:
        return False
    return asof < e <= asof + pd.offsets.BDay(days)


CHECKS = ("liq", "trend", "stab", "mom", "qual", "val", "sector", "earn")      # Reihenfolge der 8 Häkchen in der App
WATCH_MIN, WATCH_MAX = 6, 40


def _vs(dist: np.ndarray, x: float, higher_better: bool = True) -> float | None:
    """Perzentil (0–100) eines Werts gegenüber der Verteilung des heutigen Kaufpools (wie scoring.pct, für Nicht-Pool-Aktien)."""
    if x is None or x != x or not len(dist):
        return None
    lo, hi = np.searchsorted(dist, x, "left"), np.searchsorted(dist, x, "right")
    p = (lo + hi) / 2 / len(dist) * 100.0
    return p if higher_better else 100.0 - p


def checks(P: dict, C: pd.DataFrame, mcap: pd.Series, F: pd.DataFrame, scored: pd.DataFrame, top: list[str], held: set,
           sectors: dict, earn: dict, cfg: Config = CFG) -> pd.DataFrame:
    """Die 8 Einstiegskriterien je Aktie am letzten Tag – für die Watchlist „kurz vor dem Kaufsignal“.
    Liquidität (Ø Umsatz ≥ 10 Mio. $ und Börsenwert ≥ 2 Mrd. $) · Trend (Schluss > SMA 100 > SMA 200, SMA 200 steigt) ·
    Stabilität (kein Tagesverlust < −15 % in 90 T.) · Momentum/Qualität/Value: Teil-Score ≥ 50, also mindestens so gut wie die
    Hälfte des heutigen Kaufpools (fehlende Fundamentaldaten = neutral 50) · Sektor-Cap (noch Platz im Sektor) ·
    keine Quartalszahlen in den nächsten 5 Handelstagen. Das Kaufsignal selbst bleibt: Gesamt-Score unter den Top 15."""
    ind = P["ind"]
    k = len(C.index) - 1
    Cf = C.ffill(limit=engine.FILL_DAYS)
    c, sf, ss = Cf.iloc[k], ind["sma_f"].iloc[k], ind["sma_s"].iloc[k]
    ss0 = ind["sma_s"].iloc[k - cfg.slope_lag] if k >= cfg.slope_lag else ss * np.nan
    liq = (ind["dv"].iloc[k] >= cfg.min_dollar_volume) & (mcap.reindex(C.columns) >= cfg.min_market_cap)
    trend = (c > sf) & (sf > ss) & (ss > ss0)
    stab = ind["gap"].iloc[k] > cfg.gap_limit
    mraw = P["mom"].iloc[k]
    pool = scored.index
    dm = np.sort(mraw.reindex(pool).dropna().to_numpy(float))
    f = F.reindex(C.columns)
    d = {col: np.sort(f[col].reindex(pool).replace([np.inf, -np.inf], np.nan).dropna().to_numpy(float)) for col in f.columns}
    cnt: dict[str, int] = {}
    for t in set(top) | set(held):
        sc = sectors.get(t) or "?"
        cnt[sc] = cnt.get(sc, 0) + 1
    rows = {}
    for t in C.columns:
        if c.get(t) != c.get(t):
            continue
        if t in pool:
            mo, qu, va = (float(scored.at[t, x]) for x in ("mom", "qual", "val"))
            tot = float(scored.at[t, "total"])
        else:
            mo = _vs(dm, float(mraw.get(t, np.nan)))
            mo = cfg.neutral if mo is None else mo
            q = [v for v in (_vs(d["roe"], f.at[t, "roe"]), _vs(d["nde"], f.at[t, "nde"], False)) if v is not None]
            pg, rl = f.at[t, "peg"], f.at[t, "fpe_rel"]
            pg = np.inf if pg == pg and pg <= 0 else pg
            rl = np.inf if rl == rl and rl <= 0 else rl
            v = [x for x in (_vs(d["peg"], pg, False), _vs(d["fpe_rel"], rl, False)) if x is not None]
            qu = float(np.mean(q)) if q else cfg.neutral
            va = float(np.mean(v)) if v else cfg.neutral
            tot = cfg.w_momentum * mo + cfg.w_quality * qu + cfg.w_value * va
        sc = sectors.get(t) or "?"
        sec_ok = t in top or t in held or sc == "?" or cnt.get(sc, 0) < cfg.sector_cap
        rows[t] = {"liq": bool(liq.get(t, False)), "trend": bool(trend.get(t, False)), "stab": bool(stab.get(t, False)),
                   "mom": mo >= 50, "qual": qu >= 50, "val": va >= 50, "sector": bool(sec_ok), "earn": not earn.get(t, False),
                   "est": tot}
    out = pd.DataFrame(rows).T
    if len(out):
        out["n"] = out[list(CHECKS)].sum(axis=1).astype(int)
    return out


def build(data: dict, meta: dict, index_df: pd.DataFrame | None, fx_usd: dict, cfg: Config = CFG, fund: dict | None = None) -> dict | None:
    tickers = [t for t, df in data.items() if df is not None and len(df) > WARMUP and "Close" in df]
    if not tickers or index_df is None or not len(index_df):
        return None
    P_ = _panels(data, tickers)
    C = P_["Close"]
    fund = load_fund() if fund is None else fund
    cur = {t: (meta.get(t) or {}).get("currency") or "USD" for t in tickers}
    fxs = pd.Series({t: fx_usd.get(cur[t], np.nan) for t in tickers})
    mcap = pd.Series({t: (meta.get(t) or {}).get("market_cap_usd") for t in tickers}, dtype=float)
    sectors = {t: (fund.get(t) or {}).get("sec") or (meta.get(t) or {}).get("sector") or "?" for t in tickers}
    names = {t: (meta.get(t) or {}).get("name") or t for t in tickers}
    F, cov = fund_frame(fund, tickers)
    m = engine.Market(P_["Open"], P_["High"], P_["Low"], C, P_["Volume"], index_df["Close"].reindex(C.index).ffill(), fx=fxs,
                      mcap=mcap, sectors=sectors, names=names, fund=lambda t: F)
    P = engine.prepare(m, cfg)
    idx = C.index
    asof = idx[-1]
    jan = idx[idx >= pd.Timestamp(asof.year, 1, 1)]
    start = jan[0] if len(jan) and idx.get_loc(jan[0]) >= WARMUP else idx[min(WARMUP, len(idx) - 1)]
    res = engine.run(m, start, cfg=cfg, tax=False, P=P, log_days=True)
    last = res["log"][-1] if res["log"] else None
    scored = last["scored"] if last else pd.DataFrame()
    top = last["top"] if last else []
    top25 = last["top25"] if last else set()
    reg = P["reg"]
    ix = m.index_close
    sma200 = float(ix.rolling(cfg.regime_sma).mean().iloc[-1])
    atr_t, sma_f = P["atr"].loc[asof], P["ind"]["sma_f"].loc[asof]
    rk = {t: i + 1 for i, t in enumerate(scored.index)}
    held = res["pos"]
    val = float(res["equity"].iloc[-1])
    r4 = lambda x: None if x is None or (isinstance(x, float) and not math.isfinite(x)) else round(float(x), 4)

    earn = {t: _earn_flag((meta.get(t) or {}).get("earnings_date"), asof, cfg.earnings_days) for t in tickers}
    chk = checks(P, C, mcap, F, scored, top, set(held), sectors, earn, cfg)

    def row(t):
        s = scored.loc[t] if t in scored.index else None
        e = (meta.get(t) or {}).get("earnings_date")
        ck = chk.loc[t] if t in chk.index else None
        return {"t": t, "n": names.get(t), "sec": sectors.get(t), "cur": cur.get(t), "px": r4(C.at[asof, t]),
                "atr": r4(atr_t.get(t)), "sma": r4(sma_f.get(t)), "rk": rk.get(t),
                "score": r4(s["total"]) if s is not None else None, "mom": r4(s["mom"]) if s is not None else None,
                "qual": r4(s["qual"]) if s is not None else None, "val": r4(s["val"]) if s is not None else None,
                "m_raw": r4(s["mom_raw"]) if s is not None else None, "earn": _earn_flag(e, asof, cfg.earnings_days),
                "edate": str(e)[:10] if e else None, "top15": t in top, "top25": t in top25, "held": t in held,
                "chk": [int(bool(ck[x])) for x in CHECKS] if ck is not None else None, "nchk": int(ck["n"]) if ck is not None else None}

    pos = []
    for t, p in held.items():
        c = res["last_close"].get(t, p.entry_px)
        st = exit_signals.trailing_stop(p.high, float(atr_t.get(t, np.nan)), cfg)
        pos.append({**row(t), "since": p.entry_date.strftime("%Y-%m-%d"), "px_in": r4(p.entry_px), "ret": r4(c / p.entry_px - 1),
                    "hi": r4(p.high), "stop": r4(st), "w": r4(p.shares * c / val) if val else None,
                    "exit": res["pending_sell"].get(t, [])})
    pos.sort(key=lambda x: -(x["w"] or 0))
    buying = {t for t, _, _ in res["pending_buy"]}
    watch = []
    if len(chk):
        w = chk[(chk["n"] >= WATCH_MIN) & ~chk.index.isin(list(buying | set(held) | set(top)))]
        w = w.assign(est=w["est"].astype(float)).sort_values(["n", "est"], ascending=False).head(WATCH_MAX)
        for t in w.index:
            r_ = row(t)
            r_["est"] = r4(float(w.at[t, "est"]))
            r_["miss"] = [x for x in CHECKS if not bool(w.at[t, x])]
            watch.append(r_)
    b0, b1 = float(ix.loc[start]), float(ix.iloc[-1])
    closed = res["trades"]
    out = {
        "asof": asof.strftime("%Y-%m-%d"), "friday": asof.weekday() == 4,
        "regime": {"on": bool(reg.iloc[-1]), "close": r4(ix.iloc[-1]), "sma200": r4(sma200), "index": cfg.regime_index},
        "cfg": {"top_n": cfg.top_n, "sector_cap": cfg.sector_cap, "risk": cfg.risk_per_atr, "max_w": cfg.max_weight,
                "trail": cfg.trail_atr, "momentum": cfg.momentum, "exit_pct": cfg.exit_rank_pct, "earn_days": cfg.earnings_days},
        "model": {"start": start.strftime("%Y-%m-%d"), "capital": cfg.start_capital, "value": r4(val), "ret": r4(val / cfg.start_capital - 1),
                  "bench": r4(b1 / b0 - 1), "cash": r4(res["cash"] / val) if val else None, "positions": pos,
                  "trades": [{k: x[k] for k in ("t", "in", "out", "ret", "why", "days")} for x in closed[-30:]],
                  "n_trades": len(closed), "win": r4(np.mean([x["pnl"] > 0 for x in closed])) if closed else None},
        "buy": [{**row(t), "n_sh": n} for t, n, _ in res["pending_buy"]],
        "sell": [{"t": t, "n": names.get(t), "why": w} for t, w in res["pending_sell"].items()],
        "rank": [row(t) for t in list(scored.index[:60])],
        "watch": watch,
        "checks": list(CHECKS),
        "top": top, "pool": int(len(scored)), "universe": len(tickers), "cut25": int(math.ceil(len(scored) * cfg.exit_rank_pct)) if len(scored) else 0,
        "coverage": cov,
    }
    return out
