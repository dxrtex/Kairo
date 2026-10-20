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


def demo_tx() -> str:
    """Erfundene Beispiel-Trades (keine echten Nutzerdaten) – damit das Journal in den Screenshots Inhalt hat."""
    import json
    import random
    from datetime import date, timedelta
    rnd = random.Random(7)
    names = [("SAP SE", "DE0007164600"), ("Netflix Inc.", "US64110L1061"), ("Nvidia Long 120,50 $ Turbo Open End", "DE000DEMO0001"),
             ("Alcoa Corp.", "US0138721065"), ("Tesla Short 480,00 $ Turbo Open End", "DE000DEMO0002"), ("Allianz SE", "DE0008404005"),
             ("The Trade Desk Inc.", "US88339J1051"), ("Rheinmetall Long 1.400,00 € Turbo Open End", "DE000DEMO0003")]
    tx, d0 = [], date(2026, 4, 1)
    for k in range(36):
        n, isin = names[k % len(names)]
        d1 = d0 + timedelta(days=k * 5 + rnd.randint(0, 3)); d2 = d1 + timedelta(days=rnd.randint(2, 30))
        px = rnd.uniform(5, 300); qty = max(1, int(rnd.uniform(400, 1500) / px)); r = rnd.choice([-0.06, -0.05, -0.04, 0.02, 0.09, 0.15, -0.03, 0.25])
        for typ, dd, p in (("Buy", d1, px), ("Sell", d2, px * (1 + r))):
            tx.append({"date": dd.isoformat(), "time": "15:30:00", "status": "Executed", "ref": f"DEMO{k}{typ}", "desc": n, "asset": "Security",
                       "type": typ, "isin": isin, "qty": qty, "price": round(p, 2), "amount": round((-1 if typ == "Buy" else 1) * qty * p, 2),
                       "fee": 0.0 if qty * p >= 250 else 0.99, "tax": 0.0, "cur": "EUR", "id": f"DEMO{k}{typ}"})
    tx.sort(key=lambda t: t["date"])
    return json.dumps(tx)


async def main(out: Path) -> None:
    from playwright.async_api import async_playwright
    app_smoke.fetch()
    port = app_smoke.serve()
    url = f"http://127.0.0.1:{port}/"
    out.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--no-proxy-server"])
        for name, vp in (("ipad", {"width": 820, "height": 1180}), ("handy", {"width": 390, "height": 844})):
            if name == "ipad":                             # Code-Seite: gesperrt, dann falscher Code
                c0 = await b.new_context(viewport=vp, device_scale_factor=1); p0 = await c0.new_page()
                await p0.goto(f"{url}?nosplash=1"); await p0.wait_for_timeout(1200)
                await p0.screenshot(path=str(out / "ipad_gate.png"))
                for d in "12":
                    await p0.click(f'#gate [data-pin="{d}"]')
                await p0.screenshot(path=str(out / "ipad_gate_2.png"))
                await c0.close()
            if name == "handy":
                c0 = await b.new_context(viewport=vp, device_scale_factor=1); p0 = await c0.new_page()
                await p0.goto(f"{url}?nosplash=1"); await p0.wait_for_timeout(1200)
                await p0.screenshot(path=str(out / "handy_gate.png")); await c0.close()
            ctx = await b.new_context(viewport=vp, device_scale_factor=1)
            await ctx.add_init_script("try{localStorage.setItem('kairo-gate','31151c44ed55cace96a0cb05c2ca90411e7f0263b40ab89f351fcb64dd2b5220')}catch(e){}")
            await ctx.add_init_script("try{localStorage.setItem('kairo-tx-v1', " + repr(demo_tx()) + ")}catch(e){}")
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
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            if name == "ipad":                             # Übung als Broker: Spiel starten, Order-Ticket, Order prüfen, Aufträge
                await pg.goto(f"{url}?nosplash=1&sec=game"); await pg.wait_for_timeout(2500)
                if await pg.query_selector('[data-g="start"]'):
                    await pg.click('[data-g="start"]'); await pg.wait_for_timeout(1200)
                await pg.screenshot(path=str(out / "ipad_g1_depot.png"))
                await pg.screenshot(path=str(out / "ipad_g1b.png"), full_page=False)
                (out / "errors.txt").write_text("\n".join(errs) or "keine Fehler")
                if not await pg.query_selector('[data-g="tab"]'):
                    (out / "errors.txt").write_text("\n".join(errs) + "\nkein Tab – main: " + (await pg.inner_text("#main"))[:2000])
                    raise SystemExit(0)
                await pg.click('[data-g="tab"][data-v="trade"]'); await pg.wait_for_timeout(800)
                if await pg.query_selector('.g-idea'):
                    await pg.click('.g-idea'); await pg.wait_for_timeout(1200)
                    await pg.screenshot(path=str(out / "ipad_g2_ticket.png"))
                    c = await pg.evaluate("(() => gPx(state.gSel).c)()")
                    for sel, v in (("#gWkn", "DEMO123"), ("#gP0", "2.50"), ("#gK0", f"{c * 0.85:.2f}"), ("#gQty", "200")):
                        if await pg.query_selector(sel):
                            await pg.fill(sel, v); await pg.dispatch_event(sel, "input")
                    await pg.click('[data-g="review"]'); await pg.wait_for_timeout(800)
                    await pg.screenshot(path=str(out / "ipad_g3_review.png"))
                    if await pg.query_selector('[data-g="buy"]'):
                        await pg.click('[data-g="buy"]'); await pg.wait_for_timeout(1200)
                        await pg.screenshot(path=str(out / "ipad_g4_after.png"))
                await pg.click('[data-g="tab"][data-v="trade"]'); await pg.wait_for_timeout(800)
                if await pg.query_selector('.g-idea'):              # Limit-Order aufgeben
                    await pg.click('.g-idea'); await pg.wait_for_timeout(1000)
                    await pg.click('[data-g="otype"][data-v="limit"]'); await pg.wait_for_timeout(600)
                    c = await pg.evaluate("(() => gPx(state.gSel).c)()")
                    for sel, v in (("#gWkn", "DEMO456"), ("#gP0", "2.00"), ("#gK0", f"{c * 0.8:.2f}"), ("#gQty", "100"), ("#gTrig", f"{c * 0.95:.2f}")):
                        if await pg.query_selector(sel):
                            await pg.fill(sel, v); await pg.dispatch_event(sel, "input")
                    await pg.screenshot(path=str(out / "ipad_g6_limit.png"))
                    await pg.click('[data-g="review"]'); await pg.wait_for_timeout(800)
                    await pg.screenshot(path=str(out / "ipad_g7_limitreview.png"))
                    if await pg.query_selector('[data-g="buy"]'):
                        await pg.click('[data-g="buy"]'); await pg.wait_for_timeout(1200)
                await pg.click('[data-g="tab"][data-v="orders"]'); await pg.wait_for_timeout(800)
                await pg.screenshot(path=str(out / "ipad_g5_orders.png"))
                await pg.click('[data-g="tab"][data-v="depot"]'); await pg.wait_for_timeout(800)
                await pg.screenshot(path=str(out / "ipad_g8_depot.png"))
                (out / "errors.txt").write_text("\n".join(errs) or "keine Fehler")
                for sec in ("journal", "today"):                  # Begriff antippen
                    await pg.goto(f"{url}?nosplash=1&sec={sec}"); await pg.wait_for_timeout(2500)
                    n = await pg.evaluate("document.querySelectorAll('b.term').length")
                    if n:
                        await pg.evaluate("(() => { const t = document.querySelector('b.term'); t.scrollIntoView({block:'center'}); t.click(); })()")
                        await pg.wait_for_timeout(500)
                        await pg.screenshot(path=str(out / f"ipad_term_{sec}_{n}.png"))
            for k in range(3):                             # Rundgang
                await pg.goto(f"{url}?tour=1"); await pg.wait_for_timeout(2500)
                await pg.evaluate("document.querySelectorAll('.splash').forEach(x => x.remove())")
                for _ in range(k):
                    await pg.click('.tour-act .btn:not(.ghost)'); await pg.wait_for_timeout(300)
                await pg.screenshot(path=str(out / f"{name}_tour{k + 1}.png"))
            for page in ("track", "research"):
                await pg.goto(f"https://dxrtex.github.io/Kairo/{page}/")
                await pg.wait_for_timeout(2000)
                await pg.screenshot(path=str(out / f"{name}_page_{page}.png"))
            await ctx.close()
        await b.close()


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1] if len(sys.argv) > 1 else "screens")))
# Vorschau Broker 2
# B3
# P1
# P2
# P3
# P4
# P5
# Q1
# Q2
