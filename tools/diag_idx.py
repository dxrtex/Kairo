"""Einmal-Diagnose: welche Tabellen liefern die Wikipedia-Seiten der Indizes? (wird danach wieder entfernt)"""
import io, urllib.request
import pandas as pd
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"}
URLS = ["https://de.wikipedia.org/wiki/NASDAQ-100", "https://de.wikipedia.org/wiki/Nikkei_225", "https://en.wikipedia.org/wiki/Nasdaq-100",
        "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average", "https://de.wikipedia.org/wiki/MDAX", "https://de.wikipedia.org/wiki/TecDAX",
        "https://en.wikipedia.org/wiki/MDAX", "https://en.wikipedia.org/wiki/TecDAX", "https://en.wikipedia.org/wiki/FTSE_100_Index",
        "https://en.wikipedia.org/wiki/CAC_40", "https://en.wikipedia.org/wiki/Swiss_Market_Index", "https://en.wikipedia.org/wiki/Hang_Seng_Index",
        "https://en.wikipedia.org/wiki/Russell_1000_Index", "https://en.wikipedia.org/wiki/S%26P_100"]
for u in URLS:
    print("=" * 30, u)
    try:
        html = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30).read().decode("utf-8", "replace")
        for i, t in enumerate(pd.read_html(io.StringIO(html))):
            if len(t) < 15: continue
            cols = [str(c[-1] if isinstance(c, tuple) else c) for c in t.columns]
            print(f"  T{i} rows={len(t)} cols={cols[:8]}")
            print("     ", t.head(3).astype(str).values.tolist())
    except Exception as e:
        print("  FEHLER", e)
