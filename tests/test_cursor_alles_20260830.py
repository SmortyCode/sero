"""Wachen fuer den Auftrag 30.08.2026 — Listing, Loeschen, Profil, Theme, SR."""
from pathlib import Path

JS = Path("frontend/sero.js").read_text(encoding="utf-8")
PROF = Path("frontend/sero-profile.js").read_text(encoding="utf-8")
HTML = Path("frontend/index.html").read_text(encoding="utf-8")
CSS = Path("frontend/sero.css").read_text(encoding="utf-8")
CLEAN = Path("frontend/sero-clean.css").read_text(encoding="utf-8")
MANI = Path("frontend/manifest.webmanifest").read_text(encoding="utf-8")
LEGAL = Path("/Users/smorty/listo-website/legal.html").read_text(encoding="utf-8")


def test_listing_prep_hat_gate_timeout_retry():
    assert "function ebayConnectedNow" in JS
    assert "function showEbayNotConnectedHint" in JS
    assert "function startListingPrep" in JS
    assert "timeout: 20000" in JS
    assert "Listing-Vorbereitung fehlgeschlagen — erneut versuchen" in JS
    assert "eBay ist nicht verbunden" in JS
    assert "Wird vorbereitet…" in JS
    assert "state._listingPrepBusy" in JS


def test_kein_stiller_auto_list():
    i = JS.index("Kein stiller Auto-Start")
    assert "ensureItemDraft(item)" not in JS[i : i + 200]


def test_stueck_entfernen_braucht_confirm():
    assert "function askRemoveItem" in JS
    assert 'confirmSheet(L("Stück entfernen?")' in JS
    assert "askRemoveItem(item)" in JS
    assert "askRemoveItem(i)" in JS


def test_profil_kinder_pushen():
    assert "pushPane(" in PROF
    assert 'openRoot("account"' not in PROF
    assert 'openRoot("legal"' not in PROF


def test_theme_malt_light():
    assert "function themeIsDark" in JS
    assert 'classList.toggle("force-light", !dark)' in JS
    assert "html.skin-clean.force-light" in CLEAN
    assert "--bg: #ffffff" in CLEAN
    assert "html.skin-clean.force-light body" in CLEAN


def test_splash_und_empty_ohne_sr():
    splash = HTML[HTML.index('id="splash"') : HTML.index("viewLogin")]
    assert "wordmark-sero-chrome.png" in splash
    assert "monogram-white.png" not in splash
    assert "monogram-navy.png" not in splash
    empty = HTML[HTML.index('id="colEmpty"') : HTML.index("tabScan")]
    assert "wordmark-white.png" in empty
    assert "wordmark-navy.png" in empty
    assert "wordmark-sero-chrome.png" not in empty
    assert "monogram-white.png" not in empty
    assert "Noch keine Stücke." in empty


def test_ptr_hairline_kein_sr():
    i = JS.index("function attachPTR")
    chunk = JS[i : i + 400]
    assert "ptr-spin" in chunk
    assert "monogram-white.png" not in chunk
    assert "ptr-mono" not in chunk
    assert ".ptr-spin" in CSS


def test_manifest_schwarz():
    assert '"background_color": "#000000"' in MANI
    assert '"theme_color": "#000000"' in MANI


def test_agb_sagt_sero():
    agb = LEGAL[LEGAL.index('id="agb"') :]
    assert "SERO erstellt" in agb
    assert "Listo erstellt" not in agb


def test_scan_alle_anzeigen_bleibt():
    i = JS.index("function renderScan()")
    chunk = JS[i : i + 1800]
    assert "state._scanShowAll" in chunk
    assert 'switchTab("tabCollection")' not in chunk


def test_sales_null_euro_nicht_skeleton():
    assert "Keine Entwürfe." in JS
    assert "money(draftN ? draftVal : 0)" in JS
    assert "Noch nichts verkauft." in JS


def test_pins_hochgezaehlt():
    import re
    for asset, floor in (("sero.js", 255), ("sero.css", 164), ("sero-clean.css", 43), ("sero-profile.js", 23)):
        m = re.search(re.escape(asset) + r"\?v=(\d+)", HTML)
        assert m and int(m.group(1)) >= floor, f"{asset} Pin zu niedrig"


def test_teil_b_sammlung_ohne_vier_kreise():
    i = JS.index("function renderCollection")
    chunk = JS[i:i + 4500]
    assert "col-count-pill" in chunk
    assert "btnColView" not in chunk.split("paintColInvBar")[0] or "col-act" not in chunk.split("paintColInvBar")[0]
    assert '"30T"' in chunk
    assert '"1J"' in chunk
    assert "gitem-add" in JS
    assert "Wert wird ab dem 3. Stück sichtbar" in JS
    assert '["draft", L("Entwurf")]' in JS


def test_teil_b_scan_review_copy():
    assert "Das Foto wird der Entwurf." in JS
    assert "function openCamReview" in JS
    assert "scanReviewKeep" in JS
    assert "Keine Kamera an diesem Gerät." in JS
    assert 'id="scanReview"' in HTML


def test_teil_b_verkaufen_labels():
    i = JS.index("function renderSales")
    chunk = JS[i:i + 2800]
    assert 'L("Erlös")' in chunk or 'L("Entwurfswert")' in chunk
    assert 'L("Live")' in chunk
    assert 'id="salesView"' not in chunk
    assert "sales-foto-pill" in JS


def test_teil_b_profil_hub_eine_zeile():
    assert "function renderSettingsList" in PROF
    assert "menuSettings" in PROF
    assert "function paintProfileHub" in PROF
    assert "if (state.me) paintProfileHub" in PROF
    assert 'statCell(summary.in_collection, "Besitz")' in PROF


def test_d2_startup_und_maskable():
    assert "apple-touch-startup-image" in HTML
    assert "startup-1170x2532.png" in HTML
    assert "startup-780x1688.png" in HTML
    assert '"purpose": "maskable"' in MANI
    assert "icon-192.png" in MANI
    assert '"sizes": "512x512"' in MANI
    assert Path("frontend/assets/startup-1170x2532.png").is_file()
    assert Path("frontend/assets/startup-780x1688.png").is_file()
    assert Path("frontend/assets/icon-192.png").is_file()
    assert Path("frontend/assets/icon-maskable-512.png").is_file()


def test_listing_kicker_ohne_ebay_logo():
    i = JS.index("let ebayPane =")
    chunk = JS[i:i + 400]
    assert "ebayMarkHtml()" not in chunk
    assert "Listing-Design" in chunk


def test_sammlung_hero_nicht_von_sales_ueberschrieben():
    i = JS.index("function refreshColHubFromSales")
    chunk = JS[i:i + 280]
    assert "sumEl.textContent" not in chunk
    assert "refreshColHubDelta()" not in chunk


def test_drei_tabs_start_versteckt():
    assert 'html.skin-clean .tabbar .tab[data-tab="tabHome"]' in CLEAN
    assert "display: none !important" in CLEAN
    assert 'data-tab="tabSales"' in HTML
    assert 'tabIcons = { tabHome: "home", tabCollection: "stack", tabSales: "tag"' in JS


def test_verkaufen_badges_satzfall():
    i = JS.index("function saleLayoutBadge")
    chunk = JS[i:i + 500]
    assert 'L("Live")' in chunk
    assert 'L("Entwurf")' in chunk
    assert 'L("Verkauft")' in chunk
    assert 'L("ENTWURF")' not in chunk
    assert 'L("LIVE")' not in chunk


def test_d5_monogram_nicht_mehr_ausliefern():
    assert not Path("frontend/assets/monogram-white.png").exists()
    assert not Path("frontend/assets/monogram-navy.png").exists()
    assert not Path("landing/assets/monogram-white.png").exists()
    assert not Path("landing/assets/monogram-navy.png").exists()
    land = Path("landing/index.html").read_text(encoding="utf-8")
    assert "monogram-white.png" not in land
    assert "monogram-navy.png" not in land
    assert not Path("landing/en/index.html").exists()
    assert not Path("landing/landing.css").exists()
