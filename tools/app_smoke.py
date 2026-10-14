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
         "etf.json", "briefing.json", "insider.json", "h4.json"]
SECS = ["today", "etf", "scanner", "entry", "calendar", "news", "depot", "journal", "game", "bilanz", "settings"]


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


async def run(port: int) -> list[str]:
    from playwright.async_api import async_playwright
    url = f"http://127.0.0.1:{port}/"
    errs: list[str] = []
    async with async_playwright() as p:
        exe = os.environ.get("CHROME_PATH")
        b = await p.chromium.launch(**({"executable_path": exe} if exe else {}), args=["--no-proxy-server"])
        for name, vp in (("iPad", {"width": 820, "height": 1180}), ("Handy", {"width": 390, "height": 844})):
            ctx = await b.new_context(viewport=vp)
            pg = await ctx.new_page()
            pg.on("pageerror", lambda e, n=name: errs.append(f"{n}: JS-Fehler {e}"))
            pg.on("console", lambda m, n=name: m.type == "error" and "Uncaught" in m.text and errs.append(f"{n}: {m.text[:200]}"))
            for sec in SECS:
                await pg.goto(f"{url}?nosplash=1&sec={sec}")
                await pg.wait_for_timeout(2500)
                txt = (await pg.inner_text("#main")).strip() if await pg.query_selector("#main") else ""
                if len(txt) < 20:
                    errs.append(f"{name}: Reiter {sec} ist leer")
            w = await pg.evaluate("document.documentElement.scrollWidth")
            if w > vp["width"] + 2:
                errs.append(f"{name}: Seite breiter als der Bildschirm ({w}px)")
            await ctx.close()
        # Postfach-Designs (iPad quer): linke Liste und rechter Bereich dürfen sich nie überlappen
        for des in ("postfach-classic", "postfach", "postfach-aktien"):
            for vw, vh in ((1180, 820), (1024, 768)):
                ctx = await b.new_context(viewport={"width": vw, "height": vh})
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
        # Spiel: starten, Treffer wählen, Turbo eintragen, Vorschlag übernehmen, kaufen
        ctx = await b.new_context(viewport={"width": 820, "height": 1180})
        pg = await ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(f"Spiel: JS-Fehler {e}"))
        await pg.goto(f"{url}?nosplash=1&sec=game")
        await pg.wait_for_timeout(3000)
        await pg.evaluate('document.querySelectorAll(".bmodal").forEach(x => x.remove())')
        if await pg.query_selector('[data-g="start"]'):
            await pg.click('[data-g="start"]')
            await pg.wait_for_timeout(800)
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
                await pg.click('[data-g="buy"]')
                await pg.wait_for_timeout(800)
                n = await pg.evaluate('(JSON.parse(localStorage.getItem("kairo-game2")) || {pos: []}).pos.length')
                if n != 1:
                    errs.append(f"Spiel: Kauf hat nicht geklappt ({await pg.evaluate('state.gMsg')})")
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
