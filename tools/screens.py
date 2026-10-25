"""Gesamt-Prüfung der App: Screenshots aller Bereiche (Handy, iPad hoch/quer, Dunkel/Hell), JS-Fehler, fehlende Dateien,
horizontales Überlaufen, Ladezeit. Beispieldaten sind erfunden (keine Nutzerdaten).

    python tools/screens.py OUTDIR
"""
from __future__ import annotations

import asyncio
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import app_smoke  # noqa: E402

SECS = app_smoke.SECS
GATE = app_smoke.GATE
DEPOT = [{"t": "NVDA", "n": "NVIDIA", "qty": 12, "price": 110, "src": "hand"}, {"t": "SAP.DE", "n": "SAP", "qty": 3, "price": 200, "src": "hand"},
         {"t": "STT", "n": "State Street Corporation", "isin": "IE00B3YLTY66", "qty": 40, "price": 250, "src": "csv"},
         {"t": "ALV.DE", "n": "Allianz", "qty": 1, "price": 300, "src": "hand"}]


def init_js(design: str) -> str:
    return ("try{localStorage.setItem('kairo-gate','%s');const k='reversal-finder-v1';const p=JSON.parse(localStorage.getItem(k)||'{}');"
            "p.briefOff=true;p.tourDone=1;p.design='%s';localStorage.setItem(k,JSON.stringify(p));"
            "if(!localStorage.getItem('kairo-depot-v1'))localStorage.setItem('kairo-depot-v1',%s);}catch(e){}") % (GATE, design, json.dumps(json.dumps(DEPOT)))


async def shoot(b, url, out, name, vp, dpr, design, rep):
    ctx = await b.new_context(viewport=vp, device_scale_factor=dpr)
    await ctx.add_init_script(init_js(design))
    pg = await ctx.new_page()
    errs, bad = [], []
    pg.on("pageerror", lambda e: errs.append(f"pageerror: {e}"))
    pg.on("console", lambda m: errs.append(f"console.{m.type}: {m.text}"[:300]) if m.type == "error" else None)
    pg.on("response", lambda r: bad.append(f"{r.status} {r.url}") if r.status >= 400 else None)
    for sec in SECS:
        errs.clear()
        await pg.goto(f"{url}?nosplash=1&sec={sec}")
        await pg.wait_for_timeout(3200)
        await pg.evaluate("document.querySelectorAll('#newsBox,.splash').forEach(x => x.remove())")
        await pg.wait_for_timeout(200)
        await pg.screenshot(path=str(out / f"{name}_{design}_{sec}.png"))
        h = await pg.evaluate("document.documentElement.scrollHeight")
        await pg.screenshot(path=str(out / f"{name}_{design}_{sec}_full.png"), full_page=True) if h < 9000 else None
        ov = await pg.evaluate("""(() => { const W = document.documentElement.clientWidth, o = [];
          document.querySelectorAll('#main *').forEach(e => { const r = e.getBoundingClientRect(); if (r.width && r.right > W + 2 && getComputedStyle(e).position !== 'fixed') o.push((e.className || e.tagName) + ' ' + Math.round(r.right - W) + 'px'); });
          return { sw: document.documentElement.scrollWidth, W, o: o.slice(0, 8) }; })()""")
        rep.setdefault(f"{name}_{design}", {})[sec] = {"errors": list(errs), "overflow": ov if ov["sw"] > ov["W"] + 1 or ov["o"] else None, "height": h}
    rep[f"{name}_{design}"]["_404"] = sorted(set(bad))
    if design == "classic":                                   # Detailansicht einer Aktie (Scanner → erste Karte)
        await pg.goto(f"{url}?nosplash=1&sec=scanner"); await pg.wait_for_timeout(2500)
        ok = await pg.evaluate("(() => { const e = [...document.querySelectorAll('[data-open]')].find(x => x.offsetParent); if (e) { e.click(); return true; } return false; })()")
        if ok:
            await pg.wait_for_timeout(2500)
            await pg.screenshot(path=str(out / f"{name}_detail.png"))
            await pg.evaluate("document.getElementById('detail') && document.getElementById('detail').scrollTo(0, 900)")
            await pg.wait_for_timeout(500); await pg.screenshot(path=str(out / f"{name}_detail_2.png"))
    await ctx.close()


async def intro(b, url, out, rep):
    """Start wie beim Öffnen: Bilder im Zeitverlauf (weißes Aufblitzen?) – ohne Code-Sperre (bereits freigeschaltet)."""
    ctx = await b.new_context(viewport={"width": 820, "height": 1180})
    await ctx.add_init_script(f"try{{localStorage.setItem('kairo-gate','{GATE}')}}catch(e){{}}")
    pg = await ctx.new_page()
    await pg.goto("about:blank")
    nav = asyncio.create_task(pg.goto(url, wait_until="commit"))
    t0 = asyncio.get_event_loop().time()
    frames = []
    for k in range(14):
        await asyncio.sleep(0.25)
        try:
            p = out / f"intro_{k:02d}.png"
            await pg.screenshot(path=str(p))
            col = await pg.evaluate("(() => { const s = getComputedStyle(document.documentElement).backgroundColor, b = document.body ? getComputedStyle(document.body).backgroundColor : '-'; return s + ' / ' + b + ' / splash=' + !!document.querySelector('.splash'); })()")
            frames.append(f"{asyncio.get_event_loop().time() - t0:.2f}s {col}")
        except Exception as exc:
            frames.append(f"err {exc!r}"[:120])
    await nav
    rep["intro"] = frames
    await ctx.close()


async def flows(b, url, out, rep):
    """Abläufe: Trade-Plan im Einstieg, Insider-Reiter, Quartalszahlen-Fenster, Aktienkarte aus Top-Setups."""
    ctx = await b.new_context(viewport={"width": 820, "height": 1180})
    await ctx.add_init_script(init_js("classic"))
    pg = await ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(f"pageerror: {e}"))
    async def go(sec, name, js=None, wait=2500):
        await pg.goto(f"{url}?nosplash=1&sec={sec}"); await pg.wait_for_timeout(3000)
        await pg.evaluate("document.querySelectorAll('#newsBox').forEach(x => x.remove())")
        if js:
            await pg.evaluate(js); await pg.wait_for_timeout(wait)
        await pg.screenshot(path=str(out / f"flow_{name}.png"))
    await go("scanner", "topsetup_card", "(() => { const e = document.querySelector('.hrow[data-card]'); e && e.click(); })()")
    await go("entry", "entry_plan", "(() => { const e = document.querySelector('[data-ein]'); e && e.click(); })()", 3500)
    await pg.evaluate("window.scrollTo(0, 900)"); await pg.wait_for_timeout(400); await pg.screenshot(path=str(out / "flow_entry_plan_2.png"))
    await go("news", "insider", "(() => { const e = [...document.querySelectorAll('.opt')].find(x => /Insider/.test(x.textContent)); e && e.click(); })()")
    await pg.evaluate("window.scrollTo(0, 700)"); await pg.wait_for_timeout(400); await pg.screenshot(path=str(out / "flow_insider_2.png"))
    await go("calendar", "earn", "(() => { const v = [...document.querySelectorAll('button')].find(x => /Liste/.test(x.textContent)); v && v.click(); setTimeout(() => { const e = document.querySelector('[data-earn]'); e && e.click(); }, 800); })()", 3500)
    await go("bilanz", "bilanz")
    rep["flows"] = errs
    await ctx.close()


async def main(out: Path) -> None:
    from playwright.async_api import async_playwright
    out.mkdir(parents=True, exist_ok=True)
    app_smoke.fetch()
    try:
        res = json.loads((app_smoke.SITE / "data" / "results.json").read_text())["results"]
        (app_smoke.SITE / "data" / "charts").mkdir(parents=True, exist_ok=True)
        for r in [r for r in res if r.get("passed") or r.get("fast_hit")][:40] + res[:20]:
            try:
                (app_smoke.SITE / "data" / "charts" / f"{r['ticker']}.json").write_bytes(urllib.request.urlopen(app_smoke.LIVE + f"charts/{r['ticker']}.json", timeout=30).read())
            except Exception:
                pass
    except Exception as exc:
        print("Charts:", exc)
    url = f"http://127.0.0.1:{app_smoke.serve()}/"
    rep: dict = {}
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--no-proxy-server"])
        await intro(b, url, out, rep)
        try:
            await flows(b, url, out, rep)
        except Exception as exc:
            rep["flows_crash"] = repr(exc)[:400]
        for name, vp, dpr in (("handy", {"width": 390, "height": 844}, 2), ("ipad", {"width": 820, "height": 1180}, 1), ("ipadq", {"width": 1180, "height": 820}, 1)):
            for design in (("classic", "light") if name != "ipadq" else ("classic",)):
                try:
                    await shoot(b, url, out, name, vp, dpr, design, rep)
                except Exception as exc:
                    rep[f"{name}_{design}_crash"] = repr(exc)[:500]
                (out / "report.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False))
        await b.close()
    (out / "report.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1] if len(sys.argv) > 1 else "shots")))
