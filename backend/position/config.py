"""Alle Parameter der Strategie an einer Stelle (Regelwerk vom 23.11.2026, Abschnittsnummern wie im Auftrag)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Config:
    # 1. Marktregime
    regime_index: str = "^GSPC"            # Leitindex S&P 500
    regime_sma: int = 200
    # 2. Vorauswahl
    min_market_cap: float = 2_000_000_000  # USD
    min_dollar_volume: float = 10_000_000  # USD, Ø 50 Tage
    dollar_volume_days: int = 50
    sma_fast: int = 100
    sma_slow: int = 200
    slope_lag: int = 20                    # SMA 200 heute > SMA 200 vor 20 Tagen
    gap_days: int = 90
    gap_limit: float = -0.15               # kein Tagesverlust < −15 % in 90 Tagen
    # 3. Ranking
    momentum: str = "clenow"               # "clenow" (Regression 90 T. × R²) oder "6-1" (t-126 … t-21)
    clenow_days: int = 90
    w_momentum: float = 0.50
    w_quality: float = 0.30
    w_value: float = 0.20
    neutral: float = 50.0                  # fehlende Fundamentaldaten
    top_n: int = 15
    sector_cap: int = 3
    exit_rank_pct: float = 0.25            # freitags: raus, wenn nicht mehr in den Top 25 %
    # 4. Positionsgröße
    atr_days: int = 20
    risk_per_atr: float = 0.001            # 1 ATR = 0,1 % des Depots
    max_weight: float = 0.08
    max_positions: int = 15
    # 5. Exits
    trail_atr: float = 3.0
    sizing: str = "atr"                    # "atr" (Regelwerk) · "equal" nur für Diagnose-Läufe (1/15 des Depots je Position)
    use_regime: bool = True                # False nur für Diagnose-Läufe
    rebalance: str = "weekly"              # "weekly" (Regelwerk: Rang-Exit freitags, Käufe täglich) · "monthly"/"quarterly":
                                           # Rang-Exit UND Käufe nur am letzten Handelstag des Monats/Quartals (Test-Varianten)
    # 6. Praxis
    earnings_days: int = 5                 # Handelstage bis Quartalszahlen → Warn-Flag
    # Backtest
    cost: float = 0.001                    # Gebühren + Slippage je Kauf und je Verkauf
    tax: float = 0.26375                   # Abgeltungsteuer inkl. Soli
    etf_partial_exemption: float = 0.30    # Teilfreistellung Aktien-ETF (Benchmark nach Steuer)
    start_capital: float = 100_000.0
    fund_lag_days: int = 120               # Jahreszahlen gelten erst 120 Tage nach Geschäftsjahresende (10-K liegt vor)


CFG = Config()
