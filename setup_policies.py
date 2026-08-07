#!/usr/bin/env python3
"""Liest die Business-Policy-IDs (Versand, Zahlung, Rückgabe) für EBAY_DE aus
und zeigt sie an — die IDs gehören in die .env."""

import asyncio
import sys

from bot.config import EBAY_API, load_config
from bot.drafts import Store
from bot.ebay.auth import EbayAuthError, EbayClient

POLICIES = [
    ("fulfillment_policy", "fulfillmentPolicies", "fulfillmentPolicyId", "EBAY_FULFILLMENT_POLICY_ID"),
    ("payment_policy", "paymentPolicies", "paymentPolicyId", "EBAY_PAYMENT_POLICY_ID"),
    ("return_policy", "returnPolicies", "returnPolicyId", "EBAY_RETURN_POLICY_ID"),
]


async def main() -> None:
    cfg = load_config(require_policies=False)
    store = Store()
    client = EbayClient(cfg, store)
    found_any = False
    try:
        for endpoint, list_key, id_key, env_var in POLICIES:
            resp = await client.request(
                "GET", f"{EBAY_API}/sell/account/v1/{endpoint}",
                auth="user", user_id=cfg.allowed_user_id, params={"marketplace_id": "EBAY_DE"},
            )
            if resp.status_code != 200:
                print(f"❌ {endpoint}: HTTP {resp.status_code}: {resp.text[:300]}")
                continue
            policies = resp.json().get(list_key, [])
            if not policies:
                print(f"⚠️  Keine {endpoint} gefunden — in 'Mein eBay > Verkaufsrichtlinien' anlegen.")
                continue
            print(f"\n{env_var}:")
            for p in policies:
                print(f"  {p[id_key]}  —  {p.get('name', '(ohne Name)')}")
            found_any = True
        if found_any:
            print("\nDie gewünschten IDs in die .env eintragen, dann: python setup_location.py")
    except EbayAuthError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
