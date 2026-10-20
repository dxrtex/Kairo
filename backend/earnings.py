"""Quartalszahlen für den Kalender: Ergebnis gegen Erwartung, Ausblick, Kursreaktion und eine regelbasierte Einschätzung.

Quellen (frei): Yahoo Finance über yfinance (Termine mit Uhrzeit, Gewinn je Aktie erwartet/gemeldet, Umsatz-Erwartung,
gemeldeter Umsatz), Google-News-Schlagzeilen für den Ausblick (Guidance). Die Umsatz-Erwartung gibt Yahoo nur VOR den
Zahlen her – deshalb merkt sich der Scan sie im Zustand (state/earn_est.json) und vergleicht nach dem Termin.

Einschätzung = Regel, keine Prognose: Überraschung beim Gewinn (± 3 %), beim Umsatz (± 1 %) und die Richtung des
Ausblicks (zählt doppelt – der Markt handelt die Zukunft). Die tatsächliche Kursreaktion steht immer daneben.
"""

from __future__ import annotations

import math
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pandas as pd

PAST_DAYS, NEXT_DAYS = 14, 21

GUIDE_UP = re.compile(
    r"\b(rais(es|ed|ing)?|lifts?|lifted|boosts?|boosted|hikes?|hiked|ups|increases?|increased)\b[^|]{0,45}\b(guidance|outlook|forecast|view|targets?)\b"
    r"|\b(guidance|outlook|forecast)\b[^|]{0,25}\b(above|tops|beats|ahead of)\b"
    r"|\b(strong|upbeat|bullish|upgraded|rosy|robust)\b[^|]{0,20}\b(guidance|outlook|forecast)\b"
    r"|\b(hebt|erhöht|erhoeht)\b[^|]{0,30}\b(prognose|ausblick|jahresziele?|ziele)\b", re.I)
GUIDE_DOWN = re.compile(
    r"\b(cuts?|lowers?|lowered|slash(es|ed)?|reduces?|reduced|trims?|trimmed|withdraws?|withdrew|pulls?|pulled)\b[^|]{0,45}\b(guidance|outlook|forecast|view|targets?)\b"
    r"|\b(guidance|outlook|forecast)\b[^|]{0,25}\b(below|misses|missed|disappoints?|weak|falls short)\b"
<<<<<<< HEAD
    r"|\b(weak|soft|disappointing|downbeat|gloomy|cautious|lowered)\b[^|]{0,20}\b(guidance|outlook|forecast)\b"
=======
    r"|\b(weak|soft|disappointing|downbeat|gloomy|lowered)\b[^|]{0,20}\b(guidance|outlook|forecast)\b"
>>>>>>> claude/earnings-live
    r"|\b(senkt|kappt|kassiert|streicht)\b[^|]{0,30}\b(prognose|ausblick|jahresziele?|ziele)\b", re.I)
GUIDE_KEEP = re.compile(
    r"\b(reaffirms?|reaffirmed|reiterates?|reiterated|maintains?|maintained|confirms?|confirmed)\b[^|]{0,45}\b(guidance|outlook|forecast|view)\b"
    r"|\bbestätigt\b[^|]{0,30}\b(prognose|ausblick|jahresziele?|ziele)\b", re.I)


def _num(v):
    try:
        v = float(v)
        return None if math.isnan(v) or math.isinf(v) else v
    except (TypeError, ValueError):
        return None


<<<<<<< HEAD
=======
def _about(title: str, m: re.Match, words: list[str]) -> bool:
    """Gehört der Treffer zur Firma? Firmenname höchstens 90 Zeichen davor (oder 40 danach), ohne Komma/Semikolon
    dazwischen – sonst geht es meist um eine andere Firma („JPMorgan slips, TSMC's cautious outlook“)."""
    tl = title.lower()
    for w in words:
        for k in [i.start() for i in re.finditer(re.escape(w), tl)]:
            if k <= m.start():
                gap = tl[k + len(w):m.start()]
                if m.start() - k <= 90 and not re.search(r"[,;]", gap):
                    return True
            elif k - m.end() <= 40 and not re.search(r"[,;]", tl[m.end():k]):
                return True
    return False


>>>>>>> claude/earnings-live
def guidance(items: list[tuple[str, str, str]], words: list[str], since: pd.Timestamp | None = None) -> dict | None:
    """Richtung des Ausblicks aus Schlagzeilen (Titel, Link, Datum), nur wenn die Firma im Titel vorkommt und die
    Meldung nach den Zahlen erschien (Vorschauen zählen nicht). +1 angehoben, −1 gesenkt, 0 bestätigt;
    widersprüchliche Treffer → die häufigere Richtung, bei Gleichstand keine Angabe."""
    from email.utils import parsedate_to_datetime
    words = [w.lower() for w in words if w and len(w) >= 3]
    hits = []
    for title, link, date in items:
        if since is not None and date:
            try:
                if pd.Timestamp(parsedate_to_datetime(date)) < since - pd.Timedelta(hours=2):
                    continue
            except Exception:
                pass
<<<<<<< HEAD
        tl = title.lower()
        if words and not any(w in tl for w in words):
            continue
        d = 1 if GUIDE_UP.search(title) else -1 if GUIDE_DOWN.search(title) else 0 if GUIDE_KEEP.search(title) else None
=======
        d = None
        for rx, val in ((GUIDE_UP, 1), (GUIDE_DOWN, -1), (GUIDE_KEEP, 0)):
            m = rx.search(title)
            if m and (not words or _about(title, m, words)):
                d = val
                break
>>>>>>> claude/earnings-live
        if d is not None:
            hits.append({"d": d, "t": title[:180], "u": link, "date": date})
    if not hits:
        return None
    up, down = sum(h["d"] == 1 for h in hits), sum(h["d"] == -1 for h in hits)
    d = 1 if up > down else -1 if down > up else (0 if not up else None)
    if d is None:
        return {"d": None, "t": "Widersprüchliche Schlagzeilen zum Ausblick", "src": hits[:2]}
    best = next(h for h in hits if h["d"] == d)
    return {"d": d, "t": best["t"], "u": best["u"], "date": best["date"], "n": len(hits)}


def assess(eps_s: float | None, rev_s: float | None, guide_d: int | None) -> dict | None:
    """Regel: Gewinn-Überraschung ±3 % → ±1, Umsatz ±1 % → ±1, Ausblick angehoben/gesenkt → ±2."""
    pts, why = 0.0, []
    if eps_s is not None:
        if eps_s >= .03:
            pts += 1; why.append("Gewinn über der Erwartung")
        elif eps_s <= -.03:
            pts -= 1; why.append("Gewinn unter der Erwartung")
        else:
            why.append("Gewinn im Rahmen der Erwartung")
    if rev_s is not None:
        if rev_s >= .01:
            pts += 1; why.append("Umsatz über der Erwartung")
        elif rev_s <= -.01:
            pts -= 1; why.append("Umsatz unter der Erwartung")
        else:
            why.append("Umsatz im Rahmen")
    if guide_d is not None:
        pts += 2 * guide_d
        why.append({1: "Ausblick angehoben", -1: "Ausblick gesenkt", 0: "Ausblick bestätigt"}[guide_d])
    if eps_s is None and rev_s is None and guide_d is None:
        return None
    lbl, tone = (("eher positiv", "green") if pts >= 2 else ("eher negativ", "red") if pts <= -2
                 else ("leicht positiv", "green") if pts >= 1 else ("leicht negativ", "red") if pts <= -1 else ("gemischt", "yellow"))
    return {"lbl": lbl, "tone": tone, "pts": pts, "why": why}


def reaction_day(ts: pd.Timestamp, idx: pd.DatetimeIndex) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    """(Vortag, Reaktionstag) im Handelskalender der Aktie: Zahlen vor 12 Uhr Ortszeit → Reaktion am selben Tag,
    sonst (während/nach Börsenschluss) am nächsten Handelstag."""
    if not len(idx):
        return None
    tz = idx.tz
    local = ts.tz_convert(tz) if (ts.tzinfo is not None and tz is not None) else ts.tz_localize(None) if ts.tzinfo is not None else ts
    day = local.normalize()
    days = idx.normalize()
    if local.hour < 12:
        after = idx[days >= day]
    else:
        after = idx[days > day]
    if not len(after):
        return None
    r = after[0]
    before = idx[idx < r]
    return (before[-1], r) if len(before) else None


def reaction(close: pd.Series, ts: pd.Timestamp) -> dict | None:
    close = close.dropna()
    rd = reaction_day(ts, close.index)
    if not rd:
        return None
    b, r = rd
    c0, c1, cl = float(close[b]), float(close[r]), float(close.iloc[-1])
    if c0 <= 0:
        return None
    out = {"day": str(r.date()), "d1": round(c1 / c0 - 1, 4)}
    if close.index[-1] > r:
        out["since"] = round(cl / c0 - 1, 4)
        out["to"] = str(close.index[-1].date())
    return out


def typical_move(close: pd.Series, past: list[pd.Timestamp]) -> float | None:
    """Ø absolute Kursbewegung am Reaktionstag der letzten (bis zu 8) Quartalszahlen."""
    mv = [abs(r["d1"]) for ts in past[:8] if (r := reaction(close, ts))]
    return round(sum(mv) / len(mv), 4) if len(mv) >= 3 else None


def _rss(q: str) -> list[tuple[str, str, str]]:
    url = "https://news.google.com/rss/search?hl=en-US&gl=US&ceid=US:en&q=" + urllib.parse.quote(q)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Kairo)"})
        x = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "replace")
    except Exception:
        return []
    out = []
    for it in re.findall(r"<item>(.*?)</item>", x, re.S):
        t = re.search(r"<title>(.*?)</title>", it, re.S)
        l = re.search(r"<link>(.*?)</link>", it, re.S)
        d = re.search(r"<pubDate>(.*?)</pubDate>", it, re.S)
        if t:
            title = re.sub(r"<!\[CDATA\[|\]\]>", "", t.group(1)).replace("&amp;", "&").replace("&#39;", "'").replace("&quot;", '"').strip()
            out.append((title, (l.group(1).strip() if l else ""), (d.group(1).strip() if d else "")))
    return out


def _words(name: str, ticker: str) -> list[str]:
    stop = {"inc", "inc.", "corp", "corp.", "corporation", "the", "group", "holding", "holdings", "plc", "ag", "se", "sa", "nv", "co", "ltd", "company", "n.v."}
    w = [x.strip(",.") for x in (name or "").split() if x.strip(",.").lower() not in stop]
    return ([w[0]] if w else []) + [ticker.split(".")[0]]


def _eps_table(tk) -> pd.DataFrame | None:
    for attempt in range(3):
        try:
            ed = tk.get_earnings_dates(limit=12)
            if ed is not None and len(ed):
                return ed
            return None
        except Exception:
            time.sleep(2 * (attempt + 1))
    return None


def _quarter_revenue(tk, report: pd.Timestamp) -> tuple[float | None, float | None]:
    """Gemeldeter Umsatz des Quartals, dessen Ende 0–100 Tage vor dem Termin liegt, und das Vorjahresquartal."""
    try:
        q = tk.quarterly_income_stmt
        row = q.loc["Total Revenue"]
    except Exception:
        return None, None
    rep = report.tz_localize(None) if report.tzinfo is not None else report
    cols = sorted([pd.Timestamp(c) for c in row.index], reverse=True)
    cur = next((c for c in cols if pd.Timedelta(0) <= rep.normalize() - c <= pd.Timedelta(days=100)), None)
    if cur is None:
        return None, None
    prev = next((c for c in cols if pd.Timedelta(days=330) <= cur - c <= pd.Timedelta(days=400)), None)
    return _num(row.get(cur)), (_num(row.get(prev)) if prev is not None else None)


<<<<<<< HEAD
def one(t: str, ev: dict, close: pd.Series | None, est_mem: dict, today: pd.Timestamp) -> tuple[dict | None, dict | None]:
    """Ergebnis-Datensatz für eine Aktie und ggf. die gemerkte Erwartung (für den Vergleich nach dem Termin)."""
=======
def one(t: str, ev: dict, close: pd.Series | None, est_mem: dict, today: pd.Timestamp, live: bool = False) -> tuple[dict | None, dict | None]:
    """Ergebnis-Datensatz für eine Aktie und ggf. die gemerkte Erwartung (für den Vergleich nach dem Termin).
    live=True (Prüfdienst tagsüber): nur frisch gemeldete Zahlen (≤ 3 Tage), ohne Vorschau – spart Abfragen."""
>>>>>>> claude/earnings-live
    import yfinance as yf

    tk = yf.Ticker(t)
    ed = _eps_table(tk)
    if ed is None:
        return None, None
    ed = ed.sort_index(ascending=False)
    rep_col, est_col = "Reported EPS", "EPS Estimate"
    reported = ed[ed[rep_col].notna()] if rep_col in ed else ed.iloc[0:0]
    upcoming = ed[ed[rep_col].isna()] if rep_col in ed else ed
    upcoming = upcoming[upcoming.index.tz_convert("UTC").tz_localize(None).normalize() >= today - pd.Timedelta(days=1)] if len(upcoming) else upcoming
<<<<<<< HEAD
=======
    if live:
        lt = reported.index[0] if len(reported) else None
        if lt is None or today - lt.tz_convert("UTC").tz_localize(None).normalize() > pd.Timedelta(days=3):
            return None, None                              # noch nichts gemeldet – erst die nächste Prüfung
        upcoming = upcoming.iloc[0:0]
>>>>>>> claude/earnings-live
    if close is None or len(close) < 30:
        try:
            close = tk.history(period="2y", auto_adjust=False)["Close"]
        except Exception:
            close = None
    rec: dict = {"t": t, "name": ev.get("name") or t}
    new_mem = None
    past_ts = list(reported.index)
    if close is not None and len(close):
        tm = typical_move(close, past_ts)
        if tm is not None:
            rec["move"] = tm
    beats = [(_num(r[est_col]), _num(r[rep_col])) for _, r in reported.head(8).iterrows()]
    beats = [(e, a) for e, a in beats if e is not None and a is not None]
    if len(beats) >= 4:
        rec["beat"] = [sum(a > e for e, a in beats), len(beats)]
    last = reported.index[0] if len(reported) else None
    last_day = (last.tz_convert("UTC").tz_localize(None).normalize() if last is not None else None)
    if last is not None and today - last_day <= pd.Timedelta(days=PAST_DAYS):
        r0 = reported.iloc[0]
        eps_e, eps_a = _num(r0[est_col]), _num(r0[rep_col])
        res = {"ts": last.isoformat(), "date": str(last.tz_convert(last.tz).date()), "eps_e": eps_e, "eps_a": eps_a}
        if eps_e not in (None, 0) and eps_a is not None:
            res["eps_s"] = round((eps_a - eps_e) / abs(eps_e), 4)
        rev_a, rev_py = _quarter_revenue(tk, last)
        mem = est_mem.get(t) or {}
        if rev_a is not None:
            res["rev_a"] = rev_a
            if rev_py:
                res["rev_yoy"] = round(rev_a / rev_py - 1, 4)
            if mem.get("rev") and abs((pd.Timestamp(mem.get("date", "1900-01-01")) - last_day).days) <= 7:
                res["rev_e"] = mem["rev"]
                res["rev_s"] = round(rev_a / mem["rev"] - 1, 4)
        g = guidance(_rss(f"{_words(ev.get('name') or t, t)[0]} guidance OR outlook OR forecast when:{PAST_DAYS + 1}d"), _words(ev.get("name") or t, t), last)
        if g:
            res["guide"] = g
        if close is not None and len(close):
            rx = reaction(close, last)
            if rx:
                res["rx"] = rx
        res["view"] = assess(res.get("eps_s"), res.get("rev_s"), (g or {}).get("d"))
        rec["last"] = res
    if len(upcoming):
        nx = upcoming.index[-1]                             # nächster Termin (älteste der noch offenen Zeilen)
        nxt = {"ts": nx.isoformat(), "date": str(nx.date()), "eps_e": _num(upcoming.iloc[-1][est_col])}
        nxt["when"] = "vor Börsenstart" if nx.hour < 9 else "nach Börsenschluss" if nx.hour >= 16 else None
        try:
            re_ = tk.get_revenue_estimate()
            if re_ is not None and "0q" in re_.index:
                q0 = re_.loc["0q"]
                nxt.update(rev_e=_num(q0.get("avg")), rev_n=_num(q0.get("numberOfAnalysts")), rev_g=_num(q0.get("growth")))
                if nxt.get("rev_e"):
                    new_mem = {"date": nxt["date"], "rev": nxt["rev_e"], "eps": nxt.get("eps_e"), "name": ev.get("name") or t,
                               "region": ev.get("region"), "watch": ev.get("watch", False), **({"big": True} if ev.get("big") else {})}
        except Exception:
            pass
        rec["next"] = nxt
    if "last" not in rec and "next" not in rec:
        return None, new_mem
    return rec, new_mem


<<<<<<< HEAD
=======
PAGES = "https://dxrtex.github.io/Kairo/data/"


def live_main(out_dir: str = "state", est_file: str | None = None) -> None:
    """Prüfdienst tagsüber (Workflow earnings.yml): Aktien mit Quartalstermin gestern/heute/morgen.
    Sobald Yahoo die Zahlen hat, landen Ergebnis, Ausblick und Einschätzung in earnings_live.json (Branch kairo-earnings);
    die App liest die Datei direkt – ohne auf den Abendscan zu warten."""
    import json
    from pathlib import Path

    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    f = out / "earnings_live.json"
    try:
        prev = json.loads(f.read_text(encoding="utf-8")).get("tickers", {})
    except Exception:
        prev = {}
    try:
        est = json.loads(Path(est_file).read_text(encoding="utf-8")) if est_file else {}
    except Exception:
        est = {}
    cal = json.loads(urllib.request.urlopen(PAGES + "calendar.json", timeout=60).read())
    now = pd.Timestamp.now(tz="UTC")
    today = now.tz_localize(None).normalize()
    todo = {}
    for e in cal.get("events", []):
        if e.get("kind") != "earnings" or not e.get("ticker"):
            continue
        d = pd.Timestamp(e["date"])
        if not (today - pd.Timedelta(days=2) <= d <= today + pd.Timedelta(days=1)):
            continue
        p = (prev.get(e["ticker"]) or {}).get("last") or {}
        done = p.get("date") == e["date"] and p.get("rx") and p.get("guide") and now - pd.Timestamp(p["ts"]) > pd.Timedelta(hours=36)
        if not done:                                       # fertig = Reaktion und Ausblick da, Termin > 36 h her
            todo.setdefault(e["ticker"], e)

    def job(item):
        t, ev = item
        try:
            return t, one(t, ev, None, est, today, live=True)[0]
        except Exception as exc:
            print(f"Quartalszahlen live {t}: Fehler {exc!r}")
            return t, None

    with ThreadPoolExecutor(max_workers=4) as ex:
        fresh = {t: rec for t, rec in ex.map(job, list(todo.items())) if rec and rec.get("last")}
    keep = {t: r for t, r in prev.items() if t not in fresh and pd.Timestamp((r.get("last") or {}).get("date", "1900-01-01")) >= today - pd.Timedelta(days=4)}
    allr = {**keep, **fresh}
    f.write_text(json.dumps({"generated": now.isoformat(timespec="seconds"), "tickers": allr}, ensure_ascii=False, separators=(",", ":"), default=str), encoding="utf-8")
    print(f"Quartalszahlen live: {len(todo)} Termine geprüft, {len(fresh)} mit Zahlen aktualisiert, {len(allr)} in der Datei")


>>>>>>> claude/earnings-live
def run(events: list[dict], frames: dict, est_mem: dict, extra: dict[str, dict] | None = None, workers: int = 6) -> tuple[dict, dict, list[dict]]:
    """Alle Quartalstermine im Fenster (−14 bis +21 Tage) plus `extra` (gemerkte/Schwergewichte).
    Rückgabe: (earnings.json-Inhalt, neue Erwartungs-Merkliste, vergangene Termine für den Kalender)."""
    today = pd.Timestamp.now().normalize()
    todo: dict[str, dict] = {}
    for e in events:
        if e.get("kind") == "earnings" and e.get("ticker"):
            d = pd.Timestamp(e["date"])
            if today - pd.Timedelta(days=PAST_DAYS) <= d <= today + pd.Timedelta(days=NEXT_DAYS):
                todo.setdefault(e["ticker"], e)
    for t, e in (extra or {}).items():
        todo.setdefault(t, e)

    def job(item):
        t, ev = item
        df = frames.get(t)
        close = df["Close"] if df is not None and "Close" in df else None
        try:
            return t, *one(t, ev, close, est_mem, today)
        except Exception as exc:
            print(f"Quartalszahlen {t}: Fehler {exc!r}")
            return t, None, None

    out, mem = {}, {k: v for k, v in est_mem.items() if pd.Timestamp(v.get("date", "1900-01-01")) >= today - pd.Timedelta(days=30)}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for t, rec, nm in ex.map(job, list(todo.items())):
            if rec:
                out[t] = rec
            if nm:
                mem[t] = nm
    past = []
    for t, rec in out.items():
        if "last" in rec:
            ev = todo[t]
            past.append({"ticker": t, "name": ev.get("name") or t, "region": ev.get("region"), "watch": ev.get("watch", False),
                         **({"big": True} if ev.get("big") else {}), "kind": "earnings", "date": rec["last"]["date"], "done": True})
    n_last = sum("last" in r for r in out.values())
    print(f"Quartalszahlen: {len(todo)} Aktien geprüft, {n_last} mit frischen Ergebnissen, {len(out) - n_last} nur Vorschau")
    return {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "tickers": out}, mem, past
<<<<<<< HEAD
=======


if __name__ == "__main__":
    import sys
    live_main(*(sys.argv[1:3]))
>>>>>>> claude/earnings-live
