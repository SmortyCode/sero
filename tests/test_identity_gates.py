"""A8 Gates: Katalog-Gift, Ownership-Hinweise, Query-Ignoranz (Quelltext)."""
from __future__ import annotations

from pathlib import Path

from web.identity import resolve_pricing_query


def test_a8_karte_ohne_nummer_keine_pricing_query():
    item = {
        "name": "Glurak",
        "analysis": {
            "product_kind": "trading_card",
            "card_info": {"name": "Glurak", "set": "Base", "number": None,
                          "language": "de"},
        },
    }
    pq, ready, ident, ev = resolve_pricing_query(item)
    assert ready is False
    assert pq is None


def test_a8_llm_query_kein_fallback():
    item = {
        "name": "Unklar",
        "analysis": {
            "product_kind": "smartphone",
            "search_query_for_pricing": "iPhone 15 Pro Max 256GB",
            "identity_candidates": [{"model": "A"}, {"model": "B"}],
        },
    }
    pq, ready, *_ = resolve_pricing_query(item)
    assert ready is False
    assert pq is None
    assert "iPhone" not in (pq or "")


def test_a8_katalog_write_nur_bei_pricing_ready():
    """Quelltext-Wache: upsert_card/refresh_price hinter if _ready."""
    quelle = (Path(__file__).parent.parent / "web" / "app_api.py").read_text(encoding="utf-8")
    # refresh_item_price-Block: Katalog nur bei _ready
    assert "if _ready:" in quelle
    assert "Katalog übersprungen" in quelle or "nicht pricing_ready" in quelle
    # upsert_card darf nicht ungefiltert vor dem Gate stehen
    idx_gate = quelle.index("if _ready:")
    idx_upsert = quelle.index("catalog.upsert_card", idx_gate)
    assert idx_upsert > idx_gate


def test_a8_alltag_kein_pricecharting_katalog():
    """Bier/Handy/Sneaker dürfen nicht in die Sammler-Preis-DB (Hell-Is-Us-Fall)."""
    quelle = (Path(__file__).parent.parent / "web" / "app_api.py").read_text(encoding="utf-8")
    assert "ProductKind.generic" in quelle
    assert "Katalog übersprungen (Alltagsprodukt)" in quelle
    assert "_ident.kind != ProductKind.generic" in quelle
    assert "Alltags-KI-Richtwert nicht durch 1 eBay-Treffer" in quelle


def test_a8_preis_felder_frisch_nach_await():
    """Quelltext-Wache: PREIS_FELDER + frisch lesen vor Write."""
    quelle = (Path(__file__).parent.parent / "web" / "app_api.py").read_text(encoding="utf-8")
    assert "PREIS_FELDER" in quelle
    assert "col_save_analyse" in quelle
    # Pattern: frisch = col_get vor Feldübernahme
    assert "frisch" in quelle


def test_a8_blocking_texts_in_frontend():
    js = (Path(__file__).parent.parent / "frontend" / "sero.js").read_text(encoding="utf-8")
    assert "blocking_texts" in js
    assert "Identität prüfen" in js
    assert '"Wert unbekannt"' in js or "Wert unbekannt" in js


def test_a8_kein_name_fallback_fuer_katalog_query():
    """Refresh darf freie Anzeigenamen nicht als Preis-Query nehmen."""
    quelle = (Path(__file__).parent.parent / "web" / "app_api.py").read_text(encoding="utf-8")
    assert '_pq or item.get("name")' not in quelle
