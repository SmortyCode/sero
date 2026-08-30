"""Trading API: AddFixedPriceItem / AddItem — Seller-Hub-editierbare Listings.

Inventory-API-Listings (publishOffer) sind im Seller Hub nicht bearbeitbar.
Offizielle eBay-Doku (Sell Inventory): Listings created with the Inventory
API cannot be revised in Seller Hub / traditional selling tools.

OAuth: bestehender User-Token (sell.inventory) als IAF-Token, Site-ID 77
(EBAY_DE). Kein CustomLabel/SKU im XML. Versand nur ueber SellerProfiles
(Business Policies), nie Legacy-ShippingDetails daneben.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Optional
from xml.sax.saxutils import escape

from bot.config import EBAY_API
from bot.ebay.auth import EbayClient, EbayTimeout
from bot.ebay.inventory import InventoryError, kurz_titel, norm_price, translate_ebay_error
from bot.ebay.metadata import ENUM_TO_CONDITION_ID
from bot.ebay.payload import (
    MAX_LISTING_PHOTOS,
    listing_photos_in_order,
    strip_internal_ids_from_aspects,
    strip_sku_from_description,
)

log = logging.getLogger("ebay.trading")

TRADING_URL = "https://api.ebay.com/ws/api.dll"
SITE_ID_DE = "77"
COMPAT_LEVEL = "1155"
NS = {"e": "urn:ebay:apis:eBLBaseComponents"}

AUCTION_DURATION_XML = {1: "Days_1", 3: "Days_3", 5: "Days_5", 7: "Days_7", 10: "Days_10"}


class TradingError(InventoryError):
    pass


def _xml_headers(call: str, token: str) -> dict:
    return {
        "X-EBAY-API-COMPATIBILITY-LEVEL": COMPAT_LEVEL,
        "X-EBAY-API-CALL-NAME": call,
        "X-EBAY-API-SITEID": SITE_ID_DE,
        "X-EBAY-API-IAF-TOKEN": token,
        "Content-Type": "text/xml; charset=utf-8",
    }


def _cdata(text: str) -> str:
    safe = (text or "").replace("]]>", "]]]]><![CDATA[>")
    return f"<![CDATA[{safe}]]>"


def _condition_id(condition: str | None) -> str:
    enum = (condition or "USED_VERY_GOOD").strip()
    return ENUM_TO_CONDITION_ID.get(enum, "4000")


async def resolve_item_location(
    client: EbayClient,
    user_id: int,
    policies: dict,
) -> tuple[str, str, Optional[str]]:
    """Echten Item-Standort aus der beim Setup angelegten Inventory-Location lesen."""
    location_key = str((policies or {}).get("merchant_location_key") or "").strip()
    if not location_key:
        raise TradingError(
            "Dein eBay-Versandstandort fehlt. Bitte richte eBay in SERO erneut ein."
        )
    resp = await client.request(
        "GET",
        f"{EBAY_API}/sell/inventory/v1/location/{location_key}",
        auth="user",
        user_id=user_id,
    )
    if resp.status_code != 200:
        raise TradingError(
            "Dein eBay-Versandstandort konnte nicht geladen werden. "
            "Bitte richte eBay in SERO erneut ein."
        )
    try:
        data = resp.json()
    except (TypeError, ValueError):
        data = {}
    address = ((data or {}).get("location") or {}).get("address") or {}
    location = str(address.get("city") or "").strip()
    country = str(address.get("country") or "DE").strip().upper()
    postal_code = str(address.get("postalCode") or "").strip() or None
    if not location:
        raise TradingError(
            "In deinem eBay-Versandstandort fehlt die Stadt. "
            "Bitte richte eBay in SERO erneut ein."
        )
    if not country:
        raise TradingError(
            "In deinem eBay-Versandstandort fehlt das Land. "
            "Bitte richte eBay in SERO erneut ein."
        )
    return location, country, postal_code


def build_add_item_xml(
    *,
    title: str,
    description_html: str,
    category_id: str,
    price_eur: str,
    condition: str,
    aspects: dict,
    image_urls: list[str],
    policies: dict,
    listing_format: str = "FIXED_PRICE",
    quantity: int = 1,
    best_offer: Optional[dict] = None,
    auction_days: int = 7,
    location: str,
    country: str = "DE",
    postal_code: Optional[str] = None,
    include_sku: bool = False,
    sku: Optional[str] = None,
) -> str:
    """XML fuer AddFixedPriceItem (Festpreis) oder AddItem (Auktion).

    include_sku bleibt False — interne IDs nicht an eBay. Parameter nur fuer Tests.
    Keine ShippingDetails neben SellerProfiles.
    """
    if not category_id:
        raise TradingError("Keine eBay-Kategorie bestimmt — bitte das Listing neu erstellen.")
    fehlend = [k for k in ("fulfillment_policy_id", "payment_policy_id", "return_policy_id")
               if not (policies or {}).get(k)]
    if fehlend:
        raise TradingError("Dein eBay-Setup ist unvollstaendig (Versand-/Zahlungs-/"
                           "Ruecknahmerichtlinie fehlt) — bitte einmal neu einrichten.")
    if not image_urls:
        raise TradingError("eBay verlangt mindestens ein Foto — bitte ein Bild hinzufuegen.")
    item_location = str(location or "").strip()
    item_country = str(country or "").strip().upper()
    if not item_location:
        raise TradingError(
            "Dein eBay-Versandstandort hat keine Stadt. "
            "Bitte richte eBay in SERO erneut ein."
        )
    if not item_country:
        raise TradingError(
            "Dein eBay-Versandstandort hat kein Land. "
            "Bitte richte eBay in SERO erneut ein."
        )
    price = norm_price(price_eur)
    pics = listing_photos_in_order(image_urls)[:MAX_LISTING_PHOTOS]
    clean_aspects = strip_internal_ids_from_aspects(aspects)
    desc = strip_sku_from_description(description_html or "")
    fmt = (listing_format or "FIXED_PRICE").upper()
    is_auction = fmt == "AUCTION"
    call = "AddItem" if is_auction else "AddFixedPriceItem"
    req = "AddItemRequest" if is_auction else "AddFixedPriceItemRequest"
    duration = AUCTION_DURATION_XML.get(int(auction_days or 7), "Days_7") if is_auction else "GTC"
    qty = 1 if is_auction else max(1, int(quantity or 1))
    listing_type = "Chinese" if is_auction else "FixedPriceItem"

    specifics = []
    for name, values in clean_aspects.items():
        vals = values if isinstance(values, list) else [values]
        inner = "".join(f"<Value>{escape(str(v)[:65])}</Value>" for v in vals if str(v).strip())
        if inner:
            specifics.append(
                f"<NameValueList><Name>{escape(str(name)[:65])}</Name>{inner}</NameValueList>"
            )
    specifics_xml = (
        f"<ItemSpecifics>{''.join(specifics)}</ItemSpecifics>" if specifics else ""
    )
    pics_xml = "".join(f"<PictureURL>{escape(u)}</PictureURL>" for u in pics)
    postal_xml = f"<PostalCode>{escape(str(postal_code))}</PostalCode>" if postal_code else ""
    sku_xml = ""
    if include_sku and sku:
        sku_xml = f"<SKU>{escape(str(sku))}</SKU>"

    bo_xml = ""
    if not is_auction and best_offer and best_offer.get("enabled"):
        bo_xml = "<BestOfferDetails><BestOfferEnabled>true</BestOfferEnabled></BestOfferDetails>"
        mp = best_offer.get("min_price")
        if mp:
            mp_s = norm_price(mp, "Mindestpreis")
            if float(mp_s) >= float(price):
                raise TradingError(
                    f"Der Mindestpreis ({mp_s} EUR) muss unter dem Angebotspreis ({price} EUR) liegen."
                )
            bo_xml += f"<ListingDetails><MinimumBestOfferPrice currencyID=\"EUR\">{mp_s}</MinimumBestOfferPrice></ListingDetails>"

    profiles = (
        "<SellerProfiles>"
        f"<SellerShippingProfile><ShippingProfileID>{escape(str(policies['fulfillment_policy_id']))}</ShippingProfileID></SellerShippingProfile>"
        f"<SellerPaymentProfile><PaymentProfileID>{escape(str(policies['payment_policy_id']))}</PaymentProfileID></SellerPaymentProfile>"
        f"<SellerReturnProfile><ReturnProfileID>{escape(str(policies['return_policy_id']))}</ReturnProfileID></SellerReturnProfile>"
        "</SellerProfiles>"
    )

    item = (
        "<Item>"
        f"<Title>{escape(kurz_titel(title))}</Title>"
        f"<Description>{_cdata(desc)}</Description>"
        f"<PrimaryCategory><CategoryID>{escape(str(category_id))}</CategoryID></PrimaryCategory>"
        f"<StartPrice currencyID=\"EUR\">{price}</StartPrice>"
        f"<ConditionID>{_condition_id(condition)}</ConditionID>"
        f"<Country>{escape(item_country)}</Country>"
        f"<Location>{escape(item_location)}</Location>"
        "<Currency>EUR</Currency>"
        "<Site>Germany</Site>"
        f"<ListingDuration>{duration}</ListingDuration>"
        f"<ListingType>{listing_type}</ListingType>"
        f"<Quantity>{qty}</Quantity>"
        f"<PictureDetails>{pics_xml}</PictureDetails>"
        f"{specifics_xml}"
        f"{profiles}"
        f"{postal_xml}"
        f"{sku_xml}"
        f"{bo_xml}"
        "</Item>"
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<{req} xmlns="urn:ebay:apis:eBLBaseComponents">'
        "<ErrorLanguage>de_DE</ErrorLanguage>"
        "<WarningLevel>High</WarningLevel>"
        f"{item}"
        f"</{req}>"
    ), call


def build_revise_xml(
    *,
    listing_id: str,
    title: str | None = None,
    description_html: str | None = None,
    price_eur: str | None = None,
    image_urls: list[str] | None = None,
    aspects: dict | None = None,
    quantity: int | None = None,
    listing_format: str = "FIXED_PRICE",
    location: str,
    country: str = "DE",
    postal_code: str | None = None,
) -> tuple[str, str]:
    item_location = str(location or "").strip()
    item_country = str(country or "").strip().upper()
    if not item_location:
        raise TradingError(
            "Dein eBay-Versandstandort hat keine Stadt. "
            "Bitte richte eBay in SERO erneut ein."
        )
    if not item_country:
        raise TradingError(
            "Dein eBay-Versandstandort hat kein Land. "
            "Bitte richte eBay in SERO erneut ein."
        )
    is_auction = (listing_format or "").upper() == "AUCTION"
    call = "ReviseItem" if is_auction else "ReviseFixedPriceItem"
    req = "ReviseItemRequest" if is_auction else "ReviseFixedPriceItemRequest"
    parts = [
        f"<ItemID>{escape(str(listing_id))}</ItemID>",
        f"<Country>{escape(item_country)}</Country>",
        f"<Location>{escape(item_location)}</Location>",
    ]
    if postal_code:
        parts.append(f"<PostalCode>{escape(str(postal_code).strip())}</PostalCode>")
    if title:
        parts.append(f"<Title>{escape(kurz_titel(title))}</Title>")
    if description_html is not None:
        parts.append(f"<Description>{_cdata(strip_sku_from_description(description_html))}</Description>")
    if price_eur:
        parts.append(f"<StartPrice currencyID=\"EUR\">{norm_price(price_eur)}</StartPrice>")
    if quantity is not None and not is_auction:
        parts.append(f"<Quantity>{max(1, int(quantity))}</Quantity>")
    if image_urls:
        pics = listing_photos_in_order(image_urls)[:MAX_LISTING_PHOTOS]
        pics_xml = "".join(f"<PictureURL>{escape(u)}</PictureURL>" for u in pics)
        parts.append(f"<PictureDetails>{pics_xml}</PictureDetails>")
    if aspects is not None:
        clean = strip_internal_ids_from_aspects(aspects)
        specifics = []
        for name, values in clean.items():
            vals = values if isinstance(values, list) else [values]
            inner = "".join(f"<Value>{escape(str(v)[:65])}</Value>" for v in vals if str(v).strip())
            if inner:
                specifics.append(
                    f"<NameValueList><Name>{escape(str(name)[:65])}</Name>{inner}</NameValueList>"
                )
        if specifics:
            parts.append(f"<ItemSpecifics>{''.join(specifics)}</ItemSpecifics>")
    xml = (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<{req} xmlns="urn:ebay:apis:eBLBaseComponents">'
        "<ErrorLanguage>de_DE</ErrorLanguage>"
        f"<Item>{''.join(parts)}</Item>"
        f"</{req}>"
    )
    return xml, call


def build_end_xml(listing_id: str, reason: str = "NotAvailable") -> tuple[str, str]:
    xml = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<EndItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">'
        f"<ItemID>{escape(str(listing_id))}</ItemID>"
        f"<EndingReason>{escape(reason)}</EndingReason>"
        "</EndItemRequest>"
    )
    return xml, "EndItem"


def _parse_ack(resp_text: str) -> tuple[str, Optional[str], str]:
    try:
        root = ET.fromstring(resp_text)
    except ET.ParseError:
        return "failure", None, resp_text[:400]
    ack = (root.findtext("e:Ack", default="", namespaces=NS) or "").lower()
    item_id = (
        root.findtext("e:ItemID", default="", namespaces=NS)
        or root.findtext(".//e:ItemID", default="", namespaces=NS)
        or None
    )
    errs = []
    for err in root.findall(".//e:Errors", NS):
        code = err.findtext("e:ErrorCode", default="", namespaces=NS)
        short = err.findtext("e:ShortMessage", default="", namespaces=NS)
        longm = err.findtext("e:LongMessage", default="", namespaces=NS)
        errs.append(f"{code}: {longm or short}".strip(": "))
    return ack, item_id, "\n".join(errs) or resp_text[:400]


def parse_getitem(resp_text: str) -> Optional[dict]:
    try:
        root = ET.fromstring(resp_text)
    except ET.ParseError:
        return None
    ack = (root.findtext("e:Ack", default="", namespaces=NS) or "").lower()
    if ack not in ("success", "warning"):
        return None
    item = root.find("e:Item", NS)
    if item is None:
        item = root.find(".//e:Item", NS)
    if item is None:
        return None

    def t(path: str) -> str:
        return (item.findtext(path, default="", namespaces=NS) or "").strip()

    pics = [el.text for el in item.findall(".//e:PictureURL", NS) if el is not None and el.text]
    price = t("e:SellingStatus/e:CurrentPrice") or t("e:StartPrice")
    qty = t("e:Quantity")
    try:
        qty_i = int(float(qty)) if qty else 0
    except ValueError:
        qty_i = 0
    return {
        "listing_id": t("e:ItemID"),
        "title": t("e:Title"),
        "price": price,
        "quantity": qty_i,
        "pictures": pics,
        "sku": t("e:SKU"),
        "listing_type": t("e:ListingType"),
    }


async def trading_call(client: EbayClient, user_id: int, call: str, body: str):
    token = await client.get_user_token(user_id)
    try:
        resp = await client.request(
            "POST", TRADING_URL,
            auth="user", user_id=user_id,
            headers=_xml_headers(call, token),
            content=body.encode("utf-8") if isinstance(body, str) else body,
            retry=False,
        )
    except EbayTimeout as e:
        raise TimeoutError(str(e)) from e
    return resp


async def add_listing(client: EbayClient, user_id: int, xml_and_call: tuple[str, str]) -> str:
    xml, call = xml_and_call
    if "<UUID" in xml:
        raise TradingError("UUID darf nicht im eBay-Trading-Payload stehen.")
    if "<Location>" not in xml or "<Location></Location>" in xml:
        raise TradingError("Dein eBay-Versandstandort hat keine Stadt.")
    if "<SKU>" in xml or "<CustomLabel>" in xml:
        raise TradingError("Interne Bestandseinheit darf nicht im eBay-Payload stehen.")
    if "<ShippingDetails>" in xml:
        raise TradingError("Legacy-Versandfelder und Business Policies duerfen nicht zusammenstehen.")
    resp = await trading_call(client, user_id, call, xml)
    ack, item_id, err = _parse_ack(resp.text)
    if ack in ("success", "warning") and item_id:
        log.info("Trading %s Listing %s", call, item_id)
        return item_id
    raise TradingError(err or translate_ebay_error(resp.text, resp.status_code), raw=resp.text)


async def revise_listing(client: EbayClient, user_id: int, xml_and_call: tuple[str, str]) -> str:
    xml, call = xml_and_call
    if "<UUID" in xml:
        raise TradingError("UUID darf nicht im eBay-Trading-Payload stehen.")
    if "<Location>" not in xml or "<Location></Location>" in xml:
        raise TradingError("Dein eBay-Versandstandort hat keine Stadt.")
    if "<SKU>" in xml or "<CustomLabel>" in xml:
        raise TradingError("Interne Bestandseinheit darf nicht im eBay-Payload stehen.")
    resp = await trading_call(client, user_id, call, xml)
    ack, item_id, err = _parse_ack(resp.text)
    if ack in ("success", "warning"):
        return item_id or ""
    raise TradingError(err or translate_ebay_error(resp.text, resp.status_code), raw=resp.text)


async def end_listing(client: EbayClient, user_id: int, listing_id: str) -> None:
    xml, call = build_end_xml(listing_id)
    resp = await trading_call(client, user_id, call, xml)
    ack, _, err = _parse_ack(resp.text)
    if ack not in ("success", "warning"):
        raise TradingError(err or "Listing konnte nicht beendet werden.", raw=resp.text)


async def get_item(client: EbayClient, user_id: int, listing_id: str) -> Optional[dict]:
    if not listing_id:
        return None
    body = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<GetItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">'
        "<DetailLevel>ReturnAll</DetailLevel>"
        f"<ItemID>{escape(str(listing_id))}</ItemID>"
        "<IncludeItemSpecifics>true</IncludeItemSpecifics>"
        "</GetItemRequest>"
    )
    try:
        resp = await trading_call(client, user_id, "GetItem", body)
    except TimeoutError:
        return None
    if resp.status_code != 200:
        return None
    return parse_getitem(resp.text)
