import urllib.request, json, sys
T = ["META", "AAPL", "TSLA", "QBTS", "RHM.DE", "SAP.DE", "TKA.DE", "1810.HK", "BABA", "AIR.PA", "TSM", "DRO.AX", "TRAC.CN", "R3NK.DE", "HUH1V.HE", "601360.SS"]
out = []
def get(u):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=15)
        b = r.read(); return r.status, r.headers.get("content-type"), len(b), b[:4]
    except Exception as e:
        return str(e)[:60], None, 0, b""
import yfinance as yf
for t in T:
    row = {"t": t}
    row["fmp"] = get(f"https://financialmodelingprep.com/image-stock/{t}.png")[:3]
    try:
        w = (yf.Ticker(t).info or {}).get("website") or ""
    except Exception as e:
        w = ""
    row["web"] = w
    dom = w.split("//")[-1].split("/")[0].replace("www.", "") if w else ""
    if dom:
        row["gfav"] = get(f"https://www.google.com/s2/favicons?domain={dom}&sz=128")[:3]
        row["ddg"] = get(f"https://icons.duckduckgo.com/ip3/{dom}.ico")[:3]
    out.append(row)
open("snapshot/logos.json", "w").write(json.dumps(out, indent=1, default=str))
print(json.dumps(out, default=str))
