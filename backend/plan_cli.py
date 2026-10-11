"""Einzel-Analyse für den Trade-Plan: Kursdaten, Kairo-Kriterien, Basis/Stop, Widerstände und Marktlage einer Aktie.

    python -m backend.plan_cli AXON
    python -m backend.plan_cli UBER 2026-10-01   # Stand zum Schluss dieses Tages (Kauf am nächsten Tag nachrechnen)

Gibt alles als JSON zwischen ===BEGIN=== und ===END=== aus (für die Auswertung über GitHub Actions).
"""

from __future__ import annotations

import json
import sys

import numpy as np

from .config import CONFIG
from .data_provider import YFinanceProvider
from .indicators import atr as atr_ind, ema, macd, rsi
from .mbi import momentum_bias_index
from .scanner import evaluate
from .tradeplan import structure


def _ext(full, asof, *ind):
    """Indikatoren für die Ausgabe der Kerzen: bei Stichtag auf der vollen Reihe (nur Anzeige, Stop/Basis bleiben auf dem Stichtag)."""
    if not asof:
        return ind
    mb = momentum_bias_index(full["Close"], full["High"], full["Low"])
    return (atr_ind(full, 14), *(ema(full["Close"], n) for n in (20, 50, 200)), rsi(full["Close"], 14), macd(full["Close"]), mb)


def main(argv=None) -> int:
    args = argv or sys.argv[1:]
    t, asof = args[0], (args[1] if len(args) > 1 and args[1] else None)
    prov = YFinanceProvider()
    h = prov.history([t, "^GSPC", "^VIX"], "2y")
    full = h[t].dropna(subset=["Open", "High", "Low", "Close"])
    df = full[full.index <= asof] if asof else full
    info = {}
    try:
        info = prov.info(t) or {}
    except Exception as exc:
        info = {"err": repr(exc)[:100]}
    res = evaluate(df, info, ticker=t)
    a14 = atr_ind(df, 14)
    atr0 = float(a14.iloc[-1])
    e20, e50, e200 = (ema(df["Close"], n) for n in (20, 50, 200))
    r = rsi(df["Close"], 14)
    m = macd(df["Close"])
    mb = momentum_bias_index(df["Close"], df["High"], df["Low"])
    tail = full[full.index > df.index[-31]] if asof else df.tail(30)
    a14, e20, e50, e200, r, m, mb = _ext(full, asof, a14, e20, e50, e200, r, m, mb)
    bars = [{"d": str(i.date()), "o": round(float(x.Open), 2), "h": round(float(x.High), 2), "l": round(float(x.Low), 2),
             "c": round(float(x.Close), 2), "v": int(x.Volume), "atr": round(float(a14[i]), 2), "rsi": round(float(r[i]), 1),
             "e20": round(float(e20[i]), 2), "e50": round(float(e50[i]), 2), "e200": round(float(e200[i]), 2),
             "mh": round(float(m["hist"][i]), 3), "mbi_g": round(float(mb["upper_bias"][i]), 1), "mbi_r": round(float(mb["lower_bias"][i]), 1),
             "gx": bool(mb["green_x"][i])} for i, x in tail.iterrows()]
    spx, vix = h["^GSPC"]["Close"], h["^VIX"]["Close"]
    if asof:
        spx, vix = spx[spx.index <= asof], vix[vix.index <= asof]
    mk = {"spx": round(float(spx.iloc[-1]), 1), "spx_e50": round(float(ema(spx, 50).iloc[-1]), 1),
          "spx_e200": round(float(ema(spx, 200).iloc[-1]), 1), "vix": round(float(vix.iloc[-1]), 1), "date": str(spx.index[-1].date())}
    out = {"ticker": t, "asof": asof, "info": {k: info.get(k) for k in ("name", "currency", "earnings_date", "market_cap", "sector")},
           "passed": res.passed, "fast": res.fast_hit, "score": res.score,
           "criteria": [{"k": c.key, "ok": bool(c.ok), "v": c.value} for c in res.criteria],
           "plan_alt": {k: (round(float(v), 2) if isinstance(v, (int, float, np.floating)) and v is not None else v) for k, v in (res.plan or {}).items()},
           "zone": {"H": res.zone.get("H"), "H_date": res.zone.get("H_date"),
                    "fib": {k: round(float(v), 2) for k, v in ((res.zone.get("fib") or {}).get("levels") or {}).items()},
                    "support": (res.zone.get("support") or {}).get("center")},
           "structure": structure(df, atr0, (res.zone.get("fib") or {}).get("levels")), "high_52w": round(float(df["High"].tail(250).max()), 2),
           "market": mk, "bars": bars}
    print("===BEGIN===")
    print(json.dumps(out, ensure_ascii=False, default=str))
    print("===END===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
