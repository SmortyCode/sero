"""Gemeinsamer Publish-Kern (Phase B, ADR-003 Stufe 2).

App und Telegram sollen denselben Intent-Claim nutzen. Der geldrelevante
Ablauf speichert eine dauerhafte Publish-Absicht in SQLite; bei Timeout +
fehlgeschlagenem eBay-Abgleich wird publish_uncertain gesetzt — kein
automatischer Zweit-Publish.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Optional, Protocol

log = logging.getLogger("publish")

# Geschützte Endzustände — nie anfassen / nie auto-republish
END_STATES = frozenset({"published", "ended", "dry_run_done", "publish_uncertain"})
ACTIVE_STATES = frozenset({"ready_for_review", "publishing"})
VERBOTEN_DRAFT = ("publishing", "published", "ended", "dry_run_done", "publish_uncertain")


def unlock_dry_run_for_live(store, draft_id: str, *, dry_run: bool) -> Optional[str]:
    """Bereitet einen Draft auf den Publish-Claim vor.

    Rückgabe None = Claim darf folgen. Sonst Fehlercode:
      missing | terminal | dry_run_locked

    dry_run_done bleibt geschützt, solange der Testmodus an ist.
    Ist Dry-Run aus, wird der Status auf ready zurückgesetzt — Inventar/Offer
    und SKU bleiben, damit publishOffer live nachziehen kann (kein Auto-Publish).
    """
    draft = store.get_draft(draft_id)
    if not draft:
        return "missing"
    status = draft.get("status")
    if status == "dry_run_done":
        if dry_run:
            return "dry_run_locked"
        draft["status"] = "ready"
        store.update_draft(draft_id, draft)
        return None
    if status in ("published", "ended", "publish_uncertain"):
        return "terminal"
    return None


class EbayPublishPort(Protocol):
    """Minimaler Adapter — Produktion: EbayClient-Hüllen; Tests: FakeEbay."""

    async def find_offer_by_sku(self, sku: str) -> Optional[str]:
        ...

    async def find_listing_by_sku(self, sku: str) -> Optional[str]:
        ...

    async def publish_offer(self, offer_id: str) -> str:
        """Gibt listing_id zurück. Timeout → Exception."""
        ...

    async def add_listing(self, payload: dict) -> str:
        """Trading API: gibt listing_id zurück. Timeout → Exception."""
        ...


class FakeEbay:
    """Offline-Adapter für Intent-/Claim-Tests."""

    def __init__(self):
        self.publish_calls = 0
        self.sku_offer: dict[str, str] = {}
        self.sku_listing: dict[str, str] = {}
        self.timeout_on_publish = False
        self.timeout_on_lookup = False

    async def find_offer_by_sku(self, sku: str) -> Optional[str]:
        if self.timeout_on_lookup:
            raise TimeoutError("lookup timeout")
        return self.sku_offer.get(sku)

    async def find_listing_by_sku(self, sku: str) -> Optional[str]:
        if self.timeout_on_lookup:
            raise TimeoutError("lookup timeout")
        return self.sku_listing.get(sku)

    async def publish_offer(self, offer_id: str) -> str:
        self.publish_calls += 1
        if self.timeout_on_publish:
            raise TimeoutError("publish timeout")
        # offer_id -> listing
        lid = f"L-{offer_id}"
        for sku, oid in self.sku_offer.items():
            if oid == offer_id:
                self.sku_listing[sku] = lid
                break
        return lid

    async def add_listing(self, payload: dict) -> str:
        self.publish_calls += 1
        self.last_trading_payload = payload
        if self.timeout_on_publish:
            raise TimeoutError("publish timeout")
        lid = f"T-{self.publish_calls}"
        sku = (payload or {}).get("sku") or ""
        if sku:
            self.sku_listing[sku] = lid
        return lid


class LiveEbayAdapter:
    """Adapter um EbayClient + Inventory-Helfer für execute_publish."""

    def __init__(self, ebay, user_id: int):
        self.ebay = ebay
        self.user_id = user_id

    async def find_offer_by_sku(self, sku: str) -> Optional[str]:
        from bot.ebay.auth import EbayTimeout
        from bot.ebay.inventory import find_offer_for_sku
        try:
            offer = await find_offer_for_sku(self.ebay, sku, self.user_id)
        except EbayTimeout as e:
            raise TimeoutError(str(e)) from e
        if not offer:
            return None
        return offer.get("offerId") or offer.get("offer_id")

    async def find_listing_by_sku(self, sku: str) -> Optional[str]:
        from bot.ebay.auth import EbayTimeout
        from bot.ebay.inventory import find_offer_for_sku
        try:
            offer = await find_offer_for_sku(self.ebay, sku, self.user_id)
        except EbayTimeout as e:
            raise TimeoutError(str(e)) from e
        if not offer:
            return None
        listing = offer.get("listing") or {}
        return listing.get("listingId")

    async def publish_offer(self, offer_id: str) -> str:
        """Roh-Publish ohne Inventory-Reconcile — das macht execute_publish."""
        from bot.ebay.auth import EbayTimeout
        from bot.ebay.inventory import EBAY_API, DE_HEADERS, InventoryError, translate_ebay_error
        try:
            resp = await self.ebay.request(
                "POST", f"{EBAY_API}/sell/inventory/v1/offer/{offer_id}/publish",
                auth="user", user_id=self.user_id, headers=DE_HEADERS, json_body={},
            )
        except EbayTimeout as e:
            raise TimeoutError(str(e)) from e
        if resp.status_code not in (200, 201):
            raise InventoryError(translate_ebay_error(resp.text, resp.status_code), raw=resp.text)
        return resp.json()["listingId"]

    async def add_listing(self, payload: dict) -> str:
        from bot.ebay.trading import add_listing as trading_add, build_add_item_xml
        xml_and_call = payload.get("xml_and_call")
        if not xml_and_call:
            xml_and_call = build_add_item_xml(**{
                k: v for k, v in (payload or {}).items()
                if k not in ("channel", "xml_and_call")
            })
        return await trading_add(self.ebay, self.user_id, xml_and_call)


def apply_intent_to_draft(store, draft_id: str, intent: dict) -> dict:
    """Draft-Status an Intent-Endzustand anbinden (frisch lesen)."""
    draft = store.get_draft(draft_id)
    if not draft:
        return intent
    state = intent.get("state")
    if state == "published":
        draft["status"] = "published"
        if not draft.get("published_at"):
            draft["published_at"] = time.time()
        if intent.get("listing_id"):
            draft["listing_id"] = intent["listing_id"]
            draft["item_url"] = f"https://www.ebay.de/itm/{intent['listing_id']}"
        if intent.get("offer_id"):
            draft["offer_id"] = intent["offer_id"]
        if intent.get("sku"):
            draft["sku"] = intent["sku"]
        store.update_draft(draft_id, draft)
    elif state == "dry_run_done":
        draft["status"] = "dry_run_done"
        if intent.get("offer_id"):
            draft["offer_id"] = intent["offer_id"]
        if intent.get("sku"):
            draft["sku"] = intent["sku"]
        store.update_draft(draft_id, draft)
    elif state == "publish_uncertain":
        draft["status"] = "publish_uncertain"
        if intent.get("offer_id"):
            draft["offer_id"] = intent["offer_id"]
        store.update_draft(draft_id, draft)
    return intent


def ensure_publish_tables(store) -> None:
    with store._lock:  # noqa: SLF001
        store._conn.execute(  # noqa: SLF001
            """CREATE TABLE IF NOT EXISTS publish_intents (
                id TEXT PRIMARY KEY,
                draft_id TEXT NOT NULL,
                account_id TEXT,
                sku TEXT,
                state TEXT NOT NULL,
                offer_id TEXT,
                listing_id TEXT,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                fingerprint TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )"""
        )
        store._conn.execute(  # noqa: SLF001
            "CREATE INDEX IF NOT EXISTS idx_publish_draft ON publish_intents(draft_id)"
        )
        store._conn.commit()  # noqa: SLF001


def get_intent(store, intent_id: str) -> Optional[dict]:
    ensure_publish_tables(store)
    row = store._conn.execute(  # noqa: SLF001
        "SELECT * FROM publish_intents WHERE id = ?", (intent_id,)
    ).fetchone()
    return dict(row) if row else None


def active_intent_for_draft(store, draft_id: str) -> Optional[dict]:
    ensure_publish_tables(store)
    row = store._conn.execute(  # noqa: SLF001
        "SELECT * FROM publish_intents WHERE draft_id = ? AND state IN "
        "('ready_for_review','publishing') ORDER BY created_at DESC LIMIT 1",
        (draft_id,),
    ).fetchone()
    return dict(row) if row else None


def claim_or_create_intent(
    store,
    *,
    draft_id: str,
    account_id: str | int | None,
    sku: str,
    fingerprint: str | None = None,
) -> Optional[dict]:
    """Genau eine aktive Absicht pro Draft. Atomarer Draft-Claim + Intent-Zeile.

    Returns Intent-Dict oder None wenn Claim verloren / Endzustand / fremd.
    """
    ensure_publish_tables(store)

    def _owner_ok(draft: dict | None) -> bool:
        if not draft:
            return False
        if draft.get("status") in END_STATES:
            return False
        owner = draft.get("chat_id")
        if account_id is None or owner is None:
            return True
        try:
            return int(owner) == int(account_id)
        except (TypeError, ValueError):
            return str(owner) == str(account_id)

    existing = active_intent_for_draft(store, draft_id)
    if existing:
        # Zuerst claimen (atomar), dann Besitz prüfen — kein unlocked get_draft-Rennen.
        if not store.claim_draft(draft_id, "publishing", verboten=VERBOTEN_DRAFT):
            return None
        draft = store.get_draft(draft_id)
        if not _owner_ok(draft):
            store.release_draft_claim(draft_id, "ready")
            log.warning("Publish-Claim abgelehnt (fremd/Ende): Draft %s", draft_id)
            return None
        return existing

    if not store.claim_draft(draft_id, "publishing", verboten=VERBOTEN_DRAFT):
        return None
    draft = store.get_draft(draft_id)
    if not _owner_ok(draft):
        store.release_draft_claim(draft_id, "ready")
        log.warning("Publish-Claim abgelehnt (fremd/Ende): Draft %s", draft_id)
        return None

    now = time.time()
    intent_id = uuid.uuid4().hex
    with store._lock:  # noqa: SLF001
        store._conn.execute(  # noqa: SLF001
            "INSERT INTO publish_intents "
            "(id, draft_id, account_id, sku, state, offer_id, listing_id, "
            "attempts, last_error, fingerprint, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (intent_id, draft_id, str(account_id) if account_id is not None else None,
             sku, "publishing", None, None, 0, None, fingerprint, now, now),
        )
        store._conn.commit()  # noqa: SLF001
    return get_intent(store, intent_id)


def _set_intent(store, intent_id: str, **fields) -> dict:
    ensure_publish_tables(store)
    cur = get_intent(store, intent_id)
    if not cur:
        raise KeyError(intent_id)
    if cur["state"] in END_STATES and fields.get("state") not in (None, cur["state"]):
        # Geschützte Endzustände nicht überschreiben (außer idempotent gleich)
        if fields.get("state") and fields["state"] != cur["state"]:
            return cur
    fields["updated_at"] = time.time()
    cols = []
    vals = []
    for k, v in fields.items():
        cols.append(f"{k} = ?")
        vals.append(v)
    vals.append(intent_id)
    with store._lock:  # noqa: SLF001
        store._conn.execute(  # noqa: SLF001
            f"UPDATE publish_intents SET {', '.join(cols)} WHERE id = ?", vals
        )
        store._conn.commit()  # noqa: SLF001
    return get_intent(store, intent_id)


async def reconcile_intent(store, ebay: EbayPublishPort, intent: dict) -> dict:
    """SKU/Offer/Listing bei eBay abgleichen — Timeout bleibt uncertain."""
    sku = intent.get("sku") or ""
    try:
        listing_id = await ebay.find_listing_by_sku(sku)
        if listing_id:
            return _set_intent(store, intent["id"], state="published",
                               listing_id=listing_id, last_error=None)
        offer_id = intent.get("offer_id") or await ebay.find_offer_by_sku(sku)
        if offer_id and not intent.get("offer_id"):
            intent = _set_intent(store, intent["id"], offer_id=offer_id)
        return intent
    except TimeoutError as e:
        return _set_intent(store, intent["id"], state="publish_uncertain",
                           last_error=f"reconcile:{e}")


async def execute_publish(
    store,
    ebay: EbayPublishPort,
    intent_id: str,
    *,
    dry_run: bool = False,
    trading_payload: Optional[dict] = None,
) -> dict:
    """Einen Publish-Versuch ausführen. Nie auto-retry bei publish_uncertain.

    Neue Festpreis-Angebote: trading_payload → AddFixedPriceItem (Seller Hub
    editierbar). Alte Inventory-Offers: publishOffer wie bisher.
    """
    intent = get_intent(store, intent_id)
    if not intent:
        raise KeyError(intent_id)
    if intent["state"] == "publish_uncertain":
        return intent  # kein automatischer zweiter Publish
    if intent["state"] in ("published", "ended", "dry_run_done"):
        return intent

    intent = _set_intent(store, intent_id, attempts=int(intent.get("attempts") or 0) + 1,
                         state="publishing")

    if trading_payload is not None:
        if dry_run:
            return _set_intent(store, intent_id, state="dry_run_done", last_error=None)
        try:
            listing_id = await ebay.add_listing(trading_payload)
            return _set_intent(store, intent_id, state="published", listing_id=listing_id,
                               last_error=None)
        except TimeoutError:
            intent = await reconcile_intent(store, ebay, get_intent(store, intent_id))
            if intent.get("state") == "published":
                return intent
            return _set_intent(store, intent_id, state="publish_uncertain",
                               last_error="publish_timeout")
        except Exception as e:  # noqa: BLE001
            return _set_intent(store, intent_id, state="failed", last_error=str(e)[:500])

    sku = intent["sku"]
    offer_id = intent.get("offer_id")
    if not offer_id:
        try:
            offer_id = await ebay.find_offer_by_sku(sku)
        except TimeoutError:
            return _set_intent(store, intent_id, state="publish_uncertain",
                               last_error="offer_lookup_timeout")
        if offer_id:
            intent = _set_intent(store, intent_id, offer_id=offer_id)
        else:
            return _set_intent(store, intent_id, state="failed",
                               last_error="no_offer")

    if dry_run:
        return _set_intent(store, intent_id, state="dry_run_done", last_error=None)

    try:
        listing_id = await ebay.publish_offer(offer_id)
        return _set_intent(store, intent_id, state="published", listing_id=listing_id,
                           last_error=None)
    except TimeoutError:
        # Abgleich versuchen
        intent = await reconcile_intent(store, ebay, get_intent(store, intent_id))
        if intent.get("state") == "published":
            return intent
        return _set_intent(store, intent_id, state="publish_uncertain",
                           last_error="publish_timeout")
