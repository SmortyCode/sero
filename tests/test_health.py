"""Der Health-Wächter — Svens „festes, autonomes System" (04.08.2026).

Anlass: Ein leeres API-Guthaben legte die App still lahm. Jeder Scan lief in
denselben Fehler, jedes Stück landete einzeln auf „error", und niemand sah
die gemeinsame Ursache. Nach dem Aufladen half kein Automatismus — Sven
musste selbst nachhelfen.

Die Zusagen, die diese Datei bewacht:
  1. Infrastruktur-Ausfälle werden als solche erkannt (nicht als Stück-Fehler).
  2. Bei bekannter Krankheit wird nicht sinnlos angerufen (Backoff).
  3. Die Genesung löst GENAU EINMAL die Wiederaufnahme aus.
  4. Ein echter Stück-Fehler macht die Quelle NICHT krank.
"""

import time

import pytest

from web import health


@pytest.fixture(autouse=True)
def frischer_zustand():
    health.zuruecksetzen()
    yield
    health.zuruecksetzen()


class Fehler(Exception):
    pass


# ────────────────────── Klassifizierung ──────────────────────

@pytest.mark.parametrize("text,erwartet", [
    ("Your credit balance is too low to access the Anthropic API.", "kein_guthaben"),
    ("Error code: 429 - {'type': 'rate_limit_error'}", "ueberlastet"),
    ("Overloaded", "ueberlastet"),
    ("Error code: 529", "ueberlastet"),
    ("invalid x-api-key", "schluessel"),
    # Das hier ist KEIN Infrastruktur-Problem — dieses eine Foto ist schuld
    ("Could not process image: corrupt JPEG", None),
    ("keine JSON-Antwort: 'Ich sehe kein…'", None),
])
def test_klassifizierung(text, erwartet):
    assert health.klassifiziere(Fehler(text)) == erwartet


def test_netzfehler_ueber_klassennamen():
    class APIConnectionError(Exception):
        pass
    assert health.klassifiziere(APIConnectionError("boom")) == "netz"


# ────────────────────── Der Lebenszyklus ──────────────────────

def test_ausfall_genesung_und_einmaliger_weckruf():
    """Der Kern des autonomen Betriebs: krank → Backoff → gesund → EIN Weckruf."""
    assert health.darf_versuchen("ki")

    grund = health.melde("ki", Fehler("Your credit balance is too low"))
    assert grund == "kein_guthaben"
    assert not health.quelle("ki").gesund
    # Solange krank: kein sinnloser Aufruf
    assert not health.darf_versuchen("ki")
    assert not health.genesung_abholen("ki")

    # Quelle antwortet wieder
    assert health.melde("ki", None) is None
    assert health.quelle("ki").gesund
    # Der Weckruf kommt GENAU EINMAL — sonst würde die Rettung jede Runde
    # alles neu anstoßen
    assert health.genesung_abholen("ki") is True
    assert health.genesung_abholen("ki") is False


def test_backoff_waechst():
    """Ein längerer Ausfall darf keine Logflut erzeugen."""
    abstaende = []
    for _ in range(4):
        health.melde("ki", Fehler("Overloaded"))
        abstaende.append(health.quelle("ki").naechster_test - time.time())
    assert abstaende[0] < abstaende[-1], f"Backoff wächst nicht: {abstaende}"
    assert abstaende[-1] >= 100


def test_stueckfehler_macht_die_quelle_nicht_krank():
    """DIE wichtigste Abgrenzung: Ein unlesbares Foto ist kein Systemausfall.
    Würde es einen auslösen, hielte ein einziges kaputtes Bild die ganze
    Warteschlange an."""
    grund = health.melde("ki", Fehler("Could not process image"))
    assert grund is None
    assert health.quelle("ki").gesund
    assert health.darf_versuchen("ki")


def test_erster_test_nach_ausfall_ist_erlaubt():
    """Nach Ablauf des Backoff darf (und muss) wieder geprüft werden."""
    health.melde("ki", Fehler("Overloaded"))
    health.quelle("ki").naechster_test = time.time() - 1
    assert health.darf_versuchen("ki")


# ────────────────────── Der Status für die App ──────────────────────

def test_status_gruen():
    st = health.status()
    assert st["ok"] is True and st["meldung"] is None


def test_status_nennt_klartext():
    health.melde("ki", Fehler("Your credit balance is too low"))
    st = health.status()
    assert st["ok"] is False
    assert st["grund"] == "kein_guthaben"
    assert "console.anthropic.com" in st["meldung"]
    assert st["quellen"]["ki"]["gesund"] is False


def test_jeder_grund_hat_einen_text():
    """Kein Grund-Code ohne Nutzertext — sonst steht die App stumm da."""
    for grund in ("kein_guthaben", "ueberlastet", "netz", "schluessel", "ebay_auth"):
        assert health.GRUND_TEXTE.get(grund), f"Text fehlt für {grund}"


def test_quellen_sind_unabhaengig():
    """Ein eBay-Problem darf die KI-Analyse nicht anhalten und umgekehrt."""
    health.melde("ebay", Fehler("invalid x-api-key"))
    assert not health.quelle("ebay").gesund
    assert health.quelle("ki").gesund and health.darf_versuchen("ki")
