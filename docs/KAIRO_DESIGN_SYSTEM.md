# KAIRO Design System – Premium Workspace (V4)

Gilt für die optionalen Designs `premium` (dunkel) und `premium-hell`. Quelle: `<style id="ds-premium">` und
`<style id="ds-premium-hell">` in `site/index.html`. Klassisch und die übrigen Designs bleiben unverändert.

## Aktivierung und Trennung von Thema / Layout

- Einstellungen → Design → **Premium Workspace · Dunkel (neu)** oder **· Hell (neu)**; gespeichert in `state.design`
  (localStorage `reversal-finder-v1`). Zurück jederzeit über „Dunkel (Standard)“.
- `ds-premium` enthält **Layout + dunkle Tokens** und ist bei beiden Varianten aktiv; `ds-premium-hell` überschreibt **nur
  Farb-Tokens**. Thema (hell/dunkel) ist damit vom Layout getrennt. Dichte und Navigation folgen der Bildschirmbreite
  (siehe Raster) – eine eigene Dichte-Einstellung gibt es noch nicht (Offene Punkte).

## Farben

| Token | Dunkel | Hell | Verwendung |
|---|---|---|---|
| `--bg` | #0b0c0f | #f4f5f7 | Seitenhintergrund (Onyx / Papier) |
| `--surface` | #14161a | #ffffff | Karten, Leisten |
| `--surface-2` | #1b1e24 | #f0f1f4 | Zellen in Karten, Chart-Grund |
| `--surface-3` / `--line` | #262a31 | #e4e6ea / #e1e3e8 | Linien, Trenner |
| `--text` | #f2f4f7 | #111317 | Text |
| `--muted` | #a3a9b4 | #555b66 | Nebentext (≥ 4,5 : 1 auf surface) |
| `--accent` | **#0a84ff** (Kairo-Blau) | #005fc4 | Links, Linien, Logo, Akzente |
| `--accent-fill` | #0066cc | #0066cc | **Flächen mit weißer Schrift** (5,6 : 1) |
| `--up` / `--red` / `--gold` | #32d74b / #ff5a50 / #ffd60a | #16722d / #c10012 / #7a5000 | Gewinn / Verlust·Stop / Hinweis |

Regel: Weißer Text nie auf `#0A84FF` (3,65 : 1), sondern auf `--accent-fill`. Grün/Rot nie als einziges Signal – immer mit
✓/✗, Vorzeichen oder Text.

## Typografie

Systemschrift (SF Pro auf Apple). Größen: `--t-xs` 12 · `--t-sm` 13 · `--t-md` 15 · `--t-lg` 17 · `--t-xl` 22 · `--t-xxl` 28 px.
Kein Text unter 11 px (Messung `small_txt` = 0 in allen 105 Kern-Kombinationen). Zahlen in Plan-Zellen 14 px fett,
einzeilig mit Auslassung; Erklärtexte 12 px, höchstens zwei Zeilen (iPad/Desktop).

## Abstände, Radien, Flächen

4-px-Raster `--s1`…`--s8` (4–32 px). Radien `--radius` 14 · `--r-sm` 10 · `--r-xs` 8 px. **Eine** Kartenart: `surface` +
1 px `line`, kein Schatten, **kein Blur** (Leistung, ruhiger Eindruck). Fokus: sichtbarer 2-px-Rahmen (`:focus-visible`).
`prefers-reduced-motion` schaltet Animationen ab.

## Raster / Breakpoints

| Breite | Navigation | Inhalt |
|---|---|---|
| < 641 px (Telefon) | untere Tab-Leiste, deckend | eine Spalte, Segmente 44 px hoch, kompakte Scanner-Zellen |
| 641–1023 px (iPad hochkant, Split View) | untere Tab-Leiste | eine Spalte, Detail als Blatt |
| 1024–1279 px (iPad quer) | **Symbolleiste 84 px** (Symbol + Kurzname) | Scanner-Zeile als Raster *Name · 4 Plan-Zellen*, Kriterien darunter; Detail-Blatt `min(820px, 68vw)` |
| ≥ 1280 px | Seitenleiste 224 px mit Text und Zählern | wie oben, max. 1280 px |
| ≥ 1440 px | wie oben | max. 1440 px, Heute 1,2 : 1 |

## Komponenten (Kurzregeln)

- **Kopf**: Begrüßung/Titel links, Thema + Einstellungen rechts; ab 1024 px ohne Wortmarke (Logo steht in der Leiste).
- **Scanner-Zeile**: Rang · Name (ein Wort­umbruch, Auslassung) · Meta zwei Zeilen · Plan-Zellen KAUF/STOP/GRÖSSE/AUSSTIEG ·
  Kriterien-Chips 11,5 px mit ✓/✗.
- **Segmente** (Treffer/Beobachten/Meine): Zähler in derselben Zeile; aktiv = `--accent-fill`.
- **Filter-Knopf**: rechts neben der Beschreibung, nicht in eigener Zeile.
- **Detail**: Kurs + Stand-Angabe („Schlusskurs 28.10.2026 · zum Vortag“) → Chart 300 px (Telefon 220 px) → Plan-Karte.
- **Depot-Aktionen**: Hauptaktion gefüllt, Nebenaktionen als zurückhaltende Knöpfe.

## Präzisions-Kennzeichnung (Finanzdaten)

Bestehende Kennzeichnungen bleiben sichtbar und werden nicht weggestaltet: Kursstand mit Datum („Schlusskurs …“,
„Kurse vom Abendscan“), Währung an jedem Kurs, „(geschätzt)“ beim Depotwert, Hinweis „Kein Anlageberatung“. Neue Daten
wurden nicht erfunden.
