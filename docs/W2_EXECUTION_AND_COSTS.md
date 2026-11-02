# W2 – Ausführung, Kosten, Kapital, Gesamtportfolio (02.11.2026)

Alle Zahlen: `research/reversal/w2audit.py` über `backend/mrsim.py` (Lauf `w2a-41415380358`). USA/Europa 2008–2026,
10.000 € Startkapital, 5 Plätze, Top-10-Signale je Tag, Kapitalreservierung, kein Nachrücken, ganze Stücke, EUR.
**Absolute Renditen sind wegen Überlebens-Verzerrung Obergrenzen.**

## 1. Ausführungsmodelle für das Kauf-Limit

| Modell | Regel | Ausführungsquote | Ø netto je Trade (Basis-Kosten) | Vorsprung vs. Zufall (gleiches Limit) |
|---|---|---|---|---|
| opt (bisherige Annahme) | Tagestief ≤ Limit | 39 % | +0,48 % | +0,25 Pkt. |
| kons | Briefkurs muss Limit erreichen: Tief ≤ Limit·(1 − halber Spread − 0,1 %) | 33 % | +0,34 % | +0,26 Pkt. |
| streng | … − 0,5 % (Kurs läuft deutlich durch) | 24 % | +0,12 % | +0,29 Pkt. |

**Marktnahe Prüfung mit Stundenkerzen** (Yahoo, kostenlos, nur 15.11.2024–16.10.2026, 4.829 W2-Signale):

| | Ausführungsquote | Ø netto je Trade |
|---|---|---|
| Tagestief berührt Limit (opt) | 38,0 % | **+0,31 %** |
| kons (Tageskerzen) | 32,8 % | – |
| mind. eine Stundenkerze **schließt** unter dem Limit | 28,4 % | **−0,22 %** |
| mind. zwei Stundenkerzen mit Tief unter dem Limit | 30,8 % | **−0,11 %** |

Von den „berührten“ Limits waren 86 % auch nach kons, 75–81 % nach den Stunden-Kriterien ausführbar. **Entscheidend:**
Die Trades, bei denen der Kurs eine Weile unter dem Limit lag – also die, die real am sichersten ausgeführt werden –
waren im Schnitt **Verlierer**. Die Gewinne stammen überproportional aus kurzen Dochten, bei denen eine echte Order oft
nicht zum Zug kommt (Warteschlange). Das ist klassische **negative Auswahl bei Limit-Orders**. Nur 2 Jahre, nur Modell –
aber es ist der realistischste Test, den unsere kostenlosen Daten erlauben, und er spricht gegen W2.

## 2. Wirkung der Korrekturen auf das Depot (10.000 €, Basis-Kosten)

| Stand | Train | Validierung | Holdout | gesamt |
|---|---|---|---|---|
| Welle 3 (alte Engine, Nachrücken, opt) | +26,0 % | +47,5 % | +12,3 % | +27,7 % |
| Engine korrigiert (Reservierung), opt | +13,9 % | +27,4 % | +8,7 % | +16,0 % |
| mrsim opt (Spread 0,15/0,30 %) | +10,7 % | +29,4 % | +11,5 % | +15,6 % (Rückgang −39 %) |
| **mrsim kons** | **+3,3 %** | **+17,1 %** | **+1,9 %** | **+6,4 % (−52 %)** |
| mrsim streng | −4,4 % | +1,7 % | −5,7 % | −3,1 % (−76 %) |
| Kontrolle CTRL-L kons | −0,8 % | +3,2 % | +4,8 % | +1,6 % |
| A5 (Marktorder, kein Ausführungsrisiko) | +8,6 % | +28,6 % | +15,0 % | +15,2 % (−39 %) |
| Welt-ETF (ACWI, EUR) | | | | ≈ +10,5 % |

Die Engine-Korrektur (F1) halbiert den alten Wert; das vorsichtige Ausführungsmodell drittelt ihn noch einmal. Unabhängig
gerechnet stimmen Engine (opt, +16,0 %) und mrsim (opt, +15,6 %) gut überein.
**Nach Korrektur ist W2 im Depot nicht besser als A5** – der Limit-Vorteil verschwindet, sobald man nicht mehr
nachrücken darf und die Ausführung vorsichtig modelliert.

## 3. Kostenszenarien (W2, kons, 10.000 €, gesamt 2008–2026)

| Szenario | Annahme | Rendite p. a. | Rückgang | Gebühren gesamt |
|---|---|---|---|---|
| null | keine Kosten | +14,9 % | −35 % | 0 € |
| basis | PRIME+ 0,99 € < 250 €, Spread 0,15 % (liquide) / 0,30 % | +6,4 % | −52 % | 22 € |
| free | 0,99 € je Order | +3,6 % | −59 % | 6.515 € |
| **g199** | **1,99 € je Order (gettex ab 01.09.2026 laut Presse – unbestätigt)** | **−2,4 %** | −74 % | 13.080 € |
| stress | Spread ×2, 0,05 % Schlupf, 0,1 % FX | −7,4 % | −82 % | 32 € |

Kosten fressen den Ertrag fast vollständig: Zwischen „ohne Kosten“ (+14,9 %) und „Basis“ (+6,4 %) liegen 8,5 Punkte –
bei ~190 Trades im Jahr und ~0,4 % Bruttoertrag je Trade. **Unbekannte Kosten wurden nirgends als null angesetzt;**
die echten Spreads auf gettex/Lang & Schwarz sind **nicht gemessen** (keine kostenlose Quelle).

**Bitte prüfen:** Gilt bei dir seit 01.09.2026 auf gettex 1,99 € je Order (auch mit PRIME+)? Falls ja, ist W2 mit
≤ 10.000 € unwirtschaftlich. Quellen der Presseberichte: siehe Abschlussbericht.

## 4. Kapitalgrößen (W2, gesamt 2008–2026)

| Kapital | 5 feste Plätze, basis | Mindestorder 250 €, basis | Mindestorder 250 €, g199 | Hinweis |
|---|---|---|---|---|
| 500 € | −20,9 % (Totalverlust-Nähe) | +7,5 % (kons) | −28,9 % | 2 Plätze; ohne Mindestorder Gebührenfalle |
| 1.000 € | −22,1 % | +7,0 % | −64,7 % | |
| 3.000 € | +6,4 % | +6,4 % | −33,7 % | |
| 5.000 € | +6,3 % | +6,3 % | −33,9 % | |
| 10.000 € | +6,4 % | +6,4 % | −2,4 % | |
| 20.000 € | +6,4 % | +6,4 % | +3,6 % | |

(kons-Modell; mit opt ab 3.000 € jeweils rund +9 Punkte mehr, darunter ebenfalls Gebührenfalle.) Mit 90/10 entspricht dein Tradingteil bei 30.000 € Gesamtvermögen
nur 3.000 € – genau der Bereich, in dem eine Stückgebühr von 1,99 € die Strategie zerstört.

## 5. Gesamtportfolio (Start 10.000 € + 200 €/Monat, monatlich ausgeglichen, EUR, 2008–2026)

| Portfolio | Rendite p. a. | größter Rückgang | Endwert (eingezahlt 54.600 €) |
|---|---|---|---|
| **100 % Welt-ETF** | **+10,5 %** | −41 % | 218.694 € |
| 90/10 W2 (kons) | +10,2 % | −38 % | 208.184 € |
| 90/10 W2 (opt – zu optimistisch) | +11,1 % | −38 % | 235.093 € |
| 90/10 W2 (kons, Stress-Kosten) | +8,7 % | −39 % | 172.288 € |
| 90/10 A5 (Basis-Kosten) | +11,2 % | −39 % | 241.150 € |
| 90/10 B60 (5 × 1 %, Forschungskosten) | +10,2 % | −39 % | 203.944 € |
| **90/10 Dual Momentum** (S16-B-Näherung) | +10,7 % | **−32 %** | 225.977 € |

Mit realistischer Ausführung **senkt** die W2-Beimischung die Rendite leicht; Dual Momentum senkt den größten Rückgang am
deutlichsten. Unterschiede von < 1 Punkt liegen innerhalb der Modellunsicherheit.

## 6. Steuern (Szenario, nicht gerechnet)

Abgeltungsteuer + Soli (26,375 %) auf realisierte Gewinne nach Sparerpauschbetrag (1.000 €). Kurzfristiges Trading
realisiert jeden Gewinn sofort; der ETF schiebt die Steuer bis zum Verkauf (Stundungseffekt). Das verschiebt den
Vergleich zusätzlich **zugunsten des ETF** (bei 5 % Ertrag p. a. grob 0,5–1 Punkt p. a. – Größenordnung, nicht
simuliert).
