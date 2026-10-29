// Prüft den Wecker und die SEC-Erkennung von site/kursdienst.js (Version 6) ohne Netz: GitHub, SEC und KV nachgebildet.
const store = new Map();
globalThis.caches = { default: { match: async k => store.has(k.url) ? new Response(store.get(k.url)) : undefined, put: async (k, r) => store.set(k.url, await r.text()) } };
const kvm = new Map(), kv = { get: async k => kvm.get(k) ?? null, put: async (k, v) => { kvm.set(k, v); } };
const calls = [];
let secFiled = false, exact = false, secCalls = 0;
globalThis.fetch = async (u, o = {}) => {
  u = String(u);
  if (u.includes("/dispatches")) { calls.push(JSON.parse(o.body)); return new Response(null, { status: 204 }); }
  if (u.includes("earn_watch.json")) return new Response(JSON.stringify({ items: [{ t: "AAPL", n: "Apple", cik: 320193, date: "2026-10-29", ts: "2026-10-29T20:30:00+00:00", exact }] }));
  if (u.includes("data.sec.gov")) secCalls++;
  if (u.includes("data.sec.gov")) return new Response(JSON.stringify({ filings: { recent: secFiled
    ? { form: ["8-K", "4"], items: ["2.02,9.01", ""], acceptanceDateTime: ["2026-10-29T20:31:05.000Z", "2026-10-20T10:00:00.000Z"], accessionNumber: ["0000320193-26-000101", "x"], primaryDocument: ["a8-k.htm", ""] }
    : { form: ["4"], items: [""], acceptanceDateTime: ["2026-10-20T10:00:00.000Z"], accessionNumber: ["x"], primaryDocument: [""] } } }));
  throw new Error("unerwartet " + u);
};
const w = (await import("../site/kursdienst.js")).default;
const env = { GH_TOKEN: "x", KAIRO: kv };
const run = async iso => { calls.length = 0; let p; await w.scheduled({ scheduledTime: Date.parse(iso) }, env, { waitUntil: x => { p = x; } }); return p ? await p : null; };
const fails = [];
const check = (name, cond, info) => { console.log((cond ? "OK   " : "FEHLER ") + name, info ? JSON.stringify(info) : ""); if (!cond) fails.push(name); };

// Abend-Scan 22:30 Berlin (21:30 UTC) – jede Minute geweckt, nur EIN Start
let scans = 0; for (let m = 30; m < 46; m++) { await run(`2026-10-29T21:${m}:00Z`); scans += calls.filter(c => !c.inputs).length; }
const st = JSON.parse(kvm.get("wake"));
check("Scan einmal am Tag (+ Quartalszahlen alle 10 Min. → 1 + 2)", st.scan === "2026-10-29" && scans === 3, { st, scans });
// Quartalszahlen-Prüfung höchstens alle 10 Min.
kvm.clear(); store.clear();
let earn = 0; for (let m = 0; m < 30; m++) { await run(`2026-10-29T20:${String(m).padStart(2, "0")}:00Z`); earn += calls.length; }
check("earnings.yml alle 10 Min. (21:00–21:29 Berlin → 3)", earn === 3, { earn });
// SEC: vor der Meldung nichts, danach sofort mit Ticker, dann alle 3 Min. nachladen
kvm.clear(); store.clear();
await run("2026-10-29T20:31:00Z");
check("vor der SEC-Meldung kein Sofort-Start", !calls.some(c => c.inputs), calls);
secFiled = true;
await run("2026-10-29T20:32:00Z");
check("SEC-Meldung → earnings.yml mit sec=AAPL", calls.some(c => c.inputs && c.inputs.sec === "AAPL"), calls);
await run("2026-10-29T20:33:00Z");
check("gleiche Meldung nicht doppelt", !calls.some(c => c.inputs), calls);
let follow = 0; for (let m = 33; m < 45; m++) { await run(`2026-10-29T20:${m}:00Z`); follow += calls.length; }
check("danach alle 3 Min. nachladen (20:33–20:44 → 4)", follow === 4, { follow });
// gelernte Meldezeit: enges Fenster (ab 20 Min. vorher statt 3 h)
kvm.clear(); store.clear(); secFiled = false; exact = true; secCalls = 0;
await run("2026-10-29T20:00:00Z");
check("gelernte Zeit 20:30: um 20:00 noch keine SEC-Abfrage", secCalls === 0, { secCalls });
await run("2026-10-29T20:12:00Z");
check("ab 20:10 wird geprüft", secCalls === 1, { secCalls });
exact = false; secFiled = true; kvm.clear(); store.clear();
await run("2026-10-29T20:32:00Z");
const r = await (await w.fetch(new Request("https://x.workers.dev/earn", { headers: { Origin: "https://dxrtex.github.io" } }), env, { waitUntil: () => {} })).json();
check("/earn liefert die Meldung", r.hits.length === 1 && r.hits[0].t === "AAPL" && r.hits[0].url.includes("000032019326000101"), r);
process.exit(fails.length ? 1 : 0);
