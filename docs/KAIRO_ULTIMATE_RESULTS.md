# Kairo Ultimate – Ergebnisse (Runde 1, 29./30.10.2026)

Plan: `docs/KAIRO_ULTIMATE_RESEARCH_PLAN.md` (freigegeben und eingefroren, Commit `f2e946c`, Präzisierungen 9b vor dem
ersten Lauf). Code-Stand der Läufe: Branch `claude/ultimate-research`. Datensatz `prices_v1` SHA-256
`e405016e2348755bb9eef3fe5e70e7f6ff405755b15487fd15fd310a5e823c3c`. Produktive App, Scanner und Regel B60 unverändert.

| Lauf | Workflow-Run | Commit |
|---|---|---|
| Datenprüfung (Gate) | 40971029106 | (Branch-Stand 29.10. 23:05 UTC) |
| Wettbewerb A, Runde 1 (je Trade, Depot, Zufall) | 40969195427 | `6352458` |
| Wettbewerb B | 40971115447 | `f87c59c` |
| Bestätigung Vorzeit 1999–2007 / Asien | 40960444918 | siehe Abschnitt 3 |

**Kurzfassung**

1. **Wettbewerb A (Rücksetzer): Keine Verbesserung nachgewiesen.** Keine der fünf Varianten besteht die vorab festgelegten
   Regeln. Am nächsten kommt der *bestätigte Ausbruch* (E2): besser als B60 im Depot und besser als Zufall, aber der Vorsprung
   je Trade ist in der Validierung zu klein (+0,035 R statt +0,05 R), nach Holm-Korrektur nicht signifikant (p 0,072) und im
   Holdout negativ.
2. **B60 selbst ist als Depot nicht konkurrenzfähig.** Mit realistischen Stress-Kosten liegt B60 je Trade bei ≈ 0 R
   (Train −0,05 / Validierung +0,07 / Holdout −0,06 R) und im Depot in jedem Aufbau unter dem Welt-ETF (p vs. ACWI 0,99).
3. **Wettbewerb B: Dual Momentum (S16-B) ist die beste getestete Strategie für den Trading-Topf** – 14,4 % p. a. nach
   Stress-Kosten, 12,0 % nach Steuern, größter Rückgang −31 % (ACWI: 9,0 % / 7,9 % / −46 %), in allen drei Zeiträumen und in der
   unbenutzten Vorzeit 2003–2007 besser als der Markt, deutlich besser als Zufall (p 0,010), funktioniert schon mit 1.000 €.
   **Aber:** Gegen ACWI ist der Vorsprung mit p 0,069 knapp nicht signifikant → nach den Regeln **kein Beweis**, sondern der
   klar beste Kandidat für den unveränderten Papier-Test.
4. **Datenqualität geprüft und bestanden** – mit einer wichtigen, jetzt erstmals gemessenen Einschränkung: Unser
   Einzelaktien-Universum hat **+7,6 Prozentpunkte pro Jahr** mehr Rendite als der gleichgewichtete S&P 500 mit allen damaligen
   Mitgliedern (Survivorship-Bias). Absolute Renditen von Einzelaktien-Strategien sind deshalb deutlich zu hoch; nur
   Vergleiche gegen Zufall im selben Universum sind aussagekräftig. ETF-Strategien (S16-B, ACWI) betrifft das nicht.

---

## 1. Datenqualität (Plan §8b)

| Prüfung | Ergebnis | Gate | |
|---|---|---|---|
| Titel / Kerzen | 2.953 / 12,3 Mio. | – | |
| Unmögliche Kerzen (Hoch < Schluss usw.) | 0,086 % aller Kerzen (529 Titel, meist einzelne Tage) | < 0,1 % | ✓ |
| **Zweite Quelle Nasdaq** (294 zufällige US-Titel, Tagesrenditen ±1 %) | **Median 100 % Übereinstimmung**, nur 1 Titel < 95 % (TEVA) | ≥ 98 % | ✓ |
| Stooq | gesperrt (keine Antwort) → durch Nasdaq ersetzt | – | |
| Frischer Yahoo-Download (148 Titel) | 100 % gleich – keine nachträglichen Änderungen | – | ✓ |
| Fehlkurse (Sprung > 40 % mit Rücklauf) | 107 Titel | – | unsicher |
| Nicht bereinigte Splits | 113 Titel | – | unsicher |
| Kairo-Treffer mit markiertem Tag im Fenster | 35 von 49.134 (0,07 %) | ≤ 5 % | ✓ |
| **Survivorship** (gleichgewichtet US-Universum vs. RSP) | **+5,1 / +9,6 / +10,5 Pp. p. a.** (Train / Val / Holdout), gesamt **+7,6 Pp.** | messen | ⚠ |

Folgen: Der Datensatz darf benutzt werden. 223 „unsichere“ Titel werden in der Sensitivitätsrechnung herausgenommen
(Abschnitt 3). Die Survivorship-Zahl ist die wichtigste Erkenntnis der Datenprüfung: Jede Einzelaktien-Strategie (B60,
Momentum S07-B) startet mit einem Rückenwind von mehreren Prozentpunkten pro Jahr, der in der Realität fehlt.

## 2. Reproduktion

B60-Depot 5.000 €, 5 × 1 %, Basis-Kosten: **+15,1 % / −6,9 % / +11,9 %** – exakt wie Lauf 40925193877 (Soll). Zusätzlich zeigt
`backend/tests/test_b60_same.py`, dass Live-Strategie, h4live, Papier-Depot und Engine denselben Trade ergeben.

## 3. Wettbewerb A – Mean-Reversion-Championship

### 3.1 Je Trade (Ø R netto, Stress / Basis; unbegrenztes Kapital)

| Variante | Train 2008–16 | Validierung 2017–21 | Holdout 2022–26 (nur Hinweis) |
|---|---|---|---|
| **E0 B60 heute** | −0,052 / +0,095 (n 4.214) | +0,066 / +0,226 (n 3.765) | −0,055 / +0,087 (n 5.262) |
| E1 Früheinstieg | +0,000 / +0,095 (n 4.418) | +0,083 / +0,187 (n 3.568) | −0,056 / +0,036 (n 5.177) |
| **E2 Bestätigter Ausbruch** | **+0,015 / +0,108** (n 2.727) | **+0,101 / +0,202** (n 2.540) | −0,079 / +0,005 (n 3.466) |
| V1 Gültigkeit vor Kauf | −0,071 / +0,076 (n 3.480) | +0,035 / +0,194 (n 3.096) | −0,063 / +0,080 (n 4.347) |
| N1 ohne Quartalszahlen-Rückgang (nur USA) | −0,039 / +0,116 (n 2.316) | +0,132 / +0,297 (n 2.036) | +0,010 / +0,159 (n 2.742) |
| C1 Kosten ≤ 0,10 R | −0,091 / −0,029 (n 667) | +0,198 / +0,266 (n 529) | +0,395 / +0,480 (n 848) |

Stress-Kosten = doppelte gemessene Spanne, 0,05 % Slippage und 0,1 % Fremdwährung je Seite. Der Unterschied Stress ↔ Basis
(≈ 0,13–0,16 R je Trade) ist so groß wie der ganze Vorteil von B60 – **die echten Handelskosten entscheiden über B60.**

### 3.2 Depot (CAGR / größter Rückgang, Stress, 2008–2026 gesamt)

| Variante | 5 × 1 %, 10.000 € | 10 × 0,5 %, 10.000 € | 20 × 0,25 %, 10.000 € | 20 × 0,25 %, 20.000 € |
|---|---|---|---|---|
| E0 B60 | −1,6 % / −73 % | −1,7 % / −64 % | −0,1 % / −47 % | −0,6 % / −50 % |
| E1 | +1,8 % / −39 % | +1,6 % / −40 % | −0,6 % / −41 % | +0,5 % / −39 % |
| **E2** | −0,2 % / −47 % | **+1,7 % / −34 %** | **+1,3 % / −30 %** | **+1,5 % / −31 %** |
| V1 | −3,6 % / −84 % | −1,4 % / −62 % | −1,8 % / −51 % | −1,2 % / −49 % |
| N1 | −0,2 % / −76 % | −2,3 % / −68 % | −0,2 % / −41 % | −0,4 % / −45 % |
| C1 | −2,7 % / −63 % | +0,2 % / −46 % | −0,5 % / −30 % | −0,0 % / −26 % |
| *ACWI halten* | *+9,0 % / −46 %* | | | |

Mit 1.000–5.000 € und 10–20 Positionen werden die Positionen so klein (< 250 €), dass Gebühren anfallen – mehrere Aufbauten
verlieren dann fast alles. **Rücksetzer-Trading mit vielen kleinen Positionen ist bei kleinem Kapital nicht umsetzbar.**

### 3.3 Entscheidung nach Plan §7

| Variante | 1 ΔR ≥ +0,05 Train & Val | 2 Depot besser | 3 Holm p ≤ 0,05 | 4 Bestätigung | 5 > Zufall | Urteil |
|---|---|---|---|---|---|---|
| E1 | ✗ +0,052 / +0,017 | ✗ | ✗ 0,753 | *ausstehend* | ✓ (20/20 Seeds) | nicht bestanden |
| **E2** | ✗ +0,067 / **+0,035** | ✓ | ✗ **0,072** | *ausstehend* | ✓ (20/20) | **nicht bestanden (knapp)** |
| V1 | ✗ −0,019 / −0,031 | ✗ | ✗ 0,981 | *ausstehend* | ✗ | nicht bestanden |
| N1 | ✗ −0,027 / +0,051 | ✗ | ✗ 0,966 | *ausstehend* | ✓ | nicht bestanden |
| C1 | ✗ −0,039 / +0,131 | ✗ | ✗ 0,966 | *ausstehend* | ✗ | nicht bestanden |

Die Bestätigung (Punkt 4) kann das Urteil nicht mehr ändern, weil bei jeder Variante schon Punkt 1 und 3 fehlen; sie wird
nachgetragen.

**Ergebnis Wettbewerb A: Keine Verbesserung nachgewiesen. B60 bleibt die Rücksetzer-Regel; E2 ist der einzige ernsthafte
Kandidat für einen späteren Papier-Vergleich.**

| Frage | Antwort |
|---|---|
| Beste Rücksetzer-Rendite | E2 (Depot 20 × 0,25 %, 20.000 €: +1,5 % p. a. Stress) – trotzdem weit unter ACWI |
| Beste Rendite nach Risiko | E2 (Rückgang −30 % statt −47 %) |
| Robusteste Variante | keine – alle schwanken stark zwischen den Zeiträumen |
| Bester Einstieg | Ausbruch über das Basishoch (E2) vor B60 und Früheinstieg |
| Bester Portfolioaufbau | 20 × 0,25 % ab 10.000 € (kleinster Rückgang); darunter nicht umsetzbar |

## 4. Wettbewerb B – Ultimate Trading Championship (10.000 €, Stress-Kosten)

| Strategie | Train | Validierung | Holdout | gesamt | max. Rückgang | Sharpe | nach Steuern | p vs. ACWI | p vs. Zufall |
|---|---|---|---|---|---|---|---|---|---|
| ACWI halten | +7,8 % | +10,9 % | +9,0 % | +9,0 % | −46,0 % | 0,54 | +7,9 % | – | – |
| **S16-B Dual Momentum** | **+13,5 %** | **+19,1 %** | **+10,8 %** | **+14,4 %** | **−30,6 %** | **0,76** | **+12,0 %** | 0,069 | **0,010** |
| SP2F S&P 500 2× über SMA200 | +12,6 % | +22,6 % | +5,3 % | +13,4 % | −44,2 % | 0,63 | +11,4 % | 0,198 | – |
| S07-B Momentum Top 10 (Einzelaktien) | +15,2 % | +25,2 % | +1,4 % | +13,9 % | −58,1 % | 0,54 | +10,6 % | 0,258 | 0,024 |
| S13-ETF ACWI mit Trendfilter | +9,4 % | +6,2 % | +6,6 % | +8,0 % | −22,6 % | 0,64 | +6,6 % | 0,653 | – |
| SP1F S&P 500 über SMA200 | +7,6 % | +9,0 % | +6,1 % | +7,7 % | −30,4 % | 0,55 | +6,5 % | 0,644 | – |
| K1 50 % S16-B + 50 % B60 | +8,0 % | +9,5 % | +3,5 % | +7,2 % | −22,9 % | 0,54 | +5,8 % | 0,737 | – |
| B60 (20 × 0,25 %) | +2,1 % | −0,8 % | −3,7 % | −0,1 % | −46,7 % | 0,06 | −0,7 % | 0,998 | – |

Steuer vereinfacht: 26,375 % ohne Sparerpauschbetrag (der Freibetrag wird meist schon vom ETF-Kern verbraucht), Verluste aus
Aktien nur gegen Aktiengewinne, Aktien-ETFs mit 30 % Teilfreistellung, Vorabpauschale nicht modelliert, US-ETFs als
Stellvertreter für UCITS-ETFs.

**Vorzeit 2003–2007** (nie benutzt, Basis-Kosten, in USD): S16-B **+17,3 %** (−15 %, Sharpe 1,14) · SPY halten +11,5 % (−14 %) ·
SP2F +8,9 % · SP1F +4,7 %. → S16-B hält auch in einem Zeitraum, den keine bisherige Kairo-Forschung gesehen hat; die
Index-Trendfilter (SP1F/SP2F) nicht.

### Kapitalgrößen (CAGR gesamt, Stress)

| Strategie | 1.000 € | 3.000 € | 5.000 € | 10.000 € | 20.000 € |
|---|---|---|---|---|---|
| S16-B | +14,1 % | +14,3 % | +14,3 % | +14,4 % | +14,4 % |
| SP2F | +13,1 % | +13,4 % | +13,4 % | +13,4 % | +13,5 % |
| S07-B | −22,4 % | +13,5 % | +13,9 % | +13,9 % | +13,9 % |
| ACWI | +9,0 % | +9,0 % | +9,0 % | +9,0 % | +9,0 % |
| B60 5 × 1 % | −28,2 % | −2,8 % | −1,2 % | −1,6 % | +1,0 % |

### Risikostufen (Anteil investiert im Train festgelegt, Rest Geldmarkt; gesamt 2008–2026)

| Ziel | S16-B | ACWI | S07-B | SP2F |
|---|---|---|---|---|
| ≈ 10 % Rückgang | 45 % investiert · +7,6 % p. a. · −14,5 % | 20 % · +3,2 % · −9,7 % | 20 % · +4,9 % · −13,9 % | 20 % · +4,2 % · −10,0 % |
| ≈ 20 % | 95 % · +13,8 % · −29,2 % | 40 % · +4,9 % · −19,7 % | 45 % · +8,5 % · −30,2 % | 40 % · +6,9 % · −19,2 % |
| ≈ 30 % | 100 % · +14,4 % · −30,6 % | 60 % · +6,4 % · −29,1 % | 70 % · +11,5 % · −44,1 % | 65 % · +9,9 % · −30,4 % |

Die im Train eingestellten Anteile halten das Ziel später nicht immer (S16-B „20 %“ erreichte −29 %): Ziel-Rückgänge sind
Richtwerte, keine Grenzen. Bei jeder Risikostufe liefert S16-B die höchste Rendite.

### Rendite-Risiko-Kurve (gesamt, 10.000 €, Stress)

S16-B (+14,4 % / −31 %) liegt oben links von allen anderen: SP2F (+13,4 % / −44 %), S07-B (+13,9 % / −58 %), ACWI (+9,0 % / −46 %),
S13-ETF (+8,0 % / −23 %), K1 (+7,2 % / −23 %), SP1F (+7,7 % / −30 %), B60 (−0,1 % / −47 %). Keine Strategie hat bei gleichem
oder kleinerem Rückgang mehr Rendite als S16-B.

### Bewertung nach Plan §7 (Wettbewerb B)

| Strategie | (a) netto > ACWI in allen drei Zeiträumen | (b) p ≤ 0,05 gegen Zufall und ACWI | (c) Vorzeit nicht schlechter | Urteil |
|---|---|---|---|---|
| **S16-B** | ✓ | Zufall ✓ 0,010 · **ACWI ✗ 0,069** | ✓ | **knapp nicht bestanden – bester Kandidat** |
| SP2F | ✗ (Holdout +5,3 %) | ✗ | ✗ | nicht bestanden |
| S07-B | ✗ (Holdout +1,4 %) | ✗ (ACWI 0,26) | – | nicht bestanden |
| alle übrigen | ✗ | ✗ | – | nicht bestanden |

**Ergebnis Wettbewerb B: Der Welt-ETF bleibt die beste *belegte* Wahl; Dual Momentum S16-B ist der klar beste Kandidat und
geht unverändert in den Papier-Test.**

| Frage | Antwort |
|---|---|
| Höchste historische Nettorendite | S16-B (+14,4 % Stress; S07-B/SP2F ähnlich, aber mit Einbrüchen im Holdout) |
| Höchste belastbar erwartbare Nettorendite | S16-B – einzige Strategie, die in allen Zeiträumen inkl. Vorzeit vorne liegt; realistisch eher ACWI + 2–4 Pp. als +5 Pp. |
| Beste risikobereinigte Rendite | S16-B (Sharpe 0,76, Calmar ≈ 0,47) |
| Beste Strategie für kleines Kapital (1.000–5.000 €) | S16-B (eine ETF-Position, ab 1.000 € +14,1 %) |
| Beste Strategie für 10.000–20.000 € | S16-B |
| Beste bei 10 / 20 / 30 % Ziel-Rückgang | S16-B mit 45 % / 95 % / 100 % investiert |

## 5. Grenzen

- Kein unberührter Datensatz: Train/Validierung/Holdout sind mehrfach benutzt; Vorzeit 2003–2007 ist der einzige neue Prüfstein
  für S16-B (nur 5 Wechsel in 5 Jahren).
- **QQQ-Rückschaufehler bei S16-B:** Der Nasdaq-100 wurde ausgewählt, nachdem er bekanntlich gut lief; die Variante ohne QQQ
  (S16-A) hatte früher deutlich schwächer abgeschnitten. Die Vorzeit (2003–2007, nach dem Dotcom-Crash) mildert den Vorbehalt
  etwas, hebt ihn aber nicht auf.
- S16-B wechselt selten (≈ 1–2× pro Jahr) – wenige Entscheidungen, große Abhängigkeit von einzelnen Wechseln.
- Einzelaktien-Ergebnisse (B60, S07-B) sind durch den gemessenen Survivorship-Bias deutlich zu gut.
- Steuern vereinfacht; US-ETFs statt UCITS-ETFs; Ausführung auf Tageskerzen.

## 6. Antworten (Plan Phase 5)

1. **Beste Rücksetzer-Strategie:** B60 bleibt; der bestätigte Ausbruch (E2) war der beste Herausforderer, aber nicht belegt.
2. **Besser als B60?** Nein, keine Variante hat den Nachweis geschafft.
3. **Beste Strategie insgesamt:** Dual Momentum S16-B (SPY/EFA/QQQ, sonst kurze Anleihen; monatlich).
4. **Besser als ein Welt-ETF?** In allen geprüften Zeiträumen ja (+5,4 Pp. p. a. nach Stress-Kosten, +4,1 Pp. nach Steuern,
   kleinerer Rückgang) – statistisch aber nur mit p 0,069, also noch kein Beweis.
5. **Größe und Belastbarkeit des Vorteils:** groß im Rückblick, mittel belastbar (Zufall klar geschlagen, Vorzeit bestätigt,
   ACWI knapp nicht signifikant, QQQ-Vorbehalt).
6. **Bester Depotaufbau:** eine einzige ETF-Position, monatliche Prüfung am Monatsende, Order am Abend für die nächste
   Eröffnung – ab 1.000 € gebührenfrei umsetzbar (PRIME+). Für Rücksetzer-Trades: 20 × 0,25 % erst ab 10.000 €.
7. **Was das Ergebnis zerstören kann:** ein Seitwärtsmarkt mit vielen Fehlsignalen (2015/16, 2022), ein schneller Crash
   innerhalb eines Monats (Signal erst am Monatsende), Ende der US-Tech-Dominanz (QQQ), höhere Steuern durch häufigere Wechsel.
8. **Nächster Papier-Test (unverändert):** S16-B als Haupt-Kandidat (läuft schon als Papier-Depot, weiterführen und monatlich
   auswerten); daneben E2 als Rücksetzer-Herausforderer gegen B60 im Papier-Depot – erst nach Jonnys Freigabe.
