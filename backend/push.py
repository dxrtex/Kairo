"""Push-Mitteilungen aufs iPad – nur wenn es wichtig ist (Web Push, siehe webpush.py).

Stop erreicht, Kursziel erreicht, Verkaufstag (Tag 20), K.-o. nah/erreicht. Läuft tagsüber alle 30 Minuten (alerts.yml)
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
    h = yf.download(ts, period="2mo", interval="1d", group_by="ticker", auto_adjust=False, progress=False, threads=True)
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


def run(today_iso: str | None = None) -> dict:
    from datetime import datetime
    from . import state
    raw, key = os.environ.get("PUSH_SUBS"), os.environ.get("VAPID_PRIVATE_KEY")
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
    prices = prices_for(devs)
    sent = {k2: v for k2, v in state.load("push_sent.json", {}).items() if v >= _days_ago(today, 60)}
    n_sent = failed = 0
    for dev in devs:
        sub = dev.get("s") or dev
        for msg in messages(dev, prices, today, sent):
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
