"""Runde 2 (26.11.2026): Welche Regel hat langfristig das beste Verhältnis von Rendite zu Risiko?

Vorab festgelegt (keine nachträgliche Suche): wenige, in der Forschung begründete Kandidaten. Auswahl je Familie NUR im
Lernzeitraum 2000–2012 (Sharpe), Urteil im ungesehenen Testzeitraum 2013–heute, dazu nach Kosten und Abgeltungsteuer
und Bootstrap. Hauptliste: S&P-500-Mitglieder zum jeweiligen Zeitpunkt (ohne Blick in die Zukunft); zum Vergleich die
heutige Liste (zu optimistisch). Kurse aus Runde 1 (Artefakt r1-px).

Kandidaten
  A  Momentum 12-1 / 9-1 / 6-1 · Top 10 / 20 / 30 · Puffer 2× (App-Regel = 12-1, Top 10, Puffer 20)
  B  Momentum durch Schwankung (Rendite 12-1 ÷ Schwankung 12 M) · Top 20 / 30
  C  Mehrfach-Momentum (Ø Rangplatz aus 3/6/9/12 Monaten) · Top 20 / 30
  D  Nähe zum 52-Wochen-Hoch · Top 20 / 30
  E  Niedrige Schwankung (ruhigste 50 Aktien) – Gegenentwurf ohne Momentum
  F  Gleichgewichteter S&P 500 (alle Mitglieder) – einfache Alternative zum Index
  G  Schutzregeln für die beste Momentum-Variante: Marktfilter (S&P 500 unter 200-Tage-Linie → S&P 500 statt Aktien),
     Trendfilter je Aktie (nur über 200-Tage-Linie), Schwankungs-Steuerung (Ziel 15 % p. a., Rest Geld)
  H  Gewichtung: gleich gegen umgekehrt zur Schwankung
  M  Mischungen mit dem Index: 100/0, 90/10, 80/20, 70/30, 50/50
Nur Analyse – keine Änderung an der App.
"""
from __future__ import annotations

import argparse
import json
import math
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import r1_fundament as R1  # noqa: E402

LEARN = ("2000-01-01", "2012-12-31")
TEST = ("2013-01-01", None)


class E2(R1.Engine):
    def __init__(self, close, vol, spy):
        super().__init__(close, vol, spy)
        r = self.C.pct_change(fill_method=None)
        self.VOL = r.rolling(252, min_periods=200).std() * math.sqrt(252)
        self.SMA = self.C.rolling(200, min_periods=180).mean()
        self.HI = self.C.rolling(252, min_periods=200).max()
        self.spy_sma = self.spy.rolling(200).mean()
        self._sc = {}

    def score(self, d, kind: str, lb: int, elig, key: str, trend: bool = False):
        k = (d, kind, lb, key, trend)
        if k in self._sc:
            return self._sc[k]
        p = self.idx.get_loc(d)
        if p < 260:
            self._sc[k] = pd.Series(dtype=float)
            return self._sc[k]
        last = self.C.iloc[p - 1]
        ok = (self.cnt.iloc[p - 1] >= 12 * 21 + 5) & (last >= R1.MIN_PX) & (self.ADV.iloc[p - 1] >= R1.MIN_ADV) & self.Craw.iloc[p - 1].notna()
        if trend:
            ok &= last > self.SMA.iloc[p - 1]
        mom = lambda L: self.C.iloc[p - 21] / self.C.iloc[p - L * 21] - 1
        if kind == "mom":
            s = mom(lb)
        elif kind == "volmom":
            s = mom(12) / self.VOL.iloc[p - 1]
        elif kind == "multi":
            parts = [mom(L)[ok].rank(pct=True) for L in (3, 6, 9, 12)]
            s = pd.concat(parts, axis=1).mean(axis=1)
        elif kind == "hi52":
            s = last / self.HI.iloc[p - 1]
        elif kind == "lowvol":
            s = -self.VOL.iloc[p - 1]
        elif kind == "ew":
            s = pd.Series(1.0, index=last.index)
        else:
            raise ValueError(kind)
        s = s[ok].replace([np.inf, -np.inf], np.nan).dropna()
        if elig is not None:
            s = s[s.index.isin(elig)]
        s = s.sort_values(ascending=False)
        self._sc[k] = s
        return s

    def path2(self, kind, n, hold, lb, start, end, elig_fn, key, trend=False, weight="eq", mkt=False):
        held, out = [], []
        for d in self.dates(0, start, end):
            if mkt and self.spy.loc[d] < self.spy_sma.loc[d]:       # Marktfilter: ganz in den Index
                held = []
                out.append((d, ["SPY"], {"SPY": 1.0}))
                continue
            s = self.score(d, kind, lb, elig_fn(d) if elig_fn else None, key, trend)
            order = list(s.index)
            if kind == "ew":
                held = order
            else:
                keep = set(order[:max(hold, n)])
                held = [t for t in held if t in keep]
                for t in order:
                    if len(held) >= n:
                        break
                    if t not in held:
                        held.append(t)
            if not held:
                out.append((d, [], {}))
                continue
            if weight == "iv":
                v = self.VOL.loc[d, held].fillna(self.VOL.loc[d, held].median())
                w = (1 / v) / (1 / v).sum()
                wd = {t: float(w[t]) for t in held}
            else:
                wd = {t: 1 / len(held) for t in held}
            out.append((d, list(held), wd))
        return out

    def curve2(self, path, cost=R1.COST):
        vals, v0, prev = [], 1.0, {}
        for k, (d, held, wd) in enumerate(path):
            end = path[k + 1][0] if k + 1 < len(path) else self.idx[-1]
            days = self.idx[(self.idx >= d) & (self.idx <= end)]
            if not held:
                seg = pd.Series(v0, index=days)
                prev = {}
            else:
                turn = sum(abs(wd.get(t, 0) - prev.get(t, 0)) for t in set(wd) | set(prev))
                v0 *= (1 - cost * turn)
                px = self.C.loc[days, held] if held != ["SPY"] else self.spy.loc[days].to_frame("SPY")
                rel = (px / px.iloc[0]).ffill().fillna(1.0)
                w = pd.Series(wd)[held]
                seg = (rel * w).sum(axis=1) * v0
                last = rel.iloc[-1] * w
                tot = float(last.sum())
                prev = {t: float(last[t]) / tot for t in held} if tot > 0 else {}
            vals.append(seg if not vals else seg.iloc[1:])
            v0 = float(seg.iloc[-1])
        return pd.concat(vals)


def voltarget(s: pd.Series, target=0.15) -> pd.Series:
    """Anteil Aktien = Ziel ÷ Schwankung der letzten 63 Tage (höchstens 100 %), monatlich angepasst, Rest Geld (0 %)."""
    r = s.pct_change().fillna(0)
    vol = r.rolling(63).std() * math.sqrt(252)
    w = (target / vol).clip(upper=1.0).resample("ME").last().reindex(r.index, method="ffill").shift(1).fillna(1.0)
    return (1 + w * r).cumprod()


def after_tax_w(eng: E2, path: list, start_val=10_000.0) -> float:
    """Wie R1.after_tax, aber mit Gewichten je Termin; liefert CAGR nach Steuer."""
    cash, units, basis, pot, gains_y, yr = start_val, {}, {}, 0.0, 0.0, None
    px_of = lambda t, d: (eng.spy.loc[d] if t == "SPY" else eng.C.at[d, t])
    last_px = lambda t, d: float(eng.spy.loc[:d].iloc[-1]) if t == "SPY" else float(eng.C[t].loc[:d].dropna().iloc[-1]) if eng.C[t].loc[:d].notna().any() else 0.0
    for k, (d, held, wd) in enumerate(path):
        if yr is not None and d.year != yr:
            tx = max(0.0, gains_y + pot); pot = min(0.0, gains_y + pot); cash -= tx * R1.TAX; gains_y = 0.0
        yr = d.year
        val = cash + sum(units[t] * (px_of(t, d) if pd.notna(px_of(t, d)) else last_px(t, d)) for t in units)
        for t in list(units):
            p = px_of(t, d); p = last_px(t, d) if pd.isna(p) else p
            tgt = (wd.get(t, 0) * val / p) if p > 0 else 0.0
            if units[t] > tgt + 1e-12:
                q = units[t] - tgt; pr = q * p * (1 - R1.COST); cb = basis[t] * q / units[t]
                gains_y += pr - cb; basis[t] -= cb; units[t] = tgt; cash += pr
                if units[t] <= 1e-12:
                    units.pop(t); basis.pop(t)
        for t in held:
            p = px_of(t, d)
            if pd.isna(p) or p <= 0:
                continue
            cur = units.get(t, 0.0); tgt = wd[t] * val / p
            if tgt > cur + 1e-12:
                sp = min(cash, (tgt - cur) * p); units[t] = cur + sp * (1 - R1.COST) / p; basis[t] = basis.get(t, 0.0) + sp; cash -= sp
    d = eng.idx[-1]
    fin = cash + sum(units[t] * last_px(t, d) for t in units)
    unreal = sum(units[t] * last_px(t, d) - basis[t] for t in units)
    fin -= max(0.0, gains_y + pot + unreal) * R1.TAX
    yrs = (d - path[0][0]).days / 365.25
    return (fin / start_val) ** (1 / yrs) - 1


def spy_after_tax(spy: pd.Series, a, b=None) -> float:
    s = spy.loc[a:b] if b else spy.loc[a:]
    g = float(s.iloc[-1] / s.iloc[0]); yrs = (s.index[-1] - s.index[0]).days / 365.25
    return (1 + (g - 1) * (1 - R1.TAX)) ** (1 / yrs) - 1


def boot(ms: pd.Series, mb: pd.Series, n=4000, seed=11) -> dict:
    rng = np.random.default_rng(seed); N = len(ms); B, H = 12, 120
    cg, md, beat = [], [], []
    for _ in range(n):
        st = rng.integers(0, N - B, H // B); ii = np.concatenate([np.arange(s, s + B) for s in st])
        va, vb = np.cumprod(1 + ms.values[ii]), np.cumprod(1 + mb.values[ii])
        cg.append(va[-1] ** .1 - 1); md.append(float((va / np.maximum.accumulate(va) - 1).min())); beat.append(va[-1] > vb[-1])
    return {"p10": round(float(np.percentile(cg, 10)), 4), "p50": round(float(np.percentile(cg, 50)), 4), "mdd_p10": round(float(np.percentile(md, 10)), 4), "beat": round(float(np.mean(beat)), 3)}


def analyze(px: Path, out: Path) -> None:
    D = pickle.load(open(px / "px.pkl", "rb"))
    close, vol = D["close"], D["vol"]
    eng = E2(close, vol, close["SPY"].dropna())
    snaps = D.get("snaps") or []
    today = set(D["today"]) & set(close.columns)
    cache = {}
    def pit(d):
        k = d.strftime("%Y-%m")
        if k not in cache:
            cache[k] = R1.members_at(snaps, d)
        return cache[k]
    unis = [("sp500pit", pit), ("today", lambda d: today)]
    spy = eng.spy
    C = [  # (Name, Familie, kind, n, hold, lb, trend, weight, mkt)
        ("App-Regel 12-1 Top10 P20", "A", "mom", 10, 20, 12, False, "eq", False),
        ("Mom 12-1 Top20 P40", "A", "mom", 20, 40, 12, False, "eq", False), ("Mom 12-1 Top30 P60", "A", "mom", 30, 60, 12, False, "eq", False),
        ("Mom 9-1 Top10 P20", "A", "mom", 10, 20, 9, False, "eq", False), ("Mom 9-1 Top20 P40", "A", "mom", 20, 40, 9, False, "eq", False),
        ("Mom 9-1 Top30 P60", "A", "mom", 30, 60, 9, False, "eq", False), ("Mom 6-1 Top20 P40", "A", "mom", 20, 40, 6, False, "eq", False),
        ("Mom 6-1 Top30 P60", "A", "mom", 30, 60, 6, False, "eq", False),
        ("Mom÷Schwankung Top20 P40", "B", "volmom", 20, 40, 12, False, "eq", False), ("Mom÷Schwankung Top30 P60", "B", "volmom", 30, 60, 12, False, "eq", False),
        ("Mehrfach-Mom Top20 P40", "C", "multi", 20, 40, 12, False, "eq", False), ("Mehrfach-Mom Top30 P60", "C", "multi", 30, 60, 12, False, "eq", False),
        ("52-W-Hoch Top20 P40", "D", "hi52", 20, 40, 12, False, "eq", False), ("52-W-Hoch Top30 P60", "D", "hi52", 30, 60, 12, False, "eq", False),
        ("Niedrige Schwankung Top50", "E", "lowvol", 50, 75, 12, False, "eq", False),
        ("Gleichgewichteter S&P 500", "F", "ew", 0, 0, 12, False, "eq", False),
    ]
    R = {"meta": {"learn": LEARN, "test": TEST}}
    for key, el in unis:
        print(f"\n######## Liste: {key} ########", flush=True)
        res, curves, paths = {}, {}, {}
        def run(c):
            nm, fam, kind, n, hold, lb, tr, w, mk = c
            p = eng.path2(kind, n, hold, lb, "2000-01-01", None, el, key, tr, w, mk)
            return p, eng.curve2(p)
        for c in C:
            p, s = run(c); paths[c[0]] = p; curves[c[0]] = s
        # beste Momentum-Variante (A–D) nur im Lernzeitraum
        lr = {nm: R1.stats(s.loc[LEARN[0]:LEARN[1]]) for nm, s in curves.items()}
        mom_names = [c[0] for c in C if c[1] in "ABCD"]
        best = max(mom_names, key=lambda nm: lr[nm]["sharpe"] or -9)
        bc = next(c for c in C if c[0] == best)
        print(f"  beste Momentum-Variante im Lernzeitraum: {best}", flush=True)
        # G/H: Schutzregeln und Gewichtung auf die beste Variante
        extra = [(best + " + Marktfilter", "G", bc[2], bc[3], bc[4], bc[5], False, "eq", True),
                 (best + " + Trendfilter je Aktie", "G", bc[2], bc[3], bc[4], bc[5], True, "eq", False),
                 (best + " · Gewicht nach Schwankung", "H", bc[2], bc[3], bc[4], bc[5], False, "iv", False)]
        for c in extra:
            p, s = run(c); paths[c[0]] = p; curves[c[0]] = s
        curves[best + " + Schwankungs-Steuerung 15 %"] = voltarget(curves[best]); paths[best + " + Schwankungs-Steuerung 15 %"] = None
        curves["S&P 500 (Index)"] = spy.loc[curves[best].index[0]:]; paths["S&P 500 (Index)"] = None
        # Mischungen der App-Regel und der besten Variante mit dem Index
        for base in ("App-Regel 12-1 Top10 P20", best, "Niedrige Schwankung Top50"):
            for w in (0.1, 0.2, 0.3, 0.5):
                nm = f"{int((1-w)*100)}/{int(w*100)} Index/{base}"
                curves[nm] = R1.mix(curves[base], spy.reindex(curves[base].index), w); paths[nm] = None
        print(f"\n  {'Strategie':50s} {'Lernen 2000–12':>34s}   {'Test 2013–26':>34s}   {'nach Steuer Test':>16s}", flush=True)
        rows = {}
        for nm, s in curves.items():
            L, T = R1.stats(s.loc[LEARN[0]:LEARN[1]]), R1.stats(s.loc[TEST[0]:])
            at = None
            if paths.get(nm):
                try:
                    pt = [x for x in paths[nm] if x[0] >= pd.Timestamp(TEST[0])]
                    at = round(after_tax_w(eng, pt), 4)
                except Exception as e:
                    at = None
            elif nm == "S&P 500 (Index)":
                at = round(spy_after_tax(spy, TEST[0]), 4)
            ms = s.loc[TEST[0]:].resample("ME").last().pct_change().dropna()
            mb = spy.reindex(s.index).loc[TEST[0]:].resample("ME").last().pct_change().reindex(ms.index).fillna(0)
            ms_all = s.resample("ME").last().pct_change().dropna(); mb_all = spy.reindex(s.index).resample("ME").last().pct_change().reindex(ms_all.index).fillna(0)
            rows[nm] = {"learn": L, "test": T, "full": R1.stats(s.loc["2000-01-01":]), "after_tax_test": at, "boot_full": boot(ms_all, mb_all)}
            f = lambda x: f"{x['cagr']*100:5.1f} % Sh {x['sharpe']:.2f} DD {x['mdd']*100:4.0f} %" if x else "–"
            print(f"  {nm:50s} {f(L):>34s}   {f(T):>34s}   {('%.1f %%' % (at*100)) if at is not None else '–':>16s}", flush=True)
        R[key] = {"best_momentum_learn": best, "rows": rows}
        # Rangliste nach Sharpe im Testzeitraum
        rk = sorted(rows.items(), key=lambda kv: -(kv[1]["test"].get("sharpe") or -9))
        print(f"\n  Rangliste Testzeitraum nach Sharpe ({key}):", flush=True)
        for nm, r in rk[:15]:
            b = r["boot_full"]
            print(f"   {r['test']['sharpe']:.2f}  {nm:50s} CAGR {r['test']['cagr']*100:5.1f} %  MaxDD {r['test']['mdd']*100:4.0f} %  · Bootstrap 10 J. (ganzer Zeitraum): Median {b['p50']*100:4.1f} %, schlechter Fall {b['p10']*100:5.1f} %, schlägt Index {b['beat']*100:3.0f} %", flush=True)
    out.write_text(json.dumps(R, ensure_ascii=False, indent=1, default=str))
    print("\nfertig →", out, flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--px", default="px"); ap.add_argument("--out", default="r2.json")
    a = ap.parse_args(); analyze(Path(a.px), Path(a.out))
