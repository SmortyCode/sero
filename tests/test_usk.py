import pytest

from bot.main import (USK_VALUES, USK_ASPECT, build_preview, build_usk_menu,
                      current_usk, is_media_category)


def _game_draft(aspects=None):
    return {"id": "x", "chat_id": 1, "status": "ready", "format": "FIXED_PRICE",
            "price": "19.90", "quantity": 1, "photos": ["a.jpg"],
            "category_name": "PC- & Videospiele > Spiele",
            "listing": {"title": "Mario Kart 8", "condition": "USED_GOOD",
                        "description_html": "<p>x</p>", "aspects": aspects or {}}}


def test_usk_button_shown_for_game_category():
    _, kb = build_preview(_game_draft())
    labels = [b.text for row in kb.inline_keyboard for b in row]
    assert any("Altersfreigabe" in l for l in labels)


def test_usk_button_hidden_for_non_media():
    d = _game_draft(); d["category_name"] = "Plüschtiere & Kuscheltiere"
    _, kb = build_preview(d)
    labels = [b.text for row in kb.inline_keyboard for b in row]
    assert not any("Altersfreigabe" in l for l in labels)


def test_set_and_read_usk():
    d = _game_draft({"Altersfreigabe": ["USK ab 12 freigegeben"]})
    assert current_usk(d) == 12
    text, _ = build_preview(d)
    assert "USK ab 12" in text


def test_usk_menu_marks_current():
    d = _game_draft({"Altersfreigabe": ["USK ab 16 freigegeben"]})
    labels = [b.text for row in build_usk_menu(d).inline_keyboard for b in row]
    assert "✅ USK ab 16" in labels


def test_media_detection():
    assert is_media_category("PC- & Videospiele") is True
    assert is_media_category("DVDs & Blu-rays > Filme") is True
    assert is_media_category("Sammelkarten") is False


def test_usk_values_are_ebay_format():
    """Am 03.08. an der echten eBay-Taxonomie geprüft (Kategorie 139973):
    Das Feld heißt „USK-Einstufung" — ein Feld „Altersfreigabe" existiert dort
    GAR NICHT — und die Werte lauten „USK ab X Jahren". Dieser Test behauptete
    vorher das Gegenteil und hat den Fehler damit festgeschrieben."""
    assert USK_VALUES[18] == "USK ab 18 Jahren"
    assert USK_VALUES[0] == "USK ab 0 Jahren"
    assert USK_ASPECT == "USK-Einstufung"


# ── Der Fall vom 03.08.: US-Import lief in eBays Jugendschutz-Sperre ─────────

from bot.ebay.inventory import sanitize_aspects


def test_fremdrating_kommt_nie_ins_usk_feld():
    """Svens GTA III (US-Import, WATA-graded) wurde von eBay als jugendgefährdend
    abgelehnt, weil die Analyse „ESRB Mature 17+" ins deutsche USK-Feld schrieb.
    Von Hand eingestellt ging dasselbe Spiel durch — dort füllt niemand das Feld."""
    raus = sanitize_aspects({"Altersfreigabe": ["ESRB Mature 17+"],
                             "Marke": ["Rockstar Games"]})
    assert "Altersfreigabe" not in raus
    assert "USK-Einstufung" not in raus, "Fremdrating darf NICHT durchrutschen"
    assert raus["Marke"] == ["Rockstar Games"], "andere Merkmale bleiben unberührt"


@pytest.mark.parametrize("wert", [
    "ESRB Mature 17+", "ESRB M", "PEGI 18", "PEGI 16", "CERO Z",
    "ab 18", "indiziert", "Mature", "Adults Only", "unbekannt",
])
def test_alles_ausser_usk_fliegt_raus(wert):
    assert sanitize_aspects({"Altersfreigabe": [wert]}) == {}


@pytest.mark.parametrize("rein,raus", [
    ("USK ab 0 freigegeben", "USK ab 0 Jahren"),      # alte eigene Schreibweise
    ("USK ab 12 freigegeben", "USK ab 12 Jahren"),
    ("USK ab 16 Jahren", "USK ab 16 Jahren"),         # schon korrekt
    ("USK ab 18 Jahren", "USK ab 18 Jahren"),
    ("usk ab 6 jahren", "usk ab 6 jahren"),           # Groß/Klein egal
])
def test_echte_usk_werte_bleiben(rein, raus):
    e = sanitize_aspects({"Altersfreigabe": [rein]})
    assert e.get("USK-Einstufung") == [raus], e


def test_feldname_wird_auf_ebays_namen_normalisiert():
    """In der Spiele-Kategorie (139973) heißt das Feld „USK-Einstufung" —
    ein Feld „Altersfreigabe" gibt es dort gar nicht."""
    e = sanitize_aspects({"Altersfreigabe": ["USK ab 12 Jahren"]})
    assert list(e.keys()) == ["USK-Einstufung"]


def test_current_usk_erkennt_alte_und_neue_schreibweise():
    from bot.main import current_usk
    for feld in ("Altersfreigabe", "USK-Einstufung"):
        for wert, erwartet in (("USK ab 16 freigegeben", 16), ("USK ab 16 Jahren", 16)):
            d = {"listing": {"aspects": {feld: [wert]}}}
            assert current_usk(d) == erwartet, (feld, wert)
    assert current_usk({"listing": {"aspects": {"Altersfreigabe": ["ESRB Mature 17+"]}}}) is None
