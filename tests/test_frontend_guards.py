"""Quelltext-Wachen: Icons, a11y, Touch-Targets, Tabs, Pins, STR_EN."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = (ROOT / "frontend" / "sero.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "sero.css").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _icon_dict_keys() -> set[str]:
    m = re.search(r"const ICON_PATHS\s*=\s*\{(.*?)\n\};", JS, re.S)
    assert m, "ICON_PATHS Dict fehlt in sero.js"
    return set(re.findall(r"^\s*([a-z][a-z0-9]*)\s*:", m.group(1), re.M))


def _icon_call_names() -> set[str]:
    return set(re.findall(r'icon\(\s*"([a-z][a-z0-9]*)"', JS))


def test_a1_alle_icon_aufrufe_im_woerterbuch():
    keys = _icon_dict_keys()
    used = _icon_call_names()
    assert "grid" in keys, "Icon 'grid' fehlt (Sales-Ansichtsumschalter)"
    missing = sorted(used - keys)
    assert not missing, f"icon()-Aufrufe ohne Eintrag in ICON_PATHS: {missing}"


def test_a1_icon_fallback_ohne_prod_spam():
    assert "ICON_PATHS.question" in JS
    assert "_iconMissing" in JS
    assert "debug=1" in JS
    assert "console.warn" in JS


def test_a2_eye_dash_aria_labels():
    assert 'id="eyeBtn"' in HTML
    assert 'id="dashRefresh"' in HTML
    assert "function paintTopTools" in JS
    assert "Werte verbergen" in JS and "Werte anzeigen" in JS
    assert 'L("Preise aktualisieren")' in JS
    assert '"Werte verbergen":' in JS
    assert '"Preise aktualisieren":' in JS


def test_a2_hauptansicht_icon_buttons_haben_aria():
    for needle in (
        'id="eyeBtn"',
        'id="dashRefresh"',
        'id="colSearchLive"',
        'id="btnColFilter"',
        'id="btnColSort"',
        'id="alertBtn"',
        'id="priceRefresh"',
        'id="detailClose"',
        'id="detailTrash"',
        'id="detailFav"',
        'id="btnCamera"',
    ):
        assert needle in JS or needle in HTML, f"fehlt: {needle}"
    assert 'id="salesSearch"' in JS
    assert 'id="salesFilter"' in JS
    assert 'id="salesSort"' in JS
    assert "function ensureItemDraft" in JS
    assert 'aria-label="Werte verbergen"' in HTML or "Werte verbergen" in JS
    assert 'aria-label="Preise aktualisieren"' in HTML


def test_a3_touch_targets_css():
    assert re.search(r"\.fchip\s*\{[^}]*min-height:\s*44px", CSS, re.S)
    assert re.search(r"\.seg button\s*\{[^}]*min-height:\s*44px", CSS, re.S)
    assert re.search(r"\.info-i::before\s*\{[^}]*width:\s*44px", CSS, re.S)
    assert re.search(r"\.icon-btn\.sm::before\s*\{[^}]*inset:\s*-4px", CSS, re.S)


def test_a4_desktop_responsive_und_tabs():
    assert "@media (min-width: 720px)" in CSS
    assert "auto-fill" in CSS
    desk = CSS[CSS.index("@media (min-width: 720px)") :]
    assert "max-width: 430px" in desk
    assert 'data-tab="tabHome"' in HTML
    assert 'data-tab="tabCollection"' in HTML
    assert 'id="btnCamera"' in HTML
    assert 'data-tab="tabSales"' in HTML
    # Playbook Step 12: der eBay-Reiter ist raus, Start bleibt (im Clean-Skin verborgen).
    assert 'data-tab="tabProfile"' not in HTML
    tabs = re.findall(r'data-tab="([^"]+)"|id="(btnCamera)"', HTML)
    flat = [a or b for a, b in tabs]
    assert flat == ["tabHome", "tabCollection", "btnCamera", "tabSales"]


def test_a5_pins_hochgezaehlt():
    css_v = re.search(r"sero\.css\?v=(\d+)", HTML)
    dark_v = re.search(r"sero-dark\.css\?v=(\d+)", HTML)
    js_v = re.search(r"sero\.js\?v=(\d+)", HTML)
    assert css_v and int(css_v.group(1)) >= 94
    assert dark_v and int(dark_v.group(1)) >= 11
    assert js_v and int(js_v.group(1)) >= 142


def test_a5_str_en_aria_schluessel():
    keys = (
        "Werte verbergen",
        "Werte anzeigen",
        "Preise aktualisieren",
        "Ansicht wechseln",
        "Preisalarm",
        "Preis aktualisieren",
        "Erklärung",
        "Suchen",
        "Filtern",
        "Sortieren",
        "Senden",
        "Schließen",
        "Favorit",
        "Entfernen",
        "Mehr",
        "Scannen",
        "Preis selbst setzen",
        "Foto bearbeiten",
        "Hintergrund",
        "Verbindungen",
    )
    for k in keys:
        assert f'"{k}":' in JS, f"STR_EN fehlt fuer {k!r}"


def test_overview_kein_bewegungs_umschalter():
    assert 'id="itemsSeg"' not in JS
    assert "function paintTopAva" in JS
    assert 'id="topAva"' in HTML
    assert 'id="seroPriceCard"' in JS
    assert "large-title\">Scanner" not in HTML
    assert "large-title\">Verkauf" not in HTML
    assert "function titlePair" in JS
    assert "assets/titles/${name}-dark.png" in JS
    assert "assets/titles/${name}.png" in JS
    assert "titlePair(\"portfolio\"" in JS or "titlePair('portfolio'" in JS
    assert "function paintTopbarSection" in JS
    assert "topbarSection" in HTML
    assert "topbar-rule" in HTML
    assert "tab-title-flush" in HTML
    assert "ov-value-row" in JS
    assert 'assets/titles/sammlung.png' in HTML
    assert 'assets/titles/sammlung-dark.png' in HTML
    assert 'assets/titles/scanner.png' in HTML
    assert 'assets/titles/verkauf.png' in HTML
    assert 'titlePair("profil"' in JS or "titlePair('profil'" in JS
    assert 'assets/titles/einstellungen.png' in JS
    assert "title-invert" in JS
    # Kontrast: Light = kräftige/dunkle Titel, Dark = weiche
    assert 'title-light" src="assets/titles/sammlung-dark.png' in HTML
    assert 'title-dark" src="assets/titles/sammlung.png' in HTML
    assert 'logo-light" src="assets/wordmark-navy.png' in HTML
    assert 'logo-dark" src="assets/wordmark-white.png' in HTML
    for name in ("portfolio", "sammlung", "scanner", "verkauf", "profil"):
        assert (ROOT / "frontend" / "assets" / "titles" / f"{name}.png").is_file()
        assert (ROOT / "frontend" / "assets" / "titles" / f"{name}-dark.png").is_file()


def test_graded_frage_nur_bei_graded_pending():
    """Graded-Eingabe darf nicht bei jedem pending erscheinen (Rohkarte)."""
    assert 'd.pending === "graded" || d.pending === "graded_update"' in JS
    assert re.search(r"else if\s*\(\s*d\.pending\s*\)", JS) is None
    assert "function openQuickListSheet" in JS
    assert 'id="resList"' in JS


def test_sammlung_verlauf_bleibt_bei_filter():
    """Kategorie-Chips dürfen den Statistik-Chart nicht leeren."""
    assert "function collectionHistSeries" in JS
    assert "history_by_cat" in JS
    assert "histSeries = filterAn\n    ? []" not in JS
    assert "collectionHistSeries(wertItems" in JS


def test_g4_kacheln_und_direktverkauf():
    assert "sales-title-row" in CSS
    assert "function ensureItemDraft" in JS
    assert "function toggleColSelect" not in JS
    assert "col-select-bar" not in CSS
    assert 'id="salesSearch"' in JS
    assert "sales-act" in CSS
    assert "background: true" in JS or "background:!!" in JS or "{ background:" in JS


def test_listing_review_best_offer_min_und_foto_werkzeuge():
    assert "data-dbo-min" in JS
    assert 'action == "offermin"' in (
        Path(__file__).resolve().parent.parent / "web" / "app_api.py"
    ).read_text(encoding="utf-8")
    assert "function openDraftPhotoMenu" in JS
    assert "function resolveDraftPhotoItem" in JS
    assert "function draftPhotoItemHasLocal" in JS
    assert "citem-photo/${itemId}" in JS
    assert "optDraftImgTog" in JS
    assert 'act === "img"' in JS
    assert "openDraftPhotoMenu(d, 0)" in JS
    assert "lr-ph-sort" in JS
    assert "lr-bo-min" in CSS
    assert "designs-missing" in JS
    assert "Freisteller läuft im Hintergrund" in JS
    assert "lr-ph-sort" in CSS
    assert '"Mindestpreis":' in JS


def test_clean_overlay_skin():
    assert 'class="skin-clean force-dark"' in HTML
    assert "sero-clean.css?v=" in HTML
    clean = (ROOT / "frontend" / "sero-clean.css").read_text(encoding="utf-8")
    assert "html.skin-clean" in clean
    assert ".tab[data-tab=\"tabHome\"]" in clean
    assert "grid-column: 2" not in clean
    assert "tab-ebay" in clean or "order:" in clean
    # Playbook Step 12: genau drei Registerkarten, keine eBay-Wortmarke unten.
    # Verkaufen/Einstellungen erreicht man über Profil — nicht über eine zweite Tab-Leiste.
    assert 'tab-lab">eBay' not in HTML
    assert 'aria-label="eBay"' not in HTML
    assert "tab-ebay-mark" not in HTML
    assert "menuListings" not in (ROOT / "frontend" / "sero-profile.js").read_text(encoding="utf-8")
    assert 'switchTab("tabCollection")' in JS
    assert "login-mark" in HTML
    assert "login-soon" in HTML
    assert "login-app-icon" in HTML
    # Playbook Step 11: deutsches Chrome auf dem Login — kein englischer Rest.
    assert "Bald im App Store und für Android" in HTML
    assert '"Bald im App Store und für Android":' in JS
    assert "Available Soon" not in HTML
    assert "wordmark-sero-chrome.png" in HTML
    assert "assets/app-icon.png" in HTML
    assert "sero-mascot.png" not in HTML
    assert (ROOT / "frontend" / "assets" / "wordmark-sero-chrome.png").is_file()
    assert (ROOT / "frontend" / "assets" / "app-icon.png").is_file()
    assert "html.skin-clean .login-mark" in clean
    assert "html.skin-clean .login-soon" in clean
    assert "html.skin-clean .login-app-icon" in clean
    login_mark = re.search(
        r"html\.skin-clean \.login-mark\s*\{([^}]*)\}",
        clean,
    )
    assert login_mark, "Clean-Login-Wordmark fehlt"
    assert "filter: none" in login_mark.group(1)
    assert "grayscale" not in login_mark.group(1)
    top_logo = re.search(
        r"html\.skin-clean \.topbar-logo\s*\{([^}]*)\}",
        clean,
    )
    assert top_logo, "Clean-Topbar-Logo fehlt"
    assert "filter: none" in top_logo.group(1)
    assert "grayscale" not in top_logo.group(1)
    assert "html.skin-clean .login-card" in clean
    assert "var(--glass-radius)" in clean
    login_card = re.search(
        r"html\.skin-clean \.login-card\s*\{([^}]*)\}",
        clean,
    )
    assert login_card, "Clean-Login-Karte fehlt"
    assert "var(--glass-bg)" in login_card.group(1)
    assert "var(--glass-radius)" in login_card.group(1)
    assert "999px" not in login_card.group(1)
    login_btn = re.search(
        r"html\.skin-clean \.login-card \.btn-primary\s*\{([^}]*)\}",
        clean,
    )
    assert login_btn and "var(--glass-radius)" in login_btn.group(1)
    assert "999px" not in login_btn.group(1)
    assert "grayscale(1)" in clean
    raw = (ROOT / "frontend" / "sero-clean.css").read_bytes()[:20]
    assert raw.startswith(b"/* SERO"), raw[:20]


def test_tour_chrome_wordmark_kein_kreis():
    """Onboarding-Tour: flache Wordmark statt blauem SR-Kreis, Squircle-Buttons."""
    assert "function showTour" in JS
    assert "tour-wordmark" in JS
    assert "assets/wordmark-white.png" in JS
    assert "assets/wordmark-navy.png" in JS
    assert "tour-ring" not in JS
    assert "party-ring tour-ring" not in JS
    tour_src = JS[JS.index("function showTour") : JS.index("function dismissSplash")]
    assert "monogram-white.png" not in tour_src
    assert "monogram-navy.png" not in tour_src
    assert '"Willkommen":' in JS
    assert '"Fotografieren.":' in JS
    assert '"SERO legt einen Entwurf. Nichts geht live.":' in JS
    assert "Willkommen bei SERO" not in JS
    clean = (ROOT / "frontend" / "sero-clean.css").read_text(encoding="utf-8")
    mark = re.search(r"html\.skin-clean \.tour-wordmark\s*\{([^}]*)\}", clean)
    assert mark, "Clean-Tour-Wordmark fehlt"
    body = mark.group(1)
    assert "object-fit: contain" in body
    assert "filter: none" in body
    assert "grayscale" not in body
    assert "50%" not in body
    tour_btn = re.search(
        r"html\.skin-clean \.tour \.btn-primary,[\s\S]*?\{([^}]*)\}",
        clean,
    )
    assert tour_btn, "Clean-Tour-Button fehlt"
    assert "var(--glass-radius)" in tour_btn.group(1)
    assert "999px" not in tour_btn.group(1)
    assert ".tour-wordmark" in CSS
    assert ".tour-ring" not in CSS


def test_clean_ebay_tab_opens_hub():
    """Tabbar: Sammlung, Scannen, Verkaufen. Der eBay-Hub hängt am Profil, nicht unten."""
    assert not re.search(r'<button[^>]*data-tab="tabProfile"', HTML), \
        "Playbook Step 12: kein eBay-Reiter in der Tabbar"
    clean = (ROOT / "frontend" / "sero-clean.css").read_bytes()
    assert clean.startswith(b"/* SERO"), clean[:20]
    clean_txt = clean.decode("utf-8")
    assert re.search(r'tab\[data-tab="tabCollection"\]\s*\{\s*order:\s*1', clean_txt)
    assert re.search(r"#btnCamera\s*\{\s*order:\s*2", clean_txt)
    assert re.search(r'tab\[data-tab="tabSales"\]\s*\{\s*order:\s*3', clean_txt)
    hidden_block = re.search(
        r"html\.skin-clean \.tabbar \.tab\[data-tab=\"tabHome\"\]\s*\{[^}]*display:\s*none",
        clean_txt,
    )
    assert hidden_block, "Start bleibt im Clean-Skin verborgen"
    assert "display: none !important" in clean_txt
    assert "function renderEbayHub" in JS
    assert "function paintEbayHub" in JS
    assert "function openSeroProfile" in JS
    assert 'id="colEbayHub"' in JS
    assert "function catUiLabel" in JS
    assert "Weitere Karten" in JS
    assert "function catChipHtml" in JS
    # Chips sind Text. Markenlogos brachten ihre eigene Schrift mit.
    assert "logo-pokemon.svg" not in JS
    assert "logo-onepiece.svg" not in JS
    assert 'if (id === "tabProfile") renderEbayHub()' not in JS
    assert 'btn.onclick = () => openSeroProfile()' in JS
    assert 'if (id === "tabProfile") renderProfile()' not in JS
    hub = JS[JS.index("function paintEbayHub"): JS.index("window.renderEbayHub")]
    assert "colEbayHub" in hub
    assert "iframe" not in hub
    assert "col-ebay-mini" not in hub
    assert '"Designs":' in JS
    assert '"Noch keine Designs":' in JS
    assert '"{0} Designs":' in JS
    assert '"Listing-Design":' in JS
    assert 'L("eBay")}${sellTag}' in JS or 'L("eBay")' in JS
    prof = (ROOT / "frontend" / "sero-profile.js").read_text(encoding="utf-8")
    assert "async function renderProfile" in prof
    assert "openSeroProfile" in prof
    assert "openSalesBucket" in prof
    assert "menuListings" not in prof
    assert "menuDrafts" not in prof
    assert "menuSammlung" not in prof
    assert "hub-ebay" not in prof
    assert "setEbay" in prof or "menuSell" in prof
    assert (ROOT / "frontend" / "assets" / "logo-pokemon.svg").is_file()
    assert (ROOT / "frontend" / "assets" / "logo-onepiece.svg").is_file()


def test_tabbar_buttons_unveraendert():
    """Drei sichtbare Reiter: Sammlung, Scannen, Verkaufen. Kein eBay-Reiter."""
    assert 'tab-lab">Start' in HTML
    assert 'tab-lab">Sammlung' in HTML
    assert 'tab-cam-lab">Scannen' in HTML
    assert 'tab-lab">Verkaufen' in HTML
    assert 'aria-label="Verkaufen"' in HTML
    assert 'tab-lab">eBay' not in HTML
    tabs = re.findall(r'data-tab="([^"]+)"|id="(btnCamera)"', HTML)
    flat = [a or b for a, b in tabs]
    assert flat == ["tabHome", "tabCollection", "btnCamera", "tabSales"]
    nav = re.search(r'<nav class="tabbar">([\s\S]*?)</nav>', HTML)
    assert nav, "tabbar nav fehlt"
    inner = nav.group(1)
    assert inner.count("<button") == 4
    assets = ROOT / "frontend" / "assets"
    bad = [p.name for p in assets.rglob("*") if p.is_file()
           and "ebay" in p.name.lower() and p.suffix.lower() in {".svg", ".png", ".jpg", ".webp"}]
    assert not bad, f"Keine eBay-Logo-Dateien: {bad}"


def test_verkaufen_tab_ebay_wortmarke():
    """Playbook Step 12: Verkaufen trägt das Preisschild-Linienicon, keine Wortmarke."""
    btn = re.search(r'<button[^>]*data-tab="tabSales"[^>]*>[\s\S]*?</button>', HTML)
    assert btn, "tabSales-Button fehlt"
    chunk = btn.group(0)
    assert "tab-ebay-mark" not in chunk
    assert "<svg" not in chunk
    assert 'class="tic"' in chunk
    assert 'tab-lab">Verkaufen' in chunk
    assert 'aria-label="Verkaufen"' in chunk
    assert "src=" not in chunk
    assert 'tabSales: "tag"' in JS
    clean = (ROOT / "frontend" / "sero-clean.css").read_text(encoding="utf-8")
    sales = re.search(
        r'html\.skin-clean \.tabbar \.tab\[data-tab="tabSales"\]\s*\{([^}]*)\}',
        clean,
    )
    assert sales, "Clean-Regel für tabSales fehlt"
    body = sales.group(1)
    assert "order: 3" in body
    assert "flex:" in body
    # 44pt-Trefferflächen (Step 12)
    tab_rule = re.search(r"html\.skin-clean \.tab\s*\{([^}]*)\}", clean)
    assert tab_rule and "min-height: 44px" in tab_rule.group(1)
    assert 'tab[data-tab="tabSales"] .tab-ebay-mark' not in clean


def test_kein_sero_mascot_tabbar_content_breit():
    """Kein Maskottchen, keine Dock-Hülle, Pill nur so breit wie die drei Taps."""
    clean = (ROOT / "frontend" / "sero-clean.css").read_bytes()
    assert clean.startswith(b"/* SERO"), clean[:20]
    clean_txt = clean.decode("utf-8")
    assert "sero-mascot.js" not in HTML
    assert "tabbar-dock" not in HTML
    assert "tabbar-dock" not in clean_txt
    assert ".sero-mascot" not in clean_txt
    assert "sero-mascot-bob" not in clean_txt
    assert "sero-mascot-trail" not in clean_txt
    assert "@keyframes sero-mascot-bob" not in clean_txt
    bar = re.search(
        r"html\.skin-clean \.tabbar,\s*html\.skin-clean\.force-dark \.tabbar\s*\{([^}]*)\}",
        clean_txt,
    )
    assert bar, "Clean-Tabbar-Regel fehlt"
    body = bar.group(1)
    assert "width: max-content" in body
    assert "340px" not in body
    assert "min(340px" not in clean_txt
    assert "html.skin-clean .tabbar::after" not in clean_txt
    assert re.search(r"html\.skin-clean \.tab\s*\{[^}]*flex:\s*0 0 auto", clean_txt)
    assert re.search(r"html\.skin-clean \.tab-cam,\s*html\.skin-clean\.force-dark \.tab-cam", clean_txt)
    cam = re.search(
        r"html\.skin-clean \.tab-cam,\s*html\.skin-clean\.force-dark \.tab-cam,\s*"
        r"html\.skin-clean\.force-dark #btnCamera\s*\{([^}]*)\}",
        clean_txt,
    )
    assert cam, "Clean-Scan-Tab-Regel fehlt"
    assert "flex: 0 0 auto" in cam.group(1)


def test_sammlung_chart_filter_detail():
    """Chart-Scrub, Kategorien im Filter, Detail-Tabs Info|eBay, Content hinter der Pill."""
    clean = (ROOT / "frontend" / "sero-clean.css").read_bytes()
    assert clean.startswith(b"/* SERO"), clean[:20]
    clean_txt = clean.decode("utf-8")
    assert 'id="colChips"' not in JS
    assert 'id="fltCats"' in JS
    assert "function openColFilter" in JS
    assert "function catChipHtml" in JS
    assert "function bindChartScrub" in JS
    assert "setPointerCapture" in JS
    assert "function ebayHubChartValues" in JS
    assert "function ebayHubChartPoints" in JS
    assert "COL_HUB_CHART_H = 160" in JS
    assert "height: 160px" in clean_txt
    assert "mask-image: none" in clean_txt
    tabp = re.search(r"html\.skin-clean \.tab-page\s*\{([^}]*)\}", clean_txt)
    assert tabp, "Clean tab-page Regel fehlt"
    assert "padding-bottom: 0" in tabp.group(1)
    assert '<div class="section-label">${L("eBay-Entwurf")}</div>' not in JS
    assert "Listing-Design" in JS
    assert "function listingBgCss" in JS
    assert 'id="detailListingBlock"' in JS
    assert 'id="detailSeg"' in JS
    # Pins dürfen nur steigen. Eine feste Zahl musste bei jeder Änderung
    # mitgepflegt werden und schlug dann als „Fehler“ an, obwohl der Pin korrekt
    # hochgezählt war.
    for asset, floor in (("sero-clean.css", 34), ("sero.js", 245), ("sero.css", 157)):
        m = re.search(re.escape(asset) + r"\?v=(\d+)", HTML)
        assert m, f"Pin für {asset} fehlt in index.html"
        assert int(m.group(1)) >= floor, f"{asset}-Pin wurde zurückgedreht"
    assert 'id="ebayPhotoEdit"' in JS
    assert "openHeroPhotoEdit" in JS
    assert "isDetailEbaySeg(det)" in JS
    assert "cutout_status === \"error\"" in JS
    assert 'id="btnCutoutRetry"' in JS
    assert "Nochmal freistellen" in JS
    assert 'id="dryBadge"' not in HTML
    assert '$("dryBadge")' not in JS
    detail_pin = re.search(r"sero-detail\.js\?v=(\d+)", HTML)
    assert detail_pin, "Pin für sero-detail.js fehlt in index.html"
    assert int(detail_pin.group(1)) >= 6, "sero-detail.js-Pin wurde zurückgedreht"
    assert "function overviewHeroHtml" in JS
    assert "function paintDetailHeroGallery" in JS
    assert "function detailGalleryImages" in JS
    assert "function heroSourcePhotoIdx" in JS
    assert "preferDesign" in JS
    oid = JS[JS.index("async function openItemDetail"): JS.index("async function openDraftDetail")]
    assert "place_on_listing_bg" not in oid
    assert "publishOffer" not in oid
    assert "function seroPriceCardHtml" in JS
    assert "function showDetailSeg" in JS
    assert 'id="detailHero"' in JS
    assert 'id="btnHold"' in JS
    assert 'L("Als Entwurf behalten")' in JS
    assert 'L("Einstellen")' in JS
    assert 'L("über eBay")' in JS
    assert 'id="detailSeg"' in JS
    assert 'data-pane="sell"' in JS
    assert 'data-pane="overview"' in JS
    assert "d-cutout-err" in JS
    assert "Nochmal freistellen" in JS
    assert "function sellDescCard" in JS
    assert "function bindEbayDescCollapse" in JS
    assert 'L("Mehr")' in JS
    assert 'L("Weniger")' in JS
    assert '"Bearbeiten":' in JS
    assert '"Hinweise":' in JS
    assert '"Fakten":' in JS
    clean_cta = re.search(r"\.d-cta-row\s*\{([^}]*)\}", CSS)
    assert clean_cta, "d-cta-row Regel fehlt"
    assert "display: flex" in clean_cta.group(1)
    assert "html.skin-clean .d-cta-sub" in clean_txt or ".d-cta-sub" in CSS
    assert "d-desc-preview" in clean_txt
    assert "white-space: pre-wrap" in clean_txt
    assert "is-collapsed" in JS and "is-collapsed" in clean_txt
    assert "overviewPane += exemplarBlock" not in JS
    assert "html += exemplarBlock" not in JS
    assert "view.condition && !view.grade" not in JS
    assert 'LF("{0} Stück"' in JS
    assert "courtyard" not in JS.lower()
    assert "ACCEPT OFFER" not in JS
    DETAIL = (ROOT / "frontend" / "sero-detail.js").read_text(encoding="utf-8")
    assert "function priceCardModel" in DETAIL or "priceCardModel:" in DETAIL
    assert "preferDesign" in DETAIL
    assert "refresh-price" not in DETAIL
    assert "courtyard" not in DETAIL.lower()


def test_sammlung_karten_ohne_zustand_mit_ebay_marke():
    """Karten: kein Zustand, kein eBay-Logo — nur leises Entwurf/Aktiv-Badge."""
    start = JS.index("const makeCard")
    end = JS.index("const CHUNK")
    card = JS[start:end]
    assert "gcond" not in card
    assert "condLabel" not in card
    assert "g-design" not in card
    assert "design_photo" not in card
    assert "design_status" not in card
    assert '["live", L("Aktiv")]' in card or 'live", L("Aktiv")' in card
    assert "g-ebay" not in card
    assert "ebayMarkHtml" not in card
    assert "gfoot" in card
    assert "${photoInner}${liveMark}${ebayBtn}" not in card
    assert "${value}${ebayBtn}" not in card
    assert "data-ebay" not in card
    assert "publishOffer" not in card
    assert 'data-dact="upload"' not in card
    assert not re.search(r'assets/[^"\']*ebay[^"\']*\.(svg|png|jpg|webp)', JS, re.I)
    assets = ROOT / "frontend" / "assets"
    bad = [p.name for p in assets.rglob("*") if p.is_file()
           and "ebay" in p.name.lower() and p.suffix.lower() in {".svg", ".png", ".jpg", ".webp"}]
    assert not bad, f"Keine eBay-Logo-Dateien: {bad}"
    clean = (ROOT / "frontend" / "sero-clean.css").read_bytes()
    assert clean.startswith(b"/* SERO"), clean[:20]
    clean_txt = clean.decode("utf-8")
    assert "html.skin-clean .g-ebay" not in clean_txt
    assert ".g-ebay" not in CSS or "g-ebay" not in card
    DETAIL = (ROOT / "frontend" / "sero-detail.js").read_text(encoding="utf-8")
    chips = DETAIL[DETAIL.index("function detailChips"): DETAIL.index("function escHtml")]
    assert 'add("Zustand"' not in chips
    assert "view.condition" not in chips


def test_sammlung_30_tage_delta_nicht_geraten():
    """30-Tage-Zeile unter der Summe: nur echte Punkte, kein Fake-Prozent, Scrub lässt sie."""
    assert "function colHubDeltaFromPoints" in JS
    assert "function colHubDeltaSeries" in JS
    assert "function colHubDeltaHtml" in JS
    assert 'id="colHubDelta"' in JS
    assert '"30 Tage":' in JS
    assert '"seit Start":' in JS
    fn = JS[JS.index("function colHubDeltaFromPoints"): JS.index("function colHubHistoryPoints")]
    assert "fetch(" not in fn
    assert "/api/" not in fn
    assert "claude" not in fn.lower()
    assert "Math.random" not in fn
    assert "12,4" not in fn and "+12" not in fn
    assert "estimate" not in fn.lower()
    series = JS[JS.index("function colHubDeltaSeries"): JS.index("function fmtColHubPct")]
    assert "colHubHistoryPoints" in series
    assert "colHubSalesDatedPoints" in series
    assert "kind === \"d30\"" in series
    html_fn = JS[JS.index("function colHubDeltaHtml"): JS.index("function colHubDeltaFromState")]
    assert 'L("30 Tage")' in html_fn
    assert 'L("seit Start")' in html_fn
    assert '"—"' in html_fn or "—" in html_fn
    scrub = JS[JS.index("function bindChartScrub"): JS.index("function histWithLive")]
    assert "colHubDelta" not in scrub
    assert "30-Tage-Delta bleibt auf dem Endwert" in JS
    clean = (ROOT / "frontend" / "sero-clean.css").read_text(encoding="utf-8")
    assert "html.skin-clean .col-hub-delta.up .col-hub-delta-nums" in clean
    assert "html.skin-clean .col-hub-delta.down .col-hub-delta-nums" in clean
    assert "#8e8e93" in clean
    r = subprocess.run(
        ["node", str(ROOT / "tests" / "_run_col_hub_delta.js")],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    assert "SERO-COL-HUB-DELTA-OK" in r.stdout


def test_kamera_sofort_mediathek_getrennt_kein_dnd():
    """Scan öffnet die Kamera; Mediathek ohne capture; Reihenfolge per Pfeile."""
    assert 'id="camOverlay"' in HTML
    assert 'id="libraryInput"' in HTML
    assert 'id="cameraInput"' in HTML
    lib = HTML.split('id="libraryInput"', 1)[1][:120]
    assert "capture" not in lib
    assert "function openCamCapture" in JS
    assert "function addCamFiles" in JS
    assert "function openCamReview" in JS
    assert "getUserMedia" in JS
    assert "MAX_LISTING_PHOTOS = 12" in JS
    assert "ondrop" not in JS
    assert "ondragstart" not in JS
    assert 'L("Aus Mediathek")' in JS
    assert 'L("Hauptfoto")' in JS
    assert '"Aus Mediathek":' in JS
    assert '"über Inventory API verwaltet":' in JS
    assert "prepareScanFile" in JS
    assert "revokeCamShot" in JS
    assert "URL.revokeObjectURL" in JS
    assert 'id="camFlip"' in HTML
    assert 'id="camFlash"' in HTML
    assert "function flipLiveCam" in JS
    assert "function applyCamTorch" in JS
    assert "_camIndex" in JS
    assert "camAlreadyHas" in JS
    assert "Kamera nicht freigegeben. Mediathek geht trotzdem." in JS
    assert "function shippingFactRows" in JS
    assert "pc-strip" in JS
