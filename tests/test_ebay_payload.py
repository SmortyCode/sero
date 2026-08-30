"""Payload: keine Bestandseinheit, Versand-Policies, Foto-Reihenfolge, Trading-Pfad."""
from __future__ import annotations

import asyncio
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from bot.ebay.payload import (
    MAX_LISTING_PHOTOS,
    conflict_if_ebay_changed,
    is_inventory_managed,
    listing_channel,
    listing_photos_in_order,
    reject_us_shipping_code,
    strip_internal_ids_from_aspects,
    strip_sku_from_description,
)
from bot.ebay.trading import TradingError, build_add_item_xml, build_revise_xml
from web.photos import identify_paths, normalize_photo_records
from web.publish import FakeEbay, claim_or_create_intent, execute_publish


POLICIES = {
    "merchant_location_key": "loc",
    "fulfillment_policy_id": "F1",
    "payment_policy_id": "P1",
    "return_policy_id": "R1",
}


def test_max_listing_photos_is_twelve():
    assert MAX_LISTING_PHOTOS == 12


def test_sku_und_bestandeinheit_nicht_in_aspects():
    raw = {
        "Marke": ["Pokemon"],
        "SKU": ["ABCDE12345"],
        "Bestandseinheit": ["XYZXYZXYZZ"],
        "Custom Label": ["SERO-1"],
        "Versandrichtlinie": ["12345"],
        "Set": ["Base"],
    }
    clean = strip_internal_ids_from_aspects(raw)
    blob = str(clean).lower()
    assert "sku" not in blob
    assert "bestandeinheit" not in blob and "bestandseinheit" not in blob
    assert "custom" not in blob
    assert "versand" not in blob
    assert clean["Marke"] == ["Pokemon"]
    assert clean["Set"] == ["Base"]


def test_beschreibung_ohne_sku_zeile():
    html = "<p>Tolle Karte</p>\n<p>SKU: ABCDE12345</p>\n<p>Bestandseinheit intern</p>"
    out = strip_sku_from_description(html)
    assert "SKU" not in out
    assert "Bestandseinheit" not in out
    assert "Tolle Karte" in out


def test_foto_reihenfolge_index_null_ist_hauptfoto():
    urls = ["a.jpg", "b.jpg", "c.jpg"]
    assert listing_photos_in_order(urls)[0] == "a.jpg"
    recs = normalize_photo_records(["z.jpg", "y.jpg"])
    assert recs[0]["isPrimary"] is True
    assert recs[0]["original"] == "z.jpg"
    assert identify_paths(["hero.jpg", "back.jpg"]) == ["hero.jpg"]


def test_alte_ein_bild_entwuerfe_normalisieren():
    recs = normalize_photo_records("solo.jpg")
    assert len(recs) == 1 and recs[0]["isPrimary"]
    recs2 = normalize_photo_records({"image": "x.jpg", "images": ["x.jpg", "y.jpg"]})
    assert recs2[0]["original"] == "x.jpg"
    assert len(recs2) == 2


def test_us_versand_auf_ebay_de_abgelehnt():
    assert reject_us_shipping_code("USPS")
    assert reject_us_shipping_code("US_Priority")
    assert not reject_us_shipping_code("DE_DHLPaket")


def test_add_fixed_price_xml_ohne_sku_und_ohne_legacy_versand():
    xml, call = build_add_item_xml(
        title="Karte XY",
        description_html="<p>SKU: ABCDE12345</p><p>Hallo</p>",
        category_id="183454",
        price_eur="9.90",
        condition="USED_VERY_GOOD",
        aspects={"Marke": ["Pokemon"], "SKU": ["ABCDE12345"]},
        image_urls=["https://i.ebayimg.com/a.jpg", "https://i.ebayimg.com/b.jpg"],
        policies=POLICIES,
        location="München",
        postal_code="80331",
    )
    assert call == "AddFixedPriceItem"
    assert "<SKU>" not in xml
    assert "CustomLabel" not in xml
    assert "ABCDE12345" not in xml
    assert "<ShippingDetails>" not in xml
    assert "<SellerShippingProfile>" in xml
    assert "<ShippingProfileID>F1</ShippingProfileID>" in xml
    assert "<UUID" not in xml
    assert "<Location>München</Location>" in xml
    assert "<Country>DE</Country>" in xml
    assert xml.index("https://i.ebayimg.com/a.jpg") < xml.index("https://i.ebayimg.com/b.jpg")
    assert "FixedPriceItem" in xml
    assert "EBAY_DE" not in xml or "Germany" in xml


def test_auktion_nutzt_add_item():
    xml, call = build_add_item_xml(
        title="Auktion",
        description_html="x",
        category_id="1",
        price_eur="1.00",
        condition="USED_VERY_GOOD",
        aspects={},
        image_urls=["https://i.ebayimg.com/a.jpg"],
        policies=POLICIES,
        listing_format="AUCTION",
        auction_days=7,
        location="München",
    )
    assert call == "AddItem"
    assert "Chinese" in xml
    assert "<UUID" not in xml
    assert "<Location>München</Location>" in xml


def test_trading_xml_lehnt_leeren_standort_vor_ebay_ab():
    import pytest

    with pytest.raises(TradingError, match="Versandstandort.*Stadt"):
        build_add_item_xml(
            title="Karte", description_html="x", category_id="1", price_eur="1.00",
            condition="USED_VERY_GOOD", aspects={},
            image_urls=["https://i.ebayimg.com/a.jpg"], policies=POLICIES,
            location="  ",
        )


def test_revise_xml_ohne_uuid_mit_standort():
    xml, call = build_revise_xml(
        listing_id="123", title="Karte", location="München",
        country="DE", postal_code="80331",
    )
    assert call == "ReviseFixedPriceItem"
    assert "<UUID" not in xml
    assert "<Location>München</Location>" in xml
    assert "<Country>DE</Country>" in xml


def test_inventory_managed_nur_alte_offers():
    assert listing_channel({"offer_id": "O1"}) == "inventory"
    assert listing_channel({"listing_api": "trading"}) == "trading"
    assert listing_channel({}) == "trading"
    assert is_inventory_managed({"status": "published", "offer_id": "O1"})
    assert not is_inventory_managed({"status": "published", "listing_api": "trading"})


def test_ebay_konflikt_wenn_live_sich_aenderte():
    c = conflict_if_ebay_changed(
        snapshot={"title": "Alt", "price": "10.00"},
        live={"title": "Bei eBay geaendert", "price": "12.00"},
        local_title="Mein neuer Titel",
        local_price="11.00",
    )
    assert c and c["code"] == "ebay_conflict"
    assert conflict_if_ebay_changed(
        snapshot={"title": "Alt", "price": "10.00"},
        live={"title": "Alt", "price": "10.00"},
        local_title="Neu",
        local_price="11.00",
    ) is None


def test_execute_publish_trading_pfad_gemockt(tmp_path):
    from bot.drafts import Store
    store = Store(tmp_path / "pub.db")
    did = store.create_draft(1, {"status": "ready", "listing": {"title": "T"}, "sku": "SKU1"})
    ebay = FakeEbay()
    intent = claim_or_create_intent(store, draft_id=did, account_id=1, sku="SKU1")
    xml, call = build_add_item_xml(
        title="T", description_html="d", category_id="1", price_eur="2.00",
        condition="USED_VERY_GOOD", aspects={"SKU": ["NOPE"]},
        image_urls=["https://i.ebayimg.com/x.jpg"], policies=POLICIES,
        location="München",
    )
    assert "<SKU>" not in xml
    out = asyncio.run(execute_publish(
        store, ebay, intent["id"],
        trading_payload={"xml_and_call": (xml, call), "channel": "trading"}))
    assert out["state"] == "published"
    assert str(out["listing_id"]).startswith("T-")
    assert ebay.last_trading_payload["xml_and_call"][1] == "AddFixedPriceItem"


def test_frontend_und_api_wachen():
    js = (ROOT / "frontend" / "sero.js").read_text(encoding="utf-8")
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    api = (ROOT / "web" / "app_api.py").read_text(encoding="utf-8")
    pub = (ROOT / "web" / "publish.py").read_text(encoding="utf-8")
    tg = (ROOT / "bot" / "main.py").read_text(encoding="utf-8")
    assert "MAX_LISTING_PHOTOS" in js
    assert "libraryInput" in html
    assert "function openCamCapture" in js
    assert "function addCamFiles" in js
    assert "getUserMedia" in js
    assert 'id="camOverlay"' in html
    assert "prepareScanFile" in js
    assert "revokeObjectURL" in js
    assert 'L("Hauptfoto")' in js
    assert "data-mv" in js
    assert "ondrop" not in js
    assert "trading_payload" in pub
    assert "AddFixedPriceItem" in (ROOT / "bot" / "ebay" / "trading.py").read_text(encoding="utf-8")
    assert "build_add_item_xml" in api
    sales = api[api.index("async def sales("):api.index("async def sales(") + 9000]
    assert "enqueue_designs_missing" not in sales
    upload = api[api.index("async def app_run_upload"):api.index("async def app_run_update")]
    assert "build_add_item_xml" in upload
    assert "trading_payload" in upload
    assert "create_inventory_item" in upload  # nur Legacy-Inventory
    assert "legacy =" in upload
    tg_up = tg[tg.index("async def run_upload"):tg.index("async def run_update")]
    assert "build_add_item_xml" in tg_up
    assert "trading_payload" in tg_up
    assert "analyzer.analyze(_orig_photos[:1]" in api
    assert 'id="camFlip"' in html
    assert 'id="camFlash"' in html
    assert "_camIndex" in js
    assert "function flipLiveCam" in js
    assert "function applyCamTorch" in js
    assert "fulfillment_policy_view" in (ROOT / "bot" / "ebay" / "payload.py").read_text(encoding="utf-8")


def test_fulfillment_policy_view_kosten_und_handling():
    from bot.ebay.payload import fulfillment_policy_view
    view = fulfillment_policy_view({
        "fulfillmentPolicyId": "F1",
        "name": "DHL Paket",
        "marketplaceId": "EBAY_DE",
        "handlingTime": {"value": 2, "unit": "DAY"},
        "localPickup": False,
        "shippingOptions": [
            {
                "optionType": "DOMESTIC",
                "shippingServices": [{
                    "shippingServiceCode": "DE_DHLPaket",
                    "freeShipping": False,
                    "shippingCost": {"value": "5.49", "currency": "EUR"},
                }],
            },
            {"optionType": "INTERNATIONAL", "shippingServices": []},
        ],
    })
    assert view["name"] == "DHL Paket"
    assert view["handling"] == "2 Werktage"
    assert view["cost"] == "5.49 EUR"
    assert view["service"] == "DE_DHLPaket"
    assert view["international"] is True
    us = fulfillment_policy_view({
        "name": "US",
        "shippingOptions": [{
            "optionType": "DOMESTIC",
            "shippingServices": [{"shippingServiceCode": "USPS", "freeShipping": True}],
        }],
    })
    assert us["service"] is None
    free = fulfillment_policy_view({
        "name": "Frei",
        "handlingTime": {"value": 1, "unit": "DAY"},
        "shippingOptions": [{
            "optionType": "DOMESTIC",
            "shippingServices": [{"shippingServiceCode": "DE_DHLPaket", "freeShipping": True}],
        }],
    })
    assert free["cost"] == "Kostenlos"
    assert free["handling"] == "1 Werktag"
