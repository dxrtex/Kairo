"""Fed-Zinsentscheid live: sobald die Fed ihr Statement veröffentlicht, Entscheidung in die App (und als Mitteilung).

Quelle: federalreserve.gov – Statement-Seite des Tages (newsevents/pressreleases/monetaryJJJJMMTTa.htm).
Läuft im Prüfdienst (earnings.yml) und schreibt macro_live.json in den Branch kairo-earnings; die App liest die Datei
direkt (wie die Live-Quartalszahlen). Ohne Fed-Termin heute/gestern: nichts tun.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .macro import _get

URL = "https://www.federalreserve.gov/newsevents/pressreleases/monetary{d}a.htm"
PAGES = "https://dxrtex.github.io/Kairo/data/calendar.json"


def _rate(x: str) -> float:
    """„3-3/4“ → 3.75, „4“ → 4.0"""
    x = x.strip()
    m = re.fullmatch(r"(\d+)(?:-(\d+)/(\d+))?", x)
    if not m:
        raise ValueError(x)
    return int(m.group(1)) + (int(m.group(2)) / int(m.group(3)) if m.group(2) else 0)


def parse(html: str) -> dict | None:
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
    m = re.search(r"decided to (maintain|lower|raise|reduce|increase) the target range for the federal funds rate"
                  r"(?: by ([\d/ -]+?) percentage points?)? (?:at|to) ([\d/-]+) to ([\d/-]+) percent", text)
    if not m:
        return None
    verb = m.group(1)
    decision = "hold" if verb == "maintain" else "cut" if verb in ("lower", "reduce") else "hike"
    bp = None
    if m.group(2):
        b = m.group(2).strip()
        bp = round(100 * (eval_frac(b) if "/" in b and "-" not in b else _rate(b.replace(" ", ""))))
    lo, hi = _rate(m.group(3)), _rate(m.group(4))
    dis = re.search(r"Voting against (?:this|the) action (?:were|was):? (.+?)(?:, who|; |(?<!\b[A-Z])\.\s*$|(?<!\b[A-Z])\. (?=[A-Z][a-z]))", text)
    return {"decision": decision, "lo": lo, "hi": hi, "bp": bp, "dissent": dis.group(1).strip() if dis else None}


def eval_frac(b: str) -> float:
    n, d = b.split("/")
    return int(n) / int(d)


def _de(x: float) -> str:
    return f"{x:.2f}".replace(".", ",")


def headline(f: dict) -> str:
    rng = f"{_de(f['lo'])}–{_de(f['hi'])} %"
    if f["decision"] == "hold":
        return f"Fed lässt den Leitzins unverändert bei {rng}"
    verb = "senkt" if f["decision"] == "cut" else "erhöht"
    by = f" um {f['bp']} Basispunkte" if f.get("bp") else ""
    return f"Fed {verb} den Leitzins{by} auf {rng}"


def fed_today(cal: dict, today: str) -> bool:
    return any(e.get("date") == today and "Fed-Zinsentscheid" in (e.get("title") or "") for e in cal.get("events", []))


def main(out_dir: str = "state", force: str | None = None) -> None:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    f = out / "macro_live.json"
    try:
        prev = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        prev = {}
    now = datetime.now(timezone.utc)
    today = force or now.date().isoformat()
    if not force:
        try:
            import urllib.request
            cal = json.loads(urllib.request.urlopen(PAGES, timeout=60).read())
        except Exception as exc:
            print(f"Fed live: Kalender nicht geladen ({exc!r})")
            cal = {}
        if not fed_today(cal, today):
            print("Fed live: heute kein Zinsentscheid")
            return
    if (prev.get("fed") or {}).get("date") == today:
        print("Fed live: Entscheidung schon da –", prev["fed"].get("head"))
        return
    url = URL.format(d=today.replace("-", ""))
    try:
        html = _get(url)
    except Exception as exc:
        print(f"Fed live: Statement noch nicht online ({str(exc)[:80]})")
        return
    r = parse(html)
    if not r:
        print("Fed live: Statement gefunden, Entscheidung nicht lesbar")
        return
    r.update(date=today, url=url, ts=now.isoformat(timespec="seconds"), head=headline(r))
    prev["fed"] = r
    prev["generated"] = r["ts"]
    f.write_text(json.dumps(prev, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("Fed live:", r["head"])
    _push(r)


def _push(r: dict) -> None:
    raw, key = os.environ.get("PUSH_SUBS"), os.environ.get("VAPID_PRIVATE_KEY")
    if not raw or not key:
        return
    from . import webpush
    try:
        devs = json.loads(raw)
        devs = devs if isinstance(devs, list) else [devs]
        k = webpush.private_key(key.strip())
    except Exception as exc:
        print(f"Fed live: Push nicht möglich ({exc!r})")
        return
    body = "Statement der Fed ist raus." + (f" Gegenstimmen: {r['dissent']}." if r.get("dissent") else "") + " Pressekonferenz 30 Min. später."
    msg = {"title": "🏦 " + r["head"], "body": body, "url": "https://dxrtex.github.io/Kairo/?sec=calendar", "tag": "kairo-fed"}
    for dev in devs:
        try:
            print("Fed live: Push", webpush.send(dev.get("s") or dev, msg, k))
        except Exception as exc:
            print(f"Fed live: Push-Fehler {exc!r}")


if __name__ == "__main__":
    main(*(sys.argv[1:3]))
