# KAIRO – Markenidentität, Slogan und Intro

> **Update 11.11.2026 – Hauptslogan: „The moment has a method.“** (Entscheidung mit Jonny). Er verbindet den Namen
> (Kairos = der richtige Moment) mit der Methode (getestete Regel) und erzählt genau das Intro: Ein Fadenkreuz findet den Moment,
> daraus entsteht die Kerze des Zeichens. Websuche (11.11.2026): kein prominenter Gebrauch gefunden – keine Markenrechtsprüfung.
> Alternative: „Precision over prediction.“ Der frühere Claim „Patience, then precision.“ bleibt als Beschreibung der Regel nutzbar.

Stand: 12.11.2026. Grundlage ist die geprüfte App (`site/index.html`, `backend/`, `research/`), nicht Wunschfunktionen.

## 1. Was Kairo wirklich ist (aus dem Code geprüft)

| Bereich | Vorhanden | Belegt durch |
|---|---|---|
| Reversal-Scanner mit fester Regel (11 Kriterien, Seitwärtsphase, Stop) | ja | `backend/`, Scanner-Reiter, `kSt`, `kmFit` |
| Backtests / Forschung mit Prüfjahren | ja | `research/`, `backend/*study*.py`, Wahrheits-Test im Trade-Plan |
| Trade-Plan mit Risiko-basierter Größe, Stop, Hebel, Kosten | ja | `tp2Calc`, Einstieg-Reiter |
| Papier-Test (Vorwärtstest, virtuelle Depots) und Übung | ja | `paper/`, Reiter Papier und Übung |
| Ehrliche Bilanz (alle Signale, auch Verluste) | ja | Reiter Bilanz, `bilanz.json` |
| Depot, Journal, Stop-Überwachung, Mitteilungen | ja | Depot-Reiter, `kairo-alerts` |
| Markt: Lage, Breite, Heatmap, Insider, Kalender, Briefing | ja | Markt-Reiter |
| ETF-Sparplan mit Einstiegs-Ampel | ja | ETF-Reiter, `etfTiming` |
| KI-Vorhersagen, automatische Orders, Renditeversprechen | **nein** | bewusst nicht vorhanden |

**Alleinstellung:** Kairo handelt nicht viel, sondern selten und nach einer getesteten Regel – und zeigt dabei ehrlich, was die Regel bringt und was nicht. Wartezeit (die Seitwärtsphase) ist Teil der Methode. Das Risiko wird vor dem Kauf festgelegt.

**Zielgruppe:** Privatanleger mit Welt-ETF als Fundament, die einen kleinen Teil systematisch traden wollen und Impulskäufe vermeiden möchten. Sie wollen Klarheit, keine Signal-Flut.

**Positionierung:** *Die ruhige, disziplinierte Alternative zu hektischen Trading-Apps – Timing nach Regeln, mit Beweis und festem Risiko.*

Markenpersönlichkeit: ruhig · präzise · ehrlich · souverän. Nicht laut, nicht verspielt, keine Versprechen.

Sprachstil: kurze Sätze, konkrete Zahlen, kein Hype. „Kairo meldet sich“ statt „Verpasse nichts!“. Unsicherheit wird offen benannt.

## 2. Slogan

### 30 Kandidaten in sechs Richtungen

| Richtung | Kandidaten |
|---|---|
| Präzision & Intelligenz | Patience, then precision. · Precision over impulse. · Timing, tested. · The right moment, by design. · Aim before you act. |
| Daten & Evidenz | Evidence before action. · Tested, not guessed. · Signal over noise. · Proof, then position. · Der Moment ist kein Zufall. |
| Strategie & Disziplin | Trade the rule, not the mood. · Discipline, quantified. · Patience, engineered. · Geduld mit System. · Erst warten. Dann handeln. |
| Kontrolle & Risiko | Risk first. Then return. · Know your stop. · Calm is an edge. · Control the downside. · Sicher planen, ruhig handeln. |
| Professionelles Trading | Systematic by design. · Rules, then results. · Trade like a system. · Wait for the setup. · Strategie statt Bauchgefühl. |
| Minimal-Premium | The right moment. · Wait. Then act. · Less noise. Better timing. · Quiet precision. · Der richtige Moment. |

### Die zehn stärksten – Bewertung (1–5)

| Slogan | Einprägsam | Eigenständig | Emotional | Glaubwürdig | International | Premium | Passung | Σ |
|---|---|---|---|---|---|---|---|---|
| **Patience, then precision.** | 5 | 5 | 4 | 5 | 5 | 5 | 5 | **34** |
| Trade the rule, not the mood. | 5 | 4 | 4 | 5 | 5 | 3 | 5 | 31 |
| Precision over impulse. | 4 | 4 | 3 | 5 | 5 | 5 | 5 | 31 |
| Patience, engineered. | 4 | 4 | 3 | 4 | 5 | 5 | 4 | 29 |
| Timing, tested. | 4 | 4 | 2 | 5 | 5 | 4 | 5 | 29 |
| Calm is an edge. | 4 | 4 | 4 | 4 | 5 | 4 | 4 | 29 |
| Geduld mit System. | 4 | 4 | 3 | 5 | 2 | 4 | 5 | 27 |
| Evidence before action. | 3 | 3 | 2 | 5 | 5 | 4 | 5 | 27 |
| Der Moment ist kein Zufall. | 4 | 4 | 3 | 4 | 2 | 4 | 5 | 26 |
| Signal over noise. | 4 | 1 | 3 | 4 | 5 | 4 | 4 | 25 |

### Entscheidung

**Hauptslogan: „Patience, then precision.“**

- Beschreibt exakt die Methode: erst die Seitwärtsphase abwarten (Geduld), dann mit festem Stop und berechneter Größe einsteigen (Präzision). Er ist damit kein Werbeversprechen, sondern eine Arbeitsanweisung.
- Drei Wörter, Rhythmus mit Komma-Pause – gut sprech- und merkbar, auch auf dem Splash und als App-Store-Untertitel.
- International verständlich, wirkt in fünf bis zehn Jahren nicht veraltet (keine Technik- oder KI-Buzzwords).
- Verspricht keine Rendite – rechtlich und inhaltlich sauber.
- Kontinuität: Kairo nutzt den Claim bereits im Intro; er wird jetzt konsequent überall eingesetzt.

**Alternative: „Trade the rule, not the mood.“** – direkter und emotionaler, ideal für Marketing (Anzeigen, Website-Hero), weil er den Gegner benennt: Impuls und Bauchgefühl.

**Deutsche Hero-Headline:** „Regeln statt Bauchgefühl.“ (im Rundgang umgesetzt).

**Prüfung auf Nutzung:** Eine Websuche (12.11.2026) fand weder „Patience, then precision“ noch „Trade the rule, not the mood“ als prominenten Slogan eines Wettbewerbers. Das ist **keine** Markenrechtsprüfung – vor einer Eintragung oder bezahlten Werbung bitte eine Recherche bei DPMA/EUIPO durchführen lassen.

## 3. Intro

### Drei Ebenen – was die PWA braucht

| Ebene | Wann | Umsetzung |
|---|---|---|
| A. Brand Reveal | erstes Öffnen und nach jedem Update (`INTRO_V`) | „Der Moment“, ≈ 1,9 s, antippen überspringt |
| B. App Loading | alle anderen Starts | fertiges Logo, 0,5 s, danach sofort die App; feine Ladelinie nur, wenn die App wirklich noch lädt |
| C. Landing | erster Start | Rundgang (3 Schritte) mit Hero „Regeln statt Bauchgefühl.“ |

Vorher lief bei jedem Start ein 4,1-s-Video. Das wirkt beim zehnten Öffnen wie Wartezeit – deshalb jetzt die Trennung A/B.

### Sechs kreative Richtungen (Bewertung 1–5)

| Richtung | Kurzbeschreibung | Marke | Wiedererk. | Profi | Eigen | Visuell | UX | Technik | Skalierbar | Σ |
|---|---|---|---|---|---|---|---|---|---|---|
| **Der Moment** (Sieger) | Kurslinie fällt und wendet, Fadenkreuz rastet am Tief ein, Punkt wächst zur Kerze = Stamm des K, Logo schließt sich | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | **40** |
| Zeitraffer (bisher) | Ein Jahr Kerzen rauscht vorbei, bremst am Signal | 4 | 4 | 4 | 4 | 4 | 2 | 3 | 3 | 28 |
| Kairos-Uhr | Zifferblatt läuft, ein Strich leuchtet blau | 4 | 3 | 4 | 4 | 4 | 4 | 5 | 3 | 31 |
| Seitwärtsphase | Kerzen fallen, Basis-Box, blaue Ausbruchskerze | 4 | 3 | 4 | 4 | 3 | 4 | 4 | 3 | 29 |
| Datenpunkte → Zeichen | Punktwolke ordnet sich zum K | 3 | 3 | 4 | 2 | 4 | 4 | 4 | 4 | 28 |
| Scan-Strahl „1 von 6.000“ | Strahl über eine Wand aus Mini-Kerzen | 4 | 3 | 3 | 4 | 3 | 4 | 4 | 3 | 28 |

„Der Moment“ verbindet die stärksten Elemente: die Linie (ruhig statt Kerzen-Rauschen), das Fadenkreuz (Präzision) und die Kerze, die zum Logo wird (Wiedererkennung). Jedes Element erklärt einen Teil der Methode.

### Ablauf (sekundengenau)

| Zeit | Ereignis | Bedeutung |
|---|---|---|
| 0,00–0,62 s | Feine Kurslinie zeichnet sich von links, die Szene ist leicht vergrößert | der Markt: fällt und wendet |
| 0,42–0,76 s | Punkt erscheint am Tief, Fadenkreuz rastet von groß auf präzise ein | der richtige Moment wird gefunden |
| 0,62–1,32 s | Zoom ins Zeichen; Linie tritt zurück | Fokus |
| 0,66–1,38 s | Aus dem Punkt wächst der Docht, ab 0,78 s federt der Körper der blauen Kerze auf | aus dem Moment wird die Position |
| 0,94–1,65 s | Die zwei silbernen Klingen gleiten heran, ab 1,00 s die Kachel | das K schließt sich – das Zeichen |
| 1,18–1,88 s | Zeichen rückt nach links, KAIRO erscheint Buchstabe für Buchstabe; das I ist wieder eine blaue Kerze | Wortmarke |
| 1,50–2,30 s | Claim „PATIENCE, THEN PRECISION.“ | Versprechen ohne Renditeversprechen |
| ab 1,9 s | Übergang: Logo zoomt sanft weg, App blendet ein (frühestens, wenn die App bereit ist; spätestens 5 s) | nahtlos in die App |

Technik: nur `transform`/`opacity` (Grafikkarte), SVG und CSS, keine Bibliothek, kein Video (~0 KB Zusatzdaten). `prefers-reduced-motion`: fertiges Logo ohne Animation. Antippen oder Taste überspringt.

## 4. Visuelle Identität

- **Zeichen:** Kachel mit einem K aus einer blauen Kerze (Stamm) und zwei silbernen Klingen. Die Kerze steht für den einen richtigen Moment.
- **Wortmarke:** KAIRO in kräftiger Grotesk, das I ist eine blaue Kerze – Zeichen und Wortmarke erzählen dasselbe.
- **App-Icon:** das Zeichen auf tiefem Schwarz-Verlauf (bestehend, `icon.svg`).
- **Farben:** Kairo-Blau `#0A84FF` (Akzent, nur für Handlung und Signal) · Schwarz `#000` · Flächen `#121212 / #1C1C1E` · Silber `#E3E6EB → #B4BAC3` (Klingen) · Text `#F4F6FA` · Nebel `#8A93A3`. Semantik: Grün `#30D158` steigend, Rot `#FF453A` Verlust/Stop, Gold `#F4B740` Hinweis. Weitere Farbwelten (Mitternacht, Graphit, Wald, Sand) tauschen nur Flächen und Akzent.
- **Typografie:** Systemschrift (SF Pro / Segoe / Roboto), Zahlen tabellarisch; Überschriften 700–750 mit −0,02 em Laufweite; Kicker in Versalien mit +0,06 em.
- **Bewegung:** eine Auslaufkurve für Auftauchendes (`cubic-bezier(.16,1,.3,1)`), eine für Ortswechsel (`.65,0,.35,1`), eine Feder nur für die Kerze. Nichts blinkt, kein Neon, kein Glanz. Wechsel 0,3–0,4 s.
- **UI-Prinzipien:** eine Hauptaussage pro Karte · Zahlen vor Text · Blau nur für Handlung · Risiko immer sichtbar · ehrliche Unsicherheit statt Versprechen.

## 5. Kritische Selbstbewertung

Stark: Das Intro erklärt die Methode in unter zwei Sekunden, ohne Text; Zeichen, Wortmarke und Claim greifen ineinander; der Start ist für Wiederkehrer schneller als vorher.

Noch offen:
- Die Wortmarke nutzt die vorhandenen Buchstaben-Pfade; eine eigens gezeichnete Schrift (Custom Wordmark) würde die Eigenständigkeit weiter erhöhen.
- Kein Ton/Haptik – auf iOS-PWAs nicht verlässlich möglich.
- Markenrechtliche Prüfung von Name und Claim steht aus.
- Eine öffentliche Landing-Page (vor dem Login-Code) gibt es noch nicht; der Rundgang übernimmt das innerhalb der App.
