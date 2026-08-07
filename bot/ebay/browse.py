"""Browse API: Preisrecherche über vergleichbare aktive Festpreis-Angebote.

Bewusste Limitierung v1: Browse API zeigt nur AKTIVE Angebote, keine
Sold-Preise. Für einen ersten Preisanker reicht das.
"""

from __future__ import annotations

import logging
import statistics
from typing import Optional

from bot.config import EBAY_API
from bot.ebay.auth import EbayClient

log = logging.getLogger("ebay.browse")


# Svens Markt-Umschalter (03.08.): dieselbe Recherche auf drei Märkten.
# „jp" ist kein eigener eBay-Marktplatz (eBay Japan schloss 2002) — es sind
# die japanischen Händler auf ebay.com, gefiltert über den Artikelstandort.
MAERKTE = {
    "eu": {"marketplace": "EBAY_DE", "currency": "EUR", "location": None},
    "us": {"marketplace": "EBAY_US", "currency": "USD", "location": None},
    "jp": {"marketplace": "EBAY_US", "currency": "USD", "location": "JP"},
}


async def research_price(client: EbayClient, query: str, limit: int = 20,
                         market: str = "eu", title_filter=None) -> Optional[dict]:
    """Median/Min/Max aktiver Festpreisangebote. None wenn keine Treffer.

    market: "eu" (eBay.de, EUR), "us" (eBay.com, USD) oder "jp" (Händler mit
    Standort Japan auf eBay.com, USD). Preise kommen in der Währung des
    Marktes zurück — die Umrechnung gehört dem Aufrufer.

    title_filter: optionales Prädikat über den Angebots-Titel. Die breite
    Suche auf ebay.com mischt sonst fremde Karten in den Median (gemessen
    03.08.: „Ace OP02-013" bekam OP07-119 und OP13-002 untergeschoben).
    """
    m = MAERKTE.get(market) or MAERKTE["eu"]
    filters = ["buyingOptions:{FIXED_PRICE}"]
    if m["location"]:
        filters.append(f"itemLocationCountry:{m['location']}")
    resp = await client.request(
        "GET", f"{EBAY_API}/buy/browse/v1/item_summary/search",
        auth="app",
        headers={"X-EBAY-C-MARKETPLACE-ID": m["marketplace"]},
        params={"q": query, "limit": str(limit), "filter": ",".join(filters)},
    )
    if resp.status_code != 200:
        log.warning("Browse-Suche fehlgeschlagen (%s): %s", resp.status_code, resp.text[:300])
        return None

    prices: list[float] = []
    samples: list[dict] = []
    for item in resp.json().get("itemSummaries", []):
        if title_filter and not title_filter(item.get("title") or ""):
            continue
        price = item.get("price", {})
        if price.get("currency") == m["currency"]:
            try:
                value = float(price["value"])
            except (KeyError, ValueError):
                continue
            prices.append(value)
            thumbs = item.get("thumbnailImages") or ([item["image"]] if item.get("image") else [])
            samples.append({
                "title": item.get("title"),
                "price": value,
                "url": item.get("itemWebUrl"),
                "image": thumbs[0].get("imageUrl") if thumbs else None,
            })

    if not prices:
        return None

    # Ausreißer kappen (IQR): einzelne Fantasie-/Sammlerpreise verzerren sonst den
    # Median (z.B. eine "seltene" 17-€-Apfelschorle zwischen normalen Angeboten).
    trimmed = sorted(prices)
    if len(trimmed) >= 5:
        q = statistics.quantiles(trimmed, n=4)
        iqr = q[2] - q[0]
        lo, hi = q[0] - 1.5 * iqr, q[2] + 1.5 * iqr
        kept = [p for p in trimmed if lo <= p <= hi]
        if len(kept) >= 3:
            trimmed = kept

    # Die 5 günstigsten (nicht weggekappten) Angebote als echte Vergleichsbeispiele
    lo_kept, hi_kept = min(trimmed), max(trimmed)
    sample_rows = sorted(
        (s for s in samples if lo_kept <= s["price"] <= hi_kept),
        key=lambda s: s["price"])[:5]

    return {
        "count": len(trimmed),
        "min": lo_kept,
        "max": hi_kept,
        "median": round(statistics.median(trimmed), 2),
        "query": query,
        "currency": m["currency"],
        "market": market,
        "samples": sample_rows,
    }
