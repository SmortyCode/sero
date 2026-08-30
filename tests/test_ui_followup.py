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


def test_filter_chips_sind_text():
    """Kategorie-Chips tragen Text, keine Markenlogos.

    Vorher rendeten „Pokémon" und „One Piece" ihr Marken-SVG. Im Filter
    standen damit zwei Fremdschriften neben „Games" und „Weitere Karten" —
    Sven hat das als Schriftfehler gemeldet. Ein Logo wäre auch nie in
    derselben Schrift wie der Rest.
    """
    for name in ("invCatChipHtml", "catChipHtml"):
        fn = _fn(JS, name)
        assert "fchip-logo" not in fn, name
        assert "CAT_CHIP_LOGO" not in fn, name
        assert "aria-label" in fn, name
        assert "L(label)" in fn, name
    assert 'fchip-lab' in _fn(JS, "invCatChipHtml")
    assert "CAT_CHIP_LOGO" not in JS
    assert "fchip-logo" not in CLEAN
    assert "function invCatsChipOrder" in JS
    assert "CAT_CHIP_ORDER.filter" in _fn(JS, "invCatsChipOrder")
    assert 'const INV_CATS = ["One Piece", "Games", "Pokémon", "Sonstiges", "TCG Sonstiges"]' in JS


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
    # Splash folgt dem Thema: Weiß mit Anthrazit-Glyph, Schwarz mit weißem.
    # Vorher war er auch im Hellen fest schwarz — der helle Start blitzte
    # dann erst schwarz auf und sprang danach auf Weiß.
    assert "html.skin-clean.force-light #splash { background: #fff !important; }" in CLEAN
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


def test_splash_folgt_dem_thema():
    """Splash: Anthrazit-Glyph auf Weiß, weißes Glyph auf Schwarz.

    Der Splash trug nur EIN Bild. Im Hell-Modus lag darum entweder ein
    weisses Glyph auf Weiss oder ein dunkles auf Schwarz — je nachdem,
    welche Regel gerade gewann.
    """
    block = HTML.split('id="splash"')[1].split("</div>")[0]
    assert 'class="logo-light"' in block
    assert 'class="logo-dark"' in block
    assert "wordmark-navy.png" in block.split('class="logo-light"')[1][:80]
    assert "wordmark-sero-chrome.png" in block.split('class="logo-dark"')[1][:90]
    # Das Thema muss VOR dem ersten Anstrich stehen, sonst blitzt Schwarz auf.
    kopf = HTML.split("</head>")[0]
    assert "<script>" in kopf
    assert 'localStorage.getItem("sero_theme")' in kopf
    assert 'c.toggle("force-light", !dunkel)' in kopf
    # Helle Startbilder werden vor den dunklen angeboten.
    assert "startup-1170x2532-light.png" in HTML
    assert "startup-780x1688-light.png" in HTML
    assert HTML.index("startup-1170x2532-light.png") < HTML.index('startup-1170x2532.png?v=3')
    assert "(prefers-color-scheme: light)" in HTML


def test_asset_pins_einheitlich():
    """Ein Bild, ein Pin.

    Die Logos wurden neu gezeichnet, aber Topbar, Login und Leerzustände
    zeigten weiter auf ?v=3 und die Tour auf ?v=2. Wer die alte Datei im
    Cache hatte, sah dauerhaft das alte Glyph — genau der Fehler „weisses
    Logo auf hellem Grund".
    """
    import re
    quellen = {
        "index.html": HTML,
        "sero.js": JS,
        "sero-profile.js": (ROOT / "frontend" / "sero-profile.js").read_text(encoding="utf-8"),
    }
    pins: dict[str, set[str]] = {}
    for text in quellen.values():
        for datei, v in re.findall(r"assets/([\w.-]+\.png)\?v=(\d+)", text):
            pins.setdefault(datei, set()).add(v)
    uneinig = {d: sorted(vs) for d, vs in pins.items() if len(vs) > 1}
    assert not uneinig, f"Verschiedene Pins fuer dasselbe Bild: {uneinig}"


def test_hell_scan_profil_und_fokusring():
    """Die Flächen, die Sven im Hell-Modus schwarz gesehen hat."""
    # Der Scan-Sucher ist randlos und fast bildschirmhoch — schwarz bleibt
    # er im Hellen ein Block, in dem Knopf und Hinweis verschwinden.
    for regel in ("html.skin-clean.force-light .scan-finder {",
                  "html.skin-clean.force-light .scan-br {"):
        assert regel in CLEAN, regel
    for regel in ("html.skin-clean.force-light #tabProfile",
                  "html.skin-clean.force-light #profileScroll"):
        assert regel in CLEAN, regel
    profil = CLEAN.split("html.skin-clean.force-light #tabProfile")[1][:220]
    assert "#f2f2f7" in profil
    # Fokusring bleibt sichtbar, aber nicht als 2 px reines Schwarz.
    ring = CLEAN.split("html.skin-clean.force-light :focus-visible")[1][:260]
    assert "outline: 2px solid #000" not in ring
    assert "rgba(0, 0, 0, .42)" in ring
