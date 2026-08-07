#!/usr/bin/env python3
"""Legt die Inventory Location an (Pflicht für createOffer).

Der Key kommt aus EBAY_MERCHANT_LOCATION_KEY in der .env; die Adresse wird
interaktiv abgefragt.
"""

import asyncio
import sys

from bot.config import EBAY_API, load_config
from bot.drafts import Store
from bot.ebay.auth import EbayAuthError, EbayClient


async def main() -> None:
    cfg = load_config(require_policies=False)
    if not cfg.merchant_location_key:
        print("❌ EBAY_MERCHANT_LOCATION_KEY fehlt in der .env.", file=sys.stderr)
        sys.exit(1)
    store = Store()
    client = EbayClient(cfg, store)
    try:
        # Existiert die Location schon?
        resp = await client.request(
            "GET", f"{EBAY_API}/sell/inventory/v1/location/{cfg.merchant_location_key}", auth="user", user_id=cfg.allowed_user_id
        )
        if resp.status_code == 200:
            print(f"✅ Location '{cfg.merchant_location_key}' existiert bereits — nichts zu tun.")
            return

        print(f"Lege Location '{cfg.merchant_location_key}' an. Adresse eingeben:")
        name = input("  Name (z.B. 'Sero Home Base'): ").strip() or "Home"
        address1 = input("  Straße + Hausnummer: ").strip()
        city = input("  Stadt: ").strip()
        postal = input("  PLZ: ").strip()

        payload = {
            "location": {
                "address": {
                    "addressLine1": address1,
                    "city": city,
                    "postalCode": postal,
                    "country": "DE",
                }
            },
            "locationTypes": ["WAREHOUSE"],
            "merchantLocationStatus": "ENABLED",
            "name": name,
        }
        resp = await client.request(
            "POST", f"{EBAY_API}/sell/inventory/v1/location/{cfg.merchant_location_key}",
            auth="user", user_id=cfg.allowed_user_id, headers={"Content-Type": "application/json"}, json_body=payload,
        )
        if resp.status_code in (200, 201, 204):
            print(f"✅ Location '{cfg.merchant_location_key}' angelegt. Setup fertig — ./run.sh starten!")
        else:
            print(f"❌ Anlegen fehlgeschlagen ({resp.status_code}): {resp.text[:500]}", file=sys.stderr)
            sys.exit(1)
    except EbayAuthError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
