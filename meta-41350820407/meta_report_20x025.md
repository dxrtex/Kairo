# Meta-Labeling: Modell-Rangfolge für B60-Signale (zeitlich getrennt)

und wir prüfen, ob eine darauf gestützte Rangfolge oder Auswahl das DEPOT verbessert.

Vorab festgelegt (01.11.2026):
- Merkmale: Stop-Abstand in ATR, Vormomentum, ATR in % des Kurses, Markt unter 200-Tage-Linie, Kurs/Volumen (über
  200-Tage-Linie, Rückgang vom 52-Wochen-Hoch, Kapitulations-Volumen, Wochenverlust), Insider (Kauf, Cluster, Officer,
  ≥ 100 k$), Quartalszahlen/Meldungen im Rückgang (8-K), Qualität (profitabel, Bruttogewinn/Bilanzsumme, Gewinnentwicklung,
  Eigenkapitalquote), Region. Fehlende Werte → Mittel der Lerndaten + Kennzeichen „fehlt“.
- Modell: Ridge-Regression (Strafterm α = 10, standardisierte Merkmale) auf R mit Stress-Kosten – bewusst einfach und
  nachvollziehbar (Baseline vor jedem komplexen Verfahren).
- Zeitliche Trennung (walk-forward): lernen auf Train (2008–2016) → anwenden auf Validierung (2017–2021); lernen auf
  Train+Validierung → anwenden auf Holdout (2022–2026). Im Train-Zeitraum bleibt die B60-Rangfolge (kein In-Sample-Vorteil).
- Varianten im Depot (gleiche Engine, gleiche Kosten): E0 = B60 (schwächeres Vormomentum zuerst) · M_RANK = Modell-Rangfolge
  bei vollem Depot · M_FILT = B60, aber Signale im untersten Drittel der Modell-Schätzung (Schwelle aus den Lerndaten) entfallen ·
  RND = zufällige Rangfolge (3 Seeds, Kontrollgruppe).
- Bestanden, wenn (a) die Modell-Schätzung je Trade in Validierung UND Holdout positiv mit dem echten R zusammenhängt
  (Spearman > 0, p < 0,05) UND (b) M_RANK oder M_FILT im Depot (Stress-Kosten) in Validierung UND Holdout bei 10.000 € und
  20.000 € eine höhere Jahresrendite als E0 erzielt, ohne größeren Rückgang. Bestanden heißt: Challenger für den Schattentest
  – keine Regeländerung.

**Validierung** (3765 Trades): ρ -0.056 (p 0.001) · Ø R Stress je Drittel der Schätzung (unten → oben): +0.159 / +0.084 / -0.035  
wichtigste Gewichte: low_lev_fehlt -0.344, em_pos_fehlt +0.316, mom -0.112, sma200_up +0.109, deep_dd +0.092, gp_quality_fehlt -0.080, profitable -0.062, em_pos +0.040, no_news -0.040, news_earn +0.040
**Holdout** (5262 Trades): ρ +0.157 (p 0.000) · Ø R Stress je Drittel der Schätzung (unten → oben): -0.287 / -0.123 / +0.206  
wichtigste Gewichte: low_lev_fehlt -0.384, profitable_fehlt +0.340, gp_quality_fehlt -0.119, index_u200 +0.082, stop_atr +0.053, mom -0.045, em_pos +0.039, atr_pct +0.036, sma200_up +0.036, ins_cluster -0.032

| Raster | Variante | Kapital | Val CAGR (DD) | Holdout CAGR (DD) |
|---|---|---|---|---|
| 20x025 | E0 | 10.000 € | -1.9% (-17.7%) | -5.7% (-37.9%) |
| 20x025 | E0 | 20.000 € | -3.5% (-22.0%) | -3.8% (-34.4%) |
| 20x025 | M_RANK | 10.000 € | +0.2% (-24.5%) | -6.4% (-30.6%) |
| 20x025 | M_RANK | 20.000 € | +0.5% (-23.0%) | -6.8% (-31.1%) |
| 20x025 | M_FILT | 10.000 € | -2.3% (-23.9%) | -6.0% (-28.9%) |
| 20x025 | M_FILT | 20.000 € | -1.8% (-20.9%) | -5.5% (-28.3%) |
| 20x025 | RND0 | 10.000 € | -2.2% (-21.7%) | -13.0% (-49.6%) |
| 20x025 | RND0 | 20.000 € | -1.5% (-21.4%) | -12.2% (-48.2%) |
| 20x025 | RND1 | 10.000 € | +2.7% (-18.8%) | -10.5% (-42.8%) |
| 20x025 | RND1 | 20.000 € | +1.2% (-21.6%) | -11.4% (-45.5%) |
| 20x025 | RND2 | 10.000 € | -4.6% (-27.4%) | -19.0% (-63.8%) |
| 20x025 | RND2 | 20.000 € | -5.9% (-29.6%) | -8.1% (-34.7%) |

## Ergebnis

- (a) Schätzung hängt mit echtem R zusammen: nein Validierung ρ -0.056 (p 0.001) · Holdout ρ +0.157 (p 0.000)
- (b) keine Modell-Variante schlägt B60 im Depot durchgängig

**Nicht bestanden – B60 bleibt; das Modell bringt im Depot keinen belastbaren Vorteil.**
