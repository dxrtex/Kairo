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
    return json(await quotes(syms, ctx), cors);
  },
};

// Erst alle Aktien in einem Abruf (spark), fehlende einzeln (chart). Ohne Browser-Kennung – die beantwortet Yahoo mit 429.
async function quotes(syms, ctx) {
  const cache = caches.default, out = {}, miss = [];
  await Promise.all(syms.map(async s => { const hit = await cache.match(key(s)); if (hit) out[s] = await hit.json(); else miss.push(s); }));
  if (miss.length) {
    for (const host of ["query1", "query2"]) {
      const todo = miss.filter(s => !out[s]);
      if (!todo.length) break;
      try {
        const r = await fetch(`https://${host}.finance.yahoo.com/v7/finance/spark?symbols=${todo.map(encodeURIComponent).join(",")}&range=1d&interval=5m`);
        if (!r.ok) continue;
        for (const x of ((await r.json()).spark || {}).result || []) {
          const meta = x && x.response && x.response[0] && x.response[0].meta;
          if (meta && meta.regularMarketPrice > 0) out[String(x.symbol).toUpperCase()] = pack(meta);
        }
      } catch (e) { /* nächster Host */ }
    }
    for (const s of miss.filter(s => !out[s])) {
      for (const host of ["query1", "query2"]) {
        try {
          const r = await fetch(`https://${host}.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(s)}?interval=1d&range=5d`);
          if (!r.ok) continue;
          const meta = ((((await r.json()).chart || {}).result || [])[0] || {}).meta;
          if (meta && meta.regularMarketPrice > 0) { out[s] = pack(meta); break; }
        } catch (e) { /* nächster Host */ }
      }
    }
    for (const s of miss) if (out[s]) ctx.waitUntil(cache.put(key(s), new Response(JSON.stringify(out[s]), { headers: { "Cache-Control": "max-age=20" } })));
  }
  for (const s of syms) if (!(s in out)) out[s] = null;
  return out;
}

const key = s => new Request("https://kairo-kurse.cache/" + s);
const pack = m => ({ c: m.regularMarketPrice, pc: m.chartPreviousClose ?? m.previousClose ?? null, h: m.regularMarketDayHigh ?? null,
                     l: m.regularMarketDayLow ?? null, t: (m.regularMarketTime || 0) * 1000, cur: m.currency || null });

function json(obj, cors) {
  return new Response(JSON.stringify(obj), { headers: { ...cors, "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" } });
}
