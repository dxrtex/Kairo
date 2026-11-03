"""Test: Europäische Sektor-ETFs (iShares STOXX Europe 600, Xetra) bei Yahoo verfügbar? Länge, letzter Tag, Volumen."""
import yfinance as yf
C = {"EXV1.DE": "Banken", "EXV3.DE": "Technologie", "EXV4.DE": "Gesundheit", "EXH1.DE": "Öl & Gas", "EXV2.DE": "Telekom",
     "EXH4.DE": "Industrie", "EXV6.DE": "Rohstoffe", "EXH3.DE": "Lebensmittel & Getränke", "EXH9.DE": "Versorger", "EXV5.DE": "Autos",
     "EXH5.DE": "Versicherungen", "EXV8.DE": "Bau & Material", "EXH7.DE": "Konsumgüter", "EXI5.DE": "Immobilien", "EXH2.DE": "Finanzdienste",
     "EXV9.DE": "Reisen & Freizeit", "EXH8.DE": "Einzelhandel", "EXV7.DE": "Chemie", "EXH6.DE": "Medien", "^STOXX": "STOXX 600", "^N225": "Nikkei 225",
     "^STOXX50E": "Euro Stoxx 50", "^GDAXI": "DAX"}
h = yf.download(list(C), period="2y", interval="1d", group_by="ticker", auto_adjust=True, progress=False, threads=True)
for t, n in C.items():
    try:
        df = h[t].dropna(subset=["Close"]); print(f"{t:10s} {n:24s} Tage {len(df):4d} letzter {df.index[-1].date()} Kurs {df['Close'].iloc[-1]:.2f} Vol {df['Volume'].iloc[-5:].mean():.0f}")
    except Exception as e:
        print(t, n, "FEHLT", repr(e)[:80])
