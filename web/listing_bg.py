"""Hintergrundfarben für eBay-Listings (pro Stück, Whitelist).

Sammlung bleibt transparenter Freisteller; beim Listen legt render_product
den Cutout auf diese Farbe. Unbekanntes Hex → Fehler.

DEFAULT_LISTING_BG = Hintergrund 3 (Schwarz / dunkles Grau) — gilt
automatisch für alle Stücke ohne eigene Wahl; danach im Foto-Menü änderbar.
"""
from __future__ import annotations

# Standard = Taste 3 der Listing-Wahl (Weiß / Warmweiß / Schwarz)
DEFAULT_LISTING_BG = "#0B0B0D"

# Hex → Anzeigename (DE). Reihenfolge = UI-Reihenfolge.
LISTING_BG_COLORS: dict[str, str] = {
    # Weiß-Töne
    "#FFFFFF": "Reinweiß",
    "#F5F9FF": "Kaltweiß",
    "#F7F4EF": "Off-White",
    "#F5EFE3": "Warmweiß",
    # Dunkel
    "#0B0B0D": "Schwarz",
    "#2A2E35": "Anthrazit",
    "#3D4450": "Graphit",
    # SERO
    "#E4ECF6": "Eisblau",
    "#D6E6F8": "Hellblau",
    "#C5D4EA": "Navy-Hell",
}

LISTING_BG_ALLOWED = frozenset(LISTING_BG_COLORS)


def normalize_listing_bg(value: str | None) -> str | None:
    """Leer/None → None (App nutzt dann DEFAULT_LISTING_BG). Sonst #RRGGBB."""
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in ("none", "null", "default"):
        return None
    if not s.startswith("#"):
        s = "#" + s
    s = s.upper()
    if len(s) == 4:  # #RGB → #RRGGBB
        s = "#" + "".join(c * 2 for c in s[1:])
    if s not in LISTING_BG_ALLOWED:
        raise ValueError(f"Hintergrundfarbe nicht erlaubt: {value}")
    return s


def effective_listing_bg(item: dict | None) -> str:
    """Gewählte Farbe oder Hintergrund 3 (Schwarz)."""
    if item:
        raw = item.get("listing_bg")
        if raw:
            try:
                color = normalize_listing_bg(raw)
            except ValueError:
                color = None
            if color:
                return color
    return DEFAULT_LISTING_BG
