"""Ausblick direkt aus der Pressemitteilung der Firma (SEC 8-K, Anhang 99.1) – statt aus Schlagzeilen.

Firmen schreiben ihren Ausblick wörtlich hinein („expects fourth-quarter revenue of $45.0 billion to $47.0 billion“).
Kairo liest die Spanne, nimmt die Mitte und vergleicht sie mit der Analysten-Erwartung (Yahoo): ≥ +1 % → über Erwartung,
≤ −1 % → darunter, sonst im Rahmen. Ausgaben-/Investitionspläne zählen nicht.
Die SEC lässt Meldungstexte nur mit Kontakt-E-Mail in der Kennung abrufen → GitHub-Secret SEC_CONTACT (ohne: aus).
"""
from __future__ import annotations

import os
import re

_NUM = r"\$\s?(\d{1,3}(?:[.,]\d{1,3})?)\s?(billion|million|bn|b|m)?"
RANGE = re.compile(_NUM + r"\s?(?:to|and|-|–|—)\s?" + _NUM, re.I)
SINGLE = re.compile(r"\b(?:approximately|about|around|of)\s+" + _NUM, re.I)
REV = re.compile(r"\b(revenues?|net sales|total sales|sales)\b", re.I)
FWD = re.compile(r"\b(expects?|expected|anticipates?|outlook|guidance|forecasts?|projects?|sees|estimates?)\b", re.I)
FULLY = re.compile(r"\b(full[- ]year|fiscal year|annual|FY ?\d{2,4})\b", re.I)
QTR = re.compile(r"\b(quarter|q[1-4])\b", re.I)
SPENDW = re.compile(r"\b(capital expenditures?|capex|expenses?|costs?|spending|investments?)\b", re.I)
VERB = {1: re.compile(r"\b(rais(es|ed|ing)|increas(es|ed|ing)|lift(s|ed)?)\b[^.]{0,40}\b(outlook|guidance|forecast)\b", re.I),
        -1: re.compile(r"\b(lower(s|ed|ing)?|reduc(es|ed|ing)|cut(s|ting)?)\b[^.]{0,40}\b(outlook|guidance|forecast)\b", re.I)}


def _val(n: str, unit: str | None) -> float:
    x = float(n.replace(",", ""))
    u = (unit or "").lower()
    return x * (1e9 if u in ("billion", "bn", "b") else 1e6 if u in ("million", "m") else 1)


def text_of(html: str) -> str:
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    t = re.sub(r"<[^>]+>", " ", t)
    t = t.replace("&nbsp;", " ").replace("&#160;", " ").replace("&amp;", "&").replace("&#8211;", "–").replace("&#8212;", "—")
    return re.sub(r"\s+", " ", t)


def parse(text: str) -> dict | None:
    """Umsatz-Ausblick aus dem Text: {"lo","hi","mid","q": Quartal?, "s": Satz} oder nur Richtung aus Verben."""
    out = None
    for sent in re.split(r"(?<=[.;])\s+", text):
        if len(sent) > 600 or not (FWD.search(sent) and REV.search(sent)):
            continue
        m = RANGE.search(sent)
        if m and not SPENDW.search(sent[max(0, m.start() - 60):m.start()]):
            u2 = m.group(4) or m.group(2)
            lo, hi = _val(m.group(1), m.group(2) or u2), _val(m.group(3), u2)
            if lo > 1e6 and hi >= lo:
                out = {"lo": lo, "hi": hi, "mid": (lo + hi) / 2, "q": bool(QTR.search(sent)) and not FULLY.search(sent), "s": sent.strip()[:300]}
                break
        m = SINGLE.search(sent)
        if m and not out and not SPENDW.search(sent):
            v = _val(m.group(1), m.group(2))
            if v > 1e6:
                out = {"lo": v, "hi": v, "mid": v, "q": bool(QTR.search(sent)) and not FULLY.search(sent), "s": sent.strip()[:300]}
    verb = next((d for d, rx in VERB.items() if rx.search(text) and not SPENDW.search(rx.search(text).group(0))), None)
    if out:
        out["verb"] = verb
        return out
    return {"verb": verb} if verb is not None else None


def judge(g: dict | None, est_q: float | None, est_y: float | None) -> dict | None:
    """Richtung: Ausblick-Mitte gegen Analysten-Erwartung (Quartal bzw. Jahr); sonst Verb der Firma (raises/lowers)."""
    if not g:
        return None
    est = est_q if g.get("q") else est_y
    if g.get("mid") and est and abs(g["mid"] / est - 1) > 0.2:
        g = {"verb": g.get("verb")}                        # Spanne passt nicht zur Firma (Produkt/Segment, z. B. Insmed) → nur das Verb zählt
    if g.get("mid") and est:
        r = g["mid"] / est - 1
        d = 1 if r >= .01 else -1 if r <= -.01 else 0
        return {"d": d, "t": g["s"], "vs": round(r, 4), "src": "Pressemitteilung (SEC)"}
    if g.get("verb") is not None:
        return {"d": g["verb"], "t": "Pressemitteilung: Ausblick " + ("angehoben" if g["verb"] == 1 else "gesenkt"), "src": "Pressemitteilung (SEC)"}
    return None


EPS_ADJ = re.compile(r"\b(non-?gaap|adjusted|core)\b[^.$]{0,80}?\b(eps|earnings per (diluted )?share|net income per (diluted )?share)\b[^.$]{0,40}?\$\s?(\d{1,3}\.\d{2})", re.I)
EPS_GAAP = re.compile(r"\b(diluted )?(eps|earnings per (diluted )?share|net income per (diluted )?share)\b[^.$]{0,40}?\$\s?(\(?\d{1,3}\.\d{2}\)?)", re.I)
REV_ACT = re.compile(r"\b(total )?(revenues?|net sales|sales)\b[^.$]{0,40}?\b(was|were|of|totaled|reached|increased[^.$]{0,30}to|grew[^.$]{0,30}to|rose[^.$]{0,30}to)\s+" + _NUM, re.I)


EPS_TAB = re.compile(r"\b(earnings per (diluted )?share|eps)\s*[–—-]?\s*\(?(non-?gaap|adjusted)\)?\s*(\(\d\)\s*)?\$?\s?(\(?\d{1,3}\.\d{2}\)?)(?!\d)", re.I)
NOT_EPS = re.compile(r"(?i)includ|charges?\b|IPR|impact|offset|guidance|outlook|expect|dividend|distribution|buyback|repurchase")
PER_SHARE = re.compile(r"\$\s?(\(?\d{1,3}\.\d{2}\)?)\s*(per (basic |diluted |fully[- ]diluted )?share|a share|(basic |diluted )?(earnings|loss|income) per share)", re.I)
ADJ_WORDS = re.compile(r"\b(adjusted|non-?gaap|excluding|core|underlying)\b", re.I)


def _eps_val(v: str) -> float:
    return -float(v.strip("()")) if v.startswith("(") else float(v)


def results(text: str) -> dict:
    """Gemeldeter Gewinn je Aktie (bereinigt bevorzugt – damit rechnen die Analysten-Erwartungen) und Umsatz."""
    out = {}
    head = text[:12000]                                    # Kernzahlen stehen oben in der Mitteilung
    # Tabellenzeile „Earnings per share – Non-GAAP 7.48“ zuerst; Sätze über Sonderbelastungen („EPS included $4.57 of
    # IPR&D charges“, Lilly) oder den Ausblick sind kein Ergebnis
    m = EPS_TAB.search(head) or next((x for x in EPS_ADJ.finditer(head)
                                      if not NOT_EPS.search(x.group(0) + head[x.end():x.end() + 40])), None)
    if m:
        out.update(eps=_eps_val(m.group(m.lastindex)), eps_kind="bereinigt")
    else:
        adj = gaap = None                                  # Satzweise: „… or $12.78 per share“ (PBF), Dividenden ausgenommen
        for sent in re.split(r"(?<=[.;•])\s+|\u2022|&#8226;", head):
            if NOT_EPS.search(sent):
                continue
            pm = PER_SHARE.search(sent)
            if not pm or not re.search(r"(?i)income|earnings|loss|profit|eps", sent):
                continue
            v = _eps_val(pm.group(1))
            pre = sent[:pm.start()].lower()                # „net loss of $100.3 million, or $0.46 per share“ → −0,46 (Insmed)
            if v > 0 and pre.rfind("loss") > max(pre.rfind("income"), pre.rfind("earnings"), pre.rfind("profit")):
                v = -v
            if ADJ_WORDS.search(sent):
                adj = adj if adj is not None else v
            elif gaap is None:
                gaap = v
        if adj is not None:
            out.update(eps=adj, eps_kind="bereinigt")
        elif gaap is not None:
            out.update(eps=gaap, eps_kind="GAAP")
        else:
            m = EPS_GAAP.search(head)
            if m:
                out.update(eps=_eps_val(m.group(5)), eps_kind="GAAP")
    m = REV_ACT.search(head)
    if m and not FWD.search(head[max(0, m.start() - 80):m.start()]):
        v = _val(m.group(4), m.group(5))
        if v > 1e6:
            out["rev"] = v
    return out


def fetch_text(cik: int, since_iso: str) -> str | None:
    """Text der Pressemitteilung (Anhang 99.1) zum neuesten 8-K Punkt 2.02 bzw. 6-K seit since_iso. Braucht SEC_CONTACT."""
    contact = os.environ.get("SEC_CONTACT", "").strip()
    if not contact:
        return None
    import requests
    ua = {"User-Agent": f"Kairo {contact}", "Accept-Encoding": "gzip, deflate"}
    try:
        f = requests.get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json", headers=ua, timeout=20).json()["filings"]["recent"]
        for i in range(min(15, len(f["form"]))):
            if f["acceptanceDateTime"][i] < since_iso:
                break
            if f["form"][i] not in ("8-K", "6-K") or (f["form"][i] == "8-K" and "2.02" not in str(f["items"][i])):
                continue
            acc = f["accessionNumber"][i].replace("-", "")
            idx = requests.get(f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/index.json", headers=ua, timeout=20).json()
            names = [x["name"] for x in idx["directory"]["item"] if x["name"].lower().endswith((".htm", ".html"))
                     and x["name"] != f["primaryDocument"][i] and not re.match(r"(?i)(R\d+\.htm|.*index|.*-index-headers)", x["name"])]
            docs = sorted(names, key=lambda n: (not re.search(r"(?i)(ex-?99|exhibit99|press|earn|result|release)", n), n))
            for name in docs[:1]:
                return text_of(requests.get(f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{name}", headers=ua, timeout=30).text)
            return None
    except Exception as exc:
        print(f"SEC-Pressemitteilung: Fehler {exc!r}")
    return None


def fetch(cik: int, since_iso: str) -> dict | None:
    """Ausblick aus der neuesten Pressemitteilung (siehe fetch_text)."""
    t = fetch_text(cik, since_iso)
    return parse(t) if t else None
