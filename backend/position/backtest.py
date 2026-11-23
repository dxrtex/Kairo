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
    months = set(range(1, 13, r["every"]))
    first = pd.Series(idx, index=idx).groupby([idx.year, idx.month]).transform("first")
    reb = set(d for d in dates if first[d] == d and d.month in months)
    reb.add(dates[0])
    cash, pos, pot, taxes, costs = float(cfg.start_capital), {}, 0.0, 0.0, 0.0
    trades, equity, invested, last_close = [], [], [], {}

    def sell(t, px, when, why):
        nonlocal cash, pot, taxes, costs
        p = pos.pop(t)
        proceeds = p.shares * px * (1 - cfg.cost)
        costs += p.shares * px * cfg.cost
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
            top = list(mom.loc[y][ok].sort_values(ascending=False).index[: r["n"]])
            for tk in [x for x in pos if x not in top]:
                px = engine._px(m.O, t, tk)
                px = px if px == px else last_close.get(tk, pos[tk].entry_px)
                sell(tk, px, t, "rank")
            val = cash + sum(p.shares * (engine._px(m.O, t, tk) if engine._px(m.O, t, tk) == engine._px(m.O, t, tk)
                                         else last_close.get(tk, p.entry_px)) for tk, p in pos.items())
            for tk in top:
                if tk in pos or (mode == "buys" and not on):
                    continue
                px = engine._px(m.O, t, tk)
                n = int(min(val / r["n"], cash) // (px * (1 + cfg.cost))) if px == px and px > 0 else 0
                if n <= 0:
                    continue
                gross = n * px
                cash -= gross * (1 + cfg.cost)
                costs += gross * cfg.cost
                pos[tk] = engine.Pos(n, t, px, gross * (1 + cfg.cost), px, m.sectors.get(tk) or "?")
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
