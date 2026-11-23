"""Langfrist-Studie (23.11.2026): Schlagen „Fondsmanager-Prinzipien“ den Welt-/US-Markt über Jahre? – VORAB FESTGELEGT.

Wunsch Jonny: App auf langfristiges Investieren wie erfolgreiche Fondsmanager ausrichten, Rendite über Jahre maximieren.
Geprüft werden nur belegte Prinzipien (Momentum, Qualität/Rentabilität, Value), long-only, große Firmen.

A) Faktor-Datenbank Kenneth French (kostenlos, USA ab 1963, inkl. untergegangener Firmen → keine Überlebens-Verzerrung):
   Markt · Große Firmen mit starkem 12-Monats-Lauf (BIG HiPRIOR) · große rentable Firmen (BIG HiOP / „Qualität“) ·
   große günstige Firmen (BIG HiBM / Value) · Mischung der drei (monatlich gleich gewichtet).
   Kosten p. a.: Markt 0,1 %, Value/Qualität 0,3 %, Momentum 0,6 %, Mischung 0,4 %.
   Lernen 07/1963–12/1999, Prüfen 01/2000–heute. Bestanden: im Prüfzeitraum ≥ 1 %-Punkt p. a. über dem Markt nach Kosten
   UND im Lernzeitraum über dem Markt. Zusätzlich: Anteil der 10-Jahres-Zeiträume über dem Markt, längste Durststrecke.
B) Unsere eigene Aktienliste (USA, 10 Jahre; ACHTUNG Überlebens-Verzerrung: nur heute noch gelistete Aktien → schönt):
   vierteljährlich die 20 Aktien mit dem stärksten 12-Monats-Lauf (ohne letzten Monat), gleich gewichtet; Variante „ruhig“:
   von den 40 stärksten die 20 mit der geringsten Schwankung; Variante jährlich umschichten. Kosten 0,15 % je Umsatz.
   Steuer wie in Deutschland: Gewinne beim Verkauf 26,375 % (Verlusttopf), ETF erst am Ende, 30 % Teilfreistellung.
   Lernen 2017–2020, Prüfen 2021–heute. Vergleich SPY nach Steuer.

    python tools/research/longterm_study.py PXDIR
"""
from __future__ import annotations

import io
import sys
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "research"))

FF = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/{}_CSV.zip"
TAX, TFS = 0.26375, 0.30


def ff_table(name: str, want: str | None = None) -> pd.DataFrame:
    """Erste Tabelle (Monatswerte, wertgewichtet) einer French-Datei → DataFrame in Dezimal, Index Monatsende."""
    req = urllib.request.Request(FF.format(name), headers={"User-Agent": "Mozilla/5.0 research"})
    raw = urllib.request.urlopen(req, timeout=60).read()
    z = zipfile.ZipFile(io.BytesIO(raw))
    txt = z.read(z.namelist()[0]).decode("latin-1")
    return parse_ff(txt)


def parse_ff(txt: str) -> pd.DataFrame:
    lines = txt.splitlines()
    i = next(k for k, s in enumerate(lines) if s.startswith(",") and k + 1 < len(lines) and lines[k + 1].strip()[:6].isdigit())
    cols = [c.strip() for c in lines[i].split(",")[1:]]
    rows = []
    for s in lines[i + 1:]:
        p = [x.strip() for x in s.split(",")]
        if not p[0].isdigit() or len(p[0]) != 6:
            break
        rows.append([p[0]] + [float(x) for x in p[1:len(cols) + 1]])
    df = pd.DataFrame(rows, columns=["d"] + cols)
    df.index = pd.to_datetime(df.pop("d"), format="%Y%m") + pd.offsets.MonthEnd(0)
    return df.replace(-99.99, np.nan) / 100


def perf(r: pd.Series, per_year=12):
    r = r.dropna()
    if len(r) < 12:
        return {}
    eq = (1 + r).cumprod()
    yrs = len(r) / per_year
    return {"cagr": float(eq.iloc[-1] ** (1 / yrs) - 1), "vol": float(r.std() * np.sqrt(per_year)),
            "mdd": float((1 - eq / eq.cummax()).max())}


def roll_beat(r, m, win=120):
    a = (1 + r).rolling(win).apply(np.prod, raw=True)
    b = (1 + m).rolling(win).apply(np.prod, raw=True)
    ok = (a / b).dropna()
    return float((ok > 1).mean()) if len(ok) else None


def drought(r, m):
    """Längste Zeit (Jahre), in der die Strategie unter ihrem früheren Höchststand gegenüber dem Markt lag."""
    rel = ((1 + r).cumprod() / (1 + m).cumprod()).dropna()
    longest, start, peak = 0, None, -1.0
    for k, (d, v) in enumerate(rel.items()):
        if v >= peak:
            peak, start = v, k
        else:
            longest = max(longest, k - start)
    return round(longest / 12, 1)


def part_a():
    print("===== A) Faktor-Datenbank Kenneth French (USA, große Firmen, long-only) =====", flush=True)
    f = ff_table("F-F_Research_Data_Factors")
    mkt = f["Mkt-RF"] + f["RF"]
    pick = lambda df, key: df[[c for c in df.columns if c.replace(" ", "").upper().startswith(key)][0]]
    mom = pick(ff_table("6_Portfolios_ME_Prior_12_2"), "BIGHI")
    val = pick(ff_table("6_Portfolios_2x3"), "BIGHI")
    qual = pick(ff_table("6_Portfolios_ME_OP_2x3"), "BIGHI")
    j = pd.concat({"Markt": mkt, "Momentum": mom, "Value": val, "Qualität": qual}, axis=1).dropna()
    j["Mischung (Mom+Val+Qual)"] = j[["Momentum", "Value", "Qualität"]].mean(axis=1)
    cost = {"Markt": .001, "Momentum": .006, "Value": .003, "Qualität": .003, "Mischung (Mom+Val+Qual)": .004}
    for k, c in cost.items():
        j[k] = j[k] - c / 12
    print(f"  Daten {j.index[0]:%m/%Y} – {j.index[-1]:%m/%Y}, Kosten p. a. abgezogen: {cost}")
    per = {"Lernen 1963–1999": (None, "1999-12-31"), "Prüfen 2000–heute": ("2000-01-01", None), "nur 2010–heute": ("2010-01-01", None)}
    res = {}
    for pn, (a, b) in per.items():
        print(f"  -- {pn}")
        s = j.loc[a:b]
        pm = perf(s["Markt"])
        for k in j.columns:
            p = perf(s[k])
            res[(k, pn)] = p["cagr"] - pm["cagr"]
            print(f"    {k:26s} {p['cagr'] * 100:6.2f} % p. a.  Schwankung {p['vol'] * 100:5.1f} %  größter Rückgang {p['mdd'] * 100:5.1f} %"
                  + ("" if k == "Markt" else f"  Vorsprung {(p['cagr'] - pm['cagr']) * 100:+5.2f} Pkt."
                     f"  10-J.-Zeiträume vorn {roll_beat(s[k], s['Markt']) * 100:4.0f} %  längste Durststrecke {drought(s[k], s['Markt'])} J."))
    for k in [c for c in j.columns if c != "Markt"]:
        ok = res[(k, "Prüfen 2000–heute")] >= 0.01 and res[(k, "Lernen 1963–1999")] > 0
        print(f"  → {k}: {'BESTANDEN' if ok else 'nicht bestanden'}")


# ---------------------------------------------------------------- B) eigene Aktienliste
def simulate(close_m, sel_fn, every, start, cost=0.0015, tax=True):
    """Monatliche Simulation mit Umschichten alle `every` Monate; deutsche Abgeltungsteuer mit Verlusttopf."""
    dates = close_m.index[close_m.index >= start]
    cash, pos, eq_hist = 1.0, {}, []
    gains_y, carry, year = 0.0, 0.0, dates[0].year
    for k, d in enumerate(dates):
        px = close_m.loc[d]
        val = cash + sum(n * (px.get(t) if np.isfinite(px.get(t, np.nan)) else pos_last[t]) for t, (n, _) in pos.items()) if pos else cash
        if d.year != year:                                     # Steuer fürs Vorjahr
            if tax:
                net = gains_y - carry
                if net > 0:
                    cash -= net * TAX
                    val -= net * TAX
                    carry = 0.0
                else:
                    carry = -net
            gains_y, year = 0.0, d.year
        if k % every == 0:
            tgt = sel_fn(d)
            if tgt is not None:
                w = val / len(tgt) if tgt else 0.0
                for t in list(pos):
                    n, basis = pos[t]
                    p = px.get(t)
                    p = p if np.isfinite(p) else pos_last[t]
                    keep = w / p if t in tgt else 0.0
                    if keep < n:                               # (teilweise) verkaufen
                        sold = n - keep
                        gains_y += sold * (p - basis)
                        cash += sold * p * (1 - cost)
                        pos[t] = (keep, basis)
                        if keep == 0:
                            del pos[t]
                for t in tgt:
                    p = px.get(t)
                    if not np.isfinite(p):
                        continue
                    n, basis = pos.get(t, (0.0, 0.0))
                    add = w / p - n
                    if add > 0 and cash > 0:
                        add = min(add, cash / (p * (1 + cost)))
                        cash -= add * p * (1 + cost)
                        pos[t] = (n + add, (n * basis + add * p) / (n + add))
        pos_last = {t: (px.get(t) if np.isfinite(px.get(t, np.nan)) else pos_last.get(t, 0)) for t in pos} if pos else {}
        eq_hist.append(cash + sum(n * pos_last[t] for t, (n, _) in pos.items()))
    eq = pd.Series(eq_hist, index=dates)
    if tax:                                                    # am Ende alles verkaufen (fairer Vergleich zum ETF)
        unreal = sum(n * (pos_last[t] - b) for t, (n, b) in pos.items()) + gains_y - carry
        eq.iloc[-1] -= max(0.0, unreal) * TAX
    return eq


def part_b(pxdir):
    from profit_study import load_px, _yf
    print("\n===== B) Eigene Aktienliste USA (Überlebens-Verzerrung! Ergebnisse sind geschönt) =====", flush=True)
    px, meta = load_px(pxdir)
    us = {t: df for t, df in px.items() if "." not in t and len(df) > 400}
    C = pd.DataFrame({t: df["Close"] for t, df in us.items()}).sort_index()
    V = pd.DataFrame({t: df["Close"] * df["Volume"] for t, df in us.items()}).sort_index()
    cm = C.resample("ME").last()
    adv = V.rolling(63, min_periods=40).mean().resample("ME").last()
    vol = C.pct_change().rolling(126, min_periods=100).std().resample("ME").last()
    mom = cm.shift(1) / cm.shift(12) - 1
    print(f"  {C.shape[1]} US-Aktien, Monate {cm.index[0]:%m/%Y} – {cm.index[-1]:%m/%Y}")

    def top(d, n=20, calm=False):
        m = mom.loc[d][(adv.loc[d] >= 5e6) & (cm.loc[d] >= 5)].dropna()
        if len(m) < 50:
            return None
        if calm:
            c = m.nlargest(2 * n).index
            return list(vol.loc[d, c].nsmallest(n).index)
        return list(m.nlargest(n).index)

    spy = _yf("SPY", "2010-01-01")["Close"].resample("ME").last()
    start = cm.index[13]
    strat = {"Momentum Top 20 (vierteljährlich)": (lambda d: top(d), 3),
             "Momentum ruhig 20 (vierteljährlich)": (lambda d: top(d, calm=True), 3),
             "Momentum Top 20 (jährlich)": (lambda d: top(d), 12),
             "Kontrolle: alle Aktien gleich gewichtet (jährlich)": (lambda d: list(cm.loc[d][(adv.loc[d] >= 5e6) & (cm.loc[d] >= 5)].dropna().index) or None, 12)}
    for pn, (a, b) in {"Lernen 2017–2020": (start, "2020-12-31"), "Prüfen 2021–heute": ("2021-01-01", None), "gesamt": (start, None)}.items():
        print(f"  -- {pn}")
        s0 = spy.loc[a:b]
        sp = (s0 / s0.iloc[0])
        yrs = max(0.5, len(sp) / 12)
        sp_tax = sp.iloc[-1] - max(0, sp.iloc[-1] - 1) * TAX * (1 - TFS)
        print(f"    {'S&P 500 ETF':50s} vor Steuer {(sp.iloc[-1] ** (1 / yrs) - 1) * 100:6.2f} % p. a. · nach Steuer {(sp_tax ** (1 / yrs) - 1) * 100:6.2f} % p. a."
              f"  größter Rückgang {(1 - sp / sp.cummax()).max() * 100:5.1f} %")
        cmp = cm.loc[a:b]
        for name, (fn, every) in strat.items():
            for tx in (False, True):
                eq = simulate(cmp, fn, every, cmp.index[0], tax=tx)
                g = eq.iloc[-1] / eq.iloc[0]
                if not tx:
                    pre, mdd = g ** (1 / yrs) - 1, (1 - eq / eq.cummax()).max()
                else:
                    post = g ** (1 / yrs) - 1
            print(f"    {name:50s} vor Steuer {pre * 100:6.2f} % p. a. · nach Steuer {post * 100:6.2f} % p. a.  größter Rückgang {mdd * 100:5.1f} %", flush=True)


if __name__ == "__main__":
    if "--nur-b" not in sys.argv:
        try:
            part_a()
        except Exception as e:
            print("Teil A fehlgeschlagen:", repr(e))
    if len(sys.argv) > 1:
        part_b(sys.argv[1])
