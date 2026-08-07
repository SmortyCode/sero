from bot.ebay.inventory import AUCTION_DURATIONS, build_offer_payload

POLICIES = {"merchant_location_key": "loc", "fulfillment_policy_id": "f",
            "payment_policy_id": "p", "return_policy_id": "r"}


def _payload(days):
    return build_offer_payload(
        POLICIES, "SKU1", category_id="1", price_eur="1.00",
        listing_description="x", listing_format="AUCTION", auction_days=days)


def test_all_durations_map_to_ebay_enum():
    assert AUCTION_DURATIONS == {1: "DAYS_1", 3: "DAYS_3", 5: "DAYS_5",
                                 7: "DAYS_7", 10: "DAYS_10"}


def test_one_day_auction():
    assert _payload(1)["listingDuration"] == "DAYS_1"


def test_three_day_auction():
    assert _payload(3)["listingDuration"] == "DAYS_3"


def test_default_and_invalid_fall_back_to_7():
    assert _payload(7)["listingDuration"] == "DAYS_7"
    assert _payload(99)["listingDuration"] == "DAYS_7"  # ungültig -> 7


def test_fixed_price_ignores_duration():
    p = build_offer_payload(POLICIES, "SKU1", category_id="1", price_eur="9.90",
                            listing_description="x", listing_format="FIXED_PRICE",
                            auction_days=1)
    assert "listingDuration" not in p
    assert p["availableQuantity"] == 1
