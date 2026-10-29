"""Quartalszahlen für den Kalender: Ergebnis gegen Erwartung, Ausblick, Kursreaktion und eine regelbasierte Einschätzung.

Quellen (frei): Yahoo Finance über yfinance (Termine mit Uhrzeit, Gewinn je Aktie erwartet/gemeldet, Umsatz-Erwartung,
gemeldeter Umsatz), Google-News-Schlagzeilen für den Ausblick (Guidance). Die Umsatz-Erwartung gibt Yahoo nur VOR den
Zahlen her – deshalb merkt sich der Scan sie im Zustand (state/earn_est.json) und vergleicht nach dem Termin.

Einschätzung = Regel, keine Prognose: Überraschung beim Gewinn (± 3 %), beim Umsatz (± 1 %) und die Richtung des
Ausblicks (zählt doppelt – der Markt handelt die Zukunft). Die tatsächliche Kursreaktion steht immer daneben.
"""

from __future__ import annotations

import math
import os
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pandas as pd

PAST_DAYS, NEXT_DAYS = 14, 21

GUIDE_UP = re.compile(
    r"\b(rais(es|ed|ing)?|lifts?|lifted|boosts?|boosted|hikes?|hiked|ups|increases?|increased)\b[^|]{0,45}\b(guidance|outlook|forecast|view)\b"
    r"|\b(guidance|outlook|forecast)\b[^|]{0,25}\b(above|tops|beats|ahead of)\b"
    r"|\b(strong|upbeat|bullish|upgraded|rosy|robust)\b[^|]{0,20}\b(guidance|outlook|forecast)\b"
    r"|\b(hebt|erhöht|erhoeht|hob)\b[^|]{0,30}\b(prognose|ausblick|jahresziele?|ziele|umsatzziel|gewinnziel)\w*"
    r"|\b(prognose|ausblick|jahresziele?|ziele)\w*\s+(angehoben|erhöht)\b|\bprognose(erhöhung|anhebung)\b", re.I)
GUIDE_DOWN = re.compile(
    r"\b(cuts?|lowers?|lowered|slash(es|ed)?|reduces?|reduced|trims?|trimmed|withdraws?|withdrew|pulls?|pulled)\b[^|]{0,45}\b(guidance|outlook|forecast|view)\b"
    r"|\b(guidance|outlook|forecast)\b[^|]{0,25}\b(below|misses|missed|disappoints?|weak|falls short)\b"
    r"|\b(weak|soft|disappointing|downbeat|gloomy|lowered)\b[^|]{0,20}\b(guidance|outlook|forecast)\b"
    r"|\b(senkt|kappt|kassiert|streicht|senkte)\b[^|]{0,30}\b(prognose|ausblick|jahresziele?|ziele|umsatzziel|gewinnziel)\w*"
    r"|\b(prognose|ausblick|jahresziele?|ziele)\w*\s+(gesenkt|gekappt|kassiert|zurückgenommen)\b|\b(gewinnwarnung|prognosesenkung|umsatzwarnung)\b", re.I)
ANALYST = re.compile(r"\b(price target|target price|kursziel|rating|stock forecast|price forecast|price prediction|prognose für die aktie|upgrades?|downgrades?|upgraded|downgraded|analysts? (see|expect)|"
                     r"(raises|lifts|cuts|lowers|trims|boosts)\b[^|]{0,30}\btarget\b)", re.I)
# Ausgaben-/Investitionspläne sind kein Umsatz- oder Gewinnausblick (Meta 21.10.2026: „Boosts … Spending Outlook“ → Kurs −7 %)
SPEND = re.compile(r"\b(spend\w*|capex|capital (expenditures?|spending)|expenses?|costs?|investments?|invest\w*|ausgaben|investitionen|kosten)\b", re.I)
# Sondereffekte: Gewinn durch Einmalposten verzerrt (Steuer, Abschreibung, Rückstellung)
ONEOFF = re.compile(r"\b(one[- ]time|one[- ]off|non[- ]recurring|charges?|impairments?|write[- ]?downs?|tax (charge|benefit|expense|hit)|"
                    r"legal (charge|settlement)|restructuring|sonderbelastung\w*|sondereffekt\w*|einmal\w*|abschreibung\w*)\b", re.I)
GUIDE_KEEP = re.compile(
    r"\b(reaffirms?|reaffirmed|reiterates?|reiterated|maintains?|maintained|confirms?|confirmed)\b[^|]{0,45}\b(guidance|outlook|forecast|view)\b"
    r"|\b(bestätigt|bekräftigt|konkretisiert)\b[^|]{0,30}\b(prognose|ausblick|jahresziele?|ziele)\w*"
    r"|\b(prognose|ausblick|jahresziele?|ziele)\w*\s+(bestätigt|bekräftigt)\b", re.I)


def _num(v):
    try:
        v = float(v)
        return None if math.isnan(v) or math.isinf(v) else v
    except (TypeError, ValueError):
        return None


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
        if ANALYST.search(title):                        # Kursziele/Einstufungen von Analysten sind kein Ausblick der Firma
            continue
        d = None
        for rx, val in ((GUIDE_UP, 1), (GUIDE_DOWN, -1), (GUIDE_KEEP, 0)):
            m = rx.search(title)
            if m and (not words or _about(title, m, words)):
                d = val
                if SPEND.search(m.group(0)):          # Ausgabenplan („Spending Outlook“, „capex forecast“), kein Ausblick
                    d = None
                break
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


def oneoff(items: list[tuple[str, str, str]], words: list[str], since: pd.Timestamp | None = None) -> dict | None:
    """Schlagzeile nach den Zahlen, die auf einen Sondereffekt beim Gewinn hindeutet (Firma im Titel)."""
    from email.utils import parsedate_to_datetime
    words = [w.lower() for w in words if w and len(w) >= 3]
    for title, link, date in items:
        if since is not None and date:
            try:
                if pd.Timestamp(parsedate_to_datetime(date)) < since - pd.Timedelta(hours=2):
                    continue
            except Exception:
                pass
        m = ONEOFF.search(title)
        if m and not ANALYST.search(title) and (not words or _about(title, m, words)):
            return {"t": title[:180], "u": link}
    return None


def assess(eps_s: float | None, rev_s: float | None, guide_d: int | None) -> dict | None:
    """Regel: Gewinn-Überraschung ±3 % → ±1 (über ±10 % → ±2, wie in der Statistik: 61 % bzw. 39 % gestiegen),
    Umsatz ±1 % → ±1, Ausblick angehoben/gesenkt → ±2."""
    pts, why = 0.0, []
    if eps_s is not None:
        if eps_s > .10:
            pts += 2; why.append("Gewinn deutlich über der Erwartung")
        elif eps_s < -.10:
            pts -= 2; why.append("Gewinn deutlich unter der Erwartung")
        elif eps_s >= .03:
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


def _rss(q: str, de: bool = False) -> list[tuple[str, str, str]]:
    loc = "hl=de&gl=DE&ceid=DE:de" if de else "hl=en-US&gl=US&ceid=US:en"
    url = f"https://news.google.com/rss/search?{loc}&q=" + urllib.parse.quote(q)
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


_SEC_TEXT: dict = {}


def _sec_text(t: str, since: str) -> str | None:
    from . import earnfast, secguide
    if t not in _SEC_TEXT:
        cik = earnfast.ciks().get(t)
        _SEC_TEXT[t] = secguide.fetch_text(cik, since) if cik and os.environ.get("SEC_CONTACT") else None
    return _SEC_TEXT[t]


def eps_plausible(eps: float, est: float, txt: str) -> bool:
    """Große Überraschungen nicht blind verwerfen (Review K8): Nahe 0 zählt der absolute Abstand (0,10), sonst ±50 %.
    Größere Abweichung nur, wenn der Wert mindestens zweimal in der Mitteilung steht (Text + Tabelle) – dann ist ein
    Lesefehler unwahrscheinlich. Vorzeichenwechsel (Verlust ↔ Gewinn) ebenfalls nur mit dieser Bestätigung."""
    if abs(eps - est) <= max(0.5 * abs(est), 0.10) and (eps >= 0) == (est >= 0):
        return True
    v = f"{abs(eps):.2f}"
    return len(re.findall(r"(?<![\d.])" + re.escape(v) + r"(?!\d)", (txt or "")[:20000])) >= 2


def _sec_results(t: str, ev: dict, upcoming: pd.DataFrame, est_col: str, today: pd.Timestamp) -> pd.DataFrame | None:
    """Gewinn je Aktie direkt aus der Pressemitteilung, solange Yahoo ihn noch nicht hat (meist 10–40 Min. schneller).
    Erwartung = Yahoo-Schätzung für diesen Termin. Nur mit SEC_CONTACT und nur am Termin (± 1 Tag)."""
    if not os.environ.get("SEC_CONTACT") or not ev.get("date"):
        return None
    d = pd.Timestamp(ev["date"])
    if abs((today - d).days) > 1:
        return None
    from . import secguide
    txt = _sec_text(t, (d - pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
    r = secguide.results(txt) if txt else {}
    if r.get("eps") is None:
        return None
    if r["eps_kind"] == "GAAP" and re.search(r"\b(non-?gaap|adjusted)\b", txt, re.I):
        return None                                        # nur GAAP gefunden, obwohl es eine bereinigte Zahl gibt → lieber auf Yahoo warten
    est = None
    if len(upcoming) and est_col in upcoming:
        u = upcoming[[abs((i.tz_convert("UTC").tz_localize(None).normalize() - d).days) <= 3 for i in upcoming.index]]
        est = _num(u.iloc[-1][est_col]) if len(u) else None
    if est is None:
        print(f"Quartalszahlen {t}: Pressemitteilung {r['eps']} ohne Erwartung – warte auf Yahoo")
        return None
    if not eps_plausible(r["eps"], est, txt):
        print(f"Quartalszahlen {t}: Pressemitteilung {r['eps']} vs. Erwartung {est} – große Abweichung ohne Bestätigung im Text, warte auf Yahoo")
        return None
    print(f"Quartalszahlen {t}: aus der Pressemitteilung – Gewinn je Aktie {r['eps']} ({r['eps_kind']}), Erwartung {est}")
    ts = pd.Timestamp.now(tz="UTC").tz_convert("America/New_York")
    return pd.DataFrame({"EPS Estimate": [est], "Reported EPS": [r["eps"]], "Surprise(%)": [None]}, index=pd.DatetimeIndex([ts], name="Earnings Date"))


def _sec_guidance(tk, t: str, last: pd.Timestamp) -> dict | None:
    """Ausblick aus der Pressemitteilung bei der SEC (nur mit Secret SEC_CONTACT), gegen die Analysten-Erwartung."""
    if not os.environ.get("SEC_CONTACT"):
        return None
    from . import earnfast, secguide
    cik = earnfast.ciks().get(t)
    if not cik:
        return None
    lt = pd.Timestamp(last)
    since = ((lt.tz_convert("UTC").tz_localize(None) if lt.tzinfo else lt) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    txt = _sec_text(t, since)
    g = secguide.parse(txt) if txt else None
    if not g:
        return None
    est_q = est_y = None
    try:
        re_ = tk.get_revenue_estimate()
        est_q = _num(re_.loc["+1q"].get("avg")) if "+1q" in re_.index else None
        est_y = _num(re_.loc["0y"].get("avg")) if "0y" in re_.index else None
    except Exception:
        pass
    return secguide.judge(g, est_q, est_y)


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


def _from_history(tk, ev: dict, reported: pd.DataFrame, today: pd.Timestamp) -> pd.DataFrame | None:
    """Ersatz, wenn Yahoo den gerade gemeldeten Termin aus get_earnings_dates nimmt (kommt vor, z. B. Netflix 20.10.2026):
    get_earnings_history hat das Quartal schon. Termin = Kalenderdatum, Uhrzeit wie bei den bisherigen Meldungen."""
    try:
        d = pd.Timestamp(ev.get("date"))
    except Exception:
        return None
    if pd.isna(d) or not (today - pd.Timedelta(days=PAST_DAYS) <= d <= today):
        return None
    last = reported.index[0].tz_convert("UTC").tz_localize(None).normalize() if len(reported) else None
    if last is not None and last >= d - pd.Timedelta(days=2):
        return None                                       # Terminliste ist aktuell
    try:
        eh = tk.get_earnings_history()
    except Exception:
        return None
    if eh is None or not len(eh) or "epsActual" not in eh:
        return None
    eh = eh.dropna(subset=["epsActual"])
    if not len(eh):
        return None
    q = pd.Timestamp(max(eh.index))
    if not (pd.Timedelta(days=0) <= d - q <= pd.Timedelta(days=120)) or last is None or q <= last:
        return None                                       # jüngstes Quartal ist schon das zuletzt gemeldete → noch keine neuen Zahlen
    row = eh.loc[eh.index == max(eh.index)].iloc[0]
    tz = reported.index.tz if len(reported) and reported.index.tz is not None else "America/New_York"
    hrs = [i.hour for i in reported.index[:4]] if len(reported) else []
    hour = max(set(hrs), key=hrs.count) if hrs else 16
    ts = pd.Timestamp(d.year, d.month, d.day, hour).tz_localize(tz)
    if ts > pd.Timestamp.now(tz="UTC"):
        return None                                       # Meldezeit noch nicht erreicht
    e, a = _num(row.get("epsEstimate")), _num(row.get("epsActual"))
    return pd.DataFrame({"EPS Estimate": [e], "Reported EPS": [a], "Surprise(%)": [None]}, index=pd.DatetimeIndex([ts], name="Earnings Date"))


def one(t: str, ev: dict, close: pd.Series | None, est_mem: dict, today: pd.Timestamp, live: bool = False) -> tuple[dict | None, dict | None]:
    """Ergebnis-Datensatz für eine Aktie und ggf. die gemerkte Erwartung (für den Vergleich nach dem Termin).
    live=True (Prüfdienst tagsüber): nur frisch gemeldete Zahlen (≤ 3 Tage), ohne Vorschau – spart Abfragen."""
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
    syn = _from_history(tk, ev, reported, today)
    if syn is not None:                                    # Termin fehlt (noch) in der Terminliste, Zahlen stehen aber in der Historie
        reported = pd.concat([syn, reported]).sort_index(ascending=False)
        upcoming = upcoming[upcoming.index.tz_convert("UTC").tz_localize(None).normalize() > syn.index[0].tz_convert("UTC").tz_localize(None).normalize()]
    from_pr = False
    if live:
        lt = reported.index[0] if len(reported) else None
        if lt is None or today - lt.tz_convert("UTC").tz_localize(None).normalize() > pd.Timedelta(days=3):
            pr = _sec_results(t, ev, upcoming, est_col, today)   # Yahoo noch leer → Zahlen aus der Pressemitteilung (SEC)
            if pr is None:
                return None, None                          # noch nichts gemeldet – erst die nächste Prüfung
            reported = pd.concat([pr, reported]).sort_index(ascending=False)
            from_pr = True
        upcoming = upcoming.iloc[0:0]
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
        if rev_a is None and _SEC_TEXT.get(t):             # Umsatz aus der Pressemitteilung, solange Yahoo ihn noch nicht hat
            from . import secguide
            rev_a = secguide.results(_SEC_TEXT[t]).get("rev")
        mem = est_mem.get(t) or {}
        try:                                               # Umsatz-Beschleunigung (SEC-Finanzdaten) – bremst die Steig-Quote nach guten Zahlen
            from . import earnfast, revhist
            cik = earnfast.ciks().get(t)
            ac = revhist.accel(revhist.quarters(cik), rev_a, last) if cik and "." not in t else None
            if ac:
                res.update(ac)
        except Exception as exc:
            print(f"Umsatz-Beschleunigung {t}: {exc!r}")
        if rev_a is not None:
            res["rev_a"] = rev_a
            if rev_py:
                res["rev_yoy"] = round(rev_a / rev_py - 1, 4)
            if mem.get("rev") and abs((pd.Timestamp(mem.get("date", "1900-01-01")) - last_day).days) <= 7:
                res["rev_e"] = mem["rev"]
                res["rev_s"] = round(rev_a / mem["rev"] - 1, 4)
        g = _sec_guidance(tk, t, last)                     # 1. Pressemitteilung bei der SEC (mit SEC_CONTACT)
        if not g:                                          # 2. Schlagzeilen
            items = _rss(f"{_words(ev.get('name') or t, t)[0]} guidance OR outlook OR forecast when:{PAST_DAYS + 1}d")
            if "." in t and not t.endswith((".HK", ".T", ".KS", ".KQ", ".TW", ".SS", ".SZ", ".AX", ".NS", ".BO")):
                # Europa: Prognose-Änderungen sind Pflicht-Ad-hoc-Meldungen (EU-MAR) – auf Deutsch über EQS/dpa-AFX zuerst
                items = _rss(f"{_words(ev.get('name') or t, t)[0]} Prognose OR Ausblick OR Jahresziele OR Gewinnwarnung when:{PAST_DAYS + 1}d", de=True) + items
            g = guidance(items, _words(ev.get("name") or t, t), last)
        if g:
            res["guide"] = g
        if res.get("eps_s") is not None and abs(res["eps_s"]) >= .10:
            oo = oneoff(_rss(f"{_words(ev.get('name') or t, t)[0]} earnings charge OR one-time OR tax when:{PAST_DAYS + 1}d"), _words(ev.get("name") or t, t), last)
            if oo:
                res["oneoff"] = oo
        if close is not None and len(close):
            rx = reaction(close, last)
            if rx:
                res["rx"] = rx
        if from_pr:
            res["src"] = "pr"                              # vorläufig aus der Pressemitteilung – Yahoo ersetzt es bei der nächsten Prüfung
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
    from . import earnfast
    try:
        earnfast.sec_pushes(os.environ.get("SEC_HIT", ""), cal.get("events", []), out)   # zuerst: „Zahlen sind raus“
    except Exception as exc:
        print(f"Quartalszahlen: SEC-Mitteilung fehlgeschlagen ({exc!r})")
    try:
        nexts = {t: r.get("next") or {} for t, r in json.loads(urllib.request.urlopen(PAGES + "earnings.json", timeout=60).read()).get("tickers", {}).items()}
    except Exception:
        nexts = {}
    try:
        print(f"Quartalszahlen: {earnfast.watch_file(cal.get('events', []), nexts, out, today)} Termine mit SEC-Nummer für den Kursdienst")
    except Exception as exc:
        print(f"Quartalszahlen: earn_watch.json fehlgeschlagen ({exc!r})")
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
    # bisherige Ergebnisse behalten – auch für geprüfte Aktien, deren neuer Abruf gerade nichts lieferte (Review W10)
    keep = {t: r for t, r in prev.items() if t not in fresh and pd.Timestamp((r.get("last") or {}).get("date", "1900-01-01")) >= today - pd.Timedelta(days=4)}
    allr = {**keep, **fresh}
    try:
        print(f"Quartalszahlen: {earnfast.archive(fresh, out)} Meldungen im Archiv")
    except Exception as exc:
        print(f"Quartalszahlen: Archiv fehlgeschlagen ({exc!r})")
    try:
        earnfast.result_pushes(fresh, prev, cal.get("events", []), out)
    except Exception as exc:
        print(f"Quartalszahlen: Ergebnis-Mitteilung fehlgeschlagen ({exc!r})")
    f.write_text(json.dumps({"generated": now.isoformat(timespec="seconds"), "tickers": allr}, ensure_ascii=False, separators=(",", ":"), default=str), encoding="utf-8")
    print(f"Quartalszahlen live: {len(todo)} Termine geprüft, {len(fresh)} mit Zahlen aktualisiert, {len(allr)} in der Datei")


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


if __name__ == "__main__":
    import sys
    live_main(*(sys.argv[1:3]))
