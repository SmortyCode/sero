"""Metadata API: erlaubte Zustände (Conditions) pro Kategorie.

Manche Kategorien erlauben nicht alle Zustände — z.B. Sammelkarten (183454):
dort gibt es nur Graded (2750) und Ungraded (4000), 'NEW' (1000) ist ungültig
(eBay-Fehler 25059). Wir fragen die Condition-Policies ab (gecacht) und mappen
den gewünschten Zustand auf den nächstpassenden erlaubten.
"""

from __future__ import annotations

import logging
import re

from bot.config import EBAY_API
from bot.drafts import Store
from bot.ebay.auth import EbayClient

log = logging.getLogger("ebay.metadata")

CONDITION_ID_TO_ENUM = {
    "1000": "NEW",
    "1500": "NEW_OTHER",
    "1750": "NEW_WITH_DEFECTS",
    "2750": "LIKE_NEW",            # in Karten-Kategorien: "Graded"
    "3000": "USED_EXCELLENT",
    "4000": "USED_VERY_GOOD",      # in Karten-Kategorien: "Ungraded"
    "5000": "USED_GOOD",
    "6000": "USED_ACCEPTABLE",
    "7000": "FOR_PARTS_OR_NOT_WORKING",
}
ENUM_TO_CONDITION_ID = {v: k for k, v in CONDITION_ID_TO_ENUM.items()}

GRADED_MARKERS = re.compile(r"\b(graded|psa|bgs|cgc|sgc|gma|aci)\b", re.IGNORECASE)

# Bewerter + optionale Note aus Freitext ziehen, z.B. "PSA 9.5" oder "BGS 10"
GRADER_REGEX = re.compile(
    r"\b(PSA|BGS|CGC|SGC|BCCG|BVG|KSA|GMA|HGA|ISA|PCA|GSG|PGS|MNT|TAG|RCG|PCG|ACE|CGA|ARK|AGS)\b"
    r"[\s:]*(\d{1,2}(?:[.,]5)?)?",
    re.IGNORECASE,
)

GRADED_QUESTION = (
    "❓ Graded-Karte: Mir fehlen Angaben für die eBay-Pflichtfelder.\n"
    "Antworte mit:  Bewerter Note Zertifikatsnummer\n"
    "z.B.:  PSA 9.5 12345678\n"
    "Danach ✅ Hochladen erneut drücken."
)

CERT_QUESTION = (
    "❓ Graded-Karte: Mir fehlt die Zertifikatsnummer (steht auf dem Slab-Label, "
    "eBay verlangt sie zwingend).\n"
    "Antworte einfach mit der Nummer, z.B.:  12345678\n"
    "Danach ✅ Hochladen erneut drücken."
)


def has_real_graded_info(info: dict | None) -> bool:
    """Echte Graded-Angaben: Bewerter UND Note. Leere Dicts/Nullen zählen nicht.

    Sonst landet eine Rohkarte fälschlich bei Zustand Graded (LIKE_NEW) und
    eBay verlangt Zertifikat — obwohl nie ein Slab da war."""
    if not info or not isinstance(info, dict):
        return False
    grader = str(info.get("grader") or "").strip()
    grade = str(info.get("grade") or "").strip()
    return bool(grader and grade)


async def get_condition_policy(client: EbayClient, store: Store, category_id: str) -> list[dict]:
    """Vollständige Condition-Policy einer Kategorie (Conditions + Descriptors), gecacht."""
    cache_key = f"condition_policy_{category_id}"
    cached = store.kv_get(cache_key)
    if cached is not None:
        return cached
    resp = await client.request(
        "GET", f"{EBAY_API}/sell/metadata/v1/marketplace/EBAY_DE/get_item_condition_policies",
        auth="app", params={"filter": f"categoryIds:{{{category_id}}}"},
    )
    if resp.status_code != 200:
        log.warning("Condition-Policies nicht abrufbar (%s): %s — keine Anpassung",
                    resp.status_code, resp.text[:200])
        return []
    conditions: list[dict] = []
    for policy in resp.json().get("itemConditionPolicies", []):
        if str(policy.get("categoryId")) == str(category_id):
            conditions = policy.get("itemConditions", [])
            break
    store.kv_set(cache_key, conditions)
    return conditions




def _norm_grade(grade) -> str:
    g = str(grade).replace(",", ".").strip()
    return g[:-2] if g.endswith(".0") else g


def _match_value_by_token(values: list[dict], token: str) -> dict | None:
    t = token.upper().strip()
    return next((v for v in values if t and t in v["conditionDescriptorValueName"].upper()), None)


def _match_card_condition(values: list[dict], listing: dict, item_text: str) -> dict | None:
    """40001 'Kartenzustand' für Ungraded: aus Zustandsbeschreibung ableiten, Default Near Mint."""
    text = f"{listing.get('condition_description') or ''} {item_text or ''}".lower()
    for keyword, value_token in (("stark bespielt", "Stark bespielt"), ("poor", "Stark bespielt"),
                                 ("leicht bespielt", "Leicht bespielt"), ("excellent", "Leicht bespielt"),
                                 ("sehr gut", "Sehr gut"), ("very good", "Sehr gut")):
        if keyword in text:
            match = next((v for v in values
                          if value_token.lower() in v["conditionDescriptorValueName"].lower()), None)
            if match:
                return match
    return next((v for v in values
                 if "neuwertig" in v["conditionDescriptorValueName"].lower()
                 or "near mint" in v["conditionDescriptorValueName"].lower()),
                values[0] if values else None)


def build_condition_descriptors(condition_enum: str, conditions: list[dict],
                                listing: dict, item_text: str) -> tuple[list[dict] | None, str | None]:
    """(conditionDescriptors fürs Inventory Item, Rückfrage an den Nutzer).

    Liefert (None, Frage) wenn Pflichtangaben (Bewerter/Note bei Graded) fehlen.
    """
    cond_id = ENUM_TO_CONDITION_ID.get(condition_enum)
    cond = next((c for c in conditions if str(c.get("conditionId")) == cond_id), None)
    if not cond or not cond.get("conditionDescriptors"):
        return None, None

    info = listing.get("graded_info") or {}
    grader, grade, cert = info.get("grader"), info.get("grade"), info.get("cert_number")
    m = GRADER_REGEX.search(item_text or "")
    if m:
        grader = grader or m.group(1)
        grade = grade or m.group(2)

    out: list[dict] = []
    for d in cond["conditionDescriptors"]:
        did = str(d["conditionDescriptorId"])
        constraint = d.get("conditionDescriptorConstraint") or {}
        required = constraint.get("usage") == "REQUIRED"
        values = d.get("conditionDescriptorValues") or []

        if constraint.get("mode") == "FREE_TEXT":
            if did == "27503":  # Zertifikationsnummer — laut Metadata optional, faktisch Pflicht (Fehler 25066)
                if not cert:
                    return None, CERT_QUESTION
                # Freitext MUSS in additionalInfo — 'values' speichert eBay zwar,
                # aber publishOffer ignoriert es und wirft 25066 (live verifiziert 11.06.2026).
                out.append({"name": did, "additionalInfo": str(cert)})
            continue

        picked = None
        if did == "27501" and grader:  # Bewertungsexperte
            picked = _match_value_by_token(values, str(grader)) or _match_value_by_token(values, "Sonstige")
        elif did == "27502" and grade:  # Bewertung (Note)
            ng = _norm_grade(grade)
            picked = next((v for v in values if v["conditionDescriptorValueName"].strip() == ng), None)
        elif did == "40001":  # Kartenzustand (Ungraded)
            picked = _match_card_condition(values, listing, item_text)

        if not picked and required:
            if did in ("27501", "27502"):
                return None, GRADED_QUESTION
            default_id = constraint.get("defaultConditionDescriptorValueId")
            picked = next((v for v in values if v["conditionDescriptorValueId"] == default_id),
                          values[0] if values else None)
        if picked:
            out.append({"name": did, "values": [picked["conditionDescriptorValueId"]]})
    return (out or None), None


def resolve_condition(intended_enum: str, allowed_ids: list[str], item_text: str,
                      is_graded: bool = False) -> tuple[str, bool]:
    """(gültiger Condition-Enum, wurde_angepasst).

    Karten-Kategorien (Graded/Ungraded): graded nur, wenn echte graded_info
    (Bewerter+Note) vorliegt ODER Graded-Marker im Verkäufertext stehen —
    lose Karten sind ungraded. Sonst: numerisch nächstgelegener erlaubter Zustand.
    """
    intended_id = ENUM_TO_CONDITION_ID.get(intended_enum, "3000")

    if "2750" in allowed_ids and "4000" in allowed_ids:
        # Karten-Kategorie: die Metadata-API listet teils weitere Zustände (z.B. 3000),
        # die publishOffer dann trotzdem mit 25059 ablehnt — real gültig sind NUR
        # Graded (2750) und Ungraded (4000). Live beobachtet am 11.06.2026.
        graded = bool(is_graded) or bool(GRADED_MARKERS.search(item_text or ""))
        pick = "2750" if graded else "4000"
        if intended_id == pick:
            return intended_enum, False
        return CONDITION_ID_TO_ENUM[pick], intended_id != pick

    if not allowed_ids or intended_id in allowed_ids:
        return intended_enum, False

    known = [c for c in allowed_ids if c in CONDITION_ID_TO_ENUM]
    if not known:
        return intended_enum, False  # nichts Mappbares — Original behalten, eBay meldet dann konkret
    pick = min(known, key=lambda c: abs(int(c) - int(intended_id)))
    return CONDITION_ID_TO_ENUM[pick], True


def ensure_card_condition(listing: dict, allowed_ids: list[str], item_text: str) -> str:
    """Karten: Zustand setzen. Graded nur mit echten Angaben oder klarem Marker.

    Verhindert, dass Rohkarten wegen leerem graded_info oder UI-Label
    „Neuwertig“ (= LIKE_NEW) in die Graded-Pflichtfelder rutschen."""
    info = listing.get("graded_info")
    real = has_real_graded_info(info)
    if not real:
        listing.pop("graded_info", None)
    intended = normalize_condition_input(listing.get("condition") or "USED_VERY_GOOD")
    condition, _ = resolve_condition(
        intended, allowed_ids, item_text, is_graded=real)
    # LIKE_NEW ohne Slab-Daten und ohne PSA/CGC-Marker → Ungraded
    if (condition == "LIKE_NEW" and not real
            and not GRADED_MARKERS.search(item_text or "")):
        condition = "USED_VERY_GOOD"
    listing["condition"] = condition
    return condition


_LABEL_TO_ENUM = {
    "neu": "NEW",
    "neuwertig": "LIKE_NEW",
    "professionell bewertet (graded)": "LIKE_NEW",
    "graded": "LIKE_NEW",
    "nicht bewertet (ungraded)": "USED_VERY_GOOD",
    "ungraded": "USED_VERY_GOOD",
    "gebraucht — sehr gut": "USED_VERY_GOOD",
    "gebraucht — gut": "USED_GOOD",
    "gebraucht — exzellent": "USED_EXCELLENT",
    "gebraucht — akzeptabel": "USED_ACCEPTABLE",
}


def normalize_condition_input(value: str) -> str:
    """UI-Freitext oder Enum → bekannter Condition-Enum."""
    v = (value or "").strip()
    if not v:
        return "USED_VERY_GOOD"
    if v in CONDITION_ID_TO_ENUM.values():
        return v
    if v in ENUM_TO_CONDITION_ID:
        return CONDITION_ID_TO_ENUM[v]
    return _LABEL_TO_ENUM.get(v.lower(), v)
