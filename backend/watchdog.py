"""Ausfall-Warnung: schlägt ein wichtiger Ablauf fehl (Scan, Mitteilungen, Papier-Handel), kommt eine Mitteilung aufs iPad.

python -m backend.watchdog "<Ablauf>" "<Link zum Lauf>"   (Secrets PUSH_SUBS / VAPID_PRIVATE_KEY wie backend.push)
"""

from __future__ import annotations

import json
import os
import sys

from . import webpush

SHORT = {"Täglicher Scan": "Täglicher Scan", "Wichtige Mitteilungen (tagsüber)": "Mitteilungen"}


def message(name: str, url: str) -> dict:
    n = SHORT.get(name, "Papier-Handel" if name.startswith("Papier-Handel") else name)
    return {"title": f"⚠️ Kairo: {n} fehlgeschlagen",
            "body": "Der Ablauf ist abgebrochen – die App zeigt evtl. alte Daten. Details im Lauf auf GitHub.",
            "url": url, "tag": "kairo-ausfall"}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    name, url = argv[0], argv[1] if len(argv) > 1 else ""
    raw, key = os.environ.get("PUSH_SUBS"), os.environ.get("VAPID_PRIVATE_KEY")
    if not raw or not key:
        print("Ausfall-Warnung: Push nicht eingerichtet")
        return 0
    devs = json.loads(raw)
    devs = devs if isinstance(devs, list) else [devs]
    k = webpush.private_key(key.strip())
    ok = 0
    for dev in devs:
        try:
            ok += webpush.send(dev.get("s") or dev, message(name, url), k) in (200, 201, 202)
        except Exception as exc:
            print(f"Ausfall-Warnung: Fehler {exc!r}")
    print(f"Ausfall-Warnung „{name}“: an {ok}/{len(devs)} Gerät(e) gesendet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
