import json

from bot.ebay.inventory import generate_sku, translate_ebay_error
from bot.main import parse_price


def _ebay_error(error_id, message, params=None):
    err = {"errorId": error_id, "message": message}
    if params:
        err["parameters"] = params
    return json.dumps({"errors": [err]})


def test_location_error_25002():
    out = translate_ebay_error(_ebay_error(25002, "Invalid location"), 400)
    assert "25002" in out
    assert "setup_location.py" in out


def test_fulfillment_error_25007():
    out = translate_ebay_error(_ebay_error(25007, "No valid shipping service"), 400)
    assert "Versandservice" in out


def test_content_language_error_25709():
    out = translate_ebay_error(_ebay_error(25709, "Invalid value for field"), 400)
    assert "Content-Language" in out


def test_aspect_error_without_known_code():
    out = translate_ebay_error(_ebay_error(99999, "The aspect Marke is required"), 400)
    assert "Item-Specifics" in out


def test_unparseable_body_falls_back_to_http():
    out = translate_ebay_error("<html>Gateway Timeout</html>", 504)
    assert "HTTP 504" in out


def test_sku_format():
    """Seit 03.08. bewusst NEUTRAL: eBay zeigt die SKU dem Verkäufer als
    „Bestandseinheit" an — vorher stand dort „SERO-20260803-MQ56" und verriet
    Werkzeug und Einstelldatum. Jetzt zehn Zeichen ohne Aussage."""
    sku = generate_sku()
    assert len(sku) == 10
    assert sku.isalnum() and sku.isupper()
    assert "SERO" not in sku
    assert len({generate_sku() for _ in range(200)}) == 200, "SKUs müssen eindeutig sein"


def test_parse_price():
    assert parse_price("16,90") == "16.90"
    assert parse_price("16.90") == "16.90"
    assert parse_price("17") == "17.00"
    assert parse_price(" 12,5 € ") == "12.50"
    assert parse_price("gratis") is None
    assert parse_price("-5") is None
    assert parse_price("0") is None


def _policies():
    return {"merchant_location_key": "loc-key", "fulfillment_policy_id": "f1",
            "payment_policy_id": "p1", "return_policy_id": "r1"}


def test_offer_payload_fixed_price():
    from bot.ebay.inventory import build_offer_payload
    cfg = _policies()
    p = build_offer_payload(cfg, "SKU1", category_id="123", price_eur="16.90",
                            listing_description="<p>x</p>")
    assert p["format"] == "FIXED_PRICE"
    assert p["pricingSummary"] == {"price": {"value": "16.90", "currency": "EUR"}}
    assert "listingDuration" not in p
    assert p["merchantLocationKey"] == "loc-key"


def test_offer_payload_auction():
    from bot.ebay.inventory import build_offer_payload
    cfg = _policies()
    p = build_offer_payload(cfg, "SKU1", category_id="123", price_eur="9.99",
                            listing_description="<p>x</p>", listing_format="AUCTION")
    assert p["format"] == "AUCTION"
    assert p["listingDuration"] == "DAYS_7"
    assert p["pricingSummary"] == {"auctionStartPrice": {"value": "9.99", "currency": "EUR"}}


def test_offer_payload_auction_has_no_quantity():
    from bot.ebay.inventory import build_offer_payload
    cfg = _policies()
    p = build_offer_payload(cfg, "SKU1", category_id="123", price_eur="1.00",
                            listing_description="x", listing_format="AUCTION")
    assert "availableQuantity" not in p  # eBay-Fehler 25762
    fixed = build_offer_payload(cfg, "SKU1", category_id="123", price_eur="9.99",
                                listing_description="x")
    assert fixed["availableQuantity"] == 1


def test_price_rules():
    from bot.main import suggest_fixed_price, apply_price_rule, AUCTION_START_PRICE
    # Sofortkauf: ~5% unter Median, auf .90 endend
    assert suggest_fixed_price(16.90) == "15.90"
    assert suggest_fixed_price(20.00) == "18.90"
    assert suggest_fixed_price(100.00) == "94.90"
    assert suggest_fixed_price(3.00) == "2.85"   # Kleinpreise: einfach 5% unter Median
    assert suggest_fixed_price(0.50) == "1.00"   # nie unter 1 €
    # Auktion ohne Vorlage/Markt: kein stiller 1-€-Default
    draft = {"format": "AUCTION", "price_research": {"median": 50.0}, "listing": {}}
    apply_price_rule(draft)
    assert draft["price"] is None
    # Auktion mit Vorlage „1 € Start"
    draft = {"format": "AUCTION", "listing": {"tpl_price": AUCTION_START_PRICE}}
    apply_price_rule(draft)
    assert draft["price"] == AUCTION_START_PRICE == "1.00"
    # Auktion mit belegtem Marktwert
    draft = {"format": "AUCTION",
             "listing": {"market_value": "60.00", "price_state": "belegt"}}
    apply_price_rule(draft)
    assert float(draft["price"]) == 60.0 or float(draft["price"]) <= 60.0
    # Festpreis ohne Recherche: kein Preis (Nutzer muss setzen)
    draft = {"format": "FIXED_PRICE", "price_research": None}
    apply_price_rule(draft)
    assert draft["price"] is None


def test_resolve_condition():
    from bot.ebay.metadata import resolve_condition
    # Zustand erlaubt -> unverändert
    assert resolve_condition("NEW", ["1000", "3000"], "") == ("NEW", False)
    # Leere Policy (API nicht erreichbar) -> unverändert
    assert resolve_condition("NEW", [], "") == ("NEW", False)
    # Karten-Kategorie: NEW -> Ungraded (4000), ausser Graded-Marker im Text
    assert resolve_condition("NEW", ["2750", "4000"], "Glurak Holo 1. Edition") == ("USED_VERY_GOOD", True)
    assert resolve_condition("NEW", ["2750", "4000"], "Glurak PSA 9 graded") == ("LIKE_NEW", True)
    assert resolve_condition("USED_GOOD", ["2750", "4000"], "Pikachu Karte") == ("USED_VERY_GOOD", True)
    # Sonstige Kategorie: numerisch nächster erlaubter Zustand
    assert resolve_condition("NEW", ["1500", "5000"], "") == ("NEW_OTHER", True)
    assert resolve_condition("USED_ACCEPTABLE", ["1000", "5000"], "") == ("USED_GOOD", True)


def test_reorder_photos():
    from bot.main import reorder_photos
    photos = ["a.jpg", "b.jpg", "c.jpg"]
    assert reorder_photos(photos, 1) == ["b.jpg", "a.jpg", "c.jpg"]
    assert reorder_photos(photos, 2) == ["c.jpg", "a.jpg", "b.jpg"]
    assert reorder_photos(photos, 0) == photos      # schon vorn
    assert reorder_photos(photos, 7) == photos      # ausserhalb -> unverändert
    assert reorder_photos(photos, None) == photos   # Feld fehlt -> unverändert
    assert reorder_photos(photos, "1") == ["b.jpg", "a.jpg", "c.jpg"]  # Claude liefert String


def _card_policy():
    return [
        {"conditionId": "2750", "conditionDescriptors": [
            {"conditionDescriptorId": "27501",
             "conditionDescriptorConstraint": {"usage": "REQUIRED", "mode": "SELECTION_ONLY"},
             "conditionDescriptorValues": [
                 {"conditionDescriptorValueId": "275010", "conditionDescriptorValueName": "Professional Sports Authenticator (PSA)"},
                 {"conditionDescriptorValueId": "275013", "conditionDescriptorValueName": "Beckett Grading Services (BGS)"},
                 {"conditionDescriptorValueId": "2750123", "conditionDescriptorValueName": "Sonstige"}]},
            {"conditionDescriptorId": "27502",
             "conditionDescriptorConstraint": {"usage": "REQUIRED", "mode": "SELECTION_ONLY"},
             "conditionDescriptorValues": [
                 {"conditionDescriptorValueId": "275020", "conditionDescriptorValueName": "10"},
                 {"conditionDescriptorValueId": "275021", "conditionDescriptorValueName": "9.5"},
                 {"conditionDescriptorValueId": "275022", "conditionDescriptorValueName": "9"}]},
            {"conditionDescriptorId": "27503",
             "conditionDescriptorConstraint": {"mode": "FREE_TEXT"},
             "conditionDescriptorValues": []}]},
        {"conditionId": "4000", "conditionDescriptors": [
            {"conditionDescriptorId": "40001",
             "conditionDescriptorConstraint": {"usage": "REQUIRED", "mode": "SELECTION_ONLY"},
             "conditionDescriptorValues": [
                 {"conditionDescriptorValueId": "400010", "conditionDescriptorValueName": "Nahezu neuwertig oder besser (Near Mint or Better)"},
                 {"conditionDescriptorValueId": "400015", "conditionDescriptorValueName": "Leicht bespielt (Exzellent/Excellent)"}]}]},
        {"conditionId": "3000"},
    ]


def test_descriptors_graded_from_text_asks_for_cert():
    from bot.ebay.metadata import build_condition_descriptors
    # Bewerter+Note im Text, aber keine Zertifikatsnummer -> Rückfrage (eBay-Fehler 25066)
    desc, frage = build_condition_descriptors("LIKE_NEW", _card_policy(), {}, "Glurak Holo PSA 9 Karte")
    assert desc is None
    assert frage and "Zertifikatsnummer" in frage


def test_descriptors_graded_complete_from_text_and_info():
    from bot.ebay.metadata import build_condition_descriptors
    listing = {"graded_info": {"cert_number": "87654321"}}
    desc, frage = build_condition_descriptors("LIKE_NEW", _card_policy(), listing, "Glurak Holo PSA 9 Karte")
    assert frage is None
    assert {"name": "27501", "values": ["275010"]} in desc
    assert {"name": "27502", "values": ["275022"]} in desc
    assert {"name": "27503", "additionalInfo": "87654321"} in desc


def test_descriptors_graded_from_claude_info():
    from bot.ebay.metadata import build_condition_descriptors
    listing = {"graded_info": {"grader": "BGS", "grade": "9.5", "cert_number": "12345678"}}
    desc, frage = build_condition_descriptors("LIKE_NEW", _card_policy(), listing, "")
    assert frage is None
    assert {"name": "27501", "values": ["275013"]} in desc
    assert {"name": "27502", "values": ["275021"]} in desc
    assert {"name": "27503", "additionalInfo": "12345678"} in desc


def test_descriptors_graded_missing_info_asks():
    from bot.ebay.metadata import build_condition_descriptors
    desc, frage = build_condition_descriptors("LIKE_NEW", _card_policy(), {}, "Glurak Holo Karte")
    assert desc is None
    assert frage and "PSA 9.5" in frage


def test_descriptors_unknown_grader_falls_back_sonstige():
    from bot.ebay.metadata import build_condition_descriptors
    listing = {"graded_info": {"grader": "XYZGRADING", "grade": "10", "cert_number": "55555555"}}
    desc, frage = build_condition_descriptors("LIKE_NEW", _card_policy(), listing, "")
    assert frage is None
    assert {"name": "27501", "values": ["2750123"]} in desc


def test_descriptors_ungraded_card_condition():
    from bot.ebay.metadata import build_condition_descriptors
    desc, frage = build_condition_descriptors("USED_VERY_GOOD", _card_policy(),
                                              {"condition_description": "leicht bespielt"}, "")
    assert frage is None
    assert desc == [{"name": "40001", "values": ["400015"]}]
    desc, _ = build_condition_descriptors("USED_VERY_GOOD", _card_policy(), {}, "")
    assert desc == [{"name": "40001", "values": ["400010"]}]


def test_descriptors_condition_without_descriptors():
    from bot.ebay.metadata import build_condition_descriptors
    desc, frage = build_condition_descriptors("USED_EXCELLENT", _card_policy(), {}, "")
    assert desc is None and frage is None


def test_resolve_condition_card_category_rejects_phantom_3000():
    from bot.ebay.metadata import resolve_condition
    # eBay-Metadata listet 3000 als erlaubt, publishOffer lehnt es aber ab (25059) —
    # in Karten-Kategorien darf NUR Graded/Ungraded gewählt werden.
    allowed = ["2750", "3000", "4000"]
    assert resolve_condition("USED_EXCELLENT", allowed, "Pikachu Holo Karte") == ("USED_VERY_GOOD", True)
    assert resolve_condition("USED_EXCELLENT", allowed, "Glurak PSA 9") == ("LIKE_NEW", True)
    # Ungraded bleibt unverändert; "graded" OHNE Slab/Marker wird zu Ungraded korrigiert
    assert resolve_condition("USED_VERY_GOOD", allowed, "x") == ("USED_VERY_GOOD", False)
    assert resolve_condition("LIKE_NEW", allowed, "x") == ("USED_VERY_GOOD", True)
    # Claude hat einen Slab erkannt (graded_info) -> graded, egal was im Text steht
    assert resolve_condition("USED_EXCELLENT", allowed, "Near Mint Karte", is_graded=True) == ("LIKE_NEW", True)
    assert resolve_condition("LIKE_NEW", allowed, "x", is_graded=True) == ("LIKE_NEW", False)


def test_ensure_card_condition_raw_card_not_graded():
    """Rohkarte darf trotz leerem graded_info / „Neuwertig“ nicht Graded werden."""
    from bot.ebay.metadata import ensure_card_condition, has_real_graded_info

    assert has_real_graded_info(None) is False
    assert has_real_graded_info({}) is False
    assert has_real_graded_info({"grader": "PSA"}) is False
    assert has_real_graded_info({"grader": "PSA", "grade": "10"}) is True

    allowed = ["2750", "4000"]
    listing = {"condition": "LIKE_NEW", "graded_info": {}}
    assert ensure_card_condition(listing, allowed, "Luffy Leader One Piece") == "USED_VERY_GOOD"
    assert "graded_info" not in listing

    listing2 = {"condition": "Neuwertig", "graded_info": {"grader": "", "grade": ""}}
    assert ensure_card_condition(listing2, allowed, "Pikachu Holo") == "USED_VERY_GOOD"

    listing3 = {"condition": "USED_VERY_GOOD",
                "graded_info": {"grader": "PSA", "grade": "9", "cert_number": "1"}}
    assert ensure_card_condition(listing3, allowed, "Glurak") == "LIKE_NEW"


def test_offer_payload_quantity():
    from bot.ebay.inventory import build_offer_payload
    cfg = _policies()
    p = build_offer_payload(cfg, "S", category_id="1", price_eur="4.99",
                            listing_description="x", quantity=5)
    assert p["availableQuantity"] == 5
    # Auktion ignoriert Stückzahl (kein availableQuantity erlaubt)
    a = build_offer_payload(cfg, "S", category_id="1", price_eur="1.00",
                            listing_description="x", listing_format="AUCTION", quantity=5)
    assert "availableQuantity" not in a


def test_sanitize_aspects():
    from bot.ebay.inventory import sanitize_aspects
    raw = {
        "Marke": ["Pokémon"],
        "Langtext": ["x" * 200],                  # > 65 Zeichen -> kürzen
        "Leer": ["", None],                       # nur leere Werte -> Aspect fliegt raus
        "Skalar": "Einzelwert",                   # kein Array -> wrappen
        "Viele": [str(i) for i in range(30)],     # > 10 Werte -> kappen
    }
    clean = sanitize_aspects(raw)
    assert clean["Marke"] == ["Pokémon"]
    assert len(clean["Langtext"][0]) == 65
    assert "Leer" not in clean
    assert clean["Skalar"] == ["Einzelwert"]
    assert len(clean["Viele"]) == 10


def test_offer_payload_best_offer():
    from bot.ebay.inventory import build_offer_payload
    cfg = _policies()
    p = build_offer_payload(cfg, "S", category_id="1", price_eur="70.00",
                            listing_description="x",
                            best_offer={"enabled": True, "min_price": "50.00"})
    terms = p["listingPolicies"]["bestOfferTerms"]
    assert terms["bestOfferEnabled"] is True
    assert terms["autoDeclinePrice"] == {"value": "50.00", "currency": "EUR"}
    # Ohne min_price: nur aktivieren
    p2 = build_offer_payload(cfg, "S", category_id="1", price_eur="70.00",
                             listing_description="x", best_offer={"enabled": True})
    assert "autoDeclinePrice" not in p2["listingPolicies"]["bestOfferTerms"]
    # Auktion: kein Best Offer
    a = build_offer_payload(cfg, "S", category_id="1", price_eur="1.00",
                            listing_description="x", listing_format="AUCTION",
                            best_offer={"enabled": True, "min_price": "50.00"})
    assert "bestOfferTerms" not in a["listingPolicies"]


def test_user_price_overrides_everything():
    from bot.main import apply_price_rule
    # Festpreis: Verkäuferpreis schlägt Median-Regel
    draft = {"format": "FIXED_PRICE", "price_research": {"median": 30.0},
             "listing": {"user_price": "70.00"}}
    apply_price_rule(draft)
    assert draft["price"] == "70.00"
    # Auktion: expliziter Startpreis schlägt alles
    draft = {"format": "AUCTION", "listing": {"user_price": "5,00"}}
    apply_price_rule(draft)
    assert draft["price"] == "5.00"
    # Ohne Verkäuferpreis und ohne Vorlage: kein stiller 1-€-Default
    draft = {"format": "AUCTION", "listing": {}}
    apply_price_rule(draft)
    assert draft["price"] is None
    # Vorlage „1 € Start" bleibt möglich
    draft = {"format": "AUCTION", "listing": {"tpl_price": "1.00"}}
    apply_price_rule(draft)
    assert draft["price"] == "1.00"


def test_usk_age_restriction_clean_message():
    """25019 mit USK-Sperre -> klare Anleitung, KEIN HTML-Wust."""
    import json
    from bot.ebay.inventory import translate_ebay_error
    err = {"errors": [{"errorId": 25019, "message": "Cannot revise listing.",
        "parameters": [
            {"name": "0", "value": "<font color='#757575'>Computerspiel ab 18...</font>"},
            {"name": "2", "value": "BLOCK_DE_USK_NewMessaging_NOV2015"}]}]}
    out = translate_ebay_error(json.dumps(err), 400)
    assert "🔞" in out
    assert "Altersprüfung" in out
    assert "<font" not in out          # kein HTML-Blob mehr
    assert "BLOCK_DE_USK" not in out    # kein technischer Code


def test_unknown_error_keeps_short_params_only():
    import json
    from bot.ebay.inventory import translate_ebay_error
    err = {"errors": [{"errorId": 88888, "message": "X", "parameters": [
        {"name": "field", "value": "title"},
        {"name": "blob", "value": "<html>" + "x" * 300 + "</html>"}]}]}
    out = translate_ebay_error(json.dumps(err), 400)
    assert "field=title" in out
    assert "<html>" not in out
