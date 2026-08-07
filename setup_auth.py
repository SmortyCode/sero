#!/usr/bin/env python3
"""Einmaliger eBay User-OAuth-Flow (Authorization Code Grant).

Ablauf: Consent-URL im Browser öffnen, bei eBay einloggen und zustimmen,
danach die KOMPLETTE Redirect-URL (oder nur den code=…-Wert) hier einfügen.
"""

import asyncio
import sys
import urllib.parse

from bot.config import load_config
from bot.drafts import Store
from bot.ebay.auth import EbayAuthError, EbayClient


def extract_code(pasted: str) -> str:
    pasted = pasted.strip()
    if "code=" in pasted:
        query = urllib.parse.urlparse(pasted).query or pasted.split("?", 1)[-1]
        params = urllib.parse.parse_qs(query)
        if "code" in params:
            # eBay liefert den Code URL-encodiert — parse_qs decodiert bereits
            return params["code"][0]
    return pasted


async def main() -> None:
    cfg = load_config(require_policies=False)
    store = Store()
    client = EbayClient(cfg, store)
    try:
        url = client.build_consent_url()
        print("\n1. Öffne diese URL im Browser und logge dich mit deinem eBay-Verkäuferkonto ein:\n")
        print(f"   {url}\n")
        print("2. Nach der Zustimmung leitet eBay weiter — kopiere die komplette URL aus der Adresszeile.\n")
        pasted = input("Redirect-URL (oder code) hier einfügen: ")
        code = extract_code(pasted)
        await client.exchange_code(code, cfg.allowed_user_id)
        status = client.user_token_status(cfg.allowed_user_id)
        print(f"\n✅ Token gespeichert. Refresh-Token gültig für ~{status['refresh_valid_d']} Tage.")
        print("Weiter mit: python setup_policies.py")
    except EbayAuthError as e:
        print(f"\n❌ {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
