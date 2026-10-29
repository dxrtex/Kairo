"""Quartalszahlen so schnell wie möglich (Nutzer-Wunsch 28.10.2026).

1. earn_watch.json (Branch kairo-earnings): Aktien mit Termin gestern/heute/morgen samt SEC-Nummer (CIK) und erwarteter
   Uhrzeit. Der Kairo-Kursdienst (Cloudflare, Version 6) fragt damit jede Minute die SEC ab: Sobald die Firma ihre Zahlen
   offiziell meldet (Formular 8-K Punkt 2.02, bei ausländischen Firmen 6-K), weckt er sofort die Prüfung (earnings.yml).
2. Mitteilungen: „Zahlen sind raus“ direkt nach der SEC-Meldung und „Ergebnis“ sobald Yahoo die Werte hat –
   nur für Aktien aus Watchlist, Depot und offenen Trades, jede nur einmal (earn_push_sent.json).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from .config import ROOT

APP = "https://dxrtex.github.io/Kairo/?sec=calendar"


def ciks() -> dict:
    try:
        return json.loads((ROOT / "data" / "sec_cik.json").read_text(encoding="utf-8"))["cik"]
    except Exception:
        return {}


def _sec_ua() -> dict:
    c = os.environ.get("SEC_CONTACT", "").strip()
    return {"User-Agent": f"Kairo {c}" if c else "Mozilla/5.0 (Kairo)", "Accept-Encoding": "gzip, deflate"}


def typical_time(cik: int) -> str | None:
    """Uhrzeit (New York, „HH:MM“), zu der die Firma ihre letzten Quartalszahlen bei der SEC eingereicht hat
    (8-K Punkt 2.02, Median der letzten 4). Firmen melden fast immer zur selben Zeit."""
    import requests
    try:
        f = requests.get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json", headers=_sec_ua(), timeout=20).json()["filings"]["recent"]
    except Exception:
        return None
    mins = []
    for i in range(min(200, len(f["form"]))):
        if f["form"][i] == "8-K" and "2.02" in str(f["items"][i]):
            x = pd.Timestamp(f["acceptanceDateTime"][i]).tz_convert("America/New_York")
            mins.append(x.hour * 60 + x.minute)
            if len(mins) == 4:
                break
    if len(mins) < 2:
        return None
    m = int(sorted(mins)[len(mins) // 2])
    return f"{m // 60:02d}:{m % 60:02d}"


def _times(tickers: dict, out: Path, today: pd.Timestamp) -> dict:
    """Gelernte Meldezeiten, einmal am Tag je Aktie neu (earn_times.json im Zustand)."""
    f = out / "earn_times.json"
    try:
        mem = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        mem = {}
    day = str(today.date())
    for t, cik in tickers.items():
        if (mem.get(t) or {}).get("on") != day:
            mem[t] = {"hm": typical_time(cik), "on": day}
    f.write_text(json.dumps(mem, separators=(",", ":")), encoding="utf-8")
    return {t: (mem.get(t) or {}).get("hm") for t in tickers}


def watch_file(events: list[dict], nexts: dict, out: Path, today: pd.Timestamp, learn: bool = True) -> int:
    """Termine gestern/heute/morgen mit CIK und erwarteter Zeit (UTC) für den Kursdienst.
    „exact“ = Uhrzeit aus den bisherigen SEC-Meldungen der Firma gelernt (enges Prüffenster im Kursdienst)."""
    cm, items = ciks(), []
    for e in events:
        t = e.get("ticker")
        if e.get("kind") != "earnings" or not t or t not in cm:
            continue
        d = pd.Timestamp(e["date"])
        if not (today - pd.Timedelta(days=1) <= d <= today + pd.Timedelta(days=1)):
            continue
        nx = nexts.get(t) or {}
        ts = None
        if nx.get("ts") and nx.get("date") == e["date"]:
            try:
                x = pd.Timestamp(nx["ts"])
                ts = (x.tz_convert("UTC") if x.tzinfo else x.tz_localize("America/New_York").tz_convert("UTC")).isoformat()
            except Exception:
                ts = None
        items.append({"t": t, "n": e.get("name") or t, "cik": cm[t], "date": e["date"], "ts": ts, "w": bool(e.get("watch"))})
    if learn:
        hm = _times({x["t"]: x["cik"] for x in items if x["t"] in cm and "." not in x["t"]}, out, today)
        for x in items:
            h = hm.get(x["t"])
            if not h:
                continue
            ny = pd.Timestamp(f"{x['date']} {h}").tz_localize("America/New_York")
            if x["ts"]:                                    # Yahoo sagt vor/nach Börse – passt die gelernte Zeit nicht dazu, lieber breit prüfen
                hint = pd.Timestamp(x["ts"]).tz_convert("America/New_York").hour
                if (hint < 12) != (ny.hour < 12):
                    continue
            x.update(ts=ny.tz_convert("UTC").isoformat(), exact=True)
    for x in items:                                       # Prüffenster für den Kursdienst (ab Version 6 maßgeblich)
        if x["ts"]:
            e = pd.Timestamp(x["ts"])
            a, b = (e - pd.Timedelta(minutes=20), e + pd.Timedelta(hours=3)) if x.get("exact") else (e - pd.Timedelta(hours=3), e + pd.Timedelta(hours=6))
        else:
            a = pd.Timestamp(x["date"] + " 09:00").tz_localize("UTC"); b = a + pd.Timedelta(hours=17)
        x.update({"from": a.isoformat(), "to": b.isoformat()})
    (out / "earn_watch.json").write_text(json.dumps({"generated": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"), "items": items},
                                                    ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return len(items)


def _devices():
    raw, key = os.environ.get("PUSH_SUBS"), os.environ.get("VAPID_PRIVATE_KEY")
    if not raw or not key:
        return [], None
    from . import webpush
    try:
        devs = json.loads(raw)
        return (devs if isinstance(devs, list) else [devs]), webpush.private_key(key.strip())
    except Exception as exc:
        print(f"Quartalszahlen-Push: Secret nicht lesbar ({exc!r})")
        return [], None


def mine(devs: list[dict], events: list[dict]) -> set:
    """Aktien, die Jonny betreffen: Watchlist (Kalender + Kursdienst-Sterne), Depot, offene Trades."""
    s = {e["ticker"] for e in events if e.get("kind") == "earnings" and e.get("watch") and e.get("ticker")}
    for dev in devs:
        url, key = dev.get("sync"), dev.get("key")
        if not url or not key:
            continue
        try:
            import requests
            j = requests.get(f"{url.rstrip('/')}/trades", params={"key": key}, timeout=15).json()
            for k in ("p", "d", "w"):                     # Einträge {"t": "AAPL", …}
                s |= {str(x.get("t") if isinstance(x, dict) else x).upper() for x in j.get(k) or []}
        except Exception as exc:
            print(f"Quartalszahlen-Push: Kursdienst nicht erreichbar ({exc!r})")
    s.discard("")
    return s


def _pct(x):
    return f"{'+' if x >= 0 else '−'}{abs(x) * 100:.1f} %".replace(".", ",")


def _odds(sur):
    try:
        st = json.loads((ROOT / "site" / "earn_stats.json").read_text(encoding="utf-8"))
        s = sur * 100
        b = next(b for b in st["buckets"] if b["lo"] <= s < b["hi"])
        return b["up1"]
    except Exception:
        return None


def result_text(t: str, name: str, last: dict) -> dict:
    parts = []
    if last.get("eps_s") is not None:
        parts.append(f"Gewinn {_pct(last['eps_s'])} vs. Erwartung")
    if last.get("rev_s") is not None:
        parts.append(f"Umsatz {_pct(last['rev_s'])}")
    g = (last.get("guide") or {}).get("d")
    if g is not None:
        parts.append({1: "Ausblick angehoben", -1: "Ausblick gesenkt", 0: "Ausblick bestätigt"}.get(g, "Ausblick unklar"))
    p = _odds(last["eps_s"]) if last.get("eps_s") is not None else None
    v = (last.get("view") or {}).get("lbl")
    body = " · ".join(parts) + (f". Nach solchen Zahlen stieg die Aktie in {round(p * 100)} % der Fälle." if p else "")
    return {"title": f"📊 {name}: {v or 'Zahlen da'}", "body": body or "Zahlen gemeldet – Details in Kairo.", "url": APP, "tag": f"kairo-earn-{t}"}


def send(msgs: list[dict], devs: list[dict], k) -> int:
    from . import webpush
    n = 0
    for dev in devs:
        for m in msgs:
            try:
                n += webpush.send(dev.get("s") or dev, m, k) in (200, 201, 202)
            except Exception as exc:
                print(f"Quartalszahlen-Push: Fehler {exc!r}")
    return n


def sec_pushes(hits: str, events: list[dict], out: Path) -> list[str]:
    """Sofort-Mitteilung nach der SEC-Meldung (vom Kursdienst übergeben: „AAPL,MSFT“)."""
    tick = [x.strip().upper() for x in (hits or "").split(",") if x.strip()]
    if not tick:
        return []
    devs, k = _devices()
    f = out / "earn_push_sent.json"
    sent = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    rel = mine(devs, events) if devs else set()
    names = {e["ticker"]: e.get("name") or e["ticker"] for e in events if e.get("ticker")}
    today = pd.Timestamp.now(tz="Europe/Berlin").strftime("%Y-%m-%d")
    msgs = []
    for t in tick:
        key = f"sec|{t}|{today}"
        if key in sent or (rel and t not in rel):
            continue
        sent[key] = today
        msgs.append({"title": f"📊 {names.get(t, t)}: Quartalszahlen sind raus", "body": "Offizielle Meldung bei der SEC – Ergebnis und Einschätzung folgen in Kairo in wenigen Minuten.",
                     "url": APP, "tag": f"kairo-earn-{t}"})
    if msgs and devs and k:
        print(f"Quartalszahlen: SEC-Mitteilung für {', '.join(m['title'] for m in msgs)} – {send(msgs, devs, k)} gesendet")
    f.write_text(json.dumps({a: b for a, b in sent.items() if b >= (pd.Timestamp(today) - pd.Timedelta(days=10)).strftime("%Y-%m-%d")}), encoding="utf-8")
    return tick


def result_pushes(fresh: dict, prev: dict, events: list[dict], out: Path) -> None:
    """Mitteilung, sobald Yahoo die Werte eines Termins zum ersten Mal hat."""
    new = {t: r for t, r in fresh.items() if (r.get("last") or {}).get("eps_a") is not None
           and ((prev.get(t) or {}).get("last") or {}).get("date") != r["last"]["date"]}
    if not new:
        return
    devs, k = _devices()
    if not devs or not k:
        return
    f = out / "earn_push_sent.json"
    sent = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    rel = mine(devs, events)
    msgs = []
    for t, r in new.items():
        key = f"res|{t}|{r['last']['date']}"
        if key in sent or t not in rel:
            continue
        sent[key] = r["last"]["date"]
        msgs.append(result_text(t, r.get("name") or t, r["last"]))
    if msgs:
        print(f"Quartalszahlen: Ergebnis-Mitteilung für {len(msgs)} Aktie(n) – {send(msgs, devs, k)} gesendet")
    f.write_text(json.dumps(sent), encoding="utf-8")


def archive(recs: dict, out: Path) -> int:
    """Sammelt jede Meldung dauerhaft (earn_archive.json): Gewinn- und Umsatz-Überraschung, Umsatz-Beschleunigung,
    Ausblick, Kursreaktion – damit sich in einigen Monaten testen lässt, ob Umsatz und Ausblick die Prognose verbessern."""
    f = out / "earn_archive.json"
    try:
        arc = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        arc = {}
    for t, r in recs.items():
        L = r.get("last") or {}
        if not L.get("date"):
            continue
        k = f"{t}|{L['date']}"
        row = {"s": L.get("eps_s"), "rs": L.get("rev_s"), "rg": L.get("revg"), "ra": L.get("reva"),
               "g": (L.get("guide") or {}).get("d"), "gs": (L.get("guide") or {}).get("src"), "r1": (L.get("rx") or {}).get("d1")}
        arc[k] = {**arc.get(k, {}), **{a: b for a, b in row.items() if b is not None}}
    f.write_text(json.dumps(arc, separators=(",", ":")), encoding="utf-8")
    return len(arc)
