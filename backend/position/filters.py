"""2. Vorauswahl: Liquidität (in USD), Aufwärtstrend, Stabilität (Gap-Filter) – vektorisiert über alle Aktien (Spalten).

Alle Eingaben sind breite Tabellen (Index = Datum, Spalten = Ticker) mit bereinigten Kursen.
"""
from __future__ import annotations

import re
from functools import lru_cache

import numpy as np
import pandas as pd

from .config import CFG, Config


def indicators(C: pd.DataFrame, V: pd.DataFrame, fx: pd.Series | None, cfg: Config = CFG) -> dict[str, pd.DataFrame]:
    """SMA 100/200, Steigung SMA 200, Ø Dollar-Umsatz 50 T. (USD), kleinster Tagesreturn 90 T."""
    f = fx.reindex(C.columns).fillna(1.0) if fx is not None else 1.0
    sma_f = C.rolling(cfg.sma_fast, min_periods=cfg.sma_fast).mean()
    sma_s = C.rolling(cfg.sma_slow, min_periods=cfg.sma_slow).mean()
    dv = (C * V * f).rolling(cfg.dollar_volume_days, min_periods=cfg.dollar_volume_days).mean()
    gap = C.pct_change(fill_method=None).rolling(cfg.gap_days, min_periods=cfg.gap_days).min()
    return {"sma_f": sma_f, "sma_s": sma_s, "dv": dv, "gap": gap}


def pool(C: pd.DataFrame, ind: dict, mcap: pd.DataFrame | pd.Series | None, cfg: Config = CFG) -> pd.DataFrame:
    """Boolesche Tabelle: Aktie erfüllt ALLE Bedingungen aus Abschnitt 2 am Tag t."""
    sma_f, sma_s = ind["sma_f"], ind["sma_s"]
    trend = (C > sma_f) & (sma_f > sma_s) & (sma_s > sma_s.shift(cfg.slope_lag))
    liq = ind["dv"] >= cfg.min_dollar_volume
    stab = ind["gap"] > cfg.gap_limit
    if mcap is None:
        cap = pd.DataFrame(True, index=C.index, columns=C.columns)
    elif isinstance(mcap, pd.Series):
        cap = pd.DataFrame(np.broadcast_to((mcap.reindex(C.columns) >= cfg.min_market_cap).to_numpy(), C.shape), index=C.index, columns=C.columns)
    else:
        cap = mcap.reindex(index=C.index, columns=C.columns) >= cfg.min_market_cap
    return (trend & liq & stab & cap).fillna(False)


_SUFFIX = re.compile(r"\b(inc|corp|corporation|co|ltd|limited|plc|ag|se|sa|nv|n\.v|s\.a|holdings?|group|adr|ads|class [a-z]|cl [a-z]|"
                     r"ordinary shares?|common stock|sponsored|the|company|pref|preferred|vz|st)\b\.?", re.I)


@lru_cache(maxsize=None)
def norm_name(n: str) -> str:
    s = _SUFFIX.sub(" ", str(n or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def dedupe(tickers: list[str], names: dict[str, str], liquidity: dict[str, float]) -> list[str]:
    """Doppelte Listings derselben Firma (ADR + Heimataktie, Stamm-/Vorzugsaktie): nur die liquidere behalten. Reihenfolge bleibt."""
    best: dict[str, str] = {}
    for t in tickers:
        k = norm_name(names.get(t) or t) or t
        if k not in best or (liquidity.get(t) or 0) > (liquidity.get(best[k]) or 0):
            best[k] = t
    keep = set(best.values())
    return [t for t in tickers if t in keep]
