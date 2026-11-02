"""Feste, synthetische App-Daten für den Design-Prüfstand (ohne Netz, reproduzierbar).

Führt den echten Abendscan (backend.run_scan.main, Stichtag 30.10.2026) und die echte 4H-/Basis-Verfolgung
(run_scan.h4_block) mit erfundenen, aber festen Kursverläufen aus. Jede Aktie bekommt einen Verlauf
„Aufwärtstrend → Rückgang → Seitwärtsphase“ aus einem festen Zufalls-Startwert; die Startwerte in HITS erfüllen am
Stichtag alle 11 Kriterien (geprüft mit backend.scanner.evaluate). Für die Liste „Kaufbereit / wartet / verfallen“
werden Treffer-Tage in der Vergangenheit angenommen (signals.json synthetisch). Namen/Börsen/Währungen aus
tools/design_fixtures/universe.csv. KEINE echten Kurse – nur für Screenshots und Layout-Messungen.

    python tools/design_fixtures/make_site_data.py      # schreibt tools/design_fixtures/site_data/ (nicht im Repo)
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = Path(__file__).resolve().parent / "site_data"
END = "2026-10-30"
NOW = datetime(2026, 10, 30, 21, 30, tzinfo=timezone.utc)       # Freitagabend nach US-Schluss
IDX = pd.bdate_range(end=END, periods=520)
# Ticker → Startwert, der am Stichtag 11/11 ergibt (Suchlauf über 1.500 Startwerte, 51 Treffer); die ersten sechs können zusätzlich
# eine gerade fertige Seitwärtsphase haben (kaufbereit)
HITS = {"ALSN": 30, "KGX.DE": 87, "WDP.BR": 123, "NTR": 456, "CLDX": 618, "AIR.PA": 717,          # → kaufbereit
        "PLD": 59, "SNEX": 221, "TUI1.DE": 216, "ZAL.DE": 435, "ENR.DE": 631, "ADS.DE": 437, "IFX.DE": 578,  # → wartet
        "ITV.L": 28, "EQB.TO": 210, "SY1.DE": 290, "LHA.DE": 505}                                        # → verfallen
WANT = {**dict.fromkeys(list(HITS)[:6], "ready"), **dict.fromkeys(list(HITS)[6:13], "wait"), **dict.fromkeys(list(HITS)[13:], "gone")}
WATCH = ["PLD", "SNEX", "ITV.L", "EQB.TO", "SAP.DE", "AAPL", "NVDA", "TUI1.DE"]
FX = {"USD": 1.16, "GBP": .87, "CHF": .94, "CAD": 1.62, "JPY": 177.0, "HKD": 9.0, "AUD": 1.77, "SEK": 11.0, "NOK": 11.7,
      "DKK": 7.46, "PLN": 4.25}


def stock(seed: int) -> pd.DataFrame:
    """Aufwärtstrend → Rückgang 25–55 % → Seitwärtsphase (420 Handelstage)."""
    r = np.random.default_rng(seed)
    idx = IDX[-420:]
    n = len(idx); up = r.uniform(.0008, .003); dn = r.uniform(.25, .55); L = r.integers(40, 110); side = r.integers(5, 30)
    ret = r.normal(up, r.uniform(.012, .025), n); s = n - L - side
    ret[s:s + L] += np.log(1 - dn) / L
    ret[s + L:] = r.normal(0, r.uniform(.006, .014), side)
    c = r.uniform(20, 200) * np.exp(np.cumsum(ret))
    o = c * np.exp(r.normal(0, .006, n)); h = np.maximum(o, c) * np.exp(abs(r.normal(0, .01, n)))
    lo = np.minimum(o, c) * np.exp(-abs(r.normal(0, .01, n))); v = r.uniform(3e5, 3e6, n)
    return pd.DataFrame({"Open": o, "High": h, "Low": lo, "Close": c, "Volume": v}, index=idx)


def calm(seed: int) -> pd.DataFrame:
    """Ruhiger Aufwärtstrend für Indizes, Sektor-ETFs und den Welt-ETF (Marktlage: Rückenwind)."""
    r = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(r.normal(.0005, .006, len(IDX))))
    return pd.DataFrame({"Open": c, "High": c * 1.005, "Low": c * .995, "Close": c, "Volume": 1e6}, index=IDX)


def seed_of(t: str) -> int:
    return int(hashlib.md5(t.encode()).hexdigest()[:6], 16)


def frame(t: str, sector_etfs=()) -> pd.DataFrame:
    if t.endswith("=X"):                                 # Wechselkurse EURxxx=X
        v = FX.get(t[3:6], 1.0)
        return pd.DataFrame({"Open": v, "High": v, "Low": v, "Close": v, "Volume": 0.0}, index=IDX[-5:])
    if t.startswith("^") or t in sector_etfs or t in {"SPY", "QQQ", "IWM", "HYG", "IEF"}:
        df = calm(seed_of(t))
        if t == "^VIX":
            df[["Open", "High", "Low", "Close"]] = 16.0
        return df
    return stock(HITS[t] if t in HITS else 600 + seed_of(t) % 1400)


def main() -> int:
    from backend import h4live, run_scan, state
    from backend.data_provider import YFinanceProvider
    from backend.scanner import evaluate

    etfs = set(run_scan.SECTOR_ETF.values())
    YFinanceProvider.history = lambda self, tickers, period, end=None: {t: frame(t, etfs) for t in tickers}
    YFinanceProvider.info = lambda self, t: {}
    YFinanceProvider.infos = lambda self, ts: {}
    uni = pd.read_csv(Path(__file__).parent / "universe.csv", dtype={"ticker": str})
    uni["earnings_date"] = None
    run_scan.load_universe = lambda: uni
    run_scan._WATCH = {t: n for t, n in zip(uni.ticker, uni.name) if t in WATCH}
    state.READONLY = True
    OUT.mkdir(parents=True, exist_ok=True)
    run_scan.SITE = OUT
    for t, s in HITS.items():                            # Selbstprüfung
        if not evaluate(stock(s), {"currency": "USD", "market_cap_usd": 5e9}, ticker=t).passed:
            print(f"Hinweis: {t} ist am Stichtag kein Treffer")
    run_scan.main(["--tickers", ",".join(uni.ticker), "--end", "2026-10-31"])

    # Basis-/Kaufbereit-Liste: je Treffer einen Treffer-Tag in der Vergangenheit wählen (Mischung der Zustände)
    res = json.loads((OUT / "results.json").read_text())
    search = {r["t"]: r for r in json.loads((OUT / "search.json").read_text())["rows"]}
    data = {t: frame(t, etfs) for t in search}
    sigs = []
    for i, t in enumerate(HITS):
        df = data[t]
        want = WANT[t]
        pick = None
        for k in range(1, 40):
            d = str(df.index[-1 - k].date())
            it = h4live.build([{"t": t, "n": t, "d": d, "grp": "11"}], {t: df}, {}, NOW, False)
            if not it:
                continue
            b = it[0].get("base") or {}
            st = "ready" if (b.get("pending") and b.get("lo") is not None) else "wait" if it[0]["st"] == "basis" else "gone" if it[0]["st"] == "weg" else None
            if st == want:
                pick = d
                break
            pick = pick or d
        sigs.append({"t": t, "n": search.get(t, {}).get("n", t), "d": pick, "k": "hit", "cur": search.get(t, {}).get("cur")})
    real_load = state.load
    state.load = lambda name, default=None: sigs if name == "signals.json" else ([] if name in ("h4near.json", "h4trades.json") else real_load(name, default))
    h4live.hourly = lambda tickers, *a, **k: {}
    run_scan.datetime = type("D", (datetime,), {"now": staticmethod(lambda tz=None: NOW if tz else NOW.replace(tzinfo=None))})
    h4 = run_scan.h4_block(res["results"], data, search, END, True, [])
    files = {"h4.json": h4, "changes.json": {"since": None}, "alerts.json": {"enabled": False, "push": {"enabled": False}}}
    try:                                                 # ETF-Ampel wie im Abendscan
        from backend import etf
        flat = calm(seed_of("REF"))["Close"]
        files["etf.json"] = etf.compute(calm(seed_of(etf.TICKER)), flat * 0 + 16.0, flat, flat, flat, END)
    except Exception as exc:
        print(f"ETF: {exc!r}")
    for name, obj in files.items():
        (OUT / name).write_text(json.dumps(run_scan._clean(obj), ensure_ascii=False))
    stamp = NOW.isoformat(timespec="seconds")            # feste Zeitstempel → gleiche Screenshots bei jedem Lauf
    for f in OUT.glob("*.json"):
        d = json.loads(f.read_text())
        if isinstance(d, dict) and "generated" in d:
            d["generated"] = stamp
            f.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")))
    cnt = {}
    for it in h4["items"]:
        b = it.get("base") or {}
        k = "kaufbereit" if b.get("pending") and b.get("lo") is not None else it["st"]
        cnt[k] = cnt.get(k, 0) + 1
    print("4H/Basis:", cnt)
    print("geschrieben:", sorted(p.name for p in OUT.iterdir()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
