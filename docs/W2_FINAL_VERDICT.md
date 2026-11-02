# W2 – Abschlussbericht (verständliche Fassung, 02.11.2026)

## Kurzfassung

**Das Signal hinter W2 ist echt. Die Strategie W2 ist es (noch) nicht.**

- „3 Verlusttage im Aufwärtstrend“ erholt sich messbar besser als ein zufälliger Kauf – in **drei unabhängigen
  Datensätzen** (USA/Europa, 1999–2007, Asien), statistisch klar.
- Der große Vorsprung von W2 im Depot (+47,5 % p. a. in der Validierung) kam aber zu einem großen Teil aus **zwei
  Fehlern bzw. optimistischen Annahmen**: Nicht ausgeführte Limits gaben ihren Platz an andere Signale ab (Vorgriff), und
  jede Berührung des Limits galt als Kauf.
- Mit korrigierter Simulation und vorsichtiger Ausführung bringt W2 **+6,4 % p. a.** (Basis-Kosten, Rückgang −52 %) –
  **weniger als der Welt-ETF (+10,5 %)** und weniger als A5 ohne Limit (+15,2 %). Und das trotz Überlebens-Verzerrung,
  die alle Werte noch schönt.
- Die Stundenkerzen der letzten zwei Jahre zeigen: Die Limits, die real sicher ausgeführt werden, waren im Schnitt
  **Verlierer** (−0,22 % je Trade).

**Status: Nicht ausreichend bestätigt oder widerlegt** – als handelbare Strategie. W2 bleibt **unverändert im
Schattentest** (kostet nichts, liefert die fehlenden Ausführungs- und Kostendaten), **kein Echtgeld**.

## Die 12 Fragen

1. **Ist W2 historisch besser als B60?** Je Trade ja. Im Depot nach Korrektur nicht: W2 (kons) +6,4 % gegen B60 +6,2 %
   p. a.; im 90/10-Portfolio beide 10,2 %. Gleichstand innerhalb der Unsicherheit.
2. **Ist W2 nach realistischen Kosten profitabel?** Knapp, mit Basis-Kosten (+6,4 %, Obergrenze wegen Überlebens-
   Verzerrung). Mit 1,99 € je Order (gettex seit 01.09.2026 laut Presse – bitte prüfen) oder höheren Spreads: **nein**
   (−2,4 % bzw. −7,4 % p. a.).
3. **Besser als Welt-ETF oder Dual Momentum?** Nein. ETF +10,5 %, 90/10 mit W2 +10,2 %, 90/10 mit Dual Momentum +10,7 %
   bei kleinstem Rückgang (−32 %).
4. **Statistisch überzeugend?** Der **Signal-Effekt** ja (Vorsprung vs. Zufall +0,26 / +0,53 / +0,50 Punkte je Trade,
   p < 0,001 in allen drei Datensätzen). Die **Depot-Rendite** nicht: Sie hängt an Ausführung und Kosten, die wir nicht
   gemessen, nur modelliert haben.
5. **Welche Fehler wurden gefunden?** 17 Funde (docs/W2_INDEPENDENT_AUDIT.md), kritisch: Nachrücken nicht ausgeführter
   Limits in der Forschungs-Engine (F1/F2) und im Live-Schattentest (F3); dazu optimistische Limit-Ausführung (F4),
   Liquiditätsfilter in Landeswährung (F6), unklare Gebühren (F9), Überlebens-Verzerrung (F12), Mehrfachnutzung der
   Daten (F13).
6. **Wie haben sich die Ergebnisse verändert?** W2-Depot gesamt: +27,7 % → +16,0 % (Engine korrigiert) → +6,4 %
   (vorsichtige Ausführung) → −2,4 % (1,99 € je Order) → −7,4 % (Stress-Kosten).
7. **Nicht ausreichend geprüfte Strategiefamilien?** Residuale Mean Reversion (Rückgang bereinigt um den Markt) – gut
   begründet, mit vorhandenen Daten prüfbar. Branchenrelative MR und liquiditätsbewusste Rangfolge scheitern an fehlenden
   Daten (Sektoren, echte Spreads). Details: docs/W2_RESEARCH_GAPS.md.
8. **Was lässt sich mit vorhandenen Daten noch sinnvoll verbessern?** Eine vorab festgelegte Prüfung der residualen
   Variante (H-RES) und ein Quartalszahlen-Abstand (nur USA). Kein weiteres Parameter-Tuning von W2.
9. **Welche Daten fehlen wirklich?** (a) **Echte Orderausführungen** (eigene Limit-Orders mit Zeitstempel und
   Ausführungskurs), (b) **Geld-/Briefkurse** auf gettex/L&S zur Handelszeit, (c) **delistete Aktien** (gegen Überlebens-
   Verzerrung), (d) Intraday-Historie > 2 Jahre. (a) und (b) bekommst nur du über echte Orders; (c)/(d) wären kostenpflichtig.
10. **Entscheidende Risiken?** Negative Auswahl bei Limit-Orders, Stückgebühren bei kleinem Kapital, Spreads außerhalb der
    US-Handelszeit, Überlebens-Verzerrung, lange Verlustserien (bis 10 Trades in Folge, schlechteste 12 Monate −28 %).
11. **W2: Schattentest, weiter untersuchen oder verwerfen?** **Unverändert im Schattentest lassen** (jetzt mit korrekter
    Depotlogik und Live-Kontrollgruppe), **nicht weiter optimieren**, **kein Echtgeld**. Verwerfen wäre verfrüht, weil
    das Signal echt ist; Echtgeld wäre verfrüht, weil die Umsetzung nicht belegt ist.
12. **Ist die Mean-Reversion-Forschung ausgeschöpft?** Mit kostenlosen Tageskursen **weitgehend ja** – bis auf H-RES. Die
    offenen Fragen sind jetzt Daten- und Umsetzungsfragen, keine Backtest-Fragen.

## Status nach vorab festgelegten Kriterien (research/reversal/w2audit.py)

| Kriterium | Ergebnis | erfüllt |
|---|---|---|
| K1 Signal netto über Zufallskauf mit gleichem Limit (kons), p < 0,05, in allen drei Datensätzen | +0,26 / +0,53 / +0,50 Pkt., p 0,0005 | **ja** |
| K2 Depot (kons, basis) in Train, Validierung und Holdout positiv und über Kontroll-Depot | +3,3 / +17,1 / +1,9 % positiv; aber im Holdout unter der Kontrolle (+4,8 %) | **nein** (strenge Lesart; gesamt 6,4 % > 1,6 %) |
| K3 Depot mit Stress-Kosten > 0 | −7,4 % | **nein** |
| K4 90/10 mit W2 besser als 100 % ETF | 10,2 % < 10,5 % | **nein** |
| K5 3.000 € mit Mindestorder 250 € > 0 | +6,4 % (basis), −33,7 % (1,99 €) | ja (nur unter Basis-Gebühren) |

„Historisch interessant, Umsetzung offen“ hätte K1 **und** K2 verlangt. K2 ist in strenger Lesart verfehlt → **Status:
Nicht ausreichend bestätigt oder widerlegt.** Die Unklarheit „über der Kontrolle gesamt oder je Zeitraum“ lag in meiner
eigenen Formulierung; ich habe die strengere Lesart angewendet.

## Live-Validierung – vorab festgelegte Kriterien (ab 02.11.2026, eingefroren)

Der Schattentest kann **keine echte Ausführung** belegen; jede Füllung dort ist ein Modell. Er misst Signalqualität,
Ausführungsquote nach Modell und Abweichungen.

| | Kriterium |
|---|---|
| L1 Umfang | mindestens 12 Monate **und** ≥ 150 beendete W2-Signale (Signal-Ebene, kons) **und** ≥ 150 beendete CTRL-L-Signale |
| L2 Signal | Ø Netto W2 − CTRL-L > 0, einseitiger Block-Bootstrap (Monate) p < 0,10 |
| L3 Depot | W2-Depot (kons, basis) > 0 % p. a. und höchstens 2 Punkte unter dem Welt-ETF im selben Zeitraum |
| L4 Ausführung | nur mit **echten** Orderdaten: Ausführungsquote und Kaufkurs innerhalb ±25 % bzw. ±0,1 % vom kons-Modell, gemessene Kosten ≤ 0,10 % je Seite, Stückgebühr bekannt |

- Nach 3 Monaten: nur Zwischenstand (beschreibend), keine Entscheidung.
- „Prospektiv und nach Kosten belastbar bestätigt“ nur mit L1–L4. Ohne echte Orderdaten (L4) ist das Höchste
  „Historisch interessant, Umsetzung offen“.
- Eine Echtgeldfreigabe erfolgt ausschließlich durch dich.

## Empfehlung

1. **Gesamtportfolio:** 90 % Welt-ETF bleibt die Basis. Für den 10-%-Teil ist nach heutigem Wissen **Dual Momentum**
   (kleinster Rückgang, kaum Orders, gebührenunempfindlich) die robusteste geprüfte Wahl; B60 bleibt als Referenz.
2. **W2:** Schattentest weiterlaufen lassen (korrigiert, mit Live-Kontrolle). Nicht verändern, nicht optimieren.
3. **Kosten klären:** Prüfe in deiner Scalable-Preisliste, ob seit 01.09.2026 auf gettex 1,99 € je Order gilt. Das
   entscheidet über jede Strategie mit vielen kleinen Orders.
4. **Forschung:** höchstens noch **eine** vorab festgelegte Prüfung (H-RES). Danach ist die Mean-Reversion-Forschung
   mit unseren Daten abgeschlossen.

Quellen zu den Gebühren (Presse, nicht die offizielle Preisliste):
[Kagel's Trading – Scalable Kosten](https://www.kagels-trading.de/scalable-capital-kosten),
[Diefinanzarena – Scalable Kosten](https://www.diefinanzarena.de/blog/scalable-capital-kosten),
[Scalable – Sonderkonditionen](https://de.scalable.capital/en/special-conditions),
[mydealz-Diskussion](https://www.mydealz.de/deals/scalable-capital-pauschal-199-pro-xetra-order-2808137).
