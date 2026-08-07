"""Gesundheitszustand der Außenabhängigkeiten — das Herz des autonomen Betriebs.

Svens Auftrag (04.08.2026): „Es muss wirklich ein festes, autonomes System
werden, was immer gleich gut funktioniert." Der Anlass war ein leeres
API-Guthaben: Jeder Scan lief in denselben Fehler, jedes Stück landete
einzeln auf „error", und niemand sah, dass EINE Ursache dahintersteckt.

Das Prinzip hier:

  1. Ein Ausfall wird EINMAL erkannt, nicht pro Stück neu.
  2. Solange eine Quelle krank ist, wird sie nicht sinnlos angerufen —
     wartende Arbeit bleibt wartend (kostet nichts, verliert nichts).
  3. Die Genesung wird aktiv geprüft (mit wachsendem Abstand), und sobald
     sie da ist, läuft alles Wartende von selbst weiter.
  4. Die App kann den Zustand anzeigen — ein Satz statt zehn roter Kacheln.

Bewusst ohne Datenbank: Der Zustand ist Prozess-lokal und darf beim Neustart
verloren gehen. Ein Neustart ist der beste Zeitpunkt, es einfach neu zu
versuchen.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

log = logging.getLogger("health")

# Wie lange nach einem Ausfall bis zum nächsten Versuch (Sekunden).
# Kurz genug, dass Sven nach dem Aufladen nicht wartet; lang genug, dass
# ein längerer Ausfall keine Logfluten erzeugt.
BACKOFF = (30, 60, 120, 300, 600)

# Grund-Codes: geschlossene Menge, damit die App sie übersetzen kann.
GRUND_TEXTE = {
    "kein_guthaben": "Das KI-Guthaben ist aufgebraucht. Lade auf console.anthropic.com "
                     "unter Plans & Billing auf — die Analyse läuft dann automatisch weiter.",
    "ueberlastet": "Die KI-Analyse ist gerade ausgelastet. SERO versucht es automatisch weiter.",
    "netz": "Keine Verbindung zur KI-Analyse. SERO versucht es automatisch weiter.",
    "schluessel": "Der KI-Zugang ist nicht gültig (API-Schlüssel prüfen).",
    "ebay_auth": "Die eBay-Verbindung ist abgelaufen — bitte im Profil neu verbinden.",
}


def klassifiziere(exc: BaseException) -> str | None:
    """Ausfall-Grund aus einer Ausnahme ableiten.

    None heißt: KEIN Infrastruktur-Problem — dann ist wirklich dieses eine
    Stück schuld (unlesbares Foto, kaputte Antwort) und der Fehler gehört an
    das Stück, nicht an das System.
    """
    text = str(exc).lower()
    name = type(exc).__name__
    if "credit balance" in text or "insufficient" in text and "credit" in text:
        return "kein_guthaben"
    if "rate limit" in text or "429" in text or name == "RateLimitError":
        return "ueberlastet"
    if "overloaded" in text or "529" in text or name == "InternalServerError":
        return "ueberlastet"
    if "authentication" in text or "invalid x-api-key" in text or name == "AuthenticationError":
        return "schluessel"
    if name in ("APIConnectionError", "APITimeoutError", "ConnectError",
                "ReadError", "ConnectTimeout", "ReadTimeout"):
        return "netz"
    if "connection" in text and "error" in text:
        return "netz"
    return None


@dataclass
class Quelle:
    """Zustand EINER Außenabhängigkeit."""
    name: str
    gesund: bool = True
    grund: str | None = None
    seit: float = 0.0
    fehlversuche: int = 0
    naechster_test: float = 0.0
    # Wird gesetzt, sobald eine Quelle von krank auf gesund wechselt —
    # der Rettungsdienst liest und quittiert es.
    genesen: bool = field(default=False)

    def darf_versuchen(self) -> bool:
        """Lohnt ein Aufruf gerade? Bei bekannter Krankheit nur zum Testzeitpunkt."""
        return self.gesund or time.time() >= self.naechster_test

    def melde_fehler(self, grund: str) -> None:
        if self.gesund:
            log.warning("health: %s ist AUSGEFALLEN (%s)", self.name, grund)
            self.seit = time.time()
            self.fehlversuche = 0
        self.gesund = False
        self.grund = grund
        self.naechster_test = time.time() + BACKOFF[min(self.fehlversuche, len(BACKOFF) - 1)]
        self.fehlversuche += 1

    def melde_erfolg(self) -> None:
        if not self.gesund:
            dauer = (time.time() - self.seit) / 60
            log.warning("health: %s ist WIEDER DA (nach %.0f min)", self.name, dauer)
            self.genesen = True
        self.gesund = True
        self.grund = None
        self.fehlversuche = 0
        self.naechster_test = 0.0

    def als_dict(self) -> dict:
        return {
            "name": self.name,
            "gesund": self.gesund,
            "grund": self.grund,
            "text": GRUND_TEXTE.get(self.grund or "") if self.grund else None,
            "seit": self.seit if not self.gesund else None,
            "naechster_test": self.naechster_test if not self.gesund else None,
        }


QUELLEN: dict[str, Quelle] = {
    "ki": Quelle("ki"),
    "ebay": Quelle("ebay"),
}


def quelle(name: str) -> Quelle:
    if name not in QUELLEN:
        QUELLEN[name] = Quelle(name)
    return QUELLEN[name]


def melde(name: str, exc: BaseException | None) -> str | None:
    """Ergebnis eines Aufrufs melden. Gibt den Ausfall-Grund zurück (oder None).

    Der Rückgabewert ist die Entscheidungshilfe für den Aufrufer:
    - None  → das Stück selbst ist schuld, echter Fehler
    - sonst → Infrastruktur; das Stück soll WARTEN, nicht scheitern
    """
    q = quelle(name)
    if exc is None:
        q.melde_erfolg()
        return None
    grund = klassifiziere(exc)
    if grund is None:
        # Kein Infrastruktur-Problem: Die Quelle hat ja geantwortet, sie lebt.
        q.melde_erfolg()
        return None
    q.melde_fehler(grund)
    return grund


def darf_versuchen(name: str) -> bool:
    return quelle(name).darf_versuchen()


def genesung_abholen(name: str) -> bool:
    """True GENAU EINMAL nach jeder Genesung — der Auslöser für die
    Wiederaufnahme wartender Arbeit."""
    q = quelle(name)
    if q.genesen:
        q.genesen = False
        return True
    return False


def status() -> dict:
    """Gesamtbild für die App."""
    kranke = [q for q in QUELLEN.values() if not q.gesund]
    return {
        "ok": not kranke,
        "quellen": {n: q.als_dict() for n, q in QUELLEN.items()},
        "meldung": GRUND_TEXTE.get(kranke[0].grund or "") if kranke else None,
        "grund": kranke[0].grund if kranke else None,
    }


def zuruecksetzen() -> None:
    """Nur für Tests."""
    for q in QUELLEN.values():
        q.gesund, q.grund, q.fehlversuche = True, None, 0
        q.seit = q.naechster_test = 0.0
        q.genesen = False
