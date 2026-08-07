"""eBay.de-Gebührenschätzung (Privatverkäufer) — für Transparenz VOR dem Upload.

Stand Feb 2026: Privatverkauf auf eBay.de ist grundsätzlich provisionsfrei.
AUSNAHME Sammelkarten (Trading Cards): 11 % bis 990 €, 3 % darüber,
plus 0,45 € Fixgebühr pro Bestellung. Gewerbliche Konten haben eigene Tarife —
diese Schätzung gilt für Privatverkäufer.

Quelle: ebay.de/verkaeuferportal (Gebühren privat, Rate-Card Feb 2026).
"""

from __future__ import annotations

# Kategorienamen-Schlüsselwörter, die unter die Sammelkarten-Provision fallen
CARD_FEE_KEYWORDS = (
    "sammelkarten", "einzelkarten", "tcg", "trading card",
    "sammelkartenspiele", "karten-sets", "booster",
)

CARD_FEE_RATE = 0.11        # bis 990 €
CARD_FEE_RATE_ABOVE = 0.03  # Anteil über 990 €
CARD_FEE_TIER = 990.0
ORDER_FIXED_FEE = 0.45      # pro Bestellung (ab 10,01 € Gesamtbetrag)

# Gewerblich: Verkaufsprovision in JEDER Kategorie (Sätze variieren je Kategorie
# etwas — 11 % ist der übliche Basissatz, wir schätzen bewusst einheitlich).
BUSINESS_FEE_RATE = 0.11


def is_card_fee_category(category_name: str | None) -> bool:
    if not category_name:
        return False
    name = category_name.lower()
    return any(k in name for k in CARD_FEE_KEYWORDS)


def estimate_fee(category_name: str | None, price_eur: float, quantity: int = 1,
                 business: bool = False) -> dict:
    """Geschätzte eBay-Gebühr für einen Verkauf ALLER quantity Exemplare.

    business=True (gewerbliches Konto): Provision auf JEDE Kategorie.
    business=False (privat): nur Sammelkarten-Kategorien kosten Provision.
    Rückgabe: {"fee": float, "net": float, "rate": float, "applies": bool, "label": str}
    """
    total = price_eur * max(1, quantity)
    is_card = is_card_fee_category(category_name)
    if not business and not is_card:
        return {"fee": 0.0, "net": total, "rate": 0.0, "applies": False, "label": ""}

    rate = CARD_FEE_RATE if is_card else BUSINESS_FEE_RATE
    below = min(total, CARD_FEE_TIER)
    above = max(0.0, total - CARD_FEE_TIER)
    fee = below * rate + above * (CARD_FEE_RATE_ABOVE if is_card else rate)
    if total > 10.0:
        fee += ORDER_FIXED_FEE
    fee = round(fee, 2)
    label = "Sammelkarten" if is_card and not business else "gewerblich"
    return {"fee": fee, "net": round(total - fee, 2), "rate": rate,
            "applies": True, "label": label}
