"""Die 18+-Versand-Weiche (04.08.2026) — eBays titelbasierte Jugendschutz-Sperre.

Gemessen an Svens GTA-Listings: eBay behandelt „Grand Theft Auto"-Titel als
USK 18, egal was im Payload steht (unsere Listings trugen NULL Altersangaben
und landeten trotzdem in der Sperre — unsichtbar für anonyme Käufer,
Versandoptionen im Verkäufer-UI gesperrt). Solche Titel brauchen die
Versandrichtlinie mit DHL-Alterssichtprüfung.
"""

import pytest

from bot.ebay.inventory import AGE18_TITEL, policies_fuer_titel

STANDARD = {"fulfillment_policy_id": "normal-123", "payment_policy_id": "p",
            "return_policy_id": "r", "merchant_location_key": "m"}


@pytest.fixture
def mit_18er_policy(monkeypatch):
    monkeypatch.setenv("EBAY_FULFILLMENT_POLICY_18_ID", "achtzehn-999")


@pytest.mark.parametrize("titel", [
    "Grand Theft Auto Vice City PS2 USA WATA 9.8 sealed",
    "GTA San Andreas PS2 Neu",
    "Manhunt PS2 OVP",
])
def test_18er_titel_bekommen_die_sichtpruefungs_policy(mit_18er_policy, titel):
    p = policies_fuer_titel(STANDARD, titel)
    assert p["fulfillment_policy_id"] == "achtzehn-999"
    assert p["payment_policy_id"] == "p"          # Rest bleibt unangetastet


@pytest.mark.parametrize("titel", [
    "Pokémon Glurak ex 199/165 CGC 10",
    "One Piece Band 103 Manga",
    "Grandia II Dreamcast",                        # „grand" allein reicht nicht
])
def test_normale_titel_behalten_die_standard_policy(mit_18er_policy, titel):
    assert policies_fuer_titel(STANDARD, titel)["fulfillment_policy_id"] == "normal-123"


def test_ohne_konfigurierte_policy_keine_weiche(monkeypatch):
    """Fehlt die 18+-Policy in der Umgebung, bleibt alles beim Alten — die
    Weiche darf nie auf eine leere ID zeigen."""
    monkeypatch.delenv("EBAY_FULFILLMENT_POLICY_18_ID", raising=False)
    p = policies_fuer_titel(STANDARD, "Grand Theft Auto III PS2")
    assert p["fulfillment_policy_id"] == "normal-123"


def test_muster_ist_wortgrenzen_fest():
    assert AGE18_TITEL.search("GTA Vice City")
    assert not AGE18_TITEL.search("Photografie-Buch")   # „gta" nicht als Teilwort
