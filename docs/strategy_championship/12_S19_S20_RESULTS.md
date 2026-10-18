# 12 — Nutzer-Systeme S19 (Hybride Mean Reversion) und S20 (Trendfolge/VCP)

**Status: DATENBESCHRÄNKT · H4-Auslöser nur als Tageskerzen-Ersatz.** Regeln exakt nach Nutzer-Vorgabe (Protokoll v1.5/v1.6),
keine Parametersuche. Lauf `research_c3.yml` #39142206901 (Commit `a23358d`), Release `research-c3-39142206901`, Rohzahlen
`c3_results.json`, Registereinträge C3-…. Bilanzprüfungen bestanden. Holdout versiegelt.

## S20 Trendfolge / VCP (alle Titel, Risiko 1 %, Stop 1,5 ATR, Break-even ab +2 ATR, Trailing unter Vortagestief)

| Zeitraum | Kapital | CAGR | Max. DD | Sharpe | Trades | Ø Haltedauer | Kostenstress | p vs. Zufall |
|---|---|---|---|---|---|---|---|---|
| Train 2008–2016 | 5.000 € | +4,0 % | −39,9 % | 0,34 | 772 | ≈ 10 T. | −8,6 % | 0,165 |
| Train 2008–2016 | 20.000 € | +7,7 % | −27,9 % | 0,58 | 769 | 9,7 T. | −4,6 % | 0,090 |
| Validierung 2017–2021 | 5.000 € | −8,8 % | −46,6 % | −0,49 | 581 | ≈ 9 T. | −31,1 % | 0,875 |
| Validierung 2017–2021 | 20.000 € | +2,4 % | −27,2 % | 0,22 | 619 | 8,9 T. | −14,4 % | 0,455 |

**Urteil Validierung (Regeln aus 08): NICHT BESTANDEN** (nicht besser als Zufall; unter Kostenstress negativ; Sharpe < S13-ETF 0,58).
Beobachtung: Trefferquote 42–47 %, aber der enge Stop (1,5 ATR) und das Nachziehen unter das **Tages**-Tief beenden Trades nach
≈ 9–10 Tagen — der gewünschte „Trend ausreiten“-Effekt tritt auf Tagesbasis kaum ein; ≈ 4 Trades/Woche treiben die Kosten.
Mit echten H4-Tiefs wäre das Nachziehen sogar noch enger. In Train hängt das Plus zur Hälfte an den besten 1 % der Trades.

## S19 Hybride Mean Reversion (nur US)

| Variante | Train-Signale → Trades | Validierung → Trades |
|---|---|---|
| S19-PIT (Größe über Liquidität ≥ 100 Mio. USD/Tag) | 0 Trades | 0 Trades |
| S19-TODAY (heutige Marktkap. ≥ 10 Mrd. USD, Rückschaufehler) | 2 Trades (2 Stops, −2 % DD) | 2 Trades (1 Ziel, 1 Stop) |

**Urteil: NICHT TESTBAR mit Tageskerzen.** Die Filterkette ist so streng, dass in 14 Jahren und ≈ 600–900 großen US-Titeln nur
wenige Dutzend Tagessignale entstehen (Train: 64). Der Tages-Ersatz des H4-Auslösers kommt erst, wenn der Kurs schon nahe der
EMA20 ist → CRV ≥ 2 praktisch nie erfüllt. Das sagt **nichts** über die Idee mit echtem H4-Einstieg aus; dafür braucht es
4-Std.-Kerzen (vorwärts, Papier-Handel). Zusätzlich: die operative Marge war mangels Daten nicht prüfbar.

## Folgerungen

1. Beide Systeme sind sorgfältig spezifiziert, hängen aber am **H4-Teil** — der ist mit Gratisdaten historisch nicht prüfbar.
2. S20 auf Tagesbasis zeigt keinen Vorteil gegenüber Zufall und scheitert an den Kosten (viele kurze Trades, kleines Kapital).
3. Ehrlicher nächster Schritt für S19/S20: **Papier-Handel vorwärts mit echten H4-Daten** (Signale täglich protokollieren, keine
   Orders), Auswertung nach ≥ 6–12 Monaten. Alternativ registrierte Tages-Varianten (z. B. S19 ohne H4-Auslöser, Kauf zur nächsten
   Eröffnung) — jede weitere Variante erhöht aber die Zahl der Versuche.
