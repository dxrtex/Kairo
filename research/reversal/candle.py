"""Bullische Kerzen- und Chartformationen (Idee Jonny, 02.11.2026) – vorab festgelegt, vor dem ersten Lauf.

Frage A: Sind B60-Setups besser, wenn sich während der Bodenbildung (10 Handelstage vor dem Treffer bis zum Tag vor dem
         Kauf – nur Daten, die beim Kauf bekannt sind) eine bullische Formation gebildet hat?
Frage B: Sind die Formationen allein ein Kaufsignal nach einem Abverkauf – besser als ein zufälliger Kauf danach?

Formationen (Tageskerzen, bereinigt; „im Abwärtsdruck“ = Schluss des Vortags unter dem Schluss von vor 5 Tagen):
  ENGULF   Bullish Engulfing: rote Vortageskerze, grüne Kerze eröffnet ≤ Vortagesschluss und schließt ≥ Vortageseröffnung
  HAMMER   Hammer: unterer Docht ≥ 60 % der Spanne, oberer Docht ≤ 15 %, Spanne > 0
  PIERCE   Piercing Line: große rote Vortageskerze (Körper ≥ 60 % der Spanne), Eröffnung unter deren Schluss, Schluss über
           der Körpermitte, aber unter der Vortageseröffnung
  HARAMI   Bullish Harami: große rote Vortageskerze, grüner Körper liegt vollständig in deren Körper
  MSTAR    Morning Star: große rote Kerze, dann kleiner Körper (≤ 30 % davon) unter ihrem Schluss, dann grüne Kerze mit
           Schluss über der Körpermitte der roten
  SOLDIERS Three White Soldiers: drei grüne Kerzen, steigende Schlüsse, jede eröffnet im Körper der vorigen, Körper ≥ 50 %
           der Spanne, nach Rückgang (Schluss vor 3 Tagen unter dem vor 8 Tagen)
  KERZE    irgendeine der sechs Kerzenformationen
  WBODEN   Doppelboden: Tief der letzten 10 Tage innerhalb ± 3 % des Tiefs von Tag −40…−11, dazwischen ein Hoch ≥ 5 % darüber
           (Frage B: Signal erst beim Schluss über diesem Zwischenhoch = Nackenlinie)
  CUP      Cup with Handle: Hoch (Tag −150…−25), Tasse 12–40 % tief, Rand wieder ≥ 95 % des Hochs, Henkel 5–20 Tage mit
           Rücksetzer ≤ 12 % (Frage B: Signal beim Schluss über dem Henkel-Hoch = Ausbruch)
  Kerzenformationen zählen nur im Abwärtsdruck (dort sind sie als Umkehrsignal gemeint).

Messung A: R je B60-Trade mit Stress-Kosten (13.241 Trades 2008–26, korrigierte Engine), mit/ohne Formation.
Messung B: Ertrag 10 Handelstage ab Kauf zur Eröffnung nach dem Signal; Kontrolle K-ABV = zufälliger Tag nach Abverkauf
  (RSI(14) < 30 in den letzten 20 Tagen), für CUP zusätzlich K-TREND = zufälliger Tag über der 200-Tage-Linie.
  Kerzen in B nur nach Abverkauf (RSI(14) < 30 in den letzten 20 Tagen), wie bei der RSI-Prüfung.

Entscheidung (vorab festgelegt):
  A: Verstärker, wenn Ø-R mit Formation in Train, Validierung UND Holdout je ≥ 0,05 R über ohne liegt und der Welch-Test
     gesamt nach Benjamini-Hochberg q ≤ 0,10 ergibt. Nächster Schritt wäre ein Depot-Test – keine Regeländerung.
  B: besteht, wenn in Train, Validierung, Holdout (USA/Europa), Vorzeit und Asien jeweils besser als die Kontrolle,
     Bootstrap p < 0,05 nach Benjamini-Hochberg, netto (0,10 % je Seite) positiv.

    python -m research.reversal.candle a --data v1 --signals sig.parquet --sec sec --out OUT
    python -m research.reversal.candle b --px DIR --universe U.csv --set main|pre|asia --out OUT
    python -m research.reversal.candle report --dir DIR
"""
from __future__ import annotations

import argparse
import json
import sys
from math import erf, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

PAT = ("ENGULF", "HAMMER", "PIERCE", "HARAMI", "MSTAR", "SOLDIERS")
ALL = PAT + ("KERZE", "WBODEN", "CUP")
AB = ("Train", "Validierung", "Holdout")
PERIODS = {"Train": ("2008-01-01", "2016-12-31"), "Validierung": ("2017-01-01", "2021-12-31"), "Holdout": ("2022-01-01", "2026-10-16")}
SEED = 20261102


def candles(o, h, l, c) -> dict[str, np.ndarray]:
    """Kerzenformationen je Tag (nur Daten bis einschließlich des Tages)."""
    n = len(c)
    sh = lambda x, k: np.r_[np.full(k, np.nan), x[:-k]] if k else x
    body, rng_ = np.abs(c - o), h - l
    green, red = c > o, c < o
    o1, c1, h1, l1 = sh(o, 1), sh(c, 1), sh(h, 1), sh(l, 1)
    body1, rng1 = np.abs(c1 - o1), h1 - l1
    red1 = c1 < o1
    big_red1 = red1 & (body1 >= 0.6 * rng1) & (rng1 > 0)
    down = sh(c, 1) < sh(c, 6)
    with np.errstate(invalid="ignore", divide="ignore"):
        lower, upper = np.minimum(o, c) - l, h - np.maximum(o, c)
        out = {
            "ENGULF": red1 & green & (o <= c1) & (c >= o1),
            "HAMMER": (rng_ > 0) & (lower >= 0.6 * rng_) & (upper <= 0.15 * rng_),
            "PIERCE": big_red1 & green & (o < c1) & (c > (o1 + c1) / 2) & (c < o1),
            "HARAMI": big_red1 & green & (o > c1) & (c < o1),
        }
        o2, c2, h2, l2 = sh(o, 2), sh(c, 2), sh(h, 2), sh(l, 2)
        body2, rng2 = np.abs(c2 - o2), h2 - l2
        big_red2 = (c2 < o2) & (body2 >= 0.6 * rng2) & (rng2 > 0)
        out["MSTAR"] = big_red2 & (body1 <= 0.3 * body2) & (np.maximum(o1, c1) < c2) & green & (c > (o2 + c2) / 2)
        g1, g2 = sh(green.astype(float), 1) > 0, sh(green.astype(float), 2) > 0
        strong = (body >= 0.5 * rng_) & (rng_ > 0)
        s1, s2 = sh(strong.astype(float), 1) > 0, sh(strong.astype(float), 2) > 0
        out["SOLDIERS"] = (green & g1 & g2 & strong & s1 & s2 & (c > c1) & (c1 > c2)
                           & (o >= o1) & (o <= c1) & (o1 >= o2) & (o1 <= c2) & (sh(c, 3) < sh(c, 8)))
    for k in ("ENGULF", "HAMMER", "PIERCE", "HARAMI", "MSTAR"):
        out[k] = np.nan_to_num(out[k] & down).astype(bool)
    out["SOLDIERS"] = np.nan_to_num(out["SOLDIERS"]).astype(bool)
    out["KERZE"] = np.logical_or.reduce([out[k] for k in PAT])
    return out


def wboden(l, h, c) -> tuple[np.ndarray, np.ndarray]:
    """(Doppelboden gebildet, Ausbruch über die Nackenlinie) je Tag."""
    n = len(c)
    formed, brk = np.zeros(n, bool), np.zeros(n, bool)
    for i in range(41, n):
        a, b = l[i - 40:i - 10], l[i - 10:i + 1]
        j1, j2 = int(np.argmin(a)), int(np.argmin(b))
        L1, L2 = a[j1], b[j2]
        if not (L1 > 0 and abs(L2 / L1 - 1) <= 0.03):
            continue
        p1, p2 = i - 40 + j1, i - 10 + j2
        if p2 - p1 < 5:
            continue
        neck = h[p1:p2 + 1].max()
        if neck < 1.05 * max(L1, L2):
            continue
        formed[i] = True
        brk[i] = c[i] > neck and c[i - 1] <= neck
    return formed, brk


def cup(h, c) -> tuple[np.ndarray, np.ndarray]:
    """(Henkel in Bildung, Ausbruch über das Henkel-Hoch) je Tag."""
    n = len(c)
    forming, brk = np.zeros(n, bool), np.zeros(n, bool)
    for i in range(151, n):
        w = c[i - 150:i - 24]
        p = int(np.argmax(w))
        H = w[p]
        pa = i - 150 + p
        seg = c[pa:i - 4]
        if len(seg) < 20:
            continue
        L = seg.min()
        depth = 1 - L / H
        if not 0.12 <= depth <= 0.40:
            continue
        lpos = pa + int(np.argmin(seg))
        rim_win = c[lpos:i]
        if not len(rim_win):
            continue
        r = lpos + int(np.argmax(rim_win))
        rim = c[r]
        hl = i - r
        if rim < 0.95 * H or not 5 <= hl <= 20:
            continue
        handle = c[r:i]
        if handle.min() < 0.88 * rim:
            continue
        forming[i] = True
        hh = h[r:i].max()
        brk[i] = c[i] > hh
    return forming, brk


def all_patterns(d: pd.DataFrame) -> dict[str, np.ndarray]:
    o, h, l, c = (d[k].to_numpy(float) for k in ("Open", "High", "Low", "Close"))
    P = candles(o, h, l, c)
    P["WBODEN"], P["WBODEN_BRK"] = wboden(l, h, c)
    P["CUP"], P["CUP_BRK"] = cup(h, c)
    return P


# ---------------------------------------------------------------- Frage A: B60-Trades
def part_a(a) -> None:
    from research.ultimate import round1 as R
    sig, meta = R.setup(a.data, a.signals, a.sec)
    t = R.per_trade(R.build(sig, meta, "E0", 1e-5))
    adj = R._G["adj"]
    cache, rows = {}, []
    for x in t.itertuples(index=False):
        d = adj[x.ticker]
        if x.ticker not in cache:
            cache[x.ticker] = all_patterns(d)
        P = cache[x.ticker]
        idx = d.index
        i = int(idx.searchsorted(pd.Timestamp(x.signal_date), side="right") - 1)
        k = int(idx.searchsorted(pd.Timestamp(x.entry_date), side="left"))       # Kauftag; Fenster endet am Vortag
        lo, hi = max(0, i - 10), max(i + 1, k)                                  # [Treffer − 10, Kauftag − 1]
        rows.append({f: bool(P[f][lo:hi].any()) for f in ALL})
    df = t.join(pd.DataFrame(rows, index=t.index))
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    res = {}
    for f in ALL:
        m = df[f]
        row = {"share": round(float(m.mean()), 4), "n": int(m.sum()),
               "mit": round(float(df.loc[m, "R_stress"].mean()), 4) if m.any() else None,
               "ohne": round(float(df.loc[~m, "R_stress"].mean()), 4) if (~m).any() else None, "ab": {}}
        for ab in AB:
            s = df[df["abschnitt"] == ab]
            ms = s[f]
            row["ab"][ab] = {"n": int(ms.sum()), "diff": round(float(s.loc[ms, "R_stress"].mean() - s.loc[~ms, "R_stress"].mean()), 4)
                             if ms.sum() >= 10 and (~ms).sum() >= 10 else None}
        A, B = df.loc[m, "R_stress"].to_numpy(), df.loc[~m, "R_stress"].to_numpy()
        if len(A) >= 30 and len(B) >= 30:
            z = (A.mean() - B.mean()) / sqrt(A.var(ddof=1) / len(A) + B.var(ddof=1) / len(B))
            row["p"] = round(float(2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))), 5)
        res[f] = row
    ps = sorted([(r["p"], f) for f, r in res.items() if r.get("p") is not None])
    prev = 1.0
    for rank in range(len(ps), 0, -1):
        p, f = ps[rank - 1]
        prev = min(prev, p * len(ps) / rank)
        res[f]["q"] = round(prev, 5)
    for f, r in res.items():
        diffs = [v["diff"] for v in r["ab"].values()]
        up = all(x is not None and x >= 0.05 for x in diffs)
        dn = all(x is not None and x <= -0.05 for x in diffs)
        r["status"] = ("Verstärker – Kandidat für Depot-Test" if up and r.get("q", 1) <= 0.10
                       else "schadet beständig" if dn and r.get("q", 1) <= 0.10 else "kein beständiger Effekt")
    (out / "candle_a.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


# ---------------------------------------------------------------- Frage B: Formation allein als Signal
def part_b(a) -> None:
    from .mrconfirm import FX_USD, boot_p, prep, rsi
    sets = {"main": ("2008-01-01", "2026-10-16"), "pre": ("1999-01-01", "2007-12-31"), "asia": ("2008-01-01", "2026-10-16")}
    s0, s1 = (pd.Timestamp(x) for x in sets[a.set])
    uni = pd.read_csv(a.universe)
    cur = dict(zip(uni["ticker"], uni["currency"].fillna("USD")))
    p = Path(a.px)
    files = [p / "prices_v1.parquet"] if (p / "prices_v1.parquet").exists() else sorted(p.glob("px_*.parquet"))
    raw = pd.concat([pd.read_parquet(f) for f in files])
    raw["date"] = pd.to_datetime(raw["date"])
    rng = np.random.default_rng(SEED)
    rows = []
    stash = []
    for t, g in raw.groupby("ticker"):
        fx = FX_USD.get(cur.get(t, "USD"))
        if fx is None:
            continue
        d = prep(g.set_index("date"), fx)
        if len(d) < 260:
            continue
        P = all_patterns(d)
        os_ = rsi(d["Close"], 14).rolling(20, min_periods=1).min().lt(30).to_numpy()
        ok = ((d.index >= s0) & (d.index <= s1)) & d["base"].to_numpy()
        up = d["up"].to_numpy()
        flags = {f: P[f] & os_ for f in PAT + ("KERZE",)}
        flags["WBODEN"] = P["WBODEN_BRK"]
        flags["CUP"] = P["CUP_BRK"]
        stash.append((t, d, flags, os_, up, ok))
    n_k = sum(int((s[2]["KERZE"] & s[5]).sum()) for s in stash)
    n_os = sum(int((s[3] & s[5]).sum()) for s in stash)
    n_up = sum(int((s[4] & s[5]).sum()) for s in stash)
    p_os, p_up = min(1, n_k / max(n_os, 1)), min(1, n_k / max(n_up, 1))
    for t, d, flags, os_, up, ok in stash:
        flags["K-ABV"] = os_ & (rng.random(len(d)) < p_os)
        flags["K-TREND"] = up & (rng.random(len(d)) < p_up)
        o, c = d["Open"].to_numpy(float), d["Close"].to_numpy(float)
        for v, f in flags.items():
            ii = np.flatnonzero(f & ok)
            ii = ii[ii + 10 < len(c)]
            for i in ii:
                rows.append((v, t, d.index[i], c[i + 10] / o[i + 1] - 1))
    T = pd.DataFrame(rows, columns=["v", "t", "sig", "g"])
    print(f"{a.set}: {len(stash)} Aktien", T.groupby("v").size().to_dict(), flush=True)
    parts = {"all": (s0, s1)} if a.set != "main" else {k: (pd.Timestamp(x), pd.Timestamp(y)) for k, (x, y) in PERIODS.items()}
    res = {"set": a.set, "n_stocks": len(stash), "parts": {}}
    for name, (a0, a1) in parts.items():
        X = T[(T["sig"] >= a0) & (T["sig"] <= a1)]
        R_ = {}
        for v in PAT + ("KERZE", "WBODEN", "CUP", "K-ABV", "K-TREND"):
            x = X[X["v"] == v]
            if not len(x):
                continue
            ctrl = "K-TREND" if v == "CUP" else "K-ABV"
            row = {"n": int(len(x)), "g10": round(float(x["g"].mean()), 5), "win": round(float((x["g"] > 0).mean()), 3),
                   "net10": round(float(((1 + x["g"]) * 0.999 / 1.001 - 1).mean()), 5), "ctrl": ctrl}
            if not v.startswith("K-"):
                cx = X[X["v"] == ctrl]
                if len(cx):
                    dl, pv = boot_p(x, cx)
                    row.update(d_ctrl=round(dl, 5), p=round(pv, 4))
            R_[v] = row
        res["parts"][name] = R_
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / f"candle_b_{a.set}.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res["parts"], default=str)[:3000])


def report(d: Path) -> None:
    L = ["# Bullische Kerzen- und Chartformationen – Ergebnis", "",
         "Vorab festgelegt 02.11.2026 (research/reversal/candle.py).", ""]
    fa = d / "candle_a.json"
    if fa.exists():
        A = json.loads(fa.read_text())
        L += ["## A. Formation während der Bodenbildung → besseres B60-Setup?", "",
              "R je Trade mit Stress-Kosten, 13.241 B60-Trades 2008–26. Δ = mit minus ohne Formation.", "",
              "| Formation | Anteil der Setups | Ø R mit | Ø R ohne | Δ Train | Δ Validierung | Δ Holdout | q | Ergebnis |",
              "|---|---|---|---|---|---|---|---|---|"]
        for f, r in A.items():
            ds = [r["ab"][ab]["diff"] for ab in AB]
            L.append(f"| {f} | {r['share'] * 100:.0f} % | {r['mit']:+.3f} | {r['ohne']:+.3f} | "
                     + " | ".join("–" if x is None else f"{x:+.3f}" for x in ds) + f" | {r.get('q', '–')} | {r['status']} |")
        L.append("")
    B = {s: json.loads((d / f"candle_b_{s}.json").read_text()) for s in ("main", "pre", "asia") if (d / f"candle_b_{s}.json").exists()}
    if B:
        checks = []
        L += ["## B. Formation allein als Kaufsignal (Ertrag 10 Tage)", ""]
        for s, r in B.items():
            for part, P in r["parts"].items():
                lab = {"pre": "Vorzeit 99–07", "asia": "Asien 08–26"}.get(s, part)
                L += [f"### {lab} ({r['n_stocks']} Aktien)", "", "| Signal | Anzahl | Ø 10 T. | im Plus | netto | Δ gegen Kontrolle | p |", "|---|---|---|---|---|---|---|"]
                for v, x in P.items():
                    dc = "{:+.2f} Pkt. ({})".format(x["d_ctrl"] * 100, x["ctrl"]) if "d_ctrl" in x else "–"
                    L.append(f"| {v} | {x['n']} | {x['g10'] * 100:+.2f} % | {x['win'] * 100:.0f} % | {x['net10'] * 100:+.2f} % | {dc} | {x.get('p', '–')} |")
                    if "p" in x:
                        checks.append([v, lab, x["d_ctrl"], x["p"], x["net10"]])
                L.append("")
        ps = sorted(range(len(checks)), key=lambda i: checks[i][3])
        m, prev, q = len(ps), 1.0, [1.0] * len(checks)
        for rank in range(m, 0, -1):
            i = ps[rank - 1]
            prev = min(prev, checks[i][3] * m / rank)
            q[i] = prev
        L += ["### Entscheidung B", ""]
        for v in PAT + ("KERZE", "WBODEN", "CUP"):
            cs = [(c, q[i]) for i, c in enumerate(checks) if c[0] == v]
            if not cs:
                continue
            good = [c for c, qq in cs if c[2] > 0 and qq < 0.05 and c[4] > 0]
            better = [c for c, qq in cs if c[2] > 0]
            verdict = "BESTANDEN" if len(good) == len(cs) == 5 else "Hinweis" if len(better) >= 3 else "nicht bestanden"
            L.append(f"- **{v}**: {verdict} – besser als Kontrolle in {len(better)}/{len(cs)}, signifikant {len(good)} "
                     f"({', '.join(f'{c[1]} {c[2] * 100:+.2f}' for c, _ in cs)})")
    (d / "candle_report.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else ""
    ap = argparse.ArgumentParser(); ap.add_argument("cmd")
    if cmd == "a":
        ap.add_argument("--data"); ap.add_argument("--signals"); ap.add_argument("--sec"); ap.add_argument("--out", required=True)
        part_a(ap.parse_args(argv))
    elif cmd == "b":
        ap.add_argument("--px", required=True); ap.add_argument("--universe", required=True)
        ap.add_argument("--set", required=True); ap.add_argument("--out", required=True)
        part_b(ap.parse_args(argv))
    elif cmd == "report":
        ap.add_argument("--dir", required=True)
        report(Path(ap.parse_args(argv).dir))
    else:
        print(__doc__); return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
