"""Trendlinien wie in der Auto-Analyse der App (autoTA in site/index.html, Teil 1) – für den Watchlist-Alarm.

Steigende Unterstützung aus zwei Tiefs, fallender Widerstand aus zwei Hochs (Wendepunkte ±5 Kerzen, letzte 260 Kerzen),
kein Schlusskurs dazwischen deutlich jenseits der Linie, möglichst viele Berührungen. Ein Bruch zählt, wenn der letzte
Schlusskurs mehr als 0,3 ATR jenseits der Linie liegt. Reine Information – die Kairo-Regel nutzt das nicht.
"""

from __future__ import annotations

import numpy as np


def _atr(h, l, c, n=14):
    s = 0.0
    for i in range(len(c) - n, len(c)):
        s += max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    return s / n


def _pivots(a, lo, start, W=5):
    n, out = len(a), []
    for i in range(max(start, W), n - 2):
        v = a[i]
        if v != v:
            continue
        seg = a[i - W: min(n, i + W + 1)]
        if (lo and np.nanmin(seg) >= v) or (not lo and np.nanmax(seg) <= v):   # wie die App: kein Nachbar tiefer/höher
            out.append((i, float(v)))
    return out


def _line(P, lo, c, atr, last):
    n, best = len(c), None
    for a in range(len(P)):
        for b in range(a + 1, len(P)):
            (ia, pa), (ib, pb) = P[a], P[b]
            if ib - ia < 10:
                continue
            m = (pb - pa) / (ib - ia)
            if (lo and m <= 0) or (not lo and m >= 0):
                continue
            bad = False
            for i in range(ia, n):
                x = pa + m * (i - ia)
                if (c[i] < x - .35 * atr) if lo else (c[i] > x + .35 * atr):
                    if i <= ib + 2 or i < n - 3:
                        bad = True
                        break
            if bad:
                continue
            touch = sum(1 for (iq, pq) in P if iq >= ia and abs(pq - (pa + m * (iq - ia))) <= .5 * atr)
            now = pa + m * (n - 1 - ia)
            dist = (last - now) / last
            if abs(dist) > .12:
                continue
            sc = touch * 2 + ib / n
            if best is None or sc > best["sc"]:
                best = {"sc": sc, "now": now, "touch": touch, "dist": dist, "from": ia}
    return best


def trendlines(df) -> dict | None:
    """{"sup": {now, touch, dist}, "res": {...}, "brk": "down"|"up"|None} aus Tageskerzen (Spalten High/Low/Close)."""
    if df is None or len(df) < 80:
        return None
    h, l, c = (df[k].to_numpy(dtype=float) for k in ("High", "Low", "Close"))
    n, last = len(c), float(c[-1])
    if not last > 0:
        return None
    atr = _atr(h, l, c)
    start = max(0, n - 260)
    sup = _line(_pivots(l, True, start), True, c, atr, last)
    res = _line(_pivots(h, False, start), False, c, atr, last)
    brk = "down" if sup and last < sup["now"] - .3 * atr else "up" if res and last > res["now"] + .3 * atr else None
    r = lambda x: {"now": round(x["now"], 4), "touch": x["touch"], "dist": round(x["dist"], 4)} if x else None
    return {"sup": r(sup), "res": r(res), "brk": brk}
