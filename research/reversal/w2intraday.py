"""W2-Audit – marktnahe Ausführungsprüfung mit kostenlosen Stundenkerzen (Yahoo, max. ~730 Tage zurück).

Frage: Wenn das Tagestief das Kauf-Limit berührt – lag der Kurs nur kurz dort (Docht) oder handelte er eine Weile darunter?
Ohne Orderbuch/Geld-Brief-Daten bleibt das eine MODELLRECHNUNG; sie ersetzt keine echten Orderdaten.

Vorab festgelegt (02.11.2026): Für alle W2-Signale (Top 10 je Tag, USA/Europa) mit Signaltag ab dem ersten Tag, für den
Stundenkerzen vorliegen, wird am Folgetag geprüft:
  opt      Tagestief ≤ Limit
  kons     Tagestief ≤ Limit·(1 − hs − 0,1 %) oder Eröffnung·(1+hs) ≤ Limit (wie backend/mrsim)
  stunde   mindestens eine Stundenkerze SCHLIESST ≤ Limit (Kurs lag zu einem Stundenwechsel unter dem Limit)
  stunde2  mindestens zwei Stundenkerzen mit Tief ≤ Limit (mehr als ein einzelner Ausreißer)
Ausgewiesen: Ausführungsquote je Modell, Übereinstimmung Tages-/Stundendaten, Ertrag der ausgeführten Trades.

    python -m research.reversal.w2intraday --data v1 --out OUT
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from backend import mrsim as S

from .w2audit import _adjust, top_per_day

UNIVERSE = "research/strategy_championship/data/universe_frozen_2026-10-16.csv"


def hourly(tickers: list[str], start: str, end: str) -> dict[str, pd.DataFrame]:
    import yfinance as yf
    out = {}
    for k in range(0, len(tickers), 40):
        part = tickers[k:k + 40]
        for att in range(3):
            try:
                d = yf.download(part, start=start, end=end, interval="60m", auto_adjust=False, group_by="ticker",
                                progress=False, threads=True)
                break
            except Exception as exc:
                print("Fehler", repr(exc)[:80]); time.sleep(10 * 2 ** att); d = None
        if d is None or d.empty:
            continue
        for t in part:
            try:
                x = d[t] if isinstance(d.columns, pd.MultiIndex) else d
            except KeyError:
                continue
            x = x.dropna(subset=["Low", "Close"])
            if len(x):
                idx = pd.to_datetime(x.index)
                x.index = idx.tz_convert(None) if idx.tz is not None else idx
                out[t] = x
        print(f"Stundenkerzen {min(k + 40, len(tickers))}/{len(tickers)}", flush=True)
        time.sleep(1)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--universe", default=UNIVERSE)
    a = ap.parse_args(argv)
    uni = pd.read_csv(a.universe)
    cur = dict(zip(uni["ticker"], uni["currency"].fillna("USD")))
    reg = dict(zip(uni["ticker"], uni["region"].fillna("?")))
    raw = pd.read_parquet(Path(a.data) / "prices_v1.parquet")
    raw["date"] = pd.to_datetime(raw["date"])
    end = raw["date"].max()
    start = end - pd.Timedelta(days=700)
    raw = raw[raw["date"] >= start - pd.Timedelta(days=420)]
    ind, sig = {}, []
    for t, g in raw.groupby("ticker"):
        if str(reg.get(t, "")).lower() not in ("us", "eu", "europe") or cur.get(t, "USD") not in S.FX_USD:
            continue
        d = _adjust(g.set_index("date"))
        if len(d) < 220:
            continue
        x = S.indicators(d, cur.get(t, "USD"))
        ind[t] = x
        sig += S.signal_rows(t, x, start, end - pd.Timedelta(days=3))
    sig = [s for s in top_per_day(sig) if s.get("lim")]
    print(len(sig), "W2-Signale", flush=True)
    H = hourly(sorted({s["t"] for s in sig}), str(start.date()), str((end + pd.Timedelta(days=2)).date()))
    cb = S.COSTS["basis"]
    rows = []
    for s in sig:
        x = ind[s["t"]]
        i = x.index.get_loc(s["d"])
        if i + 1 >= len(x):
            continue
        day = x.index[i + 1]
        f_adj = 1.0
        o, lo = float(x["o"].iat[i + 1]), float(x["l"].iat[i + 1])
        L, hs = s["lim"], cb.hs(s["adv"])
        h = H.get(s["t"])
        hd = h[h.index.normalize() == day] if h is not None else None
        if hd is None or not len(hd):
            continue
        # Stundenkerzen sind unbereinigt, Tageskerzen bereinigt: auf das Tagestief skalieren (gleicher Tag → nur Dividendenfaktor)
        k = lo / float(hd["Low"].min()) if float(hd["Low"].min()) > 0 else np.nan
        hl, hc = hd["Low"].to_numpy(float) * k, hd["Close"].to_numpy(float) * k
        P = S.make_px(x)
        r_opt = S.trade_of(P, i, "W2", L, hs, cb, "opt")
        r_k = S.trade_of(P, i, "W2", L, hs, cb, "kons")
        rows.append({"t": s["t"], "d": str(day.date()), "opt": lo <= L, "kons": S.fill_limit(o, lo, L, hs, "kons") is not None,
                     "stunde": bool((hc <= L).any()) or o <= L, "stunde2": int((hl <= L).sum()) >= 2 or o <= L,
                     "bars": int(len(hd)), "scale": float(k),
                     "g_opt": r_opt.get("gross"), "n_opt": r_opt.get("net"), "n_kons": r_k.get("net")})
    df = pd.DataFrame(rows)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    res = {"signals": len(sig), "with_hourly": int(len(df)), "start": str(start.date()), "end": str(end.date())}
    if len(df):
        for m in ("opt", "kons", "stunde", "stunde2"):
            res[f"fill_{m}"] = round(float(df[m].mean()), 4)
        t = df[df["opt"]]
        res["of_opt_touch"] = {m: round(float(t[m].mean()), 4) for m in ("kons", "stunde", "stunde2")}
        for m in ("opt", "stunde", "stunde2"):
            x = df[df[m] & df["n_opt"].notna()]
            res[f"net_{m}"] = round(float(x["n_opt"].mean()), 5) if len(x) else None
            res[f"n_{m}"] = int(len(x))
        res["scale_ok"] = round(float(((df["scale"] > 0.9) & (df["scale"] < 1.1)).mean()), 3)
    df.to_csv(out / "w2intraday_events.csv.gz", index=False)
    (out / "w2intraday.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
