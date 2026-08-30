"""Taxonomy API: Kategorievorschlag + Pflicht-Aspects (mit SQLite-Cache)."""

from __future__ import annotations

import logging
from typing import Optional

from bot.config import EBAY_API
from bot.drafts import Store
from bot.ebay.auth import EbayClient

log = logging.getLogger("ebay.taxonomy")

KV_TREE_ID = "ebay_category_tree_id_EBAY_DE"


class TaxonomyError(Exception):
    pass


async def get_category_tree_id(client: EbayClient, store: Store) -> str:
    """Default-Tree für EBAY_DE — zur Laufzeit abfragen, nicht hardcoden; danach gecacht."""
    cached = store.kv_get(KV_TREE_ID)
    if cached:
        return cached
    resp = await client.request(
        "GET", f"{EBAY_API}/commerce/taxonomy/v1/get_default_category_tree_id",
        auth="app", params={"marketplace_id": "EBAY_DE"},
    )
    if resp.status_code != 200:
        raise TaxonomyError(f"getDefaultCategoryTreeId fehlgeschlagen ({resp.status_code}): {resp.text[:300]}")
    tree_id = resp.json()["categoryTreeId"]
    store.kv_set(KV_TREE_ID, tree_id)
    return tree_id


async def suggest_category(client: EbayClient, store: Store, query: str) -> Optional[dict]:
    """Beste Kategorie für einen Suchbegriff: {'categoryId': ..., 'categoryName': ...}."""
    tree_id = await get_category_tree_id(client, store)
    resp = await client.request(
        "GET", f"{EBAY_API}/commerce/taxonomy/v1/category_tree/{tree_id}/get_category_suggestions",
        auth="app", params={"q": query},
    )
    if resp.status_code != 200:
        raise TaxonomyError(f"getCategorySuggestions fehlgeschlagen ({resp.status_code}): {resp.text[:300]}")
    suggestions = resp.json().get("categorySuggestions", [])
    if not suggestions:
        return None
    cat = suggestions[0]["category"]
    return {"categoryId": cat["categoryId"], "categoryName": cat["categoryName"]}



async def suggest_categories(client: EbayClient, store: Store, query: str, limit: int = 8) -> list[dict]:
    """Mehrere Kategorievorschläge für die manuelle Korrektur im Review."""
    q = (query or "").strip()
    if len(q) < 2:
        return []
    tree_id = await get_category_tree_id(client, store)
    resp = await client.request(
        "GET", f"{EBAY_API}/commerce/taxonomy/v1/category_tree/{tree_id}/get_category_suggestions",
        auth="app", params={"q": q},
    )
    if resp.status_code != 200:
        raise TaxonomyError(f"getCategorySuggestions fehlgeschlagen ({resp.status_code}): {resp.text[:300]}")
    out = []
    for s in (resp.json().get("categorySuggestions") or [])[:limit]:
        cat = s.get("category") or {}
        cid = cat.get("categoryId")
        name = cat.get("categoryName")
        if cid and name:
            out.append({"categoryId": str(cid), "categoryName": name})
    return out


async def get_required_aspects(client: EbayClient, store: Store, category_id: str) -> list[str]:
    """Namen der Pflicht-Aspects (aspectRequired: true) einer Kategorie, gecacht pro categoryId."""
    cached = store.get_aspects(category_id)
    # nur nutzen, wenn auch der Single-Value-Cache da ist (kam später dazu)
    if cached is not None and store.get_aspects(f"{category_id}:single") is not None:
        from bot.ebay.payload import sanitize_required_aspects
        return sanitize_required_aspects(cached)
    tree_id = await get_category_tree_id(client, store)
    resp = await client.request(
        "GET", f"{EBAY_API}/commerce/taxonomy/v1/category_tree/{tree_id}/get_item_aspects_for_category",
        auth="app", params={"category_id": category_id},
    )
    if resp.status_code != 200:
        raise TaxonomyError(f"getItemAspectsForCategory fehlgeschlagen ({resp.status_code}): {resp.text[:300]}")
    aspects = resp.json().get("aspects", [])
    required = [
        a["localizedAspectName"]
        for a in aspects
        if a.get("aspectConstraint", {}).get("aspectRequired")
    ]
    from bot.ebay.payload import sanitize_required_aspects
    required = sanitize_required_aspects(required)
    # Nebenbei cachen, welche Merkmale nur EINEN Wert erlauben (Cardinality SINGLE) —
    # sonst lehnt eBay mit 25002 ab ("Verlag darf nur einen Wert enthalten").
    single = [
        a["localizedAspectName"]
        for a in aspects
        if a.get("aspectConstraint", {}).get("itemToAspectCardinality") == "SINGLE"
    ]
    store.set_aspects(category_id, required)
    store.set_aspects(f"{category_id}:single", single)
    log.debug("Pflicht-Aspects für %s: %s | Single-Value: %s", category_id, required, single)
    return required


async def get_single_value_aspects(client: EbayClient, store: Store, category_id: str) -> list[str]:
    """Merkmale, die nur EINEN Wert erlauben. Füllt den Cache notfalls über
    get_required_aspects (ein API-Call für beides)."""
    cached = store.get_aspects(f"{category_id}:single")
    if cached is not None:
        return cached
    await get_required_aspects(client, store, category_id)
    return store.get_aspects(f"{category_id}:single") or []
