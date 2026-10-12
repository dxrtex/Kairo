// Prüft site/kursdienst.js gegen echte Yahoo-Kurse (Cloudflare-Cache nachgebildet).
const store = new Map();
globalThis.caches = { default: { match: async k => store.has(k.url) ? new Response(store.get(k.url)) : undefined, put: async (k, r) => store.set(k.url, await r.text()) } };
const w = (await import("../site/kursdienst.js")).default;
const r = await w.fetch(new Request("https://x.workers.dev/?s=SAP.DE,AAPL,7203.T,NESN.SW,RHM.DE", { headers: { Origin: "https://dxrtex.github.io" } }), {}, { waitUntil: p => p });
const j = await r.json(); console.log(JSON.stringify(j));
const ok = Object.values(j).filter(q => q && q.c > 0).length; console.log("Kurse:", ok, "von", Object.keys(j).length);
process.exit(ok >= 4 ? 0 : 1);
