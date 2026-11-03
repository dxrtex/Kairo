"""Positions-Analyse für das Depot: Trend, Momentum, Marken für Stop/Ziele, Chance, Markt.

Läuft im Scan für alle Aktien mit Detailseite (Watchlist, Treffer, Fast-Treffer). Das Depot selbst
kennt der Scan nicht – die App verknüpft die Analyse auf dem Gerät mit Einstieg und Stückzahl.

Wahrscheinlichkeit „Ziel vor Stop“: Kurs als Zufallspfad mit Drift (Brownsche Bewegung). Für Abstand a
nach unten, b nach oben, Tagesschwankung σ und Drift μ gilt
    P(oben zuerst) = (1 − e^(−2μa/σ²)) / (1 − e^(−2μ(a+b)/σ²)),   ohne Drift a / (a + b),
und die erwartete Dauer bis eine der Marken fällt ≈ a·b / σ² Handelstage. μ kommt aus der Steigung der
EMA 50 (gedämpft, begrenzt) – Trends halten oft, aber nicht immer.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .indicators import ema, pivot_highs, pivot_lows

MARKET = (("^GSPC", "S&P 500"), ("^NDX", "Nasdaq 100"), ("^GDAXI", "DAX"), ("^STOXX", "STOXX Europe 600"), ("^N225", "Nikkei 225"), ("^VIX", "VIX"))
SECTOR_ETF = {"Technology": "XLK", "Financial Services": "XLF", "Healthcare": "XLV", "Consumer Cyclical": "XLY",
              "Consumer Defensive": "XLP", "Energy": "XLE", "Industrials": "XLI", "Basic Materials": "XLB",
              "Utilities": "XLU", "Real Estate": "XLRE", "Communication Services": "XLC"}
SECTOR_DE = {"Technology": "Technologie", "Financial Services": "Finanzen", "Healthcare": "Gesundheit",
             "Consumer Cyclical": "Zyklischer Konsum", "Consumer Defensive": "Basiskonsum", "Energy": "Energie",
             "Industrials": "Industrie", "Basic Materials": "Rohstoffe", "Utilities": "Versorger",
             "Real Estate": "Immobilien", "Communication Services": "Kommunikation"}
# Branchen-ETFs (US) für die Sektor-Ansicht der App: Kürzel → (deutscher Name, Yahoo-Branchen der Einzelaktien)
INDUSTRY_ETF = {
    "SOXX": ("Halbleiter", ("Semiconductors", "Semiconductor Equipment & Materials")),
    "IGV": ("Software", ("Software - Application", "Software - Infrastructure")),
    "FDN": ("Internet", ("Internet Content & Information", "Internet Retail")),
    "IYZ": ("Telekom", ("Telecom Services",)),
    "ESPO": ("Games & Medien", ("Electronic Gaming & Multimedia", "Entertainment")),
    "XBI": ("Biotech", ("Biotechnology",)),
    "PPH": ("Pharma", ("Drug Manufacturers - General", "Drug Manufacturers - Specialty & Generic")),
    "IHI": ("Medizintechnik", ("Medical Devices", "Medical Instruments & Supplies", "Diagnostics & Research")),
    "IHF": ("Kliniken & Kassen", ("Healthcare Plans", "Medical Care Facilities")),
    "KBE": ("Großbanken", ("Banks - Diversified",)),
    "KRE": ("Regionalbanken", ("Banks - Regional",)),
    "KIE": ("Versicherungen", ("Insurance - Diversified", "Insurance - Life", "Insurance - Property & Casualty",
                               "Insurance - Reinsurance", "Insurance - Specialty", "Insurance Brokers")),
    "IAI": ("Broker & Börsen", ("Capital Markets", "Financial Data & Stock Exchanges")),
    "ITA": ("Luftfahrt & Verteidigung", ("Aerospace & Defense",)),
    "IYT": ("Transport & Logistik", ("Railroads", "Trucking", "Integrated Freight & Logistics", "Marine Shipping")),
    "JETS": ("Airlines", ("Airlines",)),
    "PAVE": ("Bau & Infrastruktur", ("Engineering & Construction", "Building Products & Equipment",
                                      "Infrastructure Operations", "Building Materials")),
    "ITB": ("Hausbau", ("Residential Construction",)),
    "XOP": ("Öl & Gas", ("Oil & Gas E&P", "Oil & Gas Integrated")),
    "OIH": ("Öl-Service", ("Oil & Gas Equipment & Services", "Oil & Gas Drilling")),
    "CRAK": ("Raffinerien", ("Oil & Gas Refining & Marketing",)),
    "AMLP": ("Pipelines", ("Oil & Gas Midstream",)),
    "URA": ("Uran", ("Uranium",)),
    "TAN": ("Solar", ("Solar",)),
    "GDX": ("Goldminen", ("Gold",)),
    "SIL": ("Silberminen", ("Silver",)),
    "COPX": ("Kupfer", ("Copper",)),
    "PICK": ("Metalle & Bergbau", ("Other Industrial Metals & Mining", "Steel", "Aluminum", "Other Precious Metals & Mining")),
    "XRT": ("Einzelhandel", ("Specialty Retail", "Department Stores", "Discount Stores", "Apparel Retail",
                             "Home Improvement Retail", "Luxury Goods")),
    "PEJ": ("Freizeit & Reisen", ("Lodging", "Resorts & Casinos", "Travel Services", "Leisure", "Restaurants")),
    "CARZ": ("Autos", ("Auto Manufacturers", "Auto Parts")),
    "PBJ": ("Lebensmittel & Getränke", ("Packaged Foods", "Beverages - Non-Alcoholic", "Beverages - Brewers",
                                        "Beverages - Wineries & Distilleries", "Confectioners", "Farm Products")),
    "VNQ": ("REITs", ()),
    "PHO": ("Wasser", ("Utilities - Regulated Water",)),
}
# Themen (11/2026): quer zu den Yahoo-Branchen (Cybersecurity steckt dort z. B. in „Software“), deshalb mit festen Hauptwerten
# für die Liste „stärkste Aktien“. Kurse der ETFs für Rendite, Rang-Verlauf und Rotations-Bild wie bei den Branchen.
THEME_ETF = {
    "CIBR": ("Cybersecurity", ("CRWD", "PANW", "FTNT", "ZS", "NET", "OKTA", "CHKP", "CYBR", "S", "TENB", "QLYS", "RPD", "AKAM", "GEN", "VRNS")),
    "SKYY": ("Cloud", ("SNOW", "DDOG", "MDB", "NOW", "CRM", "WDAY", "NET", "TEAM", "HUBS", "ESTC", "TWLO", "AMZN", "MSFT", "GOOGL", "ORCL")),
    "BOTZ": ("KI & Robotik", ("NVDA", "ISRG", "PATH", "TER", "CGNX", "ROK", "SYM", "PLTR", "AI", "ZBRA", "6954.T", "6861.T", "ABBN.SW")),
    "IPAY": ("Zahlungen & Fintech", ("V", "MA", "PYPL", "FI", "FIS", "GPN", "AXP", "XYZ", "AFRM", "TOST", "COIN", "SOFI", "FOUR", "ADYEN.AS")),
    "GRID": ("Stromnetz & Rechenzentren", ("ETN", "PWR", "VRT", "GEV", "HUBB", "NVT", "POWL", "ANET", "SU.PA", "ABBN.SW", "SIE.DE", "PRY.MI")),
    "NLR": ("Kernkraft", ("CEG", "VST", "CCJ", "BWXT", "OKLO", "SMR", "LEU", "NXE", "TLN")),
    "LIT": ("Lithium & Batterien", ("ALB", "SQM", "TSLA", "LAC", "QS", "SLDP", "ENS", "6752.T", "PLS.AX", "MIN.AX")),
    "REMX": ("Seltene Erden", ("MP", "LYC.AX", "ILU.AX", "USAR", "ALB", "SQM")),
    "UFO": ("Raumfahrt", ("RKLB", "ASTS", "IRDM", "VSAT", "GSAT", "PL", "LUNR", "SATS", "LMT", "NOC")),
    "SLX": ("Stahl", ("NUE", "STLD", "CLF", "RS", "CMC", "MT", "TX", "VALE", "MT.AS", "TKA.DE", "SZG.DE")),
    "MOO": ("Agrar & Dünger", ("DE", "CTVA", "NTR", "CF", "MOS", "ADM", "ZTS", "TSN", "BG", "AGCO", "CNH", "FMC", "YAR.OL", "BAYN.DE")),
}
# Europa (11/2026): iShares STOXX Europe 600 Sektor-ETFs (Xetra), Maßstab STOXX 600. „flt“ = welche Aktien aus dem Scan
# (Region Europa) beim Antippen gezeigt werden – über den Sektor (sec, deutsch) oder den Branchen-ETF (ig) der Aktie.
EU_SECTOR_ETF = {
    "EXV1.DE": ("Banken", {"ig": ["KBE", "KRE"]}), "EXH5.DE": ("Versicherungen", {"ig": ["KIE"]}), "EXH2.DE": ("Finanzdienste", {"ig": ["IAI"]}),
    "EXV3.DE": ("Technologie", {"sec": ["Technologie"]}), "EXV4.DE": ("Gesundheit", {"sec": ["Gesundheit"]}), "EXH1.DE": ("Öl & Gas", {"sec": ["Energie"]}),
    "EXV2.DE": ("Telekom", {"ig": ["IYZ"]}), "EXH6.DE": ("Medien", {"ig": ["ESPO"]}), "EXH4.DE": ("Industrie", {"sec": ["Industrie"]}),
    "EXV8.DE": ("Bau & Material", {"ig": ["PAVE", "ITB"]}), "EXV6.DE": ("Rohstoffe & Bergbau", {"ig": ["PICK", "GDX", "SIL", "COPX"]}),
    "EXV7.DE": ("Chemie", {"sec": ["Rohstoffe"]}), "EXV5.DE": ("Autos", {"ig": ["CARZ"]}), "EXH3.DE": ("Lebensmittel & Getränke", {"ig": ["PBJ"]}),
    "EXH7.DE": ("Konsumgüter", {"sec": ["Basiskonsum"]}), "EXH8.DE": ("Einzelhandel", {"ig": ["XRT"]}), "EXV9.DE": ("Reisen & Freizeit", {"ig": ["PEJ", "JETS"]}),
    "EXH9.DE": ("Versorger", {"sec": ["Versorger"]}), "EXI5.DE": ("Immobilien", {"sec": ["Immobilien"]}),
}
_IND_MAP = {name: k for k, (_, names) in INDUSTRY_ETF.items() for name in names}
PERIODS = (("d1", 1), ("w1", 5), ("m1", 21), ("m3", 63))


def rank_history(rows: list[dict], hist: dict, weeks: int = 12, look: int = 21) -> None:
    """Rang je ETF (1 = stärkste 1-Monats-Rendite) an jedem der letzten `weeks` Wochenenden + heute → x["rh"] (alt → neu).
    Zeigt, ob Geld dauerhaft umschichtet (Rang steigt Woche für Woche) oder nur kurz."""
    closes = {}
    for x in rows:
        df = hist.get(x["k"])
        if df is not None:
            closes[x["k"]] = df["Close"].dropna()
    if len(closes) < 3:
        return
    C = pd.DataFrame(closes).ffill().dropna(how="all")
    if len(C) < look + 5 * weeks + 1:
        return
    pts = [len(C) - 1 - 5 * w for w in range(weeks, -1, -1)]
    for i in pts:
        r = (C.iloc[i] / C.iloc[i - look] - 1).rank(ascending=False, method="min")
        for x in rows:
            v = r.get(x["k"])
            x.setdefault("rh", []).append(int(v) if v == v and v is not None else None)


def rotation(rows: list[dict], hist: dict, bench: str = "^GSPC", tail: int = 5, hot_n: int = 0) -> None:
    """Rotations-Bild (wie ein Relative Rotation Graph) – beschreibt, sagt NICHT vorher (Backtest 2008–2026: kein Quadrant
    hatte danach einen Vorteil, siehe tools/research/rotation.py).
    x["rrg"] = {"r": relative Stärke ggü. S&P 500 im Verhältnis zum 13-Wochen-Schnitt (100 = Schnitt),
               "m": Schwung = Änderung von r über 4 Wochen (100 = keine Änderung), "q": Quadrant, "tail": letzte Wochen (alt → neu)}.
    hot_n > 0: die hot_n Zeilen mit der höchsten Mehrrendite über 4 Wochen bekommen x["hot"] (nur wenn > 0) – solche Sektoren
    liefen seit 2016 in den folgenden 13 Wochen im Schnitt ~1 % schlechter als der Markt (Hinterherkaufen lohnt nicht)."""
    b = hist.get(bench)
    if b is None or len(b) < 120:
        return
    bw = b["Close"].dropna().resample("W-FRI").last()
    rel4 = {}
    for x in rows:
        df = hist.get(x["k"])
        if df is None or len(df) < 120:
            continue
        w = df["Close"].dropna().resample("W-FRI").last()
        rs = (w / bw).dropna()
        if len(rs) < 22:
            continue
        ratio = 100 * rs / rs.rolling(13).mean()
        mom = 100 * ratio / ratio.shift(4)
        pts = [(round(float(r), 2), round(float(m), 2)) for r, m in zip(ratio.iloc[-tail:], mom.iloc[-tail:]) if r == r and m == m]
        if not pts:
            continue
        r, m = pts[-1]
        q = "leading" if r >= 100 and m >= 100 else "weakening" if r >= 100 else "improving" if m >= 100 else "lagging"
        x["rrg"] = {"r": r, "m": m, "q": q, "tail": [list(p) for p in pts]}
        if len(rs) > 4:
            rel4[x["k"]] = float(rs.iloc[-1] / rs.iloc[-5] - 1)
    if hot_n and len(rel4) >= 5:
        for k in sorted(rel4, key=lambda k: -rel4[k])[:hot_n]:
            if rel4[k] > 0:
                next(x for x in rows if x["k"] == k)["hot"] = round(rel4[k], 4)


def industry_group(industry: str | None) -> str | None:
    """Yahoo-Branche einer Aktie → Kürzel des Branchen-ETFs (oder None)."""
    if not industry or not isinstance(industry, str):
        return None
    return _IND_MAP.get(industry) or ("VNQ" if industry.startswith("REIT") else None)


def perf_row(df: pd.DataFrame, lag: int = 5) -> dict:
    """Renditen über 1T/1W/1M/3M/seit Jahresanfang – heute und (p) dieselben Zeiträume vor `lag` Handelstagen,
    damit die App Rangwechsel („Rotation“) zeigen kann."""
    c = df["Close"].dropna()
    v = c.to_numpy(float)

    def ret(end: int, n: int):
        i, j = len(v) - 1 - end, len(v) - 1 - end - n
        return round(float(v[i] / v[j] - 1), 4) if j >= 0 and v[j] else None

    def ytd(end: int):
        if len(v) <= end:
            return None
        last = c.index[len(v) - 1 - end]
        prev = c[c.index.year < last.year]
        return round(float(v[len(v) - 1 - end] / prev.iloc[-1] - 1), 4) if len(prev) and prev.iloc[-1] else None

    out = {k: ret(0, n) for k, n in PERIODS}
    out["ytd"] = ytd(0)
    out["p"] = {**{k: ret(1 if k == "d1" else lag, n) for k, n in PERIODS}, "ytd": ytd(lag)}
    return out


EUROPE = (".PA", ".AS", ".MI", ".MC", ".CO", ".ST", ".SW", ".L", ".HE", ".OL", ".BR", ".VI", ".LS", ".IR")


def _p(x: float) -> str:
    """Prozent mit Vorzeichen, deutsches Komma nicht nötig (ganze Zahlen)."""
    return f"{x * 100:+.0f} %"


def benchmark_for(ticker: str) -> str:
    if ticker.endswith(".DE"):
        return "^GDAXI"
    if ticker.endswith(EUROPE):
        return "^STOXX"
    return "^GSPC"


def _chg(c: np.ndarray, days: int) -> float | None:
    return float(c[-1] / c[-1 - days] - 1) if len(c) > days and c[-1 - days] else None


def trend_state(df: pd.DataFrame) -> dict:
    c = df["Close"].to_numpy(float)
    e20, e50, e200 = (ema(df["Close"], n).to_numpy(float) for n in (20, 50, 200))
    up = int(c[-1] > e50[-1]) + int(c[-1] > e200[-1]) + int(e50[-1] > e50[-21])
    tone = "green" if up == 3 else "red" if up == 0 else "yellow"
    label = {3: "Aufwärtstrend", 2: "leicht positiv", 1: "angeschlagen", 0: "Abwärtstrend"}[up]
    return {"c": round(float(c[-1]), 2), "d1": _chg(c, 1), "chg1m": _chg(c, 21), "chg3m": _chg(c, 63), "tone": tone, "label": label,
            "above50": bool(c[-1] > e50[-1]), "above200": bool(c[-1] > e200[-1])}


def market_context(hist: dict[str, pd.DataFrame]) -> dict:
    out = {}
    for t, name in MARKET:
        df = hist.get(t)
        if df is None or len(df) < 210:
            continue
        s = trend_state(df)
        s["name"] = name
        if t == "^VIX":
            v = s["c"]
            s.update(tone="green" if v < 18 else "yellow" if v < 25 else "red",
                     label="ruhig" if v < 18 else "erhöht" if v < 25 else "Angst/Stress")
        out[t] = s
    secs = []                                         # Branchen (US-Sektor-ETFs) für den Markt-Überblick in der App
    for name, etf in SECTOR_ETF.items():
        df = hist.get(etf)
        if df is None or len(df) < 210:
            continue
        st = trend_state(df)
        secs.append({"k": etf, "n": SECTOR_DE.get(name, name), "d1": st["d1"], "chg1m": st["chg1m"], "chg3m": st["chg3m"],
                     "tone": st["tone"], "label": st["label"], **perf_row(df)})
    if secs:
        rank_history(secs, hist)
        rotation(secs, hist, hot_n=2)                 # oberstes Fünftel der 11 Sektoren nach 4-Wochen-Mehrrendite
        out["sectors"] = sorted(secs, key=lambda x: -(x["chg1m"] if x["chg1m"] is not None else -9))
    inds = []                                         # Branchen-ETFs (feiner als die 11 Sektoren)
    for etf, (name, _) in INDUSTRY_ETF.items():
        df = hist.get(etf)
        if df is None or len(df) < 70:
            continue
        st = trend_state(df) if len(df) >= 210 else {}
        inds.append({"k": etf, "n": name, "tone": st.get("tone"), "label": st.get("label"), **perf_row(df)})
    if inds:
        rank_history(inds, hist)
        rotation(inds, hist)
        out["industries"] = sorted(inds, key=lambda x: -(x["m1"] if x["m1"] is not None else -9))
    eus = []                                          # Europa: STOXX-600-Sektoren gegen den STOXX 600
    for etf, (name, flt) in EU_SECTOR_ETF.items():
        df = hist.get(etf)
        if df is None or len(df) < 70:
            continue
        st = trend_state(df) if len(df) >= 210 else {}
        eus.append({"k": etf, "n": name, "flt": flt, "tone": st.get("tone"), "label": st.get("label"), **perf_row(df)})
    if eus:
        rank_history(eus, hist)
        rotation(eus, hist, bench="^STOXX")           # ohne „Heißgelaufen“: der Befund ist nur für US-Sektoren getestet
        out["sectors_eu"] = sorted(eus, key=lambda x: -(x["m1"] if x["m1"] is not None else -9))
    ths = []                                          # Themen (Cybersecurity, Cloud, KI …) mit festen Hauptwerten
    for etf, (name, mem) in THEME_ETF.items():
        df = hist.get(etf)
        if df is None or len(df) < 70:
            continue
        st = trend_state(df) if len(df) >= 210 else {}
        ths.append({"k": etf, "n": name, "mem": list(mem), "tone": st.get("tone"), "label": st.get("label"), **perf_row(df)})
    if ths:
        rank_history(ths, hist)
        rotation(ths, hist)
        out["themes"] = sorted(ths, key=lambda x: -(x["m1"] if x["m1"] is not None else -9))
    spx, vix = out.get("^GSPC"), out.get("^VIX")
    if spx and vix:
        good = spx["above50"] and vix["c"] < 20
        bad = (not spx["above50"] and not spx["above200"]) or vix["c"] >= 28
        out["regime"] = {"tone": "green" if good else "red" if bad else "yellow",
                         "label": "Rückenwind (Risk-on)" if good else "Gegenwind (Risk-off)" if bad else "gemischt"}
    return out


def _rel(levels: list[tuple[float, str]], close: float, tol: float = 0.015) -> list[dict]:
    """Nahe beieinander liegende Marken zusammenfassen (± 1,5 %), Quellen bündeln."""
    out: list[dict] = []
    for p, src in sorted(levels):
        if out and abs(p / out[-1]["p"] - 1) <= tol:
            g = out[-1]
            g["n"] += 1
            g["p"] = (g["p"] * (g["n"] - 1) + p) / g["n"]
            if src not in g["src"]:
                g["src"].append(src)
        else:
            out.append({"p": p, "src": [src], "n": 1})
    return out


def _prob_up(a: float, b: float, sigma: float, mu: float) -> float:
    if a <= 0:
        return 0.0
    if b <= 0:
        return 1.0
    k = 2 * mu / (sigma * sigma)
    if abs(k * (a + b)) < 1e-6:
        return a / (a + b)
    return float((1 - math.exp(-k * a)) / (1 - math.exp(-k * (a + b))))


def _p_touch(b: float, sigma: float, mu: float, days: int) -> float:
    """Wahrscheinlichkeit, dass der Kurs innerhalb von `days` Handelstagen mindestens einmal um b steigt
    (Maximum einer Brownschen Bewegung mit Drift, Spiegelungsprinzip)."""
    if b <= 0:
        return 1.0
    s = sigma * math.sqrt(days)
    phi = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
    k = min(50.0, 2 * mu * b / (sigma * sigma))
    return float(min(1.0, phi((-b + mu * days) / s) + math.exp(k) * phi((-b - mu * days) / s)))


def swing_levels(df: pd.DataFrame, close: float, atr: float, max_levels: int = 4) -> list[dict]:
    """Relevante Hochs über dem Kurs („Treppe fallender Hochs“), nächstes zuerst.

    Gerechnet auf Schlusskursen (wie im Linienchart):
    1. Kandidat: höchster Schluss im Fenster ± 5 Tage (mind. 5 Tage alt), der seitdem NIE überschritten wurde.
    2. Gipfel einer eigenen Erholungswelle: mind. 15 Handelstage nach dem vorigen (älteren, höheren) relevanten
       Hoch, und der Kurs ist vom Tief dazwischen mind. 3,5 % bzw. 0,8 Tagesschwankungen (ATR) gestiegen.
    3. Hochs, die weniger als 4 % auseinanderliegen, bilden eine Zone (Doppel-/Mehrfachhoch).
    """
    # Schlusskurse wie im Linienchart – einzelne Tagesspitzen (Dochte) zählen nicht
    h = l = df["Close"].to_numpy(float)
    dates = df.index
    n = len(h)
    if n < 15:
        return []
    after = np.append(np.maximum.accumulate(h[::-1])[::-1][1:], -np.inf)   # höchstes Hoch NACH Tag i
    cand = [i for i in range(n - 5) if h[i] == h[max(0, i - 5):i + 6].max() and h[i] > after[i] and h[i] > close]
    min_rise = max(0.035, 0.8 * atr / close)
    kept: list[int] = []
    for i in cand:                                   # alt → neu (Hochs fallen)
        if kept and i - kept[-1] < 15:               # noch dieselbe Bewegung wie das vorige Hoch
            continue
        start = kept[-1] + 1 if kept else max(0, i - 120)
        if i - start < 2:
            continue
        low = float(l[start:i].min())
        if (h[i] - low) / h[i] >= min_rise:
            kept.append(i)
    zones: list[dict] = []
    for i in reversed(kept):                         # neu → alt, nahe Hochs zu Zonen bündeln
        if zones and h[i] <= zones[-1]["lo"] * 1.04:
            z = zones[-1]
            z["hi"], z["idx"] = max(z["hi"], float(h[i])), z["idx"] + [i]
        else:
            zones.append({"lo": float(h[i]), "hi": float(h[i]), "idx": [i]})
    out = []
    for z in zones[:max_levels]:
        d = sorted(dates[j] for j in z["idx"])
        when = f"{d[0]:%d.%m.%Y}" if len(d) == 1 else f"{d[0]:%d.%m.%Y} – {d[-1]:%d.%m.%Y}"
        out.append({"p": z["lo"], "hi": z["hi"], "date": str(d[-1].date()),
                    "src": ("Hoch vom " if len(d) == 1 else f"{len(d)} Hochs, ") + when})
    return out


def take_profits(df: pd.DataFrame, close: float, atr: float, sigma: float, mu: float, ath: dict | None) -> dict:
    """Take-Profit-Zonen: relevante Hochs über dem Kurs (siehe swing_levels) und Allzeithoch,
    je mit Chance, sie in 3 / 6 Monaten mindestens einmal zu erreichen."""
    h, dates = df["High"].to_numpy(float), df.index
    top = ath or {"p": float(h.max()), "date": str(dates[int(h.argmax())].date()), "full": False}
    allt = {"p": float(top["p"]), "date": top["date"], "src": "Allzeithoch" if top.get("full", True) else "2-Jahres-Hoch"}
    levels = swing_levels(df, close, atr)
    if levels and levels[-1]["hi"] >= allt["p"] * 0.95:      # oberste Zone = Allzeithoch → nicht doppelt zeigen
        levels[-1]["ath"] = True
        allt = None
    def enrich(t):
        b = t["p"] - close
        return {**t, "p": round(t["p"], 4), "hi": round(t.get("hi", t["p"]), 4), "pct": b / close,
                "p3m": round(_p_touch(b, sigma, mu, 63), 2), "p6m": round(_p_touch(b, sigma, mu, 126), 2)}
    out = {"levels": [enrich(t) for t in levels]}
    if allt and allt["p"] > close:
        out["ath"] = enrich(allt)
    return out


def analyze(df: pd.DataFrame, res, ath: dict | None = None) -> dict:
    """Kompakte Analyse einer Aktie aus Long-Sicht."""
    f, z = res.flags, res.zone
    c, h, l = (df[k].to_numpy(float) for k in ("Close", "High", "Low"))
    n, close = len(c), float(c[-1])
    e20, e50, e200 = (ema(df["Close"], k).to_numpy(float) for k in (20, 50, 200))
    atr = float(f.get("atr") or (h[-14:] - l[-14:]).mean())
    dates = df.index

    # ---------- Marken ----------
    sup, resi = [], []
    look = max(0, n - 250)
    for i in pivot_lows(df["Low"], 3):
        if i >= look:
            (sup if l[i] < close else resi).append((float(l[i]), f"Tief {dates[i]:%d.%m.}"))
    for i in pivot_highs(df["High"], 3):
        if i >= look:
            (resi if h[i] > close else sup).append((float(h[i]), f"Hoch {dates[i]:%d.%m.}"))
    for v, name in ((e50[-1], "EMA 50"), (e200[-1], "EMA 200")):
        (sup if v < close else resi).append((float(v), name))
    hi52 = float(h[-250:].max())
    if hi52 > close:
        resi.append((hi52, "52-W.-Hoch"))
    fib = z.get("fib") or None
    if fib:
        for k, lab in (("0.382", "Fib 0,382"), ("0.618", "Fib 0,618"), ("0.79", "Fib 0,79")):
            v = fib["levels"].get(k)
            if v:
                (sup if v < close else resi).append((float(v), lab))
    if z.get("support") and z["support"]["center"] < close:
        sup.append((float(z["support"]["center"]), f"Support-Zone ({z['support']['touches']}×)"))
    sup_g = [g for g in _rel(sup, close) if close - g["p"] >= 0.3 * atr]
    res_g = [g for g in _rel(resi, close) if g["p"] - close >= 0.3 * atr]
    sup_g.sort(key=lambda g: -g["p"])
    res_g.sort(key=lambda g: g["p"])

    # Stop: unter der nächsten Unterstützung, die mind. 1 ATR entfernt ist (Rauschen nicht abfischen)
    s_cand = next((g for g in sup_g if close - g["p"] >= 1.0 * atr), None)
    stop = (s_cand["p"] - 0.25 * atr) if s_cand else close - 2.5 * atr
    stop_src = " + ".join(s_cand["src"][:2]) if s_cand else "2,5 × ATR"
    t_c = [g for g in res_g if g["p"] - close >= 1.0 * atr]
    tp1 = t_c[0] if t_c else None
    tp2 = next((g for g in t_c[1:] if g["p"] - tp1["p"] >= 1.0 * atr), None) if tp1 else None
    # Ziele aus der Fib-Extension, wenn oben keine Marke mehr liegt (z. B. am Allzeithoch)
    swing_lo = float(l[-120:].min())
    ext = lambda x: hi52 + (x - 1) * (hi52 - swing_lo)
    if not tp1:
        tp1 = {"p": max(ext(1.272), close + 2 * atr), "src": ["Fib-Extension 1,272"]}
    if not tp2:
        tp2 = {"p": max(ext(1.618), tp1["p"] + 1.5 * atr), "src": ["Fib-Extension 1,618"]}

    # ---------- Wahrscheinlichkeit & Dauer ----------
    rets = np.diff(np.log(c[-61:]))
    sigma = float(np.std(rets, ddof=1)) * close if len(rets) > 5 else atr / 1.4
    slope = (e50[-1] - e50[-21]) / 20
    mu = float(np.clip(0.3 * slope, -0.05 * sigma, 0.05 * sigma))   # höchstens ~ Sharpe 0,8 p. a.
    a = close - stop

    def target(g):
        b = g["p"] - close
        p = _prob_up(a, b, sigma, mu)
        return {"p": round(g["p"], 4), "src": " + ".join(g["src"][:2]), "pct": b / close, "prob": round(p, 2),
                "days": int(round(min(250, a * b / (sigma * sigma)))), "crv": round(b / a, 2) if a > 0 else None}

    # ---------- Faktoren ----------
    fac = []
    up = int(close > e20[-1]) + int(close > e50[-1]) + int(close > e200[-1]) + int(e50[-1] > e50[-21])
    fac.append({"k": "trend", "l": "Trend", "s": [-2, -1, 0, 1, 2][up],
                "t": {4: "Kurs über EMA 20/50/200, EMA 50 steigt", 3: "überwiegend aufwärts", 2: "gemischt",
                      1: "überwiegend abwärts", 0: "unter allen EMAs, EMA 50 fällt"}[up]})
    mh, rising = f.get("macd_hist") or 0, f.get("macd_rising")
    slope_up = (f.get("macd_slope") or 0) > 0
    fac.append({"k": "macd", "l": "MACD", "s": 1 if mh > 0 and slope_up else -1 if mh < 0 and not slope_up else 0,
                "t": ("Histogramm grün" if mh > 0 else "Histogramm rot") + (", steigt" if (f.get("macd_slope") or 0) > 0 else ", fällt")})
    r = f.get("rsi") or 50
    fac.append({"k": "rsi", "l": "RSI", "s": -1 if r >= 75 or r < 35 else 1 if 45 <= r <= 68 else 0,
                "t": f"{r:.0f} – " + ("überkauft, Rücksetzer-Gefahr" if r >= 75 else "heiß" if r >= 68 else
                                      "gesundes Momentum" if r >= 45 else "schwach" if r >= 35 else "überverkauft, Erholung möglich")})
    mbi_g, xa = f.get("mbi_green"), f.get("mbi_x_age")
    fac.append({"k": "mbi", "l": "MBI", "s": 1 if mbi_g else -1,
                "t": ("Kaufdruck überwiegt" if mbi_g else "Verkaufsdruck überwiegt")
                     + (f", grünes X vor {xa} T." if xa is not None and xa <= 15 else "")})
    dv = f.get("divergence")
    if dv:
        fac.append({"k": "div", "l": "RSI-Divergenz", "s": 1, "t": f"bullisch ({dv['kind']}) am {pd.Timestamp(dv['t2']):%d.%m.}"})
    H = z.get("H")
    if H and close < H:
        dd = (H - close) / H
        if fib and fib.get("retracement") is not None and dd >= 0.08:
            rt = fib["retracement"]
            fac.append({"k": "fib", "l": "Fibonacci", "s": 1 if 0.5 <= rt <= 0.79 and fib.get("valid") else -1 if rt > 0.886 else 0,
                        "t": f"{dd * 100:.0f} % unter dem Hoch, Retracement {rt:.2f}".replace(".", ",")
                             + (" – in der Kaufzone" if 0.618 <= rt <= 0.79 else " – unter 0,886, Impuls gebrochen" if rt > 0.886 else "")})
    vola = f.get("volatility")
    out = {"c": close, "atr": atr, "sigma": sigma, "vola": vola,
           "stop": {"p": round(stop, 4), "src": stop_src, "pct": (stop - close) / close},
           "tp": [target(tp1), target(tp2)], "fac": fac,
           "sup": [{"p": round(g["p"], 4), "src": " + ".join(g["src"][:2])} for g in sup_g[:3]],
           "res": [{"p": round(g["p"], 4), "src": " + ".join(g["src"][:2])} for g in res_g[:3]],
           "chg1m": _chg(c, 21), "chg3m": _chg(c, 63), "bench": benchmark_for(res.ticker),
           "tps": take_profits(df, close, atr, sigma, mu, ath)}
    return out


def add_context(a: dict, market: dict, sector: str | None, sector_hist: dict, earnings: str | None, today) -> None:
    """Relative Stärke, Branche, Markt und Termine als weitere Faktoren anhängen; Gesamturteil bilden."""
    b = market.get(a["bench"])
    if b and a.get("chg3m") is not None and b.get("chg3m") is not None:
        d = a["chg3m"] - b["chg3m"]
        a["fac"].append({"k": "rs", "l": "Relative Stärke", "s": 1 if d > 0.05 else -1 if d < -0.05 else 0,
                         "t": f"3 Mon. {_p(a['chg3m'])} vs. {b['name']} {_p(b['chg3m'])}"})
    etf = SECTOR_ETF.get(sector or "")
    sh = sector_hist.get(etf) if etf else None
    if sh is not None and len(sh) > 210:
        s = trend_state(sh)
        a["fac"].append({"k": "sector", "l": "Branche", "s": {"green": 1, "yellow": 0, "red": -1}[s["tone"]],
                         "t": f"{SECTOR_DE.get(sector, sector)} ({etf}): {s['label']}, 1 Mon. {_p(s['chg1m'])}"})
    reg = market.get("regime")
    if reg:
        a["fac"].append({"k": "market", "l": "Gesamtmarkt", "s": {"green": 1, "yellow": 0, "red": -1}[reg["tone"]],
                         "t": reg["label"] + (f", VIX {market['^VIX']['c']:.0f}" if "^VIX" in market else "")})
    if earnings:
        days = (pd.Timestamp(earnings).date() - today).days
        if 0 <= days <= 21:
            a["fac"].append({"k": "earn", "l": "Quartalszahlen", "s": -1 if days <= 7 else 0,
                             "t": f"in {days} Tagen ({pd.Timestamp(earnings):%d.%m.}) – Kurssprung möglich"})
        a["earn"] = earnings


def finalize(a: dict) -> None:
    """Gesamturteil 0–100 aus den gewichteten Faktoren (+1 / 0 / −1, Trend −2 … +2)."""
    weights = {"trend": 2.0, "macd": 1.0, "rsi": 0.75, "mbi": 1.0, "div": 0.75, "fib": 0.75, "rs": 1.0,
               "sector": 0.5, "market": 1.0, "earn": 0.5}
    tot = sum(weights.get(x["k"], 0.5) * x["s"] for x in a["fac"])
    mx = sum(weights.get(x["k"], 0.5) * (2 if x["k"] == "trend" else 1) for x in a["fac"])
    a["score"] = round(50 + 50 * tot / mx) if mx else 50
