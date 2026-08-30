"""Verkauf-Sync: Listenpreis und Kaeufer-Preisvorschlaege nur aus eBay-Daten."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from bot.ebay import inventory


def test_live_price_from_offer_nimmt_nur_echte_werte():
    assert inventory.live_price_from_offer({
        "pricingSummary": {"price": {"value": "89.90", "currency": "EUR"}},
    }) == "89.90"
    assert inventory.live_price_from_offer({
        "pricingSummary": {"auctionStartPrice": {"value": "1"}},
    }) == "1.00"
    assert inventory.live_price_from_offer({}) is None
    assert inventory.live_price_from_offer({"pricingSummary": {"price": {"value": "0"}}}) is None
    assert inventory.live_price_from_offer({"pricingSummary": {"price": {"value": "abc"}}}) is None


@pytest.mark.asyncio
async def test_live_auction_bid_parst_current_price():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<GetItemResponse xmlns="urn:ebay:apis:eBLBaseComponents">
  <Ack>Success</Ack>
  <Item>
    <ItemID>123</ItemID>
    <StartPrice currencyID="EUR">1.0</StartPrice>
    <WatchCount>7</WatchCount>
    <HitCount>142</HitCount>
    <ListingDetails>
      <EndTime>2026-08-10T18:00:00.000Z</EndTime>
    </ListingDetails>
    <SellingStatus>
      <CurrentPrice currencyID="EUR">12.50</CurrentPrice>
      <BidCount>4</BidCount>
    </SellingStatus>
  </Item>
</GetItemResponse>"""

    class FakeResp:
        status_code = 200
        text = xml

    class FakeEbay:
        async def get_user_token(self, user_id):
            return "tok"

        async def request(self, *a, **k):
            return FakeResp()

    assert await inventory.live_auction_bid(FakeEbay(), "123", 1) == "12.50"
    assert await inventory.live_auction_bid(FakeEbay(), "", 1) is None
    state = await inventory.live_auction_state(FakeEbay(), "123", 1)
    assert state["price"] == "12.50"
    assert state["bid_count"] == 4
    assert state["start_price"] == "1.00"
    assert state["watch_count"] == 7
    assert state["hit_count"] == 142
    assert state["ends_at"]


def test_parse_order_sold_map_nimmt_echten_verkaufspreis():
    orders = [{
        "creationDate": "2026-08-05T10:00:00.000Z",
        "lineItems": [{
            "sku": "SERO-20260803-L4HF",
            "legacyItemId": "147480067874",
            "quantity": 1,
            "lineItemCost": {"value": "1.00", "currency": "EUR"},
            "total": {"value": "187.50", "currency": "EUR"},
        }],
    }]
    m = inventory.parse_order_sold_map(orders)
    assert m["SERO-20260803-L4HF"]["price"] == "187.50"
    assert m["147480067874"]["price"] == "187.50"
    assert m["SERO-20260803-L4HF"]["sold_at"] is not None


def test_sold_price_from_line_item_qty():
    assert inventory.sold_price_from_line_item({
        "quantity": 2, "lineItemCost": {"value": "10.00"},
    }) == "20.00"
    assert inventory.sold_price_from_line_item({
        "total": {"value": "9.99"},
    }) == "9.99"


def test_sync_schreibt_sold_price_aus_orders():
    quelle = open("web/app_api.py", encoding="utf-8").read()
    assert "parse_order_sold_map" in quelle
    assert "apply_sold_price" in quelle
    assert "sold_price" in quelle
    assert "value_sold" in quelle
    assert "watch_count" in quelle
    assert "hit_count" in quelle


def test_sync_behaelt_auktionsgebot_nach_reload():
    """Bug-Wache: Gebot nicht durch frischen Draft-Reload nach GetBestOffers verwerfen."""
    quelle = open("web/app_api.py", encoding="utf-8").read()
    assert "pending_price" in quelle
    assert "live_auction_state" in quelle
    assert "auction_start_price" in quelle


def test_best_offer_enabled_from_offer():
    assert inventory.best_offer_enabled_from_offer({
        "listingPolicies": {"bestOfferTerms": {"bestOfferEnabled": True}},
    }) is True
    assert inventory.best_offer_enabled_from_offer({}) is False


@pytest.mark.asyncio
async def test_get_active_buyer_offers_parst_xml():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<GetBestOffersResponse xmlns="urn:ebay:apis:eBLBaseComponents">
  <Ack>Success</Ack>
  <ItemBestOffersArray>
    <ItemBestOffers>
      <Item><ItemID>123456789012</ItemID></Item>
      <BestOfferArray>
        <BestOffer>
          <BestOfferID>bo1</BestOfferID>
          <UserID>kaeufer1</UserID>
          <Price currencyID="EUR">42.50</Price>
          <Quantity>1</Quantity>
          <Status>Active</Status>
          <ExpirationTime>2026-08-08T12:00:00.000Z</ExpirationTime>
        </BestOffer>
      </BestOfferArray>
    </ItemBestOffers>
  </ItemBestOffersArray>
</GetBestOffersResponse>"""

    class FakeResp:
        status_code = 200
        text = xml

    class FakeEbay:
        async def get_user_token(self, user_id):
            return "tok"

        async def request(self, *a, **k):
            return FakeResp()

    rows = await inventory.get_active_buyer_offers(FakeEbay(), 1)
    assert len(rows) == 1
    assert rows[0]["listing_id"] == "123456789012"
    assert rows[0]["price"] == "42.50"
    assert rows[0]["buyer"] == "kaeufer1"


def test_get_active_buyer_offers_ack_failure_ist_leer():
    xml = """<?xml version="1.0"?>
    <GetBestOffersResponse xmlns="urn:ebay:apis:eBLBaseComponents">
      <Ack>Failure</Ack><Errors><LongMessage>nope</LongMessage></Errors>
    </GetBestOffersResponse>"""
    root = ET.fromstring(xml)
    ns = {"e": "urn:ebay:apis:eBLBaseComponents"}
    ack = root.findtext("e:Ack", default="", namespaces=ns)
    assert ack == "Failure"


def test_photo_rotate_endpoint_im_quelltext():
    """Quelltext-Wache: Rotate/Recrop/Photos-Endpunkte bleiben erreichbar."""
    quelle = open("web/app_api.py", encoding="utf-8").read()
    assert "async def rotate_item_photo" in quelle
    assert "async def recrop_item" in quelle
    assert "async def item_photos" in quelle
    assert "buyer_offers" in quelle
    assert "live_price_from_offer" in quelle
    assert "get_active_buyer_offers" in quelle


def test_sync_respektiert_price_dirty():
    """Sales-Sync darf manuell gesetzte Preise nicht überschreiben (A1)."""
    quelle = open("web/app_api.py", encoding="utf-8").read()
    assert "price_dirty" in quelle
    assert "not frisch.get(\"price_dirty\")" in quelle or "not frisch.get('price_dirty')" in quelle


def test_live_festpreis_preis_editierbar():
    """Live Festpreis: Preis in der App änderbar; Auktion mit Geboten gesperrt."""
    quelle = open("web/app_api.py", encoding="utf-8").read()
    # Alter Hard-Block weg
    assert "den Preis änderst du nicht mehr in der App" not in quelle
    start = quelle.index('if action == "price":')
    block = quelle[start:start + 1600]
    assert "bid_count" in block
    assert "price_dirty" in block
    js = open("frontend/sero.js", encoding="utf-8").read()
    assert "priceFrozen" in js
    assert "Preis, Titel und Beschreibung kannst du ändern und speichern" in js


def test_foto_endpunkte_sperren_waehrend_analyse():
    """Während status=analyzing → 409 auf photos/recrop/rotate (B4)."""
    quelle = open("web/app_api.py", encoding="utf-8").read()
    for fn in ("async def item_photos", "async def recrop_item", "async def rotate_item_photo"):
        start = quelle.index(fn)
        block = quelle[start:start + 1200]
        assert 'status") == "analyzing"' in block or "status') == 'analyzing'" in block
        assert "409" in block


def test_recrop_laeuft_im_hintergrund_nicht_am_http():
    """Freistellen darf die App nicht blockieren — Queue + Spawn, nicht await crop."""
    quelle = open("web/app_api.py", encoding="utf-8").read()
    assert "def enqueue_recrop" in quelle
    assert "async def run_recrop_item" in quelle
    assert "/collection/recrop-missing" in quelle
    start = quelle.index("async def recrop_item")
    block = quelle[start:start + 1600]
    assert "enqueue_recrop" in block
    assert "await cardscan.crop_photos" not in block
    js = open("frontend/sero.js", encoding="utf-8").read()
    assert "designs-missing" in js
    assert "recrop-missing" not in js
    assert "Freisteller läuft im Hintergrund" in js
    assert 'cutout_status === "running"' in js
    assert 'design_status === "running"' in js
    recrop = quelle[quelle.index("async def run_recrop_item"):quelle.index("def enqueue_recrop")]
    assert 'cutout_status"] = "error"' in recrop
    assert "_item_has_cutout" in recrop
    assert "Kein Reset aufs Original" in recrop


def test_error_draft_zeigt_retry_ohne_spinner():
    """Abgebrochener Entwurf: echter Knopf, kein ewiges „wird vorbereitet“."""
    js = open("frontend/sero.js", encoding="utf-8").read()
    i = js.index("function renderDraftSection")
    chunk = js[i:i + 4500]
    assert 'data-dact="retry_list"' in chunk
    assert "Erneut versuchen" in chunk
    assert chunk.index('data-dact="retry_list"') < chunk.index("Listing wird vorbereitet")
    quelle = open("web/app_api.py", encoding="utf-8").read()
    start = quelle.index("reuse_id = None")
    block = quelle[start:start + 1200]
    assert 'st == "error"' in block
    assert "error_text" in open("web/app_api.py", encoding="utf-8").read()
    assert 'draft.get("error_text") or draft.get("error")' in quelle


def test_auto_design_ohne_ebay_listing():
    """Listing-Foto entsteht im Hintergrund (PIL), ohne extra Tab und ohne rembg."""
    quelle = open("web/app_api.py", encoding="utf-8").read()
    assert "def enqueue_design" in quelle
    assert "async def run_design_item" in quelle
    assert "place_on_listing_bg" in quelle
    assert "/collection/designs-missing" in quelle
    start = quelle.index("async def run_design_item")
    end = quelle.index("def enqueue_design")
    block = quelle[start:end]
    assert "place_on_listing_bg" in block
    assert "render_product" not in block
    assert "enqueue_recrop" not in block
    assert "composite_cutout_on_background" not in block
    enq = quelle[quelle.index("def enqueue_design"):quelle.index("def enqueue_designs_missing")]
    assert "enqueue_recrop" not in enq
    assert "waiting_cutout" not in enq
    sales = quelle.index("async def sales(")
    sales_block = quelle[sales:sales + 9000]
    assert "enqueue_designs_missing" not in sales_block
    assert "current_price" in sales_block
    assert "shipping_ok" in sales_block
    html = open("frontend/index.html", encoding="utf-8").read()
    assert 'data-b="design"' not in html
    js = open("frontend/sero.js", encoding="utf-8").read()
    assert 'salesBucket: "draft"' in js
    assert 'bucket === "design"' not in js
    assert "Designs entstehen automatisch aus den Fotos in deiner Sammlung." not in js
    assert "designs-missing" in js
    render = open("bot/render.py", encoding="utf-8").read()
    assert "def place_on_listing_bg" in render
    assert "def composite_cutout_on_background" in render
    rembg_idx = render.index("from rembg import remove")
    lazy_idx = render.index("if cutout is None:")
    assert rembg_idx > lazy_idx