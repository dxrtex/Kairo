"""Watchlist-Scan in den letzten großen Scan eintragen.

    python tools/merge_partial.py LIVE PART
LIVE: site/data des letzten großen Scans (wird überschrieben), PART: Ausgabe von run_scan --partial.
Ersetzt nur die Zeilen der neu gescannten Aktien (results, search, analysis, charts); alles andere bleibt wie im großen Scan.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def _load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def _dump(p: Path, obj) -> None:
    p.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")


def merge(live: Path, part: Path) -> dict:
    L, P = _load(live / "results.json"), _load(part / "results.json")
    new = {r["ticker"]: r for r in P.get("results", [])}
    old = {r["ticker"]: r for r in L.get("results", [])}
    for t, r in new.items():                          # Branchen-KGV kommt aus allen Aktien – aus dem großen Scan übernehmen
        fu_o = ((old.get(t) or {}).get("senti") or {}).get("fu") or {}
        fu_n = (r.get("senti") or {}).get("fu")
        if fu_n is not None and "pe_sec" not in fu_n and "pe_sec" in fu_o:
            fu_n["pe_sec"] = fu_o["pe_sec"]
    rows = [new.get(r["ticker"], r) for r in L.get("results", [])] + [r for t, r in new.items() if t not in old]
    rows.sort(key=lambda r: (bool(r.get("passed")), r.get("score") or 0, r.get("crv") or 0), reverse=True)
    st = L.get("stats") or {}
    st.update(hits=sum(bool(r.get("passed")) for r in rows), fast_hits=sum(bool(r.get("fast_hit")) for r in rows),
              near_hits=sum(bool(r.get("near_hit")) for r in rows),
              trend_hits=sum(bool((r.get("tr") or {}).get("ok")) for r in rows))
    full_at = L.get("full_at") or L.get("generated")
    L.update(results=rows, stats=st, generated=P["generated"], full_at=full_at,
             partial={"at": P["generated"], "n": len(new), "tickers": sorted(new)})
    _dump(live / "results.json", L)
    if (part / "search.json").exists() and (live / "search.json").exists():
        S, SP = _load(live / "search.json"), _load(part / "search.json")
        sp = {r["t"]: r for r in SP.get("rows", [])}
        S["rows"] = [sp.get(r["t"], r) for r in S.get("rows", [])] + [r for t, r in sp.items() if t not in {x["t"] for x in S.get("rows", [])}]
        S["generated"] = P["generated"]
        _dump(live / "search.json", S)
    if (part / "analysis.json").exists() and (live / "analysis.json").exists():
        A, AP = _load(live / "analysis.json"), _load(part / "analysis.json")
        A.setdefault("tickers", {}).update(AP.get("tickers") or {})
        A["generated"] = P["generated"]
        _dump(live / "analysis.json", A)
    (live / "charts").mkdir(exist_ok=True)
    for f in (part / "charts").glob("*.json"):
        shutil.copyfile(f, live / "charts" / f.name)
    return {"n": len(new), "hits": st["hits"], "rows": len(rows)}


if __name__ == "__main__":
    print(merge(Path(sys.argv[1]), Path(sys.argv[2])))
