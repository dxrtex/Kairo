// Turbo-Rechner: viele Fälle mit bekannter Lösung (Währungen, Bezugsverhältnisse, Mini-Futures, Tippfehler, onvista-Laden).
//   node tools/turbo_unit.mjs      → Exit 1 bei Fehlern
import { sandbox, parse } from "./turbo_lib.mjs";

const FX = { EUR: 1, USD: 1 / 1.1207, HKD: 0.11, GBP: 1.15, GBp: 0.0115, CHF: 1.07, JPY: 0.006, DKK: 0.134 };
let fails = 0, n = 0;
const ok = (cond, name, info = "") => { n++; if (!cond) { fails++; console.log(`✗ ${name} ${info}`); } };
const near = (a, b, tol = 0.006) => a != null && b != null && Math.abs(a - b) <= tol;
// Anzeige: unter 1 € drei, sonst zwei Nachkommastellen
const shown = v => +v.toFixed(v < 1 ? 3 : 2);

function card(sc, t, m) {
  const sb = sandbox({ fx: FX });
  sb.state.tpT.X = t;
  const mm = { fx: FX[sc], riskEur: 30, atr: m.E * 0.02, ...m };
  return parse(sb.tpTurboHtml({ t: "X", cur: sc, n: "Test" }, mm, {}));
}
// unabhängige Rechnung: (Stop in K.-o.-Währung − Basispreis) × BV ÷ (K.-o.-Währung je €)
function expect({ sc, kc, stop, bp, cr, f }) {
  const fk = kc === "EUR" ? 1 : (f || 1 / FX[kc]);
  const stopK = kc === sc ? stop : stop * FX[sc] * fk;
  return (stopK - bp) * cr / fk;
}

// ---------- 1. Rechnung mit allen Feldern ----------
const cases = [
  // Name, Aktienwährung, Turbo-Felder, Plan (E, stop)
  ["Axon USD, Wechselkurs von HSBC", "USD", { p: 0.28, kon: 382.0278, kc: "USD", cr: 0.01, fxr: 1.1207 }, { E: 406.64, stop: 395 }],
  ["Axon USD, Wechselkurs leer (Kairo)", "USD", { p: 0.28, kon: 382.0278, kc: "USD", cr: 0.01 }, { E: 406.64, stop: 395 }],
  ["BYD HKD-Aktie, K.-o. in EUR", "HKD", { p: 2.42, kon: 7.6197, kc: "EUR", cr: 3 }, { E: 8.40 / 0.11, stop: 8.08 / 0.11 }],
  ["BYD HKD-Aktie, K.-o. in HKD", "HKD", { p: 0.75, kon: 68.5, kc: "HKD", cr: 0.1, fxr: 9.09 }, { E: 76.4, stop: 73.4 }],
  ["SAP EUR, BV 0,1", "EUR", { p: 2.35, kon: 210.5, kc: "EUR", cr: 0.1 }, { E: 233.9, stop: 225.2 }],
  ["Siemens EUR, BV 1", "EUR", { p: 21.1, kon: 180, kc: "EUR", cr: 1 }, { E: 201, stop: 193.5 }],
  ["Nestlé CHF", "CHF", { p: 0.82, kon: 76.2, kc: "CHF", cr: 0.1, fxr: 0.935 }, { E: 83.9, stop: 81.0 }],
  ["Shell GBp-Aktie, K.-o. in GBP", "GBp", { p: 2.6, kon: 23.1, kc: "GBP", cr: 1, fxr: 0.87 }, { E: 2560, stop: 2480 }],
  ["Shell GBp-Aktie, K.-o. in Pence", "GBp", { p: 2.6, kon: 2310, kc: "GBp", cr: 0.01, fxr: 87 }, { E: 2560, stop: 2480 }],
  ["Toyota JPY", "JPY", { p: 1.9, kon: 2650, kc: "JPY", cr: 0.01, fxr: 166.5 }, { E: 2960, stop: 2880 }],
  ["Novo DKK, K.-o. in EUR", "DKK", { p: 0.95, kon: 52.0, kc: "EUR", cr: 0.1 }, { E: 445, stop: 430 }],
  ["Nvidia USD, BV 0,1", "USD", { p: 3.1, kon: 152.0, kc: "USD", cr: 0.1, fxr: 1.12 }, { E: 186.7, stop: 179.9 }],
  ["sehr billiger Turbo (0,03 €)", "USD", { p: 0.031, kon: 95.0, kc: "USD", cr: 0.01, fxr: 1.12 }, { E: 98.3, stop: 97.1 }],
];
for (const [name, sc, t, m] of cases) {
  const r = card(sc, t, m);
  const e = expect({ sc, kc: t.kc, stop: m.stop, bp: t.kon, cr: t.cr, f: t.fxr });
  ok(near(r.sl, shown(e)), name, `SL ${r.sl} statt ${e.toFixed(4)} | ${r.calc}`);
  ok(r.calc && !r.red && !r.rough, name + " – Rechenweg/keine Warnung", r.txt.slice(0, 300));
  const lossU = t.p - r.sl, q = Math.floor(30 / Math.max(t.p - e, t.p * 0.05));
  ok(Math.abs(r.qty - q) <= 1, name + " – Stückzahl", `${r.qty} statt ${q}`);
  ok(r.qty * Math.max(lossU, 0) <= 30.5, name + " – Risiko ≤ 30 €", `${r.qty} × ${lossU}`);
}

// ---------- 1b. Stop-Loss im Chart (Aktienkurs für TradingView) ----------
{
  const r = card("USD", { p: 0.28, kon: 382.0278, kc: "USD", cr: 0.01, fxr: 1.1207 }, { E: 406.64, stop: 395 });
  ok(/^395,00 USD \| = 352,46 € · .*K\.-o\. liegt bei 382,03 USD/.test(r.chartSl || ""), "Chart-Stop Axon in USD + €", r.chartSl);
  const b = card("HKD", { p: 2.54, kon: 7.6197, kc: "EUR", cr: 3 }, { E: 8.30 / 0.11, stop: 8.0864 / 0.11 });
  ok(/^73,51 HKD \| = 8,086 € · .*K\.-o\. liegt bei 69,27 HKD \(7,620 €\)/.test(b.chartSl || ""), "Chart-Stop BYD in HKD + €", b.chartSl);
  const e = card("EUR", { p: 2.35, kon: 210.5, kc: "EUR", cr: 0.1 }, { E: 233.9, stop: 225.2 });
  ok(/^225,20 € \| diese Linie/.test(e.chartSl || ""), "Chart-Stop SAP nur in €", e.chartSl);
  const g = card("GBp", { p: 2.6, kon: 23.1, kc: "GBP", cr: 1, fxr: 0.87 }, { E: 2560, stop: 2480 });
  ok(/^2\.480,00 Pence/.test(g.chartSl || ""), "Chart-Stop London in Pence", g.chartSl);
}

// ---------- 2. Mini-Future: Basispreis unter dem K.-o. ----------
{
  const r = card("USD", { p: 3.0, kon: 160, bpn: 152, kc: "USD", cr: 0.1, fxr: 1.12 }, { E: 186.7, stop: 178 });
  ok(near(r.sl, (178 - 152) * 0.1 / 1.12), "Mini-Future: Wert über Basispreis", `SL ${r.sl}`);
}
// Basispreis über K.-o. (unplausibel) → K.-o. verwenden
{
  const r = card("USD", { p: 3.0, kon: 152, bpn: 160, kc: "USD", cr: 0.1, fxr: 1.12 }, { E: 186.7, stop: 178 });
  ok(near(r.sl, (178 - 152) * 0.1 / 1.12), "Basispreis > K.-o. wird ignoriert", `SL ${r.sl}`);
}

// ---------- 3. Fehler und Warnungen ----------
{ const r = card("USD", { p: 0.28 }, { E: 406, stop: 395 }); ok(r.prompt && r.sl == null, "nur Briefkurs → Aufforderung"); }
{ const r = card("USD", { kon: 382, kc: "USD", cr: 0.01 }, { E: 406, stop: 395 }); ok(r.prompt && r.sl == null, "ohne Briefkurs → Aufforderung"); }
{ const r = card("USD", { p: 0.28, kon: 399, kc: "USD", cr: 0.01 }, { E: 406, stop: 395 }); ok(r.red && r.sl == null, "K.-o. über Stop → rot"); }
{ const r = card("USD", { p: 0.28, kon: 382.03, kc: "EUR", cr: 0.01 }, { E: 406, stop: 395 }); ok(r.red && r.sl == null, "USD-Schwelle als EUR getippt → rot (über Kurs)"); }
{ const r = card("USD", { p: 0.28, kon: 382.03, kc: "USD", cr: 0.1, fxr: 1.12 }, { E: 406.6, stop: 395 }); ok(r.odd, "BV 0,1 statt 0,01 → Warnung", r.txt.slice(0, 200)); }
{ const r = card("USD", { p: 0.28, kon: 382.03, kc: "USD", cr: 0.001, fxr: 1.12 }, { E: 406.6, stop: 395 }); ok(r.odd, "BV 0,001 statt 0,01 → Warnung"); }
{ const r = card("USD", { p: 0.28, kon: 382.03, kc: "USD", cr: 0.01, fxr: 1.12 }, { E: 406.6, stop: 395 }); ok(!r.odd, "richtige Werte → keine Warnung"); }
{ const r = card("USD", { p: 0.28, kon: 382.03, kc: "USD", cr: 0.01, fxr: 0.892 }, { E: 406.6, stop: 395 }); ok(r.fxWarn, "Wechselkurs verkehrt herum (USD/EUR) → Warnung", r.txt.slice(0, 300)); }
{ const r = card("USD", { p: 0.28, kon: 382.03, kc: "USD", cr: 0.01, fxr: 1.1207 }, { E: 406.6, stop: 395 }); ok(!r.fxWarn, "richtiger Wechselkurs → keine Warnung"); }
{ const r = card("USD", { p: 0.28, kon: 392.0, kc: "USD", cr: 0.01, fxr: 1.12 }, { E: 406.6, stop: 395, atr: 8 }); ok(r.near && r.sl > 0, "K.-o. < 1 ATR unter Stop → gelb"); }
{ const r = card("USD", { p: 0.28, kon: 382.03, kc: "USD" }, { E: 406.64, stop: 395 }); ok(r.rough && near(r.sl, 0.28 * (395 - 382.03) / (406.64 - 382.03)), "ohne BV → Verhältnisrechnung + Hinweis", r.sl); }
{ const r = card("USD", { p: 0.28, ko: 340.88 }, { E: 406.64, stop: 395 }); ok(r.rough && near(r.sl, 0.28 * (395 - 382.03) / (406.64 - 382.03), 0.01), "alte Speicherung (K.-o. in €) bleibt nutzbar", r.sl); }
{
  const sb = sandbox({ fx: { EUR: 1 } });           // Wechselkurs unbekannt und nicht eingetragen
  sb.state.tpT.X = { p: 1, kon: 100, kc: "SEK", cr: 0.1 };
  const r = parse(sb.tpTurboHtml({ t: "X", cur: "SEK" }, { fx: 0.088, E: 1200, stop: 1150, atr: 20, riskEur: 30 }, {}));
  ok(r.fxMissing && r.sl == null, "fehlender Wechselkurs → rot statt falscher Zahl", r.txt.slice(0, 200));
}
// Take-Profit gleiche Formel
{
  const r = card("USD", { p: 0.28, kon: 382.0278, kc: "USD", cr: 0.01, fxr: 1.1207 }, { E: 406.64, stop: 395, tp: 440 });
  ok(near(r.tp, (440 - 382.0278) * 0.01 / 1.1207), "Take-Profit", r.tp);
}

// ---------- 4. Laden per WKN (onvista-Antworten nachgebaut) ----------
const snap = ({ ko, strike = ko, cr, ucur, spot, bid, ask, put = false, hit = false, name = "Axon Enterprise", sub = "KNOCKOUT_CERTIFICATE" }) => ({
  quote: { ask, bid, last: bid, datetimeAsk: "2026-10-15T10:38:14.460+00:00" },
  instrument: { name: `OPEN END-TURBO AUF ${name.toUpperCase()}`, entitySubType: sub },
  derivativesDetails: { description: [{ value: `Dieser Open-End Knock-Out Optionsschein (${put ? "Put" : "Call"}) bezieht sich auf ${name}` }] },
  derivativesFigure: { priceUnderlying: spot, isoCurrencyUnderlying: ucur, bidPriceCalculation: bid, askPriceCalculation: ask },
  derivativesUnderlyingList: { list: [{ instrument: { name }, isoCurrency: ucur, coverRatio: cr,
    derivativesBarrierList: { list: [{ typeBarrier: "KNOCK_OUT", barrier: ko, hasBeenHit: hit }, { typeBarrier: "STRIKE", barrier: strike }] } }] },
});
async function load(wkn, snapshot, row, { entityType = "DERIVATIVE", found = true, net = true } = {}) {
  const fetchImpl = async url => {
    if (!net) throw new Error("offline");
    const body = url.includes("/instruments/query") ? { list: found ? [{ entityType, entityValue: "1", name: "X", isin: "DE000X" }] : [] }
      : url.includes("/derivatives/1/snapshot") ? snapshot : { quote: snapshot ? snapshot.quote : {}, instrument: { name: "X" } };
    return { ok: true, json: async () => body };
  };
  const sb = sandbox({ fx: FX, rows: { X: row }, fetchImpl });
  await sb.turboLoad("X", wkn);
  return sb.state.tpT.X;
}
{
  const t = await load("HM5PPW", snap({ ko: 382.0278, cr: 0.01, ucur: "USD", spot: 408.42, bid: 0.26, ask: 0.28 }), { n: "Axon Enterprise", cur: "USD" });
  ok(t.kon === 382.0278 && t.kc === "USD" && t.cr === 0.01 && t.p === 0.28 && !t.src.warn, "Laden Axon: K.-o. USD, BV, Brief", JSON.stringify(t));
  const sb = sandbox({ fx: FX }); sb.state.tpT.X = t;
  const r = parse(sb.tpTurboHtml({ t: "X", cur: "USD" }, { fx: FX.USD, E: 406.64, stop: 395, atr: 8, riskEur: 30 }, {}));
  ok(near(r.sl, (395 - 382.0278) * 0.01 * FX.USD), "Laden Axon → SL", r.sl);
}
{
  const t = await load("TT7GC0", snap({ ko: 7.6197, cr: 3, ucur: "EUR", spot: 8.29, bid: 2.33, ask: 2.42, name: "BYD" }), { n: "BYD Company", cur: "HKD" });
  ok(t.kon === 7.6197 && t.kc === "EUR" && t.cr === 3, "Laden BYD: K.-o. EUR für HKD-Aktie", JSON.stringify(t));
  const sb = sandbox({ fx: FX }); sb.state.tpT.X = t;
  const r = parse(sb.tpTurboHtml({ t: "X", cur: "HKD" }, { fx: FX.HKD, E: 8.40 / 0.11, stop: 8.08 / 0.11, atr: 2, riskEur: 30 }, {}));
  ok(near(r.sl, 1.38), "Laden BYD → SL 1,38 €", r.sl);
}
{
  const t = await load("MINI01", snap({ ko: 160, strike: 152, cr: 0.1, ucur: "USD", spot: 186.7, bid: 3.10, ask: 3.12, name: "Nvidia", sub: "MINI_FUTURE" }), { n: "Nvidia", cur: "USD" });
  ok(t.kon === 160 && t.bpn === 152, "Laden Mini-Future: K.-o. und Basispreis getrennt", JSON.stringify(t));
}
{ const t = await load("PUT001", snap({ ko: 450, cr: 0.01, ucur: "USD", spot: 408, bid: 0.4, ask: 0.42, put: true }), { n: "Axon Enterprise", cur: "USD" }); ok(/Short\/Put/.test(t.src.warn), "Laden Put → Warnung", t.src.warn); }
{ const t = await load("HIT001", snap({ ko: 382, cr: 0.01, ucur: "USD", spot: 370, bid: 0.001, ask: 0.002, hit: true }), { n: "Axon Enterprise", cur: "USD" }); ok(/ausgeknockt|schon erreicht/.test(t.src.warn), "Laden ausgeknockt → Warnung", t.src.warn); }
{ const t = await load("HM5PPW", snap({ ko: 382, cr: 0.01, ucur: "USD", spot: 408, bid: 0.26, ask: 0.28 }), { n: "BYD Company", cur: "HKD" }); ok(/passt nicht/.test(t.src.warn), "Laden: falscher Basiswert → Warnung", t.src.warn); }
{ const t = await load("716460", null, { n: "SAP", cur: "EUR" }, { entityType: "STOCK" }); ok(/Aktie, kein Turbo/.test(t.src.warn || ""), "Laden Aktie statt Turbo → Warnung", JSON.stringify(t.src)); }
{ const t = await load("XXXXXX", null, { n: "SAP", cur: "EUR" }, { found: false }); ok(/nicht gefunden/.test(t.src.err || ""), "Laden unbekannte WKN → Hinweis"); }
{ const t = await load("HM5PPW", null, { n: "Axon", cur: "USD" }, { net: false }); ok(/nicht erreichbar/.test(t.src.err || ""), "Laden offline → Hinweis"); }
{ const t = await load("AB", null, { n: "Axon", cur: "USD" }); ok(/WKN \(6 Zeichen\)/.test(t.src.err || ""), "Laden Tippfehler WKN → Hinweis"); }
{
  // veralteter Basiswertkurs bei onvista: BV bleibt (Abweichung < 50 %), kein Aufschlag
  const t = await load("TT7GC0", snap({ ko: 7.6197, cr: 3, ucur: "EUR", spot: 8.29, bid: 2.33, ask: 2.42, name: "BYD" }), { n: "BYD", cur: "HKD" });
  ok(t.cr === 3 && !t.off, "veralteter onvista-Kurs: BV übernommen, kein Aufgeld");
  // BV passt gar nicht (Datenfehler) → nicht übernehmen
  const t2 = await load("TT7GC0", snap({ ko: 7.6197, cr: 30, ucur: "EUR", spot: 8.29, bid: 2.33, ask: 2.42, name: "BYD" }), { n: "BYD", cur: "HKD" });
  ok(!t2.cr && /Bezugsverhältnis bitte/.test(JSON.stringify(t2.src)) === false, "unplausibles BV wird nicht übernommen", JSON.stringify(t2));
}
{
  const t = await load("GBTEST", snap({ ko: 23.1, cr: 1, ucur: "GBP", spot: 25.6, bid: 2.4, ask: 2.42, name: "Shell" }), { n: "Shell", cur: "GBp" });
  ok(t.kc === "GBP" && t.kon === 23.1, "Laden Pence-Aktie: K.-o. bleibt in GBP", JSON.stringify(t));
}

{
  // Index in Punkten („$$$“ bei onvista) → wie Euro
  const t = await load("MR9XYL", snap({ ko: 1300, cr: 0.01, ucur: "$$$", spot: 1335, bid: 0.34, ask: 0.35, name: "STOXX Europe 600 Chemicals" }), { n: "STOXX Europe 600 Chemicals", cur: "EUR" });
  ok(t.kc === "EUR" && t.kon === 1300 && t.cr === 0.01, "Laden Index-Turbo (Punkte) → EUR", JSON.stringify(t));
  const sb = sandbox({ fx: FX }); sb.state.tpT.X = t;
  const r = parse(sb.tpTurboHtml({ t: "X", cur: "EUR" }, { fx: 1, E: 1335, stop: 1320, atr: 10, riskEur: 30 }, {}));
  ok(near(r.sl, 0.2), "Index-Turbo → SL (1320 − 1300) × 0,01", r.sl);
}
console.log(`${n - fails}/${n} Prüfungen bestanden`);
process.exit(fails ? 1 : 0);
