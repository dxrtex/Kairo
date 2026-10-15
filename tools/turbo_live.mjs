// Echte Turbos von onvista durch Kairos Code schicken und gegen onvistas eigene Zahlen prüfen.
//   node tools/turbo_live.mjs [WKN …]
// Prüft je Turbo: K.-o./Bezugsverhältnis/Währung geladen, innerer Wert nach Kairo ≈ onvistas innerer Wert (€),
// Stop-Loss am Turbo = unabhängig gerechnet, Warnungen (Put, ausgeknockt). Exit 1, wenn ein Long-Turbo falsch gerechnet wird.
import { sandbox, parse } from "./turbo_lib.mjs";

const OV = "https://api.onvista.de/api/v1";
const get = async u => { try { const r = await fetch(OV + u, { headers: { "User-Agent": "Mozilla/5.0" } }); return r.ok ? await r.json() : null; } catch (e) { return null; } };
const sleep = ms => new Promise(r => setTimeout(r, ms));

let fx = { EUR: 1 };
try { fx = (await (await fetch("https://dxrtex.github.io/Kairo/data/search.json")).json()).fx_eur || fx; } catch (e) { console.log("fx_eur nicht geladen", e.message); }
console.log("Wechselkurse:", Object.keys(fx).length);

// ---- Turbos finden ----
const seeds = process.argv.slice(2).length ? process.argv.slice(2) : ["HM5PPW", "TT7GC0"];
const NAMES = ["Apple", "Nvidia", "Microsoft", "Tesla", "Amazon", "Meta", "Alphabet", "Axon", "Palantir", "AMD", "Netflix", "Novo Nordisk",
  "SAP", "Siemens", "Allianz", "Rheinmetall", "Deutsche Bank", "Mercedes", "BYD", "Alibaba", "Tencent", "Nestle", "ASML", "LVMH",
  "Shell", "Toyota", "DAX", "Gold", "Bitcoin", "Infineon", "Airbus", "BASF", "Volkswagen", "Commerzbank", "Coinbase"];
const found = new Map();
const add = (it, via) => { if (it && it.entityType === "DERIVATIVE" && it.wkn && !found.has(it.wkn)) found.set(it.wkn, { ...it, via }); };
for (const w of seeds) { const q = await get(`/instruments/query?searchValue=${w}&limit=1`); add(((q || {}).list || [])[0], "Eingabe"); }
for (const w of seeds) {
  const it = found.get(w); if (!it) continue;
  const s = await get(`/derivatives/${it.entityValue}/snapshot`);
  const rel = (s && s.relatedInstrumentItemList) || {};
  const list = Array.isArray(rel) ? rel : rel.list || [];
  console.log(`verwandte Produkte bei ${w}: ${list.length}`, list.length ? JSON.stringify(list[0]).slice(0, 300) : JSON.stringify(rel).slice(0, 300));
  for (const x of list) add(x.instrument || x, "verwandt");
}
for (const nm of NAMES) {
  for (const term of [`${nm} Turbo`, `Turbo ${nm}`, `${nm} Knock-Out`, `${nm} Mini Future`]) {
    const q = await get(`/instruments/query?searchValue=${encodeURIComponent(term)}&limit=20`);
    const l = ((q || {}).list || []).filter(x => x.entityType === "DERIVATIVE");
    l.slice(0, 3).forEach(x => add(x, term));
    if (l.length) break;
    await sleep(150);
  }
}
// Listen von onvista-Webseiten (Knock-Out-/Mini-Future-Übersichten, Aktienseiten) – WKNs aus den Links
const PAGES = ["https://www.onvista.de/derivate/Knock-Outs", "https://www.onvista.de/derivate/Mini-Futures", "https://www.onvista.de/derivate",
  "https://www.onvista.de/aktien/AXON-ENTERPRISE-Aktie-US05464C1018", "https://www.onvista.de/aktien/Apple-Aktie-US0378331005",
  "https://www.onvista.de/aktien/NVIDIA-Aktie-US67066G1040", "https://www.onvista.de/aktien/SAP-Aktie-DE0007164600",
  "https://www.onvista.de/aktien/Rheinmetall-Aktie-DE0007030033", "https://www.onvista.de/aktien/Tesla-Aktie-US88160R1014",
  "https://www.onvista.de/aktien/Nestle-Aktie-CH0038863350", "https://www.onvista.de/aktien/Shell-Aktie-GB00BP6MXD84",
  "https://www.onvista.de/aktien/Toyota-Motor-Aktie-JP3633400001", "https://www.onvista.de/aktien/Novo-Nordisk-Aktie-DK0062498333",
  "https://www.onvista.de/index/DAX-Index-20735", "https://www.onvista.de/aktien/Alibaba-Group-Holding-Aktie-KYG017191142"];
for (const url of PAGES) {
  try {
    const h = await (await fetch(url, { headers: { "User-Agent": "Mozilla/5.0" } })).text();
    const w = [...new Set([...h.matchAll(/\/derivate\/(?:Knock-Outs|Mini-Futures|Turbos?)[^"'\s]*?\/\d+-([A-Z0-9]{6})-/g)].map(m => m[1]))];
    console.log(`${url.split("/").slice(-1)[0]}: ${w.length} WKNs`);
    for (const x of w.slice(0, 8)) { if (found.has(x)) continue; const q = await get(`/instruments/query?searchValue=${x}&limit=1`); add(((q || {}).list || [])[0], "Webseite"); await sleep(120); }
  } catch (e) { console.log(url, e.message); }
}
console.log(`gefunden: ${found.size} Derivate`);

// ---- jeden Turbo prüfen ----
let n = 0, bad = 0, skip = 0;
const rows = [];
for (const [wkn, it] of [...found].slice(0, 60)) {
  await sleep(250);
  const s = await get(`/derivatives/${it.entityValue}/snapshot`);
  const u = (((s || {}).derivativesUnderlyingList || {}).list || [])[0];
  const fig = (s || {}).derivativesFigure || {};
  const ucur = (u && u.isoCurrency) || fig.isoCurrencyUnderlying || "EUR";
  const name = (u && u.instrument && u.instrument.name) || it.name;
  const row = { n: name, cur: fx[ucur] != null ? ucur : "EUR" };      // Aktie in Kairo in der Währung des Basiswerts
  const sb = sandbox({ fx, rows: { X: row }, fetchImpl: (url, o) => fetch(url, { ...o, headers: { "User-Agent": "Mozilla/5.0" } }) });
  await sb.turboLoad("X", wkn);
  const t = sb.state.tpT.X || {}, src = t.src || {};
  const line = `${wkn.padEnd(7)} ${String(it.entitySubType || "").slice(0, 12).padEnd(12)} ${String(name).slice(0, 22).padEnd(22)} ${ucur}`;
  if (src.err) { rows.push(`${line}  Fehler: ${src.err}`); skip++; continue; }
  const put = /Put/.test(src.warn || ""), hit = /erreicht/.test(src.warn || "");
  const spot = +fig.priceUnderlying, cr = t.cr, ko = t.kon, bp = t.bpn && t.bpn <= ko ? t.bpn : ko;
  if (put || hit || !(spot > 0) || !(ko > 0)) { rows.push(`${line}  übersprungen (${put ? "Put/Short ✓ erkannt" : hit ? "ausgeknockt ✓ erkannt" : "keine Kursdaten"}) K.-o. ${ko} BV ${cr}`); skip++; continue; }
  n++;
  const sc = row.cur, mfx = sb.toEur(1, sc);
  const spotS = t.kc === sc ? spot : spot * sb.toEur(1, ucur) / mfx;   // Basiswert in Aktienwährung
  const koS = t.kc === sc ? ko : ko / (t.kc === "EUR" ? 1 : 1 / sb.toEur(1, t.kc)) / mfx;
  const stop = koS + 0.6 * (spotS - koS), E = spotS;
  const r = parse(sb.tpTurboHtml({ t: "X", cur: sc, n: name }, { fx: mfx, E, stop, atr: (spotS - koS) * 0.15, riskEur: 30 }, {}));
  const f = t.kc === "EUR" ? 1 : 1 / sb.toEur(1, t.kc), toK = v => t.kc === sc ? v : v * mfx * f;
  const exp = cr ? (toK(stop) - bp) * cr / f : null;
  const ivK = cr ? (toK(spotS) - bp) * cr / f : null, ivOv = +fig.intrinsicValue;
  const slOk = cr ? Math.abs(r.sl - +exp.toFixed(exp < 1 ? 3 : 2)) <= 0.006 : r.sl > 0;
  const ivOk = !cr || !(ivOv > 0) || Math.abs(ivK / ivOv - 1) < 0.04;              // gegen onvistas inneren Wert (anderer Devisenkurs → 4 %)
  const askOk = !cr || !(+t.p > 0) || Math.abs(+t.p / ivK - 1) < 0.5;
  const okAll = slOk && ivOk && !r.red;
  if (!okAll) bad++;
  rows.push(`${line}  ${okAll ? "✓" : "✗"} K.-o. ${ko} ${t.kc} BV ${cr ?? "–"}${t.bpn && t.bpn < ko ? ` BP ${t.bpn}` : ""} | Brief ${t.p} | SL ${r.sl} (soll ${exp != null ? exp.toFixed(3) : "grob"}) | innerer Wert Kairo ${ivK != null ? ivK.toFixed(3) : "–"} / onvista ${ivOv || "–"}${ivOk ? "" : " ✗"}${askOk ? "" : " · Brief passt nicht"} | Hebel ${r.lev}${r.red ? " · ROT" : ""}${r.odd ? " · Warnung passt-nicht" : ""}${r.rough ? " · ohne BV" : ""}`);
}
console.log(rows.join("\n"));
console.log(`\nLong-Turbos gerechnet: ${n}, davon falsch: ${bad}, übersprungen: ${skip}`);
process.exit(bad ? 1 : 0);
