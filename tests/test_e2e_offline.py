"""Phase D — Automatisierter Offline-E2E (Temp-DB, Fake recognize/price/ebay).

Kein Netz, keine echte data.db, kein publishOffer. Deckt Claim + uncertain
ohne Auto-Retry. Handy- und Live-Listing bleiben manuell (siehe E2E_HANDY.md).
"""
from __future__ import annotations

import asyncio
import time

import pytest

from bot.drafts import Store
from web.identity import resolve_pricing_query
from web.publish import FakeEbay, _set_intent, claim_or_create_intent, execute_publish


@pytest.fixture()
def store(tmp_path, monkeypatch):
    db = tmp_path / "e2e.db"
    col = tmp_path / "col"
    col.mkdir()
    monkeypatch.setenv("SERO_DB", str(db))
    monkeypatch.setenv("SERO_COL_DIR", str(col))
    return Store(db)


def _fake_recognize_item() -> dict:
    """Fake-Erkennung: Rohkarte mit sichtbaren Feldern (pricing_ready)."""
    return {
        "status": "ready",
        "name": "Pikachu",
        "photos": ["fake.jpg"],
        "card_info": {
            "name": "Pikachu",
            "set": "Base Set",
            "number": "58",
            "set_total": "102",
            "language": "en",
            "game": "Pokémon",
        },
        "analysis": {
            "product_kind": "raw_card",
            "card_info": {
                "name": "Pikachu",
                "set": "Base Set",
                "number": "58",
                "set_total": "102",
                "language": "en",
                "game": "Pokémon",
            },
            # Freie LLM-Query — darf Preise NICHT steuern
            "search_query_for_pricing": "IGNORE THIS LLM QUERY pokemon rare",
        },
        "est_value": 4.5,
        "price_state": "belegt",
        "price_source": "fake_e2e",
        "sold_count": 5,
        "created_at": time.time(),
    }


def test_e2e_offline_identitaet_claim_uncertain(store):
    item = _fake_recognize_item()
    pq, ready, ident, ev = resolve_pricing_query(item)
    assert ready is True, ev.blocking_reasons
    assert pq and "IGNORE" not in pq
    assert "pokemon rare" not in (pq or "").lower()

    # Entwurf gehört chat_id=1 — Claim mit derselben ID
    did = store.create_draft(1, {
        "status": "ready",
        "sku": "SERO-E2E1",
        "listing": {"title": "Pikachu #58"},
        "price": "4.50",
    })
    ebay = FakeEbay()
    ebay.sku_offer["SERO-E2E1"] = "OFF-E2E"
    ebay.timeout_on_publish = True
    ebay.timeout_on_lookup = True

    intent = claim_or_create_intent(
        store, draft_id=did, account_id=1, sku="SERO-E2E1")
    assert intent and intent["state"] == "publishing"

    _set_intent(store, intent["id"], offer_id="OFF-E2E")
    out = asyncio.run(execute_publish(store, ebay, intent["id"]))
    assert out["state"] == "publish_uncertain"

    # Kein Auto-Retry
    out2 = asyncio.run(execute_publish(store, ebay, intent["id"]))
    assert out2["state"] == "publish_uncertain"
    assert ebay.publish_calls == 1
    assert claim_or_create_intent(
        store, draft_id=did, account_id=1, sku="SERO-E2E1") is None


def test_e2e_offline_happy_dry_run(store):
    did = store.create_draft(1, {
        "status": "ready", "sku": "SKU-DRY",
        "listing": {"title": "Test"},
    })
    ebay = FakeEbay()
    ebay.sku_offer["SKU-DRY"] = "OFF-DRY"
    intent = claim_or_create_intent(
        store, draft_id=did, account_id=1, sku="SKU-DRY")
    assert intent is not None
    out = asyncio.run(execute_publish(store, ebay, intent["id"], dry_run=True))
    assert out["state"] == "dry_run_done"
    assert ebay.publish_calls == 0
