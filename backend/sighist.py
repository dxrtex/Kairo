"""Kairo-Signale je Aktie (Fahrplan 8, wie „Signal-Historie“ bei TrendSpider/TipRanks): Wo gab es in den letzten
2 Jahren einen Kairo-Treffer (11/11), und was hätte die gültige Regel B60 daraus gemacht (Netto-R)?

Nur Aufzeichnung für die Anzeige im Chart – die Regel selbst kommt unverändert aus scanner.evaluate (Treffer) und
live.strat mit RULE60 (Seitwärtsphase abwarten, Kauf, Stop, Ausstieg EMA 20 ab Tag 10, spätestens Tag 60).

  python -m backend.sighist --shard k --shards 16 --tickers tickers.txt   → sig_part_k.json
  python -m backend.sighist --combine parts --prev alt/sighist.json        → site/data/sighist.json
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd

from .bilanz import GAP
from .config import ROOT

DAYS = 504          # 2 Jahre Signale
WARM = 260          # davor genug Kurse für EMA 200 & Co.


def signals(df: pd.DataFrame, days: int = DAYS) -> list[dict]:
    """Alle frischen Kairo-Treffer der letzten `days` Handelstage mit dem Ergebnis nach Regel B60."""
    from .live import RULE60, strat
    from .scanner import evaluate

    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    n = len(df)
    if n < WARM + 20:
        return []
    out, last = [], -99
    idx = [str(d.date()) if hasattr(d, "date") else str(d)[:10] for d in df.index]
    for i in range(max(WARM, n - days), n):
        try:
            r = evaluate(df.iloc[: i + 1])
        except Exception:
            continue
        if not r.passed:
            continue
        fresh = i - last > GAP
        last = i
        if not fresh:
            continue
        st = strat(df, i, RULE60)
        rec = {"d": idx[i], "res": st.get("res")}
        if st.get("r") is not None:
            b = i + 1 + int(st.get("s") or 0)                     # Kauf-Kerze
            x = b + int(st.get("days") or 1) - 1                   # Verkaufs-Kerze (bzw. letzte bei „läuft“)
            rec.update(r=st["r"], e=st.get("e"), sl=st.get("sl"), b=idx[b] if b < n else None, x=idx[min(x, n - 1)],
                       days=st.get("days"))
        out.append(rec)
    return out


def summary(sig: list[dict]) -> dict:
    done = [s for s in sig if s.get("r") is not None and s["res"] in ("stop", "ema", "zeit")]
    if not done:
        return {"n": len(sig), "trades": 0}
    rs = [s["r"] for s in done]
    return {"n": len(sig), "trades": len(done), "avg": round(sum(rs) / len(rs), 3), "win": sum(r > 0 for r in rs),
            "best": round(max(rs), 2), "worst": round(min(rs), 2)}


def combine(parts: list[Path], prev: Path | None) -> dict:
    by: dict[str, list] = {}
    if prev and prev.exists():
        try:
            by.update(json.loads(prev.read_text()).get("by", {}))      # Aktien ohne neuen Lauf behalten ihren Stand
        except Exception:
            pass
    for p in parts:
        by.update(json.loads(p.read_text()))
    return {"generated": time.strftime("%Y-%m-%d"), "rule": "B60", "n": len(by),
            "by": by, "sum": {t: summary(v) for t, v in by.items() if v}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--tickers", help="Datei mit einem Ticker je Zeile (Standard: Aktien der letzten Ergebnisse)")
    ap.add_argument("--combine", help="Ordner mit sig_part_*.json")
    ap.add_argument("--prev")
    a = ap.parse_args(argv)
    if a.combine:
        res = combine(sorted(Path(a.combine).glob("sig_part_*.json")), Path(a.prev) if a.prev else None)
        out = ROOT / "site" / "data" / "sighist.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")))
        print(f"Kairo-Signale: {res['n']} Aktien, {sum(len(v) for v in res['by'].values())} Treffer")
        return 0
    if a.tickers:
        tickers = [t.strip() for t in Path(a.tickers).read_text().split() if t.strip()]
    else:
        tickers = [r["ticker"] for r in json.loads((ROOT / "site" / "data" / "results.json").read_text())["results"]]
    mine = sorted(set(tickers))[a.shard::a.shards]
    from .data_provider import YFinanceProvider
    data = YFinanceProvider().history(mine, "3y")
    print(f"Shard {a.shard}: {len(data)} von {len(mine)} Aktien geladen")
    res, t0 = {}, time.time()
    for k, (t, df) in enumerate(data.items()):
        try:
            res[t] = signals(df)
        except Exception as e:                       # eine kaputte Kursreihe darf den Lauf nicht stoppen
            print(f"  {t}: {e}")
        if k % 20 == 0:
            print(f"  {k}/{len(data)} · {sum(map(len, res.values()))} Treffer · {time.time() - t0:.0f} s")
    Path(f"sig_part_{a.shard}.json").write_text(json.dumps(res, separators=(",", ":")))
    print(f"Fertig: {len(res)} Aktien")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
