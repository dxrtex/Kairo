"""1. Marktregime: Neukäufe nur, wenn der Leitindex über seiner SMA 200 schließt."""
from __future__ import annotations

import pandas as pd

from .config import CFG, Config


def regime(index_close: pd.Series, cfg: Config = CFG) -> pd.Series:
    """True = Bullenmarkt (Käufe frei), False = Kaufstopp. NaN in der Anlaufzeit → False."""
    c = index_close.astype(float)
    sma = c.rolling(cfg.regime_sma, min_periods=cfg.regime_sma).mean()
    return (c > sma).fillna(False)
