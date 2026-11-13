// Formations-Studie (Runde 13.11.): Wie oft lief eine von der Auto-Analyse erkannte Formation danach wirklich in ihre Richtung?
// Nutzt exakt autoTA() aus site/index.html. Je Aktie alle 5 Handelstage die Analyse wie in der App (letzte 1.000 Kerzen),
// jede Formation einmal gezählt (erste Erkennung). Ergebnis ab Schlusskurs des Erkennungstags:
//   - mit rechnerischem Ziel: Ziel vor dem Musterpunkt auf der Gegenseite (Stop) innerhalb von 60 Tagen erreicht?
//   - immer: Richtung nach 20 Handelstagen (steigend bei bullischen, fallend bei bärischen Mustern) und Ø-Veränderung
// Vergleich: alle geprüften Tage derselben Aktien (Grundrate). Lernjahre bis 2023, Prüfjahre ab 2024.
//   node tools/patstudy.js ordner_mit_pat_px_*.json > data/patstats.json
const fs = require("fs"), path = require("path");
const autoTA = require("./autota_lib.js").load();
const dir = process.argv[2] || ".", STEP = +(process.env.PAT_STEP || 5), WIN = 1000;
const agg = {}, base = { L: { n: 0, up: 0, r: 0 }, P: { n: 0, up: 0, r: 0 } };
const add = (k, g, f) => { const a = (agg[k] = agg[k] || { L: { n: 0, hit: 0, tg: 0, dir: 0, r: 0 }, P: { n: 0, hit: 0, tg: 0, dir: 0, r: 0 } })[g]; f(a); };
let stocks = 0, t0 = Date.now();
for (const f of fs.readdirSync(dir).filter(x => /^pat_px_\d+\.json$/.test(x))) {
  const all = JSON.parse(fs.readFileSync(path.join(dir, f)));
  for (const [tk, d] of Object.entries(all)) {
    stocks++; const N = d.t.length, seen = new Map();
    for (let e = 300; e < N - 21; e += STEP) {
      const s = Math.max(0, e + 1 - WIN), c = { t: d.t.slice(s, e + 1), o: d.o.slice(s, e + 1), h: d.h.slice(s, e + 1), l: d.l.slice(s, e + 1), c: d.c.slice(s, e + 1), v: d.v.slice(s, e + 1) };
      let A; try { A = autoTA(c); } catch (err) { continue; } if (!A) continue;
      const px = d.c[e], g = d.t[e] < "2024-01-01" ? "L" : "P", r20 = d.c[e + 20] / px - 1; if (!(px > 0) || !isFinite(r20)) continue;
      base[g].n++; base[g].r += r20; if (r20 > 0) base[g].up++;
      for (const p of A.pats) {
        const anchor = p.pts.length ? d.t[s + p.pts[0][0]] : "", key = p.k + "|" + anchor, lastSeen = seen.get(key);
        if (lastSeen != null && (anchor || e - lastSeen <= 20)) { seen.set(key, e); continue; }   // schon gezählt (Muster) bzw. Ausbruch der letzten 20 Tage
        seen.set(key, e);
        const id = p.k + (p.st === "bestätigt" || p.st.startsWith("Ausbruch") ? "+" : p.st === "in Bildung" ? "~" : "");
        add(id, g, a => { a.n++; a.r += r20; if (p.bull === true ? r20 > 0 : p.bull === false ? r20 < 0 : false) a.dir++;
          if (p.target > 0 && p.pts.length) {
            const ys = p.pts.map(x => x[1]), stop = p.bull ? Math.min(...ys) : Math.max(...ys); a.tg++;
            for (let j = e + 1; j < Math.min(N, e + 61); j++) {
              if (p.bull ? d.l[j] <= stop : d.h[j] >= stop) break;
              if (p.bull ? d.h[j] >= p.target : d.l[j] <= p.target) { a.hit++; break; } } } });
      }
    }
    if (stocks % 50 === 0) console.error(`${stocks} Aktien, ${Math.round((Date.now() - t0) / 1000)} s`);
  }
}
const out = { generated: new Date().toISOString().slice(0, 10), stocks, step: STEP, base: {}, pats: {} };
for (const g of ["L", "P"]) { const b = base[g]; out.base[g] = { n: b.n, up: b.n ? +(b.up / b.n).toFixed(3) : null, r20: b.n ? +(b.r / b.n).toFixed(4) : null }; }
for (const [k, v] of Object.entries(agg)) { out.pats[k] = {};
  for (const g of ["L", "P"]) { const a = v[g]; out.pats[k][g] = { n: a.n, dir: a.n ? +(a.dir / a.n).toFixed(3) : null, r20: a.n ? +(a.r / a.n).toFixed(4) : null, tg: a.tg, hit: a.tg ? +(a.hit / a.tg).toFixed(3) : null }; } }
process.stdout.write(JSON.stringify(out, null, 1));
