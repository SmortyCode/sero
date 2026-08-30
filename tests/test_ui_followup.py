"""Quelltext-Wachen: Filter-Sheet, Sheet-Close, Detail-Tabs, Light."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = (ROOT / "frontend" / "sero.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "sero.css").read_text(encoding="utf-8")
CLEAN = (ROOT / "frontend" / "sero-clean.css").read_text(encoding="utf-8")


def _fn(src, name):
    i = src.index(f"function {name}")
    j = src.find("\nfunction ", i + 1)
    return src[i : j if j > 0 else None]


def test_filter_logo_oder_label():
    fn = _fn(JS, "invCatChipHtml")
    assert "fchip-logo" in fn
    assert "fchip-lab" in fn
    assert "aria-label" in fn
    assert "? `<img class=\"fchip-logo\"" in fn or '? `<img class="fchip-logo"' in fn
    assert ': `<span class="fchip-lab">' in fn
    assert "function invCatsChipOrder" in JS
    assert "CAT_CHIP_ORDER.filter" in _fn(JS, "invCatsChipOrder")
    assert 'const INV_CATS = ["One Piece", "Games", "Pokémon", "Sonstiges", "TCG Sonstiges"]' in JS


def test_filter_wordmark_invert_nur_dark():
    assert "html.skin-clean.force-light .fchip-logo { filter: none; }" in CLEAN
    assert "html.skin-clean.force-dark .fchip-logo" in CLEAN
    assert "filter: invert(1)" in CLEAN
    block = CLEAN.split("html.skin-clean.force-light .fchip-logo")[1][:80]
    assert "invert" not in block


def test_filter_progressive_disclosure():
    groups = _fn(JS, "invFilterGroups")
    assert 'return { all:' not in groups
    assert "INV_TCG_SET" in groups
    body = _fn(JS, "invFilterBodyHtml")
    assert 'const showGrade = cond === "graded"' in body
    assert "o.withLang && groups.tcg" in body
    assert "o.withRegion && groups.games" in body
    col = JS[JS.index("function openColFilter") : JS.index("function openColSearch")]
    assert "withLang: true" in col
    assert "withRegion: true" in col


def test_sheet_luecke_und_ziehbereich():
    assert "max-height: min(80vh," in CSS
    assert "max-height: min(88vh," not in CSS
    assert 'id="sheetHead"' in HTML
    assert 'id="sheetTitle"' in HTML
    assert "min-height: 44px" in CSS
    assert '$("sheetHead")' in JS
    assert "dy > 90" in JS
    assert "opts.dismissible !== false" in JS
    assert '$("sheetBackdrop").onclick = dismissible ? closeSheet : null' in JS


def test_detail_tabs_info_ebay():
    show = _fn(JS, "showDetailSeg")
    assert "scrollIntoView" not in show
    assert 'det.seg = wantListing ? "sell" : "overview"' in show
    rend = _fn(JS, "renderDetail")
    assert 'id="detailSeg"' in rend
    assert 'data-dseg="overview"' in rend
    assert 'data-dseg="sell"' in rend
    assert 'L("Info")' in rend
    assert 'L("eBay")' in rend
    assert 'data-pane="overview"' in rend
    assert 'data-pane="sell"' in rend
    assert 'id="detailListingBlock"' in rend
    assert "block.innerHTML = ebayPane" in rend
    assert "opts.ebayOnly" in rend
    assert "listingInputBusy" in rend
    assert "listingPaintKey" in JS
    assert '"Info": "Info"' in JS


def test_light_tokens_und_leaks():
    assert "color-scheme: light" in CLEAN
    assert "--bg: #ffffff" in CLEAN
    assert "--fill: #f2f2f7" in CLEAN
    assert "html.skin-clean.force-light #colGrid .gitem:not(.gitem-add)" in CLEAN
    assert "html.skin-clean.force-light .col-port-val" in CLEAN
    assert "html.skin-clean.force-light #viewLogin { background: #fff; }" in CLEAN
    assert "html.skin-clean.force-light #splash { background: #000 !important; }" in CLEAN
    assert "html.skin-clean.force-light .tv-prof-card" in CLEAN
    assert "html.skin-clean.force-light .d-cta-dock" in CLEAN
    assert "html.skin-clean.force-light .d-desc-preview" in CLEAN
    assert "html.skin-clean.force-light .scan-finder .btn-secondary" in CLEAN
    assert "wordmark-navy.png" in HTML
    assert "wordmark-white.png" in HTML
    assert "wordmark-sero-chrome.png" in HTML.split("id=\"splash\"")[1].split("</div>")[0]


def test_followup_pins():
    import re
    for asset, floor in (("sero.js", 255), ("sero.css", 164), ("sero-clean.css", 43), ("sero-profile.js", 23)):
        m = re.search(re.escape(asset) + r"\?v=(\d+)", HTML)
        assert m and int(m.group(1)) >= floor, f"{asset} Pin zu niedrig"


def test_kein_autopublish_followup():
    show = _fn(JS, "showDetailSeg")
    assert "publishOffer" not in show
    rend = _fn(JS, "renderDetail")
    assert "publishOffer" not in rend
    assert "function listingInputBusy" in JS
    assert "function enterGuestApp" in JS
    assert "function flushGuestDrafts" in JS
