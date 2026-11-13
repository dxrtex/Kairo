// Lädt autoTA() direkt aus site/index.html (dieselbe Logik wie in der App) – für Studie und Tests
const fs = require("fs"), path = require("path");
function load(file) {
  const s = fs.readFileSync(file || path.join(__dirname, "..", "site", "index.html"), "utf8");
  const i = s.indexOf("function autoTA(c) {"); if (i < 0) throw new Error("autoTA nicht gefunden");
  let d = 0, j = i;
  for (; j < s.length; j++) { const ch = s[j]; if (ch === "{") d++; else if (ch === "}") { d--; if (d === 0) break; } }
  const src = s.slice(i, j + 1);
  const fmt = (v, k = 2) => v == null ? "–" : Number(v).toFixed(k);
  return new Function("fmt", src + "\nreturn autoTA;")(fmt);
}
module.exports = { load };
