from bot.fees import estimate_fee, is_card_fee_category


def test_svens_booster_case():
    """Realer Fall: 5x 65 € Booster-Bundles, Sammelkarten-Kategorie -> ~36 € Gebühr."""
    fee = estimate_fee("Sammelkartenspiele/TCG Karten-Sets", 65.0, quantity=5)
    assert fee["applies"] is True
    # 325 € * 11 % + 0,45 € = 36,20 € (eBay rechnet auf Gebührengrundlage abzgl. Rabatte,
    # unsere Schätzung liegt bewusst leicht drüber = keine bösen Überraschungen)
    assert 33.0 <= fee["fee"] <= 37.0
    assert fee["net"] == round(325 - fee["fee"], 2)


def test_plush_is_free_for_private():
    fee = estimate_fee("Plüschtiere & Kuscheltiere", 25.0)
    assert fee["applies"] is False
    assert fee["fee"] == 0.0
    assert fee["net"] == 25.0


def test_business_pays_everywhere():
    """Gewerblich: auch Plüsch/Technik kosten Provision (~11 % + 0,45 €)."""
    fee = estimate_fee("Plüschtiere & Kuscheltiere", 25.0, business=True)
    assert fee["applies"] is True
    assert fee["label"] == "gewerblich"
    assert abs(fee["fee"] - (25.0 * 0.11 + 0.45)) < 0.01


def test_business_card_uses_card_label_rate():
    fee = estimate_fee("TCG OVP Displays", 65.0, quantity=5, business=True)
    assert fee["applies"] is True
    assert 33.0 <= fee["fee"] <= 37.0


def test_tier_split_above_990():
    fee = estimate_fee("Einzelkarten Pokémon", 1500.0)
    expected = 990 * 0.11 + 510 * 0.03 + 0.45
    assert abs(fee["fee"] - round(expected, 2)) < 0.01


def test_small_order_no_fixed_fee():
    fee = estimate_fee("Einzelkarten", 5.0)
    assert fee["fee"] == round(5.0 * 0.11, 2)  # unter 10 € keine Fixgebühr


def test_category_detection():
    assert is_card_fee_category("Sammelkartenspiele/TCG > Einzelkarten") is True
    assert is_card_fee_category("Booster Packs") is True
    assert is_card_fee_category("Videospiele & Konsolen") is False
    assert is_card_fee_category(None) is False
