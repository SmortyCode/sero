"""Album-Debounce: Telegram liefert Alben als separate Updates mit gemeinsamer
media_group_id und OHNE 'Album-Ende'-Event. Wir puffern pro Gruppe und starten
die Verarbeitung erst, wenn `delay` Sekunden lang nichts mehr kommt."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable


class AlbumBuffer:
    def __init__(self, callback: Callable[[str, list[Any]], Awaitable[None]], delay: float = 2.5):
        self.callback = callback
        self.delay = delay
        self._groups: dict[str, dict] = {}

    def add(self, group_id: str, item: Any) -> None:
        group = self._groups.setdefault(group_id, {"items": [], "task": None})
        group["items"].append(item)
        if group["task"] is not None:
            group["task"].cancel()
        group["task"] = asyncio.create_task(self._fire_after_delay(group_id))

    async def _fire_after_delay(self, group_id: str) -> None:
        try:
            await asyncio.sleep(self.delay)
        except asyncio.CancelledError:
            return  # neues Foto derselben Gruppe hat den Timer resettet
        group = self._groups.pop(group_id, None)
        if group:
            await self.callback(group_id, group["items"])
