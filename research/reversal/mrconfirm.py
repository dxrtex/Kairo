"""Bestätigung der Mean-Reversion-Kandidaten auf unabhängigen Daten (vorab festgelegt 02.11.2026, vor dem ersten Lauf).

Warum: A5 und W2 wurden auf USA/Europa 2008–2026 gefunden und diese Daten dreimal ausgewertet. Echte Belege liefern nur
Daten, die diese Regeln nie gesehen haben:
  pre   USA/Europa 1999–2007 (Kurse aus dem Ultimate-Bestätigungslauf 40960444918)
  asia  Asien 2008–2026 (Universum des Live-Scanners, gleicher Lauf)

Überlebens-Verzerrung: Beide Universen sind von heute aus gewählt (nur Aktien, die es noch gibt). Das schönt jede
Kauf-Strategie. Darum zählt vor allem der Vergleich mit einer KONTROLLE, die denselben Fehler hat:
  CTRL    zufälliger Kauf an einem Tag über der 200-Tage-Linie, Ausstieg wie A5 (gleiche Haltedauer-Logik)
  CTRL-L  wie CTRL, aber mit demselben Kauf-Limit wie W2 (0,5 ATR unter dem Schluss) – trennt „Signal“ von „Limit kauft billiger“

Varianten (alle Kauf/Verkauf wie in research/reversal/mrc.py bzw. backend/mrshadow.py):
  A5        3 Verlust-Schlusskurse in Folge, Schluss über 200-Tage-Linie, Kurs ≥ 1, Ø Umsatz 20 T. ≥ 5 Mio. $ → Kauf zur
            nächsten Eröffnung, Verkauf zur Eröffnung nach dem ersten Schluss über der 5-Tage-Linie, spätestens Schluss Tag 10
  W2        A5 mit Kauf-Limit 0,5 ATR(14) unter dem Signal-Schluss, gilt nur am nächsten Tag
  W2-250    W2, aber nie eine Order unter 250 € (weniger Plätze statt Kleinstorders → keine 0,99-€-Gebührenfalle)
  W2-VH     W2, Verkauf zur Eröffnung nach dem ersten Schluss über dem Vortageshoch (max. 10 Tage)
  W2-BREITE W2, keine neuen Käufe, wenn weniger als 40 % der Aktien des Universums über ihrer 200-Tage-Linie liegen

Depot: 10.000 (Landeswährung = €), 5 Plätze, je Platz 1/5 des Depotwerts, Rangfolge niedrigster RSI(2) zuerst, keine Aktie
doppelt. Ein Limit reserviert den Platz (wie bei Scalable: das Geld ist gebunden) – nicht gefüllt = Platz bleibt leer.
Kosten je Seite 0 / 0,05 / 0,10 / 0,25 % plus 0,99 € je Order unter 250 € (Scalable PRIME+). Wechselkurse: keine
(Renditen je Aktie in Landeswährung); Umsatzfilter mit festen Näherungskursen.

Vorab festgelegte Entscheidung je Datensatz:
  W2 bestätigt, wenn (a) Ø Brutto je Trade W2 − CTRL-L > 0 mit einseitigem Block-Bootstrap (Monate) p < 0,05,
  (b) Netto je Trade mit 0,10 % je Seite > 0 und (c) Depot-Jahresrendite mit 0,10 % je Seite über dem CTRL-L-Depot.
  In beiden Datensätzen → „bestätigt“, in einem → „teilweise“, sonst „nicht bestätigt“.
  Gleiches für A5 gegen CTRL.
  Verbesserung (W2-250, W2-VH, W2-BREITE): Depot-Jahresrendite mit 0,10 % je Seite in BEIDEN Datensätzen über W2 und
  größter Rückgang höchstens 5 Prozentpunkte schlechter.

    python -m research.reversal.mrconfirm --px DIR --universe U.csv --set pre|asia --out OUT
    python -m research.reversal.mrconfirm report --dir DIR      → mrconfirm_report.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SETS = {"pre": ("1999-01-01", "2007-12-31"), "asia": ("2008-01-01", "2026-10-16")}
FX_USD = {"USD": 1, "EUR": 1.1, "GBp": 0.0127, "GBP": 1.27, "CHF": 1.1, "CAD": 0.74, "SEK": 0.095, "NOK": 0.095, "DKK": 0.147,
          "PLN": 0.25, "JPY": 0.0075, "CNY": 0.14, "INR": 0.012, "HKD": 0.128, "TWD": 0.031, "KRW": 0.00075, "AUD": 0.66,
          "IDR": 0.000064, "THB": 0.028, "MYR": 0.22, "SGD": 0.74, "NZD": 0.6}
COSTS = (0.0, 0.0005, 0.001, 0.0025)
FEE, FEE_LIMIT, CAP0, SLOTS = 0.99, 250.0, 10_000.0, 5
VARIANTS = ("A5", "W2", "W2-250", "W2-VH", "W2-BREITE", "CTRL", "CTRL-L")
SEED = 20261102


def rsi(c: pd.Series, n: int) -> pd.Series:
    d = c.diff()
    up, dn = d.clip(lower=0), (-d).clip(lower=0)
    ru, rd = up.ewm(alpha=1 / n, adjust=False).mean(), dn.ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + ru / rd.replace(0, np.nan))


def atr(h, l, c, n=14) -> pd.Series:
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def prep(x: pd.DataFrame, fx: float) -> pd.DataFrame:
    """Bereinigte Kerzen (Dividenden/Splits über AdjClose/Close) und Indikatoren – alles nur aus Daten bis zum jeweiligen Tag."""
    x = x.sort_index()
    x = x[~x.index.duplicated()].dropna(subset=["Open", "High", "Low", "Close"])
    f = (x["AdjClose"] / x["Close"]).where(lambda s: np.isfinite(s) & (s > 0)).ffill().fillna(1.0) if "AdjClose" in x else 1.0
    d = pd.DataFrame({k: x[k] * f for k in ("Open", "High", "Low", "Close")}, index=x.index)
    d["raw"] = x["Close"]
    d["adv"] = (x["Close"] * x["Volume"].fillna(0) * fx).rolling(20).mean()
    c = d["Close"]
    d["sma200"], d["sma5"] = c.rolling(200).mean(), c.rolling(5).mean()
    d["rsi2"], d["atr"] = rsi(c, 2), atr(d["High"], d["Low"], c)
    d["up"] = c > d["sma200"]
    d["down3"] = (c < c.shift(1)) & (c.shift(1) < c.shift(2)) & (c.shift(2) < c.shift(3))
    d["base"] = d["up"] & (d["raw"] >= 1) & (d["adv"] >= 5e6)
    return d


def arrays(d: pd.DataFrame) -> tuple:
    return tuple(d[k].to_numpy(float) for k in ("Open", "High", "Low", "Close", "sma5"))


def replay(A: tuple, i: int, lim: float | None, exit_rule: str) -> dict | None:
    """Trade ab Signal-Index i: Kauf Eröffnung i+1 (oder Limit), Verkauf nach Regel, spätestens Schluss Tag 10."""
    o, h, l, c, s5 = A
    n = len(c)
    if i + 1 >= n:
        return None
    k0 = i + 1
    e = o[k0]
    if lim is not None:
        if not l[k0] <= lim:
            return {"fill": False, "buy": k0}
        e = min(e, lim)
    if not (np.isfinite(e) and e > 0):
        return None
    for day, k in enumerate(range(k0, n), start=1):
        if day >= 10:
            return {"fill": True, "buy": k0, "sell": k, "e": e, "x": c[k], "days": day}
        hit = c[k] > s5[k] if exit_rule == "sma5" else (k > 0 and c[k] > h[k - 1])
        if hit:
            if k + 1 < n:
                return {"fill": True, "buy": k0, "sell": k + 1, "e": e, "x": o[k + 1], "days": day + 1}
            return None
    return None


def trades_for(d: pd.DataFrame, t: str, s0: pd.Timestamp, s1: pd.Timestamp, rng: np.random.Generator, p_ctrl: float) -> list[dict]:
    out = []
    idx = d.index
    ok = (idx >= s0) & (idx <= s1)
    sig = (d["base"] & d["down3"]).to_numpy() & ok
    ctrl = d["base"].to_numpy() & ok & (rng.random(len(d)) < p_ctrl)
    close, a = d["Close"].to_numpy(float), d["atr"].to_numpy(float)
    r2 = d["rsi2"].to_numpy(float)
    A = arrays(d)
    for i in np.flatnonzero(sig | ctrl):
        lim = close[i] - 0.5 * a[i] if np.isfinite(a[i]) else None
        jobs = []
        if sig[i]:
            jobs += [("A5", None, "sma5"), ("W2", lim, "sma5"), ("W2-VH", lim, "vh")]
        if ctrl[i]:
            jobs += [("CTRL", None, "sma5"), ("CTRL-L", lim, "sma5")]
        for v, lm, ex in jobs:
            if v.startswith("W2") and lm is None:
                continue
            r = replay(A, i, lm, ex)
            if r is None:
                continue
            r.update(v=v, t=t, sig=idx[i], rk=float(r2[i]) if v.startswith(("A5", "W2")) else float(rng.random()),
                     buy_d=idx[r["buy"]])
            if r["fill"]:
                r["sell_d"] = idx[r["sell"]]
            out.append(r)
    return out


def breadth(px: dict[str, pd.DataFrame]) -> pd.Series:
    up = pd.concat({t: d["up"].where(d["sma200"].notna()) for t, d in px.items()}, axis=1)
    return up.mean(axis=1)


def portfolio(tr: pd.DataFrame, closes: pd.DataFrame, cost: float, min_order: bool = False,
              block: pd.Series | None = None) -> pd.Series:
    """Tägliches Depot: zuerst Verkäufe zur Eröffnung, dann Käufe zur Eröffnung (Signale vom Vortag), Bewertung zum Schluss."""
    dates = closes.index
    cash, pos = CAP0, {}                                   # t → (Stück, Verkaufstag, Verkaufskurs)
    eq = []
    by_buy = {d: g.sort_values("rk") for d, g in tr.groupby("buy_d")} if len(tr) else {}
    last = CAP0
    for d in dates:
        for t in [t for t, p in pos.items() if p[1] == d]:
            sh, _, x = pos.pop(t)
            val = sh * x
            cash += val * (1 - cost) - (FEE if val < FEE_LIMIT else 0)
        g = by_buy.get(d)
        if g is not None and not (block is not None and block.get(g["sig"].iloc[0], 1.0) < 0.40):
            slots = SLOTS
            if min_order:
                slots = int(max(1, min(SLOTS, last // FEE_LIMIT)))
            free = slots - len(pos)
            size = last / slots
            for _, r in g.iterrows():
                if free <= 0:
                    break
                if r["t"] in pos:
                    continue
                free -= 1                                  # Limit reserviert den Platz, auch wenn es nicht gefüllt wird
                if not r["fill"]:
                    continue
                val = min(size, cash)
                fee = FEE if val < FEE_LIMIT else 0
                if val - fee <= 0:
                    continue
                sh = (val - fee) / (r["e"] * (1 + cost))
                cash -= val
                pos[r["t"]] = (sh, r["sell_d"], r["x"])
        mv = 0.0
        for t, (sh, _, _) in pos.items():
            px = closes.at[d, t] if t in closes.columns else np.nan
            mv += sh * (px if np.isfinite(px) else 0)
        last = cash + mv
        eq.append(last)
    return pd.Series(eq, index=dates)


def stats(eq: pd.Series) -> dict:
    eq = eq[eq > 0]
    if len(eq) < 30:
        return {"cagr": None, "dd": None}
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    return {"cagr": round(float((eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1), 4),
            "dd": round(float((eq / eq.cummax() - 1).min()), 4)}


def boot_p(a: pd.DataFrame, b: pd.DataFrame, n=2000, seed=SEED) -> tuple[float, float]:
    """Einseitig: Ø Brutto(a) − Ø Brutto(b) > 0? Monatsblöcke, beide Gruppen gemeinsam gezogen."""
    ma = a.groupby(a["sig"].dt.to_period("M"))["g"].agg(["sum", "count"])
    mb = b.groupby(b["sig"].dt.to_period("M"))["g"].agg(["sum", "count"])
    m = ma.join(mb, lsuffix="_a", rsuffix="_b", how="outer").fillna(0)
    diff = m["sum_a"].sum() / m["count_a"].sum() - m["sum_b"].sum() / m["count_b"].sum()
    rng = np.random.default_rng(seed)
    arr = m.to_numpy(float)
    cnt = 0
    for _ in range(n):
        s = arr[rng.integers(0, len(arr), len(arr))]
        da = s[:, 0].sum() / max(s[:, 1].sum(), 1)
        db = s[:, 2].sum() / max(s[:, 3].sum(), 1)
        cnt += (da - db) - diff >= diff               # Verschiebungs-Bootstrap: Nullhypothese Δ = 0
    return float(diff), float((cnt + 1) / (n + 1))


def run(a) -> None:
    s0, s1 = (pd.Timestamp(x) for x in SETS[a.set])
    uni = pd.read_csv(a.universe)
    cur = dict(zip(uni["ticker"], uni["currency"].fillna("USD")))
    files = sorted(Path(a.px).glob(f"px_{a.set}_*.parquet")) or sorted(Path(a.px).glob("*.parquet"))
    raw = pd.concat([pd.read_parquet(f) for f in files])
    raw["date"] = pd.to_datetime(raw["date"])
    px = {}
    for t, g in raw.groupby("ticker"):
        fx = FX_USD.get(cur.get(t, "USD"))
        if fx is None:
            continue
        d = prep(g.set_index("date"), fx)
        if len(d) >= 260:
            px[t] = d
    print(f"{a.set}: {len(px)} Aktien", flush=True)
    rng = np.random.default_rng(SEED)
    n_sig = sum(int(((d["base"] & d["down3"]) & (d.index >= s0) & (d.index <= s1)).sum()) for d in px.values())
    n_base = sum(int((d["base"] & (d.index >= s0) & (d.index <= s1)).sum()) for d in px.values())
    p_ctrl = min(1.0, n_sig / max(n_base, 1))                # Kontrolle so häufig wie das Signal
    tr = []
    for t, d in px.items():
        tr += trades_for(d, t, s0, s1, rng, p_ctrl)
    T = pd.DataFrame(tr)
    T["g"] = np.where(T["fill"], T.get("x", np.nan) / T.get("e", np.nan) - 1, np.nan)
    print(f"{len(T)} Kandidaten, Kontrolle p {p_ctrl:.3f}", flush=True)
    closes = pd.DataFrame({t: d["Close"] for t, d in px.items()})
    closes = closes.ffill()[(closes.index >= s0) & (closes.index <= s1 + pd.Timedelta(days=30))]
    br = breadth(px)
    res = {"set": a.set, "n_stocks": len(px), "p_ctrl": p_ctrl, "trade": {}, "depot": {}}
    for v in VARIANTS:
        src = "W2" if v in ("W2-250", "W2-BREITE") else v
        x = T[(T["v"] == src)]
        f = x[x["fill"]]
        res["trade"][v] = {"signals": int(len(x)), "filled": int(len(f)),
                           "fill_rate": round(len(f) / len(x), 3) if len(x) else None,
                           "gross": round(float(f["g"].mean()), 5) if len(f) else None,
                           "days": round(float(f["days"].mean()), 2) if len(f) else None,
                           **{f"net_{c}": round(float(((f["x"] * (1 - c)) / (f["e"] * (1 + c)) - 1).mean()), 5) if len(f) else None
                              for c in COSTS}}
        dep = {}
        for c in COSTS:
            eq = portfolio(x, closes, c, min_order=(v == "W2-250"), block=br if v == "W2-BREITE" else None)
            dep[str(c)] = stats(eq)
            if c == 0.001:
                half = eq.index[len(eq) // 2]
                dep["h1"], dep["h2"] = stats(eq[eq.index <= half]), stats(eq[eq.index > half])
        res["depot"][v] = dep
        print(v, res["trade"][v], dep.get("0.001"), flush=True)
    ew = closes.pct_change(fill_method=None).clip(-0.9, 2).mean(axis=1).fillna(0)
    res["ew_universe"] = stats((1 + ew).cumprod() * CAP0)
    for v, c in (("W2", "CTRL-L"), ("A5", "CTRL"), ("W2", "A5")):
        A = T[(T["v"] == v) & T["fill"]]
        B = T[(T["v"] == c) & T["fill"]]
        res.setdefault("boot", {})[f"{v}-{c}"] = boot_p(A, B) if len(A) and len(B) else None
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / f"mrconfirm_{a.set}.json").write_text(json.dumps(res, indent=1, default=str))


def P(x):
    return "–" if x is None else f"{x * 100:+.1f} %"


def report(d: Path) -> None:
    R = {s: json.loads((d / f"mrconfirm_{s}.json").read_text()) for s in SETS if (d / f"mrconfirm_{s}.json").exists()}
    L = ["# Mean Reversion – Bestätigung auf unabhängigen Daten", "",
         "Vorab festgelegt 02.11.2026 (research/reversal/mrconfirm.py). Vorzeit = USA/Europa 1999–2007, Asien = 2008–2026.",
         "Beide Universen sind von heute aus gewählt → alle Kauf-Strategien sehen zu gut aus; maßgeblich ist der Abstand zur Kontrolle.", ""]
    for s, r in R.items():
        L += [f"## {'Vorzeit 1999–2007' if s == 'pre' else 'Asien 2008–2026'} ({r['n_stocks']} Aktien)", "",
              "| Variante | Signale | gefüllt | Brutto je Trade | netto 0,05 % | netto 0,10 % | netto 0,25 % | Ø Tage | Depot 0,10 %: Rendite p. a. (Rückgang) | 1. / 2. Hälfte | Depot 0,25 % |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for v in VARIANTS:
            t, dp = r["trade"][v], r["depot"][v]
            m = dp.get("0.001", {})
            L.append(f"| {v} | {t['signals']} | {t['fill_rate'] if t['fill_rate'] is not None else '–'} | {P(t['gross'])} | "
                     f"{P(t['net_0.0005'])} | {P(t['net_0.001'])} | {P(t['net_0.0025'])} | {t['days'] or '–'} | "
                     f"{P(m.get('cagr'))} ({P(m.get('dd'))}) | {P(dp.get('h1', {}).get('cagr'))} / {P(dp.get('h2', {}).get('cagr'))} | "
                     f"{P(dp.get('0.0025', {}).get('cagr'))} |")
        L += ["", f"Gleichgewichtetes Universum (kaufen und halten, ohne Kosten): {P(r['ew_universe']['cagr'])} p. a., "
              f"Rückgang {P(r['ew_universe']['dd'])}", ""]
        for k, b in (r.get("boot") or {}).items():
            if b:
                L.append(f"- Brutto je Trade {k}: Δ {b[0] * 100:+.2f} Prozentpunkte, Bootstrap p {b[1]:.3f}")
        L.append("")
    L += ["## Entscheidung (vorab festgelegt)", ""]
    def ok(r, v, c):
        b = (r.get("boot") or {}).get(f"{v}-{c}")
        t, dv, dc = r["trade"][v], r["depot"][v].get("0.001", {}), r["depot"][c].get("0.001", {})
        return bool(b and b[0] > 0 and b[1] < 0.05 and (t["net_0.001"] or -1) > 0
                    and (dv.get("cagr") or -9) > (dc.get("cagr") or -9))
    for v, c in (("W2", "CTRL-L"), ("A5", "CTRL")):
        n = sum(ok(r, v, c) for r in R.values())
        L.append(f"- **{v}** gegen {c}: {'bestätigt' if n == len(R) == 2 else 'teilweise bestätigt' if n else 'nicht bestätigt'} "
                 f"({', '.join(f'{s}: ' + ('ja' if ok(r, v, c) else 'nein') for s, r in R.items())})")
    for v in ("W2-250", "W2-VH", "W2-BREITE"):
        good = []
        for r in R.values():
            a_, b_ = r["depot"][v].get("0.001", {}), r["depot"]["W2"].get("0.001", {})
            good.append(a_.get("cagr") is not None and b_.get("cagr") is not None and a_["cagr"] > b_["cagr"]
                        and a_["dd"] >= b_["dd"] - 0.05)
        L.append(f"- **{v}** besser als W2: {'ja' if len(good) == 2 and all(good) else 'nein'} ({good})")
    (d / "mrconfirm_report.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "report":
        ap = argparse.ArgumentParser(); ap.add_argument("cmd"); ap.add_argument("--dir", required=True)
        report(Path(ap.parse_args(argv).dir)); return 0
    ap = argparse.ArgumentParser()
    ap.add_argument("--px", required=True); ap.add_argument("--universe", required=True)
    ap.add_argument("--set", choices=list(SETS), required=True); ap.add_argument("--out", required=True)
    run(ap.parse_args(argv)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
