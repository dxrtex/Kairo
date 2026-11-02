"""Warum lag die Quartalszahlen-Prognose daneben? Automatische Ursachensuche für jede Fehlprognose.

Kairo zeigt vor der Kursreaktion eine Wahrscheinlichkeit „steigt am Tag danach“ (Archiv: p). Reagiert der Kurs deutlich
anders, sammelt dieser Schritt Hinweise auf den Grund – und legt sie im Archiv ab (Feld „why“):
- Markt: Wie lief der Gesamtmarkt (SPY) am selben Tag? Ein Absturz mit dem Markt ist kein Fehler der Quartalszahlen-Regel.
- Vorlauf: Wie stark war die Aktie in den 20 Handelstagen davor gestiegen/gefallen („schon eingepreist“)?
- Schlagzeilen danach: Was nennen die Medien als Grund (Ausblick, Marge, Umsatz, Nutzerzahlen, Aufträge, Kosten, Zölle, KI,
  Management, Rückkauf, Analysten …)? Gezählt nach festen Stichwort-Gruppen, Titel werden zum Nachlesen gespeichert.
Die wöchentliche Bilanz (tools/earn_review.py) zählt, welche Gründe bei Fehlprognosen gehäuft vorkommen, und schlägt daraus
neue Merkmale vor. Ein Merkmal kommt erst in die Prognose, wenn es zeitlich getrennt geprüft besser ist.
"""
from __future__ import annotations

import re

import pandas as pd

MISS_MOVE = 0.03          # Fehlprognose: Kairo sagte ≥ 55 % steigt und Kurs ≤ −3 % (oder ≤ 45 % und ≥ +3 %)
MAX_PER_RUN = 15          # höchstens so viele neue Fälle je Prüflauf (Laufzeit)

REASONS = {
    "Ausblick": r"guidance|outlook|forecast|prognose|ausblick",
    "Marge": r"margins?|marge|profitability|gross margin",
    "Umsatz": r"revenue|sales|umsatz|top[- ]line",
    "Nutzer/Kunden": r"subscribers?|users?|customers?|members|nutzer|kunden|traffic|downloads",
    "Aufträge": r"bookings|billings|backlog|orders|auftrag|aufträge|rpo|pipeline",
    "Kosten": r"costs?|expenses?|spending|capex|kosten|investitionen",
    "Zölle/Politik": r"tariffs?|zölle|regulat\w*|fda|antitrust|sanction\w*|government",
    "KI/Rechenzentren": r"\bai\b|artificial intelligence|data ?cent(er|re)s?|gpu|ki\b",
    "Management": r"\bceo\b|\bcfo\b|resign\w*|steps? down|chief executive|vorstand",
    "Rückkauf/Dividende": r"buyback|repurchase|dividend|rückkauf|dividende",
    "Analysten": r"downgrad\w*|upgrad\w*|price target|kursziel|analysts?",
    "Wettbewerb": r"competition|competitor|rival|market share|wettbewerb",
    "Sondereffekt": r"one[- ]time|charge|impairment|write[- ]?down|sonder",
    "Übernahme": r"acquisition|acquire|merger|takeover|deal|übernahme",
    "Schon eingepreist": r"priced in|sell the news|expectations (were|ran) high|high bar|lofty|eingepreist",
}
_RX = {k: re.compile(v, re.I) for k, v in REASONS.items()}


def is_miss(r: dict) -> bool:
    p, r1 = r.get("p"), r.get("r1")
    if p is None or r1 is None:
        return False
    return (p >= 0.55 and r1 <= -MISS_MOVE) or (p <= 0.45 and r1 >= MISS_MOVE)


def tags(titles: list[str]) -> list[str]:
    found = []
    for k, rx in _RX.items():
        if any(rx.search(t) for t in titles):
            found.append(k)
    return found


def _move_titles(items: list[tuple[str, str, str]], words: list[str]) -> list[str]:
    """Schlagzeilen zur Kursbewegung der Firma („Intel stock plunges as …“, „Why Twilio shares fell“)."""
    mv = re.compile(r"\b(fall|fell|falls|drop\w*|plung\w*|sink\w*|slid\w*|slump\w*|tumbl\w*|sank|down|lower|bricht ein|fällt|verliert|"
                    r"jump\w*|soar\w*|surg\w*|rall\w*|climb\w*|ris(e|es|ing)|rose|up|higher|steigt|springt|why)\b", re.I)
    ws = [w.lower() for w in words if w]
    out = []
    for title, _, _ in items:
        t = re.sub(r"\s+-\s+[^-]{2,60}$", "", title)
        if any(w in t.lower() for w in ws) and mv.search(t):
            out.append(t[:180])
    return out[:8]


def analyze(arc: dict, names: dict, rss=None, prices=None) -> int:
    """Ergänzt im Archiv für bisher nicht untersuchte Fehlprognosen das Feld „why“. rss(q) und prices(tickers, start, end)
    sind austauschbar (Tests). Rückgabe: Anzahl neu untersuchter Fälle."""
    from . import earnings as E
    rss = rss or E._rss
    # Fehlprognosen zuerst; danach auch getroffene Fälle als Vergleich (sonst ließe sich nicht sagen, ob ein Grund bei
    # Fehlprognosen häufiger vorkommt als sonst)
    open_ = [k for k, r in arc.items() if r.get("r1") is not None and r.get("p") is not None and "why" not in r]
    todo = sorted(open_, key=lambda k: not is_miss(arc[k]))[:MAX_PER_RUN]
    if not todo:
        return 0
    days = [pd.Timestamp(k.split("|", 1)[1]) for k in todo]
    px = None
    try:
        tks = sorted({k.split("|", 1)[0] for k in todo} | {"SPY"})
        px = (prices or _prices)(tks, min(days) - pd.Timedelta(days=45), max(days) + pd.Timedelta(days=6))
    except Exception as exc:
        print(f"Ursachensuche: Kurse fehlen ({exc!r})")
    for k in todo:
        t, d = k.split("|", 1)
        r = arc[k]
        day = pd.Timestamp(d)
        why: dict = {}
        if px is not None:
            why.update(_market(px, t, day, r.get("r1")))
        words = E._words(names.get(t) or t, t)
        q = f"{words[0]} stock OR shares after:{(day - pd.Timedelta(days=1)).date()} before:{(day + pd.Timedelta(days=4)).date()}"
        heads = _move_titles(rss(q), words)
        why["tags"] = tags(heads)
        why["head"] = heads[:3]
        r["why"] = why
    return len(todo)


def _prices(tks: list[str], start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    import yfinance as yf
    df = yf.download(tks, start=start.date(), end=end.date(), interval="1d", auto_adjust=True, progress=False, group_by="ticker", threads=True)
    return pd.DataFrame({t: df[t]["Close"] for t in tks if t in df.columns.get_level_values(0)})


def _market(px: pd.DataFrame, t: str, day: pd.Timestamp, r1: float | None) -> dict:
    """Markt am Reaktionstag (SPY), Bewegung über dem Markt und Vorlauf der Aktie (20 Handelstage vor dem Reaktionstag)."""
    out = {}
    idx = px.index
    i = idx.searchsorted(day)
    if "SPY" in px and 0 < i < len(idx):
        spy = float(px["SPY"].iloc[i] / px["SPY"].iloc[i - 1] - 1)
        out["spy"] = round(spy, 4)
        if r1 is not None:
            out["ex"] = round(r1 - spy, 4)
    if t in px and i >= 21:
        c = px[t]
        if pd.notna(c.iloc[i - 1]) and pd.notna(c.iloc[i - 21]):
            out["run20"] = round(float(c.iloc[i - 1] / c.iloc[i - 21] - 1), 4)
    return out


def run(out, names: dict) -> int:
    """Im Prüflauf (backend.earnings.live_main): Archiv laden, neue Fälle untersuchen, speichern."""
    import json
    f = out / "earn_archive.json"
    try:
        arc = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return 0
    n = analyze(arc, names)
    if n:
        f.write_text(json.dumps(arc, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    return n
