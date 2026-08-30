"""Serverseitiger Publish-Preflight — reine Validierung, kein eBay-Call.

Gibt eine Checkliste zurück. `valid=True` nur wenn nichts Hartes fehlt.
PublishIntent / Claim bleiben in web.publish — hier wird nur geprüft.
"""
from __future__ import annotations

from typing import Any


def _issue(
    field: str,
    code: str,
    message: str,
    *,
    section: str = "",
    type: str = "missing",
    severity: str = "error",
    blocking: bool = True,
    source: str = "preflight",
) -> dict[str, str | bool]:
    out: dict[str, str | bool] = {
        "field": field,
        "field_id": field,
        "code": code,
        "message": message,
        "type": type,
        "severity": severity,
        "blocking": blocking,
        "source": source,
    }
    if section:
        out["section"] = section
    return out


_SECTION = {
    "photos": "photos",
    "title": "product",
    "description": "product",
    "category_id": "product",
    "condition": "product",
    "grading": "product",
    "question": "product",
    "status": "product",
    "item_status": "product",
    "identity": "product",
    "price": "offer",
    "format": "offer",
    "quantity": "offer",
    "best_offer": "offer",
    "auction_days": "offer",
    "shipping": "shipping",
    "payment": "shipping",
    "return": "shipping",
    "ebay": "shipping",
    "plan": "shipping",
    "draft": "product",
}


def _sec(field: str) -> str:
    if field.startswith("aspect:"):
        return "product"
    return _SECTION.get(field, "product")


def preflight_draft(
    draft: dict[str, Any] | None,
    *,
    policies: dict[str, Any] | None = None,
    ebay_connected: bool = True,
    account: dict[str, Any] | None = None,
    plan_ok: bool = True,
    item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Idempotente Validierung vor dem echten Publish.

    Keine Seiteneffekte, keine Netzwerkcalls. Geeignet für GET und als Gate
    vor claim_or_create_intent. `valid` entspricht DRAFT_VALID.
    """
    issues: list[dict[str, Any]] = []
    if not draft:
        return {"valid": False, "issues": [
            _issue("draft", "MISSING", "Entwurf fehlt", section="product")]}

    status = (draft.get("status") or "").strip()
    if status in ("published", "ended"):
        issues.append(_issue(
            "status", "TERMINAL", "Bereits veröffentlicht oder beendet",
            section=_sec("status")))
    if status == "publishing":
        issues.append(_issue(
            "status", "BUSY", "Upload läuft gerade", section=_sec("status")))
    if status == "publish_uncertain":
        issues.append(_issue(
            "status", "UNCERTAIN",
            "Publish-Stand unklar — bitte prüfen, bevor du erneut tippst",
            section=_sec("status")))
    if status in ("analyzing", "downloading", "waiting"):
        issues.append(_issue(
            "status", "ANALYZING", "Analyse läuft noch", section=_sec("status")))
    if status == "error" and not (draft.get("question") or draft.get("pending_frage")):
        issues.append(_issue(
            "status", "REVIEW",
            "Die Erstellung ist fehlgeschlagen.",
            type="invalid", severity="error", blocking=True,
            section=_sec("status")))
    if draft.get("app_pending") in ("graded", "graded_update"):
        issues.append(_issue(
            "grading", "MISSING",
            "Grading-Angaben fehlen (Bewerter, Note, Zertifikat)",
            section=_sec("grading")))
    if draft.get("question") or draft.get("pending_frage"):
        issues.append(_issue(
            "question", "OPEN", "Offene Rückfrage zuerst beantworten",
            section=_sec("question")))

    # KI-Unsicherheit und interne Identität sind kein Publish-Blocker.
    # Echtes eBay-Pflichtfeld bleibt hart (Preis, Titel, Bilder, Kategorie).
    if item:
        ist = (item.get("status") or "").strip()
        if ist in ("analyzing", "downloading", "waiting"):
            issues.append(_issue(
                "item_status", "ANALYZING",
                "Stück-Analyse läuft noch",
                type="loading", severity="info", blocking=True,
                section=_sec("item_status")))

    listing = draft.get("listing") or {}
    title = (listing.get("title") or draft.get("title") or "").strip()
    if not title:
        issues.append(_issue("title", "MISSING", "Titel fehlt", section=_sec("title")))
    elif len(title) > 80:
        issues.append(_issue(
            "title", "TOO_LONG",
            f"Titel max. 80 Zeichen (aktuell {len(title)})",
            section=_sec("title")))

    desc = (listing.get("description_html") or listing.get("description_plain")
            or draft.get("description_plain") or "").strip()
    if not desc:
        issues.append(_issue(
            "description", "MISSING", "Beschreibung fehlt",
            section=_sec("description")))

    photos = draft.get("photos") or []
    image_urls = draft.get("image_urls") or []
    if not photos and not image_urls:
        issues.append(_issue(
            "photos", "MISSING", "Mindestens ein Bild nötig",
            section=_sec("photos")))

    cat = draft.get("category_id")
    if not cat:
        issues.append(_issue(
            "category_id", "MISSING", "eBay-Kategorie wählen",
            section=_sec("category_id")))

    price = draft.get("price")
    try:
        price_f = float(str(price).replace(",", ".")) if price not in (None, "") else 0.0
    except (TypeError, ValueError):
        price_f = 0.0
    if price_f <= 0:
        issues.append(_issue(
            "price", "MISSING", "Preis festlegen",
            type="missing", severity="error", blocking=True,
            section=_sec("price")))

    fmt = (draft.get("format") or "FIXED_PRICE").upper()
    qty = int(draft.get("quantity") or 1)
    bo = draft.get("best_offer")
    best_offer = bool(isinstance(bo, dict) and bo.get("enabled"))
    price_mode = (draft.get("price_mode") or "").strip()

    if fmt == "FIXED_PRICE" and price_mode == "auction1":
        issues.append(_issue(
            "format", "INCOMPATIBLE",
            "Sofortkauf und 1-€-Auktionsstart passen nicht zusammen",
            section=_sec("format")))
    if fmt == "AUCTION" and qty > 1:
        issues.append(_issue(
            "quantity", "INCOMPATIBLE", "Auktion immer mit Stückzahl 1",
            section=_sec("quantity")))
    if fmt == "AUCTION" and best_offer:
        issues.append(_issue(
            "best_offer", "INCOMPATIBLE", "Preisvorschlag nur bei Sofortkauf",
            section=_sec("best_offer")))
    if fmt == "AUCTION":
        days = int(draft.get("auction_days") or 0)
        if days not in (1, 3, 5, 7, 10):
            issues.append(_issue(
                "auction_days", "INVALID", "Auktionsdauer 1/3/5/7/10 Tage",
                section=_sec("auction_days")))

    cond = (listing.get("condition") or "").strip()
    if not cond:
        issues.append(_issue(
            "condition", "MISSING", "Zustand festlegen",
            section=_sec("condition")))

    # Pflichtmerkmale (lokal / Cache — kein Netz)
    aspects = listing.get("aspects") or {}
    required = draft.get("required_aspects") or []
    for name in required:
        vals = aspects.get(name)
        if isinstance(vals, list):
            ok = any(str(v).strip() for v in vals)
        else:
            ok = bool(str(vals or "").strip())
        if not ok:
            issues.append(_issue(
                f"aspect:{name}", "MISSING",
                f"Pflichtmerkmal fehlt: {name}",
                section="product"))

    if not ebay_connected:
        issues.append(_issue(
            "ebay", "DISCONNECTED", "eBay-Konto verbinden",
            section=_sec("ebay")))

    pol = policies or {}
    if ebay_connected:
        has_ship = bool(
            pol.get("fulfillment_policy_id") or pol.get("shipping_policy_id")
            or pol.get("fulfillment") or pol.get("shipping"))
        has_pay = bool(pol.get("payment_policy_id") or pol.get("payment"))
        has_ret = bool(pol.get("return_policy_id") or pol.get("return"))
        if not has_ship:
            issues.append(_issue(
                "shipping", "MISSING",
                "Versandrichtlinie fehlt — Setup im Profil abschließen",
                section=_sec("shipping")))
        if not has_pay:
            issues.append(_issue(
                "payment", "MISSING",
                "Zahlungsrichtlinie fehlt — Setup im Profil abschließen",
                section=_sec("payment")))
        if not has_ret:
            issues.append(_issue(
                "return", "MISSING",
                "Rücknahmerichtlinie fehlt — Setup im Profil abschließen",
                section=_sec("return")))

    if not plan_ok:
        issues.append(_issue(
            "plan", "LIMIT", "Tarif oder Monatslimit prüfen",
            section=_sec("plan")))

    _ = account
    for iss in issues:
        iss.setdefault("section", _sec(str(iss.get("field") or "")))
        iss.setdefault("field_id", iss.get("field") or "")
        iss.setdefault("type", "invalid")
        iss.setdefault("severity", "error")
        iss.setdefault("blocking", True)
        iss.setdefault("source", "preflight")
    blocking = [i for i in issues if i.get("blocking")]
    from bot.ebay.payload import review_fields, listing_photos_in_order
    photos = listing_photos_in_order(draft.get("photos") or draft.get("image_urls"))
    review = review_fields(draft, photo_count=len(photos), policies=policies)
    return {"valid": not blocking, "issues": issues, "review": review}
