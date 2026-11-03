"""Einmal-Test: Unter welchem Symbol führt TradingView den SPDR MSCI ACWI IMI (IE00B3YLTY66) an gettex/Xetra?"""
import json
import requests
H = {"User-Agent": "Mozilla/5.0", "Origin": "https://www.tradingview.com", "Referer": "https://www.tradingview.com/"}
for q in ("IE00B3YLTY66", "SPYI", "SPDR MSCI ACWI IMI"):
    for ex in ("GETTEX", "XETR", "TRADEGATE", ""):
        u = "https://symbol-search.tradingview.com/symbol_search/v3/"
        try:
            r = requests.get(u, params={"text": q, "exchange": ex, "lang": "de", "search_type": "", "domain": "production"}, headers=H, timeout=20)
            j = r.json()
            syms = j.get("symbols", j) if isinstance(j, dict) else j
            print(f"=== {q} @ {ex or 'alle'}: {r.status_code}")
            for s in (syms or [])[:8]:
                print("   ", s.get("exchange"), s.get("symbol"), "|", s.get("description"), "|", s.get("type"), "|", s.get("isin") or "")
        except Exception as exc:
            print(q, ex, "Fehler", repr(exc)[:200])
