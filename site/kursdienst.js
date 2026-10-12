// Kairo-Kursdienst – kleiner Cloudflare Worker (kostenlos), der Kurse von Yahoo Finance für die Kairo-App holt.
// Damit bekommen auch deutsche/europäische/asiatische Aktien Live-Kurse (je nach Börse leicht verzögert, XETRA ca. 15 Min.).
// Einrichtung: Cloudflare → Workers & Pages → Create → Worker → „Hello World“ → Deploy → Edit code →
// alles ersetzen durch diesen Code → Deploy. Die Adresse (https://….workers.dev) in Kairo unter Einstellungen → Live-Kurse eintragen.
// Abruf: https://….workers.dev/?s=SAP.DE,AAPL,7203.T  →  {"SAP.DE": {"c":…, "pc":…, "h":…, "l":…, "t":…, "cur":"EUR"}, …}

const ALLOW = ["https://dxrtex.github.io"];          // nur die Kairo-App darf den Dienst im Browser nutzen
const MAX = 25;                                       // höchstens so viele Aktien je Abruf

export default {
  async fetch(request, env, ctx) {
    const origin = request.headers.get("Origin") || "";
    const cors = {
      "Access-Control-Allow-Origin": ALLOW.includes(origin) ? origin : ALLOW[0],
      "Access-Control-Allow-Methods": "GET, OPTIONS",
      "Vary": "Origin",
    };
    if (request.method === "OPTIONS") return new Response(null, { headers: cors });
    const url = new URL(request.url);
    const syms = (url.searchParams.get("s") || "").split(",").map(x => x.trim().toUpperCase())
      .filter(x => /^[A-Z0-9.\-^=]{1,20}$/.test(x)).slice(0, MAX);
    if (!syms.length) return json({ ok: true, info: "Kairo-Kursdienst läuft. Abruf: ?s=SAP.DE,AAPL" }, cors);
    const out = {};
    await Promise.all(syms.map(async s => { out[s] = await quote(s, ctx); }));
    return json(out, cors);
  },
};

async function quote(sym, ctx) {
  const cache = caches.default, key = new Request("https://kairo-kurse.cache/" + sym);
  const hit = await cache.match(key);
  if (hit) return hit.json();
  for (const host of ["query1", "query2"]) {
    try {
      const r = await fetch(`https://${host}.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(sym)}?interval=1m&range=1d`,
        { headers: { "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15" } });
      if (!r.ok) continue;
      const m = (((await r.json()).chart || {}).result || [])[0];
      const meta = m && m.meta;
      if (!meta || !(meta.regularMarketPrice > 0)) continue;
      const q = { c: meta.regularMarketPrice, pc: meta.chartPreviousClose ?? meta.previousClose ?? null,
                  h: meta.regularMarketDayHigh ?? null, l: meta.regularMarketDayLow ?? null,
                  t: (meta.regularMarketTime || 0) * 1000, cur: meta.currency || null };
      ctx.waitUntil(cache.put(key, new Response(JSON.stringify(q), { headers: { "Cache-Control": "max-age=20" } })));
      return q;
    } catch (e) { /* nächster Host */ }
  }
  return null;
}

function json(obj, cors) {
  return new Response(JSON.stringify(obj), { headers: { ...cors, "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" } });
}
