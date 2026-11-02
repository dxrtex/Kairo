"""RSI-Signallinien-Muster (Idee Jonny, 02.11.2026) – vorab festgelegt, vor dem ersten Lauf.

Beobachtung: Nach starkem Abverkauf schießt der RSI über seine Signallinie (erster Impuls) und setzt dann auf die
Signallinie zurück – oder es bildet sich eine bullische Divergenz. Danach steigt der Kurs.

Definitionen (Tageskerzen, bereinigt; RSI 14 nach Wilder, Signallinie = 14-Tage-Durchschnitt des RSI wie TradingView):
  Abverkauf   RSI < 30 innerhalb der letzten 20 Tage
  R2 IMPULS   erster Kreuzungstag des RSI über die Signallinie nach dem Abverkauf (≤ 20 Tage nach dem letzten RSI < 30)
  R1 RÜCKSETZER  nach dem Impuls kommt der RSI binnen 10 Tagen auf die Signallinie zurück (Abstand ≤ 1,5 Punkte) und
              dreht wieder nach oben, ohne sie deutlich zu brechen (RSI ≥ Signallinie − 1,5) → Signal am Dreh-Tag
              (das Muster aus Jonnys Chart). Bricht der RSI mehr als 3 Punkte unter die Linie: Muster gescheitert.
  R3 DIVERGENZ  Kurs schließt 5–30 Tage nach dem Abverkaufs-Tief unter dessen Schlusskurs, der RSI liegt dabei
              mindestens 3 Punkte über seinem damaligen Tief; Signal, sobald der RSI danach (≤ 10 Tage) über die
              Signallinie kreuzt
  Kombinationen (je für R1 und R3): +TREND über der 200-Tage-Linie · +UNTER unter der 200-Tage-Linie ·
              +VOL Kapitulations-Volumen (in den letzten 10 Tagen ein Tag mit ≥ 2× Ø-Volumen 20 Tage) ·
              +BREIT Marktbreite > 50 % der Aktien über ihrer 200-Tage-Linie
  Referenz    A5 (3 Verlusttage über der 200-Tage-Linie) – das Signal hinter W2
Grundfilter wie Scanner: Kurs ≥ 1, Ø Tagesumsatz 20 Tage ≥ 5 Mio. $.

Messung: Kauf zur Eröffnung am Tag nach dem Signal, Rendite bis zum Schluss nach 5 / 10 / 20 Handelstagen (Hauptmaß 10).
Kontrollen mit gleichem Zufalls-Anteil:
  K-ABV   zufälliger Tag NACH einem Abverkauf (RSI < 30 in den letzten 20 Tagen) – trennt das Muster vom bloßen
          „nach einem Abverkauf kaufen“
  K       zufälliger Tag
Datensätze: USA/Europa 2008–2026 (Train 2008–16, Validierung 2017–21, Holdout 2022–26), Vorzeit 1999–2007, Asien 2008–26.

Vorab festgelegte Entscheidung: Eine Variante BESTEHT, wenn ihr Ø 10-Tage-Ertrag in ALLEN fünf Prüfungen (Train,
Validierung, Holdout, Vorzeit, Asien) über K-ABV liegt, mit einseitigem Block-Bootstrap (Monate) p < 0,05 nach
Benjamini-Hochberg über alle Varianten × Prüfungen, und netto (0,10 % je Seite) positiv ist. Sonst: „Hinweis“ (in ≥ 3
Prüfungen besser) oder „nicht bestanden“. Zum Vergleich: Depot (5 Plätze, 10 Tage halten) gegen W2-Signal A5.

    python -m research.reversal.rsisig --px DIR --universe U.csv --set main|pre|asia --out OUT
    python -m research.reversal.rsisig report --dir DIR
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from .mrconfirm import CAP0, FX_USD, boot_p, breadth, portfolio, prep, rsi, stats

SETS = {"main": ("2008-01-01", "2026-10-16"), "pre": ("1999-01-01", "2007-12-31"), "asia": ("2008-01-01", "2026-10-16")}
PERIODS = {"train": ("2008-01-01", "2016-12-31"), "val": ("2017-01-01", "2021-12-31"), "hold": ("2022-01-01", "2026-10-16")}
H = (5, 10, 20)
SEED = 20261102
BASE = ("R1", "R2", "R3")
COMBOS = ("TREND", "UNTER", "VOL", "BREIT")
VARIANTS = BASE + tuple(f"{b}+{c}" for b in ("R1", "R3") for c in COMBOS) + ("A5", "K-ABV", "K")


def events(d: pd.DataFrame) -> dict[str, np.ndarray]:
    """Zustandsautomat je Aktie – nur Daten bis zum jeweiligen Tag."""
    c = d["Close"].to_numpy(float)
    r = rsi(d["Close"], 14).to_numpy(float)
    s = pd.Series(r).rolling(14).mean().to_numpy(float)
    n = len(c)
    R1, R2, R3 = (np.zeros(n, bool) for _ in range(3))
    last_os, os_low_i = -999, -1
    state, t_cross, retested = 0, -1, False
    div_armed, div_i = False, -1
    for i in range(1, n):
        if not (np.isfinite(r[i]) and np.isfinite(s[i]) and np.isfinite(s[i - 1])):
            continue
        if r[i] < 30:
            if i - last_os > 20 or os_low_i < 0:      # neue Abverkaufs-Phase
                os_low_i = i
            elif c[i] < c[os_low_i]:
                os_low_i = i
            last_os = i
            state, div_armed = 1, False
        cross = r[i] > s[i] and r[i - 1] <= s[i - 1]
        # R2 / R1
        if state == 1 and i - last_os <= 20 and cross:
            R2[i] = True
            state, t_cross, retested = 2, i, False
        elif state == 2:
            if i - t_cross > 10 or r[i] < s[i] - 3:
                state = 0
            else:
                if r[i] - s[i] <= 1.5:
                    retested = True
                if retested and r[i] > r[i - 1] and r[i] >= s[i] - 1.5 and i > t_cross:
                    R1[i] = True
                    state = 0
        if state == 1 and i - last_os > 20:
            state = 0
        # R3 Divergenz: neues Kurs-Tief 5–30 Tage nach dem Abverkaufs-Tief, RSI höher
        if os_low_i >= 0 and 5 <= i - os_low_i <= 30 and r[i] >= 30 and c[i] < c[os_low_i] and r[i] >= r[os_low_i] + 3:
            div_armed, div_i = True, i
        if div_armed:
            if i - div_i > 10:
                div_armed = False
            elif cross:
                R3[i] = True
                div_armed = False
    return {"R1": R1, "R2": R2, "R3": R3, "os": pd.Series(r).rolling(20, min_periods=1).min().lt(30).to_numpy()}


def fwd(d: pd.DataFrame, idx: np.ndarray) -> dict[int, np.ndarray]:
    o, c = d["Open"].to_numpy(float), d["Close"].to_numpy(float)
    out = {}
    for h in H:
        g = np.full(len(idx), np.nan)
        ok = idx + h < len(c)
        e = o[idx[ok] + 1]
        g[ok] = c[idx[ok] + h] / e - 1
        out[h] = g
    return out


def collect(px: dict, s0, s1, br: pd.Series, rng) -> pd.DataFrame:
    rows = []
    n_sig = 0
    cache = {}
    for t, d in px.items():
        ev = events(d)
        idx = d.index
        ok = (idx >= s0) & (idx <= s1) & d["base"].to_numpy()
        up = d["up"].to_numpy()
        vol = d.get("vr")
        cap = (d["vr"].rolling(10, min_periods=1).max() >= 2).to_numpy() if vol is not None else np.zeros(len(d), bool)
        b = br.reindex(idx).to_numpy() > 0.5
        flags = {"R1": ev["R1"], "R2": ev["R2"], "R3": ev["R3"], "A5": (d["up"] & d["down3"]).to_numpy()}
        for base in ("R1", "R3"):
            flags[f"{base}+TREND"] = ev[base] & up
            flags[f"{base}+UNTER"] = ev[base] & ~up & d["sma200"].notna().to_numpy()
            flags[f"{base}+VOL"] = ev[base] & cap
            flags[f"{base}+BREIT"] = ev[base] & b
        cache[t] = (ev, ok, flags)
        n_sig += int((ev["R1"] & ok).sum())
    n_os = sum(int((v[0]["os"] & v[1]).sum()) for v in cache.values())
    n_all = sum(int(v[1].sum()) for v in cache.values())
    p_os, p_all = min(1, 3 * n_sig / max(n_os, 1)), min(1, 3 * n_sig / max(n_all, 1))
    for t, d in px.items():
        ev, ok, flags = cache[t]
        flags["K-ABV"] = ev["os"] & (rng.random(len(d)) < p_os)
        flags["K"] = rng.random(len(d)) < p_all
        r14 = rsi(d["Close"], 14).to_numpy(float)
        for v, f in flags.items():
            ii = np.flatnonzero(f & ok)
            ii = ii[ii + 1 < len(d)]
            if not len(ii):
                continue
            g = fwd(d, ii)
            for k, i in enumerate(ii):
                rows.append((v, t, d.index[i], d.index[i + 1], float(r14[i]), *(g[h][k] for h in H)))
    T = pd.DataFrame(rows, columns=["v", "t", "sig", "buy_d", "rk", *[f"g{h}" for h in H]])
    return T


def run(a) -> None:
    s0, s1 = (pd.Timestamp(x) for x in SETS[a.set])
    uni = pd.read_csv(a.universe)
    cur = dict(zip(uni["ticker"], uni["currency"].fillna("USD")))
    p = Path(a.px)
    files = [p / "prices_v1.parquet"] if (p / "prices_v1.parquet").exists() else sorted(p.glob("px_*.parquet"))
    raw = pd.concat([pd.read_parquet(f) for f in files])
    raw["date"] = pd.to_datetime(raw["date"])
    px = {}
    for t, g in raw.groupby("ticker"):
        fx = FX_USD.get(cur.get(t, "USD"))
        if fx is None:
            continue
        x = g.set_index("date")
        d = prep(x, fx)
        if len(d) >= 260:
            v = x["Volume"].reindex(d.index).astype(float)
            d["vr"] = v / v.rolling(20).mean()
            px[t] = d
    print(f"{a.set}: {len(px)} Aktien", flush=True)
    br = breadth(px)
    T = collect(px, s0, s1, br, np.random.default_rng(SEED))
    print(T.groupby("v").size().to_string(), flush=True)
    parts = {"all": (s0, s1)} if a.set != "main" else {k: (pd.Timestamp(x), pd.Timestamp(y)) for k, (x, y) in PERIODS.items()}
    res = {"set": a.set, "n_stocks": len(px), "parts": {}}
    closes = pd.DataFrame({t: d["Close"] for t, d in px.items()}).ffill()
    for name, (a0, a1) in parts.items():
        X = T[(T["sig"] >= a0) & (T["sig"] <= a1)]
        P = {}
        ctrl = X[X["v"] == "K-ABV"].dropna(subset=["g10"]).rename(columns={"g10": "g"})
        for v in VARIANTS:
            x = X[X["v"] == v].dropna(subset=["g10"])
            if not len(x):
                P[v] = {"n": 0}
                continue
            row = {"n": int(len(x)), **{f"g{h}": round(float(x[f"g{h}"].mean()), 5) for h in H},
                   "win10": round(float((x["g10"] > 0).mean()), 3),
                   "net10": round(float(((1 + x["g10"]) * (1 - 0.001) / (1 + 0.001) - 1).mean()), 5)}
            if v != "K-ABV" and len(ctrl):
                dlt, pv = boot_p(x.rename(columns={"g10": "g"}), ctrl)
                row.update(d_ctrl=round(dlt, 5), p=round(pv, 4))
            P[v] = row
        res["parts"][name] = P
    # Depot zum Vergleich (gesamter Zeitraum, 5 Plätze, 10 Tage halten, 0,10 % je Seite)
    dep = {}
    cl = closes[(closes.index >= s0) & (closes.index <= s1 + pd.Timedelta(days=40))]
    for v in ("R1", "R2", "R3", "R1+TREND", "R3+TREND", "A5", "K-ABV"):
        x = T[(T["v"] == v)].dropna(subset=["g10"]).copy()
        if not len(x):
            continue
        pos = {t: d.index for t, d in px.items()}
        x["sell_d"] = [pos[t][min(pos[t].get_loc(b) + 9, len(pos[t]) - 1)] for t, b in zip(x["t"], x["buy_d"])]
        x["e"] = [float(px[t].at[b, "Open"]) for t, b in zip(x["t"], x["buy_d"])]
        x["x"] = [float(px[t].at[sd, "Close"]) for t, sd in zip(x["t"], x["sell_d"])]
        x["fill"] = True
        dep[v] = stats(portfolio(x, cl, 0.001))
    res["depot"] = dep
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / f"rsisig_{a.set}.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res["parts"], default=str)[:3000])


def report(d: Path) -> None:
    R = {s: json.loads((d / f"rsisig_{s}.json").read_text()) for s in SETS if (d / f"rsisig_{s}.json").exists()}
    checks = []                                      # (Variante, Prüfung, Δ, p)
    for s, r in R.items():
        for part, P in r["parts"].items():
            label = {"train": "Train 08–16", "val": "Validierung 17–21", "hold": "Holdout 22–26"}.get(part, {"pre": "Vorzeit 99–07", "asia": "Asien 08–26"}.get(s, s))
            for v, x in P.items():
                if v not in ("K-ABV", "K") and "p" in x:
                    checks.append([v, label, x["d_ctrl"], x["p"], x.get("net10")])
    ps = sorted(range(len(checks)), key=lambda i: checks[i][3])
    m, prev = len(ps), 1.0
    q = [1.0] * m
    for rank in range(m, 0, -1):
        i = ps[rank - 1]
        prev = min(prev, checks[i][3] * m / rank)
        q[i] = prev
    for i, c in enumerate(checks):
        c.append(q[i])
    L = ["# RSI-Signallinie: Impuls, Rücksetzer, Divergenz – Ergebnis", "",
         "Vorab festgelegt 02.11.2026 (research/reversal/rsisig.py). Hauptmaß: Ø Ertrag 10 Handelstage ab Kauf zur Eröffnung,",
         "verglichen mit einem zufälligen Kauf NACH einem Abverkauf (K-ABV). Benjamini-Hochberg über alle Prüfungen.", ""]
    for s, r in R.items():
        for part, P in r["parts"].items():
            L += [f"## {s} · {part} ({r['n_stocks']} Aktien)", "",
                  "| Variante | Signale | 5 T. | 10 T. | 20 T. | im Plus (10 T.) | netto 10 T. | Δ gegen K-ABV | p |", "|---|---|---|---|---|---|---|---|---|"]
            for v in VARIANTS:
                x = P.get(v, {})
                if not x.get("n"):
                    continue
                f = lambda k: f"{x[k] * 100:+.2f} %" if x.get(k) is not None else "–"
                dc = "{:+.2f} Pkt.".format(x["d_ctrl"] * 100) if "d_ctrl" in x else "–"
                L.append(f"| {v} | {x['n']} | {f('g5')} | {f('g10')} | {f('g20')} | {x['win10'] * 100:.0f} % | {f('net10')} | "
                         f"{dc} | {x.get('p', '–')} |")
            L.append("")
        if r.get("depot"):
            L += [f"Depot {s} (5 Plätze, 10 Tage, 0,10 % je Seite): " + " · ".join(
                f"{v} {st['cagr'] * 100:+.1f} % p. a. (Rückgang {st['dd'] * 100:.0f} %)" for v, st in r["depot"].items() if st.get("cagr") is not None), ""]
    L += ["## Entscheidung (vorab festgelegt)", ""]
    for v in VARIANTS:
        if v in ("K-ABV", "K"):
            continue
        cs = [c for c in checks if c[0] == v]
        if not cs:
            continue
        good = [c for c in cs if c[2] > 0 and c[5] < 0.05 and (c[4] or -1) > 0]
        better = [c for c in cs if c[2] > 0]
        verdict = ("BESTANDEN" if len(good) == len(cs) == 5 else "Hinweis" if len(better) >= 3 else "nicht bestanden")
        L.append(f"- **{v}**: {verdict} – besser als K-ABV in {len(better)}/{len(cs)} Prüfungen, davon signifikant {len(good)} "
                 f"({', '.join(f'{c[1]} {c[2] * 100:+.2f}' for c in cs)})")
    (d / "rsisig_report.md").write_text("\n".join(L) + "\n")
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
