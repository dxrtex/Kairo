"""Fundamentaldaten für alle Aktien des Scans (Yahoo „info“, kostenlos) und die Kairo-Schneeflocke.

    python -m backend.fundamentals --shard 0 --shards 8          → fund_part_0.json (Rohwerte je Aktie)
    python -m backend.fundamentals --combine teile/ --prev alt.json → site/data/fund.json

Fünf Achsen wie bei Simply Wall St, je 0–6 Punkte aus sechs einfachen Prüfungen:
  Bewertung (KGV/KBV/EV-EBITDA gegen die Branche, Analystenziel), Wachstum (Umsatz, Gewinn, erwartetes KGV),
  Rentabilität (Margen, Eigenkapitalrendite), Gesundheit (Verschuldung, Liquidität, freier Cashflow),
  Dividende (Rendite, Ausschüttungsquote). Reine Einordnung – die Kairo-Regel nutzt das nicht.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from .config import ROOT

FIELDS = {"pe": "trailingPE", "fpe": "forwardPE", "pb": "priceToBook", "ps": "priceToSalesTrailing12Months", "ev": "enterpriseToEbitda",
          "pm": "profitMargins", "om": "operatingMargins", "gm": "grossMargins", "rg": "revenueGrowth", "eg": "earningsGrowth",
          "roe": "returnOnEquity", "roa": "returnOnAssets", "de": "debtToEquity", "cr": "currentRatio", "fcf": "freeCashflow",
          "cash": "totalCash", "debt": "totalDebt", "pr": "payoutRatio", "beta": "beta", "tm": "targetMeanPrice", "cp": "currentPrice",
          "rm": "recommendationMean", "na": "numberOfAnalystOpinions", "mc": "marketCap", "dr": "dividendRate", "rev": "totalRevenue",
          # Ergänzt 14.11.2026 (Smart Money / Dividende) – kommt aus demselben Abruf, kostet nichts extra
          "spf": "shortPercentOfFloat", "sr": "shortRatio", "shs": "sharesShort", "shp": "sharesShortPriorMonth",
          "hpi": "heldPercentInstitutions", "hpn": "heldPercentInsiders", "dy5": "fiveYearAvgDividendYield",
          "exd": "exDividendDate", "eps": "trailingEps", "feps": "forwardEps", "so": "sharesOutstanding"}


def fetch(tickers: list[str], pause: float = 0.3, budget_s: float = 5000) -> dict:
    import yfinance as yf
    out, t0 = {}, time.time()
    for k, t in enumerate(tickers):
        if time.time() - t0 > budget_s:
            print(f"Zeitbudget erreicht nach {k} Aktien")
            break
        info = {}
        for attempt in range(3):
            try:
                info = yf.Ticker(t).get_info() or {}
                break
            except Exception as exc:
                if "429" in str(exc) or "Too Many" in str(exc):
                    time.sleep(20 * (attempt + 1))
                else:
                    break
        row = {k2: info.get(src) for k2, src in FIELDS.items() if isinstance(info.get(src), (int, float)) and info.get(src) == info.get(src)}
        if info.get("sector"):
            row["sec"] = info["sector"]
        if len(row) >= 3:
            out[t] = row
        if k % 100 == 0:
            print(f"  {k}/{len(tickers)} · {len(out)} mit Daten · {time.time() - t0:.0f} s", flush=True)
        time.sleep(pause)
    return out


def _med(vals):
    v = [x for x in vals if x is not None]
    return statistics.median(v) if len(v) >= 5 else None


def score(r: dict, med: dict, allmed: dict) -> list[int]:
    """Fünf Achsen je 0–6: Bewertung, Wachstum, Rentabilität, Gesundheit, Dividende."""
    m = {**allmed, **{k: v for k, v in (med or {}).items() if v is not None}}
    g = lambda k: r.get(k)
    pe, fpe, pb, ev = g("pe"), g("fpe"), g("pb"), g("ev")
    dy = (g("dr") / g("cp")) if g("dr") and g("cp") else 0
    val = sum([bool(pe and pe > 0 and m.get("pe") and pe < m["pe"]), bool(pe and 0 < pe < 20), bool(fpe and pe and 0 < fpe < pe),
               bool(pb and m.get("pb") and 0 < pb < m["pb"]), bool(ev and m.get("ev") and 0 < ev < m["ev"]),
               bool(g("tm") and g("cp") and g("tm") > g("cp") * 1.2)])
    gro = sum([bool((g("rg") or 0) > .05), bool((g("rg") or 0) > .15), bool((g("eg") or 0) > .05), bool((g("eg") or 0) > .15),
               bool(fpe and pe and 0 < fpe < pe * .9), bool(m.get("rg") is not None and (g("rg") or -9) > m["rg"])])
    pro = sum([bool((g("pm") or -1) > 0), bool(m.get("pm") is not None and (g("pm") or -9) > m["pm"]), bool((g("roe") or 0) > .1),
               bool((g("roe") or 0) > .2), bool((g("om") or 0) > .1), bool((g("gm") or 0) > .4)])
    de = g("de")
    hea = sum([bool(de is not None and de < 100), bool(de is not None and de < 50), bool((g("cr") or 0) > 1), bool((g("cr") or 0) > 1.5),
               bool((g("fcf") or 0) > 0), bool(g("cash") is not None and g("debt") is not None and g("cash") > g("debt"))])
    pr = g("pr")
    div = sum([bool(dy > 0), bool(dy > .015), bool(dy > .03), bool(dy > 0 and pr is not None and pr < .9), bool(dy > 0 and pr is not None and pr < .6),
               bool(dy > 0 and (g("fcf") or 0) > 0)])
    return [val, gro, pro, hea, div]


def combine(parts: list[Path], prev: Path | None) -> dict:
    raw = {}
    if prev and prev.exists():                         # Fehlversuche: alten Stand behalten
        try:
            raw = {t: {k: v for k, v in r.items() if k not in ("sf",)} for t, r in json.loads(prev.read_text()).get("by", {}).items()}
        except Exception:
            raw = {}
    for p in parts:
        raw.update(json.loads(p.read_text()))
    secs = {}
    for r in raw.values():
        secs.setdefault(r.get("sec") or "–", []).append(r)
    keys = ("pe", "pb", "ev", "rg", "pm")
    pos = lambda k, v: v if v is not None and (k not in ("pe", "pb", "ev") or v > 0) else None
    allmed = {k: _med([pos(k, r.get(k)) for r in raw.values()]) for k in keys}
    med = {s: {k: _med([pos(k, r.get(k)) for r in rs]) for k in keys} for s, rs in secs.items()}
    by = {}
    for t, r in raw.items():
        rr = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()}
        rr["sf"] = score(r, med.get(r.get("sec") or "–"), allmed)
        by[t] = rr
    return {"generated": time.strftime("%Y-%m-%d"), "n": len(by), "med": med, "all": allmed, "by": by}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--combine")
    ap.add_argument("--prev")
    a = ap.parse_args(argv)
    if a.combine:
        res = combine(sorted(Path(a.combine).glob("fund_part_*.json")), Path(a.prev) if a.prev else None)
        out = ROOT / "site" / "data"
        out.mkdir(parents=True, exist_ok=True)
        (out / "fund.json").write_text(json.dumps(res, separators=(",", ":"), allow_nan=False))
        print(f"Fundamentaldaten: {res['n']} Aktien")
        return 0
    from .universe import load as load_universe
    tickers = sorted(set(load_universe()["ticker"]))[a.shard::a.shards]
    out = fetch(tickers)
    Path(f"fund_part_{a.shard}.json").write_text(json.dumps(out, separators=(",", ":")))
    print(f"Shard {a.shard}: {len(out)} von {len(tickers)} Aktien")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
