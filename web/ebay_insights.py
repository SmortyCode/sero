"""eBay Marketplace Insights — die offizielle Verkaufsdaten-API (letzte 90 Tage).

STAND 03.08.2026: eBay hat Svens Antrag ABGELEHNT. Wortlaut des Developer
Support: „Access to this API is highly limited and generally reserved for
eBay's approved partners only." Der OAuth-Scope buy.marketplace.insights ist
der App nicht gewährt — schon die Token-Anfrage scheitert mit invalid_scope,
nicht erst der Aufruf.

Der Code bleibt bewusst stehen: Sollte Sven später eBay-Partner werden, genügt
SERO_EBAY_INSIGHTS=1 und die Quelle steht wieder an erster Stelle der Kaskade.
Bis dahin ist sie AUS — jede Anfrage wäre ein garantierter Fehlschlag und
kostet nur Zeit im Scan.
"""

from __future__ import annotations

import logging
import os
import time
import urllib.parse

import httpx

log = logging.getLogger("ebay_insights")
_http = httpx.AsyncClient(timeout=20)
_token: dict = {}
# Standardmäßig aus (siehe Kopf) — mit SERO_EBAY_INSIGHTS=1 wieder anschalten
enabled = os.environ.get("SERO_EBAY_INSIGHTS") == "1"
_disabled_until = 0.0


async def _app_token() -> str | None:
    if _token.get("t") and time.time() < _token.get("exp", 0):
        return _token["t"]
    cid, sec = os.environ.get("EBAY_CLIENT_ID"), os.environ.get("EBAY_CLIENT_SECRET")
    if not cid or not sec:
        return None
    r = await _http.post("https://api.ebay.com/identity/v1/oauth2/token",
                         auth=(cid, sec),
                         data={"grant_type": "client_credentials",
                               "scope": "https://api.ebay.com/oauth/api_scope"})
    if r.status_code != 200:
        return None
    j = r.json()
    _token.update(t=j["access_token"], exp=time.time() + j.get("expires_in", 7200) - 60)
    return _token["t"]


async def insights_rows(query: str) -> list[dict]:
    """Verkaufs-Zeilen im sold.py-Format — [] wenn (noch) nicht freigeschaltet."""
    global _disabled_until
    if not enabled or time.time() < _disabled_until:
        return []
    tok = await _app_token()
    if not tok:
        return []
    try:
        r = await _http.get(
            "https://api.ebay.com/buy/marketplace_insights/v1_beta/item_sales/search"
            f"?q={urllib.parse.quote(query)}&limit=20",
            headers={"Authorization": f"Bearer {tok}",
                     "X-EBAY-C-MARKETPLACE-ID": "EBAY_DE"})
        if r.status_code in (401, 403) or (r.status_code == 200 and "errors" in r.text[:80]):
            _disabled_until = time.time() + 6 * 3600
            log.info("insights: noch nicht freigeschaltet — 6 h Pause")
            return []
        r.raise_for_status()
        out = []
        for it in r.json().get("itemSales", []):
            p = (it.get("lastSoldPrice") or {})
            try:
                price = float(p.get("value"))
            except (TypeError, ValueError):
                continue
            out.append({"title": it.get("title") or "", "price": price,
                        "currency": p.get("currency") or "EUR",
                        "date": (it.get("lastSoldDate") or "")[:10],
                        "url": it.get("itemWebUrl"),
                        "image": (it.get("image") or {}).get("imageUrl")})
        return out
    except Exception as e:  # noqa: BLE001
        log.warning("insights: %s", e)
        return []
