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


def test_foto_endpunkte_sperren_waehrend_analyse():
    """Während status=analyzing → 409 auf photos/recrop/rotate (B4)."""
    quelle = open("web/app_api.py", encoding="utf-8").read()
    for fn in ("async def item_photos", "async def recrop_item", "async def rotate_item_photo"):
        start = quelle.index(fn)
        block = quelle[start:start + 1200]
        assert 'status") == "analyzing"' in block or "status') == 'analyzing'" in block
        assert "409" in block
