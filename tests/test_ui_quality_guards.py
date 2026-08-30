"""UI-Qualitaetswachen: Bildselektor, Grid, Tokens, Fokus, Titel."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "frontend" / "sero.css").read_text(encoding="utf-8")
DARK = (ROOT / "frontend" / "sero-dark.css").read_text(encoding="utf-8")
JS = (ROOT / "frontend" / "sero.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def test_bildselektor_endet_vor_ph_strip():
    """Produktbilder duerfen nicht die .ph-strip-Flex-Regeln erben."""
    m = re.search(
        r"\.gitem img,\s*\.d-photos img,\s*\.rc img,\s*\.mv-row img,\s*\.sale-row img,"
        r"[\s\S]{0,200}?\{([^}]*)\}",
        CSS,
    )
    assert m, "Fade-Regel fuer Produktbilder fehlt"
    block = m.group(0)
    assert "opacity" in block
    assert "overflow-x" not in block
    assert "scroll-snap-type" not in block
    assert re.search(r"(?m)^\.ph-strip\s*\{", CSS)
    assert not re.search(
        r"\.sale-row img,\s*/\*[\s\S]*?\.ph-strip\s*\{",
        CSS,
    )


def test_offer_seg_nutzt_definiertes_card_token():
    assert "--card:" in CSS or "--card:" in DARK
    assert "var(--card" in CSS
    assert re.search(r"\.offer-seg button\.on\s*\{[^}]*var\(--card", CSS, re.S)


def test_sammlungsgrid_minmax0():
    assert "repeat(2, minmax(0, 1fr))" in CSS
    assert "repeat(4, minmax(0, 1fr))" in CSS


def test_kontrast_tokens_solide():
    assert "--label-2: #3d4f6a" in CSS
    assert "--label-3: #5a6b86" in CSS
    assert "--label-3: #8fa3bd" in DARK
    assert "--btn-bg-bot:" in CSS


def test_focus_visible_vorhanden():
    assert ":focus-visible" in CSS


def test_login_labels_for_id():
    assert 'for="loginId"' in HTML
    assert 'for="loginCode"' in HTML
    assert 'for="signupEmail"' in HTML


def test_titlepair_ohne_default_900x340():
    assert "w = 900" not in JS and "w=900" not in JS
    assert "function refreshThemeTitles" in JS
    assert "function titleSrc" in JS
    assert 'tabCollection: ["sammlung", "Sammlung"]' in JS


def test_login_scrollbar():
    assert "#viewLogin" in CSS
    assert "overflow-y: auto" in CSS


def test_live_listing_preis_gesperrt():
    assert "price-live" in JS
    assert 'data-b="ended">Verkauft' in HTML
    assert "Noch nichts verkauft" in JS
    assert "function showDetailSeg" in JS
    assert "hideDetailSeg" not in JS
    assert "priceFrozen" in JS
    assert "ended_reason" in (ROOT / "web" / "app_api.py").read_text(encoding="utf-8")


def test_dark_tabbar_hellblau_transparent():
    """Navy-Skin behält Hellblau; Clean-Glass ist grau/weiss, kein altes Hellblau."""
    assert "rgba(168, 210, 255, .78)" in DARK
    assert "rgba(6, 12, 24, .38)" in DARK
    assert "#b8d6ff" in DARK
    clean = (ROOT / "frontend" / "sero-clean.css").read_text(encoding="utf-8")
    assert "rgba(168, 210, 255" not in clean
    assert "rgba(6, 12, 24, .38)" not in clean
    assert "#b8d6ff" not in clean
    assert "rgba(126, 182, 255" not in clean
    assert "--glass-bg:" in clean
    assert "--glass-blur:" in clean
    assert "--glass-radius:" in clean
    assert "--glass-radius-sm:" in clean
    bar = re.search(
        r"html\.skin-clean \.tabbar,\s*html\.skin-clean\.force-dark \.tabbar\s*\{([^}]*)\}",
        clean,
    )
    assert bar, "Clean-Tabbar-Regel fehlt"
    body = bar.group(1)
    assert "backdrop-filter" in body
    assert "-webkit-backdrop-filter" in body
    assert "var(--glass-bg)" in body
    assert "var(--glass-border)" in body
    assert "var(--glass-radius)" in body
    assert "999px" not in body
    assert "rgba(168, 210, 255" not in body
    ava = re.search(r"html\.skin-clean \.topbar-ava\s*\{([^}]*)\}", clean)
    assert ava and "var(--glass-radius)" in ava.group(1)
    assert "50%" not in ava.group(1)
    act = re.search(
        r"html\.skin-clean \.col-actions \.col-act,[\s\S]*?\{([^}]*)\}",
        clean,
    )
    assert act and "var(--glass-radius)" in act.group(1)
    assert "999px" not in act.group(1)
    tab = re.search(r"html\.skin-clean \.tab\s*\{([^}]*)\}", clean)
    assert tab and "var(--glass-radius-sm)" in tab.group(1)
    sales = re.search(r"html\.skin-clean #salesSeg\s*\{([^}]*)\}", clean)
    assert sales and "var(--glass-radius)" in sales.group(1)
    bulk = re.search(r"html\.skin-clean \.sales-bulk-bar\s*\{([^}]*)\}", clean)
    assert bulk and "var(--glass-radius)" in bulk.group(1)


def test_delete_sofort_mit_restore():
    assert "pendingDeletes" in JS
    assert "/restore" in JS
    assert "_skipEnsureDraft" in JS
    assert "formatListingEnd" in JS
    assert "listing-end" in CSS
    assert "post(`/api/app/collection/item/${item.id}/delete`).catch(() => {}).finally(loadCollection)" not in JS
    api = (ROOT / "web" / "app_api.py").read_text(encoding="utf-8")
    assert "/collection/item/{item_id}/restore" in api


def test_lr_ph_sort_touch_targets():
    """Listing-Review: Stern + Pfeile unter Thumbs — 44px-Ziele, kein Inline-Styling."""
    assert ".lr-ph-sort" in CSS
    assert "min-width: 44px" in CSS
    assert "ph-star.is-main" in CSS
    assert "lr-ph-sort" in JS
    assert "starfill" in JS
    assert 'class="ph-sort lr-ph-sort"' in JS
    assert "style=" not in re.search(
        r'lr-ph-sort[\s\S]{0,400}',
        JS,
    ).group(0)


def test_sammlung_karten_kein_zustand_kein_ebay_asset():
    start = JS.index("const makeCard")
    end = JS.index("const CHUNK")
    card = JS[start:end]
    assert "gcond" not in card
    assert "condLabel" not in card
    assert "g-ebay" not in card
    assert "ebayMarkHtml" not in card
    assert not re.search(r'assets/[^"\']*ebay[^"\']*', JS, re.I)
    assert "function itemLiveOnEbay" in JS


def test_sammlung_30_tage_delta_clean_farben():
    """Clean-Skin: kein Gruen/Rot am Sammlungswert (Teil B). Funktionen bleiben."""
    clean = (ROOT / "frontend" / "sero-clean.css").read_text(encoding="utf-8")
    assert "col-hub-delta" in JS
    assert "colHubDeltaFromPoints" in JS
    assert "Math.random" not in JS[JS.index("function colHubDeltaFromPoints"): JS.index("function colHubChartMarkup")]
    assert "html.skin-clean .col-hub-delta.up .col-hub-delta-nums" in clean
    assert "#8e8e93" in clean
