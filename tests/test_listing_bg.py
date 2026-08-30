"""Whitelist und Normalisierung für Listing-Hintergrundfarben."""
from __future__ import annotations

import pytest

from bot.render import DEFAULT_BG_COLOR
from web.listing_bg import (
    DEFAULT_LISTING_BG,
    LISTING_BG_ALLOWED,
    LISTING_BG_COLORS,
    effective_listing_bg,
    normalize_listing_bg,
)


def test_palette_hat_weiss_dunkel_sero():
    assert "#FFFFFF" in LISTING_BG_ALLOWED
    assert "#F5F9FF" in LISTING_BG_ALLOWED
    assert "#0B0B0D" in LISTING_BG_ALLOWED
    assert "#2A2E35" in LISTING_BG_ALLOWED
    assert "#E4ECF6" in LISTING_BG_ALLOWED
    assert len(LISTING_BG_COLORS) >= 10


def test_default_ist_schwarz_hintergrund_3():
    assert DEFAULT_LISTING_BG == "#0B0B0D"
    assert DEFAULT_BG_COLOR == "#0B0B0D"
    assert effective_listing_bg(None) == "#0B0B0D"
    assert effective_listing_bg({}) == "#0B0B0D"
    assert effective_listing_bg({"listing_bg": "#F5F9FF"}) == "#F5F9FF"


def test_normalize_ok_und_leer():
    assert normalize_listing_bg("#f5f9ff") == "#F5F9FF"
    assert normalize_listing_bg("FFFFFF") == "#FFFFFF"
    assert normalize_listing_bg("") is None
    assert normalize_listing_bg(None) is None
    assert normalize_listing_bg("default") is None


def test_normalize_lehnt_fremd_ab():
    with pytest.raises(ValueError):
        normalize_listing_bg("#FF00FF")


def test_frontend_swatches_decken_whitelist():
    """sero.js LISTING_BG_SWATCHES muss dieselben Hex wie listing_bg.py haben."""
    from pathlib import Path
    import re
    js = (Path(__file__).resolve().parent.parent / "frontend/sero.js").read_text(encoding="utf-8")
    m = re.search(r"const LISTING_BG_SWATCHES = \[(.*?)\];", js, re.S)
    assert m, "LISTING_BG_SWATCHES fehlt in sero.js"
    hexes = set(re.findall(r'hex:\s*"(#[0-9A-Fa-f]{6})"', m.group(1)))
    assert hexes == set(LISTING_BG_ALLOWED), (
        f"Abweichung Frontend↔Backend: "
        f"nur JS {hexes - LISTING_BG_ALLOWED} / nur Py {LISTING_BG_ALLOWED - hexes}")
    assert 'DEFAULT_LISTING_BG = "#0B0B0D"' in js
    assert 'SELL_TPL_DEFAULT = { format: "FIXED_PRICE", auction_days: 7, price_mode: "market", price_value: null, bg: "black" }' in js


def test_clean_skin_studio_ist_hintergrund_3():
    from pathlib import Path
    css = (Path(__file__).resolve().parent.parent / "frontend/sero-clean.css").read_text(encoding="utf-8")
    assert "--thumb-bg: #0B0B0D" in css
    assert "var(--listing-bg, #0B0B0D)" in css
    assert "#f5f9ff" not in css.lower()


def test_foto_menue_hat_hintergrund():
    from pathlib import Path
    js = (Path(__file__).resolve().parent.parent / "frontend/sero.js").read_text(encoding="utf-8")
    assert "optPhotoBg" in js
    assert "openListingBgPicker" in js
    assert "render_kwargs_for_item" in (
        Path(__file__).resolve().parent.parent / "web/app_api.py"
    ).read_text(encoding="utf-8")
