import json
import yfinance as yf
for t in ["RHM.DE", "TSM", "NVDA", "SAP.DE", "ENR.DE", "AAPL", "BABA", "AMD", "AVGO", "IREN", "MSFT", "META", "ASML", "TKA.DE"]:
    d = yf.Ticker(t).history(period="5y", auto_adjust=False).dropna(subset=["Open", "High", "Low", "Close"])
    json.dump({"t": [x.strftime("%Y-%m-%d") for x in d.index], "o": [round(float(v), 4) for v in d["Open"]], "h": [round(float(v), 4) for v in d["High"]],
               "l": [round(float(v), 4) for v in d["Low"]], "c": [round(float(v), 4) for v in d["Close"]], "v": [int(v) for v in d["Volume"]]},
              open("snapshot/long_" + t + ".json", "w"))
    print(t, len(d))
