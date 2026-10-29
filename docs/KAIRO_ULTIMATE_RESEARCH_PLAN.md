# Kairo Ultimate – Forschungsprotokoll (Entwurf, 29.10.2026)

**Status: FREIGEGEBEN von Jonny am 29.10.2026 („Einverständnis für alles, was kostenlos ist“) und ab diesem Commit eingefroren.
Kostenpflichtige Daten (Norgate) sind nicht freigegeben.** Abweichungen nur als neue, datierte Version unten.
Fixierter Code-Stand für die gesamte Forschung: `main` @ `f11bb37` (nach Review 2, alle Korrekturen gemergt).
Datensatz: `prices_v1` (SHA-256 `e405016e2348755bb9eef3fe5e70e7f6ff405755b15487fd15fd310a5e823c3c`, 2005-01 … 2026-10-16,
USA/Europa, 2.954 Titel), Asien-Kurse aus `v2_test asia`, neue Datensätze bekommen eigene Prüfsummen.
Produktive B60-Regel (`backend/rule.py`) und Scanner bleiben unverändert. Neue Forschung nur unter `research/ultimate/`.
Keine Orders, kein PR ohne Freigabe, keine kostenpflichtigen Daten ohne Freigabe.

---

## 0. Ehrliche Ausgangslage (Kurzfassung)

1. **Es gibt keinen unberührten historischen Datensatz mehr.** Train 2008–16, Validierung 2017–21 und Holdout 2022–26
   (USA/Europa) wurden in über 30 Läufen benutzt; der Holdout ist seit 19.10.2026 offen. Nichts aus dieser Runde kann
   „bewiesen“ heißen – bestenfalls „Kandidat für den unveränderten Papier-Test“.
2. **Survivorship-Bias:** `prices_v1` enthält nur heute noch gelistete Firmen. Das begünstigt gerade Rücksetzer-Käufe
   (gefallene Aktien, die sich erholt haben, sind drin; die pleitegegangenen fehlen). Auch zufällige Einstiege mit der
   B60-Mechanik sind deshalb positiv.
3. **B60 hat je Trade nur einen kleinen Vorsprung vor dem Zufall:** +0,140 R gegenüber +0,107 R (Zufallstitel, gleiche
   Mechanik), also ≈ +0,03 R (Bericht 22). Als Depot 2008–26 (5 × 1 %, 5.000 €): +8,0 % p. a. mit Basis-Kosten, **−1,2 % mit
   Stress-Kosten**, Rückgang −53 %; ACWI halten +9,0 %, −46 % (Bericht 24). Breit gestreut (20 × 0,25 %, 10.000 €): +7,0 % /
   −0,1 %, Rückgang −27 %.
4. **Die Kosten entscheiden.** Stress-Kosten kosten je Trade ≈ 0,3–0,5 % des Kurses. Bei einem Stop-Abstand von 3–5 % sind das
   0,1 R und mehr – so viel wie der ganze Vorteil.
5. **Bester bisheriger Kandidat insgesamt:** Dual Momentum S16-B (SPY/EFA/QQQ → SHY). Als einziger in allen drei Zeiträumen
   netto besser als ACWI (Holdout +13,4 % vs. +9,8 %, Rückgang −22 %), aber gegen Zufall nur p = 0,07 (Bericht 20).

---

## 1. Bestandsaufnahme: Was wurde schon getestet?

### 1.1 Mean Reversion / Kairo

| Frage | Ergebnis | Belastbarkeit | Quelle |
|---|---|---|---|
| Kairo-Auswahl vs. Zufall (gleiche Mechanik) | +0,03 R je Trade, gepoolt p < 0,05, je Abschnitt p 0,10–0,25 | schwach, Survivorship | 22 |
| Kairo als Depot (5 × 1 %) | schlechter als ACWI, unter Stress negativ | belastbar negativ | 24 |
| Depot-Aufbau 5/10/20 Plätze | 20 × 0,25 % am stabilsten (−27 % DD), Stress ≈ 0 % | explorativ | 24 (v2.7) |
| Ausstieg: max. 60 statt 40 Tage | besser, p 0,0002 | bestätigt (je Trade) | 23 |
| Ausstieg: Nachziehen, EMA ab Tag 5, Zeit 20 T. | schlechter / nicht besser | belastbar negativ | 23 |
| Schneller Ausstieg bei Erholung (SMA5) | stark schlechter | belastbar negativ | HYBRID_MR_TEST |
| 11 Kriterien: andere Schwellen (78 Varianten) | keine besteht; Divergenz ≥ 5 überall leicht besser, n. s. | belastbar | SCHWELLEN_TEST |
| Fib 0,79 statt flacher | nicht besser, eher schlechter | belastbar negativ | 21 |
| Ruhe-Filter (Spanne/Hin und Her) | Holdout schlechter → aus | nachträgliche Schwellen | CLEAN_SETUP_TEST |
| Volumen-Austrocknung, Dochte, „Hug“ | p > 0,4 | negativ | CLEAN_SETUP_TEST |
| Starker/schneller Abverkauf davor | eher schlechter | negativ | CLEAN_SETUP_TEST |
| Rangfolge: schwaches Vormomentum zuerst | je Trade bestätigt (p 0,004); im Depot uneinheitlich | Survivorship-anfällig | 22, CLEAN_SETUP_TEST |
| Marktfilter S&P > EMA200 | kehrt sich um, nicht bestätigt | negativ | 22 |
| Qualität / KGV / Fundamental | neutral bzw. schlechter | belastbar negativ | FUND_TEST_RESULTS |
| Kauf kurz vor Quartalszahlen | nicht schlechter (eher besser) | explorativ | CLEAN_SETUP_TEST |
| 4H-Einstieg | 2017–21 n. s., 2022–26 deutlich schlechter | negativ | 28 (N1) |
| RSI(2)-Rücksetzer, Hybrid MR + Trend | Vorteil nur 2008–16, danach weg | belastbar negativ | HYBRID_MR_TEST, 16 |
| S19 Hybride MR (4H, SEC) | handelt kaum, ≈ 0 % | negativ | 12, 30 |
| Asien (B60 unverändert) | +0,08 / +0,13 / +0,17 R, alle positiv | einmal benutzt | CLEAN_SETUP_TEST |

**Noch nie getestet:** Einstieg per Ausbruch über das Basishoch (Buy-Stop), Früheinstieg mit Umkehrkerze, erneute
Gültigkeitsprüfung zwischen Treffer und Kauf (außer „Tief unter Invalidierung“), Ursache des Rückgangs (Quartalszahlen
vs. ohne Nachricht), Kosten je R als Filter, Kairo in Kombination mit Dual Momentum innerhalb des Trading-Topfs.

### 1.2 Andere Strategiefamilien

| Strategie | Train | Validierung | Holdout | Urteil |
|---|---|---|---|---|
| S16-B Dual Momentum SPY/EFA/QQQ → SHY | +16,6 % | +19,3 % (p 0,025) | +13,4 % (p 0,07) | einziger konsistenter Kandidat, QQQ-Rückschau-Vorbehalt |
| S07-B Momentum 6-1/Vol Top 10 | +16,9 % | +27,9 % | +8,3 %, −57 % DD, p 0,72 | im Holdout gescheitert |
| S13-ETF ACWI > SMA10 | +8,7 % (2008–21) | +6,7 % | – | ruhig (−22 %), weniger Rendite |
| SP2F S&P 500 2× über SMA200 (1989–2026) | +12,5 % | +10,2 % | +16,6 % | knapp nicht bestanden (SMA100 schwach) |
| Multi-Asset TSMOM G4 | +6,9 % | +4,1 % | – | nicht bestanden |
| Faktoren K1–K4, PEAD, Insider | positiv | < ACWI, = Zufall | – | nicht bestanden |
| S20 Trendfolge/VCP, Ausbruch 55 T. | – | negativ / = Zufall | – | nicht bestanden |
| Hebel / Zielvolatilität auf ETF + DM | – | – | – | kein Renditegewinn |

### 1.3 Was war zum Handelstag bekannt?

- Kurse: nur bis zum Entscheidungstag; Kauf frühestens zur nächsten Eröffnung (Engine erzwingt das).
- Quartalszahlen: SEC 8-K Punkt 2.02 mit Einreichungszeitpunkt (Release `research-sec-v3`), nur USA.
- Fundamentaldaten: XBRL erst ab dem Tag nach der Einreichung.
- Universum: heutige Liste → Survivorship (nicht behebbar mit Gratisdaten).
- Wechselkurse: nur bis zum Tag (seit Review-Paket 3 auch im Papier-Depot).

---

## 2. Einheitliche Forschungsbasis (Pflicht vor jedem Vergleich)

- **Einziger Simulator:** `research/strategy_championship/engine.py` (Kassenbuch, Lücken, PRIME+-Kosten, Stückzahlen,
  Kapitalbindung, max. offene Positionen). Keine Zahlen aus anderen Simulatoren im Vergleich.
- **B60-Reproduktion:** `backend/tests/test_b60_same.py` zeigt schon heute, dass Live-Strategie, h4live, Papier-KAIRO und
  Engine denselben Trade ergeben. Vor Runde 1 zusätzlich: der B60-Depot-Lauf (5.000 €, 5 × 1 %, mom) muss die Zahlen
  aus Lauf 40925193877 exakt wiederholen (+15,1 % / −6,9 % / +11,9 %), sonst Abbruch und Fehlersuche.
- **Kosten:** Basis = PRIME+ (0,99 € unter 250 €, sonst 0), gemessene Spannen je Titel. Stress = 1,99 € unter 250 €,
  Spanne 0,2 %, Slippage 0,05 % je Seite, Fremdwährung 0,1 % je Seite. Ergänzend „Hart“: Spanne 0,4 % (Nebenwerte).
- **Steuern (vereinfacht, gekennzeichnet):** 26,375 % (Abgeltung + Soli, ohne Kirchensteuer), Sparerpauschbetrag
  1.000 € p. a.; **Aktien-Verluste nur mit Aktien-Gewinnen verrechenbar** (eigener Topf); Aktien-ETFs 30 % Teilfreistellung,
  Vorabpauschale vereinfacht; Verlustvortrag ins nächste Jahr. Welt-ETF: Steuer erst beim Verkauf am Ende.

---

## 3. Wettbewerb A – beste Rücksetzer-Strategie

Gemeinsam für alle Varianten: Treffer = unveränderter Scanner 11/11 (Signale aus Sweep-Variante 0), Invalidierung =
tiefstes Tief der 10 Kerzen bis zum Treffer, höchstens 10 Kerzen warten, Ausstieg B60 (Stop, EMA20-Schluss ab Tag 10,
spätestens Tag 60), Rangfolge mom. Je Hypothese **eine** vorab festgelegte Regel, keine Parametersuche.

| Nr. | Hypothese | Regel (fest) | Wirtschaftliche Begründung |
|---|---|---|---|
| **H1** | Einstieg (A3) | **E0** B60 wie heute. **E1 Früheinstieg:** ab der 3. Kerze nach dem Treffer, wenn die letzten 3 Kerzen ≤ 1,5 ATR Spanne haben UND der Tag im oberen Drittel seiner Spanne und über dem Vortageshoch schließt → Kauf zur nächsten Eröffnung, Stop = tiefstes Tief seit Treffer − 0,25 ATR. **E2 Bestätigter Ausbruch:** nach fertiger 5-Kerzen-Basis Buy-Stop am Abend auf Basishoch + 0,05 ATR, gültig bis 10 Kerzen; Ausführung zum Stop-Kurs, bei Kurslücke zur Eröffnung nur bis Basishoch + 0,5 ATR, sonst verfällt die Order; Stop = Basistief − 0,25 ATR. | E1: früher drin = größere Gewinner bei gleichem Stop. E2: Ausbruch filtert scheiternde Basen (≈ 2/3 der Trades verlieren), kostet aber Einstiegspreis. Beide sind abends vorab platzierbar. |
| **H2** | Gültigkeit vor dem Kauf (A4) | **V1:** B60, aber Kauf entfällt, wenn zwischen Treffer und Kauf an einem Schluss MACD wieder unter die Signallinie fällt **und** RSI14 unter dem RSI des Treffertags liegt (Umkehr gescheitert). Nicht alle 11 Kriterien neu verlangen. | Ein Momentum-Umkehrsignal, das vor dem Kauf zurückfällt, ist eine neue, schlechtere Lage; Kapital bleibt frei für intakte Treffer. |
| **H3** | Ursache des Rückgangs (A1) | **N1:** nur USA. Treffer ausschließen, wenn im Rückgang (Hoch → Treffer) eine Quartalsmeldung (8-K 2.02) lag, auf die der Kurs am Folgetag ≤ −5 % reagierte („Nachrichten-Rückgang“). Beschreibend zusätzlich: Anteil des Rückgangs, der auf die Branche entfällt. | Literatur (Chan 2003; PEAD): Kurse fallen nach schlechten Nachrichten weiter, Rückgänge ohne Nachricht erholen sich eher. |
| **H4** | Kosten je R | **C1:** B60, aber nur Trades, deren Stress-Kosten (Kauf + Verkauf) höchstens 0,10 R betragen, d. h. Stop-Abstand ≥ 10 × Kosten in % (≈ ≥ 3 % bei Euro-Aktien, ≥ 5 % bei Fremdwährung). | Kein Vorhersage-, sondern ein Kostenvorteil: enge Stops machen die festen Kosten im Verhältnis riesig. |
| **H5** | Kombination (Wettbewerb B) | **K1:** Trading-Topf 50 % Dual Momentum S16-B + 50 % bester Rücksetzer aus H1–H4 (sonst B60) mit 20 × 0,25 %, jährliches Rebalancing. | Tagesrenditen DM–Kairo-S korrelieren nur 0,45; DM handelt monatlich, B60 wochenweise. |

**Bewusst nicht in Runde 1:** Verkaufsdruck-Merkmale (A2) – Volumen-Austrocknung, Dochte, Ruhe, Divergenz-Schwellen und
Abverkaufs-Tempo wurden schon getestet und sind gescheitert oder nicht signifikant; eine neue Kombination daraus wäre
Datenschürfen. Ausstieg (A5) bleibt B60 (Nachziehen, EMA ab Tag 5 und Zeitausstieg 20 T. waren schlechter); erst in
Runde 2 und nur für eine Siegervariante.

---

## 4. Wettbewerb B – beste Strategie insgesamt

Teilnehmer, jeweils mit den **bereits festgelegten** Regeln (keine Nachoptimierung):
B60 · bester Rücksetzer aus A · S16-B Dual Momentum · S07-B Momentum Top 10 · SP1F/SP2F S&P 500 über SMA200 (1× / 2×,
gehebelter UCITS-ETF als Umsetzung) · S13-ETF ACWI > SMA10 · K1-Kombination · Kontrollen: ACWI halten, Zufallsdepots
(gleiche Mechanik, zufällige Titel bzw. zufällige ETF-Auswahl, 200 Seeds).
Bekannte Schwächen bleiben stehen: S19/S20, RSI(2), 4H und Faktorstrategien werden nicht wiederholt.

---

## 5. Depot-Modell

- Kapital: 1.000 / 3.000 / 5.000 / 10.000 / 20.000 €.
- Aufbau (nur Stop-Strategien): 5 × 1 %, 10 × 0,5 %, 20 × 0,25 % Risiko je Trade; Einsatz nie über freie Kasse.
- Realistisch: ganze Stückzahlen, PRIME+-Grenze 250 €, Spanne/Slippage, Wechselkurse am Tag, Kurslücken über Nacht
  (Stop zur Eröffnung, wenn darunter), Orders, die nicht ausführbar sind (außerhalb der Spanne, Lücke über Grenze), verfallen.
- Strategien, die erst ab mehr Kapital als 20.000 € funktionieren, scheiden aus.

### Risikostufen

Ziel-Rückgang 10 / 20 / 30 % (Forschungsziele, keine Garantie): Anteil investiert vs. Tagesgeld (Zins = Geldmarkt) bzw.
Risiko je Trade wird **nur im Train** so gewählt, dass der größte Rückgang das Ziel trifft; danach unverändert auf
Validierung und Bestätigung. Hebel nur, wenn eine Strategie ungehebelt bestanden hat. Zusätzlich eine Auswertung
„höchste absolute Rendite“ – nur informativ. Ergebnis: Rendite-Risiko-Kurve aller Teilnehmer.

---

## 6. Kennzahlen (jede Variante)

CAGR Basis / Stress / Hart, nach Steuern; größter Rückgang; Sharpe, Sortino, Calmar; Profit-Faktor; Ø und Median R netto;
Trefferquote; Trades; Ø Haltedauer; Kapitalauslastung; Ø Kosten je Trade (€ und R); schlechteste 12 Monate und Marktphase;
Ergebnis ohne die besten 1 % Trades; Block-Bootstrap-Intervalle (90 %) für CAGR und Ø R.

---

## 7. Gegen Überanpassung

1. Diese Datei wird vor dem ersten Lauf eingefroren (Commit-Hash in den Ergebnissen); jede Abweichung = neue Version.
2. Höchstens 5 Haupt-Hypothesen (H1–H5), 6 Vergleiche (E1, E2, V1, N1, C1, K1).
3. **Entdeckung:** Train 2008–16 → Validierung 2017–21 (vorwärts: Entscheidung nur mit Train, Prüfung in Validierung).
   Holdout 2022–26 wird berichtet, zählt aber **nicht** als Beweis (schon geöffnet).
4. **Bestätigung (für diese Hypothesen nie benutzt):**
   - **K-Vorzeit:** USA/Europa 1999–2007 (Dotcom-Crash, kostenlos neu von Yahoo geladen, eigene Prüfsumme). Noch stärkerer
     Survivorship-Bias → nur **relativer** Vergleich (Variante vs. B60 vs. Zufall), keine absoluten Renditen.
   - **K-Asien:** 2008–26, B60 bisher nur einmal als Ganzes geprüft; die Varianten dort nie.
   - Für ETF-Strategien: S16-B/SP2F 2001–2007 (vor dem bisherigen Train).
5. Block-Bootstrap mit 3-Monats-Blöcken; Holm-Korrektur über die 6 Vergleiche.
6. Kontrolle gegen Zufall mit identischer Mechanik.
7. Stress- und Hart-Kosten.
8. Danach unveränderter Papier-Test (≥ 6, besser 12 Monate) – erst dann echtes Geld.

### Bestehensregeln Wettbewerb A (alle müssen erfüllt sein)

1. Ø R netto (Stress) mindestens +0,05 R besser als B60 in Train **und** Validierung.
2. Depot-CAGR (Stress, 10.000 €, 20 × 0,25 %) höher als B60 in Train **und** Validierung.
3. Gepoolt Train + Validierung: Bootstrap-p ≤ 0,05 nach Holm-Korrektur.
4. Gleiche Richtung (Ø R besser als B60) in K-Vorzeit **und** K-Asien (für N1 nur USA-Vorzeit).
5. Besser als Zufall mit gleicher Mechanik (p ≤ 0,10), mindestens 300 Trades je Abschnitt.

Sonst: **„Keine Verbesserung nachgewiesen“** – B60 bleibt.

### Bestehensregeln Wettbewerb B

Gewinner einer Risikostufe ist die Strategie mit der höchsten CAGR nach Stress-Kosten und Steuern, wenn sie (a) in
Train, Validierung und Holdout netto über ACWI liegt, (b) gegen Zufall und gegen ACWI p ≤ 0,05 (Holm) erreicht und (c) in
der Bestätigung (Vorzeit) nicht schlechter als ACWI ist. Erfüllt das keiner: Ergebnis „Welt-ETF bleibt beste belegte Wahl“,
bester Kandidat geht in den Papier-Test.

---

## 8. Daten und Rechenaufwand

- Vorhanden: `prices_v1`, Benchmarks `bench_v1`, ETF-Daten, SEC-Release `research-sec-v3`, Asien-Kurse.
- Neu (kostenlos): Yahoo-Kurse 1997–2007 für dasselbe Universum (`prices_pre_v1`), ETF-Kurse ab 1993.
- Rechnen: GitHub Actions wie bisher (Matrix-Läufe, ≈ 40 Shards), geschätzt 3–6 Stunden Laufzeit je Runde, keine Kosten.
- **Optional, kostenpflichtig – nur mit Freigabe:** Norgate Data US Platinum (inkl. Delistings seit 1990), 630 USD für
  12 Monate bzw. 346,50 USD für 6 Monate laut Norgate-Preisseite (vor Kauf prüfen; Daten nach Ablauf zu löschen). Würde den
  Survivorship-Bias für die USA klären und wäre der einzige echte neue Prüfstein.

## 8b. Datenqualität – Pflicht vor jedem Strategietest (Wunsch Jonny, 29.10.2026)

Kein Ergebnis darf durch schlechte oder ungenaue Daten entstehen. Deshalb gilt:

1. **Prüfung jedes Datensatzes** (`research/ultimate/data_audit.py`, Workflow `research_ultimate_audit.yml`) –
   USA/Europa, Asien und die neue Vorzeit 1999–2007 einzeln:
   Lücken, unmögliche Kerzen (Hoch unter Schluss usw.), Fehlkurse (Sprung > 40 % mit Rücklauf am Folgetag),
   Stillstand, nicht bereinigte Splits, **Gegenprobe mit einer zweiten, unabhängigen Quelle (Stooq)** an einer
   Zufallsstichprobe, Vergleich mit einem frischen Yahoo-Download (nachträgliche Änderungen) und Anteil der Kairo-Treffer,
   die von markierten Tagen betroffen sind.
2. **Gate (vorab festgelegt):** Ein Datensatz wird nur benutzt, wenn unmögliche Kerzen < 0,1 % aller Kerzen, Median-
   Übereinstimmung mit Stooq ≥ 98 % der Tage (±1 %) und höchstens 5 % der Treffer von markierten Tagen betroffen sind.
   Sonst: erst reparieren (neu laden / Titel ausschließen), Prüfung wiederholen.
3. **Unsichere Titel** (Fehlkurs, Split-Rest, viele kaputte Kerzen oder Gegenprobe < 95 %): jedes Ergebnis wird einmal
   mit und einmal ohne sie gerechnet. Kippt das Urteil, gilt es als **nicht belastbar**.
4. **Survivorship-Bias messen statt nur nennen:** Gleichgewichtetes Halten unseres US-Universums gegen den
   gleichgewichteten S&P 500 (RSP, alle damaligen Mitglieder) – der Abstand pro Jahr ist eine Untergrenze für die
   Verzerrung. Jede absolute Rendite einer Einzelaktien-Strategie wird mit diesem Abstand ausgewiesen.
5. **Wechselkurse und Benchmarks** werden mit derselben Prüfung kontrolliert (Lücken, Sprünge).
6. **Was Prüfungen nicht reparieren können:** fehlende Pleite-Firmen. Mit Gratisdaten bleibt dieser Vorbehalt bei jedem
   Rücksetzer-Ergebnis stehen; nur Daten mit Delistings (z. B. Norgate) lösen ihn – Entscheidung bei Jonny.

## 9. Grenzen der Aussagekraft

Survivorship-Bias (nicht behebbar ohne Bezahldaten), mehrfach benutzte Zeiträume, Gratisdaten (Yahoo-Fehler, Splits),
vereinfachte Steuern, Ausführung im Modell (Tageskerzen, keine Teilausführung, keine Handelsunterbrechungen).
Kein Ergebnis dieser Runde wird als „bewiesen“ bezeichnet.

## 9b. Präzisierungen beim Einfrieren (vor jedem Lauf, 29.10.2026)

- **E1:** Kauf nur, wenn die Eröffnung in (Stop, Schluss des Auslösetags + 0,5 ATR] liegt; sonst verfällt die Order (je
  Auslösetag eine Order, höchstens ein Kauf je Treffer). Fenster wie B60: Kerze 3 … 10 nach dem Treffer, Invalidierung gleich.
- **E2:** Je Abend nach fertiger Basis eine Buy-Stop-Order für den nächsten Tag (Basishoch/-tief der ersten fertigen Basis,
  danach unverändert), höchstens 10 Abende; Tief unter dem Basistief vor dem Ausbruch → keine weiteren Orders. Ausführung,
  wenn das Tageshoch den Stop-Kurs erreicht: zum Stop-Kurs bzw. zur Eröffnung, wenn diese darüber liegt (höchstens
  Basishoch + 0,5 ATR, sonst verfällt das Signal). Am Kauftag zählt ein Tief unter dem Stop als ausgestoppt (vorsichtig,
  Reihenfolge im Tag unbekannt). Risiko 0,5–3 ATR wie B60, gemessen ab dem Ausführungskurs.
- **V1:** MACD 12/26/9 und RSI14 (Wilder) auf bereinigten Schlusskursen der ganzen Reihe bis zum jeweiligen Tag.
- **N1:** Rückgangsfenster = 60 Handelstage bis einschließlich Treffertag. Reaktionstag = erster Handelstag am/nach dem
  Annahmedatum der 8-K (Punkt 2.02); Reaktion = Schluss Reaktionstag / Schluss Vortag − 1 (bereinigt). Titel ohne
  SEC-Zuordnung bleiben drin (wie B60).
- **C1:** Kostenquote = 2 × (Stress-Spanne/2 + Slippage + FX) des Titels; Stop-Abstand = (Schluss des Entscheidungstags −
  Stop) / Schluss. Order nur, wenn Kostenquote / Stop-Abstand ≤ 0,10.
- **Je Trade (Ø R):** unbegrenztes Kapital, Stress-Kosten ohne feste Gebühr (die zählt im Depot-Test).
- **Zufall:** je Treffer ein zufälliger zulässiger Titel desselben Tags und derselben Region mit derselben Einstiegsvariante,
  20 Durchgänge.

## 10. Ablauf und Ergebnisse

Runde 1 (nach Freigabe): Reproduktion B60 → H1–H4 je Trade und im Depot → Bestätigung → Wettbewerb B mit H5 und
Risikostufen. Ergebnisse in `docs/KAIRO_ULTIMATE_RESULTS.md` mit Commit, Datensatz-Prüfsummen, Parametern und Lauf-IDs.
