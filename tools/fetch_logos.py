"""Firmenlogos für alle Aktien des Scans laden und als kleine PNG-Dateien ablegen.

Läuft in GitHub Actions (logos.yml), nie in der App. Kostenlose Quellen ohne Schlüssel, der Reihe nach:
  1. Financial Modeling Prep  image-stock/<TICKER>.png  (auch mit Heimatbörsen-Varianten, z. B. DEZ.DE → DEZ.F, US-ADR)
  2. Website der Firma (Yahoo) → Google-Favicon-Dienst in 256 px, danach DuckDuckGo-Icon
Ein Logo wird nur übernommen, wenn es scharf genug ist (≥ 48 px) und kein Platzhalter
(gleiches Bild bei vielen Aktien). Vorhandene Logos bleiben, neue kommen dazu.

Aufruf: python tools/fetch_logos.py <search.json> <ausgabe-ordner> [--limit N]
Ergebnis: <ordner>/<TICKER>.png und <ordner>/index.json (Liste der Ticker mit Logo).
"""
from __future__ import annotations

import concurrent.futures as cf
import hashlib
import io
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

import requests
from PIL import Image

UA = {"User-Agent": "Mozilla/5.0 (Kairo logo fetcher)"}
SIZE = 96
MIN_SRC = 48


def safe(t: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", t)


def get(url: str, timeout: float = 8.0) -> bytes | None:
    for i in range(2):
        try:
            r = requests.get(url, headers=UA, timeout=timeout)
            if r.status_code == 200 and r.content and len(r.content) > 120:
                return r.content
            if r.status_code in (404, 400, 403):
                return None
        except Exception:
            time.sleep(0.5 + i)
    return None


def normalize(raw: bytes) -> tuple[bytes, str] | None:
    """Bild prüfen, Rand beschneiden, auf SIZE×SIZE (transparent) einpassen. Gibt PNG und Bild-Hash zurück."""
    try:
        im = Image.open(io.BytesIO(raw))
        if getattr(im, "n_frames", 1) > 1:
            im.seek(0)
        if im.format == "ICO":
            im = im.ico.getimage(max(im.ico.sizes(), key=lambda s: s[0] * s[1]))  # größte Ebene
        im = im.convert("RGBA")
    except Exception:
        return None
    if max(im.size) < MIN_SRC or min(im.size) < 16:
        return None
    # einfarbige / leere Bilder verwerfen
    px = im.resize((16, 16)).getdata()
    vis = [p for p in px if p[3] > 24]
    if len(vis) < 6:
        return None
    # fast weißen oder transparenten Rand abschneiden
    bg = Image.new("RGBA", im.size, (255, 255, 255, 0))
    flat = Image.alpha_composite(Image.new("RGBA", im.size, (255, 255, 255, 255)), im).convert("L")
    mask = flat.point(lambda v: 255 if v < 245 else 0)
    alpha = im.split()[3].point(lambda v: 255 if v > 24 else 0)
    box = Image.composite(mask, Image.new("L", im.size, 0), alpha).getbbox() or alpha.getbbox()
    if box:
        im = im.crop(box)
    w, h = im.size
    s = (SIZE - 8) / max(w, h)
    im = im.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)
    out = bg.resize((SIZE, SIZE))
    out.paste(im, ((SIZE - im.size[0]) // 2, (SIZE - im.size[1]) // 2), im)
    buf = io.BytesIO()
    out.save(buf, "PNG", optimize=True)
    h8 = hashlib.sha1(out.resize((24, 24)).tobytes()).hexdigest()
    return buf.getvalue(), h8


def variants(t: str) -> list[str]:
    base, _, suf = t.partition(".")
    v = [t]
    if suf:
        if suf in ("DE", "F", "MU", "BE", "SG", "HM", "DU", "HA"):
            v += [f"{base}.DE", f"{base}.F"]
        v.append(base)  # oft das Heimat-/US-Kürzel
    return list(dict.fromkeys(v))


def domain(url: str) -> str:
    m = re.match(r"^(?:https?://)?(?:www\d?\.)?([^/:?#]+)", (url or "").strip())
    return m.group(1).lower() if m else ""


def website(t: str, company: dict) -> str:
    w = (company.get(t) or {}).get("web") or ""
    if w:
        return w
    try:
        import yfinance as yf
        return (yf.Ticker(t).get_info() or {}).get("website") or ""
    except Exception:
        return ""


def candidates(t: str, company: dict):
    for v in variants(t):
        yield "fmp", f"https://financialmodelingprep.com/image-stock/{v}.png"
    d = domain(website(t, company))
    if d:
        yield "gfav", f"https://www.google.com/s2/favicons?domain={d}&sz=256"
        yield "ddg", f"https://icons.duckduckgo.com/ip3/{d}.ico"


def fetch_one(t: str, company: dict, skip_hash: set[str]):
    for src, url in candidates(t, company):
        raw = get(url)
        if not raw:
            continue
        n = normalize(raw)
        if not n or n[1] in skip_hash:
            continue
        return t, src, n[0], n[1]
    return t, None, None, None


def main() -> None:
    a = sys.argv[1:]
    if len(a) < 2:
        print(__doc__)
        sys.exit(2)
    search, out = Path(a[0]), Path(a[1])
    limit = int(a[a.index("--limit") + 1]) if "--limit" in a else 100000
    out.mkdir(parents=True, exist_ok=True)
    rows = json.loads(search.read_text())["rows"]
    tickers = [r["t"] for r in rows if r.get("t")]
    extra = Path("data/watchlist.json")
    if extra.exists():
        for k, v in json.loads(extra.read_text()).items():
            if isinstance(v, list):
                tickers += v
    tickers = list(dict.fromkeys(tickers))
    company = {}
    if Path("data/company.json").exists():
        try:
            company = json.loads(Path("data/company.json").read_text())
        except Exception:
            company = {}

    meta_p = out / "meta.json"
    meta = json.loads(meta_p.read_text()) if meta_p.exists() else {}
    # Platzhalter-Erkennung: Bilder, die bei vielen Aktien gleich aussehen
    counts = Counter(m.get("h") for m in meta.values() if m.get("h"))
    skip = {h for h, c in counts.items() if c >= 4}
    for t, m in list(meta.items()):
        if m.get("h") in skip:
            (out / f"{safe(t)}.png").unlink(missing_ok=True)
            meta.pop(t)
    now = time.time()
    # neu versuchen: ohne Logo, und Fehlversuche frühestens nach 7 Tagen erneut
    todo = [t for t in tickers if t not in meta or (not meta[t].get("src") and now - meta[t].get("at", 0) > 7 * 86400)]
    todo = todo[:limit]
    print(f"{len(tickers)} Aktien, {sum(1 for m in meta.values() if m.get('src'))} Logos vorhanden, {len(todo)} zu laden")
    got = Counter()
    with cf.ThreadPoolExecutor(12) as ex:
        for i, (t, src, png, h) in enumerate(ex.map(lambda t: fetch_one(t, company, skip), todo)):
            if src:
                (out / f"{safe(t)}.png").write_bytes(png)
                meta[t] = {"src": src, "h": h, "at": now}
            else:
                meta[t] = {"src": None, "at": now}
            got[src or "–"] += 1
            if i % 250 == 0:
                print(i, dict(got), flush=True)
    # zweiter Platzhalter-Durchgang über alle
    counts = Counter(m.get("h") for m in meta.values() if m.get("h"))
    for t, m in list(meta.items()):
        if m.get("h") and counts[m["h"]] >= 4:
            (out / f"{safe(t)}.png").unlink(missing_ok=True)
            meta[t] = {"src": None, "at": now}
    have = sorted(t for t, m in meta.items() if m.get("src") and (out / f"{safe(t)}.png").exists())
    meta_p.write_text(json.dumps(meta, separators=(",", ":")))
    (out / "index.json").write_text(json.dumps(have, separators=(",", ":")))
    print(f"fertig: {len(have)}/{len(tickers)} mit Logo ({100 * len(have) / max(1, len(tickers)):.1f} %) · neu: {dict(got)}")
    miss = [t for t in tickers if t not in set(have)]
    print("ohne Logo (Auszug):", " ".join(miss[:60]))


if __name__ == "__main__":
    main()
