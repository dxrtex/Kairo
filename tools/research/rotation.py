"""Forschung: Kann man Sektor-/Branchenrotation früh erkennen? (Rotations-Radar)

Wöchentliche Kurse der 11 Sektor- und 34 Branchen-ETFs gegen SPY. Für jede Woche werden Signale berechnet,
danach die Mehrrendite gegenüber SPY in den nächsten 4/8/13 Wochen gemessen.
Signale:
  rrg      Quadrant wie im Relative Rotation Graph (Verhältnis = rel. Stärke ggü. 13-Wochen-Schnitt, Schwung = 4-Wochen-Änderung)
  mom4/13/26/52  relative Rendite ggü. SPY (52: ohne letzte 4 Wochen)
  accel    Beschleunigung: rel. 4 Wochen minus 4/13 der rel. 13 Wochen
  flow     Geldfluss: Dollar-Umsatz 4 Wochen ggü. 26 Wochen × Richtung (Akkumulation)
  breakout rel. Stärke auf 26-Wochen-Hoch (aus Seitwärtslage)
Auswertung: je Woche Rang über alle ETFs → Quintile; Mehrrendite oberstes minus unterstes Quintil, Trefferquote,
t-Wert aus nicht überlappenden Zeiträumen, getrennt vor/nach 2016 (Robustheit).

    python tools/research/rotation.py out.json
"""
from __future__ import annotations

import json
import math
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from backend.analysis import INDUSTRY_ETF, SECTOR_ETF, THEME_ETF  # noqa: E402

H = (4, 8, 13)


def load():
    import yfinance as yf
    tk = sorted(set(SECTOR_ETF.values()) | set(INDUSTRY_ETF) | {k for k in THEME_ETF if not k.startswith("*")} | {"SPY"})   # Körbe (*) haben keine ETF-Historie
    h = yf.download(tk, period="max", interval="1d", auto_adjust=True, progress=False, group_by="ticker", threads=True)
    px, dv = {}, {}
    for t in tk:
        try:
            df = h[t].dropna(subset=["Close"])
        except Exception:
            continue
        w = df.resample("W-FRI").agg({"Close": "last", "Volume": "sum"}).dropna()
        px[t] = w["Close"]; dv[t] = w["Close"] * w["Volume"]
    return pd.DataFrame(px), pd.DataFrame(dv)


def signals(px: pd.DataFrame, dv: pd.DataFrame) -> dict[str, pd.DataFrame]:
    spy = px["SPY"]; X = px.drop(columns="SPY")
    rs = X.div(spy, axis=0)
    ratio = 100 * rs / rs.rolling(13).mean()
    mom = 100 * ratio / ratio.shift(4)
    rel = lambda n, s=0: (rs.shift(s) / rs.shift(n)) - 1
    ret1 = X.pct_change()
    acc = (np.sign(ret1 - spy.pct_change().values[:, None]) * dv.drop(columns="SPY")).rolling(4).sum() / dv.drop(columns="SPY").rolling(4).sum()
    vol_up = dv.drop(columns="SPY").rolling(4).mean() / dv.drop(columns="SPY").rolling(26).mean()
    q = pd.DataFrame(np.select([(ratio >= 100) & (mom >= 100), (ratio >= 100) & (mom < 100), (ratio < 100) & (mom < 100), (ratio < 100) & (mom >= 100)],
                               [1, 2, 3, 4], 0), index=X.index, columns=X.columns).where(ratio.notna() & mom.notna())
    return {"ratio": ratio, "mom": mom, "quad": q,
            "mom4": rel(4), "mom13": rel(13), "mom26": rel(26), "mom52": rel(52, 4),
            "accel": rel(4) - rel(13) * 4 / 13,
            "rrg_speed": (ratio - 100) * 0 + (mom - 100),            # nur Schwung
            "flow": acc * vol_up.clip(0, 3),
            "breakout": (rs >= rs.rolling(26).max()).astype(float).where(rs.notna()) - (rs <= rs.rolling(26).min()).astype(float).where(rs.notna())}


def fwd(px):
    spy = px["SPY"]; X = px.drop(columns="SPY")
    return {h: (X.shift(-h) / X - 1).sub(spy.shift(-h) / spy - 1, axis=0) for h in H}


def tstat(x):
    x = np.asarray([v for v in x if v == v]); n = len(x)
    return (float(x.mean() / (x.std(ddof=1) / math.sqrt(n))) if n > 2 and x.std() > 0 else float("nan")), n


def eval_rank(sig: pd.DataFrame, F: dict, uni: list[str], start="2008-01-01"):
    out = {}
    S = sig[uni].loc[start:]
    for h, f in F.items():
        f = f[uni].loc[start:]
        rows = []
        for i, d in enumerate(S.index):
            s = S.loc[d].dropna(); y = f.loc[d].reindex(s.index).dropna(); s = s.reindex(y.index)
            if len(s) < 8:
                continue
            r = s.rank(pct=True)
            top, bot = y[r > .8].mean(), y[r <= .2].mean()
            rows.append((d, top, bot, top - bot, float((y[r > .8] > 0).mean()), float(s.corr(y, method="spearman"))))
        df = pd.DataFrame(rows, columns=["d", "top", "bot", "ls", "hit", "ic"]).set_index("d")
        res = {}
        for name, part in (("alle", df), ("bis2015", df.loc[:"2015-12-31"]), ("ab2016", df.loc["2016-01-01":]), ("ab2021", df.loc["2021-01-01":])):
            nov = part.iloc[::h]                                   # nicht überlappend
            t, n = tstat(nov["ls"])
            res[name] = {"top": round(float(part.top.mean()) * 100, 2), "bot": round(float(part.bot.mean()) * 100, 2),
                         "spread": round(float(part.ls.mean()) * 100, 2), "t": round(t, 2), "n": n,
                         "hit_top": round(float(part.hit.mean()) * 100, 1), "ic": round(float(part.ic.mean()), 3)}
        out[h] = res
    return out


def eval_quad(q: pd.DataFrame, F: dict, uni, start="2008-01-01"):
    names = {1: "Leading", 2: "Weakening", 3: "Lagging", 4: "Improving"}
    out = {}
    Q = q[uni].loc[start:]
    prev = Q.shift(1)
    for h, f in F.items():
        f = f[uni].loc[start:]
        r = {}
        for k, nm in names.items():
            m = (Q == k)
            v = f.where(m).stack().dropna()
            r[nm] = {"mean": round(float(v.mean()) * 100, 2), "hit": round(float((v > 0).mean()) * 100, 1), "n": int(v.size)}
        for (a, b) in ((3, 4), (4, 1), (1, 2), (2, 3)):
            v = f.where((prev == a) & (Q == b)).stack().dropna()
            r[f"{names[a]}→{names[b]}"] = {"mean": round(float(v.mean()) * 100, 2), "hit": round(float((v > 0).mean()) * 100, 1), "n": int(v.size),
                                           "ab2016": round(float(v.loc["2016-01-01":].mean()) * 100, 2) if v.size else None}
        out[h] = r
    return out


def combo(sig, F, uni):
    """Kombination: rel. Momentum 26 W (Trend) + Beschleunigung + Fluss – je Woche als Rang-Mittel."""
    z = sum(sig[k][uni].rank(axis=1, pct=True) for k in ("mom26", "accel", "flow")) / 3
    return eval_rank(z, F, uni)


def main(out_path: str) -> int:
    px, dv = load()
    print("ETFs:", px.shape[1] - 1, "Wochen:", len(px), "ab", px.index[0].date())
    S, F = signals(px, dv), fwd(px)
    sec = [t for t in SECTOR_ETF.values() if t in px]; ind = [t for t in INDUSTRY_ETF if t in px]; th = [t for t in THEME_ETF if t in px]
    res = {}
    for uname, uni in (("sektoren", sec), ("branchen", ind), ("themen", th), ("branchen+themen", ind + th), ("alle", sec + ind + th)):
        r = {k: eval_rank(S[k], F, uni) for k in ("mom4", "mom13", "mom26", "mom52", "accel", "rrg_speed", "ratio", "flow", "breakout")}
        r["kombi"] = combo(S, F, uni)
        r["quadrant"] = eval_quad(S["quad"], F, uni)
        res[uname] = r
        print(f"\n===== {uname} ({len(uni)} ETFs) – Spread oberstes minus unterstes Quintil, % Mehrrendite ggü. SPY =====")
        for k, v in r.items():
            if k == "quadrant":
                continue
            print(f"{k:10s} " + " | ".join(f"{h}W: {v[h]['alle']['spread']:+.2f} (t {v[h]['alle']['t']:+.1f}; ab16 {v[h]['ab2016']['spread']:+.2f} t {v[h]['ab2016']['t']:+.1f}; ab21 {v[h]['ab2021']['spread']:+.2f}) top-hit {v[h]['alle']['hit_top']}%" for h in H))
        print("Quadranten (Mehrrendite % / Trefferquote):")
        for h in H:
            print(f"  {h}W: " + " · ".join(f"{k} {x['mean']:+.2f}/{x['hit']}% n{x['n']}" for k, x in r["quadrant"][h].items()))
    # Aktueller Stand (letzte Woche) zur Anschauung
    last = S["quad"].iloc[-1]
    res["jetzt"] = {t: {"quad": int(last[t]) if last[t] == last[t] else None, "ratio": round(float(S["ratio"][t].iloc[-1]), 1), "mom": round(float(S["mom"][t].iloc[-1]), 1)} for t in sec + ind + th}
    json.dump(res, open(out_path, "w"), ensure_ascii=False, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "rotation.json"))
