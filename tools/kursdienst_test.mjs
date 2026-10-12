// Prüft site/kursdienst.js gegen echte Yahoo-Kurse (Cloudflare-Cache nachgebildet) – mit Diagnose der Rohantworten.
const store = new Map();
globalThis.caches = { default: { match: async k => store.has(k.url) ? new Response(store.get(k.url)) : undefined, put: async (k, r) => store.set(k.url, await r.text()) } };
const w = (await import("../site/kursdienst.js")).default;
const r = await w.fetch(new Request("https://x.workers.dev/?s=SAP.DE,AAPL,7203.T,NESN.SW,RHM.DE&debug=1", { headers: { Origin: "https://dxrtex.github.io" } }), {}, { waitUntil: p => p });
const j = await r.json(); console.log(JSON.stringify(j));
const ok = Object.values(j).filter(q => q && q.c > 0).length; console.log("Kurse:", ok, "von", Object.keys(j).length);

// Ausweichquellen einzeln prüfen (so, als wäre Yahoo gesperrt)
const real = globalThis.fetch;
globalThis.fetch = (u, o) => /spark|chart/.test(String(u)) ? Promise.resolve(new Response("", { status: 429 })) : real(u, o);
store.clear();
const r2 = await w.fetch(new Request("https://x.workers.dev/?s=SAP.DE,AAPL,7203.T&debug=1"), {}, { waitUntil: p => p });
console.log("ohne spark/chart:", JSON.stringify(await r2.json()));

globalThis.fetch = real;
const sr = await (await w.fetch(new Request("https://x.workers.dev/?q=Hensoldt"), {}, { waitUntil: p => p })).json();
console.log("Suche:", JSON.stringify(sr).slice(0, 300));
const cd = await (await w.fetch(new Request("https://x.workers.dev/?c=HAG.DE"), {}, { waitUntil: p => p })).json();
console.log("Kerzen:", cd.name, cd.cur, cd.exch, "n =", cd.c && cd.c.length, "letzter Schluss", cd.c && cd.c[cd.c.length - 1]);
process.exit(ok >= 4 && sr.quotes && sr.quotes.length && cd.c && cd.c.length > 200 ? 0 : 1);
