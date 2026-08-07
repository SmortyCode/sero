"""Sell Inventory API: InventoryItem -> Offer -> Publish.

PFLICHT auf EBAY_DE: Content-Language: de-DE (sonst kryptische Fehler wie 25709).
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
import string
from datetime import datetime
from typing import Optional

from bot.config import EBAY_API
from bot.ebay.auth import EbayClient, EbayTimeout

# Policies-Dict pro Nutzer (Multi-Tenant): merchant_location_key,
# fulfillment_policy_id, payment_policy_id, return_policy_id

log = logging.getLogger("ebay.inventory")

DE_HEADERS = {
    "Content-Language": "de-DE",
    "Accept-Language": "de-DE",
    "Content-Type": "application/json",
}

# Bekannte Fehlercodes menschenlesbar übersetzen.
# ACHTUNG: 25002 ist ein SAMMELCODE ("user error") — der Hint wird nur gezeigt,
# wenn die Message zum jeweiligen Fall passt (siehe translate_ebay_error).
ERROR_HINTS = {
    25002: "merchantLocationKey fehlt oder die Inventory-Location existiert nicht — `python setup_location.py` ausführen.",
    25007: "Die Fulfillment Policy hat keinen gültigen Versandservice — Versandrichtlinie in 'Mein eBay > Verkaufsrichtlinien' prüfen.",
    25709: "Ungültiges Feld oder fehlender Content-Language-Header (sollte de-DE sein).",
    25001: "Systemfehler bei eBay — später erneut versuchen.",
    25604: "Pflicht-Item-Specifics der Kategorie fehlen (Aspects) — Kategorie-Pflichtfelder prüfen.",
    25059: "Der Zustand ist für diese Kategorie nicht erlaubt (z.B. Einzelkarten: nur Graded/Ungraded) — der Bot passt das beim nächsten ✅ automatisch an.",
    25019: "Das Angebot wurde von eBay abgelehnt (Grundsätze/Bezeichnung) — Titel/Beschreibung prüfen.",
}

# eBays Jugendschutz-Sperre für USK-18-Spiele braucht eine eigene, klare Meldung
USK_MESSAGE = (
    "🔞 eBay stuft diesen Artikel als jugendgefährdendes Spiel (USK 18 / indiziert) ein.\n"
    "Solche Artikel dürfen nur mit Versand MIT Altersprüfung verkauft werden — die hast "
    "du in deinen eBay-Versandrichtlinien noch nicht hinterlegt.\n\n"
    "So löst du es:\n"
    "• Ist das Spiel NICHT ab 18: ✏️ Titel bearbeiten und Begriffe wie „ab 18“, „USK 18“, "
    "„indiziert“ entfernen, dann erneut ✅.\n"
    "• Ist es WIRKLICH ab 18: Lege auf eBay einmalig die Versandrichtlinie „DHL Paket mit "
    "Alterssichtprüfung ab 18 Jahre“ an (Mein eBay → Verkaufsrichtlinien → Versand). "
    "Danach kann ich sie für 18+-Artikel nutzen — sag mir Bescheid.\n"
    "• Sonst einfach ❌ Verwerfen."
)


def _usable_param(value) -> Optional[str]:
    """Kurze, saubere Parameterwerte für die Fehlerausgabe — HTML-Blobs raus."""
    if not value:
        return None
    text = str(value)
    if "<" in text or len(text) > 120:
        return None
    return text


class InventoryError(Exception):
    def __init__(self, message: str, raw: Optional[str] = None):
        super().__init__(message)
        self.raw = raw


def norm_price(value, feld: str = "Preis") -> str:
    """Preis für eBay normalisieren — oder klar scheitern.
    Bisher wurde nur Komma durch Punkt ersetzt: aus None wurde der String
    "None", aus Müll wurde Müll, und eBay antwortete mit kryptischen Codes,
    lange nachdem der eigentliche Fehler passiert war."""
    from decimal import Decimal, InvalidOperation
    s = str(value or "").replace("€", "").replace("\u00a0", "").strip()
    s = s.replace(" ", "")
    if "," in s and "." in s:
        dez = max(s.rfind(","), s.rfind("."))
        s = s[:dez].replace(",", "").replace(".", "") + "." + s[dez + 1:]
    else:
        s = s.replace(",", ".")
    try:
        d = Decimal(s)
    except InvalidOperation:
        raise InventoryError(f"{feld} ist keine gültige Zahl: {value!r}") from None
    if not d.is_finite():
        # Decimal("nan") und Decimal("inf") parsen KLAGLOS — und der
        # Bereichsvergleich mit NaN würde selbst eine InvalidOperation werfen.
        raise InventoryError(f"{feld} ist keine gültige Zahl: {value!r}")
    if not (Decimal("0.01") <= d <= Decimal("1000000")):
        raise InventoryError(f"{feld} liegt außerhalb des erlaubten Bereichs: {value!r}")
    return f"{d:.2f}"


def kurz_titel(title: str, max_len: int = 80) -> str:
    """eBay kappt Titel hart bei 80 Zeichen — wir kappen an der Wortgrenze,
    damit nicht mitten im Kartennamen abgeschnitten wird."""
    t = (title or "").strip()
    if len(t) <= max_len:
        return t
    schnitt = t.rfind(" ", 0, max_len)
    return t[:schnitt] if schnitt > max_len // 2 else t[:max_len]


def generate_sku() -> str:
    """Interner Inventar-Schlüssel. eBay zeigt ihn dem Verkäufer als
    „Bestandseinheit" an — deshalb bewusst NEUTRAL: vorher stand dort
    „SERO-20260803-MQ56" und verriet Werkzeug und Einstelldatum.
    Ganz weglassen geht nicht, die Inventar-Schnittstelle verlangt ihn."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=10))


# eBay-Limits: Aspect-Wert max. 65 Zeichen, sonst lehnt publishOffer ab;
# konservativ zusätzlich max. 10 Werte pro Aspect, leere Werte raus.
MAX_ASPECT_VALUE_LEN = 65
MAX_ASPECT_VALUES = 10
MAX_IMAGES = 24


# Jedes Merkmal, das nach Altersangabe aussieht — die Analyse erfindet hier
# immer wieder neue Namen („USK", „USK-Einstufung", „Altersfreigabe", …).
# Erkennung deshalb per Muster statt per fester Liste.
_USK_FELD_RE = re.compile(r"^(usk|fsk|altersfreigabe|altersempfehlung|altersbeschr)", re.I)
_USK_OK = re.compile(r"^USK\s*ab\s*(0|6|12|16|18)\s*Jahren?$", re.I)
_USK_ZAHL = re.compile(r"USK\s*ab\s*(\d{1,2})", re.I)


def bereinige_altersfreigabe(aspects: dict) -> dict:
    """In ein deutsches USK-Feld gehört NUR eine deutsche USK-Einstufung.

    Der Analyse-Prompt bittet um die USK-Stufe vom Cover. Bei US-Importen ohne
    USK-Logo antwortete die KI sinnvollerweise mit dem, was dort steht — etwa
    „ESRB Mature 17+". Für eBay ist das ein Erwachsenen-Signal: Das Listing lief
    in die Jugendschutz-Sperre, obwohl das Spiel gar nicht ab 18 ist. Von Hand
    eingestellt ging dasselbe Spiel durch, weil dort niemand das Feld füllt.

    Regel: gültige USK-Werte auf eBays Schreibweise normalisieren, alles andere
    (ESRB, PEGI, CERO, „Mature", „ab 18") ersatzlos streichen. Lieber kein
    Merkmal als ein falsches — die Stufe lässt sich in der App jederzeit setzen.
    """
    out = dict(aspects or {})
    for feld in list(out.keys()):
        if not _USK_FELD_RE.match(str(feld).strip()):
            continue
        werte = out[feld] if isinstance(out[feld], list) else [out[feld]]
        behalten = []
        for w in werte:
            s = str(w).strip()
            if _USK_OK.match(s):
                behalten.append(s)
                continue
            treffer = _USK_ZAHL.search(s)      # „USK ab 12 freigegeben" o. Ä.
            if treffer and int(treffer.group(1)) in (0, 6, 12, 16, 18):
                behalten.append(f"USK ab {int(treffer.group(1))} Jahren")
        out.pop(feld)
        if behalten:
            # Immer unter dem Namen ablegen, den eBay in der Spiele-Kategorie führt
            out["USK-Einstufung"] = behalten[:1]
    return out


def sanitize_aspects(aspects: dict) -> dict:
    clean: dict = {}
    for name, values in bereinige_altersfreigabe(aspects).items():
        if not name:
            continue
        if not isinstance(values, list):
            values = [values]
        vals = [str(v).strip()[:MAX_ASPECT_VALUE_LEN] for v in values if v and str(v).strip()]
        if vals:
            clean[str(name).strip()[:65]] = vals[:MAX_ASPECT_VALUES]
    return clean


def translate_ebay_error(resp_text: str, status_code: int) -> str:
    """eBay-Fehlerantwort in eine verständliche Meldung übersetzen."""
    lines: list[str] = []
    try:
        body = json.loads(resp_text)
        for err in body.get("errors", []):
            code = err.get("errorId")
            msg = err.get("message", "")
            params = err.get("parameters") or []
            param_blob = " ".join(str(p.get("value", "")) for p in params)
            # Jugendschutz-Sperre (USK 18): eigene, verständliche Meldung statt HTML-Wust
            if code == 25019 and ("USK" in param_blob or "ab 18" in param_blob
                                  or "jugendgef" in param_blob.lower()):
                lines.append(USK_MESSAGE)
                continue
            hint = ERROR_HINTS.get(code)
            if code == 25002:
                # Sammelcode: Hint nur, wenn er wirklich passt
                low = msg.lower()
                if "nur einen wert" in low or "only one value" in low:
                    hint = ("Das Merkmal erlaubt nur einen Wert — einfach ✅ erneut "
                            "drücken, ich kürze es automatisch.")
                elif "location" not in low and "merchant" not in low:
                    hint = None  # generischer user error: Message spricht für sich
            if not hint and "aspect" in msg.lower():
                hint = ERROR_HINTS[25604]
            line = f"eBay-Fehler {code}: {msg}"
            if hint:
                line += f"\n→ {hint}"
            else:
                # nur bei UNbekanntem Fehler kurze, saubere Parameter zeigen (keine HTML-Blobs)
                clean = [f"{p.get('name')}={_usable_param(p.get('value'))}"
                         for p in params if _usable_param(p.get("value"))]
                if clean:
                    line += "\n   (" + ", ".join(clean) + ")"
            lines.append(line)
    except (json.JSONDecodeError, AttributeError):
        pass
    if not lines:
        lines.append(f"eBay-Fehler (HTTP {status_code}): {resp_text[:400]}")
    return "\n".join(lines)


async def create_inventory_item(
    client: EbayClient,
    sku: str,
    *,
    user_id: int,
    title: str,
    description: str,
    condition: str,
    condition_description: Optional[str],
    aspects: dict,
    image_urls: list[str],
    condition_descriptors: Optional[list[dict]] = None,
    quantity: int = 1,
) -> None:
    if not image_urls:
        # eBay lehnt bildlose Listings ohnehin ab — nur eben erst ganz am Ende
        # der Kette und mit einer Meldung, die niemandem weiterhilft.
        raise InventoryError("eBay verlangt mindestens ein Foto — bitte ein Bild hinzufügen.")
    payload = {
        "condition": condition,
        "product": {
            "title": kurz_titel(title),
            "description": description,
            "aspects": sanitize_aspects(aspects),
            "imageUrls": image_urls[:MAX_IMAGES],
        },
        "availability": {"shipToLocationAvailability": {"quantity": max(1, quantity)}},
    }
    if condition_description and condition != "NEW":
        payload["conditionDescription"] = condition_description[:1000]
    if condition_descriptors:
        payload["conditionDescriptors"] = condition_descriptors

    resp = await client.request(
        "PUT", f"{EBAY_API}/sell/inventory/v1/inventory_item/{sku}",
        auth="user", user_id=user_id, headers=DE_HEADERS, json_body=payload,
    )
    if resp.status_code not in (200, 201, 204):
        raise InventoryError(translate_ebay_error(resp.text, resp.status_code), raw=resp.text)
    log.info("InventoryItem %s angelegt", sku)


async def get_inventory_item(client: EbayClient, sku: str, user_id: int) -> Optional[dict]:
    """Aktuelles InventoryItem holen (Titel, Aspects, Zustand, Bilder) — für Bearbeitung."""
    resp = await client.request(
        "GET", f"{EBAY_API}/sell/inventory/v1/inventory_item/{sku}",
        auth="user", user_id=user_id, headers=DE_HEADERS,
    )
    if resp.status_code != 200:
        return None
    return resp.json()


# Erlaubte Auktionsdauern (eBay-Enum). Default 7 Tage.
AUCTION_DURATIONS = {1: "DAYS_1", 3: "DAYS_3", 5: "DAYS_5", 7: "DAYS_7", 10: "DAYS_10"}
DEFAULT_AUCTION_DAYS = 7


# eBay behandelt manche Serien TITELBASIERT als USK 18 — gemessen 04.08.:
# GTA-Listings ohne jede Altersangabe im Payload landeten trotzdem in der
# Jugendschutz-Sperre (für anonyme Käufer unsichtbar, Versandoptionen im
# Verkäufer-UI gesperrt). Solche Titel bekommen automatisch die
# 18+-Versandrichtlinie mit DHL-Alterssichtprüfung.
AGE18_TITEL = re.compile(r"grand theft auto|\bgta\b|manhunt|postal\s*2", re.I)


def policies_fuer_titel(policies: dict, title: str | None) -> dict:
    """Standard-Policies — oder die 18+-Variante, wenn der Titel in eBays
    Jugendschutz-Raster fällt und EBAY_FULFILLMENT_POLICY_18_ID gesetzt ist."""
    p18 = os.environ.get("EBAY_FULFILLMENT_POLICY_18_ID", "").strip()
    if p18 and title and AGE18_TITEL.search(title):
        neu = dict(policies or {})
        neu["fulfillment_policy_id"] = p18
        log.info("18+-Titel erkannt (%r) — Versandrichtlinie mit Alterssichtprüfung", title[:40])
        return neu
    return policies


def build_offer_payload(policies: dict, sku: str, *, category_id: str, price_eur: str,
                        listing_description: str, listing_format: str = "FIXED_PRICE",
                        quantity: int = 1, best_offer: Optional[dict] = None,
                        auction_days: int = DEFAULT_AUCTION_DAYS) -> dict:
    # Letzte Verteidigungslinie vor eBay: alles, was hier durchrutscht, wird
    # zu einem Live-Fehler mit kryptischem Code — oder schlimmer, zu einem
    # Listing mit Preis "None".
    if not category_id:
        raise InventoryError("Keine eBay-Kategorie bestimmt — bitte das Listing neu erstellen.")
    fehlend = [k for k in ("merchant_location_key", "fulfillment_policy_id",
                           "payment_policy_id", "return_policy_id")
               if not (policies or {}).get(k)]
    if fehlend:
        raise InventoryError("Dein eBay-Setup ist unvollständig (Versand-/Zahlungs-/"
                             "Rücknahmerichtlinie oder Standort fehlt) — bitte einmal "
                             "neu einrichten.")
    price_eur = norm_price(price_eur)
    payload = {
        "sku": sku,
        "marketplaceId": "EBAY_DE",
        "format": listing_format,
        "categoryId": category_id,
        "listingDescription": listing_description,
        "merchantLocationKey": policies["merchant_location_key"],
        "listingPolicies": {
            "fulfillmentPolicyId": policies["fulfillment_policy_id"],
            "paymentPolicyId": policies["payment_policy_id"],
            "returnPolicyId": policies["return_policy_id"],
        },
    }
    if listing_format == "AUCTION":
        # eBay-Fehler 25762: availableQuantity ist bei Auktionen nicht erlaubt
        payload["listingDuration"] = AUCTION_DURATIONS.get(auction_days, "DAYS_7")
        payload["pricingSummary"] = {"auctionStartPrice": {"value": price_eur, "currency": "EUR"}}
    else:
        if int(quantity) < 1:
            raise InventoryError(f"Stückzahl muss mindestens 1 sein (war: {quantity}).")
        payload["availableQuantity"] = int(quantity)
        payload["pricingSummary"] = {"price": {"value": price_eur, "currency": "EUR"}}
        # Preisvorschlag (Best Offer) — nur bei Festpreis möglich
        if best_offer and best_offer.get("enabled"):
            terms: dict = {"bestOfferEnabled": True}
            if best_offer.get("min_price"):
                mp = norm_price(best_offer["min_price"], "Mindestpreis")
                if float(mp) >= float(price_eur):
                    raise InventoryError(f"Der Mindestpreis ({mp} €) muss unter dem "
                                         f"Angebotspreis ({price_eur} €) liegen.")
                terms["autoDeclinePrice"] = {"value": mp, "currency": "EUR"}
            payload["listingPolicies"]["bestOfferTerms"] = terms
    return payload


async def find_offer_for_sku(client: EbayClient, sku: str, user_id: int) -> Optional[dict]:
    """Gibt es zu dieser SKU schon ein Offer? Wird gebraucht, wenn eBay auf einen
    Anlage-Versuch nicht geantwortet hat: nachsehen ist sicher, ein zweiter POST
    würde ein zweites Angebot erzeugen."""
    resp = await client.request(
        "GET", f"{EBAY_API}/sell/inventory/v1/offer",
        auth="user", user_id=user_id, headers=DE_HEADERS,
        params={"sku": sku, "limit": 10},
    )
    if resp.status_code != 200:
        return None
    offers = resp.json().get("offers") or []
    return offers[0] if offers else None


async def get_offer(client: EbayClient, offer_id: str, user_id: int) -> Optional[dict]:
    """Zustand eines Offers bei eBay — die Wahrheit, wenn unsere Notizen unsicher sind."""
    resp = await client.request(
        "GET", f"{EBAY_API}/sell/inventory/v1/offer/{offer_id}",
        auth="user", user_id=user_id, headers=DE_HEADERS,
    )
    return resp.json() if resp.status_code == 200 else None


def live_price_from_offer(data: dict) -> Optional[str]:
    """Listenpreis aus einer getOffer-Antwort — nur echte eBay-Zahlen, nie geraten."""
    ps = data.get("pricingSummary") or {}
    obj = ps.get("price") or ps.get("auctionStartPrice") or {}
    val = obj.get("value")
    if val is None or val == "":
        return None
    try:
        f = float(str(val).replace(",", "."))
    except (TypeError, ValueError):
        return None
    if f <= 0:
        return None
    return f"{f:.2f}"


def best_offer_enabled_from_offer(data: dict) -> bool:
    terms = ((data.get("listingPolicies") or {}).get("bestOfferTerms") or {})
    return bool(terms.get("bestOfferEnabled"))


async def get_active_buyer_offers(client: EbayClient, user_id: int) -> list[dict] | None:
    """Aktive Käufer-Preisvorschläge (Trading API GetBestOffers).

    Erfolg: Liste (kann leer sein). Fehler/Timeout: None — Aufrufer behält
    den letzten bekannten Stand (Claude-Review B3).
    """
    import xml.etree.ElementTree as ET

    body = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<GetBestOffersRequest xmlns="urn:ebay:apis:eBLBaseComponents">'
        "<BestOfferStatus>Active</BestOfferStatus>"
        "<DetailLevel>ReturnAll</DetailLevel>"
        "</GetBestOffersRequest>"
    )
    try:
        token = await client.get_user_token(user_id)
        resp = await client.request(
            "POST", "https://api.ebay.com/ws/api.dll",
            auth="user", user_id=user_id,
            headers={
                "X-EBAY-API-COMPATIBILITY-LEVEL": "1155",
                "X-EBAY-API-CALL-NAME": "GetBestOffers",
                "X-EBAY-API-SITEID": "77",
                "X-EBAY-API-IAF-TOKEN": token,
                "Content-Type": "text/xml",
            },
            content=body.encode("utf-8"),
        )
    except Exception as e:  # noqa: BLE001
        log.warning("GetBestOffers fehlgeschlagen für %s: %s", user_id, e)
        return None
    if resp.status_code != 200:
        log.warning("GetBestOffers HTTP %s für %s: %s",
                    resp.status_code, user_id, (resp.text or "")[:300])
        return None
    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError:
        log.warning("GetBestOffers: ungültiges XML für %s", user_id)
        return None
    ns = {"e": "urn:ebay:apis:eBLBaseComponents"}
    ack = (root.findtext("e:Ack", default="", namespaces=ns)
           or root.findtext("Ack", default=""))
    if ack not in ("Success", "Warning"):
        err = (root.findtext(".//e:LongMessage", default="", namespaces=ns)
               or root.findtext(".//LongMessage", default="")
               or root.findtext(".//e:ShortMessage", default="", namespaces=ns)
               or "")
        log.warning("GetBestOffers Ack=%s für %s: %s", ack, user_id, err[:200])
        return None
    def _find_first(node, *paths: str):
        for p in paths:
            el = node.find(p, ns) if ":" in p else node.find(p)
            if el is not None:
                return el
        return None

    def _txt(node, *names: str) -> str:
        for n in names:
            v = node.findtext(f"e:{n}", default="", namespaces=ns) or node.findtext(n, default="")
            if v:
                return v.strip()
        return ""

    def _parse_bo(bo, listing_id: str) -> dict | None:
        price_el = _find_first(bo, "e:Price", "Price")
        price = (price_el.text or "").strip() if price_el is not None else ""
        currency = (price_el.attrib.get("currencyID", "") if price_el is not None else "") or "EUR"
        status = _txt(bo, "Status")
        if status and status.upper() not in ("ACTIVE", "PENDING", ""):
            return None
        try:
            eur = float(price.replace(",", ".")) if price else None
        except ValueError:
            return None
        if eur is None:
            return None
        try:
            qty = int(_txt(bo, "Quantity") or "1") or 1
        except ValueError:
            qty = 1
        return {
            "listing_id": listing_id,
            "price": f"{eur:.2f}",
            "currency": currency,
            "quantity": qty,
            "buyer": _txt(bo, "UserID") or None,
            "expires": _txt(bo, "ExpirationTime") or None,
            "status": status or "Active",
            "best_offer_id": _txt(bo, "BestOfferID") or None,
        }

    out: list[dict] = []
    blocks = root.findall(".//e:ItemBestOffers", ns) or root.findall(".//ItemBestOffers")
    if blocks:
        for block in blocks:
            item_el = _find_first(block, "e:Item", "Item")
            listing_id = _txt(item_el, "ItemID") if item_el is not None else ""
            bos = block.findall(".//e:BestOffer", ns) or block.findall(".//BestOffer")
            for bo in bos:
                row = _parse_bo(bo, listing_id)
                if row:
                    out.append(row)
    else:
        for bo in (root.findall(".//e:BestOffer", ns) or root.findall(".//BestOffer")):
            row = _parse_bo(bo, "")
            if row:
                out.append(row)
    return out


async def create_offer(client: EbayClient, policies: dict, sku: str, *,
                       user_id: int,
                       category_id: str, price_eur: str, listing_description: str,
                       listing_format: str = "FIXED_PRICE", quantity: int = 1,
                       best_offer: Optional[dict] = None,
                       auction_days: int = DEFAULT_AUCTION_DAYS,
                       title: Optional[str] = None) -> str:
    policies = policies_fuer_titel(policies, title)
    payload = build_offer_payload(
        policies, sku, category_id=category_id, price_eur=price_eur,
        listing_description=listing_description, listing_format=listing_format,
        quantity=quantity, best_offer=best_offer, auction_days=auction_days,
    )
    try:
        resp = await client.request(
            "POST", f"{EBAY_API}/sell/inventory/v1/offer",
            auth="user", user_id=user_id, headers=DE_HEADERS, json_body=payload,
        )
    except EbayTimeout:
        # Vielleicht ist das Offer trotzdem entstanden — nachsehen, nicht neu anlegen
        vorhanden = await find_offer_for_sku(client, sku, user_id)
        if vorhanden and vorhanden.get("offerId"):
            log.warning("Offer %s war trotz Zeitüberschreitung angelegt", vorhanden["offerId"])
            return vorhanden["offerId"]
        raise InventoryError(
            "eBay hat auf das Anlegen nicht geantwortet. Das Angebot ist nicht online — "
            "probier es gleich noch einmal.") from None
    if resp.status_code not in (200, 201):
        raise InventoryError(translate_ebay_error(resp.text, resp.status_code), raw=resp.text)
    offer_id = resp.json()["offerId"]
    log.info("Offer %s für SKU %s angelegt", offer_id, sku)
    return offer_id


async def update_offer(client: EbayClient, policies: dict, offer_id: str, sku: str, *,
                       user_id: int,
                       category_id: str, price_eur: str, listing_description: str,
                       listing_format: str = "FIXED_PRICE", quantity: int = 1,
                       best_offer: Optional[dict] = None,
                       auction_days: int = DEFAULT_AUCTION_DAYS,
                       title: Optional[str] = None) -> None:
    """Bestehendes (noch unveröffentlichtes) Offer aktualisieren — z.B. nach Dry-Run
    oder Preisänderung. updateOffer ist ein Full-Replace mit demselben Payload."""
    policies = policies_fuer_titel(policies, title)
    payload = build_offer_payload(
        policies, sku, category_id=category_id, price_eur=price_eur,
        listing_description=listing_description, listing_format=listing_format,
        quantity=quantity, best_offer=best_offer, auction_days=auction_days,
    )
    resp = await client.request(
        "PUT", f"{EBAY_API}/sell/inventory/v1/offer/{offer_id}",
        auth="user", user_id=user_id, headers=DE_HEADERS, json_body=payload,
    )
    if resp.status_code not in (200, 204):
        raise InventoryError(translate_ebay_error(resp.text, resp.status_code), raw=resp.text)
    log.info("Offer %s aktualisiert", offer_id)


async def withdraw_offer(client: EbayClient, offer_id: str, user_id: int) -> None:
    """Veröffentlichtes Listing beenden (vom Markt nehmen). Inventar/Offer bleiben
    bestehen, das eBay-Angebot wird zurückgezogen."""
    resp = await client.request(
        "POST", f"{EBAY_API}/sell/inventory/v1/offer/{offer_id}/withdraw",
        auth="user", user_id=user_id, headers=DE_HEADERS, json_body={},
    )
    if resp.status_code not in (200, 204):
        raise InventoryError(translate_ebay_error(resp.text, resp.status_code), raw=resp.text)
    log.info("Offer %s zurückgezogen (Listing beendet)", offer_id)


async def publish_offer(client: EbayClient, offer_id: str, user_id: int) -> str:
    try:
        resp = await client.request(
            "POST", f"{EBAY_API}/sell/inventory/v1/offer/{offer_id}/publish",
            auth="user", user_id=user_id, headers=DE_HEADERS, json_body={},
        )
    except EbayTimeout:
        # Der gefährlichste Fall: das Listing kann live sein, während bei uns
        # „nicht gelistet" steht. Dann würde der nächste Versuch dieselbe Karte
        # ein zweites Mal einstellen. Also erst bei eBay nachsehen.
        offer = await get_offer(client, offer_id, user_id)
        if offer and offer.get("listing", {}).get("listingId"):
            listing_id = offer["listing"]["listingId"]
            log.warning("Offer %s war trotz Zeitüberschreitung live -> Listing %s",
                        offer_id, listing_id)
            return listing_id
        raise InventoryError(
            "eBay hat beim Veröffentlichen nicht geantwortet. Das Angebot ist nicht "
            "online — probier es gleich noch einmal.") from None
    if resp.status_code not in (200, 201):
        raise InventoryError(translate_ebay_error(resp.text, resp.status_code), raw=resp.text)
    listing_id = resp.json()["listingId"]
    log.info("Offer %s published -> Listing %s", offer_id, listing_id)
    return listing_id
