"""Screenshots aller Bereiche (iPad und Handy) mit den veröffentlichten Daten – für die UX-Prüfung.

    python tools/screens.py OUTDIR
"""
from __future__ import annotations

import asyncio
import json
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
    try:                                               # Probe: schnellere Quellen für frisch gemeldete Zahlen (Netflix 20.10. nach Börsenschluss)
        import urllib.request as _ur, yfinance as _yf
        out.mkdir(parents=True, exist_ok=True)
        lines = []
        tk = _yf.Ticker("NFLX")
        try: lines.append("earnings_dates:\n" + str(tk.get_earnings_dates(limit=3)))
        except Exception as exc: lines.append(f"ed ERR {exc!r}")
        try: lines.append("history:\n" + str(tk.get_earnings_history()))
        except Exception as exc: lines.append(f"eh ERR {exc!r}")
        for nm, u in (("nasdaq-surprise", "https://api.nasdaq.com/api/company/NFLX/earnings-surprise"),
                      ("nasdaq-calendar", "https://api.nasdaq.com/api/calendar/earnings?date=2026-10-20"),
                      ("yahoo-qs", "https://query2.finance.yahoo.com/v10/finance/quoteSummary/NFLX?modules=earnings,earningsHistory,calendarEvents"),
                      ("yahoo-cal", "https://finance.yahoo.com/calendar/earnings?day=2026-10-20")):
            try:
                req = _ur.Request(u, headers={"User-Agent": "Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/120 Safari/537.36", "Accept": "application/json, text/plain, */*"})
                x = _ur.urlopen(req, timeout=20).read().decode("utf-8", "replace")
                import re as _re2
                i = x.find("NFLX"); lines.append(f"== {nm}: {len(x)} B\n{x[:1500]}\n...{x[max(0,i-300):i+900] if i >= 0 else ''}")
            except Exception as exc:
                lines.append(f"== {nm} ERR {exc!r}")
        (out / "probe_fast.txt").write_text("\n\n".join(lines))
    except Exception:
        import traceback
        (out / "probe_fast.txt").write_text(traceback.format_exc())
    try:                                               # Prüfdienst tagsüber testen (wie Workflow earnings.yml)
        import time as _t
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from backend import earnings as _e
        out.mkdir(parents=True, exist_ok=True)
        t0 = _t.time(); _e.live_main("/tmp/earnlive", None)
        (out / "earn_live.txt").write_text(f"{_t.time() - t0:.0f} s\n" + Path("/tmp/earnlive/earnings_live.json").read_text()[:100000])
    except Exception:
        import traceback
        out.mkdir(parents=True, exist_ok=True); (out / "earn_live.txt").write_text(traceback.format_exc())
    try:                                               # Quartalszahlen wie im Scan erzeugen (echte Daten) – für die Kalender-Ansicht
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from backend import earnings
        cp = app_smoke.SITE / "data" / "calendar.json"
        cal = json.loads(cp.read_text())
        extra = {t: {"ticker": t, "name": n, "big": True} for t, n in (("NFLX", "Netflix"), ("JPM", "JPMorgan"), ("ASML", "ASML"), ("TSLA", "Tesla"), ("SAP", "SAP"), ("MSFT", "Microsoft"))}
        earn, mem, past = earnings.run(cal["events"], {}, {}, extra)
        have = {(e.get("ticker"), e["date"]) for e in cal["events"]}
        cal["events"] = sorted(cal["events"] + [e for e in past if (e["ticker"], e["date"]) not in have], key=lambda e: (e["date"], e["kind"], e.get("name", "")))
        for e in cal["events"]:
            rec = earn["tickers"].get(e.get("ticker") or "")
            if e["kind"] == "earnings" and rec and (rec.get("last") or {}).get("date") == e["date"]:
                e["done"] = True; e["tone"] = ((rec["last"].get("view") or {}).get("tone")) or "gray"
        cp.write_text(json.dumps(cal, ensure_ascii=False))
        (app_smoke.SITE / "data" / "earnings.json").write_text(json.dumps(earn, ensure_ascii=False, default=str))
        out.mkdir(parents=True, exist_ok=True)
        (out / "earnings.json").write_text(json.dumps(earn, ensure_ascii=False, indent=1, default=str)[:200000])
    except Exception as exc:
        import traceback
        out.mkdir(parents=True, exist_ok=True); (out / "earnings_err.txt").write_text(traceback.format_exc())
    try:                                               # Größe je Feld in results.json / search.json (für die Ladezeit)
        out.mkdir(parents=True, exist_ok=True)
        lines = []
        for fn in ("results.json", "search.json"):
            d = json.loads((app_smoke.SITE / "data" / fn).read_text())
            rows = d.get("results") or d.get("rows") or []
            tot = {}
            for r in (rows if isinstance(rows, list) else []):
                for k, v in (r.items() if isinstance(r, dict) else []):
                    tot[k] = tot.get(k, 0) + len(json.dumps(v, ensure_ascii=False, separators=(",", ":")))
            lines.append(f"{fn}: {(app_smoke.SITE / 'data' / fn).stat().st_size // 1024} KB, Typ {type(d).__name__}, Schlüssel {list(d)[:8] if isinstance(d, dict) else ''}")
            lines += [f"  {k}: {v // 1024} KB" for k, v in sorted(tot.items(), key=lambda x: -x[1])[:20]]
        import gzip
        for f in sorted((app_smoke.SITE / "data").glob("*.json"), key=lambda f: -f.stat().st_size)[:12]:
            b = f.read_bytes(); lines.append(f"{f.name}: {len(b) // 1024} KB roh, {len(gzip.compress(b, 6)) // 1024} KB gzip")
        (out / "sizes.txt").write_text("\n".join(lines))
    except Exception as exc:
        (out / "sizes.txt").write_text(f"Fehler {exc!r}")
    try:                                               # Charts der Treffer (für die Detailansicht)
        import json as _j, urllib.request as _u
        res = _j.loads((app_smoke.SITE / "data" / "results.json").read_text())["results"]
        (app_smoke.SITE / "data" / "charts").mkdir(parents=True, exist_ok=True)
        for r in [r for r in res if r.get("passed") or r.get("fast_hit")][:60]:
            try:
                (app_smoke.SITE / "data" / "charts" / f"{r['ticker']}.json").write_bytes(_u.urlopen(app_smoke.LIVE + f"charts/{r['ticker']}.json", timeout=30).read())
            except Exception:
                pass
    except Exception as exc:
        print("Charts:", exc)
    port = app_smoke.serve()
    url = f"http://127.0.0.1:{port}/"
    out.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--no-proxy-server"])
        for nm, vp in (("handy", {"width": 390, "height": 844}), ("ipad", {"width": 820, "height": 1180})):   # Quartalszahlen im Kalender
            ec = await b.new_context(viewport=vp, device_scale_factor=2 if nm == "handy" else 1)
            await ec.add_init_script("try{localStorage.setItem('kairo-gate','31151c44ed55cace96a0cb05c2ca90411e7f0263b40ab89f351fcb64dd2b5220')}catch(e){}")
            await ec.add_init_script("try{const k='reversal-finder-v1';const p=JSON.parse(localStorage.getItem(k)||'{}');p.briefOff=true;p.tourDone=1;p.calView='list';localStorage.setItem(k,JSON.stringify(p))}catch(e){}")
            ep = await ec.new_page()
            errs = []
            ep.on("pageerror", lambda e: errs.append(str(e)))
            await ep.goto(f"{url}?nosplash=1&sec=calendar"); await ep.wait_for_timeout(3500)
            await ep.evaluate("(() => { const n = document.getElementById('newsBox'); if (n) n.remove(); })()")
            await ep.screenshot(path=str(out / f"earn_{nm}_list.png"))
            for tag, sel in (("done", ".ev[data-earn]:has(.ev-res)"), ("next", ".ev[data-earn]:not(:has(.ev-res))")):
                el = await ep.query_selector(sel)
                if not el:
                    errs.append(f"kein Termin für {tag}"); continue
                await el.click(); await ep.wait_for_timeout(1800)
                await ep.screenshot(path=str(out / f"earn_{nm}_{tag}.png"))
                cl = await ep.query_selector("#earnBox .cm-x")
                if cl:
                    await cl.click(); await ep.wait_for_timeout(300)
            (out / f"earn_{nm}_errors.txt").write_text("\n".join(errs) or "keine Fehler")
            await ec.close()
        for nm, vp in (("ipad", {"width": 820, "height": 1180}), ("handy", {"width": 390, "height": 844})):   # neuer Nutzer: Code → Intro → Rundgang → Heute
            nc = await b.new_context(viewport=vp, device_scale_factor=1)
            npg = await nc.new_page()
            await npg.goto(url); await npg.wait_for_timeout(700)
            await npg.screenshot(path=str(out / f"new_{nm}_1_gate.png"))
            for d in "7777":
                await npg.click(f'#gate [data-pin="{d}"]'); await npg.wait_for_timeout(120)
            for k, w in ((2, 500), (3, 1200), (4, 2500)):
                await npg.wait_for_timeout(w)
                await npg.screenshot(path=str(out / f"new_{nm}_{k}_intro.png"))
            await npg.wait_for_timeout(4000)
            await npg.screenshot(path=str(out / f"new_{nm}_5_tour.png"))
            for _ in range(3):
                if await npg.query_selector(".tour-act .btn:not(.ghost)"):
                    await npg.click(".tour-act .btn:not(.ghost)"); await npg.wait_for_timeout(400)
            await npg.wait_for_timeout(800)
            await npg.screenshot(path=str(out / f"new_{nm}_6_today.png"))
            await npg.screenshot(path=str(out / f"new_{nm}_7_today_full.png"), full_page=True)
            await nc.close()
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
            await ctx.add_init_script("try{const k='reversal-finder-v1';const p=JSON.parse(localStorage.getItem(k)||'{}');p.briefOff=true;p.tourDone=1;localStorage.setItem(k,JSON.stringify(p))}catch(e){}")
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
            await pg.goto(f"{url}?nosplash=1&sec=scanner"); await pg.wait_for_timeout(2500)   # Detailansicht
            await pg.evaluate("document.querySelectorAll('.bmodal').forEach(x => x.remove())")
            for j, sel in enumerate(("r => r.passed && kSt(r).k === 'ready'", "r => r.passed && kSt(r).k === 'wait'", "r => r.fast_hit && !r.passed")):
                t = await pg.evaluate(f"(() => {{ const r = data.results.find({sel}); return r ? r.ticker : null; }})()")
                if t:
                    await pg.evaluate(f"openCard({t!r})"); await pg.wait_for_timeout(1200)
                    await pg.screenshot(path=str(out / f"{name}_card{j + 1}.png"))
                    await pg.evaluate("closeCard()")
            for k in range(3):                             # Rundgang
                await pg.goto(f"{url}?tour=1"); await pg.wait_for_timeout(2500)
                await pg.evaluate("document.querySelectorAll('.splash').forEach(x => x.remove())")
                for _ in range(k):
                    hit = await pg.evaluate("""(() => { const b = document.querySelector('.tour-act .btn:not(.ghost)'); if (!b) return 'kein Knopf';
                      const r = b.getBoundingClientRect(), el = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
                      return (el ? el.className + ' / ' + (el.parentElement && el.parentElement.id) : 'nichts') + ' · Fenster ' + document.querySelectorAll('#tour').length; })()""")
                    with open(out / "errors.txt", "a") as fh:
                        fh.write(f"\n{name} Rundgang {k}: {hit}")
                    await pg.click('.tour-act .btn:not(.ghost)', timeout=5000); await pg.wait_for_timeout(300)
                await pg.screenshot(path=str(out / f"{name}_tour{k + 1}.png"))
            if name == "ipad":                             # helles Design (Automatisch + System hell)
                lc = await b.new_context(viewport=vp, device_scale_factor=1, color_scheme="dark")
                await lc.add_init_script("try{localStorage.setItem('kairo-gate','31151c44ed55cace96a0cb05c2ca90411e7f0263b40ab89f351fcb64dd2b5220');localStorage.setItem('kairo-tx-v1', " + repr(demo_tx()) + ");const k='reversal-finder-v1';const p=JSON.parse(localStorage.getItem(k)||'{}');p.briefOff=true;p.tourDone=1;p.design='light';localStorage.setItem(k,JSON.stringify(p))}catch(e){}")
                lp = await lc.new_page()
                for sec in ("today", "scanner", "entry", "etf", "depot", "journal", "game", "bilanz", "paper", "settings", "news", "calendar"):
                    await lp.goto(f"{url}?nosplash=1&sec={sec}"); await lp.wait_for_timeout(2200)
                    await lp.screenshot(path=str(out / f"light_{sec}.png"))
                    if sec == "today":
                        await lp.evaluate("window.scrollTo(0, 1100)"); await lp.wait_for_timeout(400)
                        await lp.screenshot(path=str(out / "light_today_1.png"))
                    if sec == "scanner":
                        t = await lp.evaluate("(() => { const r = data.results.find(r => r.passed); return r ? r.ticker : null; })()")
                        if t:
                            await lp.evaluate(f"openCard({t!r})"); await lp.wait_for_timeout(1200)
                            await lp.screenshot(path=str(out / "light_card.png")); await lp.evaluate("closeCard()")
                await lc.close()
            if name == "ipad":                             # Ladezeit: was lädt die Startseite, wie lange bis zur Anzeige?
                pc = await b.new_context(viewport=vp)
                await pc.add_init_script("try{localStorage.setItem('kairo-gate','31151c44ed55cace96a0cb05c2ca90411e7f0263b40ab89f351fcb64dd2b5220');const k='reversal-finder-v1';const p=JSON.parse(localStorage.getItem(k)||'{}');p.briefOff=true;p.tourDone=1;localStorage.setItem(k,JSON.stringify(p))}catch(e){}")
                pp = await pc.new_page()
                await pp.goto(f"{url}?nosplash=1"); await pp.wait_for_timeout(6000)
                rep = await pp.evaluate("""(() => { const r = performance.getEntriesByType('resource').map(e => [e.name.split('/').slice(-2).join('/'), Math.round(e.transferSize/1024), Math.round(e.duration)]);
                  const n = performance.getEntriesByType('navigation')[0]; return { dom: Math.round(n.domContentLoadedEventEnd), load: Math.round(n.loadEventEnd), html: Math.round(n.transferSize/1024), res: r.sort((a, b) => b[1] - a[1]).slice(0, 25) }; })()""")
                (out / "perf.txt").write_text(json.dumps(rep, indent=1))
                await pc.close()
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
# Z1
