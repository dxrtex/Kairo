// Prüft site/kursdienst.js gegen echte Yahoo-Kurse (Cloudflare-Cache nachgebildet) – mit Diagnose der Rohantworten.
const UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15";
for (const u of ["https://query1.finance.yahoo.com/v8/finance/chart/SAP.DE?interval=1m&range=1d",
                 "https://query2.finance.yahoo.com/v8/finance/chart/SAP.DE?interval=1m&range=1d",
                 "https://query1.finance.yahoo.com/v8/finance/chart/SAP.DE?interval=1d&range=5d",
                 "https://query1.finance.yahoo.com/v7/finance/spark?symbols=SAP.DE&range=1d&interval=5m"]) {
  for (const h of [{ "User-Agent": UA }, { "User-Agent": UA, "Accept": "application/json", "Accept-Language": "de-DE,de;q=0.9" }, {}]) {
    try { const r = await fetch(u, { headers: h }); const t = await r.text(); console.log(r.status, Object.keys(h).length, u.slice(8, 70), t.slice(0, 140).replace(/\s+/g, " ")); }
    catch (e) { console.log("ERR", u, String(e).slice(0, 100)); }
  }
}
const store = new Map();
globalThis.caches = { default: { match: async k => store.has(k.url) ? new Response(store.get(k.url)) : undefined, put: async (k, r) => store.set(k.url, await r.text()) } };
const w = (await import("../site/kursdienst.js")).default;
const r = await w.fetch(new Request("https://x.workers.dev/?s=SAP.DE,AAPL,7203.T,NESN.SW,RHM.DE", { headers: { Origin: "https://dxrtex.github.io" } }), {}, { waitUntil: p => p });
const j = await r.json(); console.log(JSON.stringify(j));
const ok = Object.values(j).filter(q => q && q.c > 0).length; console.log("Kurse:", ok, "von", Object.keys(j).length);
process.exit(ok >= 4 ? 0 : 1);
