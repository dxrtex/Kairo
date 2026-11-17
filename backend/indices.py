"""Index-Mitglieder für die Heatmap (Wunsch 16.11.2026: „Index: S&P 500 ▾“ wie bei Profi-Tools statt „die 220 größten der Region“).

Quelle: die Bestandteil-Tabellen der Wikipedia-Artikel (kostenlos, werden bei Index-Änderungen zeitnah gepflegt). Jede Tabelle
wird an der Spalte Ticker/Symbol/Code erkannt; die Kürzel werden auf Yahoo-Schreibweise gebracht und mit dem Kairo-Scan
abgeglichen – gibt es das Kürzel nicht, hilft der Firmenname. Nur Aktien, die Kairo kennt, landen in der Liste; wie viele
fehlen, steht mit in der Datei („498 von 503“).

Fällt eine Quelle aus oder sieht die Tabelle unplausibel aus (zu wenige Treffer), bleibt der letzte gute Stand von der Seite.

Ausgabe site/data/indices.json: {"generated", "idx": {key: {"n": Name, "t": [Ticker], "total": Mitglieder laut Quelle}}}
"""
from __future__ import annotations

import io
import json
import re
import urllib.request
from datetime import datetime, timezone

import pandas as pd

PAGES = "https://dxrtex.github.io/Kairo/data/indices.json"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"}
# key, Anzeige, Quelle, Yahoo-Endung für nackte Kürzel, (min., max.) Mitglieder in der Tabelle, Mindestanteil im Kairo-Scan
INDICES = [
    ("sp500", "S&P 500", "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", "", (480, 520), .9),
    # Nasdaq 100 und Nikkei 225 (17.11.2026): die englischen Artikel führen keine Bestandteil-Tabelle mehr – deutsche Wikipedia
    ("ndx", "Nasdaq 100", "https://de.wikipedia.org/wiki/NASDAQ-100", "", (95, 110), .9),
    ("dax", "DAX 40", "https://en.wikipedia.org/wiki/DAX", ".DE", (38, 42), .85),
    ("sx5e", "Euro Stoxx 50", "https://en.wikipedia.org/wiki/EURO_STOXX_50", None, (48, 52), .8),
    ("n225", "Nikkei 225", "https://de.wikipedia.org/wiki/Nikkei_225", ".T", (215, 235), .7),
    # Dow Jones: die Wikipedia-Tabellen haben nur Firmennamen (ohne Kürzel) – Zuordnung über den Namen, nur US-Aktien
    ("dji", "Dow Jones", "https://de.wikipedia.org/wiki/Dow_Jones_Industrial_Average", "", (29, 31), .8),
    # weitere Indizes (17.11.2026, Tabellen per Testlauf geprüft): Nebenwerte Deutschland, Großbritannien, Frankreich, Schweiz, Hongkong
    ("mdax", "MDAX", "https://en.wikipedia.org/wiki/MDAX", ".DE", (48, 54), .75),
    ("tecdax", "TecDAX", "https://de.wikipedia.org/wiki/TecDAX", ".DE", (28, 32), .75),
    ("ukx", "FTSE 100", "https://en.wikipedia.org/wiki/FTSE_100_Index", ".L", (95, 105), .75),
    ("cac", "CAC 40", "https://en.wikipedia.org/wiki/CAC_40", ".PA", (38, 42), .8),
    ("smi", "SMI", "https://en.wikipedia.org/wiki/Swiss_Market_Index", ".SW", (18, 22), .75),
    ("hsi", "Hang Seng", "https://en.wikipedia.org/wiki/Hang_Seng_Index", ".HK", (70, 100), .7),
]
NAME_ONLY = {"dji"}                       # Indizes, deren Tabelle nur Namen hat
TICK_COL = re.compile(r"^(ticker|symbol|code|ticker symbol)$", re.I)
NAME_COL = re.compile(r"^(company|security|name|constituent|company name|unternehmen)(\s*\(.*\))?$", re.I)   # auch „Name (A–Z)“
EX_SUFFIX = {"xetra": ".DE", "frankfurt": ".DE", "fwb": ".DE", "euronext paris": ".PA", "paris": ".PA", "euronext amsterdam": ".AS",
             "amsterdam": ".AS", "euronext brussels": ".BR", "brussels": ".BR", "borsa italiana": ".MI", "milan": ".MI",
             "bme": ".MC", "madrid": ".MC", "helsinki": ".HE", "euronext dublin": ".IR", "dublin": ".IR", "lisbon": ".LS", "sehk": ".HK"}


def norm_name(s: str) -> str:
    s = str(s or "").lower()
    s = re.sub(r"\b(inc|incorporated|corp|corporation|co|com|company|ag|se|sa|nv|n\.v|plc|ltd|limited|holdings?|group|the|class [a-z]|spa|s\.p\.a|kgaa|& co)\b", " ", s)
    return re.sub(r"[^a-z0-9]", "", s)[:18]


def _tables(url: str) -> list[pd.DataFrame]:
    html = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read().decode("utf-8", "replace")
    return pd.read_html(io.StringIO(html))


def pick_table(tables: list[pd.DataFrame], lo: int, hi: int, by_name: bool = False) -> pd.DataFrame | None:
    """Die Bestandteil-Tabelle: hat eine Ticker-Spalte (bzw. nur Namen) und passende Zeilenzahl (bei mehreren: die mit den meisten Zeilen)."""
    best = None
    col_ok = (lambda c: NAME_COL.match(c)) if by_name else (lambda c: TICK_COL.match(c))
    for t in tables:
        cols = [re.sub(r"\[.*?\]", "", str(c[-1] if isinstance(c, tuple) else c)).strip() for c in t.columns]   # „Symbol[9]“ → Symbol
        if not any(col_ok(c) for c in cols) or not lo <= len(t) <= hi:
            continue
        t = t.copy(); t.columns = cols
        if best is None or len(t) > len(best):
            best = t
    return best


def candidates(raw: str, suffix: str | None) -> list[str]:
    """Mögliche Yahoo-Kürzel zu einem Tabellen-Kürzel („BRK.B“ → BRK-B, „ADS“ → ADS.DE, „XETRA: SAP“ → SAP.DE, „7203“ → 7203.T)."""
    s = str(raw or "").strip().upper().replace(" ", " ")
    if not s or s == "NAN":
        return []
    s = re.sub(r"^(\d+)\.0$", r"\1", s)              # Nikkei-Codes kommen als Zahl („9983.0“)
    if suffix == ".HK" or s.startswith("SEHK"):     # Hongkong: „SEHK: 5“ → 0005.HK (vierstellig)
        m = re.search(r"(\d+)$", s)
        return [m.group(1).zfill(4) + ".HK"] if m else []
    out: list[str] = []
    m = re.match(r"^([A-Z .]+):\s*([A-Z0-9.\-]+)$", s)
    if m:
        ex = EX_SUFFIX.get(m.group(1).strip().lower())
        sym = m.group(2)
        if ex:
            out.append(sym.split(".")[0] + ex)
        s = sym
    if suffix == "":                       # USA: Punkt in Klassen-Aktien → Bindestrich
        out += [s.replace(".", "-"), s]
    elif suffix == ".L":                   # London: Klassen mit Punkt („BT.A“) → Bindestrich, „RR.“ → RR
        b = s.rstrip(".")
        out += [b + ".L" if not b.endswith(".L") else b, b.replace(".", "-") + ".L", s]
    elif suffix:
        out += [s if s.endswith(suffix) else s.split(".")[0] + suffix, s]
    else:                                  # Euro Stoxx: Kürzel meist schon mit Börsen-Endung
        out += [s, s.split(".")[0] + ".DE", s.split(".")[0] + ".PA", s.split(".")[0] + ".AS"]
    seen, res = set(), []
    for c in out:
        if c and c not in seen:
            seen.add(c); res.append(c)
    return res


def resolve(table: pd.DataFrame, suffix: str | None, universe: dict[str, str]) -> tuple[list[str], int]:
    """Tabelle → Ticker aus dem Kairo-Scan (Kürzel, sonst Firmenname). universe: Ticker → Name."""
    tcol = next((c for c in table.columns if TICK_COL.match(c)), None)
    ncol = next((c for c in table.columns if NAME_COL.match(c)), None)
    by_name: dict[str, str] = {}
    us_only = suffix == ""
    for t, n in universe.items():
        if not (us_only and tcol is None and "." in t):
            by_name.setdefault(norm_name(n), t)
    got: list[str] = []
    for _, row in table.iterrows():
        hit = next((c for c in candidates(row[tcol], suffix) if c in universe), None) if tcol is not None else None
        if not hit and ncol is not None:
            nn = norm_name(row[ncol])
            hit = by_name.get(nn)
            if not hit and tcol is None and len(nn) >= 5:        # nur Namen: „Amazon“ ↔ „Amazon.com“, „UnitedHealth“ ↔ „UnitedHealth Group“
                hit = next((t for k, t in by_name.items() if k.startswith(nn) or nn.startswith(k) and len(k) >= 5), None)
        if hit and hit not in got:
            got.append(hit)
    return got, len(table)


def _previous() -> dict:
    try:
        return json.loads(urllib.request.urlopen(urllib.request.Request(PAGES, headers=UA), timeout=20).read()).get("idx", {})
    except Exception:
        return {}


def build(universe: dict[str, str], fetch=_tables, previous=_previous) -> dict:
    out, prev, log = {}, None, []
    for key, name, url, suffix, (lo, hi), share in INDICES:
        try:
            tab = pick_table(fetch(url), lo, hi, by_name=key in NAME_ONLY)
            if tab is None:
                raise ValueError("keine passende Tabelle")
            got, total = resolve(tab, suffix, universe)
            if len(got) < share * total:
                raise ValueError(f"nur {len(got)} von {total} im Scan")
            out[key] = {"n": name, "t": got, "total": total}
            log.append(f"{name} {len(got)}/{total}")
        except Exception as exc:
            prev = previous() if prev is None else prev
            if key in prev:
                out[key] = prev[key]
                log.append(f"{name}: alter Stand ({exc})")
            else:
                log.append(f"{name}: fehlt ({exc})")
    print("Indizes: " + " · ".join(log))
    return {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "idx": out}
