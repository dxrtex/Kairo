"""Live-Probe der veröffentlichten App: Suche im Reiter „Einstieg“ und Trade-Plan im echten Browser.

    python tools/live_probe.py "Axon"
"""
import asyncio
import json
import sys
import urllib.request

from playwright.async_api import async_playwright

URL = "https://dxrtex.github.io/Kairo/"


async def main(q: str) -> None:
    d = json.load(urllib.request.urlopen(URL + "data/search.json"))
    rows = d.get("rows") or []
    hit = [r for r in rows if q.lower() in (r.get("t", "") + " " + r.get("n", "")).lower()]
    print("search.json:", d.get("generated"), "Zeilen", len(rows), "mit pl", sum(1 for r in rows if r.get("pl")))
    for r in hit[:5]:
        print("ZEILE", json.dumps(r, ensure_ascii=False)[:1500])
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 820, "height": 1180})
        errs = []
        pg.on("pageerror", lambda e: errs.append("pageerror " + str(e)))
        pg.on("console", lambda m: m.type == "error" and errs.append("console " + m.text))
        await pg.goto(URL + "?nosplash=1")
        await pg.wait_for_timeout(4000)
        await pg.evaluate('goSec("entry")')
        await pg.wait_for_timeout(2500)
        await pg.fill("#einQ", q)
        await pg.wait_for_timeout(1500)
        print("LISTE:", (await pg.inner_text("#einList"))[:800])
        opt = await pg.query_selector("#einList .ein-opt")
        if opt:
            await opt.click()
            await pg.wait_for_timeout(2500)
            box = await pg.query_selector("#tpBox")
            print("TP:", (await box.inner_text())[:2500] if box else "kein #tpBox")
        print("FEHLER:", errs)
        await b.close()


asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "Axon"))
