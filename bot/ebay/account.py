"""Automatisches Verkäufer-Setup pro Nutzer (Multi-Tenant-Onboarding).

Macht für jeden neuen Nutzer das, was beim Erstaufbau manuell nötig war:
Business-Policies-Programm aktivieren, Richtlinien anlegen (oder vorhandene
übernehmen), Inventory-Location anlegen.
"""

from __future__ import annotations

import logging

from bot.config import EBAY_API
from bot.ebay.auth import EbayClient
from bot.ebay.inventory import DE_HEADERS, translate_ebay_error

log = logging.getLogger("ebay.account")

POLICY_ENDPOINTS = [
    ("fulfillment_policy", "fulfillmentPolicies", "fulfillmentPolicyId", "fulfillment_policy_id"),
    ("payment_policy", "paymentPolicies", "paymentPolicyId", "payment_policy_id"),
    ("return_policy", "returnPolicies", "returnPolicyId", "return_policy_id"),
]

CAT = [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}]

DEFAULT_POLICY_BODIES = {
    "payment_policy": {
        "name": "Listo Standard",
        "marketplaceId": "EBAY_DE",
        "categoryTypes": CAT,
    },
    "return_policy": {
        "name": "Listo Keine Ruecknahme",
        "marketplaceId": "EBAY_DE",
        "returnsAccepted": False,
        "categoryTypes": CAT,
    },
    "fulfillment_policy": {
        "name": "Listo DHL Paket",
        "marketplaceId": "EBAY_DE",
        "categoryTypes": CAT,
        "handlingTime": {"value": 2, "unit": "DAY"},
        "shippingOptions": [{
            "optionType": "DOMESTIC",
            "costType": "FLAT_RATE",
            "shippingServices": [{
                "sortOrder": 1,
                "shippingCarrierCode": "DHL",
                "shippingServiceCode": "DE_DHLPaket",
                "shippingCost": {"value": "5.49", "currency": "EUR"},
                "freeShipping": False,
            }],
        }],
    },
}


class AccountSetupError(Exception):
    pass


async def _opt_in_business_policies(client: EbayClient, user_id: int) -> None:
    resp = await client.request(
        "POST", f"{EBAY_API}/sell/account/v1/program/opt_in",
        auth="user", user_id=user_id,
        headers={"Content-Type": "application/json"},
        json_body={"programType": "SELLING_POLICY_MANAGEMENT"},
    )
    if resp.status_code not in (200, 204):
        raise AccountSetupError(
            f"Business-Policies-Aktivierung fehlgeschlagen: {translate_ebay_error(resp.text, resp.status_code)}"
        )
    log.info("Business Policies für Nutzer %s aktiviert", user_id)


async def get_or_create_policies(client: EbayClient, user_id: int) -> dict:
    """Vorhandene Richtlinien übernehmen, fehlende mit Listo-Defaults anlegen.
    Bei fehlendem Opt-in (Fehler 20403) automatisch aktivieren und wiederholen."""
    result: dict = {}
    opted_in = False
    for endpoint, list_key, id_key, field in POLICY_ENDPOINTS:
        for attempt in (1, 2):
            resp = await client.request(
                "GET", f"{EBAY_API}/sell/account/v1/{endpoint}",
                auth="user", user_id=user_id, params={"marketplace_id": "EBAY_DE"},
            )
            if resp.status_code == 200:
                break
            if resp.status_code == 400 and "20403" in resp.text and not opted_in and attempt == 1:
                await _opt_in_business_policies(client, user_id)
                opted_in = True
                continue
            raise AccountSetupError(
                f"Richtlinien-Abfrage fehlgeschlagen: {translate_ebay_error(resp.text, resp.status_code)}"
            )
        policies = resp.json().get(list_key, [])
        if policies:
            result[field] = policies[0][id_key]
            log.info("Nutzer %s: vorhandene %s übernommen (%s)", user_id, endpoint, result[field])
        else:
            create = await client.request(
                "POST", f"{EBAY_API}/sell/account/v1/{endpoint}",
                auth="user", user_id=user_id, headers=DE_HEADERS,
                json_body=DEFAULT_POLICY_BODIES[endpoint],
            )
            if create.status_code not in (200, 201):
                raise AccountSetupError(
                    f"Richtlinie {endpoint} konnte nicht angelegt werden: "
                    f"{translate_ebay_error(create.text, create.status_code)}"
                )
            result[field] = create.json()[id_key]
            log.info("Nutzer %s: %s angelegt (%s)", user_id, endpoint, result[field])
    return result


async def create_location(client: EbayClient, user_id: int, location_key: str,
                          address1: str, postal_code: str, city: str) -> None:
    # Existiert die Location schon (z.B. erneutes Onboarding)?
    check = await client.request(
        "GET", f"{EBAY_API}/sell/inventory/v1/location/{location_key}",
        auth="user", user_id=user_id,
    )
    if check.status_code == 200:
        return
    payload = {
        "location": {"address": {
            "addressLine1": address1, "city": city,
            "postalCode": postal_code, "country": "DE",
        }},
        "locationTypes": ["WAREHOUSE"],
        "merchantLocationStatus": "ENABLED",
        "name": "Listo Versandstandort",
    }
    resp = await client.request(
        "POST", f"{EBAY_API}/sell/inventory/v1/location/{location_key}",
        auth="user", user_id=user_id,
        headers={"Content-Type": "application/json"}, json_body=payload,
    )
    if resp.status_code not in (200, 201, 204):
        raise AccountSetupError(
            f"Versandstandort konnte nicht angelegt werden: {translate_ebay_error(resp.text, resp.status_code)}"
        )
    log.info("Location %s für Nutzer %s angelegt", location_key, user_id)
