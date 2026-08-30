"""Numerische Geldwerte — verhindert float-str TypeError."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


def as_money(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(Decimal(str(value).replace(",", ".").strip().replace("€", "").replace("EUR", "").strip()))
    except (InvalidOperation, ValueError, TypeError):
        return None
