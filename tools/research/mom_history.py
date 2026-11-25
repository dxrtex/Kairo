"""Kann Momentum über Jahre verlieren? (Frage 25.11.2026) – 99 Jahre US-Daten ohne Überlebens-Verzerrung.

Quelle: Kenneth R. French Data Library (CRSP, alle NYSE/AMEX/NASDAQ-Aktien inkl. Pleiten und Delistings):
10 Portfolios nach 12-2-Momentum (monatlich neu gebildet) und Marktrendite (Mkt-RF + RF). Oberstes Zehntel = „Hi PRIOR“
– das kommt unserer Regel am nächsten (wir: Top 10 Aktien, 12-1, vierteljährlich; dort Hunderte Aktien → breiter gestreut).

    python tools/research/mom_history.py
"""
from __future__ import annotations

import io
import urllib.request
import zipfile

import numpy as np
import pandas as pd

BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"


def section(name: str, title: str) -> pd.DataFrame:
    raw = urllib.request.urlopen(BASE + name, timeout=120).read()
    txt = zipfile.ZipFile(io.BytesIO(raw)).read(zipfile.ZipFile(io.BytesIO(raw)).namelist()[0]).decode("latin-1").splitlines()
    i = next(k for k, l in enumerate(txt) if title.lower() in l.lower()) if title else 0
    j = next(k for k in range(i, len(txt)) if txt[k].strip().startswith(","))       # Kopfzeile
    hdr = [h.strip() for h in txt[j].split(",")]
    rows = []
    for l in txt[j + 1:]:
        p = [x.strip() for x in l.split(",")]
        if len(p) < 2 or not p[0].isdigit() or len(p[0]) != 6:
            break
        rows.append(p)
    df = pd.DataFrame(rows, columns=["d"] + hdr[1:]).set_index("d").astype(float) / 100
    df.index = pd.to_datetime(df.index, format="%Y%m") + pd.offsets.MonthEnd(0)
    return df


def dd_stats(r: pd.Series):
    w = (1 + r).cumprod()
    dd = w / w.cummax() - 1
    under, best, cur, start, bstart = 0, 0, 0, None, None
    for d, v in dd.items():
        if v < 0:
            cur += 1
            start = start or d
            if cur > best:
                best, bstart = cur, start
        else:
            cur, start = 0, None
    return dd.min(), dd.idxmin(), best / 12, bstart


def main():
    for wt, title in (("WERTGEWICHTET", "Value Weight Returns -- Monthly"), ("GLEICHGEWICHTET", "Equal Weight Returns -- Monthly")):
        mom = section("10_Portfolios_Prior_12_2_CSV.zip", title)
        ff = section("F-F_Research_Data_Factors_CSV.zip", "")
        mkt = (ff["Mkt-RF"] + ff["RF"]).reindex(mom.index)
        hi = mom[mom.columns[-1]]
        lo = mom[mom.columns[0]]
        print(f"\n################ {wt} · {mom.index[0]:%Y}–{mom.index[-1]:%Y} · oberstes Zehntel (Hi PRIOR) vs. Gesamtmarkt ################")
        cagr = lambda r: (1 + r).prod() ** (12 / len(r)) - 1
        print(f"  Gesamt: Momentum {cagr(hi) * 100:5.1f} % p. a. · Markt {cagr(mkt) * 100:5.1f} % · schwächstes Zehntel {cagr(lo) * 100:5.1f} %")
        for a in range(1927, 2030, 10):
            m = (hi.index.year >= a) & (hi.index.year < a + 10)
            if m.sum() >= 24:
                print(f"  {a}er: Momentum {cagr(hi[m]) * 100:6.1f} % · Markt {cagr(mkt[m]) * 100:6.1f} % · Vorsprung {(cagr(hi[m]) - cagr(mkt[m])) * 100:+5.1f}")
        for nm, r in (("Momentum", hi), ("Markt", mkt)):
            d, when, yrs, st = dd_stats(r)
            print(f"  {nm}: größter Rückgang {d * 100:5.1f} % (Tief {when:%m/%Y}) · längste Zeit unter dem alten Hoch {yrs:4.1f} Jahre (ab {st:%m/%Y})")
        for y in (1, 3, 5, 10):
            n = 12 * y
            rh = (1 + hi).rolling(n).apply(np.prod, raw=True) - 1
            rm = (1 + mkt).rolling(n).apply(np.prod, raw=True) - 1
            ok = rh.notna() & rm.notna()
            print(f"  {y:2d} Jahre am Stück: Momentum im Minus in {(rh[ok] < 0).mean() * 100:4.1f} % der Zeiträume (schlimmster {rh[ok].min() * 100:6.1f} % bis {rh[ok].idxmin():%m/%Y}) · "
                  f"schlechter als der Markt in {(rh[ok] < rm[ok]).mean() * 100:4.1f} % · Markt im Minus in {(rm[ok] < 0).mean() * 100:4.1f} %")
        print("  Bekannte Einbrüche (Momentum / Markt):")
        for a, b, nm in (("1929-09", "1932-06", "Weltwirtschaftskrise"), ("2000-03", "2002-09", "Dotcom-Crash"), ("2007-10", "2009-02", "Finanzkrise"),
                         ("2009-03", "2009-12", "Erholung 2009 (Momentum-Crash)"), ("2020-02", "2020-03", "Corona"), ("2022-01", "2022-12", "2022"),
                         ("2016-01", "2026-12", "unser Backtest-Zeitraum")):
            m = (hi.index >= a) & (hi.index <= pd.Timestamp(b) + pd.offsets.MonthEnd(0))
            if m.sum():
                print(f"    {nm:<32} {((1 + hi[m]).prod() - 1) * 100:7.1f} % / {((1 + mkt[m]).prod() - 1) * 100:7.1f} %")


if __name__ == "__main__":
    main()
