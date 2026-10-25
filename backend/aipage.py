"""KI-Ansicht (site/ai/index.html): die App als reines HTML ohne JavaScript – für ChatGPT, Claude & Co.

Die App selbst baut ihren Inhalt per JavaScript auf; KI-Abrufer sehen davon nur eine leere Hülle. Diese Seite wird bei jedem
Scan neu geschrieben: Aufbau der App, Regeln, heutige Treffer, ETF-Ampel, Live-Bilanz, Papier-Depots, nächste Termine.
Keine Nutzerdaten (Depot, Journal bleiben auf dem Gerät).

    python -m backend.aipage            # aus den Dateien in site/data
"""

from __future__ import annotations

import html
import json
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = "https://dxrtex.github.io/Kairo/"
REPO = "https://github.com/dxrtex/Kairo"
PAPER = "https://raw.githubusercontent.com/dxrtex/Kairo/paper-data/summary.json"
REG = {"us": "USA", "europe": "Europa", "asia": "Asien"}

SECTIONS = [
    ("Heute", "Startseite: „Heute zu tun“ (Kaufkandidaten mit fertiger Seitwärtsphase, Verkaufstage, Stops), Top-Setups, "
              "eigene Aktien, ETF-Ampel, Kairo-Bilanz, Quartalszahlen eigener Aktien."),
    ("ETF", "Kernanlage: Ampel für den SPDR MSCI ACWI IMI (SPYI) – Sparplan läuft immer, die Ampel sagt nur, wann Extra-Geld investiert wird."),
    ("Scanner", "Täglicher Scan von rund 6.000 Aktien (USA, Europa, Asien) nach 11 festen Kriterien; Listen Treffer / Beobachten / Meine; "
                "Tippen öffnet eine Karte mit Kurs, Trade-Plan, Chart und Kennzahlen."),
    ("Einstieg", "Trade-Plan je Aktie: Stop (Basis-Tief − 0,25 ATR), Positionsgröße für 1 % Risiko, Turbo-K.-o. und Hebel, Kosten nach Scalable PRIME+."),
    ("Markt", "Nachrichten (eigene Aktien, Markt, Insider) und Kalender (Quartalszahlen mit Ergebnis, Ausblick und Einschätzung, Dividenden, Zinsen)."),
    ("Depot", "Bestand mit Depot-Check (Klumpen, Branchen, Regionen, Währungen), Journal aus dem Scalable-Export mit Mustererkennung, "
              "Übungsdepot mit Spielgeld, Kairo-Bilanz (Forschung + Live) und Papier-Depots (virtuelle Strategien)."),
    ("Einstellungen", "Name, Design, Live-Kurse (eigener Schlüssel), Mitteilungen, Backup. Alles bleibt auf dem Gerät."),
]


def _load(name: str):
    try:
        return json.loads((ROOT / "site" / "data" / name).read_text(encoding="utf-8"))
    except Exception:
        return None


def _e(x) -> str:
    return html.escape("" if x is None else str(x))


def _n(v, d=2) -> str:
    return "–" if v is None else f"{v:,.{d}f}".replace(",", " ").replace(".", ",")


def _pct(v, d=0) -> str:
    return "–" if v is None else f"{100 * v:+.{d}f} %".replace(".", ",").replace("-", "−")


def _status(r: dict, h4: dict) -> str:
    it = h4.get(r.get("ticker")) or {}
    st = it.get("st")
    if st == "basis":
        return f"wartet auf Seitwärtsphase (Tag {it.get('day', '?')} von 10)"
    if st in ("4h", "go"):
        return "kaufbereit (Seitwärtsphase fertig)"
    if st == "weg":
        return "verfallen"
    if st in ("run", "sell"):
        return "Einstieg vorbei"
    return "wartet auf Seitwärtsphase"


def render(today: str | None = None, paper: list | None = None) -> str:
    res = _load("results.json") or {}
    rows = res.get("results") or []
    h4 = {x.get("t"): x for x in ((_load("h4.json") or {}).get("items") or [])}
    etf = _load("etf.json") or {}
    bil = (_load("bilanz.json") or {}).get("live") or {}
    cal = (_load("calendar.json") or {}).get("events") or []
    gen = res.get("generated", "")
    hits = [r for r in rows if r.get("passed")]
    hits.sort(key=lambda r: (r.get("region") not in ("us", "europe"), "kaufbereit" not in _status(r, h4), (r.get("flags") or {}).get("mom61") or 9))
    out = [f"""<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kairo – KI-Ansicht (Stand {_e(gen[:10])})</title>
<meta name="description" content="Kairo als reines HTML für KI-Assistenten: Aufbau der App, Regeln, heutige Treffer, ETF-Ampel, Live-Bilanz, Papier-Depots.">
<style>body{{font:15px/1.55 system-ui,sans-serif;max-width:980px;margin:0 auto;padding:20px;color:#111}}table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{border-bottom:1px solid #ddd;padding:4px 6px;text-align:left}}h2{{margin-top:28px}}.m{{color:#666}}</style></head><body>
<h1>Kairo – KI-Ansicht</h1>
<p>Diese Seite zeigt die Kairo-App als reinen Text, damit KI-Assistenten sie vollständig lesen und bewerten können (die App selbst
wird per JavaScript aufgebaut). Stand des Scans: <b>{_e(gen)}</b>. Wird bei jedem Scan automatisch neu erzeugt.</p>
<p><b>Was Kairo ist:</b> privater Aktien-Scanner als Web-App (PWA) fürs iPad/iPhone eines Privatanlegers (Broker Scalable Capital, Tarif PRIME+).
Feste, getestete Regeln statt Bauchgefühl; keine Broker-Anbindung, keine Orders, keine Anlageberatung. Kernanlage ist ein Welt-ETF;
Kairo-Trades sind der kleinere, aktive Teil.</p>
<ul><li>App: <a href="{APP}">{APP}</a> (Zugangscode-Sperre; Inhalt per JavaScript)</li>
<li>Forschung &amp; Backtests (alle getesteten Strategien): <a href="{APP}research/">{APP}research/</a></li>
<li>Öffentliche Live-Bilanz aller Treffer: <a href="{APP}track/">{APP}track/</a></li>
<li>Quellcode (öffentlich): <a href="{REPO}">{REPO}</a> – App: <code>site/index.html</code>, Scanner: <code>backend/scanner.py</code>, Scan: <code>backend/run_scan.py</code></li>
<li>Hinweis: Die Adresse unterscheidet Groß-/Kleinschreibung – <code>/Kairo/</code> mit großem K.</li></ul>

<h2>Aufbau der App</h2><table><tr><th>Bereich</th><th>Inhalt</th></tr>
{''.join(f'<tr><td><b>{_e(a)}</b></td><td>{_e(b)}</td></tr>' for a, b in SECTIONS)}</table>

<h2>Die Kairo-Regel (wie getestet)</h2>
<ol><li>Treffer: alle 11 Kriterien erfüllt (u. a. Rücksetzer ≥ 20 % vom 52-Wochen-Hoch, Fibonacci-Zone 0,618–0,886, RSI-Divergenz,
MACD dreht, Momentum-Bias-Signal, Liquidität).</li>
<li>Einstieg: innerhalb von 10 Handelstagen nach dem Treffer bilden 5 Tage eine enge Seitwärtsphase (Spanne ≤ 1,5 ATR) → Kauf zur nächsten Eröffnung;
fällt der Kurs vorher unter das Tief der 10 Tage, ist der Treffer gescheitert.</li>
<li>Stop: Tief der Seitwärtsphase − 0,25 ATR; Risiko 0,5–3 ATR; 1 % Risiko je Trade.</li>
<li>Ausstieg: Stop, ab Tag 10 Tagesschluss unter der EMA 20 (Verkauf am nächsten Morgen), spätestens Tag 60. Kein festes Kursziel.</li>
<li>Rangfolge: schwächeres Vormomentum (Rendite Monat −6 … −1) zuerst; getestet nur USA und Europa.</li></ol>
<p class="m">Forschung 2008–2026 (49.134 Kairo-Treffer, Kosten PRIME+): Ø +0,14 R je Trade nach Kosten, zufällige Einstiege mit derselben Mechanik +0,11 R.
Als Depot bisher nicht besser als ein Welt-ETF – deshalb läuft Kairo im Papier-Test, Details auf der Forschungsseite.</p>
"""]
    try:
        n_ready = sum("kaufbereit" in _status(r, h4) for r in hits if r.get("region") in ("us", "europe"))
        st = res.get("stats") or {}
        out.append(f"""<h2>Heute: Treffer im Scanner</h2>
<p>{len(hits)} Treffer (11/11), davon {n_ready} kaufbereit in USA/Europa · {_e(st.get('loaded') or len(rows))} Aktien geprüft.</p>
<table><tr><th>#</th><th>Aktie</th><th>Ticker</th><th>Region</th><th>Kurs</th><th>Status</th><th>Stop</th><th>Vormomentum</th><th>Score</th></tr>""")
        for k, r in enumerate(hits[:40], 1):
            pl = r.get("plan") or {}
            out.append(f"<tr><td>{k}</td><td>{_e(r.get('name'))}</td><td>{_e(r.get('ticker'))}</td><td>{_e(REG.get(r.get('region'), r.get('region')))}</td>"
                       f"<td>{_n(r.get('close'))} {_e(r.get('currency'))}</td><td>{_e(_status(r, h4))}</td><td>{_n(pl.get('stop'))}</td>"
                       f"<td>{_pct((r.get('flags') or {}).get('mom61'))}</td><td>{_e(r.get('score'))}</td></tr>")
        out.append("</table>")
    except Exception as exc:
        out.append(f"<p class='m'>Treffer nicht verfügbar ({_e(type(exc).__name__)}).</p>")
    if etf:
        out.append(f"""<h2>ETF-Ampel (SPDR MSCI ACWI IMI, SPYI)</h2><p><b>{_e(etf.get('t'))}</b> – Kurs {_n(etf.get('c'))} € ·
{_pct(-(etf.get('dd') or 0), 1)} unter dem Hoch · Stand {_e(etf.get('date'))}</p><p>{_e(etf.get('s'))}</p>""")
    s = bil.get("strat60") or bil.get("strat")
    if s:
        out.append(f"""<h2>Live-Bilanz der Kairo-Regel (seit {_e(bil.get('since'))}, USA/Europa)</h2>
<ul><li>Trades mit Einstieg: {_e(s.get('mtm_n', s.get('n')))} · Ø {_n(s.get('mtm_r', s.get('avg_r')))} R (offene zum heutigen Stand) · im Plus {_pct(s.get('mtm_win', s.get('win')))}</li>
<li>Beendet: {_e(s.get('n'))} · Ø {_n(s.get('avg_r'))} R · am Stop {_pct(s.get('stop'))} · laufend: {_e(s.get('open'))}</li></ul>
<p class="m">Anfangs schließen fast nur Stops; Gewinner laufen bis zu 60 Tage. Vollständige Liste: <a href="{APP}track/">Live-Bilanz</a>.</p>""")
    if paper:
        out.append("<h2>Papier-Depots (virtuell, ohne echtes Geld, Kosten wie PRIME+)</h2><table><tr><th>Depot</th><th>Start</th><th>Wert</th><th>Rendite</th><th>abgeschlossen</th><th>offen</th></tr>")
        for p in paper:
            out.append(f"<tr><td>{_e(p.get('name') or p.get('sid'))}</td><td>{_e(p.get('start'))}</td><td>{_n(p.get('eur'), 0)} €</td>"
                       f"<td>{_pct(p.get('ret'), 1)}</td><td>{_e(p.get('trades'))}</td><td>{_e(p.get('open'))}</td></tr>")
        out.append("</table>")
    up = [e for e in cal if e.get("kind") == "earnings" and not e.get("done") and e.get("date", "") >= (today or str(date.today()))][:20]
    if up:
        out.append("<h2>Nächste Quartalszahlen</h2><ul>" + "".join(f"<li>{_e(e.get('date'))}: {_e(e.get('name') or e.get('ticker'))} ({_e(e.get('ticker'))})</li>" for e in up) + "</ul>")
    out.append("""<h2>Was eine KI hier gut prüfen kann</h2><ul><li>Regeln und Forschung: Methodik, Kosten, Überanpassung, Survivorship-Bias.</li>
<li>Bedienung: Aufbau oben; Quellcode der Oberfläche in <code>site/index.html</code>.</li>
<li>Risiko: Positionsgröße 1 %, Stop-Logik, Hebel/Turbos, Klumpenschutz (max. 2 Positionen je Sektor).</li></ul>
<p class="m">Keine Anlageberatung. Daten aus frei verfügbaren Quellen (Yahoo Finance u. a.), ohne Gewähr.</p></body></html>""")
    return "\n".join(out)


def paper_summary() -> list | None:
    try:
        d = json.loads(urllib.request.urlopen(PAPER, timeout=20).read())
        return [{"name": k, "start": v.get("start"), "eur": v.get("depot_eur"), "ret": v.get("rendite"), "open": v.get("offen"),
                 "trades": v.get("trades")} for k, v in d.items() if isinstance(v, dict)]
    except Exception:
        return None


def write(root: Path = ROOT, today: str | None = None) -> Path:
    out = root / "site" / "ai"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(render(today, paper_summary()), encoding="utf-8")
    return out / "index.html"


if __name__ == "__main__":
    print(write())
