import requests, re
UAS = ["Kairo Scanner kairo-bot@users.noreply.github.com", "Kairo Research admin@kairo-app.de", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"]
URLS = ["https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&owner=include&count=40&output=atom",
        "https://www.sec.gov/Archives/edgar/daily-index/2026/QTR4/",
        "https://efts.sec.gov/LATEST/search-index?q=%22%22&forms=4&dateRange=custom&startdt=2026-10-08&enddt=2026-10-09",
        "https://data.sec.gov/submissions/CIK0001069183.json",
        "http://openinsider.com/latest-insider-purchases-25k",
        "http://openinsider.com/screener?s=&o=&pl=&ph=&ll=&lh=&fd=7&fdr=&td=0&tdr=&fdlyl=&fdlyh=&daysago=&xp=1&vl=50&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=100&page=1"]
for u in URLS:
    for ua in UAS:
        try:
            r = requests.get(u, headers={"User-Agent": ua, "Accept-Encoding": "gzip, deflate"}, timeout=20)
            print(r.status_code, len(r.text), ua[:22], u[:70], repr(r.text[:80]) if r.status_code != 200 else "")
        except Exception as e:
            print("ERR", ua[:22], u[:70], repr(e)[:80])
r = requests.get(URLS[-1], headers={"User-Agent": UAS[2]}, timeout=20)
i = r.text.find("tinytable"); print(r.text[i:i+3000])
