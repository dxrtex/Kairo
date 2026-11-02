"""Design-Prüfstand (KAIRO DESIGN V4): reproduzierbare Screenshots + Messwerte je Ansicht, Bildschirmgröße und Design.

Deterministisch: synthetische App-Daten aus tools/design_fixtures/site_data (erzeugt mit make_site_data.py, echter Scan-Code), feste Uhrzeit (Fr 30.10.2026 22:30), alle externen Anfragen blockiert
(Live-Kurse, Nachrichten), Test-Depot mit Stop-Warnung, langen Namen und mehreren Währungen.

Messwerte je Ansicht:
  scroll     Seitenhöhe in Bildschirmhöhen (Scrollaufwand)
  overflow   horizontale Überbreite in px (sollte 0 sein)
  small_txt  sichtbare Texte < 11 px
  small_tap  sichtbare Schaltflächen/Links mit Trefferfläche < 32 px (Höhe oder Breite)
  contrast   sichtbare Texte unter WCAG-AA-Kontrast (4,5 : 1, große Schrift 3 : 1)
  nodes      sichtbare Elemente im ersten Bildschirm (visuelle Dichte)
  first_cards Überschriften im ersten Bildschirm (was sieht man sofort)
  ms         Zeit bis die Ansicht gerendert ist

    python tools/design_shots.py --out DIR --designs classic,premium [--views today,scanner] [--vps ipad-p,iphone]
"""
from __future__ import annotations

import argparse
import asyncio
import functools
import http.server
import json
import threading
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"
FIX = Path(__file__).resolve().parent / "design_fixtures" / "site_data"   # python tools/design_fixtures/make_site_data.py
GATE = "31151c44ed55cace96a0cb05c2ca90411e7f0263b40ab89f351fcb64dd2b5220"
VPS = {"iphone": (390, 844), "iphone-max": (430, 932), "ipad-p": (834, 1194), "ipad-l": (1194, 834), "ipad-split": (694, 1024),
       "desk": (1440, 900), "desk-xl": (1920, 1080)}
VIEWS = ["today", "scanner", "detail", "entry", "depot", "bilanz", "etf", "journal", "calendar", "news", "game", "paper", "settings"]
DEPOT = [
    {"t": "PLD", "n": "Prologis, Inc.", "qty": 12, "price": 104.0, "date": "2026-10-20", "src": "hand", "stop": 106.5},
    {"t": "SNEX", "n": "StoneX Group Inc.", "qty": 30, "price": 46.5, "date": "2026-10-14", "src": "hand", "stop": 43.0},
    {"t": "ITV.L", "n": "ITV plc – Independent Television Network Holdings (sehr langer Name zum Testen)", "qty": 900,
     "price": 0.72, "date": "2026-10-09", "src": "hand", "stop": 0.66},
    {"t": "EQB.TO", "n": "EQB Inc.", "qty": 10, "price": 71.0, "date": "2026-10-23", "src": "hand"},
]

METRICS_JS = r"""
() => {
  const vw = innerWidth, vh = innerHeight;
  const vis = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && +s.opacity > 0.05; };
  const lum = c => { const m = c.match(/[\d.]+/g); if (!m) return null; const [r,g,b] = m.slice(0,3).map(v => { v = +v / 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
    return 0.2126*r + 0.7152*g + 0.0722*b; };
  const alpha = c => { const m = c.match(/[\d.]+/g); return m && m.length > 3 ? +m[3] : 1; };
  const bgOf = el => { for (let e = el; e; e = e.parentElement) { const c = getComputedStyle(e).backgroundColor; if (alpha(c) > 0.5) return c; }
    return getComputedStyle(document.body).backgroundColor; };
  let small = 0, lowc = 0, checked = 0, tap = 0, nodes = 0;
  const lows = [];
  const all = [...document.querySelectorAll('#main *, header *, nav *, .tabs *, #cardModalBody *')];
  for (const el of all) {
    if (!vis(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.top < vh && r.bottom > 0) nodes++;
    const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim().length > 1);
    if (own) {
      const s = getComputedStyle(el); const fs = parseFloat(s.fontSize);
      if (fs < 11) small++;
      if (checked < 1500) { checked++;
        const a = lum(s.color), b = lum(bgOf(el)); if (a != null && b != null) { const cr = (Math.max(a,b) + .05) / (Math.min(a,b) + .05);
          const big = fs >= 18.66 || (fs >= 14 && +s.fontWeight >= 700); if (cr < (big ? 3 : 4.5) && alpha(s.color) > 0.3) { lowc++; if (lows.length < 6) lows.push((el.textContent || '').trim().slice(0, 30) + ' ' + cr.toFixed(2)); } } }
    }
    if (el.matches('button, a, [role=button], input, select, .chip, .opt, [data-card]') && (r.height < 32 || r.width < 32)) tap++;
  }
  const heads = [...document.querySelectorAll('#main h1, #main h2, #main h3, #main .section-title, #main .hcard .hh, #main .hcard h3')]
    .filter(e => vis(e) && e.getBoundingClientRect().top < vh).map(e => (e.textContent || '').trim().slice(0, 40)).slice(0, 8);
  const H = Math.max(document.documentElement.scrollHeight, document.body.scrollHeight);
  const modal = document.querySelector('#cardModalBody');
  const mh = document.body.classList.contains('card-open') && modal ? modal.scrollHeight : 0;
  // Scanner/Master-Detail: erste Aktienzeile, Zeilenhöhe, ganz sichtbare Zeilen, Liste und Detail gleichzeitig sichtbar
  const rows = [...document.querySelectorAll('#main .bd-card, #main .bd-row')].filter(vis);
  const r0 = rows[0] && rows[0].getBoundingClientRect();
  const navH = (() => { const n = document.querySelector('nav.tabbar'); if (!n || !vis(n)) return 0; const b = n.getBoundingClientRect(); return b.top > vh / 2 ? vh - b.top : 0; })();
  const ready = rows.filter(e => e.matches('.bd-card'));
  const rowH = ready.length ? Math.round(ready.slice(0, 3).reduce((a, e) => a + e.getBoundingClientRect().height, 0) / Math.min(3, ready.length)) : null;
  const full = rows.filter(e => { const b = e.getBoundingClientRect(); return b.top >= 0 && b.bottom <= vh - navH; }).length;
  const det = document.querySelector('#cardModalBody'), mainEl = document.querySelector('#main');
  let md = false;
  if (det && vis(det) && mainEl && rows.length) { const a = rows[0].getBoundingClientRect(), b = det.getBoundingClientRect(); md = a.right <= b.left + 1 && a.width > 200; }
  return { first_row: r0 ? Math.round(r0.top) : null, first_row_bottom: r0 ? Math.round(r0.bottom) : null, row_h: rowH, rows_full: full, nav_h: Math.round(navH), master_detail: md,
           scroll: +(Math.max(H, mh) / vh).toFixed(2), overflow: Math.max(0, document.documentElement.scrollWidth - vw),
           small_txt: small, small_tap: tap, contrast: lowc, contrast_ex: lows, nodes, first_cards: heads };
}
"""


def serve() -> int:
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE))
    http.server.SimpleHTTPRequestHandler.log_message = lambda *a: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv.server_address[1]


async def shoot(b, url, design, vp, views, out, metrics):
    w, h = VPS[vp]
    import re
    ver = re.search(r'const APP_VER = "([\d.]+)"', (SITE / "index.html").read_text()).group(1)
    ctx = await b.new_context(viewport={"width": w, "height": h}, device_scale_factor=1,
                              color_scheme="light" if design == "light" else "dark", reduced_motion="reduce")
    await ctx.add_init_script(f"""try{{localStorage.setItem('kairo-gate','{GATE}');
      const k='reversal-finder-v1';const p=JSON.parse(localStorage.getItem(k)||'{{}}');p.tourDone=1;p.design='{design}';p.name='Jonny';p.briefOff=1;p.newsSeen='{ver}';
      localStorage.setItem(k,JSON.stringify(p));
      if(!localStorage.getItem('kairo-depot-v1'))localStorage.setItem('kairo-depot-v1',{json.dumps(json.dumps(DEPOT))});}}catch(e){{}}""")

    charts = json.loads((Path(__file__).parent / "design_fixtures" / "charts.json").read_text())

    async def route(r):
        u = r.request.url
        if u.startswith(url + "data/"):                  # App-Daten immer aus dem festen Fixture (make_site_data.py)
            from urllib.parse import unquote
            rel = unquote(u[len(url) + 5:].split("?")[0])
            f = FIX / rel
            if "charts/" in rel and rel[7:-5] in charts:
                await r.fulfill(status=200, content_type="application/json", body=json.dumps(charts[rel[7:-5]]))
            elif f.is_file():
                await r.fulfill(status=200, content_type="application/json", body=f.read_bytes())
            else:
                await r.fulfill(status=404, body="")
            return
        if u.startswith(url):
            await r.continue_()
        else:
            await r.abort()
    await ctx.route("**/*", route)
    pg = await ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)[:160]))
    try:
        await pg.clock.set_fixed_time("2026-10-30T22:30:00+01:00")
    except Exception:
        pass
    for v in views:
        sec = "scanner" if v == "detail" else v
        t0 = asyncio.get_event_loop().time()
        await pg.goto(f"{url}?nosplash=1&sec={sec}")
        await pg.wait_for_timeout(1800)
        if v == "detail":
            await pg.evaluate("openCard('PLD')")
            await pg.wait_for_timeout(1500)
        ms = int((asyncio.get_event_loop().time() - t0) * 1000)
        await pg.evaluate("document.querySelectorAll('.splash,#tour,#newsBox,#briefBox,.bmodal').forEach(x => x.remove())")
        m = await pg.evaluate(METRICS_JS)
        m.update(ms=ms, errors=list(errs))
        errs.clear()
        metrics[f"{design}|{vp}|{v}"] = m
        d = out / design / vp
        d.mkdir(parents=True, exist_ok=True)
        await pg.screenshot(path=str(d / f"{v}.png"))
        if v in ("today", "scanner", "detail", "depot", "entry"):
            await pg.screenshot(path=str(d / f"{v}_full.png"), full_page=True)
    await ctx.close()


async def main_async(a):
    from playwright.async_api import async_playwright
    if not (FIX / "results.json").exists():
        import subprocess, sys
        subprocess.run([sys.executable, str(FIX.parent / "make_site_data.py")], check=True, stdout=subprocess.DEVNULL)
    port = serve()
    url = f"http://127.0.0.1:{port}/"
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    metrics = {}
    async with async_playwright() as p:
        import os
        import glob
        exe = os.environ.get("CHROME_PATH") or next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome"), reverse=True)), None)
        b = await p.chromium.launch(args=["--no-proxy-server"], **({"executable_path": exe} if exe else {}))
        for design in a.designs.split(","):
            for vp in a.vps.split(","):
                await shoot(b, url, design, vp, a.views.split(","), out, metrics)
                print(design, vp, "fertig", flush=True)
        await b.close()
    mf = out / "metrics.json"
    old = json.loads(mf.read_text()) if mf.exists() else {}
    old.update(metrics)
    mf.write_text(json.dumps(old, indent=1, ensure_ascii=False))
    return metrics


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--designs", default="classic")
    ap.add_argument("--views", default=",".join(VIEWS))
    ap.add_argument("--vps", default=",".join(VPS))
    a = ap.parse_args()
    asyncio.run(main_async(a))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
