"""Prüfung: angezeigte Meldezeit (earn_watch) gegen echte SEC-Eingangszeit (8-K Punkt 2.02)."""
import json, os, sys, time
import pandas as pd, requests
UA = {"User-Agent": f"Kairo {os.environ.get('SEC_CONTACT','').strip() or 'research'}", "Accept-Encoding": "gzip, deflate"}
pred = json.load(open(sys.argv[1]))
rows = []
for p in pred:
    try:
        f = requests.get(f"https://data.sec.gov/submissions/CIK{int(p['cik']):010d}.json", headers=UA, timeout=20).json()["filings"]["recent"]
    except Exception as e:
        rows.append({**p, "err": repr(e)}); continue
    time.sleep(0.15)
    act = None
    for i in range(min(60, len(f["form"]))):
        if f["form"][i] in ("8-K", "6-K") and ("2.02" in str(f["items"][i]) or f["form"][i] == "6-K"):
            x = pd.Timestamp(f["acceptanceDateTime"][i])
            d = x.tz_convert("America/New_York").date().isoformat()
            if abs((pd.Timestamp(d) - pd.Timestamp(p["date"])).days) <= 1:
                act = x.tz_convert("UTC").isoformat(); break
    mins = []
    for i in range(min(200, len(f["form"]))):
        if f["form"][i] == "8-K" and "2.02" in str(f["items"][i]):
            x = pd.Timestamp(f["acceptanceDateTime"][i]).tz_convert("America/New_York")
            if x.date().isoformat() < p["date"]:
                mins.append(x.hour * 60 + x.minute)
                if len(mins) == 4: break
    r = {**p, "act": act, "spread": (max(mins) - min(mins)) if len(mins) >= 2 else None}
    if act and p.get("ts"):
        r["diff_min"] = round((pd.Timestamp(act) - pd.Timestamp(p["ts"])).total_seconds() / 60)
    rows.append(r)
json.dump(rows, open(sys.argv[2], "w"), indent=0)
ok = [r for r in rows if "diff_min" in r]
for lab, sel in (("exact", [r for r in ok if r["exact"]]), ("yahoo", [r for r in ok if not r["exact"]])):
    ad = sorted(abs(r["diff_min"]) for r in sel)
    if ad: print(lab, len(ad), "median", ad[len(ad)//2], "<=15:", sum(a <= 15 for a in ad), ">60:", sum(a > 60 for a in ad))
ex = [r for r in ok if r["exact"] and r["spread"] is not None]
for lim in (30, 45, 60, 90):
    keep = [r for r in ex if r["spread"] <= lim]; drop = [r for r in ex if r["spread"] > lim]
    print(f"Grenze {lim}: behalten {len(keep)} (davon >60 Min daneben {sum(abs(r['diff_min'])>60 for r in keep)}, <=15 {sum(abs(r['diff_min'])<=15 for r in keep)}), raus {len(drop)} (davon gut <=15: {sum(abs(r['diff_min'])<=15 for r in drop)})")
for r in sorted(ok, key=lambda r: -abs(r["diff_min"]))[:30]:
    print(r["t"], r["date"], "exact" if r["exact"] else "yahoo", "spread", r.get("spread"), "pred", r["ts"], "act", r["act"], r["diff_min"])
print("ohne SEC-Treffer:", [r["t"] for r in rows if not r.get("act")])
