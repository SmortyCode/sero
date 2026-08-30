"""Zentrale Besitz-, Mengen- und Wertlogik für Collection, Dashboard, Historie, Profil.

Produktregel Portfolio (beschlossen, unverändert):
  portfolio_owned = nicht wishlist, nicht sold_ts, draft nicht published/ended.

physical_inventory = nicht wishlist, nicht sold_ts (inkl. noch physisch vorhandene
  eBay-Live-Stücke).

Geld intern in Cent (int). Anzeige-Euro über cents_to_eur / eur_to_cents.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any, Iterable
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo("Europe/Berlin")
CENT = Decimal("0.01")

# Draft-Status, die ein Stück aus dem Portfolio nehmen
PORTFOLIO_EXCLUDED_DRAFT = frozenset({"published", "ended"})

# Quellen, die als belegte bzw. Spannen-Marktwerte gelten (kein eigener Wert)
MARKET_SOURCES_BELEGT = frozenset({
    "ebay_sold", "cardmarket", "tcgplayer", "scryfall", "ygoprodeck",
    "tcgdex", "tcgcsv", "pricecharting",
})
MARKET_SOURCES_SPANNE = frozenset({"ebay", "ebay_eu", "pricecharting_weak"})


def eur_to_cents(value: Any) -> int | None:
    """Euro → Cent. None/ungültig → None. Nie still 0 bei fehlendem Wert."""
    if value is None or value == "":
        return None
    try:
        d = Decimal(str(value).replace(",", ".").strip())
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not d.is_finite():
        return None
    return int((d.quantize(CENT, rounding=ROUND_HALF_UP) * 100).to_integral_value())


def cents_to_eur(cents: int | None) -> float | None:
    if cents is None:
        return None
    return float((Decimal(int(cents)) / 100).quantize(CENT, rounding=ROUND_HALF_UP))


def cents_to_eur_str(cents: int | None) -> str | None:
    if cents is None:
        return None
    return f"{(Decimal(int(cents)) / 100).quantize(CENT, rounding=ROUND_HALF_UP)}"


def quantity_of(item: dict) -> int:
    try:
        q = int(item.get("quantity") or 1)
    except (TypeError, ValueError):
        return 1
    return max(0, min(q, 10000))


def is_wishlist(item: dict) -> bool:
    return bool(item.get("wishlist"))


def is_sold(item: dict) -> bool:
    return bool(item.get("sold_ts"))


def draft_status_of(item: dict, draft_status_by_id: dict[str, str] | None = None) -> str | None:
    st = item.get("draft_status")
    if st:
        return st
    did = item.get("draft_id")
    if did and draft_status_by_id is not None:
        return draft_status_by_id.get(did)
    return None


def is_portfolio_owned(item: dict, draft_status_by_id: dict[str, str] | None = None) -> bool:
    """Portfolio: kein Wunsch, nicht verkauft, nicht live/beendet auf eBay."""
    if is_wishlist(item) or is_sold(item):
        return False
    st = draft_status_of(item, draft_status_by_id)
    if st in PORTFOLIO_EXCLUDED_DRAFT:
        return False
    return True


def is_physical_inventory(item: dict, draft_status_by_id: dict[str, str] | None = None) -> bool:
    """Physischer Bestand inkl. aktiver eBay-Angebote und beendeter Listings
    ohne Verkaufsmarkierung; ohne Wunsch/Verkauft."""
    if is_wishlist(item) or is_sold(item):
        return False
    return True


def value_basis(item: dict) -> str:
    """market | own_value | none — was den Portfolio-Wert speist."""
    src = item.get("price_source")
    state = item.get("price_state")
    if src == "manual" or state == "eigener_wert":
        return "own_value"
    cents = unit_value_cents(item)
    if cents is None:
        return "none"
    if state == "unbekannt":
        return "none"
    if src in MARKET_SOURCES_BELEGT or src in MARKET_SOURCES_SPANNE:
        return "market"
    if state in ("belegt", "spanne"):
        return "market"
    return "none"


def unit_value_cents(item: dict) -> int | None:
    """Einzelstück-Wert in Cent. Unbekannt → None (nie versteckter Alt-Wert)."""
    if item.get("price_state") == "unbekannt" and item.get("price_source") != "manual":
        return None
    if item.get("price_source") == "manual":
        raw = item.get("est_value_manual", item.get("est_value"))
        return eur_to_cents(raw)
    if item.get("price_state") == "unbekannt":
        return None
    return eur_to_cents(item.get("est_value"))


def position_value_cents(item: dict) -> int | None:
    u = unit_value_cents(item)
    if u is None:
        return None
    return u * quantity_of(item)


@dataclass(frozen=True)
class PortfolioSummary:
    row_count: int
    piece_count: int
    portfolio_total_cents: int
    physical_row_count: int
    physical_piece_count: int
    physical_total_cents: int
    market_piece_count: int
    market_value_cents: int
    own_value_piece_count: int
    own_value_cents: int
    invested_cents: int | None

    @property
    def portfolio_total(self) -> float:
        return cents_to_eur(self.portfolio_total_cents) or 0.0

    @property
    def physical_total(self) -> float:
        return cents_to_eur(self.physical_total_cents) or 0.0

    @property
    def market_coverage_pieces(self) -> float:
        if self.piece_count <= 0:
            return 0.0
        return round(self.market_piece_count / self.piece_count, 4)

    @property
    def market_coverage_value(self) -> float:
        if self.portfolio_total_cents <= 0:
            return 0.0
        return round(self.market_value_cents / self.portfolio_total_cents, 4)

    def as_stats_dict(self) -> dict[str, Any]:
        return {
            "count": self.row_count,
            "row_count": self.row_count,
            "piece_count": self.piece_count,
            "total_value": self.portfolio_total,
            "total_value_cents": self.portfolio_total_cents,
            "physical_inventory": {
                "row_count": self.physical_row_count,
                "piece_count": self.physical_piece_count,
                "total_value": self.physical_total,
            },
            "value_basis": {
                "market_piece_count": self.market_piece_count,
                "market_value": cents_to_eur(self.market_value_cents) or 0.0,
                "own_value_piece_count": self.own_value_piece_count,
                "own_value": cents_to_eur(self.own_value_cents) or 0.0,
                "market_coverage_pieces": self.market_coverage_pieces,
                "market_coverage_value": self.market_coverage_value,
            },
            "invested": cents_to_eur(self.invested_cents) if self.invested_cents is not None else None,
        }


def summarize_portfolio(
    items: Iterable[dict],
    *,
    draft_status_by_id: dict[str, str] | None = None,
) -> PortfolioSummary:
    row = piece = total = 0
    phys_row = phys_piece = phys_total = 0
    mkt_piece = mkt_val = own_piece = own_val = 0
    invested = 0
    has_invest = False
    for item in items:
        q = quantity_of(item)
        pos = position_value_cents(item)
        basis = value_basis(item)
        if is_portfolio_owned(item, draft_status_by_id):
            row += 1
            piece += q
            if pos is not None:
                total += pos
                if basis == "market":
                    mkt_piece += q
                    mkt_val += pos
                elif basis == "own_value":
                    own_piece += q
                    own_val += pos
            pp = eur_to_cents(item.get("purchase_price"))
            if pp is not None:
                invested += pp * q
                has_invest = True
        if is_physical_inventory(item, draft_status_by_id):
            phys_row += 1
            phys_piece += q
            if pos is not None:
                phys_total += pos
    return PortfolioSummary(
        row_count=row,
        piece_count=piece,
        portfolio_total_cents=total,
        physical_row_count=phys_row,
        physical_piece_count=phys_piece,
        physical_total_cents=phys_total,
        market_piece_count=mkt_piece,
        market_value_cents=mkt_val,
        own_value_piece_count=own_piece,
        own_value_cents=own_val,
        invested_cents=invested if has_invest else None,
    )


def berlin_today(now: datetime | None = None) -> str:
    dt = now or datetime.now(BERLIN)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=BERLIN)
    else:
        dt = dt.astimezone(BERLIN)
    return dt.date().isoformat()


def berlin_day_from_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts, BERLIN).date().isoformat()


def ensure_history_ends_at_total(
    history: list[dict],
    *,
    portfolio_total_cents: int,
    now: datetime | None = None,
) -> tuple[list[dict], str, str]:
    """Letzter Historienpunkt = aktueller Portfolio-Total (Berlin-Tag).

    Liefert (history, as_of_day, timezone_name).
    """
    as_of = now or datetime.now(BERLIN)
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=BERLIN)
    else:
        as_of = as_of.astimezone(BERLIN)
    day = as_of.date().isoformat()
    total = cents_to_eur(portfolio_total_cents) or 0.0
    out = [dict(p) for p in (history or []) if p and p.get("day")]
    if out and out[-1].get("day") == day:
        out[-1] = {**out[-1], "value": total}
    else:
        out.append({"day": day, "value": total})
    return out, day, "Europe/Berlin"


def collection_revision(
    *,
    item_count: int,
    items_updated_at: float | None,
    draft_fingerprint: str | None = None,
) -> str:
    """Revision hängt an Items UND Draft-Fingerprint (Statusänderungen)."""
    base = f"{item_count}:{items_updated_at or 0}"
    if draft_fingerprint:
        return f"{base}:{draft_fingerprint}"
    return base


def draft_status_fingerprint(statuses: Iterable[str]) -> str:
    """Kompakte, stabile Kennung über Draft-Status (ohne Sync-Zeitstempel)."""
    from collections import Counter
    c = Counter(str(s or "") for s in statuses)
    return ",".join(f"{k}={c[k]}" for k in sorted(c))
