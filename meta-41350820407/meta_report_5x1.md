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
| 5x1 | E0 | 10.000 € | -12.4% (-51.9%) | +3.2% (-37.5%) |
| 5x1 | E0 | 20.000 € | -13.4% (-54.7%) | -9.1% (-40.0%) |
| 5x1 | M_RANK | 10.000 € | -11.4% (-52.1%) | -13.4% (-54.2%) |
| 5x1 | M_RANK | 20.000 € | -12.6% (-53.3%) | -21.5% (-70.2%) |
| 5x1 | M_FILT | 10.000 € | -7.8% (-38.4%) | -0.1% (-41.7%) |
| 5x1 | M_FILT | 20.000 € | -5.2% (-30.8%) | -2.9% (-36.6%) |
| 5x1 | RND0 | 10.000 € | -11.9% (-53.5%) | -10.5% (-46.1%) |
| 5x1 | RND0 | 20.000 € | -13.9% (-58.7%) | -10.9% (-49.2%) |
| 5x1 | RND1 | 10.000 € | -13.3% (-53.7%) | +0.5% (-45.5%) |
| 5x1 | RND1 | 20.000 € | -9.7% (-47.5%) | -11.3% (-45.0%) |
| 5x1 | RND2 | 10.000 € | -16.9% (-64.0%) | -20.4% (-66.3%) |
| 5x1 | RND2 | 20.000 € | -16.3% (-62.6%) | -19.8% (-66.5%) |

## Ergebnis

- (a) Schätzung hängt mit echtem R zusammen: nein Validierung ρ -0.056 (p 0.001) · Holdout ρ +0.157 (p 0.000)
- (b) keine Modell-Variante schlägt B60 im Depot durchgängig

**Nicht bestanden – B60 bleibt; das Modell bringt im Depot keinen belastbaren Vorteil.**
