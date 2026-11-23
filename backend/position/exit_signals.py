"""5. Exits: Trendbruch (Close < SMA 100), Trailing-Stop (Close < höchster Schlusskurs seit Kauf − 3 × ATR 20),
freitags: nicht mehr in den Top 25 % des Gesamt-Rankings."""
from __future__ import annotations

import math

from .config import CFG, Config


def trailing_stop(highest_close: float, atr_value: float, cfg: Config = CFG) -> float:
    return highest_close - cfg.trail_atr * atr_value if atr_value and not math.isnan(atr_value) else float("nan")


def exit_reasons(close: float, sma_fast: float, highest_close: float, atr_value: float, is_friday: bool,
                 in_top_quantile: bool, cfg: Config = CFG) -> list[str]:
    r = []
    if sma_fast == sma_fast and close < sma_fast:
        r.append("trend")                       # Close < SMA 100
    st = trailing_stop(highest_close, atr_value, cfg)
    if st == st and close < st:
        r.append("stop")                        # Trailing-Stop
    if is_friday and not in_top_quantile:
        r.append("rank")                        # aus den Top 25 % gefallen
    return r


LABELS = {"trend": "Trendbruch (Schluss unter SMA 100)", "stop": "Trailing-Stop (3 × ATR unter dem Hoch seit Kauf)",
          "rank": "nicht mehr in den Top 25 % (Freitags-Prüfung)", "delisted": "Kursreihe endet (Delisting/Übernahme)"}
