"""Preflight-Checkliste — nur Fake-Daten, kein eBay."""
from __future__ import annotations

from web.preflight import preflight_draft


def _ok_draft(**over):
    d = {
        "status": "ready",
        "listing": {
            "title": "Testkarte OP01-001",
            "description_html": "<p>Beschreibung</p>",
            "condition": "USED_VERY_GOOD",
        },
        "photos": ["/tmp/a.jpg"],
        "category_id": "183454",
        "price": "12.50",
        "format": "FIXED_PRICE",
        "quantity": 1,
    }
    d.update(over)
    return d


def _ok_policies():
    return {
        "fulfillment_policy_id": "f1",
        "payment_policy_id": "p1",
        "return_policy_id": "r1",
        "merchant_location_key": "home",
    }


def test_valid_draft_passes():
    pf = preflight_draft(_ok_draft(), policies=_ok_policies(), ebay_connected=True)
    assert pf["valid"] is True
    assert pf["issues"] == []


def test_uncertain_ohne_frage_blockiert_nicht():
    pf = preflight_draft(_ok_draft(status="uncertain"), policies=_ok_policies())
    assert pf["valid"] is True
    assert not any(i.get("blocking") and i.get("code") == "REVIEW" for i in pf["issues"])


def test_open_question_blocked():
    pf = preflight_draft(
        _ok_draft(status="uncertain", question="Ist das ein Sakko?"),
        policies=_ok_policies())
    assert pf["valid"] is False
    assert any(i["field"] == "question" for i in pf["issues"])


def test_analyzing_blocked():
    pf = preflight_draft(_ok_draft(status="analyzing"), policies=_ok_policies())
    assert pf["valid"] is False
    assert any(i["code"] == "ANALYZING" for i in pf["issues"])


def test_publish_uncertain_blocked():
    pf = preflight_draft(_ok_draft(status="publish_uncertain"), policies=_ok_policies())
    assert pf["valid"] is False
    assert any(i["code"] == "UNCERTAIN" for i in pf["issues"])


def test_issue_schema_hat_field_id_type_severity_blocking_source():
    pf = preflight_draft(_ok_draft(price=None), policies=_ok_policies())
    price = next(i for i in pf["issues"] if i["field"] == "price")
    assert price["field_id"] == "price"
    assert price["type"] == "missing"
    assert price["severity"] == "error"
    assert price["blocking"] is True
    assert price["source"] == "preflight"
    assert pf["valid"] is False
    pf = preflight_draft(
        _ok_draft(price=None, category_id=None),
        policies=_ok_policies())
    codes = {i["field"] for i in pf["issues"]}
    assert "price" in codes and "category_id" in codes


def test_fixed_plus_auction1_rejected():
    pf = preflight_draft(
        _ok_draft(format="FIXED_PRICE", price_mode="auction1"),
        policies=_ok_policies())
    assert pf["valid"] is False
    assert any(i["code"] == "INCOMPATIBLE" for i in pf["issues"])


def test_auction_qty_and_best_offer_rejected():
    pf = preflight_draft(
        _ok_draft(format="AUCTION", quantity=2,
                  best_offer={"enabled": True, "min_price": "10.00"}, auction_days=7),
        policies=_ok_policies())
    fields = {i["field"] for i in pf["issues"]}
    assert "quantity" in fields
    assert "best_offer" in fields


def test_policies_missing():
    pf = preflight_draft(_ok_draft(), policies={}, ebay_connected=True)
    fields = {i["field"] for i in pf["issues"]}
    assert "shipping" in fields and "payment" in fields and "return" in fields


def test_ebay_disconnected():
    pf = preflight_draft(_ok_draft(), policies=_ok_policies(), ebay_connected=False)
    assert any(i["field"] == "ebay" for i in pf["issues"])


def test_missing_aspect_blocked():
    d = _ok_draft(required_aspects=["Spiel"], listing={
        "title": "Testkarte OP01-001",
        "description_html": "<p>Beschreibung</p>",
        "condition": "USED_VERY_GOOD",
        "aspects": {},
    })
    pf = preflight_draft(d, policies=_ok_policies())
    assert pf["valid"] is False
    assert any(i["field"] == "aspect:Spiel" for i in pf["issues"])
    assert any(i.get("section") == "product" for i in pf["issues"])


def test_item_needs_review_ist_kein_identity_blocker():
    pf = preflight_draft(
        _ok_draft(), policies=_ok_policies(),
        item={"status": "needs_review"})
    assert pf["valid"] is True
    assert not any(i["field"] == "identity" for i in pf["issues"])


def test_identity_uncertain_blockiert_nicht():
    pf = preflight_draft(
        _ok_draft(), policies=_ok_policies(),
        item={"status": "ready", "identity_eval": {"recognition_state": "uncertain"}})
    assert pf["valid"] is True
    assert not any(i["field"] == "identity" for i in pf["issues"])


def test_game_identity_confirmed_clears_preflight_blockers():
    """Games nach Listing-Confirm: needs_review am Stück blockiert nicht mehr."""
    pf = preflight_draft(
        _ok_draft(), policies=_ok_policies(),
        item={
            "status": "ready",
            "identity_user_confirmed": True,
            "identity_eval": {
                "recognition_state": "needs_review",
                "listing_ready": True,
                "blocking_reasons": ["MISSING_REGION"],
            },
        })
    assert pf["valid"] is True
    assert pf["issues"] == []


def test_card_needs_review_ohne_confirm_blockiert_nicht():
    """Unsichere Karte: keine Identitäts-Wand, Publish nicht gesperrt."""
    pf = preflight_draft(
        _ok_draft(), policies=_ok_policies(),
        item={
            "status": "needs_review",
            "identity_eval": {"recognition_state": "needs_review"},
        })
    assert pf["valid"] is True
    fields = {i["field"] for i in pf["issues"]}
    assert "item_status" not in fields
    assert "identity" not in fields
