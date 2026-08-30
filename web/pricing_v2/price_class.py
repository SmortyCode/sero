"""Anzeige-Preisklassen aus Quelle/Zustand ableiten."""
from __future__ import annotations

from typing import Any

from web.pricing_v2.types import PriceClass


def derive_price_class(item: dict[str, Any]) -> str:
    src = (item.get("price_source") or "").lower()
    state = item.get("price_state")
    reason = item.get("price_reason")
    if item.get("est_value") is None or state == "unbekannt":
        return PriceClass.NO_MARKET_DATA.value
    if src == "manual" or state == "eigener_wert":
        return PriceClass.NO_MARKET_DATA.value  # eigener Wert ist kein Marktbeleg
    if src == "ebay_sold":
        if state == "belegt":
            return PriceClass.EXACT_SOLD.value
        return PriceClass.ESTIMATED_SOLD.value
    if src.startswith("pricecharting"):
        return PriceClass.GUIDE_VALUE.value
    if src in ("cardmarket", "tcgplayer", "tcgcsv", "scryfall", "ygoprodeck", "tcgdex"):
        return PriceClass.RAW_MARKET.value
    if src in ("ebay", "ebay_eu"):
        return PriceClass.ASKING_ONLY.value
    if src == "estimate":
        return PriceClass.NO_MARKET_DATA.value
    if reason == "NUR_ANGEBOTE":
        return PriceClass.ASKING_ONLY.value
    return PriceClass.NO_MARKET_DATA.value
