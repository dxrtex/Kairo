for (const u of ["https://stooq.com/q/l/?s=sap.de&f=sd2t2ohlcv&h&e=csv", "https://stooq.com/q/l/?s=sap.de+aapl.us&f=sd2t2ohlcv&h&e=csv",
                 "https://stooq.com/q/l/?s=sap.de,aapl.us&f=sd2t2ohlcv&h&e=csv", "https://stooq.pl/q/l/?s=sap.de&f=sd2t2ohlcv&h&e=csv",
                 "https://stooq.com/q/l/?s=sap.de&f=sd2t2ohlcp&h&e=csv", "https://stooq.com/q/l/?s=7203.jp&f=sd2t2ohlcv&h&e=csv"]) {
  for (const h of [{}, { "User-Agent": "Mozilla/5.0" }]) {
    try { const r = await fetch(u, { headers: h }); console.log(r.status, Object.keys(h).length, u.slice(8, 80), (await r.text()).slice(0, 160).replace(/\s+/g, " | ")); }
    catch (e) { console.log("ERR", u, String(e).slice(0, 80)); }
  }
}
