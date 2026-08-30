"""ADR-001 F1 — schmale Ports (Schnittstellen) ohne Verhaltensänderung.

Ziel: Store / Foto / Queue später austauschbar machen (SQLite→Postgres,
Filesystem→S3, asyncio-Task→dauerhafte Queue), ohne Big-Bang.
Aktuell: nur Typen/Protokolle + Docstrings. Produktion bleibt unverändert.
"""
from __future__ import annotations

from typing import Any, Optional, Protocol


class StorePort(Protocol):
    """Persistenz — heute bot.drafts.Store (SQLite)."""

    def kv_get(self, key: str) -> Any: ...
    def kv_set(self, key: str, value: Any) -> None: ...
    def get_draft(self, draft_id: str) -> Optional[dict]: ...
    def save_draft(self, draft_id: str, **fields: Any) -> None: ...


class PhotoPort(Protocol):
    """Foto-Ablage — heute collection_photos/ auf Disk."""

    def path_for(self, account_id: int, name: str) -> Any: ...
    def exists(self, account_id: int, name: str) -> bool: ...


class QueuePort(Protocol):
    """Hintergrundjobs — heute asyncio.create_task in app_api."""

    def enqueue_scan(self, item_id: str) -> None: ...
    def enqueue_price_refresh(self, item_id: str) -> None: ...


# Re-Export des Publish-Ports (schon in publish.py produktiv genutzt)
from web.publish import EbayPublishPort, FakeEbay  # noqa: E402,F401

__all__ = [
    "StorePort",
    "PhotoPort",
    "QueuePort",
    "EbayPublishPort",
    "FakeEbay",
]
