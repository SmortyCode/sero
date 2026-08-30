"""Canary-/Feature-Flags."""
import os

from web.pipeline_flags import cutout_v2_enabled, pricing_v2_enabled
from web.pricing_v2.price_class import derive_price_class


def test_flags_default_off(monkeypatch):
    monkeypatch.delenv("SERO_CUTOUT_V2", raising=False)
    monkeypatch.delenv("SERO_CUTOUT_V2_CANARY", raising=False)
    monkeypatch.delenv("SERO_PRICING_V2", raising=False)
    monkeypatch.delenv("SERO_PRICING_V2_CANARY", raising=False)
    assert cutout_v2_enabled("abc") is False
    assert pricing_v2_enabled("abc") is False


def test_canary_allowlist(monkeypatch):
    monkeypatch.delenv("SERO_CUTOUT_V2", raising=False)
    monkeypatch.setenv("SERO_CUTOUT_V2_CANARY", "376e7889dd81,other")
    assert cutout_v2_enabled("376e7889dd81") is True
    assert cutout_v2_enabled("nope") is False


def test_price_class_mapping():
    assert derive_price_class({"est_value": 10, "price_source": "ebay_sold",
                               "price_state": "belegt"}) == "EXACT_SOLD"
    assert derive_price_class({"est_value": 10, "price_source": "pricecharting",
                               "price_state": "belegt"}) == "GUIDE_VALUE"
    assert derive_price_class({"est_value": 10, "price_source": "ebay_eu",
                               "price_state": "spanne"}) == "ASKING_ONLY"
    assert derive_price_class({"est_value": None, "price_state": "unbekannt"}) == "NO_MARKET_DATA"


def test_glance_vor_cutout():
    """Klassifikation vor Freistellen; Analyse läuft parallel danach."""
    from pathlib import Path
    quelle = Path("web/app_api.py").read_text(encoding="utf-8")
    i = quelle.index("async def analyze_collection_item")
    chunk = quelle[i:i + 5500]
    assert "glance_scan" in chunk
    assert "apply_scan_kind" in chunk
    assert "GLANCE_TIMEOUT_S" in chunk
    assert chunk.index("glance_scan") < chunk.index("crop_photos")
    assert "listing_task" in chunk
    assert "analyzer.analyze" in chunk
    claude = Path("bot/claude_client.py").read_text(encoding="utf-8")
    assert "async def identity_glance" in claude
    cs = Path("web/cardscan.py").read_text(encoding="utf-8")
    assert "GLANCE_MODEL" in cs
    assert "product | card | slab" in cs or "product|card|slab" in cs


def test_drei_cutout_routen():
    from web.cutout_v2.routing import should_warp, scan_kind_to_legacy
    assert should_warp("raw") is True
    assert should_warp("slab") is True
    assert should_warp("other") is False
    assert should_warp("sleeve") is False
    assert scan_kind_to_legacy("product") == "other"
    assert scan_kind_to_legacy("card") == "raw"
    assert scan_kind_to_legacy("slab") == "slab"
    r = open("web/cutout_v2/routing.py", encoding="utf-8").read()
    assert "product — Alltagsstück" in r or "product =" in r
    assert "alte Rechteck-Technik" in r
    assert "Warp aufs Case" in r
