"""Profil-Kennzahlen — zentrale Semantik für App und Tests.

Aktiv auf eBay: Drafts mit status == published.
In Sammlung (= physical_inventory): Summe quantity ohne wishlist/sold_ts;
  aktive Listings bleiben Besitz bis zum echten Verkauf.
Im Portfolio: physical_inventory OHNE published/ended (siehe web.portfolio).
Verkauft: nur Items mit sold_ts; ended ohne Sold-Markierung zählt nicht.

Hinweis: „In Sammlung“ und „Im Portfolio“ sind bewusst unterschiedliche Zahlen.
"""
from __future__ import annotations

import json
from typing import Any

from web import portfolio as portfolio_math


def _qty(item: dict) -> int:
    return portfolio_math.quantity_of(item)


def is_sold_item(item: dict) -> bool:
    return portfolio_math.is_sold(item)


def in_collection_item(item: dict) -> bool:
    """Physischer Besitz inkl. eBay-Live — Alias für physical_inventory."""
    return portfolio_math.is_physical_inventory(item)


def is_sold_draft(draft: dict) -> bool:
    """Verkauf nur bei explizitem Sold-Endgrund — nicht jedes ended."""
    if draft.get("status") != "ended":
        return False
    reason = str(draft.get("ended_reason") or "")
    return reason == "Verkauft" or reason.startswith("Verkauft")


def summarize_profile(*, items: list[dict], drafts: list[dict]) -> dict[str, Any]:
    """Berechnet Profil-Kennzahlen aus Rohdaten (gleiche Besitzregeln wie Portfolio)."""
    dmap = {d["id"]: d.get("status") for d in drafts if d.get("id")}
    enriched = []
    for i in items:
        if i.get("draft_id") and not i.get("draft_status"):
            enriched.append({**i, "draft_status": dmap.get(i["draft_id"])})
        else:
            enriched.append(i)
    summary = portfolio_math.summarize_portfolio(enriched, draft_status_by_id=dmap)
    active = sum(1 for d in drafts if d.get("status") == "published")
    sold_ids = {i.get("id") for i in items if is_sold_item(i) and i.get("id")}
    sold = len(sold_ids)
    linked = {
        i.get("draft_id") for i in items
        if is_sold_item(i) and i.get("draft_id")
    }
    for d in drafts:
        if not is_sold_draft(d):
            continue
        did = d.get("id")
        if did and did in linked:
            continue
        sold += 1
    return {
        "active_on_ebay": active,
        "in_collection": summary.physical_piece_count,
        "in_collection_label": "Besitz inklusive eBay-Angebote",
        "portfolio_pieces": summary.piece_count,
        "portfolio_label": "Im Portfolio",
        "sold": sold,
    }


def load_account_items(store, account_id: int) -> list[dict]:
    rows = store._conn.execute(  # noqa: SLF001
        "SELECT id, data FROM collection_items WHERE account_id = ?",
        (account_id,),
    ).fetchall()
    items = []
    for row in rows:
        try:
            data = json.loads(row["data"])
        except (TypeError, ValueError, json.JSONDecodeError):
            data = {}
        data["id"] = row["id"]
        items.append(data)
    return items


def load_account_drafts(store, chat_id: int) -> list[dict]:
    rows = store._conn.execute(  # noqa: SLF001
        "SELECT id FROM drafts WHERE chat_id = ?", (chat_id,),
    ).fetchall()
    drafts = []
    for row in rows:
        d = store.get_draft(row["id"])
        if d:
            drafts.append(d)
    return drafts


def profile_summary_for(store, account: dict, chat_id: int) -> dict[str, Any]:
    items = load_account_items(store, account["id"])
    drafts = load_account_drafts(store, chat_id)
    stats = summarize_profile(items=items, drafts=drafts)
    try:
        alerts_n = store._conn.execute(  # noqa: SLF001
            "SELECT COUNT(*) c FROM price_alerts WHERE account_id = ? "
            "AND triggered_at IS NULL",
            (account["id"],),
        ).fetchone()["c"]
    except Exception:
        alerts_n = 0
    stats["active_alerts"] = int(alerts_n or 0)
    return stats
