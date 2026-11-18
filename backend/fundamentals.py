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
          "exd": "exDividendDate", "eps": "trailingEps", "feps": "forwardEps", "so": "sharesOutstanding",
          # Ergänzt 18.11.2026 (Screener wie im Profi-Terminal): PEG, operativer Cashflow (→ KCV), Rendite 52 Wochen
          "peg": "trailingPegRatio", "ocf": "operatingCashflow", "w52": "52WeekChange"}


def _num(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if v == v and abs(v) != float("inf") else None


def eps_history(df) -> list:
    """Gewinn je Aktie der letzten Quartale aus get_earnings_dates(): [[datum, schätzung, tatsächlich], …] aufsteigend, höchstens 8.
    Künftige Termine (noch ohne tatsächlichen Wert) fallen weg."""
    if df is None or getattr(df, "empty", True):
        return []
    out = []
    for ix, r in df.iterrows():
        a, e = _num(r.get("Reported EPS")), _num(r.get("EPS Estimate"))
        if a is None:
            continue
        out.append([str(ix)[:10], None if e is None else round(e, 4), round(a, 4)])
    out.sort(key=lambda x: x[0])
    return out[-8:]


def quarter_revenue(df) -> list:
    """Umsatz je Quartal aus quarterly_income_stmt: [[quartalsende, umsatz], …] aufsteigend, höchstens 8."""
    if df is None or getattr(df, "empty", True):
        return []
    rows = {str(k).replace(" ", "").lower(): k for k in df.index}
    rk = rows.get("totalrevenue") or rows.get("operatingrevenue")
    if rk is None:
        return []
    out = [[str(c)[:10], round(_num(df.at[rk, c]))] for c in df.columns if _num(df.at[rk, c]) is not None]
    out.sort(key=lambda x: x[0])
    return out[-8:]


def updowns(df, n: int = 10) -> list:
    """Hoch-/Abstufungen der Analysten (upgrades_downgrades): [[datum, bank, von, nach, aktion, kursziel], …] neueste zuerst."""
    if df is None or getattr(df, "empty", True):
        return []
    out = []
    for ix, r in df.sort_index(ascending=False).head(n).iterrows():
        pt = _num(r.get("currentPriceTarget"))
        out.append([str(ix)[:10], str(r.get("Firm") or "")[:40], str(r.get("FromGrade") or ""), str(r.get("ToGrade") or ""),
                    str(r.get("Action") or ""), round(pt, 2) if pt else None])
    return out


def short_desc(text: str | None, limit: int = 340) -> str:
    """Erste ein bis zwei Sätze der Firmenbeschreibung (Yahoo), höchstens ~340 Zeichen."""
    t = " ".join(str(text or "").split())
    if not t:
        return ""
    parts, out = t.split(". "), ""
    for p in parts:
        nxt = (out + ". " if out else "") + p.rstrip(".")
        if len(nxt) > limit and out:
            break
        out = nxt
        if len(out) >= limit * .55:
            break
    return (out[:limit].rstrip() + ".") if out else ""


def income_history(df) -> list:
    """Umsatz und Gewinn je Geschäftsjahr aus get_income_stmt(): [[jahr, umsatz, nettogewinn], …] aufsteigend, höchstens 5."""
    if df is None or getattr(df, "empty", True):
        return []
    rows = {str(k).replace(" ", "").lower(): k for k in df.index}
    rk, nk = rows.get("totalrevenue"), rows.get("netincome") or rows.get("netincomecommonstockholders")
    if rk is None:
        return []
    out = []
    for col in df.columns:
        rev = _num(df.at[rk, col])
        ni = _num(df.at[nk, col]) if nk is not None else None
        if rev is None:
            continue
        out.append([str(col)[:4], round(rev), None if ni is None else round(ni)])
    out.sort(key=lambda x: x[0])
    return out[-5:]


# Jahresabschlüsse außerhalb der USA (18.11.2026): dieselbe Tabelle wie fin.json aus der SEC (backend/finhist.py),
# nur aus Yahoos Jahresberichten (Gewinn- und Verlustrechnung, Bilanz, Kapitalfluss). Zeilen: erster vorhandener Name gewinnt.
FA_ROWS = {"rev": ("totalrevenue", "operatingrevenue"), "gp": ("grossprofit",), "oi": ("operatingincome", "totaloperatingincomeasreported"),
           "ni": ("netincomecommonstockholders", "netincome"), "eps": ("dilutedeps", "basiceps"), "fcf": ("freecashflow",),
           "cash": ("cashandcashequivalents", "cashcashequivalentsandshortterminvestments"),
           "debt": ("longtermdebt", "longtermdebtandcapitalleaseobligation"), "eq": ("stockholdersequity", "commonstockequity")}


def annual_fin(inc, bal=None, cf=None, cur: str | None = None) -> dict | None:
    """Yahoo-Jahresberichte → {"y": [jahre], "fye": "MM-TT", Kennzahl: [werte], "cur": währung, "src": "yahoo"} – Format wie fin.json."""
    frames = [f for f in (inc, bal, cf) if f is not None and not getattr(f, "empty", True)]
    if inc is None or getattr(inc, "empty", True):
        return None
    val: dict = {}                                     # (kennzahl, jahresende) → wert
    for f in frames:
        rows = {str(k).replace(" ", "").lower(): k for k in f.index}
        for m, names in FA_ROWS.items():
            key = next((rows[n] for n in names if n in rows), None)
            if key is None:
                continue
            for col in f.columns:
                v = _num(f.at[key, col])
                if v is not None:
                    val.setdefault((m, str(col)[:10]), v)
    ends = sorted({e for (m, e) in val if m == "rev"})[-6:]
    if len(ends) < 2:
        return None
    out: dict = {"y": [e[:4] for e in ends], "fye": ends[-1][5:10]}
    for m in FA_ROWS:
        vs = [val.get((m, e)) for e in ends]
        if any(v is not None for v in vs):
            out[m] = [None if v is None else (round(v, 2) if m == "eps" else round(v)) for v in vs]
    if cur:
        out["cur"] = str(cur)[:4]
    out["src"] = "yahoo"
    return out


def monthly(df, years: int = 12) -> dict | None:
    """Monats-Schlusskurse für den Bewertungsverlauf über viele Jahre: {"m0": "JJJJ-MM", "c": [kurse]} (4 gültige Stellen)."""
    if df is None or getattr(df, "empty", True) or "Close" not in df:
        return None
    c = df["Close"].dropna()
    c = c[c > 0].iloc[-12 * years:]
    if len(c) < 24:
        return None
    sig = lambda v: float(f"{v:.4g}")
    return {"m0": c.index[0].strftime("%Y-%m"), "c": [sig(float(v)) for v in c]}


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
        if info.get("industry"):
            row["ind"] = str(info["industry"])[:60]
        d = short_desc(info.get("longBusinessSummary"))
        if d:
            row["_d"] = d
        if len(row) >= 3:                              # Verlauf für die Übersichtskarte (14.11.2026): Gewinn je Quartal, Umsatz/Gewinn je Jahr
            tk = yf.Ticker(t)
            try:
                eh = eps_history(tk.get_earnings_dates(limit=12))
                if eh:
                    row["eh"] = eh
            except Exception:
                pass
            inc = None
            try:
                inc = tk.get_income_stmt()
                ih = income_history(inc)
                if ih:
                    row["ih"] = ih
            except Exception:
                pass
            if inc is not None:                        # ganze Jahrestabelle (USA: Ersatz, wenn die SEC nichts hat, z. B. TSM mit 20-F)
                try:
                    fa = annual_fin(inc, tk.get_balance_sheet(), tk.get_cashflow(), info.get("financialCurrency"))
                    if fa:
                        row["fa"] = fa
                except Exception:
                    pass
            try:
                qh = quarter_revenue(tk.quarterly_income_stmt)
                if qh:
                    row["qh"] = qh
            except Exception:
                pass
            try:                                       # Monatskurse 12 Jahre → KGV/KUV-Verlauf über viele Jahre
                pm = monthly(tk.history(period="12y", interval="1mo", auto_adjust=False))
                if pm:
                    row["pm"] = pm
            except Exception:
                pass
            if (row.get("mc") or 0) >= 5e9:            # Hoch-/Abstufungen nur für größere Werte (dort gibt es sie)
                try:
                    ud = updowns(tk.upgrades_downgrades)
                    if ud:
                        row["ud"] = ud
                except Exception:
                    pass
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
    """Zusammenführen; Firmenbeschreibungen (_d) gehen getrennt nach desc.json (nur im Chart nachgeladen)."""
    raw, desc = {}, {}
    if prev and prev.exists() and (prev.parent / "desc.json").exists():
        try:
            desc = json.loads((prev.parent / "desc.json").read_text())
        except Exception:
            desc = {}
    if prev and prev.exists():                         # Fehlversuche: alten Stand behalten
        try:
            raw = {t: {k: v for k, v in r.items() if k not in ("sf",)} for t, r in json.loads(prev.read_text()).get("by", {}).items()}
        except Exception:
            raw = {}
    for p in parts:
        for t, r in json.loads(p.read_text()).items():
            if r.get("_d"):
                desc[t] = r.pop("_d")
            raw[t] = r
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
    return {"generated": time.strftime("%Y-%m-%d"), "n": len(by), "med": med, "all": allmed, "by": by, "_desc": desc}


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
        desc = res.pop("_desc", {})
        (out / "fund.json").write_text(json.dumps(res, separators=(",", ":"), allow_nan=False))
        (out / "desc.json").write_text(json.dumps(desc, separators=(",", ":"), ensure_ascii=False))
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
