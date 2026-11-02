# KAIRO Design – Ergebnisse (V4 02.11.2026, V5 03.11.2026)

V5-Ergebnisse stehen in Abschnitt 7 ff.; Abschnitte 1–6 sind der V4-Stand (damals mit echten Scan-Daten vom 29.10.).

Vergleich **Klassisch** (Standard, unverändert) gegen **Premium Workspace** (optional), gleiche Daten, gleiche Uhrzeit,
Chromium. Nachmessen:

    python tools/design_shots.py --out OUT --designs classic,premium,premium-hell \
        --vps iphone,iphone-max,ipad-p,ipad-l,ipad-split,desk,desk-xl --views today,scanner,detail,entry,depot

## 1. Kernwege – gemessene Positionen

| Messung | Gerät | Klassisch | Premium | Wirkung |
|---|---|---|---|---|
| Erste Aktie im Scanner (px von oben) | iPad quer | 527 | **330** | −37 % |
| Höhe einer Kaufbereit-Zeile | iPad quer | 179 | **126** | −30 % |
| Kaufbereit-Zeilen ganz sichtbar | iPad quer | 1 | **3** | ×3 |
| Kaufbereit-Zeilen ganz sichtbar | Desktop 1440 | 2 | **4** | ×2 |
| Chart im Detail – Oberkante | iPad quer | 757 (unter dem sichtbaren Bereich) | **252** | sofort sichtbar |
| Chart im Detail – Fläche B × H | iPad quer | 481 × 150 | **733 × 300** | ×3,0 |
| Chart im Detail – Oberkante | Telefon | 821 (unter dem sichtbaren Bereich) | **305** | sofort sichtbar |
| Chart – Höhe | Telefon | 150 | **220** | +47 % |
| Erste Aktie im Scanner | Telefon | 644 | 592 | −8 % |
| Höhe einer Kaufbereit-Zeile | Telefon | 363 | 366 | gleich (nach Runde 3; Runde 2 war 407) |
| Scrollhöhe Scanner (Bildschirme) | iPad quer | 4,42 | **3,57** | −19 % |
| Scrollhöhe Scanner | Desktop XL | 3,41 | **2,76** | −19 % |

## 2. Qualitätsmessungen (Summe über 7 Größen × 5 Kernansichten = 35 Kombinationen je Design)

| Messung | Klassisch | Premium dunkel | Premium hell |
|---|---|---|---|
| Horizontale Überbreite (px) | **10** (Telefon-Scanner/Detail je 5) | **0** | **0** |
| Text < 11 px | 0 | 0 | 0 |
| Trefferflächen < 32 px | 228 | **206** | **206** |
| Kontrast unter WCAG AA | 63 | **0** | 21 ¹ |
| JavaScript-Fehler | 0 | 0 | 0 |
| Renderzeit je Ansicht | ~1,9 s | ~1,9 s | ~1,9 s (Wartezeit des Prüfstands, kein Unterschied) |

¹ Alle 21 sind derselbe **Messfehler**: der aktive Reiter in der Tab-Leiste hat weißen Text auf einem *Geschwister*-Element
(`.tab-ind`), das die Messung nicht als Hintergrund erkennt (gemessen 1,00 : 1, tatsächlich 5,6 : 1 – siehe Screenshot).
Dieselbe Ursache steckt in einem Teil der klassischen Befunde. Echte Befunde im hellen Design (Grün/Blau/Orange auf
getöntem Grund 3,9–4,5 : 1, Orange 1,8 : 1) wurden in Runde 2 behoben.

## 3. Iterationen je Kernansicht

| Ansicht | Runde 1 | Runde 2 | Runde 3 |
|---|---|---|---|
| Scanner | Seitenleiste, kompakter Kopf → 1. Aktie 540 → 400 px | Aktualisieren-Knöpfe einzeilig, Zähler in Segmenten, Zeile als Raster | Symbolleiste 84 px auf iPad quer (Name nicht mehr vierzeilig), Filter neben Beschreibung; Telefon: Überbreite 5 → 0 px, Zeilenhöhe 407 → 366 px |
| Detail | Chart vor Plan, Blatt 820 px | Chart-SVG selbst 300 px hoch (vorher nur Container → leere Fläche) | – |
| Heute | Raster 1,2 : 1 ab 1440 px | „Erste Schritte“ nach unten, Abstand zum Kopf | – |
| Depot | – | Positionen vor Analyse, Aktionen kompakt | – |
| Einstieg | Seitenleiste/Kopf | keine weitere Änderung nötig (bereits kurz) | – |
| Hell | Tokens | Kontrast: Akzent/Grün/Rot/Gold dunkler, Orange-Hinweis #a34700, Füllflächen #0066cc, Tab-Leiste deckend | – |

Alle übrigen Ansichten (ETF, Bilanz, Journal, Kalender, News, Übung, Papier, Einstellungen) wurden im Premium-Design
auf iPad quer gesichtet: keine Überlappung, keine Überbreite, keine leeren Bereiche (ETF-Live-Chart von TradingView ist
im Prüfstand absichtlich blockiert).

## 4. Vorher / Nachher

| | |
|---|---|
| iPad quer – Scanner | `docs/design/ipad-quer_scanner.jpg` |
| iPad quer – Detail | `docs/design/ipad-quer_detail.jpg` |
| iPad quer – Heute / Depot / Einstieg | `docs/design/ipad-quer_today.jpg`, `…_depot.jpg`, `…_entry.jpg` |
| Telefon – Scanner / Detail | `docs/design/iphone_scanner.jpg`, `docs/design/iphone_detail.jpg` |
| Desktop 1440 – Hell | `docs/design/desktop-hell_scanner.jpg`, `docs/design/desktop-hell_detail.jpg` |

## 5. Tests

| Test | Ergebnis |
|---|---|
| `tools/app_smoke.py` (alle Reiter iPad + Telefon, Spiel-Kauf, Postfach-Designs) **+ neu: Premium dunkel/hell auf 1194×834, 834×1194, 390×844, alle 12 Reiter, JS-Fehler, leer, Überbreite** | **bestanden** |
| `pytest backend/tests` | **199 bestanden** |
| Tradinglogik / Kriterien / Strategieparameter | unverändert (kein Diff außerhalb CSS + Designliste) |

## 6. Zusammenfassung nach Kategorien

- **Implementiert:** optionales Premium-Design dunkel/hell, Designsystem-Tokens, responsive Navigation (Leiste 224/84 px,
  Tab-Leiste), Scanner-Raster, Chart-zuerst-Detail, Heute-/Depot-Reihenfolge, Kontrast-Füllfarbe, Prüfstand, App-Test.
- **Getestet:** 3 Designs × 7 Größen × 5 Kernansichten (+ 8 weitere Ansichten auf iPad quer), App-Test, pytest.
- **Nachweisbar verbessert:** Scanner iPad quer (1. Aktie −37 %, 3× so viele Zeilen sichtbar), Chart im Detail auf allen
  Größen sofort sichtbar und 2–3× größer, Überbreite 10 → 0 px, Kontrast 63 → 0 (dunkel), Trefferflächen −10 %.
- **Noch offen / Nicht möglich:** siehe `docs/KAIRO_DESIGN_OPEN_ITEMS.md`.


---

## 7. V5 „Mission 9+/10“ – Ausgangslage und Messgrundlage

- Branch `claude/design-v5` (Basis `claude/design-v4` adf280a). Kein PR, kein Merge.
- **Neue Messgrundlage:** Die Umgebung erreicht github.io und GitHub-Artefakte nicht mehr. Deshalb erzeugt
  `tools/design_fixtures/make_site_data.py` feste App-Daten mit dem **echten Scan-Code** (`run_scan.main`, `h4_block`) aus
  erfundenen, festen Kursverläufen: 16 Treffer, davon 6 kaufbereit, 7 wartend, 4 verfallen; Depot mit 4 Positionen und 0 € freiem
  Trading-Kapital (Grenzfall). **Keine echten Kurse.** Uhr fest auf Fr 30.10.2026 22:30.
- Vorher = V4-Code auf diesen Daten, Nachher = V5-Code auf denselben Daten. Die V4-Zahlen in Abschnitt 1 (alte Daten) sind
  damit nicht direkt vergleichbar; maßgeblich ist Abschnitt 8.

## 8. Zielmetriken V4 → V5 (Premium, Scanner, feste Daten)

| Kennzahl | Ziel | iPad quer V4 | **iPad quer V5** | erfüllt |
|---|---|---|---|---|
| Oberkante erste Aktie | ≤ 300 px | 328 | **290** | ja |
| Zeilenhöhe | ≤ 90 px | 126 | **85** | ja |
| ganz sichtbare Zeilen | ≥ 5 | 4 | **6** | ja |
| Liste + Detail gleichzeitig | ja | nein (Fenster) | **ja (Master-Detail)** | ja |

| Kennzahl | Ziel | iPhone 390 V4 | **iPhone 390 V5** | erfüllt |
|---|---|---|---|---|
| erste Aktie vollständig ohne Scrollen (über der Tab-Leiste, 771 px) | ja | nein (544–935) | **ja (483–607)** | ja |
| Zeilenhöhe | ≤ 140 px | 391 | **112** | ja |
| Scrollhöhe Scanner (Bildschirme) | – | 5,85 | **2,77** | −53 % |

Weitere Größen (V4 → V5): iPhone Max erste Aktie 544 → 448 px, Zeile 331 → 99 px; iPad hochkant 512 → 416 px, Zeile
216 → 85 px, 2 → 6 Zeilen sichtbar; Split View 694 px 512 → 435 px, Zeile 283 → 85 px; Desktop XL 328 → 271 px, 5 → 8 Zeilen.
Master-Detail greift auf iPad quer, Desktop und Desktop XL (≥ 1024 px), sonst bewusst das Fenster.

## 9. Qualität über 7 Größen × 5 Kernansichten (35 je Design)

| Messung | Klassisch (unverändert) | Premium dunkel V4 → **V5** | Premium hell V4 → **V5** |
|---|---|---|---|
| Horizontale Überbreite (px) | 0 | 0 → **0** | 0 → **0** |
| Text < 11 px | 7 | 7 → **0** | 7 → **0** |
| Trefferflächen < 32 px | 220 | 198 → **198** (keine neuen) | 198 → **198** |
| Kontrast unter WCAG AA | 56 ¹ | 0 ² → **0** | 56 ¹ → **0** |
| JavaScript-Fehler | 0 | 0 → **0** | 0 → **0** |
| Scrollhöhe Detail iPhone / iPad quer (Bildschirme) | – | 5,85 / 2,68 → **2,77 / 2,21** | gleich |
| Scrollhöhe Heute iPad quer | – | 2,55 → 2,69 (+ Kennzahlenreihe) | gleich |

¹ V4-Messung: zum großen Teil Messfehler (Reiter-Indikator, `color(srgb …)`-Hintergründe aus `color-mix`). Der Prüfstand
erkennt beides seit V5 korrekt.
² Mit der korrigierten Messung kam in V4 ein **echter** Fehler zum Vorschein, den die alte Messung verdeckt hatte: Im dunklen
Premium-Design war der aktive Reiter unter 1024 px Blau auf Blau (1,5 : 1). In V5 behoben (Weiß, 5,6 : 1). Außerdem behoben:
Zonen-Kennzeichnung im Detail in Hell (1,5 → 6,6 : 1) und die Tage des Nachbarmonats im Kalender (3,2 → ≥ 4,5 : 1).

## 10. Iterationen V5 (je Kernbereich mindestens zwei Runden)

| Bereich | Runde 1 | Runde 2 | Runde 3 |
|---|---|---|---|
| Master-Detail | Liste links / Detail rechts, Leerzustand; Kopf zu hoch (1. Aktie 550 px), ✕ über Score-Ring | Kopf verdichtet: Titel nur für Screenreader, Suche 44 px, „Stand“ nur bei Doppelung ausgeblendet → 456 px | ⓘ · Aktualisieren · Filter in einer Zeile, Liste flach → **290 px**; ✕ frei |
| Scanner-Zeile | Kauf/Stop + Segmentbalken → 108 px, Kauf/Stop untereinander | Balken oben rechts, Kauf/Stop in einer Zeile → 86 px; Vormomentum wurde abgeschnitten | Meta volle Breite, Namenskürzung neben dem Balken → **85 px**, nichts abgeschnitten |
| iPhone | Karte 108 px, Kopf zu hoch (erste Aktie 692 px) | Erklärung als ⓘ, Werkzeugzeile → 568 px; Stop/Vormomentum rechts abgeschnitten | Kauf/Stop umbrechend, Meta zweizeilig → **483–607 px, 112 px**, nichts abgeschnitten |
| Heute-Cockpit | Kennzahlenreihe; „Kaufbereit 6“ widersprach scheinbar „Heute zu tun · 5“ | Kachel erklärt „nur 5 Plätze frei“, Regel einmal oben, Zeilen 105 → 86 px (iPhone), Erste Schritte vor dem Fußbereich | – |
| Detail-Chart | Raster, Kursmarke, Datum (Format abgeschnitten); Stop-Marke widersprach dem Plan („Stop –“) | Datum TT.MM., Marken überlappungsfrei, Stop/Ziel nur wenn der Plan sie nennt, Datumsachse unter dem Chart | mit freiem Kapital: Stückzahl brach die Zeile um (107 px) → rechts in Zeile 2, wieder 85 px |
| Premium Hell | gleiche Struktur geprüft | Zonen-Kennzeichnung 1,5 → 6,6 : 1, Kalender-Nachbartage ≥ 4,5 : 1, Mindestschrift 11 px | aktiver Reiter (dunkel, < 1024 px) Blau auf Blau 1,5 : 1 → Weiß 5,6 : 1 (Fehler bestand schon in V4) |

## 11. Funktionssicherheit V5

| Prüfung | Ergebnis |
|---|---|
| Master-Detail-Verhaltenstest (15 Schritte: Leerzustand, Auswahl, Wechsel mit Chart-Neuzeichnung, Listen-Scroll bleibt, Segmentwechsel, Escape, Tastatur Enter, Bereich verlassen, zurück, Designwechsel bei offenem Detail, 834 px Fenster, Drehen auf quer, Klassisch unverändert) | **15/15 bestanden** |
| `tools/app_smoke.py` (alle Reiter iPad + Telefon, Spiel-Kauf, Postfach, Premium dunkel/hell in 3 Größen) | **bestanden** (auf den festen Daten) |
| `pytest backend/tests` | **199 bestanden** |
| Klassisch unverändert | alle JS-Änderungen mit `isPrem()` abgesichert, alle CSS-Regeln in `ds-premium`; Pixelvergleich V4-Code vs. V5-Code zeigt nur dieselben Abweichungen wie zwei Läufe mit identischem Code (Tab-Animation, Chart-Zeitpunkt) → **keine Änderung** |
| JavaScript-Fehler im Prüfstand | 0 |
| Leistung | Renderzeit je Ansicht im Prüfstand ~2,2 s V4 wie V5 (Wartezeit dominiert); neue CSS ~8 KB, JS ~2 KB, keine Bibliothek, kein Blur |

## 12. Zusammenfassung V5

### A. Vorher vs. Nachher
- **iPad quer:** Aus „Liste, Fenster drüber“ wird ein Arbeitsplatz. Die Liste bleibt links stehen (6 Kaufbereit-Zeilen ganz
  sichtbar statt 4), rechts stehen Chart und Plan. Aktienwechsel ohne Schließen, Scrollposition und Filter bleiben erhalten.
- **iPhone:** Eine Kaufbereit-Zeile ist 112 statt 391 px hoch, die erste Aktie ist ohne Scrollen vollständig sichtbar, und der
  Scanner ist etwa halb so lang (2,77 statt 5,85 Bildschirme).
- **Scanner:** Die 11 Kriterien sind ein ruhiger Segmentbalken mit „11/11“ statt 11 bunter Chips. Gleiche Angaben (Ausstieg,
  Stückzahl 0) stehen einmal oben. Erklärung, Aktualisieren und Filter liegen in einer Zeile.
- **Detail:** Der Chart hat Raster, Kursmarke, Datumsachse sowie Stop und Ziel. Der Stop wird nur gezeigt, wenn der Plan ihn
  auch nennt.
- **Heute:** „Heute zu tun“ ist klar die erste Ebene. Darunter vier Kennzahlen (Kaufbereit, Positionen, nächster Stop,
  ETF-Ampel), ehrlich mit „–“, wenn ein Wert fehlt.
- **Hell:** gleiche Struktur, Kontrast vollständig AA.

### B. Messwerte
Abschnitte 8 und 9: alle verbindlichen Zielwerte erreicht (iPad 290 px / 85 px / 6 Zeilen / Master-Detail; iPhone vollständig
sichtbar / 112 px; 0 Überbreite; 0 Kontrastfehler; 0 Text < 11 px; Trefferflächen 198 < 206, keine neuen; 0 JS-Fehler;
App-Test und Backend-Tests bestanden).

### C. Umgesetzte Änderungen
`site/index.html`:
- CSS ausschließlich in `ds-premium`.
- JS mit `isPrem()`-Schutz: `mdSync()`, `openCard`/`closeCard` (Master-Detail), `boardCard` (Kaufzone kompakt, Stückzahl),
  `boardHtml` (Hinweis über der Liste), `renderMain` (ⓘ-Erklärung), `todoTodayHtml`/`pKpiHtml` (Cockpit), `miniSvg`
  (Chart-Marken), `scanbar` (Klasse `sb-plain`).

Prüfstand:
- `tools/design_shots.py`
- `tools/design_fixtures/make_site_data.py`
- `universe.csv`

Commits auf `claude/design-v5` (P1 Prüfstand, P2/P3 Master-Detail + Zeilen, P5 Cockpit, P6 Kontrast/Schrift, Chart,
Reiter-Kontrast, Trefferflächen).

### D. Funktionssicherheit
Abschnitt 11.

Nicht möglich:
- Safari/WebKit und echtes Gerät (nicht installiert bzw. nicht vorhanden).
- Messung mit echten Scan-Daten (github.io aus der Umgebung gesperrt).

### E. Offene Punkte
`docs/KAIRO_DESIGN_OPEN_ITEMS.md`, Abschnitt V5. Wichtigste:
- Chart ohne Tooltip und Zoom (V1)
- Master-Detail nur im Scanner (V2)
- Warte-Zeilen-Balken (V3)

### F. Qualitätsbewertung (gewichtete Kriterien laut Auftrag)

| Bereich | Gewicht | Punkte | Begründung |
|---|---|---|---|
| iPad-Layout und Flächennutzung | 25 % | 93 | alle Zielwerte, echtes Master-Detail; Leerzustand nimmt bei 0 Auswahl viel Fläche ein |
| Bedienbarkeit und Abläufe | 25 % | 90 | 15/15 Verhaltensprüfungen; Chart ohne Tooltip/Zoom; Master-Detail nur im Scanner |
| Visuelle Qualität und Konsistenz | 20 % | 89 | einheitliche Zeilen, Raster, Hierarchie; Warte-Zeilen noch anders; Tippfehler „Platze“ im gemeinsamen Text |
| iPhone | 15 % | 88 | Ziel erreicht, Scanner halb so lang; Kennzahlen auf „Heute“ erst nach Scrollen |
| Accessibility, Leistung, Technik | 15 % | 89 | 0 Kontrast-/Schriftfehler, keine neuen kleinen Flächen, Tests grün; kein Safari-/Gerätetest, synthetische Daten |
| **Gesamt** | | **90,0 / 100** | |

| Ansicht | Note |
|---|---|
| iPad quer | **9,3** |
| iPad hochkant | 8,8 |
| iPhone | 8,8 |
| Desktop | 9,1 |
| Premium Hell | 9,0 |
| **Premium Workspace gesamt** | **9,0 / 10** – knapp erreicht, kein kritischer Mangel offen |

10/10 ist es nicht: Dafür fehlen ein interaktiver Detail-Chart (Tooltip, Zoom), Master-Detail auch in Einstieg und Depot und
die Prüfung auf dem echten iPad in Safari.

### Status je Punkt
| Punkt | Status |
|---|---|
| Master-Detail iPad | Implementiert · Getestet · Nachweisbar verbessert |
| Scanner-Zeilen ≤ 90 px | Implementiert · Getestet · Nachweisbar verbessert |
| iPhone-Darstellung | Implementiert · Getestet · Nachweisbar verbessert |
| Heute-Cockpit | Implementiert · Getestet |
| Details/Chart | Implementiert · Getestet (Tooltip/Zoom: Noch offen) |
| Premium Hell | Implementiert · Getestet · Nachweisbar verbessert |
| Übrige Ansichten | Getestet (Kalender, Einstellungen, Depot verbessert) |
| Safari/echtes Gerät | Nicht möglich |
