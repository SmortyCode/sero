"""Feature-/Canary-Flags für Cutout v2 und Pricing v2.

Default: alles aus. Canary nur über Allowlist oder Prozent — kein stilles 100%.
"""
from __future__ import annotations

import hashlib
import os


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip() in ("1", "true", "True", "yes", "on")


def _canary_hit(item_id: str | None, env_name: str) -> bool:
    """SERO_*_CANARY=id1,id2 oder Prozent 1-100 (deterministisch über item_id)."""
    raw = (os.environ.get(env_name) or "").strip()
    if not raw:
        return False
    if item_id and item_id in {x.strip() for x in raw.split(",") if x.strip() and not x.strip().isdigit()}:
        return True
    # Prozent: reine Zahl
    try:
        pct = int(raw)
    except ValueError:
        # Gemischt: Allowlist ohne Treffer
        return False
    if pct <= 0 or not item_id:
        return False
    pct = min(100, pct)
    h = int(hashlib.sha1(item_id.encode()).hexdigest()[:8], 16) % 100
    return h < pct


def cutout_v2_enabled(item_id: str | None = None) -> bool:
    if _truthy("SERO_CUTOUT_V2"):
        return True
    return _canary_hit(item_id, "SERO_CUTOUT_V2_CANARY")


def cutout_v2_shadow(item_id: str | None = None) -> bool:
    if _truthy("SERO_CUTOUT_V2_SHADOW"):
        return True
    return _canary_hit(item_id, "SERO_CUTOUT_V2_SHADOW_CANARY")


def pricing_v2_enabled(item_id: str | None = None) -> bool:
    if _truthy("SERO_PRICING_V2"):
        return True
    return _canary_hit(item_id, "SERO_PRICING_V2_CANARY")


def pricing_v2_shadow(item_id: str | None = None) -> bool:
    if _truthy("SERO_PRICING_V2_SHADOW"):
        return True
    return _canary_hit(item_id, "SERO_PRICING_V2_SHADOW_CANARY")
