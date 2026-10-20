"""Screenshots aller Bereiche (iPad und Handy) mit den veröffentlichten Daten – für die UX-Prüfung.

    python tools/screens.py OUTDIR
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import app_smoke  # noqa: E402

SECS = app_smoke.SECS


async def main(out: Path) -> None:
    from playwright.async_api import async_playwright
    app_smoke.fetch()
    port = app_smoke.serve()
    url = f"http://127.0.0.1:{port}/"
    out.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--no-proxy-server"])
        for name, vp in (("ipad", {"width": 820, "height": 1180}), ("handy", {"width": 390, "height": 844})):
            ctx = await b.new_context(viewport=vp, device_scale_factor=1)
            await ctx.add_init_script("try{const k='reversal-finder-v1';const p=JSON.parse(localStorage.getItem(k)||'{}');p.briefOff=true;localStorage.setItem(k,JSON.stringify(p))}catch(e){}")
            pg = await ctx.new_page()
            for sec in SECS:
                await pg.goto(f"{url}?nosplash=1&sec={sec}")
                await pg.wait_for_timeout(3000)
                await pg.screenshot(path=str(out / f"{name}_{sec}.png"))
                if name == "ipad":                         # lange Seiten in Bildschirm-Abschnitten (ohne Vollbild-Artefakte)
                    h = await pg.evaluate("document.documentElement.scrollHeight")
                    for k in range(1, min(6, int(h // 1000) + 1)):
                        await pg.evaluate(f"window.scrollTo(0, {k * 1000})")
                        await pg.wait_for_timeout(400)
                        await pg.screenshot(path=str(out / f"{name}_{sec}_{k}.png"))
            await pg.goto(f"{url}?nosplash=1&sec=scanner")
            await pg.wait_for_timeout(2000)
            for v in await pg.eval_on_selector_all("[data-view]", "els => els.map(e => e.dataset.view)"):
                await pg.click(f'[data-view="{v}"]')
                await pg.wait_for_timeout(800)
                await pg.screenshot(path=str(out / f"{name}_scanner_{v}.png"))
            ein = await pg.eval_on_selector_all("[data-ein]", "els => els.slice(0,1).map(e => e.dataset.ein)")
            if ein:
                await pg.goto(f"{url}?nosplash=1&sec=entry")
                await pg.wait_for_timeout(1500)
            for page in ("track", "research"):
                await pg.goto(f"https://dxrtex.github.io/Kairo/{page}/")
                await pg.wait_for_timeout(2000)
                await pg.screenshot(path=str(out / f"{name}_page_{page}.png"))
            await ctx.close()
        await b.close()


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1] if len(sys.argv) > 1 else "screens")))
