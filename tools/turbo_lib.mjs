// Lädt den echten Turbo-Code aus site/index.html (onvista-Laden + Stop-Loss-Rechnung) in eine Sandbox – für Tests ohne Browser.
import { readFileSync } from "node:fs";
import vm from "node:vm";

const HTML = readFileSync(new URL("../site/index.html", import.meta.url), "utf8");
const cut = (from, to) => {
  const a = HTML.indexOf(from), b = HTML.indexOf(to, a);
  if (a < 0 || b < 0) throw new Error(`Abschnitt nicht gefunden: ${from}`);
  return HTML.slice(a, b);
};
const line = start => { const a = HTML.indexOf(start); return HTML.slice(a, HTML.indexOf("\n", a)); };

const CODE = [
  line("const nf = "), line("const fmt = "), line("const pct = "), line("const esc = "),
  line("const sgnPct = "), line("const eur = "), line("const eur2 = "),
  cut("const OV = ", 'document.addEventListener("click", e => { const b = e.target.closest("[data-tpload]")'),
  cut("const tpKcOpts = ", "function tpHtml(r, S)"),
  "this.turboLoad = turboLoad; this.tpTurboHtml = tpTurboHtml; this.ovTurbo = ovTurbo;",
].join("\n");

export function sandbox({ fx = { EUR: 1 }, rows = {}, fetchImpl = globalThis.fetch } = {}) {
  const ctx = {
    state: { tpT: {} }, save() {}, tpRefresh() {}, fetch: fetchImpl, console, Intl, Math, JSON, Date, Number, String, Set, Object, isNaN,
    TP: { kob: 1.0 }, rowOf: t => rows[t] || null,
  };
  ctx.fxEur = fx;
  ctx.toEur = (v, cur) => v == null ? null : v * (ctx.fxEur[cur] ?? (cur === "EUR" ? 1 : NaN));
  vm.createContext(ctx);
  vm.runInContext(CODE, ctx);
  return ctx;
}

// Zahlen aus dem HTML der Turbo-Karte lesen
const num = s => s == null ? null : +s.replace(/\./g, "").replace(",", ".").replace("−", "-");
export function parse(html) {
  const txt = html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");
  const g = re => { const m = html.match(re); return m ? num(m[1]) : null; };
  return {
    sl: g(/Stop-Loss am Turbo<\/span><b class="down">([\d.,]+) €/),
    tp: g(/Take-Profit am Turbo<\/span><b class="up">([\d.,]+) €/),
    qty: g(/<b>([\d.]+) Stück<\/b>/),
    lev: g(/Hebel ≈ ×([\d.,]+)/),
    calc: (txt.match(/Rechnung: ([^·]*?€)/) || [])[1] || null,
    red: /tone-red/.test(html), odd: /passt nicht zum Aktienkurs/.test(html), near: /weniger als 1 ATR/.test(html),
    rough: /Ohne Bezugsverhältnis/.test(html), prompt: /Trag Briefkurs und K\.-o\.-Schwelle ein/.test(html), fxMissing: /Wechselkurs EUR\/\S+ fehlt/.test(html), fxWarn: /verkehrt herum/.test(html),
    txt,
  };
}
