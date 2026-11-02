# KAIRO Design V4 – Ergebnisse (02.11.2026)

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
