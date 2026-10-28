"""Einmal-Prüfung: RSI-Divergenz im Detail (alle Tiefs der letzten 60 Tage mit RSI)."""
import sys
from backend.data_provider import YFinanceProvider
from backend.config import CONFIG
from backend.scanner import evaluate, find_rsi_divergence, pivot_lows
from backend.indicators import rsi

rc = CONFIG.rsi
for t in sys.argv[1:]:
    df = YFinanceProvider().history([t], CONFIG.history.period).get(t).dropna(subset=["Close"])
    n = len(df)
    r = rsi(df["Close"], rc.length).to_numpy()
    print(f"\n=== {t}: letzte Kerze {df.index[-1].date()} Schluss {df['Close'].iloc[-1]:.2f} RSI {r[-1]:.1f}")
    for k in range(1, 4):
        piv = pivot_lows(df["Low"], k, getattr(rc, "pivot_tolerance", 0.0))
        print(f"Pivot-Tiefs (je {k} Kerzen) letzte 60 T.:",
              ", ".join(f"{df.index[i].date():%d.%m.} L {df['Low'].iloc[i]:.2f} RSI {r[i]:.1f}" for i in piv if n - 1 - i <= 60))
    print("Divergenz-Ergebnis:", find_rsi_divergence(df["Low"], r, rc))
    print("Tagesdaten letzte 45 T.:")
    for i in range(max(0, n - 45), n):
        print(f"  {df.index[i].date()} O {df['Open'].iloc[i]:.2f} H {df['High'].iloc[i]:.2f} L {df['Low'].iloc[i]:.2f} C {df['Close'].iloc[i]:.2f} RSI {r[i]:.1f}")
    res = evaluate(df, {}, ticker=t)
    for c in res.criteria:
        print(f"{'OK ' if c.ok else 'NEIN'} {c.label}: {c.value}")
