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
    if (!syms.length) return json({ ok: true, info: "Kairo-Kursdienst läuft (Version 2). Abruf: ?s=SAP.DE,AAPL" }, cors);
    const diag = url.searchParams.has("debug") ? [] : null;
    const out = await quotes(syms, ctx, diag);
    return json(diag ? { ...out, _diag: diag } : out, cors);
  },
};

// Quellen nacheinander, bis jede Aktie einen Kurs hat:
// 1) Yahoo Sammelabruf (spark) · 2) Yahoo einzeln (chart) – beide ohne Browser-Kennung (sonst 429)
// 3) Yahoo mit Anmelde-Cookie + Crumb (quote) – wie yfinance, mit Browser-Kennung
async function quotes(syms, ctx, diag) {
  const cache = caches.default, out = {}, miss = [];
  const log = (src, st) => { if (diag) diag.push(`${src}: ${st}`); };
  await Promise.all(syms.map(async s => { const hit = diag ? null : await cache.match(key(s)); if (hit) out[s] = await hit.json(); else miss.push(s); }));
  const todo = () => miss.filter(s => !out[s]);
  if (miss.length) {
    for (const host of ["query1", "query2"]) {                                 // 1) spark
      if (!todo().length) break;
      try {
        const r = await fetch(`https://${host}.finance.yahoo.com/v7/finance/spark?symbols=${todo().map(encodeURIComponent).join(",")}&range=1d&interval=5m`);
        log("spark " + host, r.status);
        if (!r.ok) continue;
        for (const x of ((await r.json()).spark || {}).result || []) {
          const meta = x && x.response && x.response[0] && x.response[0].meta;
          if (meta && meta.regularMarketPrice > 0) out[String(x.symbol).toUpperCase()] = pack(meta);
        }
      } catch (e) { log("spark " + host, "Fehler " + e); }
    }
    for (const s of todo()) {                                                 // 2) chart
      for (const host of ["query1", "query2"]) {
        try {
          const r = await fetch(`https://${host}.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(s)}?interval=1d&range=5d`);
          log("chart " + host, r.status);
          if (!r.ok) continue;
          const meta = ((((await r.json()).chart || {}).result || [])[0] || {}).meta;
          if (meta && meta.regularMarketPrice > 0) { out[s] = pack(meta); break; }
        } catch (e) { log("chart " + host, "Fehler " + e); }
      }
    }
    if (todo().length) await crumbQuotes(todo(), out, log);                   // 3) quote mit Cookie + Crumb
    for (const s of miss) if (out[s]) ctx.waitUntil(cache.put(key(s), new Response(JSON.stringify(out[s]), { headers: { "Cache-Control": "max-age=20" } })));
  }
  for (const s of syms) if (!(s in out)) out[s] = null;
  return out;
}

async function crumbQuotes(syms, out, log) {
  try {
    const UA = { "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15" };
    const c = await fetch("https://fc.yahoo.com/", { redirect: "manual", headers: UA });
    const cookie = (c.headers.get("set-cookie") || "").split(";")[0];
    log("cookie", cookie ? "ok" : "keins (" + c.status + ")");
    if (!cookie) return;
    const cr = await fetch("https://query1.finance.yahoo.com/v1/test/getcrumb", { headers: { ...UA, cookie } });
    const crumb = cr.ok ? (await cr.text()).trim() : "";
    log("crumb", cr.status);
    if (!crumb) return;
    const r = await fetch(`https://query1.finance.yahoo.com/v7/finance/quote?symbols=${syms.map(encodeURIComponent).join(",")}&crumb=${encodeURIComponent(crumb)}`, { headers: { ...UA, cookie } });
    log("quote", r.status);
    if (!r.ok) return;
    for (const q of ((await r.json()).quoteResponse || {}).result || []) {
      if (q.regularMarketPrice > 0) out[String(q.symbol).toUpperCase()] = { c: q.regularMarketPrice, pc: q.regularMarketPreviousClose ?? null,
        h: q.regularMarketDayHigh ?? null, l: q.regularMarketDayLow ?? null, t: (q.regularMarketTime || 0) * 1000, cur: q.currency || null };
    }
  } catch (e) { log("quote", "Fehler " + e); }
}

const key = s => new Request("https://kairo-kurse.cache/" + s);
const pack = m => ({ c: m.regularMarketPrice, pc: m.chartPreviousClose ?? m.previousClose ?? null, h: m.regularMarketDayHigh ?? null,
                     l: m.regularMarketDayLow ?? null, t: (m.regularMarketTime || 0) * 1000, cur: m.currency || null });

function json(obj, cors) {
  return new Response(JSON.stringify(obj), { headers: { ...cors, "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" } });
}
