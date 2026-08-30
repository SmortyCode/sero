"""18 cases: eBay pane stability, validation, no identity wall.

Vanilla JS source guards + logic tests. No React Testing Library.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = (ROOT / "frontend" / "sero.js").read_text(encoding="utf-8")
DETAIL = (ROOT / "frontend" / "sero-detail.js").read_text(encoding="utf-8")
MOB = (ROOT / "frontend" / "sero-mobile.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "sero.css").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
PRE = (ROOT / "web" / "preflight.py").read_text(encoding="utf-8")
API = (ROOT / "web" / "app_api.py").read_text(encoding="utf-8")
IDENT = (ROOT / "web" / "identity.py").read_text(encoding="utf-8")


def _fn(src: str, name: str) -> str:
    key = "function " + name
    i = src.index(key)
    rest = src[i + len(key) :]
    a = rest.find("\nfunction ")
    b = rest.find("\nasync function ")
    ends = [n for n in (a, b) if n >= 0]
    return src[i : i + len(key) + min(ends)] if ends else src[i:]


def test_f01_kein_volles_innerhtml_nach_preis_save():
    chunk = _fn(JS, "doAction")
    assert "DRAFT_LIGHT_ACTIONS" in JS
    assert "DRAFT_LIGHT_ACTIONS.has(action)" in chunk
    assert "preserve: true" in chunk and "ebayOnly" in chunk
    assert "await refreshDetail(true)" not in chunk


def test_f02_scroll_wird_gesichert():
    assert "function captureDetailViewState" in JS
    assert "function restoreDetailViewState" in JS
    assert "scrollTop" in _fn(JS, "captureDetailViewState")
    assert "restoreDetailViewState" in _fn(JS, "doAction")
    assert "restoreDetailViewState" in _fn(JS, "closeSheet")


def test_f03_hero_nicht_neu_bauen_wenn_signatur_gleich():
    assert "function detailHeroSignature" in JS
    paint = _fn(JS, "paintDetailHeroGallery")
    assert "det._heroSig" in paint
    assert "track.scrollLeft = 0" not in paint
    rend = _fn(JS, "renderDetail")
    assert "keepShell" in rend
    assert "opts.ebayOnly" in rend


def test_f04_galerie_index_bleibt():
    paint = _fn(JS, "paintDetailHeroGallery")
    assert "keepIdx" in paint
    assert "photoIdx" in paint


def test_f05_listener_cleanup_gallery_swipe():
    gal = _fn(JS, "bindDetailGallery")
    assert "removeEventListener" in gal
    sw = _fn(JS, "bindDetailPaneSwipe")
    assert "removeEventListener" in sw
    rend = _fn(JS, "renderDetail")
    assert "skipHeroBind" in rend


def test_f06_preis_sheet_gleiche_instanz():
    inp = _fn(JS, "openInput")
    assert "state._inputKey" in inp
    assert "recede: false" in inp
    assert "state._inputBusy" in inp


def test_f07_eine_mutation_bei_uebernehmen():
    inp = _fn(JS, "openInput")
    assert "state._inputBusy" in inp
    act = _fn(JS, "doAction")
    assert "_draftActionTail" in act
    sheet = _fn(JS, "openSheet")
    assert "save.disabled = true" in sheet


def test_f08_ios_tastatur_visual_viewport():
    assert "interactive-widget=overlays-content" in HTML
    assert "--vv-keyboard" in MOB
    assert "bottom: var(--vv-keyboard" in CSS
    assert "html.vv-keyboard #viewApp.recede" in CSS
    assert "wantRecede" in _fn(JS, "openSheet")


def test_f09_keine_roten_fehler_waehrend_loading():
    assert 'type: "loading"' in DETAIL
    apply = _fn(JS, "applyListingFieldHints")
    assert "opts.loading" in apply
    cta = _fn(JS, "syncPublishCta")
    assert "v.loading" in cta


def test_v01_keine_identitaets_wand():
    chunk = _fn(JS, "renderDraftSection")
    assert "lr-gate" not in chunk
    assert "Identität bestätigen" not in chunk
    assert "Noch nicht bereit zum Veröffentlichen" not in chunk
    assert "Identität bestätigen" not in JS
    assert "confirm_identity" not in _fn(JS, "handleDraftAction")
    assert '"identity", "REVIEW"' not in PRE


def test_delete_once_pending_lock():
    chunk = _fn(JS, "removeItemWithUndo")
    assert "pendingDeletes" in chunk
    assert "/delete" in chunk
    assert "status: \"inflight\"" in chunk
    assert "dismissSheetNow" in chunk
    assert "hideActions: true" in _fn(JS, "openItemMoreMenu")
    assert "pointer-events: none" in CSS


def test_price_save_clears_bitte_pruefen():
    assert "function parseEuro" in DETAIL
    val = _fn(DETAIL, "listingValidation")
    assert "parseEuro(draft" in val
    assert 'message: "Bitte prüfen"' not in val


def test_ebay_cta_portal_fixed():
    assert 'id="detailCtaDock"' in HTML
    assert "function syncDetailCtaDock" in JS
    assert "position: fixed" in CSS
    assert "--vv-keyboard" in CSS
    assert "html.skin-clean .d-ebay-cta-wrap { display: none; }" in (
        ROOT / "frontend" / "sero-clean.css"
    ).read_text(encoding="utf-8") or "d-ebay-cta-wrap { display: none" in (
        ROOT / "frontend" / "sero-clean.css"
    ).read_text(encoding="utf-8")


def test_v02_fehler_am_feld():
    assert "function applyListingFieldHints" in JS
    assert "function fieldElForIssue" in JS
    assert "lr-field-msg" in CSS
    assert "lr-miss" in _fn(JS, "applyListingFieldHints")


def test_v03_unsichere_ki_gelb_nicht_blockierend():
    assert "KI_RICHTWERT" in DETAIL
    assert "o.blocking === false" in DETAIL or "blocking === false" in DETAIL
    assert ".lr-warn" in CSS
    assert "#c9a227" in CSS
    val = _fn(DETAIL, "listingValidation")
    assert 'fieldId: "price"' in val
    assert 'message: "Bitte prüfen"' not in val


def test_v04_fehlender_preis_ist_feld_kein_riesenblock():
    chunk = _fn(JS, "renderDraftSection")
    assert "Preis festlegen" in chunk
    assert "lr-preflight-list" not in chunk
    assert 'id="lr-price"' in chunk


def test_v05_publish_kompakt():
    chunk = _fn(JS, "renderDraftSection")
    assert "Noch {0} Angaben" in chunk
    assert 'id="lr-publish"' in chunk


def test_v06_tipp_auf_gesperrten_publish_scrollt():
    hand = _fn(JS, "handleDraftAction")
    assert "jumpPreflightField" in hand
    assert "iss.blocking" in hand
    assert "confirmPublishDraft" in hand


def test_v07_eine_validierungsquelle():
    assert "function listingValidation" in DETAIL
    assert "function listingIssue" in DETAIL
    assert "fieldId" in DETAIL
    assert "listingValidationFor" in JS
    assert "field_id" in PRE
    assert "pricing_ready" in IDENT


def test_r01_abort_dedup_generation():
    assert "const detailWins = SM.makeLatestWins()" in JS
    assert "const preflightWins = SM.makeLatestWins()" in JS
    assert "makeInflightDedup" in MOB
    ref = _fn(JS, "refreshDetail")
    assert "detailWins.begin()" in ref
    assert "ticket.signal" in ref
    assert "e.superseded" in ref
    assert "preflightDedup" in JS


def test_r02_col_get_nach_await_keine_doppel_ebay_mutation():
    assert "def col_save_identity" in API
    assert "frisch = store.get_draft(draft_id)" in API
    start = API.index('elif action == "upload"')
    end = API.index('elif action == "save"')
    pub = API[start:end]
    assert "preflight_draft" in pub
    assert "app_run_upload" in pub


def test_kein_react():
    for blob in (JS, DETAIL, HTML):
        assert "useEffect" not in blob
        assert "ReactDOM" not in blob


def test_pins_hochgezaehlt():
    js_v = int(re.search(r"sero\.js\?v=(\d+)", HTML).group(1))
    det_v = int(re.search(r"sero-detail\.js\?v=(\d+)", HTML).group(1))
    mob_v = int(re.search(r"sero-mobile\.js\?v=(\d+)", HTML).group(1))
    css_v = int(re.search(r"sero\.css\?v=(\d+)", HTML).group(1))
    clean_v = int(re.search(r"sero-clean\.css\?v=(\d+)", HTML).group(1))
    assert js_v >= 235
    assert det_v >= 6
    assert mob_v >= 4
    assert css_v >= 151
    assert clean_v >= 30


def test_listing_kein_remount_bei_sheet_input():
    assert "function listingInputBusy" in JS
    assert "function listingPaintKey" in JS
    assert "function flushQueuedDetailPaint" in JS
    assert "skipListingPaint" in _fn(JS, "renderDetail")
    ref = _fn(JS, "refreshDetail")
    assert "listingInputBusy()" in ref
    assert "listingPaintKey" in ref
    act = _fn(JS, "doAction")
    assert "listingInputBusy()" in act
    assert "state._detailPaintQueued" in act
    close = _fn(JS, "closeSheet")
    assert "flushQueuedDetailPaint" in close


def test_ebay_only_aktualisiert_listing_block():
    rend = _fn(JS, "renderDetail")
    assert 'block.innerHTML = ebayPane' in rend or "block.innerHTML = ebayPane" in rend
    assert 'id="detailListingBlock"' in rend
    assert "opts.ebayOnly" in rend


def test_offermin_kein_keystroke_remount():
    chunk = _fn(JS, "wireDraftSection")
    assert "boMin.oninput" not in chunk
    assert "boMin.onblur = saveBoMin" in chunk
    assert "boMin.onchange = saveBoMin" in chunk


def test_toast_faengt_keine_tipps_wenn_unsichtbar():
    block = CSS.split("#toast {", 1)[1].split("#toast.show", 1)[0]
    assert "pointer-events: none" in block
    assert "pointer-events: auto" not in block
    assert "pointer-events: auto" in CSS.split("#toast.show", 1)[1][:120]


def test_sheet_input_kein_ios_zoom():
    inp = _fn(JS, "openInput")
    assert "autocomplete=\"off\"" in inp
    assert "enterkeyhint=" in inp
    assert "font-size: 17px" in CSS
    assert "touch-action: manipulation" in CSS
