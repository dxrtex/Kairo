"""Push-Mitteilungen aufs iPad – nur wenn es wichtig ist (Web Push, siehe webpush.py).

Stop erreicht, Kursziel erreicht, Verkaufstag (Tag 20 bzw. 40), Schluss unter der EMA 20 (4H-Trades ab Tag 10), K.-o. nah/erreicht,
4H-Bestätigung, Watchlist-Aktie wird Fast-Treffer (10/11) oder Treffer (11/11). Läuft tagsüber alle 30 Minuten (alerts.yml)
und nach dem Abendscan; jede Meldung kommt nur einmal (state/push_sent.json).

Einrichtung (einmalig): In der App unter Einstellungen → Mitteilungen aktivieren, den angezeigten Code kopieren und als
GitHub-Secret PUSH_SUBS speichern; zusätzlich VAPID_PRIVATE_KEY. Der Code enthält das Abo des Geräts und – optional –
offene Trade-Pläne (Basiswert, Stop, Ziel, K.-o., Verkaufstag) und Depot (Basiswert, K.-o.), keine Beträge. Er liegt nur in den Secrets, nie im Repo.
"""

from __future__ import annotations

import json
import os

from . import webpush

_OWNER, _, _NAME = os.environ.get("GITHUB_REPOSITORY", "dxrtex/Kairo").partition("/")
APP = f"https://{_OWNER.lower()}.github.io/{_NAME}/"


def _num(x) -> str:
    return "–" if x is None else f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(x: float) -> str:
    return f"{x * 100:.1f} %".replace(".", ",")


def _hit(df, since, col, fn):
    """Tiefst-/Höchstkurs seit dem Kauftag (Tageskerzen inkl. laufendem Tag)."""
    x = df[df.index >= since] if since else df.tail(1)
    v = x[col].dropna()
    return float(fn(v)) if len(v) else None


def messages(dev: dict, prices: dict, today: str, sent: dict) -> list[dict]:
    """Nur Wichtiges: Stop erreicht, Take-Profit erreicht, Verkaufstag, K.-o. nah/erreicht. Jede Meldung nur einmal (sent)."""
    out = []

    def add(key, title, body, sec="entry"):
        if key in sent:
            return
        sent[key] = today
        out.append({"title": title, "body": body, "url": APP + f"?sec={sec}", "tag": "kairo-" + key.split(":")[0]})

    for p in dev.get("p") or []:                       # offene Trade-Pläne (Einstieg)
        t, df = p.get("t"), prices.get(p.get("t"))
        n, cur = (p.get("n") or t or "")[:28], p.get("cur") or ""
        if not t:
            continue
        x = p.get("x")
        if x and x <= today and today <= (p.get("x2") or "9999") and x >= _days_ago(today, 10):
            add(f"exit:{p.get('i')}", f"📆 Verkaufstag: {n}", "Tag 20 erreicht – laut Kairo-Strategie heute verkaufen (Turbo im Depot verkaufen, Trade im Journal schließen).")
        if df is None or not len(df):
            continue
        ex = ema_exit(df, p.get("d"), today) if p.get("e") else None
        if ex:                                         # 4H-Trade: ab Tag 10 Schluss unter der EMA 20 → zur nächsten Eröffnung verkaufen
            add(f"ema:{p.get('i')}", f"📉 Verkaufen: {n} – Schluss unter der EMA 20",
                f"Tag {ex['day']}: Schluss {_num(ex['c'])} {cur} unter der EMA 20 ({_num(ex['ema'])} {cur}). Laut 4H-Regel zur nächsten Eröffnung "
                "verkaufen – egal ob Gewinn oder Verlust (Turbo im Depot verkaufen, Trade im Journal schließen).")
        lo, hi = _hit(df, p.get("d"), "Low", min), _hit(df, p.get("d"), "High", max)
        if p.get("sl") and lo is not None and lo <= p["sl"]:
            add(f"sl:{p.get('i')}", f"🛑 Stop erreicht: {n}", f"Tief {_num(lo)} {cur} unter dem Stop {_num(p['sl'])} {cur}. Prüfe, ob die Stop-Order ausgeführt wurde, und schließe den Trade im Journal.")
        elif p.get("tp") and hi is not None and hi >= p["tp"]:
            add(f"tp:{p.get('i')}", f"🎯 Kursziel erreicht: {n}", f"Hoch {_num(hi)} {cur} über dem Ziel {_num(p['tp'])} {cur} – Gewinn mitnehmen oder Teilverkauf.")
        c = float(df["Close"].dropna().iloc[-1])
        if p.get("ko") and c > 0:
            _ko(add, n, c, float(p["ko"]), "long", today, cur, "entry")
    for d in dev.get("d") or []:                       # Depot: K.-o.-Schwelle
        df = prices.get(d.get("t"))
        if not d.get("ko") or df is None or not len(df):
            continue
        _ko(add, (d.get("n") or d["t"])[:28], float(df["Close"].dropna().iloc[-1]), float(d["ko"]), d.get("dir", "long"), today, "", "depot")
    return out


def ema_exit(df, since: str | None, today: str, span: int = 20, start: int = 10) -> dict | None:
    """Letzter fertiger Tagesschluss (vor heute) unter der EMA 20 und mindestens Tag 10 des Trades (Kauftag = Tag 1)?"""
    import numpy as np
    if not since:
        return None
    c = df["Close"].dropna()
    c = c[[str(i) < today for i in c.index]]
    if len(c) < span:
        return None
    ema = c.ewm(span=span, adjust=False).mean()
    d = str(c.index[-1])
    day = int(np.busday_count(since, d)) + 1
    if day < start or d < since or not float(c.iloc[-1]) < float(ema.iloc[-1]):
        return None
    return {"day": day, "c": float(c.iloc[-1]), "ema": float(ema.iloc[-1]), "d": d}


def _ko(add, n, c, ko, direction, today, cur, sec):
    dist = (c - ko) / c if direction == "long" else (ko - c) / c
    if dist <= 0:
        add(f"kohit:{n}:{ko}", f"💥 K.-o. erreicht: {n}", f"Kurs {_num(c)} {cur} hat die K.-o.-Schwelle {_num(ko)} {cur} erreicht.", sec)
    elif dist < 0.05:
        add(f"ko:{n}:{ko}:{today}", f"⚠️ K.-o. nah: {n}", f"Nur noch {_pct(dist)} bis zur K.-o.-Schwelle {_num(ko)} {cur} (Kurs {_num(c)}).", sec)


def _days_ago(today: str, n: int) -> str:
    from datetime import date, timedelta
    return (date.fromisoformat(today) - timedelta(days=n)).isoformat()


def prices_for(devs: list[dict]) -> dict:
    """Tageskerzen (inkl. laufendem Handelstag, ~15 Min. verzögert) für alle Basiswerte aus Plänen und Depot."""
    import yfinance as yf
    ts = sorted({x.get("t") for dev in devs for x in (dev.get("p") or []) + (dev.get("d") or [])
                 if x.get("t") and not str(x.get("t")).startswith("~")})
    if not ts:
        return {}
    h = yf.download(ts, period="6mo", interval="1d", group_by="ticker", auto_adjust=False, progress=False, threads=True)   # 6 Monate: EMA 20 eingeschwungen
    out = {}
    for t in ts:
        try:
            df = h[t] if len(ts) > 1 else h
            df = df.dropna(subset=["Close"])
            df.index = [str(i.date()) for i in df.index]
            out[t] = df
        except Exception:
            pass
    return out


def synced(dev: dict) -> dict:
    """Mit Kairo-Kursdienst: aktuelle offene Trades und Depot dort abholen (die App speichert sie bei jeder Änderung).
    Ohne Antwort bleibt der Stand aus dem Secret."""
    url, key = dev.get("sync"), dev.get("key")
    if not url or not key:
        return dev
    try:
        import requests
        r = requests.get(f"{url.rstrip('/')}/trades", params={"key": key}, timeout=15)
        j = r.json() if r.ok else {}
        if isinstance(j.get("p"), list) and isinstance(j.get("d"), list):
            print(f"Push: Trades vom Kursdienst – {len(j['p'])} offen, {len(j['d'])} im Depot")
            return {**dev, "p": j["p"], "d": j["d"]}
        print(f"Push: Kursdienst ohne Trades ({r.status_code}) – Stand aus dem Secret")
    except Exception as exc:
        print(f"Push: Kursdienst nicht erreichbar ({exc!r}) – Stand aus dem Secret")
    return dev


def etf_message(today: str, sent: dict) -> list[dict]:
    """ETF-Ampel: Mitteilung nur, wenn sie auf Grün bzw. Dunkelgrün springt (höchstens einmal je Farbe und Monat)."""
    try:
        import yfinance as yf
        from . import etf
        d = yf.download([etf.TICKER, "^VIX", "HYG", "IEF"], period="2y", interval="1d", auto_adjust=True, progress=False)["Close"]
        e = etf.compute(d[etf.TICKER].to_frame("Close"), d["^VIX"], d["HYG"], d["IEF"])
    except Exception as exc:
        print(f"Push: ETF-Ampel nicht berechnet ({exc!r})")
        return []
    lv, prev = e.get("lv"), sent.get("etf:last")
    sent["etf:last"] = lv or prev
    key = f"etf:{lv}:{today[:7]}"
    if lv not in ("yellow", "green2") or lv == prev or key in sent:
        return []
    sent[key] = today
    ic = "🟢" if lv == "green2" else "🟡"
    return [{"title": f"{ic} ETF-Ampel: {e['t']}", "body": f"SPYI {_num(e['c'])} € · {_pct(e['dd'])} unter dem Hoch · VIX {e.get('vix') or '–'}. Die Sparrate läuft weiter.",
             "url": APP + "?sec=etf", "tag": "kairo-etf"}]


def h4_update(today: str) -> list[dict]:
    """4H-Top-Setup tagsüber: Kairo-Treffer, die auf die 4H-Bestätigung warten, nach jeder abgeschlossenen 4H-Kerze neu
    prüfen. Kandidaten aus dem Abendscan (h4.json), Ergebnis für die App in state/h4live.json (Branch kairo-alerts)."""
    from datetime import datetime, timezone
    import pandas as pd
    from . import h4live, state
    try:
        loc = __import__("pathlib").Path(__file__).resolve().parents[1] / "site" / "data" / "h4.json"
        if loc.exists():
            base = json.loads(loc.read_text(encoding="utf-8"))
        else:
            import requests
            base = requests.get(APP + "data/h4.json", timeout=30).json()
    except Exception as exc:
        print(f"4H: Kandidaten nicht geladen ({exc!r})")
        return []
    # Basis entsteht erst zum Tagesschluss (Abendscan) – tagsüber nur, wer auf 4H wartet oder läuft (Stop untertags).
    # Alle Stufen (11/11, 10/11, 9/11); Mitteilungen nur für echte Einstiege (h4_messages)
    cands = [{k: it.get(k) for k in ("t", "n", "d", "cur", "soft", "grp") if it.get(k) is not None} for it in base.get("items") or []
             if it.get("st") in ("4h", "go", "run", "sell")]
    if not cands:
        state.save("h4live.json", {"generated": datetime.now(timezone.utc).isoformat(timespec="minutes"), "items": []})
        print("4H: keine offenen Kandidaten")
        return []
    import yfinance as yf
    ts = sorted({c["t"] for c in cands})
    h = yf.download(ts, period="1y", interval="1d", group_by="ticker", auto_adjust=True, progress=False, threads=True)
    daily = {}
    for t in ts:
        try:
            df = (h[t] if isinstance(h.columns, pd.MultiIndex) else h)[["Open", "High", "Low", "Close"]].dropna()
            df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
            daily[t] = df[df.index < pd.Timestamp(today)]            # laufender Tag: noch keine fertige Tageskerze
        except Exception:
            pass
    now = datetime.now(timezone.utc)
    items = h4live.build(cands, daily, h4live.hourly(ts), now, intraday=True)
    state.save("h4live.json", {"generated": now.isoformat(timespec="minutes"), "items": items})
    print("4H: " + ", ".join(f"{it['t']} {it['st']}" for it in items))
    return items


def h4_messages(items: list[dict], today: str, sent: dict, rk: float | None) -> list[dict]:
    """Nur eine Mitteilung je Treffer: wenn die 4H-Bestätigung da ist (Kauf zur Eröffnung der nächsten 4H-Kerze)."""
    out = []
    for it in items:
        if (it.get("grp") or "11") not in ("11", "10s"):
            continue                                   # 10/11 und 9/11: nur Status in der App, keine Mitteilung
        tr = it.get("trade") or {}
        fresh = it["st"] == "go" or (it["st"] == "run" and (tr.get("day") or 99) <= 1)
        key = f"h4:{it['t']}:{it['d']}"
        if not fresh or key in sent:
            continue
        sent[key] = today
        cur = it.get("cur") or ""
        sl = (it.get("base") or {}).get("sl")
        px = tr.get("e") or (it.get("trig") or {}).get("c")
        n = (it.get("n") or it["t"])[:28]
        if not sl or not px:
            continue
        dist = px - sl
        b = it.get("base") or {}
        gate = (f" Nur kaufen, wenn die Eröffnung zwischen {_num(b.get('lo'))} und {_num(b.get('hi'))} {cur} liegt – sonst verfällt das Setup."
                if b.get("pending") and it["st"] == "go" else "")
        qty = (f" · bei {rk:.0f} € Risiko ≈ {int(rk / dist)} Aktien" if rk and cur == "EUR" else f" · Risiko je Aktie {_num(dist)} {cur}") + " – Turbo-Stückzahl im Einstieg"
        out.append({"title": f"✅ 4H bestätigt: {n} – Einstieg",
                    "body": f"{'Fast-Treffer (nur MBI-Abklingen fehlt, getrennt gezählt)' if it.get('soft') else 'Kairo-Treffer'} + Seitwärtsphase + 4H (RSI, MACD, MBI, Strukturbruch). Kauf jetzt bzw. zur nächsten Eröffnung "
                            f"(~{_num(px)} {cur}). Stop {_num(sl)} {cur} ({_pct(dist / px)} Abstand){qty}. Verkauf ab Tag 10 bei Schluss unter der EMA 20, "
                            f"spätestens Tag 40 – Kairo meldet sich.{gate}",
                    "url": APP + f"?sec=entry&t={it['t']}", "tag": "kairo-h4"})
    return out


def _short(label: str) -> str:
    return label.split(":")[0].split("(")[0].strip()


def watch_messages(today: str, rows: list[dict] | None = None) -> list[dict]:
    """Watchlist (data/watchlist.json): Mitteilung, wenn eine Aktie zum Fast-Treffer (10/11) oder Treffer (11/11) wird –
    nur beim Wechsel nach oben (Zustand in state/watch_state.json), je Firma einmal. Nur Vorbereitung, kein Kaufsignal."""
    from . import state
    if rows is None:
        try:
            loc = __import__("pathlib").Path(__file__).resolve().parents[1] / "site" / "data" / "results.json"
            if loc.exists():
                rows = json.loads(loc.read_text(encoding="utf-8")).get("results") or []
            else:
                import requests
                rows = requests.get(APP + "data/results.json", timeout=60).json().get("results") or []
        except Exception as exc:
            print(f"Watchlist: Ergebnisse nicht geladen ({exc!r})")
            return []
    lvl = {}
    for r in rows:
        if not r.get("in_watchlist"):
            continue
        n = (r.get("name") or r["ticker"])[:28]
        v = 2 if r.get("passed") else 1 if r.get("fast_hit") else 0
        if v > lvl.get(n, (0,))[0]:
            lvl[n] = (v, r)
    # Zustand je Firma: [Stufe, zuletzt gesehen] – eine Woche gemerkt, damit ein kurzes Hin und Her nicht doppelt meldet
    old = {n: x for n, x in state.load("watch_state.json", {}).items() if isinstance(x, list) and x[1] >= _days_ago(today, 7)}
    first = not old
    out = []
    for n, (v, r) in sorted(lvl.items(), key=lambda x: -x[1][0]):
        if v <= (old.get(n) or [0])[0]:
            continue
        t = r["ticker"]
        if v == 2:
            out.append({"_n": n, "title": f"⭐ Treffer aus deiner Watchlist: {n}",
                        "body": "Alle 11 Kriterien im Tageschart erfüllt. Noch nicht kaufen: erst die Seitwärtsphase (bis 10 Tage), dann die "
                                "4H-Bestätigung – dafür kommt eine eigene Mitteilung.",
                        "url": APP + f"?sec=entry&t={t}", "tag": "kairo-watch"})
        else:
            miss = ", ".join(_short(m) for m in (r.get("missing") or [])[:2]) or "ein Kriterium"
            out.append({"_n": n, "title": f"👀 Bald Treffer? {n} – 10 von 11",
                        "body": f"Fehlt nur noch: {miss}. " + ("Nur das MBI-Abklingen fehlt – darf ins 4H-Setup: Kairo meldet sich bei der 4H-Bestätigung."
                                if r.get("mbi_soft") else "Noch kein Kaufsignal – Kairo meldet sich, wenn es ein Treffer wird."),
                        "url": APP + f"?sec=entry&t={t}", "tag": "kairo-watch"})
    new = {n: [max(v, (old.get(n) or [0])[0]), today] for n, (v, r) in lvl.items() if v}
    state.save("watch_state.json", {**old, **new})
    if len(out) > 5:                                   # erste Prüfung bzw. viele auf einmal: eine Sammel-Mitteilung statt Flut
        names = [m["_n"] for m in out]
        out = [{"title": f"👀 Watchlist: {len(out)} Aktien kurz vor oder bei einem Treffer",
                "body": ", ".join(names[:10]) + (" …" if len(names) > 10 else "") + ". Details in der App unter Watchlist.",
                "url": APP + "?sec=scanner", "tag": "kairo-watch"}]
    print(f"Watchlist: {len(out)} Mitteilung(en){' (erste Prüfung)' if first else ''}")
    return [{k: v for k, v in m.items() if k != "_n"} for m in out]


def run(today_iso: str | None = None) -> dict:
    from datetime import datetime
    from . import state
    raw, key = os.environ.get("PUSH_SUBS"), os.environ.get("VAPID_PRIVATE_KEY")
    try:                                               # 4H-Status immer aktualisieren (auch ohne Mitteilungen – die App zeigt ihn)
        h4_items = h4_update(today_iso or datetime.now().strftime("%Y-%m-%d"))
    except Exception as exc:
        print(f"4H: Fehler {exc!r}")
        h4_items = []
    if not raw or not key:
        print("Push: nicht eingerichtet (Secrets PUSH_SUBS / VAPID_PRIVATE_KEY fehlen)")
        return {"enabled": False}
    try:
        devs = json.loads(raw)
        devs = devs if isinstance(devs, list) else [devs]
        k = webpush.private_key(key.strip())
    except Exception as exc:
        print(f"Push: Secret nicht lesbar ({exc!r})")
        return {"enabled": True, "ok": False}
    today = today_iso or datetime.now().strftime("%Y-%m-%d")
    devs = [synced(dev) for dev in devs]
    prices = prices_for(devs)
    sent = {k2: v for k2, v in state.load("push_sent.json", {}).items() if v >= _days_ago(today, 60)}
    n_sent = failed = 0
    etf_msg = etf_message(today, sent)
    h4_msg = h4_messages(h4_items, today, sent, next((d.get("rk") for d in devs if d.get("rk")), None))
    try:
        watch_msg = watch_messages(today)
    except Exception as exc:
        print(f"Watchlist: Fehler {exc!r}")
        watch_msg = []
    for dev in devs:
        sub = dev.get("s") or dev
        for msg in messages(dev, prices, today, sent) + etf_msg + h4_msg + watch_msg:
            try:
                st = webpush.send(sub, msg, k)
                n_sent += st in (200, 201, 202)
                failed += st not in (200, 201, 202)
                if st not in (200, 201, 202):
                    print(f"Push: Status {st}" + (" – Abo abgelaufen, in der App neu aktivieren" if st in (404, 410) else ""))
            except Exception as exc:
                failed += 1
                print(f"Push: Fehler {exc!r}")
    state.save("push_sent.json", sent)
    print(f"Push: {n_sent} Mitteilungen gesendet, {failed} fehlgeschlagen, {len(devs)} Gerät(e), {len(prices)} Kurse")
    return {"enabled": True, "ok": failed == 0, "sent": n_sent, "date": today}


if __name__ == "__main__":
    run()
