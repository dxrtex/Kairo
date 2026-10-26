"""Einmal-Prüfung: alle Kriterien mit Werten für einzelne Aktien ausgeben."""
import sys
from backend.data_provider import YFinanceProvider
from backend.config import CONFIG
from backend.scanner import evaluate

for t in sys.argv[1:]:
    df = YFinanceProvider().history([t], CONFIG.history.period).get(t)
    print(f"\n=== {t}: letzte Kerze {df.index[-1].date()} Schluss {df['Close'].iloc[-1]:.2f}")
    res = evaluate(df, {}, ticker=t)
    for c in res.criteria:
        print(f"{'OK ' if c.ok else 'NEIN'} {c.label}: {c.value}  [{c.threshold}]")
    f = res.flags
    print("MACD-Ratio", f.get("raw_macd_ratio"), "steigend", f.get("raw_rising"), "| MBI-Alter", f.get("raw_mbi_age"), "Fade", f.get("raw_mbi_fade"), "Ref", f.get("raw_mbi_ref"))
