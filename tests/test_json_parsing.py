import json

import pytest

from bot.claude_client import parse_listing_json

VALID = {
    "title": "Pokémon Glurak Plüschtier 30cm",
    "subtitle": None,
    "description_html": "<p>Schönes Plüschtier, siehe Fotos.</p>",
    "category_query": "Pokemon Plüschtier",
    "condition": "USED_GOOD",
    "condition_description": "Leichte Gebrauchsspuren",
    "aspects": {"Marke": ["Pokémon"], "Charakter": ["Glurak"]},
    "search_query_for_pricing": "Glurak Plüschtier 30cm",
    "estimated_weight_grams": 300,
}


def test_plain_json():
    assert parse_listing_json(json.dumps(VALID))["title"] == VALID["title"]


def test_json_with_fences():
    text = "```json\n" + json.dumps(VALID) + "\n```"
    assert parse_listing_json(text)["condition"] == "USED_GOOD"


def test_json_with_bare_fences():
    text = "```\n" + json.dumps(VALID) + "\n```"
    assert parse_listing_json(text)["aspects"]["Marke"] == ["Pokémon"]


def test_json_with_whitespace():
    assert parse_listing_json("\n\n  " + json.dumps(VALID) + "  \n") is not None


def test_invalid_json_raises():
    with pytest.raises(json.JSONDecodeError):
        parse_listing_json("Hier ist dein Listing: {kaputt")


def test_missing_required_field_raises():
    broken = {k: v for k, v in VALID.items() if k != "title"}
    with pytest.raises(json.JSONDecodeError):
        parse_listing_json(json.dumps(broken))


def test_ohne_search_query_for_pricing_ok():
    """Phase A: freie Pricing-Query ist kein Pflichtfeld mehr."""
    data = {k: v for k, v in VALID.items() if k != "search_query_for_pricing"}
    out = parse_listing_json(json.dumps(data))
    assert out["title"] == VALID["title"]


def test_identity_candidates_werden_gekuerzt():
    data = dict(VALID)
    data["identity_candidates"] = ["A" * 100, "B", ""] + [f"x{i}" for i in range(10)]
    out = parse_listing_json(json.dumps(data))
    assert out["identity_candidates"] is not None
    assert len(out["identity_candidates"]) <= 8
    assert len(out["identity_candidates"][0]) <= 80


def test_non_object_raises():
    with pytest.raises(json.JSONDecodeError):
        parse_listing_json('["liste", "statt", "objekt"]')
