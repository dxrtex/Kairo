"""Markt tagsüber: Sektoren, Branchen, Heatmap und Gewinner/Verlierer alle 30 Minuten (Mitteilungsdienst, Branch kairo-alerts).

Nur Anzeige – keine Signale, kein x/11, kein Kauf-Status (die bleiben beim Tagesschluss des Abendscans).
Aktien: die größten je Region aus dem veröffentlichten Suchindex (wie die Heatmap der App). Kurse von Yahoo, ca. 15 Min. verzögert.

    python -m backend.mktlive        # einmal rechnen und state/mktlive.json schreiben
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

TOP = {"us": 200, "europe": 200, "asia": 120}       # Heatmap der App zeigt höchstens 160 je Region
TOP_DE = 60                                          # Deutschland extra, damit die DAX-Werte sicher dabei sind


def pick(rows: list[dict]) -> list[str]:
    """Größte Aktien je Region (Börsenwert) aus dem Suchindex."""
    out = set()
    rows = [r for r in rows if "liquidity" not in (r.get("km") or [])]    # illiquide Zweitlistings (HP in Wien …) weglassen
    for reg, n in TOP.items():
        xs = sorted([r for r in rows if r.get("r") == reg and r.get("mc")], key=lambda r: -r["mc"])[:n]
        out |= {r["t"] for r in xs}
    de = sorted([r for r in rows if str(r.get("t", "")).endswith(".DE") and r.get("mc")], key=lambda r: -r["mc"])[:TOP_DE]
    return sorted(out | {r["t"] for r in de})


def _frames(tickers: list[str], period: str) -> dict:
    import pandas as pd
    import yfinance as yf
    h = yf.download(tickers, period=period, interval="1d", group_by="ticker", auto_adjust=True, progress=False, threads=True)
    out = {}
    for t in tickers:
        try:
            df = (h[t] if isinstance(h.columns, pd.MultiIndex) else h).dropna(subset=["Close"])
            df.index = pd.to_datetime(df.index).tz_localize(None)
            if len(df) > 5:
                out[t] = df
        except Exception:
            pass
    return out


def build(search_rows: list[dict]) -> dict:
    from .analysis import ASSET_ETF, EU_SECTOR_ETF, INDUSTRY_ETF, MARKET, SECTOR_ETF, THEME_ETF, market_context
    from .run_scan import day_moves
    etfs = sorted(set(SECTOR_ETF.values()) | set(INDUSTRY_ETF) | set(THEME_ETF) | set(EU_SECTOR_ETF) | set(ASSET_ETF) | {t for t, _ in MARKET})   # Indizes: Kacheln + Maßstab
    mkt = market_context(_frames(etfs, "2y"))
    stocks = pick(search_rows)
    rows = {}
    for t, df in _frames(stocks, "1y").items():
        m = day_moves(df)
        if m.get("d1") is not None:
            rows[t] = {k: m.get(k) for k in ("d1", "d5", "m1", "m3", "ytd", "rv")} | {"c": round(float(df["Close"].iloc[-1]), 4)}
    return {"generated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
            "sectors": mkt.get("sectors", []), "industries": mkt.get("industries", []), "themes": mkt.get("themes", []), "sectors_eu": mkt.get("sectors_eu", []), "assets": mkt.get("assets", []),
            "idx": {t: mkt[t] for t, _ in MARKET if t in mkt}, "rows": rows}


def update(app_url: str) -> dict | None:
    import requests
    from . import state
    try:
        rows = requests.get(app_url + "data/search.json", timeout=60).json().get("rows") or []
    except Exception as exc:
        print(f"Markt tagsüber: Suchindex nicht geladen ({exc!r})")
        return None
    out = build(rows)
    state.save("mktlive.json", out)
    print(f"Markt tagsüber: {len(out['sectors'])} Sektoren, {len(out['industries'])} Branchen, {len(out['rows'])} Aktien")
    return out


def main() -> int:
    from .push import APP
    out = update(APP)
    if out:
        print(json.dumps({k: v for k, v in out.items() if k != "rows"}, ensure_ascii=False)[:1500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
