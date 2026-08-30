"""Phase B — Publish-Intent + Claim (ADR-003 Stufe 2)."""
from __future__ import annotations

import asyncio
import threading

import pytest

from bot.drafts import Store
from web.publish import (
    FakeEbay,
    _set_intent,
    active_intent_for_draft,
    claim_or_create_intent,
    execute_publish,
    get_intent,
    unlock_dry_run_for_live,
)


@pytest.fixture()
def store(tmp_path):
    return Store(tmp_path / "pub.db")


def _draft(store, status="ready"):
    return store.create_draft(1, {"status": status, "listing": {"title": "T"}, "sku": "SKU1"})


def test_parallele_claims_ein_gewinner(store):
    did = _draft(store)
    results = []

    def try_claim():
        results.append(claim_or_create_intent(
            store, draft_id=did, account_id=1, sku="SKU1"))

    threads = [threading.Thread(target=try_claim) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    winners = [r for r in results if r]
    assert len(winners) == 1
    assert winners[0]["state"] == "publishing"
    assert active_intent_for_draft(store, did)["id"] == winners[0]["id"]


def test_zweiter_aufrufer_verliert(store):
    did = _draft(store)
    a = claim_or_create_intent(store, draft_id=did, account_id=1, sku="SKU1")
    b = claim_or_create_intent(store, draft_id=did, account_id=1, sku="SKU1")
    assert a and b is None


def test_publish_einmal(store):
    did = _draft(store)
    ebay = FakeEbay()
    ebay.sku_offer["SKU1"] = "OFF1"
    intent = claim_or_create_intent(store, draft_id=did, account_id=1, sku="SKU1")
    out = asyncio.run(execute_publish(store, ebay, intent["id"]))
    assert out["state"] == "published"
    assert out["listing_id"]
    assert ebay.publish_calls == 1


def test_timeout_ohne_lookup_wird_uncertain(store):
    did = _draft(store)
    ebay = FakeEbay()
    ebay.sku_offer["SKU1"] = "OFF1"
    ebay.timeout_on_publish = True
    ebay.timeout_on_lookup = True
    intent = claim_or_create_intent(store, draft_id=did, account_id=1, sku="SKU1")
    # Offer schon bekannt — Timeout erst beim Publish, Lookup danach scheitert
    _set_intent(store, intent["id"], offer_id="OFF1")
    out = asyncio.run(execute_publish(store, ebay, intent["id"]))
    assert out["state"] == "publish_uncertain"
    # Kein Auto-Retry
    out2 = asyncio.run(execute_publish(store, ebay, intent["id"]))
    assert out2["state"] == "publish_uncertain"
    assert ebay.publish_calls == 1


def test_timeout_mit_listing_wird_published(store):
    did = _draft(store)
    ebay = FakeEbay()
    ebay.sku_offer["SKU1"] = "OFF1"
    ebay.sku_listing["SKU1"] = "L-EXIST"
    ebay.timeout_on_publish = True
    intent = claim_or_create_intent(store, draft_id=did, account_id=1, sku="SKU1")
    out = asyncio.run(execute_publish(store, ebay, intent["id"]))
    assert out["state"] == "published"
    assert out["listing_id"] == "L-EXIST"


def test_dry_run_kein_publish(store):
    did = _draft(store)
    ebay = FakeEbay()
    ebay.sku_offer["SKU1"] = "OFF1"
    intent = claim_or_create_intent(store, draft_id=did, account_id=1, sku="SKU1")
    out = asyncio.run(execute_publish(store, ebay, intent["id"], dry_run=True))
    assert out["state"] == "dry_run_done"
    assert ebay.publish_calls == 0


def test_telegram_upload_soll_claim_nutzen():
    """Quelltext-Wache: Telegram-Pfad nutzt Intent + gemeinsamen Publish-Kern."""
    from pathlib import Path
    quelle = (Path(__file__).parent.parent / "bot" / "main.py").read_text()
    start = quelle.index("async def run_upload")
    ende = quelle.index("async def run_update", start) if "async def run_update" in quelle[start:] else start + 8000
    block = quelle[start:ende]
    assert "claim_or_create_intent" in block
    assert "execute_publish" in block


def test_endzustaende_geschuetzt(store):
    did = _draft(store, status="published")
    assert claim_or_create_intent(store, draft_id=did, account_id=1, sku="SKU1") is None


def test_uncertain_kein_auto_retry(store):
    did = _draft(store)
    ebay = FakeEbay()
    ebay.sku_offer["SKU1"] = "OFF1"
    intent = claim_or_create_intent(store, draft_id=did, account_id=1, sku="SKU1")
    _set_intent(store, intent["id"], offer_id="OFF1")
    ebay.timeout_on_publish = True
    ebay.timeout_on_lookup = True
    out = asyncio.run(execute_publish(store, ebay, intent["id"]))
    assert out["state"] == "publish_uncertain"
    calls = ebay.publish_calls
    out2 = asyncio.run(execute_publish(store, ebay, intent["id"]))
    assert out2["state"] == "publish_uncertain"
    assert ebay.publish_calls == calls


def test_failed_retry_gleiche_absicht(store):
    did = _draft(store)
    ebay = FakeEbay()
    intent = claim_or_create_intent(store, draft_id=did, account_id=1, sku="SKU1")
    _set_intent(store, intent["id"], state="failed", sku="SKU1", last_error="no_offer")
    # failed ist kein aktiver Intent — neuer Claim braucht Draft wieder ready
    store.release_draft_claim(did, "ready")
    # Bestehende Intent-Zeile mit failed: erneuter claim_or_create erzeugt neue Absicht
    # mit gleicher SKU (Retry-Pfad).
    intent2 = claim_or_create_intent(store, draft_id=did, account_id=1, sku="SKU1")
    assert intent2 is not None
    assert intent2["sku"] == "SKU1"


def test_neustart_nach_offer_setzt_fort(store):
    """Offer schon auf Intent — Publish ohne erneutes Offer-Lookup."""
    did = _draft(store)
    ebay = FakeEbay()
    intent = claim_or_create_intent(store, draft_id=did, account_id=1, sku="SKU1")
    _set_intent(store, intent["id"], offer_id="OFF-SAVED", sku="SKU1")
    out = asyncio.run(execute_publish(store, ebay, intent["id"]))
    assert out["state"] == "published"
    assert out["listing_id"]
    assert ebay.publish_calls == 1


def test_fremder_account_kein_claim(store):
    did = store.create_draft(42, {"status": "ready", "listing": {"title": "T"}, "sku": "SKU1"})
    assert claim_or_create_intent(store, draft_id=did, account_id=99, sku="SKU1") is None
    assert claim_or_create_intent(store, draft_id=did, account_id=42, sku="SKU1") is not None


def test_app_und_telegram_gleicher_service():
    """B-Exit: beide Pfade rufen denselben Publish-Kern."""
    from pathlib import Path
    app = (Path(__file__).parent.parent / "web" / "app_api.py").read_text(encoding="utf-8")
    bot = (Path(__file__).parent.parent / "bot" / "main.py").read_text(encoding="utf-8")
    for quelle, name in ((app, "app"), (bot, "bot")):
        assert "claim_or_create_intent" in quelle, name
        assert "execute_publish" in quelle, name
        assert "LiveEbayAdapter" in quelle, name


def test_alle_geschuetzten_endzustaende(store):
    for status in ("published", "ended", "dry_run_done", "publish_uncertain"):
        did = _draft(store, status=status)
        assert claim_or_create_intent(
            store, draft_id=did, account_id=1, sku="SKU1") is None


def test_unlock_dry_run_bleibt_gesperrt_wenn_dry_run_an(store):
    did = _draft(store, status="dry_run_done")
    assert unlock_dry_run_for_live(store, did, dry_run=True) == "dry_run_locked"
    assert store.get_draft(did)["status"] == "dry_run_done"
    assert claim_or_create_intent(store, draft_id=did, account_id=1, sku="SKU1") is None


def test_unlock_dry_run_fuer_live_dann_claim_und_publish(store):
    """Nach Testlauf und ausgeschaltetem Dry-Run: freigeben → Claim → publishOffer."""
    did = store.create_draft(1, {
        "status": "dry_run_done", "listing": {"title": "T"},
        "sku": "SKU1", "offer_id": "OFF-DRY",
    })
    assert unlock_dry_run_for_live(store, did, dry_run=False) is None
    assert store.get_draft(did)["status"] == "ready"
    intent = claim_or_create_intent(store, draft_id=did, account_id=1, sku="SKU1")
    assert intent is not None
    _set_intent(store, intent["id"], sku="SKU1", offer_id="OFF-DRY")
    ebay = FakeEbay()
    ebay.sku_offer["SKU1"] = "OFF-DRY"
    out = asyncio.run(execute_publish(store, ebay, intent["id"], dry_run=False))
    assert out["state"] == "published"
    assert ebay.publish_calls == 1


def test_unlock_laesst_terminal_unveraendert(store):
    for status in ("published", "ended", "publish_uncertain"):
        did = _draft(store, status=status)
        assert unlock_dry_run_for_live(store, did, dry_run=False) == "terminal"
        assert store.get_draft(did)["status"] == status


def test_neustart_mit_sku_ohne_offer_id(store):
    """Nach Inventory/Offer-Zwischenstand: SKU bekannt, Offer per Lookup."""
    did = _draft(store)
    ebay = FakeEbay()
    ebay.sku_offer["SKU1"] = "OFF-LOOKUP"
    intent = claim_or_create_intent(store, draft_id=did, account_id=1, sku="SKU1")
    _set_intent(store, intent["id"], sku="SKU1", offer_id=None)
    out = asyncio.run(execute_publish(store, ebay, intent["id"]))
    assert out["state"] == "published"
    assert out.get("offer_id") == "OFF-LOOKUP"


def test_app_telegram_parallel_ein_gewinner(store):
    """Simuliert App+Telegram-DoppelTipp auf demselben Draft."""
    did = _draft(store)
    results = []

    def app_claim():
        results.append(("app", claim_or_create_intent(
            store, draft_id=did, account_id=1, sku="SKU1")))

    def tg_claim():
        results.append(("tg", claim_or_create_intent(
            store, draft_id=did, account_id=1, sku="SKU1")))

    threads = [threading.Thread(target=app_claim), threading.Thread(target=tg_claim)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    winners = [r for _, r in results if r]
    assert len(winners) == 1
