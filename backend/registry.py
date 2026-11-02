"""Champion-Challenger-Register: welche Regeln und Prognosemodelle gibt es, in welchem Stand sind sie, was fehlt zur Freigabe?

Grundsatz: Automatische Forschung ja, automatische Strategieänderung nein.
- Champion = gültige Handelsregel (B60). Sie ändert sich nur mit ausdrücklicher Freigabe.
- Challenger laufen getrennt (Forschung → Schattentest) und werden an vorab festgelegten Hürden gemessen.
- Prognose-Anzeigen (Quartalszahlen-Wahrscheinlichkeit) dürfen sich nach festen Regeln selbst nacheichen, weil sie nur
  Information sind; alles, was Handelsentscheidungen ändert (Kriterien, Einstieg, Stop, Ausstieg, Rangfolge, Filter),
  braucht die Freigabe.

Stufen: idee → forschung (historisch geprüft) → schatten (läuft live ohne Geld) → kandidat (Hürden erfüllt, wartet auf
Freigabe) → champion. Verworfen bleibt mit Grund sichtbar, damit dieselbe Idee nicht erneut als neu gilt.
"""
from __future__ import annotations

STAGES = ("idee", "forschung", "schatten", "kandidat", "champion", "verworfen")

# Hürden für Handelsregeln (vor jedem Test festgelegt, gleich für alle Challenger)
GATES_RULE = {
    "hist_periods": "Ø Netto-R mit Stress-Kosten in Train, Validierung UND Holdout besser als der Champion",
    "hist_depot": "Depot (gleiche Raster und Kosten) mit besserer Rendite bei nicht größerem Rückgang",
    "independent": "zusätzlich in mindestens einem unabhängigen Datensatz (Vorzeit 1997–2007 oder Asien) nicht schlechter",
    "shadow_n": 30,              # abgeschlossene Live-Schatten-Trades je Regel
    "shadow_months": 12,         # Mindestdauer des Schattentests
    "approval": "ausdrückliche Freigabe durch Jonny",
}
# Hürden für Prognose-Anzeigen (z. B. Quartalszahlen): zeitlich getrennter Brier-Score besser, genug Fälle
GATES_FORECAST = {"min_cases": 200, "metric": "Brier-Score auf zeitlich späteren Fällen besser als das laufende Modell",
                  "auto_display": True, "affects_trades": False}

REGISTRY = [
    {"id": "B60", "kind": "regel", "stage": "champion", "since": "2026-10-29",
     "what": "11/11 → Seitwärtsphase (5 Kerzen ≤ 1,5 ATR, ≤ 10 Tage) → Kauf zur Eröffnung, Stop Basis-Tief − 0,25 ATR, "
             "Ausstieg EMA 20 ab Tag 10, spätestens Tag 60", "evidence": "13.241 Trades 2008–26: +0,12 R normal, −0,03 R Stress"},
    {"id": "E2", "kind": "regel", "stage": "schatten", "since": "2026-10-31",
     "what": "wie B60, aber Kauf per Buy-Stop über dem Basishoch (+0,05 ATR)", "evidence": "je Trade in Vorzeit/Asien besser, Depot nicht durchgängig",
     "next": "Schattentest läuft seit 01.11.2026 (paper/e2shadow.py, Freigabe erteilt)"},
    {"id": "Q1", "kind": "filter", "stage": "verworfen", "since": "2026-10-31", "what": "nur ruhige Setups",
     "evidence": "je Trade besser, im Depot nicht"},
    {"id": "N1", "kind": "filter", "stage": "verworfen", "since": "2026-10-30", "what": "keine US-Treffer nach Quartalszahlen-Rückgang",
     "evidence": "Ultimate Runde 1 nicht bestanden"},
    {"id": "R1-R4", "kind": "regel", "stage": "verworfen", "since": "2026-10-31", "what": "Stop-Mindestabstand, Rangfolge nach Stop, Mindestorder, Kombination",
     "evidence": "Reversal Ultimate: keine Variante bestanden"},
    {"id": "LEARN-PRE", "kind": "filter", "stage": "verworfen", "since": "2026-11-01",
     "what": "Filter aus vorher erkennbaren Merkmalen (Stop < 1 ATR, Momentum > 25 %, ATR > 5 %, Markt < 200-Tage-Linie)",
     "evidence": "Lern-Test 2008–26: kein Merkmal schadet beständig; live weiter beobachtet (backend/tradewhy.py)"},
    {"id": "A5", "kind": "regel", "stage": "schatten", "since": "2026-11-01",
     "what": "3 Verlust-Schlusskurse in Folge über der 200-Tage-Linie → Kauf zur Eröffnung, Verkauf bei Schluss über der 5-Tage-Linie (max. 10 Tage), 5 Plätze",
     "evidence": "normal: +16 % / +35 % / +12 % p. a. (Train/Val/Holdout), Stress: Totalverlust; Kostenschwelle 0,09 % je Seite; liquide Variante schlägt ETF nicht",
     "next": "Schattentest läuft seit 01.11.2026 (backend/mrshadow.py); entscheidend: echte Kosten < ~0,08 % je Seite über 3 Monate",
     "confirm": "02.11.2026 unabhängig bestätigt: Vorzeit und Asien je Trade +0,35 / +0,30 Prozentpunkte besser als Zufallskauf (p < 0,001)"},
    {"id": "W2", "kind": "regel", "stage": "schatten", "since": "2026-11-01",
     "what": "wie A5, aber Kauf-Limit 0,5 ATR unter dem Signal-Schluss (gilt einen Tag)",
     "evidence": "Welle 3: normal Val +47,5 % / Holdout +12,3 % p. a., Stress Val +15,1 % / Holdout −11,3 %; "
                 "90/10 mit ETF: normal +10,5 % statt +8,5 % p. a., Stress +7,9 %; dieselben Daten dreimal ausgewertet → nur Hinweis",
     "next": "Schattentest läuft seit 01.11.2026 (backend/mrshadow.py); Limit-Füllung live prüfen",
     "confirm": "02.11.2026 unabhängig bestätigt: Vorzeit 1999–2007 und Asien 2008–2026 je Trade +0,38 / +0,45 Prozentpunkte "
                "besser als Zufallskauf mit gleichem Limit (p < 0,001); Varianten 250-€-Regel, Vortageshoch, Marktbreite nicht besser"},
    {"id": "C1-ETF", "kind": "regel", "stage": "schatten", "since": "2026-11-01",
     "what": "RSI(2) < 10 über der 200-Tage-Linie auf Index-ETFs, Verkauf über der 5-Tage-Linie",
     "evidence": "+8–9 % p. a. in allen Zeiträumen, Rückgang −20 %, auch mit Stress-Kosten positiv – aber unter dem Welt-ETF",
     "next": "Schattentest auf Sektor-ETFs läuft seit 01.11.2026 (backend/mrshadow.py)"},
    {"id": "MRC-REST", "kind": "regel", "stage": "verworfen", "since": "2026-11-01",
     "what": "RSI(2)-Varianten, IBS, Z-Score, Wochen-Verlierer, B60 mit schnellen Ausstiegen, Basis-/Spannen-/Wartezeit-Varianten, Panik-Risiko",
     "evidence": "Mean-Reversion-Meisterschaft 01.11.2026: keine schlägt B60 mit Stress-Kosten durchgängig (docs/KAIRO_MR_MEISTERSCHAFT.md)"},
    {"id": "COMBO", "kind": "filter", "stage": "verworfen", "since": "2026-11-01",
     "what": "Kriterien + Insider / Qualität / Quartalszahlen-Kontext; Meta-Modell aus allen Merkmalen",
     "evidence": "kein Merkmal besteht nach Mehrfachtest-Korrektur; Quartalszahlen-Rückgang seit 2017 schlechter, Qualität knapp – live beobachtet"},
    {"id": "EARN-M1", "kind": "prognose", "stage": "champion", "since": "2026-10-30",
     "what": "Quartalszahlen: Gewinn-Stufe × Ausblick", "evidence": "Brier 0,2396 statt 0,2417 (zeitlich getrennt)",
     "next": "Nacheichung automatisch ab 200 Fällen, nur wenn zeitlich getrennt besser (tools/earn_review.py)"},
]


def by_stage(stage: str) -> list[dict]:
    return [x for x in REGISTRY if x["stage"] == stage]


def may_change_trades(entry: dict) -> bool:
    """Nur der Champion einer Handelsregel bestimmt Trades; alles andere bleibt Forschung/Anzeige."""
    return entry["kind"] in ("regel", "filter") and entry["stage"] == "champion"


def promote_allowed(entry: dict, result: dict) -> tuple[bool, list[str]]:
    """Prüft vorab festgelegte Hürden. Rückgabe (alle erfüllt?, fehlende Punkte). Auch bei True gilt: Freigabe nötig."""
    miss = []
    if entry["kind"] == "prognose":
        if (result.get("cases") or 0) < GATES_FORECAST["min_cases"]:
            miss.append(f"erst {result.get('cases', 0)} von {GATES_FORECAST['min_cases']} Fällen")
        if not result.get("brier_better"):
            miss.append("Brier-Score zeitlich getrennt nicht besser")
        return not miss, miss
    for k in ("hist_periods", "hist_depot", "independent"):
        if not result.get(k):
            miss.append(GATES_RULE[k])
    if (result.get("shadow_n") or 0) < GATES_RULE["shadow_n"]:
        miss.append(f"Schattentest: {result.get('shadow_n', 0)} von {GATES_RULE['shadow_n']} Trades")
    if (result.get("shadow_months") or 0) < GATES_RULE["shadow_months"]:
        miss.append(f"Schattentest: {result.get('shadow_months', 0)} von {GATES_RULE['shadow_months']} Monaten")
    miss.append(GATES_RULE["approval"])                # immer – nie automatisch
    return False, miss
