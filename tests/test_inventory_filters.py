"""Quelltext-Wachen: Inventar Search/Filter/Sort auf Sammlung und Verkaufen."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = (ROOT / "frontend" / "sero.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
API = (ROOT / "web" / "app_api.py").read_text(encoding="utf-8")


def test_inv_cats_multi_select_empty_all():
    assert 'const INV_CATS = ["One Piece", "Games", "Pokémon", "Sonstiges", "TCG Sonstiges"]' in JS
    assert "function invToggleCat" in JS
    assert "function itemMatchesInvCats" in JS
    assert "if (!cats || !cats.length) return true;" in JS
    assert 'id="colInvChips"' not in HTML
    assert 'id="salesInvChips"' not in HTML
    assert "function invChipRowHtml" not in JS
    col = JS[JS.index("function paintColInvBar"): JS.index("function renderCollection")]
    assert "colInvChips" not in col
    assert "invToggleCat" not in col
    sales = JS[JS.index("function paintSalesInvBar"): JS.index("function saleLayoutBadge")]
    assert "salesInvChips" not in sales
    assert "invToggleCat" not in sales
    assert 'id="fltCats"' in JS
    badge = JS[JS.index("function invFilterBadgeCount"): JS.index("function invSheetActive")]
    assert "invCatsSelected(f).length" in badge
    assert "invSheetFacetCount(f)" in badge


def test_filter_sheet_labels():
    assert 'invFacetChip("cond", "raw", "Roh"' in JS
    assert 'invFacetChip("cond", "graded", "Graded"' in JS
    for g in ("PSA", "BGS", "SGC", "CGC", "WATA"):
        assert g in JS
    for n in ('"10"', '"9.8"', '"9.5"', '"8.5"'):
        assert n in JS
    assert '"Deutsch"' in JS and '"Englisch"' in JS and '"Japanisch"' in JS
    assert '"PAL"' in JS and '"NTSC"' in JS
    assert 'openInvFilter("Filter"' in JS
    assert '}, "Anwenden")' in JS
    assert 'L("Zurücksetzen")' in JS
    assert "function openColFilter" in JS
    assert "function openSalesFilter" in JS
    sales_flt = JS[JS.index("function openSalesFilter"): JS.index("function paintSalesInvBar")]
    assert "withCats: true" in sales_flt
    col_flt = JS[JS.index("function openColFilter"): JS.index("function openColSearch")]
    assert "withCats: true" in col_flt
    assert "state.filter.cats" in col_flt
    assert "withLang: true" in col_flt
    assert "withRegion: true" in col_flt


def test_sort_defaults_and_labels():
    col = JS[JS.index("function openColSort"): JS.index("function openColFilter")]
    assert "Zuletzt hinzugefügt" in col
    assert 'value: "new"' in col
    assert "Wert (höchster zuerst)" in col
    assert "Wert (niedrigster zuerst)" in col
    assert "Name (A–Z)" in col
    assert "Name (Z–A)" in col
    assert "Best match" not in col
    assert "Größte Preisbewegung" not in col
    assert "Popularität" not in col
    assert "function salesSortDefault" in JS
    assert 'if (bucket === "draft") return "edited"' in JS
    assert 'if (bucket === "ended") return "sold"' in JS
    assert 'return "end_asc"' in JS
    sales = JS[JS.index("function openSalesSort"): JS.index("function openSalesSearch")]
    assert "Zuletzt bearbeitet" in sales
    assert "Bald endend" in sales
    assert "Neu eingestellt" in sales
    assert "Zuletzt verkauft" in sales
    assert "Ending soonest" not in JS[JS.index("function openColSort"): JS.index("function openColSearch")]


def test_search_placeholders():
    assert "Titel, Set, Cert-Nr." in HTML
    assert "Titel, Artikelnummer" in HTML
    assert 'placeholder="Titel, Set, Cert-Nr."' in HTML
    assert 'id="colSearchLive"' in HTML
    assert 'id="salesSearchLive"' in HTML
    assert "function itemSearchHay" in JS
    hay = JS[JS.index("function itemSearchHay"): JS.index("function itemValueNum")]
    assert "cert_number" in hay
    search_ui = JS[JS.index("function openColSearch"): JS.index("async function importListings")]
    assert "cameraInput" not in search_ui
    assert "btnCamera" not in search_ui


def test_empty_copy_stueck_vocab():
    assert "Noch keine Stücke" in HTML
    assert "Artikel fotografieren" in HTML or "Artikel fotografieren" in JS
    # Playbook Step 13: ein Weg nach vorn. Import steht unter Daten & Backup.
    assert 'id="emptyImport"' not in HTML
    assert "emptyImport" not in JS
    assert "Artikel fotografieren" in JS
    assert "Keine Treffer für „{0}“" in JS
    assert "Suchbegriff kürzen oder Filter zurücksetzen." in JS
    assert "There's nothing here" not in JS
    assert "There's nothing here" not in HTML
    es = JS[JS.index("function emptyState"): JS.index("function emptyState") + 500]
    assert "sekundar" in es


def test_layout_two_modes_and_counts():
    assert "function colViewMode" in JS
    cv = JS[JS.index("function colViewMode"): JS.index("function salesViewMode")]
    assert 'return "list"' in cv
    assert 'return "g2"' in cv
    assert 'LF("{0} Stück"' in JS
    assert 'id="colInvCount"' in HTML
    assert 'id="salesInvCount"' in HTML
    assert "saleLayoutBadge" in JS
    assert 'L("Live")' in JS
    assert 'L("Entwurf")' in JS
    assert 'L("Verkauft")' in JS


def test_applied_chips_clear_keeps_category_on_empty_reset():
    """Applied-Chips nur fuer andere Facets; Kategorie nur im Filter-Sheet."""
    assert "function invAppliedHtml" in JS
    assert "Alles zurücksetzen" in JS
    applied = JS[JS.index("function invAppliedHtml"): JS.index("function invRemoveApplied")]
    assert "invCatsSelected" not in applied
    assert "INV_CATS" not in applied
    empty = JS[JS.index("if (!items.length && hasItems)"): JS.index("function openColSort")]
    assert "invResetSheetFacets(state.filter)" in empty
    assert 'state.colQuery = ""' in empty
    sales_empty = JS[JS.index('$("salesEmpty").hidden = rows.length > 0'): JS.index("fadeImgs($(\"salesList\"))")]
    assert "invResetSheetFacets(state.salesFilter)" in sales_empty
    reset_fn = JS[JS.index("function invResetSheetFacets"): JS.index("function cloneInvFacets")]
    assert "f.cats = []" in reset_fn


def test_no_autopublish_in_inventory_ui():
    chunk = JS[JS.index("function openColFilter"): JS.index("async function importListings")]
    assert "publishOffer" not in chunk
    assert "/sales/publish-drafts" not in chunk
    assert "claim_draft" not in chunk
    sales_chunk = JS[JS.index("function openSalesFilter"): JS.index("function saleFormatLabel")]
    assert "publishOffer" not in sales_chunk
    assert "claim_or_create_intent" in API
