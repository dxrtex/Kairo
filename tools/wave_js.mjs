// Wellenstudie: ruft die ECHTE Chart-Wellenlogik (chartModel aus site/index.html) mit verschiedenen Grenzen für den
// „fast vollen Rücksetzer“ auf. Ändert nichts an der App. Eingabe (stdin, JSON): {t,o,h,l,c, samples:[{i,H,L}], thrs:[…]}
// Ausgabe (stdout, JSON): je Sample und Grenze [iL, iH] der klassischen Welle (absolute Indizes) oder null.
import { readFileSync } from "node:fs"; import vm from "node:vm";
const H = readFileSync(new URL("../site/index.html", import.meta.url), "utf8");
const a = H.indexOf("function chartModel("), b = H.indexOf("\n}\n", a) + 3, SRC = H.slice(a, b);
const KEY = "if ((M - c.l[cur]) / (M - c.l[j]) >= .786 && big(cur)) ws.push(cur);";
if (!SRC.includes(KEY)) throw new Error("Wellenregel nicht gefunden");
const inp = JSON.parse(readFileSync(0, "utf8")), N = 1000;
const fns = inp.thrs.map(thr => { const ctx = { dateDE: s => s, fmt: v => v, Math };
  vm.createContext(ctx); vm.runInContext(SRC.replace(KEY, KEY.replace(">= .786", ">= " + thr)) + "; this.f = chartModel;", ctx); return ctx.f; });
const out = inp.samples.map(s => { const lo = Math.max(0, s.i - N + 1), sl = k => inp[k].slice(lo, s.i + 1);
  const c = { t: sl("t"), o: sl("o"), h: sl("h"), l: sl("l"), c: sl("c") };
  const r = { zone: { fib: { L_date: s.L }, H_date: s.H } };
  return fns.map(f => { try { const m = f(c, r); return m.cls ? [m.cls.iL + lo, m.cls.iH + lo] : null; } catch { return null; } }); });
process.stdout.write(JSON.stringify(out));
