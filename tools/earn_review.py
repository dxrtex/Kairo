"""Prognose-Bilanz Quartalszahlen: Wie gut lag Kairo? Wöchentlich aus dem eigenen Archiv (earn_archive.json).

Für jede Meldung mit Kursreaktion: gezeigte Wahrscheinlichkeit „steigt am Tag danach“ (p, Stand v) gegen die echte Reaktion.
Ausgabe earn_review.md (für Jonny und Claude) und earn_review.json (für die App):
- Trefferquote und Brier-Score (mittlerer quadratischer Fehler; Münzwurf = 0,25) gesamt, je Stand der Regel und je Ausblick
- Eichung: Wenn Kairo „60–70 %“ sagt – stieg die Aktie dann auch in 60–70 % der Fälle?
- größte Fehlprognosen mit Schlagzeile (Ausblick falsch erkannt?)
- Vorschläge: Gewinn-Stufe × Ausblick, deren echte Quote mit genug Fällen deutlich von der gezeigten abweicht.
Vorschläge werden nicht automatisch übernommen – jede Änderung an der Regel bekommt einen neuen Stand (earnfast.MODEL).

    python tools/earn_review.py <earn_archive.json> <site/earn_stats.json> <out_dir>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import earnmodel, earnwhy  # noqa: E402

GK = {-1: "gesenkt", 0: "bestätigt", 1: "angehoben"}
MISS = 0.03
MIN_SUGGEST = 30          # so viele Fälle braucht eine Zelle, bevor eine Anpassung vorgeschlagen wird
DIFF_SUGGEST = 0.10       # … und so weit (Prozentpunkte/100) muss die echte Quote abweichen


def frame(arc: dict, stats: dict) -> pd.DataFrame:
    B = stats.get("buckets") or []
    rows = []
    for k, r in arc.items():
        if r.get("r1") is None or r.get("s") is None:
            continue
        t, d = k.split("|", 1)
        b = next((i for i, x in enumerate(B) if x["lo"] <= r["s"] * 100 < x["hi"]), None)
        w = r.get("why") or {}
        rows.append({"t": t, "d": d, "s": r["s"], "rs": r.get("rs"), "gi": r.get("g"), "r1": r["r1"], "y": float(r["r1"] > 0), "p": r.get("p"), "v": r.get("v") or "vor Aufzeichnung",
                     "g": GK.get(r.get("g"), "keine Meldung"), "gt": r.get("gt") or "", "b": b, "bn": B[b]["name"] if b is not None else "?",
                     "why": "why" in r, "tags": w.get("tags") or [], "head": w.get("head") or [], "spy": w.get("spy"), "ex": w.get("ex"),
                     "run20": w.get("run20"), "miss": earnwhy.is_miss(r)})
    return pd.DataFrame(rows)


def score(D: pd.DataFrame) -> dict:
    D = D[D["p"].notna()]
    if not len(D):
        return {"n": 0}
    p, y = D["p"].astype(float), D["y"]
    return {"n": int(len(D)), "hit": float(((p > .5) == (y > .5)).mean()), "brier": float(((p - y) ** 2).mean()),
            "coin": float(((0.5 - y) ** 2).mean()), "up": float(y.mean())}


MIN_CAND = 15             # so viele Fehlprognosen mit demselben Grund, bevor er als neues Merkmal vorgeschlagen wird
K_SMOOTH = 20             # Glättung der Nacheichung zur Gewinn-Stufe hin (Pseudo-Fälle)
MIN_CALIB = 200           # so viele Meldungen braucht die Nacheichung insgesamt


def why_section(D: pd.DataFrame, p) -> list[str]:
    """Warum lagen wir falsch? Gründe bei Fehlprognosen gegen Gründe bei getroffenen Fällen (nur untersuchte Fälle)."""
    W = D[D["why"]]
    p("\n## Warum lagen wir falsch? (automatische Ursachensuche)\n")
    M, H = W[W["miss"]], W[~W["miss"]]
    if len(M) < 5 or len(H) < 5:
        p(f"Noch zu wenige untersuchte Fälle ({len(M)} Fehlprognosen, {len(H)} Vergleichsfälle).")
        return []
    p(f"{len(M)} Fehlprognosen und {len(H)} Vergleichsfälle untersucht.\n")
    mk = M[M["spy"].notna()]
    if len(mk):
        same = ((mk["spy"] * mk["r1"] > 0) & (mk["spy"].abs() >= 0.01)).mean()
        small = (mk["ex"].abs() < MISS).mean()
        p(f"- Markt: Bei {same:.0%} der Fehlprognosen lief der Gesamtmarkt am selben Tag um ≥ 1 % in dieselbe Richtung; "
          f"bei {small:.0%} war die Bewegung über dem Markt kleiner als {MISS:.0%} – dann lag es eher am Markt als an den Zahlen.")
    rm, rh = M["run20"].dropna(), H["run20"].dropna()
    if len(rm) >= 5 and len(rh) >= 5:
        p(f"- Vorlauf (20 Handelstage davor): Fehlprognosen Ø {rm.mean():+.1%}, getroffene Ø {rh.mean():+.1%}.")
    p("\n| Grund in den Schlagzeilen danach | bei Fehlprognosen | bei getroffenen | Faktor |\n|---|---|---|---|")
    cand = []
    for k in earnwhy.REASONS:
        fm, fh = M["tags"].apply(lambda x: k in x).mean(), H["tags"].apply(lambda x: k in x).mean()
        nm = int(M["tags"].apply(lambda x: k in x).sum())
        lift = fm / fh if fh > 0 else float("inf") if fm > 0 else 1.0
        if nm:
            p(f"| {k} | {fm:.0%} ({nm}) | {fh:.0%} | {lift:.1f} |")
        if nm >= MIN_CAND and lift >= 1.5:
            cand.append(f"{k}: bei {fm:.0%} der Fehlprognosen genannt, sonst {fh:.0%} → als Merkmal prüfen")
    if len(rm) >= MIN_CAND and len(rh) >= MIN_CAND and abs(rm.mean() - rh.mean()) >= 0.05:
        cand.append(f"Vorlauf: Fehlprognosen Ø {rm.mean():+.1%} gegen {rh.mean():+.1%} → „schon eingepreist“ als Merkmal prüfen")
    p("\n**Kandidaten für neue Merkmale:** " + ("; ".join(cand) if cand else f"noch keine (ein Grund braucht ≥ {MIN_CAND} Fehlprognosen und Faktor ≥ 1,5)."))
    ex = M.sort_values("r1", key=lambda x: -x.abs()).head(8)
    if len(ex):
        p("\nBeispiele:")
        for r in ex.itertuples():
            p(f"- {r.t} {r.d}: Kairo {float(r.p):.0%}, Kurs {r.r1:+.1%}" + (f" (Markt {r.spy:+.1%})" if r.spy is not None and r.spy == r.spy else "")
              + (f" · Gründe: {', '.join(r.tags)}" if r.tags else "") + (f" – „{r.head[0]}“" if r.head else ""))
    return cand


def calibrate(D: pd.DataFrame, stats: dict) -> dict:
    """Nacheichung Gewinn-Stufe × Ausblick aus den eigenen Meldungen (geglättet zur Gewinn-Statistik seit 2019).
    Übernommen (adopt) nur, wenn sie in der jüngeren Hälfte – mit Werten nur aus der älteren Hälfte – genauer ist als die
    damals gezeigte Prognose. So passt sich die Zahl laufend an, ohne sich die Vergangenheit schönzurechnen."""
    B = stats.get("buckets") or []
    X = D[D["b"].notna() & D["p"].notna()].sort_values("d")
    if len(X) < MIN_CALIB or not B:
        return {"adopt": False, "text": f"Noch nicht: {len(X)} von {MIN_CALIB} nötigen Meldungen mit aufgezeichneter Prognose."}

    def fit(T):
        cell = {}
        for (b, g), x in T.groupby(["b", "g"]):
            prior = B[int(b)]["up1"]
            cell[f"{int(b)}|{g}"] = round(float((x["y"].sum() + K_SMOOTH * prior) / (len(x) + K_SMOOTH)), 3)
        return cell
    half = len(X) // 2
    old, new = X.iloc[:half], X.iloc[half:]
    c = fit(old)
    q = np.array([c.get(f"{int(b)}|{g}", B[int(b)]["up1"]) for b, g in zip(new["b"], new["g"])])
    b_new, b_shown = float(((q - new["y"]) ** 2).mean()), float(((new["p"].astype(float) - new["y"]) ** 2).mean())
    adopt = b_new < b_shown
    full = fit(X)
    n = {f"{int(b)}|{g}": int(len(x)) for (b, g), x in X.groupby(["b", "g"])}
    txt = (f"Geprüft an den jüngeren {len(new)} Meldungen: Brier nachgeeicht {b_new:.3f} gegen gezeigt {b_shown:.3f} → "
           + ("**übernommen** (die App nutzt ab jetzt die nachgeeichten Werte)." if adopt else "nicht übernommen (nicht genauer)."))
    return {"adopt": bool(adopt), "p": full, "n": n, "brier_new": b_new, "brier_shown": b_shown, "text": txt}


MIN_MODEL = 200           # so viele Meldungen braucht das Modell
FOLDS = 3                 # Prüfzeiträume (die jüngsten Meldungen, je Zeitraum nur mit älteren geschätzt)


def model_fit(D: pd.DataFrame, stats: dict, guide: dict | None) -> dict:
    """Logistisches Modell (backend/earnmodel.py): Langzeit-Quote Gewinn × Ausblick und Umsatz-Überraschung – rollierend geprüft: Die Meldungen werden
    nach Datum sortiert; die jüngere Hälfte in FOLDS Zeiträume geteilt; für jeden wird nur mit früheren Tagen geschätzt
    und gegen die damals gezeigte Zahl verglichen. Übernommen nur, wenn es über alle Zeiträume genauer ist (Brier)."""
    X = D.sort_values("d").reset_index(drop=True)
    X = X.assign(x=[earnmodel.features(earnmodel.prior(stats, guide, s, None if pd.isna(g) else int(g)), None if pd.isna(rs) else rs)
                    for s, rs, g in zip(X["s"], X["rs"], X["gi"])])
    X = X[X["x"].notna()].reset_index(drop=True)
    if len(X) < MIN_MODEL:
        return {"adopt": False, "text": f"Noch nicht: {len(X)} von {MIN_MODEL} nötigen Meldungen."}
    days = sorted(X["d"].unique())
    cut0 = days[len(days) // 2]
    later = [d for d in days if d >= cut0]
    parts = [later[i * len(later) // FOLDS:(i + 1) * len(later) // FOLDS] for i in range(FOLDS)]
    pm, ps, yy, rows = [], [], [], []
    for ds in parts:
        if not ds:
            continue
        tr, te = X[X["d"] < ds[0]], X[X["d"].isin(ds)]
        w = earnmodel.fit(list(tr["x"]), list(tr["y"]))
        q = np.array([earnmodel.predict(w, x) for x in te["x"]])
        m = te["p"].notna().to_numpy()
        if m.sum():
            sh = te["p"].astype(float).to_numpy()
            rows.append({"von": ds[0], "bis": ds[-1], "n": int(m.sum()), "model": float(((q[m] - te["y"].to_numpy()[m]) ** 2).mean()),
                         "shown": float(((sh[m] - te["y"].to_numpy()[m]) ** 2).mean()),
                         "hit_model": float(((q[m] > .5) == (te["y"].to_numpy()[m] > .5)).mean()),
                         "hit_shown": float(((sh[m] > .5) == (te["y"].to_numpy()[m] > .5)).mean())})
            pm += list(q[m]); ps += list(sh[m]); yy += list(te["y"].to_numpy()[m])
    if not yy:
        return {"adopt": False, "text": "Keine geprüften Meldungen mit gezeigter Prognose."}
    pm, ps, yy = map(np.array, (pm, ps, yy))
    b_m, b_s = float(((pm - yy) ** 2).mean()), float(((ps - yy) ** 2).mean())
    better = sum(r["model"] < r["shown"] for r in rows)
    adopt = b_m < b_s and better >= (len(rows) + 1) // 2
    w = earnmodel.fit(list(X["x"]), list(X["y"]))
    txt = (f"Rollierend geprüft an {len(yy)} jüngeren Meldungen ({len(rows)} Zeiträume, je nur mit älteren geschätzt): "
           f"Brier Modell {b_m:.3f} gegen gezeigt {b_s:.3f}, Richtung {float(((pm > .5) == (yy > .5)).mean()):.0%} gegen "
           f"{float(((ps > .5) == (yy > .5)).mean()):.0%}, besser in {better} von {len(rows)} Zeiträumen → "
           + ("**übernommen** (App und Mitteilungen rechnen ab jetzt mit dem Modell)." if adopt else "nicht übernommen."))
    return {"adopt": bool(adopt), "f": earnmodel.FEATURES, "w": w, "n": int(len(X)), "since": str(X["d"].min()), "until": str(X["d"].max()),
            "brier_model": round(b_m, 4), "brier_shown": round(b_s, 4), "folds": rows, "up": round(float(X["y"].mean()), 3), "text": txt}


def latency(arc: dict) -> dict:
    """Wie schnell ist Kairo? Minuten von der Meldezeit (Yahoo-Termin; bei US-Firmen meist die Minute der Pressemitteilung)
    bis zur ersten Prüfung mit Zahlen (seen) und bis zur Mitteilung (push). Nur Fälle mit plausiblen Werten (0–24 h)."""
    def mins(a, b):
        try:
            m = (pd.Timestamp(b) - pd.Timestamp(a)).total_seconds() / 60
            return m if 0 <= m <= 24 * 60 else None
        except Exception:
            return None
    seen = [m for r in arc.values() if (m := mins(r.get("ts"), r.get("seen"))) is not None]
    push = [m for r in arc.values() if (m := mins(r.get("seen"), r.get("push"))) is not None]
    q = lambda x, f: round(float(np.percentile(x, f)), 1) if x else None
    return {"n_seen": len(seen), "seen_med": q(seen, 50), "seen_p90": q(seen, 90), "n_push": len(push), "push_med": q(push, 50), "push_p90": q(push, 90)}


def review(arc_file: str, stats_file: str, out_dir: str) -> dict:
    arc = json.loads(Path(arc_file).read_text(encoding="utf-8"))
    stats = json.loads(Path(stats_file).read_text(encoding="utf-8"))
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    D = frame(arc, stats)
    L = ["# Prognose-Bilanz Quartalszahlen\n"]
    p = L.append
    lat = latency(arc)
    if lat["n_seen"]:
        p(f"Schnelligkeit: erste Zahlen im Mittel {lat['seen_med']:.0f} Min. nach der Meldezeit (90 % innerhalb {lat['seen_p90']:.0f} Min., "
          f"{lat['n_seen']} Meldungen)" + (f"; Mitteilung im Mittel {lat['push_med']:.0f} Min. danach" if lat["n_push"] else "") + ".\n")
    if not len(D):
        p("Noch keine Meldungen mit Kursreaktion.")
        (out / "earn_review.md").write_text("\n".join(L), encoding="utf-8")
        (out / "earn_review.json").write_text(json.dumps({"n": 0, "lat": lat}, ensure_ascii=False), encoding="utf-8")
        return {"n": 0, "lat": lat}
    S = score(D)
    p(f"{len(D)} Meldungen mit Kursreaktion ({D['d'].min()} bis {D['d'].max()}), davon {S['n']} mit aufgezeichneter Prognose.\n")
    p("| Bereich | n | Richtung getroffen | Brier (kleiner = besser) | Münzwurf |\n|---|---|---|---|---|")
    line = lambda name, s: p(f"| {name} | {s['n']} | {s['hit']:.0%} | {s['brier']:.3f} | {s['coin']:.3f} |") if s.get("n") else None
    line("alle", S)
    for v, g in D.groupby("v"):
        line(f"Stand {v}", score(g))
    for k in ("gesenkt", "bestätigt", "angehoben", "keine Meldung"):
        line(f"Ausblick {k}", score(D[D["g"] == k]))
    P = D[D["p"].notna()].copy()
    if len(P):
        p("\n## Eichung – stimmt die gezeigte Zahl?\n")
        p("| Kairo sagte | n | tatsächlich gestiegen |\n|---|---|---|")
        P["bin"] = pd.cut(P["p"].astype(float), [0, .3, .4, .5, .6, .7, 1.0], include_lowest=True)
        for b, g in P.groupby("bin", observed=True):
            p(f"| {b.left:.0%}–{b.right:.0%} | {len(g)} | {g['y'].mean():.0%} |")
    p("\n## Gewinn × Ausblick – echte Quote (n)\n")
    p("| Gewinn | gesenkt | bestätigt | angehoben | keine Meldung |\n|---|---|---|---|---|")
    sugg = []
    B = stats.get("buckets") or []
    for b in sorted(D["b"].dropna().unique()):
        s = D[D["b"] == b]
        cells = []
        for k in ("gesenkt", "bestätigt", "angehoben", "keine Meldung"):
            x = s[s["g"] == k]
            cells.append(f"{x['y'].mean():.0%} ({len(x)})" if len(x) else "–")
            shown = x["p"].dropna().astype(float).mean() if x["p"].notna().any() else B[int(b)]["up1"]
            if len(x) >= MIN_SUGGEST and abs(x["y"].mean() - shown) >= DIFF_SUGGEST:
                sugg.append(f"{B[int(b)]['name']} + Ausblick {k}: gezeigt Ø {shown:.0%}, tatsächlich {x['y'].mean():.0%} (n {len(x)})")
        p(f"| {B[int(b)]['name']} | " + " | ".join(cells) + " |")
    p("\n## Vorschläge zur Anpassung\n")
    p("\n".join(f"- {x}" for x in sugg) if sugg else f"- keine (Zellen brauchen ≥ {MIN_SUGGEST} Fälle und ≥ {DIFF_SUGGEST:.0%} Abweichung)")
    p("\n## Größte Fehlprognosen (zum Nachprüfen der Ausblick-Erkennung)\n")
    if len(P):
        P["miss"] = (P["p"].astype(float) - P["y"]).abs() * P["r1"].abs()
        for r in P.sort_values("miss", ascending=False).head(15).itertuples():
            p(f"- {r.t} {r.d}: Kairo {float(r.p):.0%} steigt, Kurs {r.r1:+.1%} · Gewinn {r.s:+.0%} · Ausblick {r.g}" + (f" – „{r.gt}“" if r.gt else ""))
    cand = why_section(D, p)
    calib = calibrate(D, stats)
    p("\n## Automatische Nacheichung (Gewinn × Ausblick)\n")
    p(calib["text"])
    (out / "earn_calib.json").write_text(json.dumps({k: v for k, v in calib.items() if k != "text"}, ensure_ascii=False), encoding="utf-8")
    try:
        guide = json.loads((Path(stats_file).parent / "earn_guide.json").read_text(encoding="utf-8"))
    except Exception:
        guide = None
    mdl = model_fit(D, stats, guide)
    p("\n## Prognose-Modell (Langzeit-Quote + Umsatz, auf eigene Meldungen geeicht)\n")
    p(mdl["text"])
    if mdl.get("w"):
        p("\n| Merkmal | Gewicht |\n|---|---|")
        for f, v in zip(mdl["f"], mdl["w"]):
            p(f"| {earnmodel.NAMES[f]} | {v:+.2f} |")
        if mdl.get("folds"):
            p("\n| Zeitraum | n | Brier Modell | Brier gezeigt | Richtung Modell | Richtung gezeigt |\n|---|---|---|---|---|---|")
            for r in mdl["folds"]:
                p(f"| {r['von']} – {r['bis']} | {r['n']} | {r['model']:.3f} | {r['shown']:.3f} | {r['hit_model']:.0%} | {r['hit_shown']:.0%} |")
    (out / "earn_model.json").write_text(json.dumps({k: v for k, v in mdl.items() if k != "text"}, ensure_ascii=False), encoding="utf-8")
    (out / "earn_review.md").write_text("\n".join(L), encoding="utf-8")
    res = {"n": S["n"], "hit": S.get("hit"), "brier": S.get("brier"), "since": str(D["d"].min()), "suggest": sugg, "candidates": cand,
           "calib": calib.get("adopt", False), "model": mdl.get("adopt", False), "lat": lat}
    (out / "earn_review.json").write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    return res


if __name__ == "__main__":
    print(json.dumps(review(*sys.argv[1:4]), ensure_ascii=False, indent=1))
