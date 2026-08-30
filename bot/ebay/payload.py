"""Zentraler eBay-Payload: Bilder, Merkmale, Versand — ohne interne IDs.

Neue Festpreis-Angebote gehen ueber die Trading API (AddFixedPriceItem),
damit der Seller Hub das Listing bearbeiten kann. Die Inventory API
(publishOffer) erzeugt Angebote, die im Seller Hub nicht editierbar sind.

Interne Schluessel (SKU, Draft-ID) bleiben in der Datenbank. Sie gehoeren
nicht in Item Specifics, Custom Label oder die Beschreibung.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

# eBay.de: Gallery in der Praxis 12 Bilder (Inventory erlaubt 24, UI-Limit 12).
MAX_LISTING_PHOTOS = 12

# Aspect-Namen, unter denen eine interne SKU / Bestandseinheit landen wuerde.
_SKU_ASPECT_NORM = frozenset({
    "sku",
    "bestandeinheit",
    "bestandseinheit",
    "customlabel",
    "sellersku",
    "internesku",
    "inventorysku",
    "verkaeufersku",
    "verkaeufersku",
})

_SHIP_ASPECT_NORM = frozenset({
    "shipping",
    "versand",
    "shippingpolicy",
    "versandrichtlinie",
    "fulfillmentpolicy",
    "shippingpolicyid",
    "fulfillmentpolicyid",
    "paymentpolicyid",
    "returnpolicyid",
    "usps",
    "fedex",
    "upsground",
})

# Zehnstellige interne SKU (generate_sku) — nicht in oeffentliche Felder.
_INTERNAL_SKU_RE = re.compile(r"^[A-Z0-9]{10}$")
_SKU_LINE_RE = re.compile(
    r"(?im)^.*\b(sku|bestandeinheit|bestandseinheit|custom\s*label)\b.*$",
)
_US_SHIP_RE = re.compile(
    r"^(US_|USA_|FEDEX|UPS|USPS|PRIORITY_MAIL|FIRST_CLASS)",
    re.I,
)


def _norm_name(name: str) -> str:
    s = (name or "").strip().lower()
    s = s.replace("ae", "ae")
    s = (s.replace("\u00e4", "ae").replace("\u00f6", "oe")
         .replace("\u00fc", "ue").replace("\u00df", "ss"))
    return re.sub(r"[\s_\-./]+", "", s)


def is_internal_id_aspect(name: str) -> bool:
    return _norm_name(name) in _SKU_ASPECT_NORM


def is_shipping_id_aspect(name: str) -> bool:
    return _norm_name(name) in _SHIP_ASPECT_NORM


def looks_like_internal_sku(value: Any) -> bool:
    s = str(value or "").strip()
    return bool(_INTERNAL_SKU_RE.match(s))


def strip_internal_ids_from_aspects(aspects: dict | None) -> dict:
    """SKU / Bestandseinheit / KI-Versand-IDs aus Item Specifics entfernen."""
    out: dict = {}
    for name, values in (aspects or {}).items():
        if is_internal_id_aspect(name) or is_shipping_id_aspect(name):
            continue
        if not isinstance(values, list):
            values = [values]
        kept = []
        for v in values:
            if v is None or str(v).strip() == "":
                continue
            if looks_like_internal_sku(v) and is_internal_id_aspect(name):
                continue
            kept.append(v)
        if kept:
            out[str(name).strip()] = kept
    return out


def sanitize_required_aspects(names: list[str] | None) -> list[str]:
    return [n for n in (names or []) if n and not is_internal_id_aspect(n)
            and not is_shipping_id_aspect(n)]


def strip_sku_from_description(html: str | None) -> str:
    """Zeilen mit Bestandseinheit/SKU aus der Beschreibung streichen."""
    text = html or ""
    return _SKU_LINE_RE.sub("", text)


def listing_photos_in_order(
    photos: list | None,
    image_urls: list | None = None,
    *,
    limit: int = MAX_LISTING_PHOTOS,
) -> list:
    """Index 0 ist das Hauptfoto. Alte 1-Bild-Listen bleiben gueltig."""
    seq = list(photos or []) or list(image_urls or [])
    out = []
    for p in seq:
        if p in (None, "", False):
            continue
        out.append(p)
        if len(out) >= limit:
            break
    return out


def listing_channel(draft: dict | None) -> str:
    """trading = Seller-Hub-editierbar; inventory = altes publishOffer-Listing."""
    d = draft or {}
    api = (d.get("listing_api") or "").strip().lower()
    if api == "trading":
        return "trading"
    if api == "inventory":
        return "inventory"
    if d.get("offer_id"):
        return "inventory"
    return "trading"


def uses_inventory_api(draft: dict | None) -> bool:
    return listing_channel(draft) == "inventory"


def is_inventory_managed(draft: dict | None) -> bool:
    """Veroeffentlicht ueber Inventory API — im Seller Hub nicht bearbeitbar."""
    d = draft or {}
    if d.get("status") not in ("published", "ended"):
        return False
    return uses_inventory_api(d)


def list_inventory_managed_drafts(store) -> list[dict]:
    """Readonly: welche Live-Listings ueber Inventory/publishOffer laufen."""
    rows = store._conn.execute(  # noqa: SLF001
        "SELECT id, data FROM drafts"
    ).fetchall()
    out = []
    for r in rows:
        try:
            d = json.loads(r["data"])
        except (TypeError, json.JSONDecodeError):
            continue
        d["id"] = r["id"]
        if not is_inventory_managed(d):
            continue
        listing = d.get("listing") or {}
        out.append({
            "draft_id": r["id"],
            "listing_id": d.get("listing_id") or d.get("item_id"),
            "offer_id": d.get("offer_id"),
            "sku": d.get("sku"),
            "status": d.get("status"),
            "title": listing.get("title"),
            "item_url": d.get("item_url"),
        })
    return out


def policies_for_listing(policies: dict | None, draft: dict | None) -> dict:
    """Konto-Richtlinien, optional Entwurf-Override. Keine KI-IDs."""
    base = dict(policies or {})
    d = draft or {}
    for key in ("fulfillment_policy_id", "payment_policy_id", "return_policy_id",
                "merchant_location_key"):
        override = d.get(key)
        if override:
            base[key] = override
    return base


def reject_us_shipping_code(code: str | None) -> bool:
    """US-Dienste gehoeren nicht auf EBAY_DE."""
    return bool(code and _US_SHIP_RE.match(str(code).strip()))


def ebay_snapshot_from_getitem(live: dict | None) -> dict:
    live = live or {}
    return {
        "title": (live.get("title") or "").strip(),
        "price": str(live.get("price") or "").strip(),
        "quantity": int(live.get("quantity") or 0),
        "picture_count": len(live.get("pictures") or []),
    }


def conflict_if_ebay_changed(
    *,
    snapshot: dict | None,
    live: dict | None,
    local_title: str | None,
    local_price: str | None,
) -> Optional[dict]:
    """eBay ist Quelle der Wahrheit. Konflikt, wenn Live != letzter Sync
    und Live != das, was die App gerade senden will."""
    if not live:
        return None
    snap = snapshot or {}
    live_title = (live.get("title") or "").strip()
    live_price = str(live.get("price") or "").strip()
    want_title = (local_title or "").strip()
    want_price = str(local_price or "").strip()
    snap_title = (snap.get("title") or "").strip()
    snap_price = str(snap.get("price") or "").strip()
    if not snap_title and not snap_price:
        return None
    ebay_moved = (snap_title and live_title and live_title != snap_title) or (
        snap_price and live_price and live_price != snap_price
    )
    if not ebay_moved:
        return None
    if live_title == want_title and live_price == want_price:
        return None
    return {
        "code": "ebay_conflict",
        "message": "Das Listing hat sich bei eBay geaendert. eBay gilt.",
        "ebay": {"title": live_title, "price": live_price},
        "app": {"title": want_title, "price": want_price},
    }


def review_fields(draft: dict, *, photo_count: int, policies: dict | None) -> dict:
    """Kompakte Review-Ansicht vor dem Publish — fehlende Stellen markieren."""
    listing = (draft or {}).get("listing") or {}
    pol = policies or {}
    photos_ok = photo_count >= 1
    title = (listing.get("title") or draft.get("title") or "").strip()
    title_ok = 1 <= len(title) <= 80
    ship_ok = bool(
        pol.get("fulfillment_policy_id") or pol.get("shipping_policy_id")
        or pol.get("fulfillment") or pol.get("shipping")
    )
    price = draft.get("price")
    try:
        price_ok = float(str(price or "").replace(",", ".")) > 0
    except (TypeError, ValueError):
        price_ok = False
    return {
        "photos_ok": photos_ok,
        "photo_count": photo_count,
        "photo_max": MAX_LISTING_PHOTOS,
        "title_ok": title_ok,
        "title": title,
        "price_ok": price_ok,
        "shipping_ok": ship_ok,
        "listing_api": listing_channel(draft),
        "inventory_managed": is_inventory_managed(draft),
    }


def fulfillment_policy_view(raw: dict | None) -> dict:
    """Anzeige-Felder aus einer eBay-Fulfillment-Policy (kein Payload)."""
    p = raw or {}
    handling = p.get("handlingTime") or {}
    hval = handling.get("value")
    hunit = str(handling.get("unit") or "DAY").upper()
    handling_label = None
    if hval is not None and str(hval).strip() != "":
        try:
            n = int(hval)
        except (TypeError, ValueError):
            n = None
        if n is not None and hunit.startswith("DAY"):
            handling_label = f"{n} Werktag" if n == 1 else f"{n} Werktage"
        elif n is not None:
            handling_label = f"{n} {hunit.lower()}"
        else:
            handling_label = str(hval)
    cost_label = None
    service_label = None
    international = False
    pickup = bool(p.get("localPickup") or p.get("pickupDropOff"))
    for opt in p.get("shippingOptions") or []:
        otype = str(opt.get("optionType") or "").upper()
        if otype == "INTERNATIONAL":
            international = True
            continue
        for s0 in opt.get("shippingServices") or []:
            code = s0.get("shippingServiceCode") or s0.get("shippingCarrierCode") or ""
            if reject_us_shipping_code(code):
                continue
            if not service_label:
                service_label = code or None
            if s0.get("freeShipping"):
                cost_label = "Kostenlos"
            elif cost_label is None:
                money = s0.get("shippingCost") or {}
                val = money.get("value")
                if val is not None and str(val).strip() != "":
                    cost_label = f"{val} {money.get('currency') or 'EUR'}"
            if service_label and cost_label:
                break
    return {
        "id": p.get("fulfillmentPolicyId") or p.get("id"),
        "name": p.get("name") or "",
        "handling": handling_label,
        "cost": cost_label,
        "service": service_label,
        "international": international,
        "pickup": pickup,
        "marketplaceId": p.get("marketplaceId") or "EBAY_DE",
        "returns": None,
    }
