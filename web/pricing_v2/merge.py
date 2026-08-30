"""Singleflight + monotones Merge: verified darf nie durch weak/error verdrängt werden."""
from __future__ import annotations

import threading
import time
from typing import Any, Callable


_LOCKS: dict[str, threading.Lock] = {}
_GUARD = threading.Lock()
_RANK = {"verified": 3, "exact": 3, "weak": 1, "no_match": 0, "error": 0}


def _lock_for(key: str) -> threading.Lock:
    with _GUARD:
        if key not in _LOCKS:
            _LOCKS[key] = threading.Lock()
        return _LOCKS[key]


def confidence_rank(conf: str | None, source: str | None = None) -> int:
    c = (conf or "").lower()
    if c in _RANK:
        return _RANK[c]
    s = (source or "").lower()
    if "weak" in s:
        return 1
    if s in ("ebay_sold", "pricecharting", "tcgcsv", "cardmarket"):
        return 3
    if s in ("pricecharting_weak", "estimate"):
        return 1
    return 2


def should_replace(existing: dict[str, Any] | None, incoming: dict[str, Any]) -> bool:
    if not existing:
        return True
    er = confidence_rank(existing.get("confidence"), existing.get("source"))
    ir = confidence_rank(incoming.get("confidence"), incoming.get("source"))
    if ir < er:
        return False
    if ir > er:
        return True
    # gleicher Rang: neuerer Timestamp nur wenn value vorhanden
    if incoming.get("value") is None and existing.get("value") is not None:
        return False
    return True


def singleflight(key: str, fn: Callable[[], Any]) -> Any:
    """Genau ein Providerlauf pro Key; parallele Aufrufer warten mit."""
    lock = _lock_for(key)
    with lock:
        return fn()
