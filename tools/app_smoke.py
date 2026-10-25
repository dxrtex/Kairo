"""App-Test im echten Browser – läuft vor jeder Veröffentlichung (scan.yml) und bei jedem Push (regression.yml).

Öffnet site/ mit den Daten in site/data, klickt jeden Reiter auf iPad- und Handy-Größe durch und spielt im Spiel einen
kompletten Turbo-Kauf. Jeder JavaScript-Fehler, eine leere Seite oder ein gescheiterter Kauf → Exit-Code 1, die App wird
dann nicht veröffentlicht (die alte Version bleibt online).

    python tools/app_smoke.py                 # Daten aus site/data (nach dem Scan)
    python tools/app_smoke.py --fetch         # vorher die veröffentlichten Daten laden (für Tests ohne Scan)
"""
from __future__ import annotations

import argparse
import asyncio
import functools
import http.server
import os
import sys
import threading
import urllib.request
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"
LIVE = "https://dxrtex.github.io/Kairo/data/"
FILES = ["results.json", "search.json", "analysis.json", "alerts.json", "bilanz.json", "changes.json", "calendar.json",
         "etf.json", "briefing.json", "insider.json", "h4.json", "earnings.json"]
SECS = ["today", "etf", "scanner", "entry", "calendar", "news", "depot", "journal", "game", "paper", "bilanz", "settings"]


def fetch() -> None:
    (SITE / "data").mkdir(parents=True, exist_ok=True)
    for f in FILES:
        try:
            (SITE / "data" / f).write_bytes(urllib.request.urlopen(LIVE + f, timeout=60).read())
        except Exception as exc:
            print(f"Laden {f}: {exc!r}")


def serve() -> int:
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE))
    http.server.SimpleHTTPRequestHandler.log_message = lambda *a: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv.server_address[1]



GATE = "31151c44ed55cace96a0cb05c2ca90411e7f0263b40ab89f351fcb64dd2b5220"                                         # SHA-256 des Zugangscodes (wie in index.html)


async def new_ctx(b, **kw):
    """Browser-Kontext mit freigeschaltetem Zugangscode – die Tests prüfen die App, nicht die Sperre."""
    ctx = await b.new_context(**kw)
    await ctx.add_init_script(f"try{{localStorage.setItem('kairo-gate','{GATE}')}}catch(e){{}}")
    await ctx.add_init_script("try{const k='reversal-finder-v1';const p=JSON.parse(localStorage.getItem(k)||'{}');p.tourDone=1;localStorage.setItem(k,JSON.stringify(p))}catch(e){}")
    return ctx


async def tour_check(b, url, errs):
    """Erstes Öffnen: Rundgang erscheint, „Weiter“ blättert, „Los geht’s“ schließt ihn dauerhaft."""
    ctx = await b.new_context(viewport={"width": 820, "height": 1180})
    await ctx.add_init_script(f"try{{localStorage.setItem('kairo-gate','{GATE}')}}catch(e){{}}")
    pg = await ctx.new_page()
    await pg.goto(f"{url}?tour=1")
    await pg.wait_for_timeout(3000)
    await pg.evaluate("document.querySelectorAll('.splash').forEach(x => x.remove())")
    if not await pg.query_selector(".tour-box"):
        errs.append("Rundgang: erscheint nicht")
    else:
        for _ in range(3):
            await pg.click(".tour-act .btn:not(.ghost)", timeout=5000)
            await pg.wait_for_timeout(300)
        if await pg.query_selector("#tour"):
            errs.append("Rundgang: lässt sich nicht schließen")
        elif not await pg.evaluate("JSON.parse(localStorage.getItem('reversal-finder-v1') || '{}').tourDone"):
            errs.append("Rundgang: wird nicht als gesehen gespeichert")
    await ctx.close()


async def gate_check(b, url, errs):
    """Ohne Freigabe: Code-Seite sichtbar, falscher Code bleibt gesperrt, der richtige öffnet die App.
    Der Code steht nicht im Klartext im Repo – der Test sucht ihn über den Hash (wie die App)."""
    import hashlib
    code = next(c for c in (f"{i:04d}" for i in range(10000))
                if hashlib.sha256(f"kairo-gate:{c}".encode()).hexdigest() == GATE)
    wrong = "1234" if code != "1234" else "4321"
    ctx = await b.new_context(viewport={"width": 820, "height": 1180})
    pg = await ctx.new_page()
    await pg.goto(f"{url}?nosplash=1")
    await pg.wait_for_timeout(1500)
    if not await pg.query_selector("#gate"):
        errs.append("Zugang: Code-Seite fehlt")
    else:
        if not await pg.query_selector('#gate a[href="rechtliches.html"]'):
            errs.append("Zugang: Link zu Impressum/Datenschutz fehlt")
        lp = await ctx.new_page()                    # Rechtliches ist ohne Code erreichbar
        await lp.goto(url.rstrip("/") + "/rechtliches.html")
        for sec in ("impressum", "datenschutz", "risiko"):
            if not await lp.query_selector(f"#{sec}"):
                errs.append(f"Rechtliches: Abschnitt {sec} fehlt")
        await lp.close()
        for d in wrong:
            await pg.click(f'#gate [data-pin="{d}"]')
        await pg.wait_for_timeout(700)
        if not await pg.query_selector("#gate"):
            errs.append("Zugang: falscher Code öffnet die App")
        for d in code:
            await pg.click(f'#gate [data-pin="{d}"]')
        await pg.wait_for_timeout(900)
        if await pg.query_selector("#gate"):
            errs.append("Zugang: richtiger Code öffnet die App nicht")
    await ctx.close()



HEAD = "date;time;status;reference;description;assetType;type;isin;shares;price;amount;fee;tax;currency"


async def import_check(b, url, errs):
    """Neuer Scalable-Export ersetzt den alten (Depot-Import + Journal); Hand-Positionen bleiben; falsche Datei ändert nichts."""
    ctx = await new_ctx(b, viewport={"width": 820, "height": 1180})
    await ctx.add_init_script("""try{if(!localStorage.getItem('kx-imp')){localStorage.setItem('kx-imp','1');
      localStorage.setItem('kairo-depot-v1', JSON.stringify([{t:'MSFT',n:'Microsoft',qty:1,price:300,date:'2026-01-02',src:'hand'}]))}}catch(e){}""")
    pg = await ctx.new_page()
    await pg.goto(f"{url}?nosplash=1&sec=depot")
    await pg.wait_for_timeout(2500)
    await pg.evaluate('document.querySelectorAll(".bmodal").forEach(x => x.remove())')
    a = HEAD + "\n2026-03-02;10:00:00;Executed;R1;Apple Inc.;Security;Buy;US0378331005;2;200;-400;0;0;EUR" \
             "\n2026-03-05;10:00:00;Executed;R2;Apple Inc.;Security;Buy;US0378331005;1;210;-210;0;0;EUR"
    bb = HEAD + "\n2026-04-01;10:00:00;Executed;R9;SAP SE;Security;Buy;DE0007164600;3;150;-450;0;0;EUR"
    state = "(() => { const d = JSON.parse(localStorage.getItem('kairo-depot-v1') || '[]'); return { isins: d.map(x => x.isin || x.t).sort().join(','), tx: JSON.parse(localStorage.getItem('kairo-tx-v1') || '[]').length }; })()"
    for name, body, want_isins, want_tx in (("a.csv", a, "MSFT,US0378331005", 2), ("b.csv", bb, "DE0007164600,MSFT", 1),
                                             ("falsch.csv", "foo;bar\n1;2", "DE0007164600,MSFT", 1)):
        await pg.set_input_files("#depCsv", files=[{"name": name, "mimeType": "text/csv", "buffer": body.encode()}])
        await pg.wait_for_timeout(1500)
        got = await pg.evaluate(state)
        if got["isins"] != want_isins or got["tx"] != want_tx:
            errs.append(f"Import {name}: erwartet {want_isins} / {want_tx} Transaktionen, bekommen {got}")
    await ctx.close()


async def ui_check(b, url, errs):
    """Detailansicht mit Kairo-Plan, Textgröße, Design „Hell“, Einstellungen mit Feedback."""
    ctx = await new_ctx(b, viewport={"width": 820, "height": 1180})
    pg = await ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(f"UI: JS-Fehler {e}"))
    await pg.goto(f"{url}?nosplash=1&sec=scanner")
    await pg.wait_for_timeout(2500)
    await pg.evaluate('document.querySelectorAll(".bmodal").forEach(x => x.hidden = true)')
    t = await pg.evaluate("(() => { const r = data.results.find(r => r.passed); return r ? r.ticker : null; })()")
    if t:
        await pg.evaluate(f"openCard({t!r})")
        await pg.wait_for_timeout(600)
        if not await pg.query_selector("#cardModalBody .kplan"):
            errs.append("Detailansicht: Kairo-Plan fehlt")
        await pg.evaluate("closeCard()")
    t2 = await pg.evaluate("(() => { const r = data.results.find(r => !r.criteria); return r ? r.ticker : null; })()")
    if t2:                                                   # schlanke Zeile ohne Kriterien-Details darf nicht abstürzen
        await pg.evaluate(f"openCard({t2!r})")
        await pg.wait_for_timeout(400)
        if not await pg.query_selector("#cardModalBody .kplan"):
            errs.append("Detailansicht ohne Kriterien-Details: Fehler")
        await pg.evaluate("closeCard()")
    await pg.goto(f"{url}?nosplash=1&sec=settings")
    await pg.wait_for_timeout(1500)
    await pg.evaluate('document.querySelectorAll(".bmodal").forEach(x => x.hidden = true)')
    await pg.click('[data-tsize="big"]')
    await pg.wait_for_timeout(300)
    if not await pg.evaluate("document.documentElement.classList.contains('big')"):
        errs.append("Textgröße: wird nicht übernommen")
    await pg.click('[data-tsize=""]')
    await pg.click('[data-design="light"]')
    await pg.wait_for_timeout(300)
    if not await pg.evaluate("isLight() && document.getElementById('ds-light').media === 'all'"):
        errs.append("Design Hell: wird nicht aktiv")
    if not await pg.query_selector('[data-fb="copy"]'):
        errs.append("Einstellungen: Feedback fehlt")
    await pg.goto(f"{url}?nosplash=1&sec=news")
    await pg.wait_for_timeout(1500)
    if await pg.query_selector("#main .nw-l"):
        errs.append("News: zeigt „Was ist neu“ statt der Nachrichten")
    await pg.goto(f"{url}?nosplash=1&sec=calendar")                # Quartalstermin antippen → Ergebnis/Vorschau
    await pg.wait_for_timeout(2000)
    await pg.evaluate('document.querySelectorAll(".bmodal").forEach(x => x.hidden = true)')
    ev = await pg.query_selector(".ev[data-earn]")
    if not ev and await pg.query_selector('[data-cal="calView"][data-v="list"]'):
        await pg.click('[data-cal="calView"][data-v="list"]'); await pg.wait_for_timeout(500)
        ev = await pg.query_selector(".ev[data-earn]")
    if ev:
        await ev.click(); await pg.wait_for_timeout(1500)
        if not await pg.query_selector("#earnBox .eq-h"):
            errs.append("Kalender: Quartalszahlen öffnen sich nicht")
    await ctx.close()

async def backup_check(b, url, errs):
    """Backup: ohne Haken keine Schlüssel in der Datei, mit Haken schon; Einlesen stellt Depot und Schlüssel wieder her."""
    import json as _json
    ctx = await new_ctx(b, viewport={"width": 820, "height": 1180}, accept_downloads=True)
    pg = await ctx.new_page()
    pg.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
    await pg.goto(f"{url}?nosplash=1&sec=settings")
    await pg.evaluate("localStorage.setItem('kx-td','TESTKEY'); localStorage.setItem('kairo-depot-v1','[]')")
    await pg.goto(f"{url}?nosplash=1&sec=settings")
    await pg.wait_for_timeout(2000)
    files = {}
    for keys in (False, True):
        if keys:
            await pg.check("#bkKeys")
        async with pg.expect_download() as dl:
            await pg.click("[data-backup]")
        path = await (await dl.value).path()
        files[keys] = path
        data = _json.loads(open(path, encoding="utf-8").read())["data"]
        if ("kx-td" in data) != keys:
            errs.append(f"Backup: Schlüssel {'fehlen trotz' if keys else 'drin ohne'} Haken")
    await pg.evaluate("localStorage.removeItem('kx-td'); localStorage.removeItem('kairo-depot-v1')")
    await pg.set_input_files("#restoreFile", files[True])
    await pg.wait_for_timeout(2500)
    got = await pg.evaluate("[localStorage.getItem('kx-td'), localStorage.getItem('kairo-depot-v1')]")
    if got != ["TESTKEY", "[]"]:
        errs.append(f"Backup: Einlesen stellt nicht alles wieder her ({got})")
    await ctx.close()


async def run(port: int) -> list[str]:
    from playwright.async_api import async_playwright
    url = f"http://127.0.0.1:{port}/"
    errs: list[str] = []
    async with async_playwright() as p:
        exe = os.environ.get("CHROME_PATH")
        b = await p.chromium.launch(**({"executable_path": exe} if exe else {}), args=["--no-proxy-server"])
        await gate_check(b, url, errs)
        await tour_check(b, url, errs)
        await import_check(b, url, errs)
        await backup_check(b, url, errs)
        await ui_check(b, url, errs)
        for name, vp in (("iPad", {"width": 820, "height": 1180}), ("Handy", {"width": 390, "height": 844})):
            ctx = await new_ctx(b, viewport=vp)
            pg = await ctx.new_page()
            pg.on("pageerror", lambda e, n=name: errs.append(f"{n}: JS-Fehler {e}"))
            pg.on("console", lambda m, n=name: m.type == "error" and "Uncaught" in m.text and errs.append(f"{n}: {m.text[:200]}"))
            for sec in SECS:
                await pg.goto(f"{url}?nosplash=1&sec={sec}")
                await pg.wait_for_timeout(2500)
                txt = (await pg.inner_text("#main")).strip() if await pg.query_selector("#main") else ""
                if len(txt) < 20:
                    errs.append(f"{name}: Reiter {sec} ist leer")
            # Scanner: jede Ansicht (⚡ Einstiege · Treffer · Beobachten · Trend · Meine) und die Unterreiter von Depot/Markt
            await pg.goto(f"{url}?nosplash=1&sec=scanner")
            await pg.wait_for_timeout(2000)
            for v in await pg.eval_on_selector_all("[data-view]", "els => els.map(e => e.dataset.view)"):
                await pg.click(f'[data-view="{v}"]')
                await pg.wait_for_timeout(500)
                if not (await pg.query_selector(f'[data-view="{v}"].on')):
                    errs.append(f"{name}: Scanner-Ansicht {v} lässt sich nicht wählen")
            for sec in ("depot", "news"):
                await pg.goto(f"{url}?nosplash=1&sec={sec}")
                await pg.wait_for_timeout(1500)
                for sub in await pg.eval_on_selector_all("[data-gosub]", "els => els.map(e => e.dataset.gosub)"):
                    await pg.click(f'[data-gosub="{sub}"]')
                    await pg.wait_for_timeout(800)
                    if len((await pg.inner_text("#main")).strip()) < 20:
                        errs.append(f"{name}: Unterreiter {sub} ist leer")
            w = await pg.evaluate("document.documentElement.scrollWidth")
            if w > vp["width"] + 2:
                errs.append(f"{name}: Seite breiter als der Bildschirm ({w}px)")
            await ctx.close()
        # Postfach-Designs (iPad quer): linke Liste und rechter Bereich dürfen sich nie überlappen
        for des in ("postfach-classic", "postfach", "postfach-aktien"):
            for vw, vh in ((1180, 820), (1024, 768)):
                ctx = await new_ctx(b, viewport={"width": vw, "height": vh})
                pg = await ctx.new_page()
                await pg.add_init_script(f"localStorage.setItem('reversal-finder-v1', JSON.stringify({{design: '{des}'}}))")
                await pg.goto(f"{url}?nosplash=1&sec=today")
                await pg.wait_for_timeout(2500)
                for step in ("Liste", "Detail"):
                    if step == "Detail":
                        it = await pg.query_selector(".pf-it[data-pf]")
                        if not it:
                            break
                        await pg.evaluate('document.querySelectorAll(".bmodal").forEach(x => x.remove())')
                        await it.click()
                        await pg.wait_for_timeout(1200)
                    r = await pg.evaluate("""() => { const b = s => { const e = document.querySelector(s); return e && e.getBoundingClientRect(); };
                        const L = b('.pf-list'), R = b('.pf-detail') || b('.pf-right');
                        return { ov: !!(L && R && R.left > L.left + 10 && R.left < L.right + 4), sw: document.documentElement.scrollWidth }; }""")
                    if r["ov"] or r["sw"] > vw + 2:
                        errs.append(f"{des} {vw}px ({step}): Bereiche überlappen oder Seite zu breit ({r})")
                await ctx.close()
        # Übung (Broker): Spiel starten, alle drei Reiter, Order-Ticket öffnen und prüfen lassen – jeder JS-Fehler zählt
        ctx = await new_ctx(b, viewport={"width": 820, "height": 1180})
        pg = await ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(f"Übung: JS-Fehler {e}"))
        await pg.goto(f"{url}?nosplash=1&sec=game")
        await pg.wait_for_timeout(2500)
        await pg.evaluate('document.querySelectorAll(".bmodal").forEach(x => x.remove())')
        if await pg.query_selector('[data-g="start"]'):
            await pg.click('[data-g="start"]')
            await pg.wait_for_timeout(1200)
            for v in ("trade", "orders", "depot"):
                if not await pg.query_selector(f'[data-g="tab"][data-v="{v}"]'):
                    errs.append(f"Übung: Reiter {v} fehlt nach dem Start")
                    break
                await pg.click(f'[data-g="tab"][data-v="{v}"]')
                await pg.wait_for_timeout(600)
        await ctx.close()
        # Einstieg: Aktie wählen, Turbo von Hand eintragen (Briefkurs, K.-o. + Währung, Bezugsverhältnis) → Stop-Loss am Turbo prüfen
        ctx = await new_ctx(b, viewport={"width": 820, "height": 1180})
        pg = await ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(f"Einstieg: JS-Fehler {e}"))
        await pg.goto(f"{url}?nosplash=1&sec=entry")
        await pg.wait_for_timeout(3000)
        await pg.evaluate('document.querySelectorAll(".bmodal").forEach(x => x.remove())')
        info = await pg.evaluate("""() => { if (!searchIdx) return null;
            const r = searchIdx.find(x => x.s === "hit" && x.cur && x.cur !== "EUR") || searchIdx.find(x => x.s === "hit") || searchIdx.find(x => x.c > 0);
            if (!r) return null; state.einT = r.t; state.tpT = {}; render();
            const m = tp2Calc(r, einSetup(r)); return m && m.stop ? { t: r.t, cur: r.cur || "EUR", E: m.E, stop: m.stop, fx: m.fx } : null; }""")
        await pg.wait_for_timeout(1500)
        if info and await pg.query_selector("#tpKO"):
            ko = info["stop"] - (info["E"] - info["stop"])            # K.-o. in Aktienwährung, Abstand wie Kauf→Stop
            p_brief = (info["E"] - ko) * 0.1 * info["fx"]
            if await pg.query_selector("#tpKC"):
                await pg.select_option("#tpKC", info["cur"])
                await pg.wait_for_timeout(500)
            for sel, val in (("#tpTP", f"{p_brief:.4f}"), ("#tpKO", f"{ko:.4f}"), ("#tpCR", "0.1")):
                await pg.fill(sel, val)
                await pg.dispatch_event(sel, "input")
                await pg.dispatch_event(sel, "change")
                await pg.wait_for_timeout(300)
            box = await pg.inner_text("#tpBox")
            exp = (info["stop"] - ko) * 0.1 * info["fx"]
            import re as _re
            m = _re.search(r"Stop-Loss am Turbo\s*([\d.,]+) €", box)
            got = float(m.group(1).replace(".", "").replace(",", ".")) if m else None
            if got is None or abs(got - exp) > 0.011 or "Stop-Loss im Chart" not in box or "Rechnung:" not in box:
                errs.append(f"Einstieg {info['t']}: Turbo von Hand → SL {got} statt {exp:.3f} ({box[box.find('Stop-Loss am Turbo'):][:200]!r})")
            else:
                print(f"Einstieg {info['t']} ({info['cur']}): Turbo von Hand eingetippt → SL {got} € ✓")
        else:
            print("Einstieg: kein planbarer Treffer – Turbo-Eingabe-Test übersprungen")
        await ctx.close()
        # Spiel: starten, Treffer wählen, Turbo eintragen, Vorschlag übernehmen, kaufen
        ctx = await new_ctx(b, viewport={"width": 820, "height": 1180})
        pg = await ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(f"Spiel: JS-Fehler {e}"))
        await pg.goto(f"{url}?nosplash=1&sec=game")
        await pg.wait_for_timeout(3000)
        await pg.evaluate('document.querySelectorAll(".bmodal").forEach(x => x.remove())')
        if await pg.query_selector('[data-g="start"]'):
            await pg.click('[data-g="start"]')
            await pg.wait_for_timeout(800)
            if await pg.query_selector('[data-g="tab"][data-v="trade"]'):    # Broker-Ansicht: Kairo-Treffer stehen unter „Handeln“
                await pg.click('[data-g="tab"][data-v="trade"]')
                await pg.wait_for_timeout(600)
            pick = await pg.query_selector('.g-idea[data-g="pick"]')
            if pick:
                await pick.click()
                await pg.wait_for_timeout(800)
                c = await pg.evaluate("(() => { const t = state.gSel; return gPx(t).c; })()")
                await pg.fill("#gP0", "1.50")
                await pg.dispatch_event("#gP0", "input")
                await pg.fill("#gK0", f"{c * 0.85:.2f}")
                await pg.dispatch_event("#gK0", "input")
                st = await pg.query_selector("#gStop")
                if st and not (await st.input_value()):
                    await pg.fill("#gStop", f"{c * 0.93:.2f}")
                    await pg.dispatch_event("#gStop", "input")
                await pg.fill("#gQty", "10")
                await pg.dispatch_event("#gQty", "input")
                if await pg.query_selector('[data-g="review"]'):                 # erst „Order prüfen“, dann kostenpflichtig kaufen
                    await pg.click('[data-g="review"]')
                    await pg.wait_for_timeout(600)
                await pg.click('[data-g="buy"]')
                await pg.wait_for_timeout(800)
                n = await pg.evaluate('(JSON.parse(localStorage.getItem("kairo-game2")) || {pos: []}).pos.length')
                if n != 1:
                    errs.append(f"Spiel: Kauf hat nicht geklappt ({await pg.evaluate('state.gMsg')})")
                else:                                                            # Limit-Order: reserviert Geld, Depotwert bleibt gleich
                    tot0 = await pg.evaluate("gTotals(gLoad()).total")
                    await pg.click('[data-g="tab"][data-v="trade"]'); await pg.wait_for_timeout(500)
                    await pg.click('.g-idea[data-g="pick"]'); await pg.wait_for_timeout(600)
                    await pg.click('[data-g="otype"][data-v="limit"]'); await pg.wait_for_timeout(500)
                    for sel, v in (("#gP0", "1.50"), ("#gK0", f"{c * 0.8:.2f}"), ("#gQty", "10"), ("#gTrig", f"{c * 0.95:.2f}")):
                        await pg.fill(sel, v); await pg.dispatch_event(sel, "input")
                    await pg.click('[data-g="review"]'); await pg.wait_for_timeout(500)
                    await pg.click('[data-g="buy"]'); await pg.wait_for_timeout(600)
                    g2 = await pg.evaluate("(() => { const g = gLoad(); return { p: (g.pend || []).length, n: g.pos.length, t: gTotals(g).total }; })()")
                    if g2["p"] != 1 or g2["n"] != 1 or abs(g2["t"] - tot0) > 0.01:
                        errs.append(f"Spiel: Limit-Order falsch ({g2}, vorher {tot0:.2f}, {await pg.evaluate('state.gMsg')})")
                    elif await pg.query_selector('[data-g="cancel"]'):
                        await pg.click('[data-g="cancel"]'); await pg.wait_for_timeout(400)
                        if await pg.evaluate("(gLoad().pend || []).length") != 0:
                            errs.append("Spiel: Limit-Order lässt sich nicht streichen")
            else:
                print("Spiel: heute keine Kairo-Treffer – Kauf-Test übersprungen")
        else:
            print("Spiel: Start-Knopf fehlt (ETF-Kurs fehlt?) – Kauf-Test übersprungen")
        await ctx.close()
        await b.close()
    return errs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    a = ap.parse_args()
    if a.fetch:
        fetch()
    if not (SITE / "data" / "results.json").exists():
        print("Keine Daten in site/data – mit --fetch starten")
        return 1
    errs = asyncio.run(run(serve()))
    for e in errs:
        print("FEHLER:", e)
    print("App-Test:", "bestanden" if not errs else f"{len(errs)} Fehler")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
