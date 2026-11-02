# W2 – Unabhängiger forensischer Audit (02.11.2026)

Branch `claude/w2-audit` (Basis: `claude/ultimate-research` 92061de + `main` 2469ae1). Ergebnisläufe auf
`claude/reversal-out`, Ordner `w2a-41415380358`. Keine Handelsregel wurde verändert (W2, A5, B60, E2 eingefroren).

## 1. Ist die W2-Definition im Code die beschriebene?

| Element | Beschreibung | mrc.py (Forschung) | mrconfirm.py (Bestätigung) | mrshadow.py (live, vorher) | mrsim.py (neu, gemeinsam) |
|---|---|---|---|---|---|
| 3 fallende Schlusskurse | ja | ja (bereinigt) | ja | ja | ja |
| über 200-Tage-Linie | ja | ja | ja | ja | ja |
| Kurs ≥ 1, Ø Umsatz ≥ 5 Mio. $ | ja | ja (`s01.eligible`, + ≥ 300 Tage Historie) | ja (feste Wechselkurse) | **Umsatz in Landeswährung** (F6) | ja (in USD) |
| Limit Schluss − 0,5 ATR(14), nur Folgetag | ja | ja (Rohkurs) | ja (bereinigt) | ja | ja |
| Rangfolge niedrigster RSI(2) | ja | ja | ja | ja (nur unter gefüllten, F3) | ja |
| Verkauf Eröffnung nach Schluss > SMA5, spätestens Schluss Tag 10 | ja | ja | ja | ja | ja |
| kein Stop | ja | ja | ja | ja | ja |

Parität nachgewiesen durch `research/strategy_championship/tests/test_w2_parity.py`: Live-Signal (`mrshadow.signal_today`)
= Forschungssignal (`mrsim.indicators`) an 160 Stichtagen; `mrsim.simulate` trifft dieselben Entscheidungen wie
`mrconfirm.portfolio` (gleiche Trades, Endwert < 2 % Abweichung aus Kassenrundung).

## 2. Funde (Problem → Auswirkung → betroffene Ergebnisse → Korrektur → Testnachweis)

| # | Schwere | Problem | Auswirkung | Betroffen | Korrektur | Test |
|---|---|---|---|---|---|---|
| **F1** | **kritisch** | Engine: eine nicht ausgeführte Buy-Limit-Order belegte keinen Platz; ein schlechter gereihtes Signal rückte am selben Tag nach | Vorgriff: man weiß morgens nicht, welches Limit gefüllt wird. Mehr und „ausgewählte“ Trades | Welle 3 W1/W2 Depotwerte, 90/10-Mischungen in KAIRO_MR_MEISTERSCHAFT §4 | `engine.run(reserve_limits=True)` (Standard): ungefüllte Limits belegen Platz + Kapital des Tages | `test_engine.py::test_unfilled_buy_limit_reserves_slot_no_backfill` |
| **F2** | hoch | `mrc.top_per_day(…, 4·Plätze)`: bis 20 Limit-Orders je Tag für 5 Plätze | verstärkt F1 (≈ 2,5× so viele Kaufgelegenheiten) | wie F1 | durch F1-Korrektur unschädlich | wie F1 |
| **F3** | **kritisch** | Live-Schattentest `mrshadow.depot()` wählte die 5 Plätze nur unter bereits gefüllten Signalen | Vorgriff im Schattentest – Live-Ergebnis wäre zu gut gewesen | Bilanz-Anzeige W2/A5 (noch keine Daten, Start 02.11.) | Depot über `backend/mrsim.simulate` (Reservierung, kein Nachrücken) | `test_mrshadow.py::test_event_depot_no_backfill_…`, `test_mrsim.py::test_unfilled_limit_keeps_slot_no_backfill` |
| **F4** | hoch | Überall „Tagestief berührt Limit = ausgeführt, zum Limit“ | optimistisch: Warteschlange, Briefkurs, Docht | alle W2-Ergebnisse | drei Ausführungsmodelle opt/kons/streng + Stundenkerzen-Prüfung | `test_mrsim.py::test_fill_models` (8 Fälle) |
| F5 | mittel | `mrconfirm.portfolio` gibt den Platz nach Zeitausstieg (Schluss Tag 10) schon zur Eröffnung desselben Tages frei | leichter Vorgriff in den Bestätigungs-Depots (nicht in den Je-Trade-Vergleichen) | KAIRO_MR_MEISTERSCHAFT §5 Depotspalten | in mrsim korrekt; mrconfirm bleibt als eingefrorene Forschung, Fund dokumentiert | Parität nur auf Trades ohne Zeitausstieg exakt (`test_w2_parity.py`) |
| **F6** | mittel | Live-Liquiditätsfilter in Landeswährung (GBp in Pence, SEK, NOK …) | zu großzügig für Nicht-USD-Titel; Live ≠ Forschung | Schattentest | Umrechnung in USD (`mrsim.FX_USD`) | `test_mrsim.py::test_signal_…_and_fx` |
| F7 | mittel | Kosten uneinheitlich: Engine schlägt auf Limit-Käufe den halben Spread auf, mrconfirm rechnet pauschal, mrshadow 0,05 %/0,25 % | Ergebnisse nicht vergleichbar | alle | mrsim: Limit-Kauf zahlt genau seinen Preis, aber „kons“ verlangt, dass der Briefkurs das Limit erreicht; Marktorders/Verkäufe zahlen halben Spread | `test_mrsim.py::test_costs_reduce_return…` |
| F8 | gering | Spread-Klasse aus dem Median-Umsatz über die **ganze** Historie (`wave1.spreads`) | kleiner Vorgriff bei der Kostenklasse | Engine-Läufe | mrsim: Umsatz am Signaltag | – |
| **F9** | hoch | Gebührenannahme 0,99 € unter 250 €, sonst 0 € (PRIME+) – laut mehreren Quellen gilt auf gettex seit 01.09.2026 bis 1,99 € je Order auch für PRIME+ (offizielle Preisliste nicht geprüft) | trifft eine Strategie mit ~190 Orders/Jahr hart | alle Depot-Ergebnisse | Szenario `g199` ergänzt; Bestätigung durch Jonny nötig | Kapitalszenarien im Kostenbericht |
| F10 | mittel | Vorzeit/Asien in Landeswährung, ohne Wechselkurse | absolute Renditen dort nicht in EUR | §5 Bestätigung | gekennzeichnet; nur Relativvergleiche gewertet | – |
| F11 | mittel | Kursdatenfehler (z. B. +857.291 % in 20 Tagen durch falsche Split-Bereinigung) | einzelne Ausreißer können Mittelwerte verzerren | mrc/mrconfirm-Je-Trade-Mittel | w2audit begrenzt Je-Trade-Renditen auf −90 … +300 % | – |
| **F12** | **hoch, nicht behebbar** | Überlebens-Verzerrung: alle Universen = heute noch gelistete Aktien | absolute Renditen zu hoch; Wechselwirkung mit Mean Reversion (Rücksetzer von Überlebenden erholen sich „per Definition“) | alle | Kontrollen mit gleicher Verzerrung, Zeitverlauf des Vorsprungs (§4), Kennzeichnung | – |
| **F13** | hoch | Datenschnüffelei: W2 wurde nach Welle 1 und 2 auf denselben Daten aus 4 Varianten gewählt; der Holdout 2022–26 ist seit 19.10.2026 entsiegelt und mehrfach benutzt | Hauptdaten sind kein frischer Beweis | Welle 3 | nur Vorzeit/Asien gelten als unabhängig für W2 | §3 |
| F14 | gering | Handel auf dividendenbereinigten Kursen | Limit-/Kursniveaus historisch leicht verschoben, Renditen korrekt | alle | dokumentiert | – |
| F15 | mittel, nicht prüfbar | Ausführung in Deutschland (gettex/LS, EUR) statt Heimatbörse; Tageshoch/-tief der Heimatbörse ≠ deutscher Handelsplatz; „Eröffnung“ für US-Aktien = 15:30 Uhr | Füllungen und Ausstiegskurse können abweichen | alle | nur prospektiv messbar (eigene Orders) | – |
| F16 | Hinweis | Engine-Buy-Stop (E2) hat dieselbe Nachrück-Logik wie F1 | E2-Depotwerte evtl. leicht optimistisch | E2-Forschung | **nicht geändert** (E2 eingefroren), nur dokumentiert | – |
| F17 | behoben | RSI-/Kerzen-Test vom 02.11.: Grundfilter enthielt Aufwärtstrend | erster Lauf ungültig | rsis-41410055775 | bereits korrigiert und wiederholt | – |

## 3. Statistik und Unabhängigkeit

| Schritt | vorab festgelegt? | Daten | unabhängig für W2? |
|---|---|---|---|
| Welle 1 (22 Varianten, A5 darunter) | ja | USA/Europa 2008–26 | – (Entdeckung) |
| Welle 2 (Kostenraster, liquide Varianten) | ja, nach Welle 1 | dieselben | nein |
| Welle 3 (W1–W4, W2 = beste von 4) | ja, nach Welle 2 | dieselben (3. Nutzung) | **nein – Auswahlverzerrung** |
| Bestätigung Vorzeit 1999–2007, Asien 2008–26 | ja, vor dem Lauf | neue Daten | **ja** (für die W2-Parameter); Überlebens-Verzerrung bleibt |
| Dieser Audit (w2audit) | ja, Kriterien K1–K5 vor dem Lauf | alle drei | Hauptdaten: nein · Vorzeit/Asien: ja |

- **Bootstrap:** Monatsblöcke, beide Gruppen gemeinsam gezogen → berücksichtigt, dass viele Signale am selben Markttag
  entstehen (Marktereignisse). Abhängigkeit innerhalb derselben Aktie über Monate hinweg ist nicht modelliert; bei
  > 2.800 Aktien je Datensatz gering.
- **Mehrfachtests:** W2 ist der Sieger von ~30 Varianten. Für die Hauptdaten bräuchte es eine Korrektur, die der Auswahl
  Rechnung trägt; für Vorzeit/Asien ist es **eine** vorab festgelegte Hypothese je Datensatz → keine Korrektur nötig.
- **Ergebnis K1 (Signal gegen Zufallskauf mit gleichem Limit, vorsichtige Ausführung, netto):** USA/Europa +0,26 Pkt.
  (95 %: +0,10 … +0,41, p 0,0005), Vorzeit +0,53 (p 0,0005), Asien +0,50 (p 0,0005). In der Validierung 2017–21 allein
  nicht signifikant (+0,17, p 0,18). Der **Signal-Effekt ist robust**; das ist die stärkste Evidenz im ganzen Projekt.

## 4. Überlebens-Verzerrung – was sich prüfen lässt

- Nicht verfügbar (kostenlos): delistete Aktien, historische Indexzugehörigkeit, historische Listings. Eine vollständige
  Korrektur ist **nicht möglich**.
- Vorsprung W2 − Kontrolle je Kalenderjahr (USA/Europa, kons): 2008–2016 Ø ≈ +0,38, 2017–2021 ≈ +0,13, 2022–2026 ≈ +0,20 Pkt.;
  Vorzeit (am weitesten vom Einfrierdatum) +0,53. Der Vorsprung ist **in den ältesten Daten am größten** – vereinbar mit
  Überlebens-Verzerrung (oder mit nachlassender Anomalie). Im jüngsten, am wenigsten verzerrten Abschnitt bleibt er
  positiv (+0,23, p 0,02).
- Absolute Renditen: Schon „kaufen und halten“ des Universums liefert in diesen Daten +17–22 % p. a. → **alle absoluten
  Depotrenditen dieses Berichts sind Obergrenzen**, keine Zukunftserwartung.
- Datenqualität (Bewertung): Signal-Vorteil gegen Kontrolle **mittel–gut belastbar** · absolute Depotrenditen **schwach**
  · Ausführung **schwach (Modell)** · Kosten **schwach (Annahmen, Gebühr unbestätigt)**.

## 5. Technische Korrekturen (Branch `claude/w2-audit`)

- `backend/mrsim.py` – gemeinsame Ereignis-Simulation (Signal → Order geplant → Kapital reserviert → ausgeführt /
  nicht ausgeführt / zu klein / abgelaufen → Position → geschlossen), 3 Ausführungsmodelle, 5 Kostenszenarien, ganze Stücke,
  Mindestorder, EUR-Bewertung.
- `research/strategy_championship/engine.py` – `reserve_limits` (F1).
- `backend/mrshadow.py` – Depot über mrsim (F3), USD-Liquidität (F6), Ereignis-Log nur anhängend, eingefrorene
  Abschlüsse, Live-Kontrollgruppe CTRL-L (10 zufällige Aufwärtstrend-Aktien je Abend, gleiches Limit), zusätzliche Felder
  je Signal (ATR, 200-Tage-Linie, Umsatz, Währung, Regelversion, Erkennungstag).
- Tests: 17 neue (mrsim 14, Parität 3) + Engine + Schattentest; gesamt 275 bestanden.
