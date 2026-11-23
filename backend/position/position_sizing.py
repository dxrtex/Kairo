"""4. Positionsgröße: 1 ATR 20 = 0,1 % des Depots, höchstens 8 % des Depots je Position."""
from __future__ import annotations

import math

import pandas as pd

from .config import CFG, Config


def atr(H: pd.DataFrame, L: pd.DataFrame, C: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    """Average True Range (einfacher Durchschnitt über n Tage) auf bereinigten Kursen."""
    pc = C.shift(1)
    tr = pd.concat([(H - L), (H - pc).abs(), (L - pc).abs()]).groupby(level=0).max()
    tr = tr.reindex(C.index)
    return tr.rolling(n, min_periods=n).mean()


def shares(portfolio_value: float, atr_value: float, close: float, cfg: Config = CFG) -> int:
    """Shares = min(floor(PV·0,001 / ATR), floor(PV·0,08 / Close)); 0 bei fehlenden/ungültigen Werten."""
    if not (portfolio_value > 0 and atr_value and atr_value > 0 and close and close > 0) or any(
            math.isnan(x) for x in (portfolio_value, atr_value, close)):
        return 0
    return int(max(0, min(math.floor(portfolio_value * cfg.risk_per_atr / atr_value), math.floor(portfolio_value * cfg.max_weight / close))))
