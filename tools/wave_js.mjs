// Wellenstudie: ruft die ECHTE Chart-Wellenlogik (chartModel aus site/index.html) mit verschiedenen Grenzen für den
// „fast vollen Rücksetzer“ auf. Ändert nichts an der App. Eingabe (stdin, JSON): {t,o,h,l,c, samples:[{i,H,L}], thrs:[…]}
// Ausgabe (stdout, JSON): je Sample und Grenze [iL, iH] der klassischen Welle (absolute Indizes) oder null.
import { readFileSync } from "node:fs"; import vm from "node:vm";
const H = readFileSync(new URL("../site/index.html", import.meta.url), "utf8");
const a = H.indexOf("function chartModel("), b = H.indexOf("\n}\n", a) + 3, SRC = H.slice(a, b);
const KEY = "if ((M - c.l[cur]) / (M - c.l[j]) >= .786 && big(cur)) ws.push(cur);";
if (!SRC.includes(KEY)) throw new Error("Wellenregel nicht gefunden");
// Modus „big“: große Welle – heute (0) gegen Variante (1): ist die große Welle gebrochen, die nächste ältere Welle nehmen,
// deren 78,6-%-Linie der Kurs noch nicht unterschritten hat (statt der Mindestgröße 1,2×)
const ESC0 = "if (out.big && last < (out.big.H - (out.big.H - out.big.L) * .786) * .995) { const b2 = mk(bigFrom(out.big.iL, 1.2)); if (b2) out.big = b2; }";
const ESC1 = "if (out.big && last < (out.big.H - (out.big.H - out.big.L) * .786) * .995) {\n      const s = out.big.iL, Hp = c.h[topSince(s)], W = 10, piv = []; let cur = s, pick = null;\n      for (let i = s - 1; i >= 0; i--) { const v = c.l[i]; if (v == null) continue; let ok = true;\n        for (let k = Math.max(0, i - W); k <= Math.min(n - 1, i + W); k++) if (c.l[k] != null && c.l[k] < v) { ok = false; break; } if (ok) piv.push(i); }\n      for (const j of piv) { if (j >= cur || c.l[j] >= c.l[cur]) continue;\n        let M = -Infinity; for (let k = j; k <= cur; k++) if (c.h[k] != null && c.h[k] > M) M = c.h[k];\n        if (cur !== s && (M - c.l[cur]) / (M - c.l[j]) >= .786 && last >= (Hp - (Hp - c.l[cur]) * .786) * .995) { pick = cur; break; }\n        cur = j; }\n      const b2 = mk(pick ?? bigFrom(out.big.iL, 1.2)); if (b2) out.big = b2; }";
if (!SRC.includes(ESC0)) throw new Error("Eskalation nicht gefunden");
const inp = JSON.parse(readFileSync(0, "utf8")), N = 1000, BIG = inp.mode === "big";
const mkF = src => { const ctx = { dateDE: s => s, fmt: v => v, Math }; vm.createContext(ctx); vm.runInContext(src + "; this.f = chartModel;", ctx); return ctx.f; };
const fns = BIG ? [mkF(SRC), mkF(SRC.replace(ESC0, ESC1))] : inp.thrs.map(thr => mkF(SRC.replace(KEY, KEY.replace(">= .786", ">= " + thr))));
const out = inp.samples.map(s => { const lo = Math.max(0, s.i - N + 1), sl = k => inp[k].slice(lo, s.i + 1);
  const c = { t: sl("t"), o: sl("o"), h: sl("h"), l: sl("l"), c: sl("c") };
  const r = { zone: { fib: { L_date: s.L }, H_date: s.H } };
  return fns.map(f => { try { const m = f(c, r); const w = BIG ? m.big : m.cls; return w ? [w.iL + lo, w.iH + lo] : null; } catch { return null; } }); });
process.stdout.write(JSON.stringify(out));
