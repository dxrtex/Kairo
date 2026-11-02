# W2 – Lückenanalyse der Mean-Reversion-Forschung (Stand 02.11.2026)

Teil des unabhängigen W2-Audits. Frage: Welche ernsthaft begründeten Ansätze wurden noch **nicht** oder nur unvollständig
geprüft – und welche lassen sich mit unseren kostenlosen Daten überhaupt belastbar prüfen? W2 bleibt dabei eingefroren.

Status: **getestet** (vorab festgelegt, mit Kontrolle und unabhängiger Bestätigung) · **unvollständig** · **nicht getestet** ·
**nicht belastbar prüfbar** (Daten fehlen).

## 1. Bestandsaufnahme der geprüften Strategieklassen

| Klasse | Varianten | Status | Ergebnis |
|---|---|---|---|
| Kurzfristige Einzelaktien-MR (RSI(2), IBS, 3/4 Verlusttage, Z-Score) | A1–A9, A5L, A1L, A6L, W3, W4 | getestet (Hauptdaten) | A5 vorn, nur mit niedrigen Kosten; Rest schwächer |
| MR mit Kauf-Limit | W1, W2 | getestet + Bestätigung Vorzeit/Asien + Audit | Signal je Trade signifikant über Zufallskauf mit gleichem Limit; nach Audit-Korrektur im Depot schwächer als A5 (Marktorder) und als der Welt-ETF; Stundenkerzen zeigen negative Auswahl bei sicher ausgeführten Limits |
| Wochen-Verlierer (Short-Term-Reversal) | A7, A7L | getestet | hohe Kostenempfindlichkeit, nicht bestanden |
| B60 mit anderen Ausstiegen/Basis | B1–B11 | getestet | nicht besser als B60 |
| ETF-MR | C1 (Index-ETFs), ETF-RSI(2) live | getestet | robust, aber unter Welt-ETF |
| Filter aus Zusatzinfos | Insider, Analysten, Qualität, Quartalszahlen, Meta-Modell | getestet | nichts besteht |
| RSI-Signallinie, Divergenz | R1–R3 + Kombinationen | getestet | Hinweise, nicht bestanden |
| Kerzen-/Chartformationen | 6 Kerzen, W-Boden, Cup | getestet | nicht bestanden |
| Marktbreite-Filter für W2 | W2-BREITE | getestet (Vorzeit/Asien) | nicht besser |
| Ausstieg Vortageshoch für W2 | W2-VH | getestet (Vorzeit/Asien) | nicht besser |
| Mindestorder 250 € | W2-250 | getestet | ohne Wirkung bei 10.000 €, Wirkung bei Kleinkapital siehe Kostenbericht |

## 2. Lücken nach Themen (Vorgabe A–F)

### A. Branchenrelative Mean Reversion – **nicht belastbar prüfbar (nur USA eingeschränkt)**
Fällt eine Aktie stärker als ihr Sektor? Im eingefrorenen Universum fehlt die Sektor-Zuordnung (Spalte leer, siehe
Lern-Test 01.11.2026). Für US-Werte ginge eine Näherung über die SPDR-Sektor-ETFs (XLK, XLF …) – dafür bräuchte es eine
Sektor-Zuordnung je Aktie (kostenlos nur unzuverlässig per Yahoo-Abfrage). **Ökonomische Begründung: mittel** (Branchen-
nachrichten erklären einen Teil des Rückgangs; der Rest ist eher Überreaktion).

### B. Residuale Mean Reversion – **nicht getestet, prüfbar, Priorität 1**
Den Teil des 3-Tage-Rückgangs isolieren, der NICHT durch den Markt der Region (^GSPC, ^STOXX) erklärt wird
(Beta-bereinigt, 60-Tage-Schätzung aus der Vergangenheit). Die Literatur (z. B. „Short-term residual reversal“,
Blitz u. a. 2013) findet bei residualen Umkehrsignalen einen stabileren, weniger marktabhängigen Effekt als bei
Rohrenditen. **Mit vorhandenen Daten prüfbar** (Indizes sind im Datensatz). Begründung: **hoch**. Vorschlag einer
vorab festgelegten Hypothese:
> H-RES: „W2-Signale, deren 3-Tage-Rückgang zu ≥ 70 % unternehmensspezifisch ist (Residuum), erholen sich stärker als
> W2-Signale mit überwiegend marktbedingtem Rückgang“ – geprüft je Trade gegen CTRL-L, Vorzeit + Asien als Bestätigung.
Achtung: Das wäre eine W2-Variante. W2 bleibt eingefroren; H-RES würde als eigener Herausforderer laufen.

### C. Liquiditätsbewusste Mean Reversion – **unvollständig, Daten fehlen**
A5L/A1L/A6L (nur liquide Titel) waren schwächer – der Bruttoertrag kommt eher aus weniger liquiden Werten, wo die
echten Spreads höher sind. Eine Rangfolge nach *erwartetem Nettoertrag* braucht **gemessene Spreads** je Titel und
Handelsplatz. Die haben wir nicht (nur ein Liquiditäts-Modell). **Erst mit echten Geld-/Briefdaten sinnvoll** – Quelle:
eigene Orderdaten (Journal-Kosten-Check) oder kostenpflichtige Daten (nicht freigegeben).

### D. Marktregime und Volatilität – **beschreibend erledigt, keine Filter**
Ausverkaufs-Risiko (B5), Marktbreite (W2-BREITE) wurden geprüft und nicht bestanden. Der Audit-Lauf zeigt den W2-Ertrag
nach VIX-Stufen nur beschreibend. Ein Filter nur, weil er rückblickend gut aussieht, wäre Datenschnüffelei – **nicht
weiter verfolgen**, außer mit neuer ökonomischer Begründung und neuen Daten.

### E. Alternative Instrumente – **getestet**
ETF-RSI(2) (C1 und Sektor-ETFs live): geringste Kosten, robust, aber unter dem Welt-ETF. Einzelaktien-Optionen,
Futures, Leerverkäufe: bei Scalable mit Aktien nicht sinnvoll / nicht im Risikoprofil – **bewusst ausgeschlossen**.

### F. Portfolio statt Einzeltrade – **unvollständig**
Geprüft: 5/10 Plätze, Kapitalbindung, Mindestorder, Kapitalgrößen (Audit). **Nicht geprüft:** Sektor-Klumpen innerhalb
der 5 Plätze (Daten fehlen, siehe A), dynamische Platzzahl nach Signalmenge, Nettoertrag je gebundener Kapitaleinheit
gegen ETF-Opportunitätskosten (der Audit liefert den Vergleich über die 90/10-Rechnung). Begründung: **mittel**;
Effekt eher auf Schwankung als auf Rendite.

## 3. Weitere Ansätze

| Ansatz | Status | Bewertung |
|---|---|---|
| Kauf kurz vor Börsenschluss statt Folgetag (Overnight-Effekt) | nicht belastbar prüfbar | keine historischen Intraday-Daten (kostenlos nur ~2 Jahre Stundenkerzen) |
| Limit-Höhe als Raster (0,25/0,5/0,75/1,0 ATR) | nicht getestet | **bewusst nicht**: wäre Feintuning auf bekannten Daten. Erst nach Live-Daten zur Ausführung |
| Gewinnmitnahme-Ziel statt 5-Tage-Linie | unvollständig (Vortageshoch, SMA20 geprüft) | geringe Priorität |
| Quartalszahlen-Abstand (kein Kauf kurz vor Zahlen) | unvollständig | Begründung hoch (Lückenrisiko); 8-K-Termine nur USA; Priorität 2 |
| Paare / statistische Arbitrage | nicht belastbar prüfbar | braucht Leerverkauf |
| Maschinelles Lernen über alle Merkmale | getestet (Meta-Modell für B60) | nicht bestanden; für W2 nicht wiederholen ohne neue Daten |

## 4. Priorisierung (nur ernsthaft begründete, noch offene Ansätze)

1. **H-RES – residuale Mean Reversion** (Begründung hoch, Daten vorhanden, eine vorab festgelegte Hypothese, Bestätigung
   auf Vorzeit/Asien). Einziger Ansatz mit realistischer Chance auf echten Mehrwert ohne neue Daten.
2. **Quartalszahlen-Abstand** (nur USA, 8-K-Daten vorhanden) – Risikoreduktion statt Renditesuche.
3. **Liquiditätsbewusste Rangfolge** – erst wenn echte Spreads aus Orders/Journal vorliegen.

## 5. Wo zusätzliche historische Optimierung keinen Mehrwert mehr liefert

- Weitere Parameter-Raster für W2 (Limit-Abstand, Ausstieg, Filter): Die Hauptdaten sind mehrfach ausgewertet; jede weitere
  Variante erhöht vor allem die Wahrscheinlichkeit eines Zufallssiegers.
- Weitere technische Muster (Kerzen, Indikator-Kombinationen): mehrfach geprüft, ohne Bestand.
- Regime-Filter ohne neue ökonomische Begründung.

**Fazit:** Mit unseren kostenlosen Tageskursen ist die Forschung zu W2 im Kern ausgeschöpft – bis auf **einen** gut
begründeten offenen Ansatz (H-RES) und eine Risikofrage (Quartalszahlen). Die wichtigsten offenen Fragen (echte
Ausführung, echte Spreads, echte Kosten) sind **keine Forschungs-, sondern Datenfragen** und lassen sich nur prospektiv
beantworten.
