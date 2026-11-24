"""Backtest der Position-Strategie mit deutscher Abgeltungsteuer.

    python -m backend.position.backtest prices SHARD SHARDS         → bpx_SHARD.pkl.gz (bereinigte Tageskurse, 12 Jahre)
    python -m backend.position.backtest run PXDIR [--universe us|all] [--momentum clenow|6-1] [--start 2016-01-04]
    python -m backend.position.backtest run PXDIR --strategy langfrist     → bisherige Regel als Vergleich (gleiche Daten/Kosten/Steuer)

Daten: Kurse aus yfinance (auto_adjust → split- und dividendenbereinigt: Open/High/Low/Close), Universum backend/universe,
Fundamentaldaten zeitpunktgenau aus den SEC-Jahresabschlüssen (fin.json, nur USA): ROE = Gewinn / Eigenkapital,
Nettoverschuldung / EBITDA ≈ (Schulden − Cash) / operativer Gewinn (EBIT, ohne Abschreibungen – konservativ).
Ein Geschäftsjahr gilt erst 120 Tage nach seinem Ende (10-K liegt vor). PEG, Forward-KGV und 5-Jahres-KGV gibt es
historisch nicht → neutral 50 (wird im Bericht genannt). Börsenwert historisch ≈ heutige Aktienzahl × Kurs (Näherung).
"""
from __future__ import annotations

import argparse
import gzip
import json
import pickle
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from . import engine
from .config import CFG, Config

ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------- Daten
def _git_json(branch: str, name: str):
    try:
        out = subprocess.run(["git", "show", f"origin/{branch}:{name}"], cwd=ROOT, capture_output=True, check=True).stdout
        return json.loads(out)
    except Exception:
        p = ROOT / name
        return json.loads(p.read_text()) if p.exists() else None


def prices(shard: int, shards: int) -> None:
    from backend.data_provider import YFinanceProvider
    from backend.universe import load as load_universe
    u = load_universe()
    fin = (_git_json("kairo-fin", "fin.json") or {}).get("by") or {}
    tick = sorted(set(u["ticker"]) | {t for t, v in fin.items() if v.get("y")})
    mine = tick[shard::shards]
    data = YFinanceProvider().history(mine, "12y")
    px = {t: df[["Open", "High", "Low", "Close", "Volume"]].astype("float32") for t, df in data.items()}
    with gzip.open(f"bpx_{shard}.pkl.gz", "wb") as f:
        pickle.dump(px, f)
    print(f"Shard {shard}: {len(px)} von {len(mine)} Aktien")


def _yf(t: str, start="2010-01-01") -> pd.DataFrame:
    import yfinance as yf
    d = yf.Ticker(t).history(period="max", interval="1d", auto_adjust=True)
    d.index = pd.to_datetime(d.index).tz_localize(None).normalize()
    return d[d.index >= start]


def fx_usd(currencies) -> dict:
    """1 Einheit Währung = x USD (heutiger Kurs; GBp/GBX = Pence)."""
    import yfinance as yf
    out = {"USD": 1.0}
    for c in {c for c in currencies if c and c not in ("USD",)}:
        base = "GBP" if c in ("GBp", "GBX") else c
        try:
            v = float(yf.Ticker(f"{base}USD=X").history(period="5d")["Close"].dropna().iloc[-1])
            out[c] = v / 100 if c in ("GBp", "GBX") else v
        except Exception:
            pass
    return out


def load_market(pxdir: str, universe: str = "us", cfg: Config = CFG) -> tuple[engine.Market, dict]:
    from backend.universe import load as load_universe
    px = {}
    for p in sorted(Path(pxdir).glob("**/bpx_*.pkl.gz")):
        with gzip.open(p, "rb") as f:
            for t, df in pickle.load(f).items():
                df = df.copy()
                df.index = pd.to_datetime(df.index)
                if df.index.tz is not None:
                    df.index = df.index.tz_localize(None)
                df.index = df.index.normalize()
                px[t] = df[~df.index.duplicated(keep="last")]
    u = load_universe().set_index("ticker")
    fin = (_git_json("kairo-fin", "fin.json") or {}).get("by") or {}
    fund = (_git_json("kairo-fund", "fund.json") or {}).get("by") or {}
    if universe == "us":
        px = {t: d for t, d in px.items() if t in fin and fin[t].get("y") and "." not in t}
    px = {t: d for t, d in px.items() if len(d) > 300}
    meta = {"n_prices": len(px), "missing": set(), "notes": []}
    fields = {k: pd.DataFrame({t: d[k] for t, d in px.items()}).sort_index() for k in ("Open", "High", "Low", "Close", "Volume")}
    cols = fields["Close"].columns
    cur = {t: (u["currency"].get(t) if t in u.index else None) or ("USD" if "." not in t else None) for t in cols}
    fx = fx_usd(set(cur.values()))
    fxs = pd.Series({t: fx.get(cur[t], np.nan) for t in cols})
    # Börsenwert historisch ≈ heutige Aktienzahl × Kurs × FX (Näherung; Aktienzahl ändert sich durch Rückkäufe/Ausgaben)
    so = pd.Series({t: (fund.get(t) or {}).get("so") for t in cols}, dtype=float)
    mcap = fields["Close"] * so * fxs
    nomc = so.isna()
    if nomc.any():          # ohne Aktienzahl: heutiger Börsenwert aus dem Universum (konstant)
        now = pd.Series({t: (u["market_cap_usd"].get(t) if t in u.index else np.nan) for t in cols}, dtype=float)
        mcap.loc[:, nomc] = np.broadcast_to(now[nomc].to_numpy(), (len(mcap), int(nomc.sum())))
        meta["notes"].append(f"{int(nomc.sum())} Aktien ohne Aktienzahl → heutiger Börsenwert konstant")
    sectors = {t: (fund.get(t) or {}).get("sec") or (u["sector"].get(t) if t in u.index else None) or "?" for t in cols}
    names = {t: (u["name"].get(t) if t in u.index else t) for t in cols}
    roe, nde = _pit_panels(fin, fields["Close"].index, list(cols), cfg)
    meta["missing"] |= {"peg", "forward_pe", "pe_5y_avg", "earnings_dates_hist"}
    if universe == "all":
        meta["notes"].append("Nicht-US-Aktien: keine historischen Fundamentaldaten → Qualität neutral 50")

    def fund_at(t):
        if roe is None:
            return None
        return pd.DataFrame({"roe": roe.loc[t], "nde": nde.loc[t]})

    gspc = _yf(cfg.regime_index)["Close"].reindex(fields["Close"].index).ffill()
    m = engine.Market(fields["Open"], fields["High"], fields["Low"], fields["Close"], fields["Volume"], gspc, fx=fxs,
                      mcap=mcap, sectors=sectors, names=names if universe == "all" else {}, fund=fund_at)
    return m, meta


def _pit_panels(fin: dict, dates: pd.DatetimeIndex, cols: list[str], cfg: Config):
    """ROE und Nettoverschuldung/EBITDA je Tag, nur aus Jahresabschlüssen mit Stichtag ≤ t (FYE + 120 Tage)."""
    roe, nde = {}, {}
    for t in cols:
        v = fin.get(t)
        if not v or not v.get("y"):
            continue
        mm, dd = (v.get("fye") or "12-31").split("-")
        g = lambda k, i: (v.get(k) or [])[i] if i < len(v.get(k) or []) else None
        r1, r2 = {}, {}
        for i, y in enumerate(v["y"]):
            try:
                avail = pd.Timestamp(int(y), int(mm), min(int(dd), 28)) + pd.Timedelta(days=cfg.fund_lag_days)
            except Exception:
                continue
            ni, eq, debt, cash, oi = (g(k, i) for k in ("ni", "eq", "debt", "cash", "oi"))
            r1[avail] = ni / eq if ni is not None and eq and eq > 0 else np.nan
            if oi is not None:
                nd = (debt or 0) - (cash or 0)
                r2[avail] = nd / oi if oi > 0 else (np.inf if nd > 0 else -1.0)
        if r1:
            roe[t] = pd.Series(r1).sort_index()
        if r2:
            nde[t] = pd.Series(r2).sort_index()
    if not roe:
        return None, None
    R = pd.DataFrame(roe).reindex(dates.union(pd.DatetimeIndex(sorted({d for s in roe.values() for d in s.index})))).sort_index().ffill().reindex(dates)
    N = pd.DataFrame(nde).reindex(R.index.union(pd.DatetimeIndex(sorted({d for s in nde.values() for d in s.index})))).sort_index().ffill().reindex(dates)
    return R.reindex(columns=cols), N.reindex(columns=cols)


# ---------------------------------------------------------------- Kennzahlen
def metrics(eq: pd.Series) -> dict:
    eq = eq.dropna()
    r = eq.pct_change().dropna()
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    return {"start": float(eq.iloc[0]), "end": float(eq.iloc[-1]), "total": float(eq.iloc[-1] / eq.iloc[0] - 1),
            "cagr": float((eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1) if yrs > 0 else None,
            "mdd": float((1 - eq / eq.cummax()).max()), "sharpe": float(r.mean() / r.std() * np.sqrt(252)) if r.std() > 0 else None}


# ---------------------------------------------------------------- Vergleich: bisherige Strategie (Kairo Langfrist)
BASE = {"n": 20, "lb": 12, "every": 3, "min_adv": 5e6, "min_px": 5.0}


def run_baseline(m: engine.Market, start, cfg: Config = CFG, tax: bool = True, rule: dict | None = None) -> dict:
    """Bisherige Regel (backend/langfrist.py, v2026.11.242) mit DENSELBEN Kursen, Kosten und Steuern wie die neue Strategie:
    am ersten Handelstag im Jan/Apr/Jul/Okt die 20 US-Aktien mit dem höchsten 12-1-Momentum (Kurs vor 1 Monat / vor 12 Monaten),
    Ø Umsatz 63 T. ≥ 5 Mio. $, Kurs ≥ 5 $; Rangliste mit Kursen bis zum Vortag, Ausführung zur Eröffnung des Tauschtags.
    Raus, wer nicht mehr in den Top 20 ist; neue Titel gleich gewichtet (Depotwert / 20) aus dem verfügbaren Cash."""
    r = {**BASE, **(rule or {})}
    mode = r.get("regime", "none")      # none · quarter (Tauschtag: Filter aus → alles verkaufen, Cash) ·
                                         # daily (Filter aus → alles raus; wieder an → sofort Top 20) · buys (nur keine neuen Käufe)
    ixc = m.index_close.ffill()
    reg = (ixc > ixc.rolling(cfg.regime_sma).mean()).reindex(m.C.index).fillna(False)
    Cf = m.C.ffill(limit=engine.FILL_DAYS)
    fx = m.fx.reindex(Cf.columns).fillna(1.0) if m.fx is not None else 1.0
    mom = Cf.shift(21) / Cf.shift(r["lb"] * 21) - 1
    adv = (m.C * m.V.fillna(0) * fx).rolling(63, min_periods=40).mean()
    last_valid = m.C.apply(lambda s: s.last_valid_index())
    idx = m.C.index
    dates = idx[idx >= pd.Timestamp(start)]
    months = set(range(1 + r.get("offset", 0), 13, r["every"]))   # offset 1 → Feb/Mai/Aug/Nov
    first = pd.Series(idx, index=idx).groupby([idx.year, idx.month]).transform("first")
    reb = set(d for d in dates if first[d] == d and d.month in months)
    reb.add(dates[0])
    cash, pos, pot, taxes, costs = float(cfg.start_capital), {}, 0.0, 0.0, 0.0
    trades, equity, invested, last_close = [], [], [], {}
    fee = lambda v: r.get("fee_fix", 0.0) if v < r.get("fee_free", float("inf")) else 0.0   # z. B. Scalable PRIME+: 0,99 € unter 250 € Orderwert
    mc = m.mcap.ffill() if isinstance(m.mcap, pd.DataFrame) else m.mcap

    def sell(t, px, when, why):
        nonlocal cash, pot, taxes, costs
        p = pos.pop(t)
        f0 = fee(p.shares * px)
        proceeds = p.shares * px * (1 - cfg.cost) - f0
        costs += p.shares * px * cfg.cost + f0
        gain = proceeds - p.basis
        if tax:
            if gain < 0:
                pot += -gain
            else:
                use = min(pot, gain)
                pot -= use
                taxes += (gain - use) * cfg.tax
                cash -= (gain - use) * cfg.tax
        cash += proceeds
        trades.append({"t": t, "in": p.entry_date.strftime("%Y-%m-%d"), "out": when.strftime("%Y-%m-%d"), "n": p.shares,
                       "px_in": p.entry_px, "px_out": px, "pnl": proceeds - p.basis, "ret": proceeds / p.basis - 1, "why": why,
                       "days": int((when - p.entry_date).days)})

    was_on = True
    for t in dates:
        k = idx.get_loc(t)
        on = bool(reg.iloc[k - 1]) if k > 0 else True
        go = t in reb or (mode == "daily" and on and not was_on)
        if mode == "daily" and not on and pos:
            for tk in list(pos):
                px = engine._px(m.O, t, tk)
                sell(tk, px if px == px else last_close.get(tk, pos[tk].entry_px), t, "regime")
        if mode in ("daily", "quarter") and not on:
            go = False
            if mode == "quarter" and t in reb:
                for tk in list(pos):
                    px = engine._px(m.O, t, tk)
                    sell(tk, px if px == px else last_close.get(tk, pos[tk].entry_px), t, "regime")
        was_on = on
        if go and k > 0:
            y = idx[k - 1]
            ok = (mom.loc[y] > -1) & (adv.loc[y] >= r["min_adv"]) & (Cf.loc[y] * fx >= r["min_px"]) & m.O.loc[t].notna()
            if r.get("min_mc") and mc is not None:                       # nur große Firmen (Börsenwert in USD)
                mcy = mc.loc[y] if isinstance(mc, pd.DataFrame) else mc
                ok &= (mcy.reindex(ok.index) >= r["min_mc"]).fillna(False)
            ranked = list(mom.loc[y][ok].sort_values(ascending=False).index)
            keep = set(ranked[: r.get("hold") or r["n"]])                 # Puffer: behalten, solange in den Top „hold“
            for tk in [x for x in pos if x not in keep]:
                px = engine._px(m.O, t, tk)
                px = px if px == px else last_close.get(tk, pos[tk].entry_px)
                sell(tk, px, t, "rank")
            val = cash + sum(p.shares * (engine._px(m.O, t, tk) if engine._px(m.O, t, tk) == engine._px(m.O, t, tk)
                                         else last_close.get(tk, p.entry_px)) for tk, p in pos.items())
            cands = ranked if (r.get("hold") or r.get("sec_max")) else ranked[: r["n"]]
            secn = {}
            for tk in pos:
                secn[m.sectors.get(tk) or "?"] = secn.get(m.sectors.get(tk) or "?", 0) + 1
            for tk in cands:
                if len(pos) >= r["n"]:
                    break
                if tk in pos or (mode == "buys" and not on):
                    continue
                sec = m.sectors.get(tk) or "?"
                if r.get("sec_max") and sec != "?" and secn.get(sec, 0) >= r["sec_max"]:
                    continue                                               # höchstens sec_max Aktien je Branche
                px = engine._px(m.O, t, tk)
                budget = min(val / r["n"], cash)
                n = int(budget // (px * (1 + cfg.cost))) if px == px and px > 0 else 0
                if n > 0 and n * px * (1 + cfg.cost) + fee(n * px) > cash:
                    n = int((cash - fee(n * px)) // (px * (1 + cfg.cost)))
                if n <= 0:
                    continue
                gross = n * px
                f0 = fee(gross)
                cash -= gross * (1 + cfg.cost) + f0
                costs += gross * cfg.cost + f0
                pos[tk] = engine.Pos(n, t, px, gross * (1 + cfg.cost) + f0, px, sec)
                secn[sec] = secn.get(sec, 0) + 1
        for tk in list(pos):
            c = engine._px(m.C, t, tk)
            if c == c:
                last_close[tk] = c
            lv = last_valid.get(tk)
            if lv is not None and pd.notna(lv) and (pd.Timestamp(lv) < t or (pd.Timestamp(lv) == t and t < idx[-1])):
                sell(tk, last_close.get(tk, pos[tk].entry_px), pd.Timestamp(lv), "delisted")
        val = cash + sum(p.shares * last_close.get(tk, p.entry_px) for tk, p in pos.items())
        equity.append((t, val))
        invested.append(1 - cash / val if val > 0 else 0.0)
    return {"equity": pd.Series(dict(equity)), "invested": float(np.mean(invested)), "cash": cash, "pos": pos, "last_close": last_close,
            "trades": trades, "taxes": taxes, "costs": costs, "pot": pot, "P": {"reg": reg if mode != "none" else pd.Series(True, index=idx)}}


def report(m: engine.Market, meta: dict, start: str, cfg: Config, strategy: str = "position", rule: dict | None = None) -> dict:
    if strategy == "langfrist":
        pre, post = run_baseline(m, start, cfg, tax=False, rule=rule), run_baseline(m, start, cfg, tax=True, rule=rule)
    else:
        P = engine.prepare(m, cfg)
        pre = engine.run(m, start, cfg=cfg, tax=False, P=P)
        post = engine.run(m, start, cfg=cfg, tax=True, P=P)
    end_after = engine.liquidate_after_tax(post, cfg)
    spy = _yf("SPY")["Close"].reindex(pre["equity"].index).ffill()
    bench = spy / spy.iloc[0] * cfg.start_capital
    b_end_after = bench.iloc[-1] - max(0.0, bench.iloc[-1] - cfg.start_capital) * cfg.tax * (1 - cfg.etf_partial_exemption)
    yrs = (pre["equity"].index[-1] - pre["equity"].index[0]).days / 365.25
    tr = post["trades"]
    closed = [x for x in tr if x["why"] != "open"]
    mp, mb = metrics(pre["equity"]), metrics(bench)
    eq_after = post["equity"]
    mpost = metrics(eq_after)
    halves = {}
    for nm, (a, b) in {"2016–2020": (None, "2020-12-31"), "2021–heute": ("2021-01-01", None)}.items():
        e, bb = pre["equity"].loc[a:b], bench.loc[a:b]
        if len(e) > 50:
            halves[nm] = {"cagr": metrics(e)["cagr"], "mdd": metrics(e)["mdd"], "bench_cagr": metrics(bb)["cagr"], "bench_mdd": metrics(bb)["mdd"]}
    rep = {
        "period": [pre["equity"].index[0].strftime("%Y-%m-%d"), pre["equity"].index[-1].strftime("%Y-%m-%d")],
        "start_capital": cfg.start_capital, "end_pre_tax": mp["end"], "end_after_tax": end_after,
        "total_pre": mp["total"], "cagr_pre": mp["cagr"], "total_after": end_after / cfg.start_capital - 1,
        "cagr_after": (end_after / cfg.start_capital) ** (1 / yrs) - 1,
        "bench_end": float(bench.iloc[-1]), "bench_end_after": float(b_end_after), "bench_total": mb["total"], "bench_cagr": mb["cagr"],
        "bench_cagr_after": (b_end_after / cfg.start_capital) ** (1 / yrs) - 1, "bench_mdd": mb["mdd"], "bench_sharpe": mb["sharpe"],
        "mdd": mp["mdd"], "mdd_after": mpost["mdd"], "sharpe": mp["sharpe"], "trades": len(closed),
        "win_rate": float(np.mean([x["pnl"] > 0 for x in closed])) if closed else None,
        "avg_days": float(np.mean([x["days"] for x in closed])) if closed else None,
        "costs": post["costs"], "taxes": post["taxes"], "halves": halves,
        "exits": {k: sum(1 for x in closed if k in x["why"].split(",")) for k in ("trend", "stop", "rank", "delisted", "regime")},
        "invested": pre["invested"], "regime_on": float(pre["P"]["reg"].loc[pre["equity"].index].mean()),
        "missing": sorted(meta["missing"]), "notes": meta["notes"], "n_prices": meta["n_prices"],
    }
    return rep


# ---------------------------------------------------------------- Mischung Welt-ETF + Langfrist-Strategie
def mix(strat_eq: pd.Series, liq_factor: float, etf: pd.Series, w: float, cfg: Config = CFG) -> dict:
    """Depot aus Welt-ETF (Anteil 1−w) und Langfrist-Strategie (Anteil w), Ausgleich am ersten Handelstag jedes Jahres.
    strat_eq: Depotwert der Strategie im Lauf MIT Steuern (realisierte Gewinne innerhalb der Strategie schon versteuert).
    ETF: Kauf/Verkauf 0,10 %, Gewinne beim Verkauf mit 26,375 % auf 70 % (Teilfreistellung), ETF-Verluste in eigenen Topf.
    Näherungen: Entnahmen aus der Strategie beim Ausgleich ohne Extra-Steuer (Bestände wechseln dort ohnehin vierteljährlich,
    kaum unrealisierte Gewinne); am Ende Strategie-Anteil × liq_factor (Steuer auf offene Gewinne wie im Einzellauf); keine Vorabpauschale."""
    idx = strat_eq.index
    e = etf.reindex(idx).ffill().bfill()
    rs, re = strat_eq.pct_change().fillna(0.0), e.pct_change().fillna(0.0)
    cap = cfg.start_capital
    S = cap * w
    U = cap * (1 - w) * (1 - cfg.cost)
    B, pot, taxes, costs = cap * (1 - w), 0.0, 0.0, cap * (1 - w) * cfg.cost
    years = pd.Series(idx, index=idx).groupby(idx.year).first()
    reb = set(years.iloc[1:])
    vals = []
    for t in idx:
        S *= 1 + rs[t]
        U *= 1 + re[t]
        if t in reb and 0 < w < 1:
            tot = S + U
            tu = tot * (1 - w)
            if U > tu:                                          # ETF verkaufen → Strategie
                x = U - tu
                g = x * (1 - B / U) if U > 0 else 0.0
                tx = 0.0
                if g < 0:
                    pot += -g
                else:
                    use = min(pot, g)
                    pot -= use
                    tx = (g - use) * (1 - cfg.etf_partial_exemption) * cfg.tax
                B *= 1 - x / U
                U -= x
                c = x * cfg.cost
                S += x - tx - c
                taxes, costs = taxes + tx, costs + c
            else:                                               # Strategie verkaufen → ETF
                y = tu - U
                c = y * cfg.cost * 2
                S -= y
                U += y - c
                B += y - c
                costs += c
        vals.append((t, S + U))
    v = pd.Series(dict(vals))
    g = max(0.0, U - B)
    use = min(pot, g)
    etf_tax = (g - use) * (1 - cfg.etf_partial_exemption) * cfg.tax
    end_after = U - etf_tax + S * liq_factor
    yrs = (idx[-1] - idx[0]).days / 365.25
    m = metrics(v)
    ann = (v.groupby(v.index.year).last() / pd.concat([pd.Series({idx[0].year: cap}), v.groupby(v.index.year).last().shift(1).dropna()]).sort_index() - 1)
    return {"w": w, "end_pre": m["end"], "end_after": end_after, "cagr_after": (end_after / cap) ** (1 / yrs) - 1, "cagr_pre": m["cagr"],
            "mdd": m["mdd"], "sharpe": m["sharpe"], "taxes_rebal": taxes, "costs": costs,
            "worst_year": float(ann.min()), "worst_year_y": int(ann.idxmin()), "years": {int(k): round(float(x), 4) for k, x in ann.items()},
            "mdd_2122": float((1 - v.loc["2021":"2022"] / v.loc["2021":"2022"].cummax()).max())}


def mix_report(m: engine.Market, start: str, cfg: Config, etf_ticker: str = "ACWI", rule: dict | None = None) -> list[dict]:
    post = run_baseline(m, start, cfg, tax=True, rule=rule)
    f = engine.liquidate_after_tax(post, cfg) / float(post["equity"].iloc[-1])
    etf = _yf(etf_ticker)["Close"]
    out = [mix(post["equity"], f, etf, w, cfg) for w in (0.0, 0.2, 0.3, 0.5, 1.0)]
    e = lambda x: f"{x:,.0f} €".replace(",", ".")
    p = lambda x: f"{x * 100:+.1f} %".replace(".", ",")
    print(f"\n===== Mischung Welt-ETF ({etf_ticker}) + Langfrist-Strategie, Ausgleich jährlich, {post['equity'].index[0]:%Y-%m-%d} – {post['equity'].index[-1]:%Y-%m-%d} =====")
    print("  ETF/Strategie   Ende n. St.   CAGR n. St.  CAGR v. St.  Max DD   DD 2021/22  Sharpe  schlechtestes Jahr  Steuer Ausgleich")
    for r in out:
        print(f"  {round((1 - r['w']) * 100):>3}/{round(r['w'] * 100):<3}       {e(r['end_after']):>13} {p(r['cagr_after']):>10} {p(r['cagr_pre']):>11} {p(-r['mdd']):>8} {p(-r['mdd_2122']):>10}"
              f"  {r['sharpe']:.2f}   {p(r['worst_year'])} ({r['worst_year_y']})   {e(r['taxes_rebal'])}")
    print("  Jahresrenditen (vor Liquidationssteuer):")
    for r in out:
        print(f"  {round((1 - r['w']) * 100):>3}/{round(r['w'] * 100):<3} " + " ".join(f"{y}:{v * 100:+.0f}%" for y, v in r["years"].items()))
    return out


def variants_report(m: engine.Market, start: str) -> list[dict]:
    """Varianten der Langfrist-Regel: Anzahl Aktien, Mindest-Börsenwert, Depotgröße mit echten Gebühren (Scalable PRIME+)."""
    from dataclasses import replace as _rp
    rows = []

    def one(label, cap, rule):
        cfg = _rp(CFG, start_capital=cap)
        post = run_baseline(m, start, cfg, tax=True, rule=rule)
        end_after = engine.liquidate_after_tax(post, cfg)
        eq = post["equity"]
        yrs = (eq.index[-1] - eq.index[0]).days / 365.25
        mt = metrics(eq)
        closed = [x for x in post["trades"] if x["why"] != "open"]
        halves = {nm: metrics(eq.loc[a:b])["cagr"] for nm, (a, b) in {"16-20": (None, "2020-12-31"), "21-26": ("2021-01-01", None)}.items()}
        rows.append({"v": label, "cap": cap, "end": end_after, "cagr": (end_after / cap) ** (1 / yrs) - 1, "mdd": mt["mdd"], "sharpe": mt["sharpe"],
                     "trades": len(closed), "costs": post["costs"], "h1": halves["16-20"], "h2": halves["21-26"],
                     "cash": 1 - post["invested"]})
        r_ = rows[-1]
        print(f"  {label:<38} {cap:>8,.0f} €  Ende {r_['end']:>12,.0f} €  CAGR n. St. {r_['cagr']*100:5.1f} %  Max DD {r_['mdd']*100:5.1f} %  Sharpe {r_['sharpe'] or 0:.2f}"
              f"  16–20 {r_['h1']*100:5.1f} %  21–26 {r_['h2']*100:5.1f} %  Trades {r_['trades']:4d}  Kosten {r_['costs']:>9,.0f} €  Ø Cash {r_['cash']*100:4.1f} %".replace(",", "."), flush=True)

    print("\n===== A) Anzahl Aktien × Mindest-Börsenwert (100.000 €, 0,10 % Kosten, Abgeltungsteuer) =====")
    for mcap, ml in ((0, "alle"), (10e9, "ab 10 Mrd. $"), (50e9, "ab 50 Mrd. $")):
        for n in (10, 15, 20):
            one(f"Top {n} · {ml}", 100_000, {"n": n, "min_mc": mcap})
    print("\n===== B) Echte Gebühren Scalable PRIME+ (0,99 € unter 250 € Orderwert) + 0,10 % Spread, ganze Stücke =====")
    for cap in (1_500, 3_000, 6_000, 15_000):
        for n in (5, 10, 15, 20):
            one(f"Top {n} · alle · PRIME+", cap, {"n": n, "fee_fix": 0.99, "fee_free": 250})
    return rows


def robust_report(m: engine.Market, start: str, etf_ticker: str = "ACWI") -> list[dict]:
    """Letztes Paket: ist Top 10 belastbar (Tauschmonate, Lauf-Zeitraum, Startjahr)? Puffer-Regel, Branchen-Grenze, 70/30 je Variante."""
    rows = []
    etf = _yf(etf_ticker)["Close"]

    def one(sect, label, rule, st=start, mixit=False):
        post = run_baseline(m, st, CFG, tax=True, rule=rule)
        end_after = engine.liquidate_after_tax(post, CFG)
        eq = post["equity"]
        yrs = (eq.index[-1] - eq.index[0]).days / 365.25
        mt = metrics(eq)
        closed = [x for x in post["trades"] if x["why"] != "open"]
        row = {"sect": sect, "v": label, "rule": rule, "start": str(st), "cagr": (end_after / CFG.start_capital) ** (1 / yrs) - 1,
               "mdd": mt["mdd"], "sharpe": mt["sharpe"] or 0.0, "trades_y": len(closed) / yrs, "taxes": post["taxes"],
               "days": float(np.mean([x["days"] for x in closed])) if closed else 0.0}
        line = (f"  {label:<44} CAGR n. St. {row['cagr']*100:5.1f} %  Max DD {row['mdd']*100:5.1f} %  Sharpe {row['sharpe']:.2f}"
                f"  Verkäufe/J {row['trades_y']:5.1f}  Ø Haltedauer {row['days']:4.0f} T.  Steuern {row['taxes']:>9,.0f} €")
        if mixit:
            f = end_after / float(eq.iloc[-1])
            mx = mix(eq, f, etf, 0.3, CFG)
            row["mix"] = {"cagr": mx["cagr_after"], "mdd": mx["mdd"], "sharpe": mx["sharpe"], "worst": mx["worst_year"]}
            line += f"  | 70/30: CAGR {mx['cagr_after']*100:5.1f} %  Max DD {mx['mdd']*100:5.1f} %  Sharpe {mx['sharpe']:.2f}  schlechtestes Jahr {mx['worst_year']*100:+.1f} %"
        print(line.replace(",", "."), flush=True)
        rows.append(row)
        return row

    print("\n===== 1) Top 10 vs. Top 20 je Tauschmonate und Lauf-Zeitraum (100.000 €, Kosten, Steuern) =====")
    for off, ml in ((0, "Jan/Apr/Jul/Okt"), (1, "Feb/Mai/Aug/Nov"), (2, "Mär/Jun/Sep/Dez")):
        for lb in (6, 9, 12):
            for n in (10, 20):
                one("robust", f"Top {n} · {lb}-1 Mon. · {ml}", {"n": n, "lb": lb, "offset": off})
    print("\n===== 2) Top 10 vs. Top 20 je Startjahr (bis heute) =====")
    for st in ("2016-01-01", "2018-01-01", "2020-01-01", "2022-01-01"):
        if pd.Timestamp(st) < pd.Timestamp(start):
            continue
        for n in (10, 20):
            one("start", f"Top {n} · Start {st[:4]}", {"n": n}, st=st)
    print("\n===== 3) Puffer-Regel und Branchen-Grenze, dazu 70/30 mit Welt-ETF (" + etf_ticker + ") =====")
    for label, rule in (("Top 20 (bisher)", {"n": 20}),
                        ("Top 10", {"n": 10}),
                        ("Top 10 · behalten bis Platz 15", {"n": 10, "hold": 15}),
                        ("Top 10 · behalten bis Platz 20", {"n": 10, "hold": 20}),
                        ("Top 10 · behalten bis Platz 30", {"n": 10, "hold": 30}),
                        ("Top 20 · behalten bis Platz 40", {"n": 20, "hold": 40}),
                        ("Top 10 · max. 3 je Branche", {"n": 10, "sec_max": 3}),
                        ("Top 10 · max. 2 je Branche", {"n": 10, "sec_max": 2}),
                        ("Top 10 · Puffer 20 · max. 3 je Branche", {"n": 10, "hold": 20, "sec_max": 3})):
        one("final", label, rule, mixit=True)
    print("\n===== 4) Puffer 20 auch mit anderen Tauschmonaten (Gegenprobe) =====")
    for off, ml in ((1, "Feb/Mai/Aug/Nov"), (2, "Mär/Jun/Sep/Dez")):
        for label, rule in (("Top 10", {"n": 10}), ("Top 10 · Puffer 20", {"n": 10, "hold": 20})):
            one("check", f"{label} · {ml}", {**rule, "offset": off})
    return rows


def etf_report(m: engine.Market, start: str, cfg: Config = CFG) -> list[dict]:
    """Lohnt sich der Aufwand? Eigene Regel gegen fertige ETFs (Welt, S&P 500, Momentum-ETFs), allein und als 70/30 mit Welt-ETF.
    ETF allein: Kauf 0,10 %, am Ende 26,375 % Steuer auf 70 % des Gewinns (Teilfreistellung), keine Vorabpauschale (begünstigt ETFs leicht)."""
    world = _yf("ACWI")["Close"]
    out = []
    p = lambda x: f"{x * 100:5.1f} %"

    def line(label, eq, end_after, mx):
        yrs = (eq.index[-1] - eq.index[0]).days / 365.25
        mt = metrics(eq)
        part = lambda e: metrics(e)["cagr"] if len(e) > 20 else float("nan")
        h1, h2 = part(eq.loc[:"2020-12-31"]), part(eq.loc["2021-01-01":])
        row = {"v": label, "cagr": (end_after / cfg.start_capital) ** (1 / yrs) - 1, "mdd": mt["mdd"], "sharpe": mt["sharpe"] or 0.0,
               "h1": h1, "h2": h2, "mix": {k: mx[k] for k in ("cagr_after", "mdd", "sharpe", "worst_year")} if mx else None}
        s_ = (f"  {label:<40} allein: CAGR n. St. {p(row['cagr'])}  Max DD {p(row['mdd'])}  Sharpe {row['sharpe']:.2f}  16–20 {p(h1)}  21–26 {p(h2)}")
        if mx:
            s_ += f"  | 70 % Welt-ETF + 30 %: CAGR n. St. {p(mx['cagr_after'])}  Max DD {p(mx['mdd'])}  Sharpe {mx['sharpe']:.2f}  schlechtestes Jahr {mx['worst_year']*100:+.1f} %"
        print(s_, flush=True)
        out.append(row)

    print(f"\n===== Eigene Regel vs. fertige ETFs, ab {start}, nach Steuern (Momentum-ETF-Anteil im 70/30 ohne Steuer beim jährlichen Ausgleich) =====")
    idx0 = None
    for label, rule in (("Eigene Regel: Top 10 + Puffer 20", {"n": 10, "hold": 20}), ("Eigene Regel: Top 20 (bisher)", {"n": 20})):
        post = run_baseline(m, start, cfg, tax=True, rule=rule)
        eq = post["equity"]
        idx0 = eq.index if idx0 is None else idx0
        ea = engine.liquidate_after_tax(post, cfg)
        line(label, eq, ea, mix(eq, ea / float(eq.iloc[-1]), world, 0.3, cfg))
    for t, label in (("ACWI", "Welt-ETF (MSCI ACWI)"), ("URTH", "Welt-ETF (MSCI World)"), ("SPY", "S&P 500"),
                     ("MTUM", "Momentum-ETF USA (MSCI USA Momentum)"), ("IWMO.L", "Momentum-ETF Welt (MSCI World Momentum)"),
                     ("QQQ", "Nasdaq 100")):
        try:
            c = _yf(t)["Close"].reindex(idx0).ffill().dropna()
        except Exception as e:                                     # noqa: BLE001
            print(f"  {label}: keine Daten ({e})")
            continue
        if len(c) < 0.9 * len(idx0):
            print(f"  {label}: zu kurze Historie ({c.index[0]:%Y-%m-%d})")
            continue
        eq = c / c.iloc[0] * cfg.start_capital * (1 - cfg.cost)
        e_ = float(eq.iloc[-1])
        ea = e_ * (1 - cfg.cost) - max(0.0, e_ - cfg.start_capital) * cfg.tax * (1 - cfg.etf_partial_exemption)
        mx = None if t in ("ACWI",) else mix(eq, ea / e_, world, 0.3, cfg)
        line(label, eq, ea, mx)
    return out


def print_report(rep: dict, title: str):
    e = lambda x: f"{x:,.0f} €".replace(",", ".")
    p = lambda x: "–" if x is None else f"{x * 100:+.1f} %".replace(".", ",")
    print(f"\n===== {title} ({rep['period'][0]} – {rep['period'][1]}, {rep['n_prices']} Aktien) =====")
    print(f"  Startkapital                  {e(rep['start_capital'])}")
    print(f"  Endkapital vor Steuern        {e(rep['end_pre_tax'])}   (Index Buy & Hold: {e(rep['bench_end'])})")
    print(f"  Endkapital nach Steuern       {e(rep['end_after_tax'])}   (Index nach Steuer, 30 % Teilfreistellung: {e(rep['bench_end_after'])})")
    print(f"  Gesamtrendite vor / nach St.  {p(rep['total_pre'])} / {p(rep['total_after'])}   (Index {p(rep['bench_total'])})")
    print(f"  CAGR vor / nach Steuern       {p(rep['cagr_pre'])} / {p(rep['cagr_after'])} p. a.   (Index {p(rep['bench_cagr'])} / {p(rep['bench_cagr_after'])})")
    print(f"  Max Drawdown                  {p(-rep['mdd'])}   (Index {p(-rep['bench_mdd'])})")
    print(f"  Sharpe Ratio                  {rep['sharpe']:.2f}   (Index {rep['bench_sharpe']:.2f})")
    print(f"  Trades / Win-Rate / Haltedauer {rep['trades']} / {p(rep['win_rate'])} / {rep['avg_days']:.0f} Tage" if rep["trades"] else "  Trades: 0")
    print(f"  Exits: Trendbruch {rep['exits']['trend']} · Trailing-Stop {rep['exits']['stop']} · Rang {rep['exits']['rank']} · Delisting {rep['exits']['delisted']} · Marktfilter {rep['exits'].get('regime', 0)}")
    print(f"  Ø investiert                  {rep['invested'] * 100:.0f} % des Depots · Marktfilter „Käufe frei“ an {rep['regime_on'] * 100:.0f} % der Tage")
    print(f"  Transaktionskosten gesamt     {e(rep['costs'])}")
    print(f"  Abgeltungsteuer gesamt        {e(rep['taxes'])}")
    for k, v in rep["halves"].items():
        print(f"  {k}: CAGR {p(v['cagr'])} (Index {p(v['bench_cagr'])}) · Max DD {p(-v['mdd'])} (Index {p(-v['bench_mdd'])})")
    print(f"  Historisch nicht vorhanden (neutral 50 bzw. nicht geprüft): {', '.join(rep['missing'])}")
    for n in rep["notes"]:
        print(f"  Hinweis: {n}")
    print("  Hinweis Überlebens-Verzerrung: Das Universum enthält nur heute gelistete Aktien – Pleiten/Delistings der Vergangenheit fehlen.")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("a", nargs="?")
    ap.add_argument("b", nargs="?")
    ap.add_argument("--universe", default="us")
    ap.add_argument("--momentum", default="clenow")
    ap.add_argument("--start", default="2016-01-04")
    ap.add_argument("--out", default="")
    ap.add_argument("--trail", type=float, default=CFG.trail_atr, help="Diagnose: 0 = ohne Trailing-Stop")
    ap.add_argument("--sizing", default="atr", help="Diagnose: equal = 1/15 je Position")
    ap.add_argument("--no-regime", action="store_true", help="Diagnose: ohne Marktfilter")
    ap.add_argument("--risk", type=float, default=CFG.risk_per_atr, help="Risiko je ATR (Anteil des Depots)")
    ap.add_argument("--maxw", type=float, default=CFG.max_weight, help="Positions-Cap")
    ap.add_argument("--rebalance", default=CFG.rebalance, help="weekly | monthly | quarterly")
    ap.add_argument("--regime-mode", default="none", help="nur --strategy langfrist: none | quarter | daily | buys")
    ap.add_argument("--strategy", default="position", help="langfrist = bisherige Regel (12-1-Momentum, Top 20, quartalsweise)")
    x = ap.parse_args(argv)
    if x.cmd == "prices":
        prices(int(x.a), int(x.b))
        return 0
    if x.cmd == "mix10":                                          # Mischungen mit der endgültigen Regel Top 10 + Puffer 20
        m, meta = load_market(x.a, x.universe, Config())
        out = mix_report(m, x.start, Config(), rule={"n": 10, "hold": 20})
        if x.out:
            Path(x.out).write_text(json.dumps(out, ensure_ascii=False, default=str))
        return 0
    if x.cmd == "etf":
        m, meta = load_market(x.a, x.universe, Config())
        out = etf_report(m, x.start)
        if x.out:
            Path(x.out).write_text(json.dumps(out, ensure_ascii=False, default=str))
        return 0
    if x.cmd == "robust":
        m, meta = load_market(x.a, x.universe, Config())
        out = robust_report(m, x.start)
        if x.out:
            Path(x.out).write_text(json.dumps(out, ensure_ascii=False, default=str))
        return 0
    if x.cmd == "variants":
        m, meta = load_market(x.a, x.universe, Config())
        out = variants_report(m, x.start)
        if x.out:
            Path(x.out).write_text(json.dumps(out, ensure_ascii=False, default=float))
        return 0
    if x.cmd == "mix":
        cfg = Config()
        m, meta = load_market(x.a, x.universe, cfg)
        out = mix_report(m, x.start, cfg)
        if x.out:
            Path(x.out).write_text(json.dumps(out, ensure_ascii=False, default=float))
        return 0
    cfg = Config(momentum=x.momentum, trail_atr=x.trail, sizing=x.sizing, use_regime=not x.no_regime, risk_per_atr=x.risk,
                 max_weight=x.maxw, rebalance=x.rebalance)
    m, meta = load_market(x.a, x.universe, cfg)
    rep = report(m, meta, x.start, cfg, x.strategy, {"regime": x.regime_mode})
    if x.strategy == "langfrist":
        rep["missing"] = []
        print_report(rep, f"BISHERIGE Strategie Kairo Langfrist (12-1-Momentum, Top 20, quartalsweise) · Marktfilter {x.regime_mode} · Universum {x.universe}")
    else:
        print_report(rep, f"Universum {x.universe} · Momentum {x.momentum} · Risiko {x.risk:.3%} je ATR · Cap {x.maxw:.0%} · Stop {x.trail} ATR · "
                          f"Rebalancing {x.rebalance} · Größe {x.sizing} · Marktfilter {'aus' if x.no_regime else 'an'}")
    if x.out:
        Path(x.out).write_text(json.dumps(rep, ensure_ascii=False, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())
