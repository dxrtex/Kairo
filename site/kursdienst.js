// Kairo-Kursdienst (Version 5) – kleiner Cloudflare Worker (kostenlos) für die Kairo-App.
//   ?s=SAP.DE,AAPL      Kurse (Yahoo Finance, je nach Börse leicht verzögert)
//   ?q=Rheinmetall      Aktiensuche an allen Börsen
//   ?c=RHM.DE           Tageskerzen (1 Jahr) – damit plant Kairo auch Aktien außerhalb des Scans
//   /trades?key=…       offene Trades, Depot und Watchlist für Scan und Mitteilungen (GET lesen, POST speichern) – braucht den KV-Speicher „KAIRO“
// Einrichtung: Cloudflare → Workers & Pages → Worker → Edit code → alles ersetzen → Deploy (Anleitung in Kairo → Einstellungen).

const ALLOW = ["https://dxrtex.github.io"];          // nur die Kairo-App darf den Dienst im Browser nutzen
const MAX = 25;                                       // höchstens so viele Aktien je Abruf

// Version 5: pünktlicher Wecker (optional). GitHub startet geplante Läufe oft Stunden zu spät – Cloudflare nicht.
// Einrichtung: Settings → Variables and Secrets → Secret „GH_TOKEN“ (GitHub-Schlüssel mit Actions: Read and write),
// Settings → Triggers → Cron Triggers: „*/5 * * * *“ (alle 5 Minuten). Der Worker entscheidet selbst, was fällig ist.
const REPO = "dxrtex/Kairo";
async function dispatch(env, wf) {
  const r = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${wf}/dispatches`, {
    method: "POST", body: JSON.stringify({ ref: "main" }),
    headers: { Authorization: "Bearer " + env.GH_TOKEN, Accept: "application/vnd.github+json", "User-Agent": "kairo-kursdienst", "Content-Type": "application/json" } });
  return r.status;
}
function berlin(now) {
  const p = Object.fromEntries(new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/Berlin", weekday: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23" })
    .formatToParts(now).map(x => [x.type, x.value]));
  return { wd: p.weekday, hm: +p.hour * 100 + +p.minute };
}
async function wake(env, now = new Date()) {
  if (!env || !env.GH_TOKEN) return "kein GH_TOKEN";
  const { wd, hm } = berlin(now), work = !["Sat", "Sun"].includes(wd), done = [];
  // Abend-Scan: Mo–Fr um 22:30 Uhr Berlin (der Lauf prüft selbst, ob er schon online ist)
  if (work && hm >= 2230 && hm < 2235) done.push("scan " + await dispatch(env, "scan.yml"));
  // Quartalszahlen + Fed: alle 10 Min. in den Meldezeiten (06–09, 12–16, 19–01 Uhr Berlin)
  const win = (hm >= 600 && hm < 900) || (hm >= 1200 && hm < 1600) || hm >= 1900 || hm < 100;
  if ((work || (wd === "Sat" && hm < 100)) && win && now.getUTCMinutes() % 10 < 5) done.push("zahlen " + await dispatch(env, "earnings.yml"));
  // Fed-Tag: 18:55–20:30 Uhr Berlin alle 5 Min. (earnings.yml prüft selbst, ob heute ein Zinsentscheid ist)
  if (work && hm >= 1855 && hm < 2030 && now.getUTCMinutes() % 10 >= 5) done.push("fed " + await dispatch(env, "earnings.yml"));
  return done.join(", ") || "nichts fällig";
}

export default {
  async scheduled(event, env, ctx) { ctx.waitUntil(wake(env, new Date(event.scheduledTime))); },
  async fetch(request, env, ctx) {
    const origin = request.headers.get("Origin") || "";
    const cors = {
      "Access-Control-Allow-Origin": ALLOW.includes(origin) ? origin : ALLOW[0],
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
      "Vary": "Origin",
    };
    if (request.method === "OPTIONS") return new Response(null, { headers: cors });
    const url = new URL(request.url);
    if (url.pathname.replace(/\/+$/, "") === "/trades") return trades(request, env, url, cors);
    const q = (url.searchParams.get("q") || "").trim();
    if (q) return json(await search(q), cors);
    const c = (url.searchParams.get("c") || "").trim().toUpperCase();
    if (c && /^[A-Z0-9.\-^=]{1,20}$/.test(c)) return json(await candles(c), cors);
    const syms = (url.searchParams.get("s") || "").split(",").map(x => x.trim().toUpperCase())
      .filter(x => /^[A-Z0-9.\-^=]{1,20}$/.test(x)).slice(0, MAX);
    if (!syms.length) return json({ ok: true, info: "Kairo-Kursdienst läuft (Version 5). Abruf: ?s=SAP.DE,AAPL", kv: !!(env && env.KAIRO) }, cors);
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

// Aktiensuche (Yahoo): nur Aktien, mit Yahoo-Kürzel (z. B. RHM.DE), Börse und Name
async function search(q) {
  for (const host of ["query1", "query2"]) {
    try {
      const r = await fetch(`https://${host}.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(q)}&quotesCount=15&newsCount=0&listsCount=0`);
      if (!r.ok) continue;
      const l = ((await r.json()).quotes || []).filter(x => x.symbol && (x.quoteType === "EQUITY" || x.typeDisp === "Equity"));
      return { quotes: l.map(x => ({ symbol: x.symbol, name: x.longname || x.shortname || x.symbol, exch: x.exchDisp || x.exchange || "", sector: x.sectorDisp || x.sector || "" })) };
    } catch (e) { /* nächster Host */ }
  }
  return { quotes: [], error: "Suche gerade nicht erreichbar" };
}

// Tageskerzen eines Jahres (Yahoo) – nur vollständige Kerzen
async function candles(sym) {
  for (const host of ["query1", "query2"]) {
    try {
      const r = await fetch(`https://${host}.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(sym)}?interval=1d&range=1y`);
      if (!r.ok) continue;
      const res = (((await r.json()).chart || {}).result || [])[0];
      const qd = res && res.indicators && res.indicators.quote && res.indicators.quote[0];
      if (!qd || !res.timestamp) continue;
      const o = [], h = [], l = [], c = [], t = [];
      res.timestamp.forEach((ts, i) => { if ([qd.open[i], qd.high[i], qd.low[i], qd.close[i]].every(v => v != null && v > 0)) {
        o.push(qd.open[i]); h.push(qd.high[i]); l.push(qd.low[i]); c.push(qd.close[i]); t.push(ts * 1000); } });
      const m = res.meta || {};
      return { symbol: sym, name: m.longName || m.shortName || sym, cur: m.currency || null, exch: m.fullExchangeName || m.exchangeName || "", t, o, h, l, c };
    } catch (e) { /* nächster Host */ }
  }
  return { symbol: sym, error: "keine Kerzen" };
}

// Offene Trades für die Mitteilungen: die App speichert sie hier, die Prüfung auf GitHub liest sie.
// Schutz: Der erste Schlüssel, der speichert, gehört dem Dienst – andere Schlüssel werden abgelehnt.
async function trades(request, env, url, cors) {
  if (!env || !env.KAIRO) return json({ error: "KV-Speicher „KAIRO“ fehlt – in Cloudflare unter Settings → Bindings anlegen" }, cors, 501);
  const key = url.searchParams.get("key") || "";
  if (key.length < 16) return json({ error: "Schlüssel fehlt" }, cors, 401);
  const owner = await env.KAIRO.get("owner");
  if (owner && owner !== key) return json({ error: "falscher Schlüssel" }, cors, 403);
  if (request.method === "POST") {
    const body = await request.text();
    if (body.length > 50000) return json({ error: "zu groß" }, cors, 413);
    let data; try { data = JSON.parse(body); } catch (e) { return json({ error: "kein JSON" }, cors, 400); }
    if (!owner) await env.KAIRO.put("owner", key);
    const prev = JSON.parse((await env.KAIRO.get("trades")) || "{}");
    const w = Array.isArray(data.w) ? data.w.slice(0, 400) : prev.w;            // Watchlist (ab Version 4); fehlt sie, bleibt die alte
    await env.KAIRO.put("trades", JSON.stringify({ p: data.p || [], d: data.d || [], ...(w ? { w, wat: Array.isArray(data.w) ? Date.now() : prev.wat } : {}), at: Date.now() }));
    return json({ ok: true }, cors);
  }
  return json(JSON.parse((await env.KAIRO.get("trades")) || '{"p":[],"d":[]}'), cors);
}

const key = s => new Request("https://kairo-kurse.cache/" + s);
const pack = m => ({ c: m.regularMarketPrice, pc: m.chartPreviousClose ?? m.previousClose ?? null, h: m.regularMarketDayHigh ?? null,
                     l: m.regularMarketDayLow ?? null, t: (m.regularMarketTime || 0) * 1000, cur: m.currency || null });

function json(obj, cors, status = 200) {
  return new Response(JSON.stringify(obj), { status, headers: { ...cors, "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" } });
}
