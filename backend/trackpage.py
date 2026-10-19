"""Öffentliche Live-Bilanz als statische Seite (site/track/index.html, ohne JavaScript – auch für KI-Assistenten lesbar).

Jeder Kairo-Treffer wird am Abend des Signaltags im Branch kairo-data gespeichert (Git-Commit mit Zeitstempel) und danach
automatisch nach der aktuellen Kairo-Regel verfolgt (live.py, st60). Nichts wird nachträglich entfernt – auch Verlierer nicht.
"""

from __future__ import annotations

import html
from pathlib import Path

REPO = "https://github.com/dxrtex/Kairo"
REG = {"us": "USA", "europe": "Europa", "asia": "Asien/Pazifik"}
RES = {"wait": "wartet auf Seitwärtsphase", "nobase": "kein Einstieg", "run": "läuft", "stop": "Stop", "ema": "Ausstieg EMA20",
       "zeit": "Ausstieg Tag 60"}
DONE = ("stop", "ema", "zeit")


def summary(hits: list[dict]) -> dict:
    st = [(h.get("st60") or {}) for h in hits]
    done = [x["r"] for x in st if x.get("res") in DONE and x.get("r") is not None]
    run = [x["r"] for x in st if x.get("res") == "run" and x.get("r") is not None]
    return {"n": len(hits), "nobase": sum(x.get("res") == "nobase" for x in st), "wait": sum(x.get("res") in (None, "wait") for x in st),
            "run": len(run), "run_r": sum(run) / len(run) if run else None, "done": len(done),
            "avg": sum(done) / len(done) if done else None, "sum": sum(done) if done else None,
            "win": sum(r > 0 for r in done) / len(done) if done else None}


def _f(v, d=2, sign=True, pct=False):
    if v is None:
        return "–"
    v = 100 * v if pct else v
    s = f"{v:+.{d}f}" if sign else f"{v:.{d}f}"
    return s.replace(".", ",").replace("-", "−") + (" %" if pct else "")


def render(sig: list[dict], today: str) -> str:
    hits = sorted([s for s in sig if s.get("k") == "hit"], key=lambda s: (s["d"], s["t"]), reverse=True)
    since = min((s["d"] for s in hits), default=today)
    groups = [("Alle Regionen", hits), ("USA + Europa (wie Papier-Depot)", [h for h in hits if h.get("region") in ("us", "europe")])] + \
             [(REG[r], [h for h in hits if h.get("region") == r]) for r in REG]
    rows = "\n".join(f"<tr><td>{html.escape(g)}</td><td>{s['n']}</td><td>{s['nobase']}</td><td>{s['wait']}</td><td>{s['run']}</td>"
                     f"<td>{s['done']}</td><td>{_f(s['avg'])} R</td><td>{_f(s['win'], 0, False, True)}</td><td>{_f(s['sum'], 1)} R</td></tr>"
                     for g, s in ((g, summary(h)) for g, h in groups))
    lst = "\n".join(
        f"<tr><td>{h['d']}</td><td>{html.escape(h['t'])}</td><td>{html.escape(h.get('n') or '')}</td><td>{REG.get(h.get('region'), '–')}</td>"
        f"<td>{h.get('score') or ''}</td><td>{RES.get((h.get('st60') or {}).get('res'), 'wartet auf Seitwärtsphase')}</td>"
        f"<td>{_f((h.get('st60') or {}).get('r')) + ' R' if (h.get('st60') or {}).get('r') is not None else '–'}</td></tr>"
        for h in hits[:400])
    return f'''<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kairo – Live-Bilanz</title>
<meta name="description" content="Öffentliche, automatisch geführte Live-Bilanz aller Kairo-Scanner-Treffer seit {since}, inklusive Verlierer.">
<style>
:root{{--bg:#fff;--fg:#1d1d1f;--mut:#6e6e73;--line:#e5e5ea;--acc:#0a84ff}}
@media (prefers-color-scheme:dark){{:root{{--bg:#000;--fg:#f5f5f7;--mut:#a1a1a6;--line:#2c2c2e}}}}
body{{background:var(--bg);color:var(--fg);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;margin:0;padding:24px 16px}}
main{{max-width:980px;margin:0 auto}} h1{{font-size:28px;margin:0 0 4px}} h2{{margin-top:32px;font-size:20px}}
a{{color:var(--acc)}} .mut{{color:var(--mut)}} .tw{{overflow-x:auto}}
table{{border-collapse:collapse;width:100%;font-size:14px}} td,th{{border-bottom:1px solid var(--line);padding:7px 6px;text-align:left;vertical-align:top;white-space:nowrap}}
th{{color:var(--mut);font-weight:600}}
</style></head><body><main>
<h1>Kairo – Live-Bilanz</h1>
<p class="mut">Stand {today} · Treffer seit {since} · <a href="../">zur App</a> · <a href="../research/">Forschung &amp; Backtests</a></p>

<h2>Was hier gezählt wird</h2>
<p>Jeder Treffer des täglichen Kairo-Scanners (Long-Reversal-Setup) wird automatisch nach der aktuellen Regel verfolgt – ohne Auswahl, ohne nachträgliches Löschen:
nach dem Treffer bis zu 10 Handelstage auf eine Seitwärtsphase warten (5 Kerzen, Spanne ≤ 1,5 ATR), Kauf zur nächsten Eröffnung in der Spanne,
Stop = Tief der Seitwärtsphase − 0,25 ATR; Ausstieg ab Tag 10 bei Schluss unter der EMA 20 (zur nächsten Eröffnung), spätestens Tag 60.
Ergebnis in R (Vielfache des Risikos je Trade), nach Modellkosten. Fällt der Kurs vor dem Einstieg unter das 10-Tage-Tief oder bildet sich keine Seitwärtsphase, zählt der Treffer als „kein Einstieg“.</p>
<p><b>Erwartung aus dem Backtest 2008–2026</b> (49.134 Treffer, Kosten Scalable PRIME+): Ø +0,14 R je Trade, Zufalls-Einstiege +0,11 R –
also ein kleiner Vorteil mit vielen Verlierern; aussagekräftig erst ab einigen hundert abgeschlossenen Trades.</p>
<p><b>Nachprüfbar:</b> Die Treffer stehen in <a href="{REPO}/commits/kairo-data">Git-Commits mit Zeitstempel</a> (Datei signals.json).
Eine nachträgliche Änderung wäre in der Historie sichtbar.</p>

<h2>Übersicht</h2>
<div class="tw"><table><thead><tr><th>Gruppe</th><th>Treffer</th><th>kein Einstieg</th><th>wartet</th><th>läuft</th><th>abgeschlossen</th><th>Ø R</th><th>Gewinner</th><th>Summe R</th></tr></thead><tbody>
{rows}
</tbody></table></div>

<h2>Treffer (neueste zuerst, max. 400)</h2>
<div class="tw"><table><thead><tr><th>Signaltag</th><th>Ticker</th><th>Name</th><th>Region</th><th>Score</th><th>Status</th><th>Ergebnis</th></tr></thead><tbody>
{lst}
</tbody></table></div>
<p class="mut">Laufende Trades: Stand zum letzten Schluss. Zusätzlich laufen virtuelle Depots mit begrenztem Kapital (KAIRO, KAIROS u. a.):
<a href="{REPO}/tree/paper-data">Papier-Depots</a>. Keine Anlageberatung.</p>
</main></body></html>
'''


def write(sig: list[dict], today: str, root: Path) -> Path:
    out = root / "site" / "track"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(render(sig, today), encoding="utf-8")
    return out / "index.html"
