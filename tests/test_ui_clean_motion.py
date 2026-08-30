"""Wachen fuer sero-ui-clean-motion.md — Clean-Skin + Micro-Motion."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = (ROOT / "frontend" / "sero.js").read_text(encoding="utf-8")
PROF = (ROOT / "frontend" / "sero-profile.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "sero.css").read_text(encoding="utf-8")
CLEAN = (ROOT / "frontend" / "sero-clean.css").read_text(encoding="utf-8")


def test_chrome_nur_splash():
    splash = HTML[HTML.index('id="splash"') : HTML.index("viewLogin")]
    assert "wordmark-sero-chrome.png" in splash
    top = HTML[HTML.index("topbar-brand") : HTML.index("topbar-spacer")]
    assert "wordmark-navy.png" in top
    assert "wordmark-white.png" in top
    assert "wordmark-sero-chrome.png" not in top
    login = HTML[HTML.index("viewLogin") : HTML.index("viewApp")]
    assert "wordmark-sero-chrome.png" not in login
    assert 'SERO_APP_VERSION = "4.1.0"' in PROF


def test_eine_primaeraktion_und_faq_in_hilfe():
    assert 'id="homeScanOne"' in JS
    # 30.08.: Wirklich nur EINE Primäraktion. Stapel und „nur erfassen"
    # hängen am Plus-Knopf der Bodenleiste, nicht als zweite Knopfreihe.
    assert "home-sell-chips" not in JS
    assert 'id="homeScanBatch"' not in JS
    assert 'id="homeCollectOnly"' not in JS
    assert 'key: "faq"' not in JS
    assert "function faqAccordionHtml" in JS
    assert "faqAccordionHtml" in PROF
    assert "Aus Fotos" in JS
    assert '"Aus Fotos":' in JS
    assert "sell-tpl-text" in JS
    assert "Wert wird ab dem 3. Stück sichtbar" in JS
    assert '"Wert wird ab dem 3. Stück sichtbar":' in JS
    assert "Erlöse erscheinen hier" in JS
    assert '"Erlöse erscheinen hier":' in JS


def test_motion_kit_vorhanden():
    assert "animation: logoIn" in CSS
    after = CSS.split(".tab-cam::after")[1][:400]
    assert "orbbreathe 2.8s" not in after
    login_card = CLEAN[CLEAN.index("html.skin-clean .login-card"):]
    assert "animation: pageIn" in login_card[:500]
    assert "function morphColHubChart" in JS
    assert "function paintSalesSegInk" in JS
    assert "skel-stat" in PROF
    assert "prefers-reduced-motion" in CLEAN


def test_kein_auto_publish_kein_vierter_tab():
    assert "function startListingPrep" in JS
    assert 'data-tab="tabSales"' in HTML
    assert 'data-tab="tabHome"' in HTML
    assert 'data-tab="tabWish"' not in HTML
    assert "listingPaintKey" in JS
    assert "listingInputBusy" in JS
    assert "function flushGuestDrafts" in JS
    assert "function collectionFiltersActive" in JS
