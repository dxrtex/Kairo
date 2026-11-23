"""Kairo Position: risikokontrolliertes Multi-Faktor-Momentum-Modell mit SMA-200-Marktfilter (Auftrag Jonny, 23.11.2026).

Module: config (alle Parameter) · market_regime (Leitindex über SMA 200) · filters (Liquidität, Trend, Gap) ·
scoring (Clenow-Momentum/6-1, Qualität, Value, Perzentile, Top 15 mit Sektor-Cap) · position_sizing (ATR 20) ·
exit_signals (Trendbruch, Trailing-Stop, Top-25-%-Prüfung freitags) · engine (Tages-Simulation: Backtest UND Live-Modelldepot) ·
backtest (Kennzahlen, Steuer-Bericht) · scan (täglicher Lauf im Abendscan). Reine Analyse – keine Orders.
"""
