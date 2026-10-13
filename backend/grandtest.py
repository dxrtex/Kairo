"""Großer Strategie-Vergleich: Welche Richtung bringt einem Privatanleger (3.000 €, Scalable, kein Daytrading) am meisten?

Alle Strategien unter gleichen Bedingungen, Tag für Tag:
- Startdepot 3.000 €, Gebühr 0,99 € je Order (Scalable Free), Spread 0,05 % (ETF) bzw. 0,1 % (Aktie).
- Entscheidungen nur mit Daten bis zum Monatsende, ausgeführt zum Schluss des nächsten Handelstags (kein Blick in die Zukunft).
- Standard-Parameter aus der Literatur (200-Tage-Linie, 12-Monats-Momentum, Top 3 Sektoren, Top 10 Aktien) – nichts optimiert.
- Steuern (Näherung): 26,375 % Abgeltungsteuer, 1.000 € Freibetrag/Jahr, Verlustvortrag; aktive Strategien versteuern
  jährlich, Kaufen-und-Halten erst am Ende; Aktien-ETFs mit 30 % Teilfreistellung.
- Risiko-Stufen: Jede Strategie zusätzlich mit Cash gemischt bzw. gehebelt (Faktor k), sodass der größte Rückgang höchstens
  20 / 30 / 50 % beträgt – zeigt, wer bei gleichem Risiko am meisten bringt (k im Nachhinein gewählt → nur zum Vergleichen).

Grenzen: Aktien-Strategien (Momentum, Insider, Kairo) nutzen das heutige Aktien-Universum (Survivorship-Bias → zu gut);
Kurse in US-Dollar (Wechselkurs nicht eingerechnet).

    python -m backend.grandtest [--kairo Ordner1 Ordner2 …]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from .config import ROOT

START, FEE, SP_ETF, SP_STK = 3000.0, 0.99, 0.0005, 0.001
TAX, ALLOW = 0.26375, 1000.0
ETFS = ["SPY", "QQQ", "EFA", "ACWI", "AGG", "IEF", "BIL", "GLD", "XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB",
        "USMV", "MTUM", "QUAL", "VLUE", "^IRX", "^VIX"]
SECTORS = ["XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB"]
EQ_ETF = set(["SPY", "QQQ", "EFA", "ACWI", "USMV", "MTUM", "QUAL", "VLUE", "SPY2X", "SPY3X"] + SECTORS)


def _closes(tickers: list[str], period: str = "max", batch: int = 60, pause: float = 4.0) -> pd.DataFrame:
    """Schlusskurse (bereinigt) – langsam und mit Wiederholungen, weil Yahoo sonst sperrt (Rate-Limit)."""
    import yfinance as yf
    frames, todo = [], list(dict.fromkeys(tickers))
    for rnd in range(4):
        failed = []
        for i in range(0, len(todo), batch):
            part = todo[i:i + batch]
            try:
                d = yf.download(part, period=period, interval="1d", auto_adjust=True, progress=False, threads=True, group_by="column")
                c = d["Close"] if isinstance(d.columns, pd.MultiIndex) else d[["Close"]].rename(columns={"Close": part[0]})
                ok = [t for t in c.columns if c[t].notna().any()]
                frames.append(c[ok])
                failed += [t for t in part if t not in ok]
            except Exception as exc:
                print("Download-Fehler", repr(exc)[:120], flush=True)
                failed += part
            time.sleep(pause)
        print(f"Kurse Runde {rnd + 1}: {len(todo) - len(failed)} von {len(todo)} geladen", flush=True)
        if not failed or len(failed) == len(todo) and rnd > 0:
            break
        todo = failed
        time.sleep(60)
    out = pd.concat(frames, axis=1) if frames else pd.DataFrame()
    out.index = pd.to_datetime(out.index).tz_localize(None).normalize()
    out = out[~out.index.duplicated()]
    return out.loc[:, ~out.columns.duplicated()].sort_index()


# ---------- Simulation ----------
def run_weights(rets: pd.DataFrame, targets: dict, spreads: dict, start: float = START, fee: float = FEE, drift: float = 0.5) -> pd.Series:
    """Depotwert je Tag. targets: {Ausführungstag: {Anlage: Gewicht}} (Gewichte summieren ≤ 1, Rest = CASH).
    Gehandelt wird nur, was sich ändert: Ausstiege, Einstiege, Positionen mit mehr als `drift` relativer Abweichung."""
    hold, val, out, trades = {}, start, {}, 0
    days = rets.index
    for t in days:
        r = rets.loc[t]
        for a in list(hold):
            x = r.get(a)
            hold[a] *= 1 + (0.0 if x is None or not np.isfinite(x) else x)
        val = sum(hold.values()) if hold else val
        if t in targets:
            w = {a: x for a, x in targets[t].items() if x > 0}
            w["CASH"] = max(0.0, 1 - sum(w.values()))
            tot = sum(hold.values()) if hold else val
            new, cost = {}, 0.0
            for a in set(w) | set(hold):
                cur, tgt = hold.get(a, 0.0), tot * w.get(a, 0.0)
                if a != "CASH" and (cur == 0 or tgt == 0 or abs(tgt - cur) > drift * cur):
                    if abs(tgt - cur) > 1:
                        cost += fee + abs(tgt - cur) * spreads.get(a, SP_STK)
                        trades += 1
                    new[a] = tgt
                else:
                    new[a] = cur if a != "CASH" else 0.0
            new["CASH"] = tot - sum(v for a, v in new.items() if a != "CASH") - cost
            hold = {a: v for a, v in new.items() if v > 0.01 or a == "CASH"}
            val = sum(hold.values())
        elif not hold:
            hold = {"CASH": val}
        out[t] = val
    s = pd.Series(out)
    s.attrs["trades"] = trades
    return s


def stats(v: pd.Series, mode: str = "active", tf: float = 1.0) -> dict:
    v = v.dropna()
    if len(v) < 60 or v.iloc[0] <= 0:
        return {}
    yrs = (v.index[-1] - v.index[0]).days / 365.25
    cagr = (v.iloc[-1] / v.iloc[0]) ** (1 / yrs) - 1
    dd = 1 - v / v.cummax()
    yr = v.groupby(v.index.year).last()
    first = pd.Series([v.iloc[0]], index=[v.index[0].year - 1])
    yret = pd.concat([first, yr]).pct_change().dropna()
    return {"von": str(v.index[0].date()), "bis": str(v.index[-1].date()), "cagr": round(float(cagr), 4),
            "mdd": round(float(dd.max()), 4), "schlechtestes_jahr": round(float(yret.min()), 3),
            "verlustjahre": int((yret < 0).sum()), "jahre": int(len(yret)), "nach_steuern": round(after_tax(v, mode, tf), 4),
            "ende_eur": round(float(v.iloc[-1] / v.iloc[0] * START)), "orders": v.attrs.get("trades")}


def after_tax(v: pd.Series, mode: str, tf: float) -> float:
    """CAGR nach Steuern (Näherung). mode active: Gewinne jährlich versteuert; hold: erst beim Verkauf am Ende."""
    v = v / v.iloc[0] * START
    yrs = (v.index[-1] - v.index[0]).days / 365.25
    if mode == "hold":
        gain = max(0.0, (v.iloc[-1] - START) * tf - ALLOW)
        return float(((v.iloc[-1] - gain * TAX) / START) ** (1 / yrs) - 1)
    val, carry = START, 0.0
    yr = v.groupby(v.index.year).last()
    prev = START
    for y, x in yr.items():
        g = val * (x / prev - 1)
        prev = x
        taxable = g * tf
        if taxable < 0:
            carry += -taxable
            tax = 0.0
        else:
            use = min(carry, taxable)
            carry -= use
            tax = max(0.0, taxable - use - ALLOW) * TAX
        val = val + g - tax
    return float((val / START) ** (1 / yrs) - 1)


def scaled(r: pd.Series, cash: pd.Series, k: float) -> pd.Series:
    """Strategie-Rendite mit Faktor k: k < 1 = Rest in Cash, k > 1 = auf Kredit (Cash + 1,5 % p. a.)."""
    c = cash.reindex(r.index).fillna(0)
    out = k * r + (1 - k) * c
    if k > 1:
        out -= (k - 1) * 0.015 / 252
    return out


def risk_levels(v: pd.Series, cash: pd.Series) -> dict:
    r = v.pct_change().dropna()
    res = {}
    for tgt in (0.2, 0.3, 0.5):
        best = None
        for k in np.arange(0.1, 3.01, 0.05):
            s = (1 + scaled(r, cash, k)).cumprod()
            if (1 - s / s.cummax()).max() <= tgt:
                yrs = (s.index[-1] - s.index[0]).days / 365.25
                best = {"k": round(float(k), 2), "cagr": round(float(s.iloc[-1] ** (1 / yrs) - 1), 4)}
        res[f"max_{int(tgt * 100)}"] = best
    return res


# ---------- Insider (OpenInsider, historisch nach Meldedatum) ----------
def insider_history(months: list[pd.Timestamp]) -> dict:
    from .insider import _cells, _num_us
    out = {}
    for m in months:
        a, b = m.replace(day=1), m
        params = {"s": "", "fd": "-1", "fdr": f"{a:%m/%d/%Y} - {b:%m/%d/%Y}", "td": "0", "xp": "1", "vl": "100",
                  "isofficer": "1", "iscob": "1", "isceo": "1", "ispres": "1", "iscoo": "1", "iscfo": "1", "isgc": "1", "isvp": "1",
                  "grp": "0", "sortcol": "0", "cnt": "1000", "page": "1"}
        try:
            page = requests.get("http://openinsider.com/screener", params=params, headers={"User-Agent": "Mozilla/5.0 (Kairo Scanner)"}, timeout=40).text
        except Exception as exc:
            print("Insider", m.date(), repr(exc)[:80])
            continue
        tab = re.search(r'<table[^>]*class="tinytable"[^>]*>(.*?)</table>', page, re.S)
        if not tab:
            continue
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", tab.group(1), re.S)
        head = [h.replace("\xa0", " ").lower() for h in _cells(rows[0])] if rows else []
        ti = next((i for i, h in enumerate(head) if h.startswith("ticker")), None)
        vi = next((i for i, h in enumerate(head) if h.startswith("value")), None)
        if ti is None or vi is None:
            continue
        agg = {}
        for r in rows[1:]:
            c = _cells(r)
            if len(c) <= max(ti, vi):
                continue
            tk = (re.findall(r"[A-Z][A-Z0-9.\-]{0,7}", c[ti].upper()) or [""])[-1]
            val = abs(_num_us(c[vi]))
            if tk and 0 < val < 2e9:
                agg[tk] = agg.get(tk, 0) + val
        out[str(m.date())] = agg
        time.sleep(0.6)
    print(f"Insider: {len(out)} Monate, {sum(len(x) for x in out.values())} Aktien-Monate", flush=True)
    return out


def load_kairo(dirs: list[str]) -> list[pd.Series]:
    from .shortswing import kairo_series
    res = []
    for d in dirs:
        hits = []
        for p in sorted(Path(d).glob("bilanz_part_*.json")):
            for e in json.loads(p.read_text()):
                if e.get("k") == "hit" and e.get("px") and e["px"].get("wd"):
                    hits.append(e)
        seen, uniq = set(), []
        for e in hits:
            if (e["t"], e["d"]) not in seen:
                seen.add((e["t"], e["d"]))
                uniq.append(e)
        ser = kairo_series({"hit": uniq})
        print(f"Kairo {d}: {len(uniq)} Treffer, {len(ser)} Tage", flush=True)
        if ser:
            s = pd.Series(ser)
            s.index = pd.to_datetime(s.index)
            res.append(s.sort_index())
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kairo", nargs="*", default=[])
    ap.add_argument("--stocks", type=int, default=3000)
    a = ap.parse_args(argv)
    t0 = time.time()
    px = _closes(ETFS)
    print("ETF-Daten:", {c: str(px[c].first_valid_index().date()) for c in px.columns if px[c].notna().any()}, flush=True)
    spy = px["SPY"].dropna()
    cal = spy.index[spy.index >= "1999-01-01"]
    px = px.reindex(cal).ffill(limit=5)
    cash = (px["^IRX"].ffill().fillna(0) / 100 / 252).shift(1).fillna(0)
    rets = px.drop(columns=["^IRX", "^VIX"]).pct_change()
    rets["CASH"] = cash
    r_spy = rets["SPY"]
    for L in (2, 3):
        rets[f"SPY{L}X"] = L * r_spy - (L - 1) * (cash + 0.005 / 252) - 0.009 / 252
    spreads = {c: SP_ETF for c in rets.columns}
    month_end = pd.DatetimeIndex(pd.Series(cal, index=cal).groupby([cal.year, cal.month]).last().values)
    nxt = {me: cal[min(len(cal) - 1, cal.get_loc(me) + 1)] for me in month_end}
    sma200 = px["SPY"].rolling(200).mean()
    ret12 = px.pct_change(252)
    ret6 = px.pct_change(126)
    cash12 = (1 + cash).rolling(252).apply(np.prod, raw=True) - 1

    def plan(fn, start="1999-01-01"):
        tg = {}
        for me in month_end:
            if me < pd.Timestamp(start):
                continue
            w = fn(me)
            if w is not None:
                tg[nxt[me]] = w
        return tg

    up = lambda me: px.at[me, "SPY"] > sma200.at[me] if np.isfinite(sma200.at[me]) else True
    S = {}
    S["A1 S&P 500 kaufen und halten"] = (plan(lambda me: {"SPY": 1}), "hold", 0.7)
    S["A2 Welt-ETF (ACWI) kaufen und halten"] = (plan(lambda me: {"ACWI": 1} if np.isfinite(px.at[me, "ACWI"]) else None), "hold", 0.7)
    S["A3 Nasdaq-100 kaufen und halten"] = (plan(lambda me: {"QQQ": 1}), "hold", 0.7)
    S["B Trendfilter: S&P 500 nur über der 200-Tage-Linie"] = (plan(lambda me: {"SPY": 1} if up(me) else {}), "active", 0.7)
    state = {"lev": False}
    def vix_fn(me):
        v = px.at[me, "^VIX"]
        if np.isfinite(v):
            state["lev"] = v >= 30 or (state["lev"] and v >= 20)
        return {"SPY2X": 1} if state["lev"] else {"SPY": 1}
    S["C S&P 500, im Ausverkauf (VIX ≥ 30) doppelt"] = (plan(vix_fn), "active", 0.7)
    def gem(me):
        s12, e12, c12 = ret12.at[me, "SPY"], ret12.at[me, "EFA"], cash12.at[me]
        if not all(np.isfinite([s12, e12])) or not np.isfinite(px.at[me, "AGG"]):
            return None
        if s12 <= (c12 if np.isfinite(c12) else 0):
            return {"AGG": 1}
        return {"SPY": 1} if s12 >= e12 else {"EFA": 1}
    S["D Dual Momentum (USA / Welt / Anleihen)"] = (plan(gem), "active", 0.7)
    def sect(me, trend=False):
        r6 = {s: ret6.at[me, s] for s in SECTORS if np.isfinite(ret6.at[me, s])}
        if len(r6) < 6:
            return None
        if trend and not up(me):
            return {}
        top = sorted(r6, key=r6.get, reverse=True)[:3]
        return {s: 1 / 3 for s in top}
    S["E1 Sektor-Rotation (Top 3 von 9)"] = (plan(sect), "active", 0.7)
    S["E2 Sektor-Rotation + Trendfilter"] = (plan(lambda me: sect(me, True)), "active", 0.7)
    S["F1 2× S&P 500 mit Trendfilter"] = (plan(lambda me: {"SPY2X": 1} if up(me) else {}), "active", 0.7)
    S["F2 3× S&P 500 mit Trendfilter"] = (plan(lambda me: {"SPY3X": 1} if up(me) else {}), "active", 0.7)
    S["F3 2× S&P 500 immer"] = (plan(lambda me: {"SPY2X": 1}), "hold", 0.7)
    for f, n in (("USMV", "Low-Volatility"), ("MTUM", "Momentum-Faktor"), ("QUAL", "Qualitäts-Faktor"), ("VLUE", "Value-Faktor")):
        S[f"G {n}-ETF ({f}) halten"] = (plan(lambda me, f=f: {f: 1} if np.isfinite(px.at[me, f]) else None), "hold", 0.7)

    results, values = {}, {}
    for name, (tg, mode, tf) in S.items():
        if not tg:
            continue
        v = run_weights(rets, tg, spreads)
        v = v[v.index >= min(tg)]
        values[name] = (v, mode, tf)
    print("ETF-Strategien fertig", f"{time.time() - t0:.0f} s", flush=True)

    # ---------- Aktien-Momentum (US-Universum von heute) ----------
    try:
        from .universe import load as load_universe
        uni = load_universe()
        us = [t for t in uni.loc[uni["region"] == "us", "ticker"].astype(str) if "." not in t and "^" not in t][: a.stocks]
        st = _closes(us, "11y").reindex(cal).ffill(limit=5)
        st = st.loc[:, st.notna().sum() > 300]
        print(f"Aktien: {st.shape[1]} von {len(us)} mit Kursen", f"{time.time() - t0:.0f} s", flush=True)
        coverage = {"aktien_geladen": int(st.shape[1]), "aktien_universum": len(us)}
        srets = st.pct_change().clip(-0.9, 3)
        mom = st.shift(21) / st.shift(252) - 1                      # 12-1 Monate
        allr = pd.concat([rets, srets], axis=1)
        sp2 = {**spreads, **{c: SP_STK for c in srets.columns}}
        def mom_fn(me, trend=False, n=10):
            m = mom.loc[me].dropna()
            m = m[(st.loc[me, m.index] >= 5)]
            m = m[m < 20]                                            # offensichtliche Datenfehler (Splits) auslassen
            if len(m) < 100:
                return None
            if trend and not up(me):
                return {}
            return {t: 1 / n for t in m.nlargest(n).index}
        for nm, fn in (("H1 Aktien-Momentum: Top 10, monatlich", lambda me: mom_fn(me)),
                       ("H2 Aktien-Momentum + Trendfilter", lambda me: mom_fn(me, True)),
                       ("H3 Aktien-Momentum: Top 5 + Trendfilter", lambda me: mom_fn(me, True, 5))):
            tg = plan(fn)
            if tg:
                v = run_weights(allr, tg, sp2)
                values[nm] = (v[v.index >= min(tg)], "active", 1.0)
        print("Momentum fertig", f"{time.time() - t0:.0f} s", flush=True)
    except Exception as exc:
        print("Momentum: Fehler", repr(exc)[:200], flush=True)

    # ---------- Insider-Käufe ----------
    try:
        months = [me for me in month_end if me >= pd.Timestamp("2016-01-01")]
        ih = insider_history(months)
        if sum(len(x) for x in ih.values()) > 200:
            tk = sorted({t for x in ih.values() for t in x})
            ipx = _closes(tk, "11y").reindex(cal).ffill(limit=5)
            irets = ipx.pct_change().clip(-0.9, 3)
            allr = pd.concat([rets, irets], axis=1)
            sp3 = {**spreads, **{c: SP_STK for c in irets.columns}}
            def ins_fn(me, trend=False):
                x = ih.get(str(me.date()))
                if not x:
                    return None
                if trend and not up(me):
                    return {}
                row = ipx.loc[me]
                ok = [t for t in sorted(x, key=x.get, reverse=True) if t in row.index and np.isfinite(float(row[t])) and float(row[t]) >= 5][:10]
                return {t: 1 / 10 for t in ok} if len(ok) >= 3 else None
            for nm, fn in (("I1 Insider-Käufe: Top 10 je Monat", ins_fn), ("I2 Insider-Käufe + Trendfilter", lambda me: ins_fn(me, True))):
                tg = plan(fn, "2016-01-01")
                if tg:
                    v = run_weights(allr, tg, sp3)
                    values[nm] = (v[v.index >= min(tg)], "active", 1.0)
        else:
            print("Insider: zu wenig Daten – nicht testbar", flush=True)
    except Exception as exc:
        print("Insider: Fehler", repr(exc)[:200], flush=True)

    # ---------- Kairo (aus dem Wahrheits-Test) und Mischungen ----------
    try:
        ks = load_kairo(a.kairo)
        kser = []
        for i, k in enumerate(ks, 1):
            k = k.reindex(cal).ffill()
            k = k[k.index >= k.first_valid_index()].dropna()
            values[f"J{i} Kairo-Swing (Stichprobe {i})"] = (k, "active", 1.0)
            kser.append(k.pct_change().fillna(0))
        if kser:
            kr = pd.concat(kser, axis=1).dropna().mean(axis=1)
            for wk in (0.3, 0.5):
                for base_name in ("A1 S&P 500 kaufen und halten", "B Trendfilter: S&P 500 nur über der 200-Tage-Linie"):
                    br = values[base_name][0].pct_change()
                    rr = pd.concat({"b": br, "k": kr}, axis=1).dropna()
                    # monatlich zurück auf die Zielgewichte (2 Orders à 0,99 €)
                    val, wb, out = START, 1 - wk, {}
                    sb, sk = START * wb, START * wk
                    last_m = None
                    for t, row in rr.iterrows():
                        sb *= 1 + row["b"]
                        sk *= 1 + row["k"]
                        if last_m is not None and t.month != last_m:
                            tot = sb + sk - 2 * FEE
                            sb, sk = tot * wb, tot * wk
                        last_m = t.month
                        out[t] = sb + sk
                    values[f"K {int((1 - wk) * 100)} % {base_name.split(' ', 1)[1].split(':')[0]} + {int(wk * 100)} % Kairo"] = (pd.Series(out), "active", 0.85)
    except Exception as exc:
        print("Kairo: Fehler", repr(exc)[:200], flush=True)

    # ---------- Auswertung in Zeitfenstern ----------
    kw = [v for n, (v, _, _) in values.items() if n.startswith("J")]
    k0 = max(v.index[0] for v in kw) if kw else pd.Timestamp("2017-10-16")
    k1 = min(v.index[-1] for v in kw) if kw else cal[-1]
    windows = {"lang (ab 2000)": (pd.Timestamp("2000-01-01"), cal[-1]), "ab 2008 (mit Finanzkrise)": (pd.Timestamp("2008-01-01"), cal[-1]),
               "Kairo-Zeitraum": (k0, k1)}
    for name, (v, mode, tf) in values.items():
        res = {}
        for wn, (w0, w1) in windows.items():
            vv = v[(v.index >= w0) & (v.index <= w1)]
            if len(vv) < 250 or vv.index[0] > w0 + timedelta(days=40):
                continue
            vv = vv.copy()
            vv.attrs = v.attrs
            s = stats(vv, mode, tf)
            if s:
                s["risiko"] = risk_levels(vv, cash)
                res[wn] = s
        results[name] = res
    report = {"generated": time.strftime("%Y-%m-%d"), "abdeckung": locals().get("coverage"), "annahmen": {"start": START, "gebuehr": FEE, "steuer": TAX, "freibetrag": ALLOW},
              "fenster": {k: [str(a.date()), str(b.date())] for k, (a, b) in windows.items()}, "strategien": results}
    out = ROOT / "data" / "grandtest.json"
    out.write_text(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    print("===BEGIN===")
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    print("===END===")
    print(f"fertig in {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
