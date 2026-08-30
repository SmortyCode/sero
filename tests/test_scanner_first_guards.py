"""Scanner-first: Copy, Nav, CTA-Semantik, Kamera — ohne eBay-Calls."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = (ROOT / "frontend" / "sero.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "sero.css").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
API = (ROOT / "web" / "app_api.py").read_text(encoding="utf-8")
PRE = (ROOT / "web" / "preflight.py").read_text(encoding="utf-8")


def test_01_scan_button_opens_camera_sync_and_has_label():
    assert 'id="btnCamera"' in HTML
    # Der Plus-Knopf trägt kein Wort mehr — die Beschriftung hängt am aria-label.
    assert 'aria-label="Scannen"' in HTML
    assert 'L("Scannen")' in JS
    # Kamera im gleichen Gesture: startScanMode öffnet Input vor Tab-Wechsel
    assert "$(\"btnCamera\").onclick" in JS
    assert "function startScanMode" in JS
    i = JS.index("function startScanMode")
    chunk = JS[i:i + 720]
    assert "cameraInput" in chunk
    assert "openCamCapture" in chunk
    assert "function openCamCapture" in JS
    assert "libraryInput" in HTML
    assert 'id="libraryInput" type="file" accept="image/*" multiple hidden>' in HTML
    assert "capture" not in HTML.split('id="libraryInput"', 1)[1][:80]
    assert "MAX_LISTING_PHOTOS" in JS
    assert "function commitScanFast" in JS
    assert "function openScanDoneSheet" in JS
    assert "tab-cam.active" in CSS or ".tab-cam.active" in CSS
    assert 'id="cameraInput"' in HTML
    assert 'id="cameraInput" type="file" accept="image/*" capture="environment" hidden>' in HTML
    assert "multiple hidden" not in HTML.split('id="cameraInput"', 1)[1][:120]
    assert 'id="camFlip"' in HTML
    assert 'id="camFlash"' in HTML
    assert 'id="scanFinder"' in HTML
    assert "scan-finder" in HTML
    assert "scan-br-tl" in HTML
    # Das Plus öffnet das Scan-Menü; erst die Zeile darin startet Kamera
    # oder Mediathek — beide im bestehenden Ablauf.
    assert '$("btnCamera").onclick = () => {\n  toggleScanMenu();\n};' in JS
    assert 'id="scanMenu"' in HTML
    assert 'id="scanMenuCam"' in HTML
    assert 'id="scanMenuLib"' in HTML
    assert "function openScanMenu" in JS
    assert "function closeScanMenu" in JS
    assert 'scanMenuPick(() => startScanMode("SELL_SINGLE"))' in JS
    assert "scanMenuPick(openScanLibrary)" in JS
    assert "function openScanLibrary" in JS
    # Doppeltipp-Schutz: kein zweiter Kamera- oder Dateidialog.
    assert "function scanMenuPick" in JS
    assert "scanMenuPick._last" in JS
    assert '"Foto machen": "Take photo"' in JS
    assert '"Aus Mediathek auswählen": "Choose from library"' in JS
    assert '$("emptyAdd").onclick = () => startScanMode("SELL_SINGLE")' in JS


def test_02_collect_only_skips_ensure_draft():
    assert 'state.scanIntent === "COLLECT_ONLY"' in JS
    i = JS.index("async function ensureItemDraft")
    chunk = JS[i:i + 350]
    assert "COLLECT_ONLY" in chunk


def test_03_scan_result_leads_to_review_not_publish_text():
    assert 'L("Entwurf prüfen")' in JS
    i = JS.index("function showScanResult")
    end = JS.index("function showScanFailed")
    chunk = JS[i:end]
    assert "Entwurf prüfen" in chunk
    assert "Jetzt bei eBay veröffentlichen" not in chunk


def test_scan_fast_commit_ohne_ebay_listing():
    """Kamera-Scan hält Blobs lokal, Nutzer wählt Hero — kein stilles eBay-Listing."""
    start = JS.index("async function commitScanFast")
    end = JS.index("async function stageUpload")
    chunk = JS[start:end]
    assert "addCamFiles" in chunk
    assert "/list" not in chunk
    assert "ensureItemDraft" not in chunk
    assert "function openScanDoneSheet" in chunk
    assert "Weiter scannen" in chunk
    assert "Mit dem Entwurf fortsetzen" in chunk
    assert "In der Sammlung anschauen" in chunk
    assert "function openCamCapture" in JS
    assert "function openCamSheet" in JS
    assert 'L("Aus Mediathek")' in JS
    assert "MAX_LISTING_PHOTOS" in JS
    staged = JS[JS.index("function openStagedSheet"):JS.index("function openBatchSheet")]
    assert "items-from-stage" in staged
    assert "openScanDoneSheet" in staged
    assert "sortiert.unshift" in staged
    assert "Weiteres Foto hinzufügen" in staged
    assert 'L("Fertig")' in staged
    assert "cameraInput" in staged
    assert "fileInput" in staged
    assert "addingToItem" in JS
    assert '"Mit dem Entwurf fortsetzen":' in JS
    assert '"In der Sammlung anschauen":' in JS


def test_04_only_publish_cta_is_jetzt_bei_ebay():
    assert "data-dact=\"upload\"" in JS
    assert "Noch {0} Angaben" in JS
    assert 'id="lr-publish"' in JS
    # Confirm-Sheet bleibt die einzige Stelle mit dem vollen Publish-Satz
    i = JS.index("async function confirmPublishDraft")
    end = JS.index("function handleDraftAction")
    chunk = JS[i:end]
    assert "Jetzt bei eBay veröffentlichen" in chunk
    assert "claim_or_create_intent" in API
    assert "preflight_draft" in API
    assert "function confirmPublishDraft" in JS


def test_05_preflight_blocks_uncertain_analyzing():
    """Analyse und unklarer Publish-Stand bleiben hart — interne Identität nicht."""
    assert "ANALYZING" in PRE
    assert "UNCERTAIN" in PRE
    assert "publish_uncertain" in PRE
    assert '"identity", "REVIEW"' not in PRE
    assert '@router.get("/draft/{draft_id}/preflight")' in API


def test_08_portfolio_price_not_auto_tpl():
    # ensureItemDraft darf Marktwert als Vorschlag setzen, aber Upload braucht
    # expliziten Confirm — kein stiller Publish.
    assert "confirmPublishDraft" in JS
    assert "trackFunnel(\"publish_started\")" in JS


def test_09_incompatible_formats_in_preflight():
    assert "FIXED_PRICE" in PRE and "auction1" in PRE
    assert "Auktion immer mit Stückzahl 1" in PRE
    assert "Preisvorschlag nur bei Sofortkauf" in PRE


def test_login_and_nav_copy():
    assert "Scannen. Prüfen. Bei eBay verkaufen." in HTML
    assert "Fertiger eBay-Entwurf direkt nach dem Scan" in HTML
    assert 'tab-lab">Verkaufen</span>' in HTML
    assert 'aria-label="Verkaufen"' in HTML
    assert "SERO erkennt dein Produkt und bereitet dein eBay-Angebot vor." in HTML


def test_home_hero_and_listings_default():
    assert "function homeSellHero" in JS
    assert "Fotografieren. Prüfen. Bei eBay verkaufen." in JS
    assert "Artikel fotografieren" in JS
    assert 'salesBucket: "draft"' in JS
    assert 'data-b="active">Aktiv' in HTML
    assert '"Verkaufen":' in JS
    i = JS.index('if (id === "tabSales")')
    chunk = JS[i:i + 280]
    assert 'state.salesBucket = "draft"' in chunk
    assert "function openBulkReviewSheet" in JS
    assert "Auf eBay hochladen" in JS
    assert "{0} Stück auf eBay hochladen" in JS
    assert "Erstes Listing vorbereiten" in JS
    assert "home-sell-hero" in CSS


def test_no_auf_ebay_listen_as_publish_button():
    """Publish-Knopf im Draft: kompakt, nicht 'Auf eBay listen'."""
    i = JS.index("function renderDraftSection")
    end = JS.index("function drow(")
    chunk = JS[i:end]
    assert "Noch {0} Angaben" in chunk
    assert 'id="lr-publish"' in chunk
    assert "data-dact=\"upload\"" in chunk
    assert "Jetzt live listen" not in chunk
    assert "Auf eBay listen" not in chunk


def test_pins_bumped():
    assert re.search(r"sero\.css\?v=(\d+)", HTML)
    assert int(re.search(r"sero\.css\?v=(\d+)", HTML).group(1)) >= 132
    assert int(re.search(r"sero-dark\.css\?v=(\d+)", HTML).group(1)) >= 19
    assert int(re.search(r"sero\.js\?v=(\d+)", HTML).group(1)) >= 195


def test_no_ebay_corporate_logo_asset():
    assets = ROOT / "frontend" / "assets"
    names = [p.name.lower() for p in assets.rglob("*") if p.is_file()]
    bad = [n for n in names if "ebay" in n and n.endswith((".png", ".svg", ".jpg", ".webp"))]
    assert not bad, f"Keine eBay-Logo-Assets ohne Freigabe: {bad}"


def test_10_listing_review_a_to_d():
    """Review A–D in einem Screen, Controls an data-dact gebunden."""
    i = JS.index("function renderDraftSection")
    end = JS.index("function drow(")
    chunk = JS[i:end]
    assert "A · Bilder" in chunk
    assert "B · Produkt" in chunk
    assert "C · Angebot" in chunk
    assert "D · Versand & Regeln" in chunk
    assert 'id="lr-photos"' in chunk
    assert 'id="lr-product"' in chunk
    assert 'id="lr-offer"' in chunk
    assert 'id="lr-shipping"' in chunk
    assert 'data-dact="aspect"' in chunk
    assert 'drow("cat"' in chunk or 'data-dact="cat"' in chunk
    assert 'data-dact="cardsearch"' in chunk
    assert "reviewGateBlocked" in JS
    assert "fillPreflightChecklist" in JS
    assert "jumpPreflightField" in JS


def test_11_publish_cta_kompakt_ohne_identitaets_wand():
    i = JS.index("function renderDraftSection")
    end = JS.index("function drow(")
    chunk = JS[i:end]
    assert "Noch {0} Angaben" in chunk
    assert 'id="lr-publish"' in chunk
    assert "data-dact=\"upload\"" in chunk
    assert "lr-gate" not in chunk
    assert "Identität bestätigen" not in chunk
    assert "Erst Angaben prüfen" not in chunk
    assert "reviewGateBlocked" in JS


def test_12_manual_card_search_reachable():
    assert "function openCardSearch" in JS
    assert "btnCardSearch" in JS
    assert "openCardSearch(item)" in JS
    assert 'data-dact="cardsearch"' in JS
    assert "/collection/item/" in JS and "/match" in JS


def test_13_portfolio_ki_asking_not_auto_listing_price():
    assert "function listingTippFromItem" in JS
    i = JS.index("function listingTippFromItem")
    chunk = JS[i:i + 700]
    assert 'price_source === "estimate"' in chunk
    assert 'price_source === "manual"' in chunk
    assert "ASKING_ONLY" in chunk
    assert "KI_RICHTWERT" in chunk
    # ensureItemDraft nutzt listingTippFromItem, nicht rohes est_value
    j = JS.index("async function ensureItemDraft")
    ens = JS[j:j + 1200]
    assert "listingTippFromItem(item)" in ens
    assert "item.est_value != null ? Number(item.est_value)" not in ens


def test_14_category_and_aspects_backend():
    assert 'elif action == "aspect"' in API
    assert 'elif action == "cat"' in API
    assert "/category-suggest" in API
    assert "REVISION_CONFLICT" in API
    assert "/sell-template" in API
    assert "/scan-session" in API


def test_15_confirm_only_publish_wording():
    i = JS.index("async function confirmPublishDraft")
    end = JS.index("function handleDraftAction")
    chunk = JS[i:end]
    assert "Jetzt bei eBay veröffentlichen" in chunk
    assert "jumpPreflightField" in chunk or "lr-pf-jump" in chunk


# ── Phase 3 Audit ──────────────────────────────────────────

def test_16_batch_group_editor_before_analysis():
    """Batch: Preview → editierbare Gruppen → Confirm, kein stilles loadCollection als Abschluss."""
    assert "scan-batch-preview" in JS
    assert "scan-batch-confirm" in JS
    assert "function openBatchGroupEditor" in JS
    assert "data-bg-split" in JS
    assert "data-bg-merge" in JS
    assert "data-bg-main" in JS
    assert "scan-batch-preview" in API
    assert "scan-batch-confirm" in API
    assert "BatchConfirmBody" in API
    # Abschluss: Queue / Listings, nicht nur toast + loadCollection
    i = JS.index("function openBatchGroupEditor")
    chunk = JS[i:i + 2200]
    assert "loadScanSession" in chunk
    assert 'switchTab("tabCollection")' in chunk
    assert "Warteschlange" in chunk or "scan_session" in chunk


def test_17_persistent_scan_queue_ui():
    assert "function loadScanSession" in JS
    assert "function renderScanQueue" in JS
    assert "Scan-Warteschlange" in JS
    assert "Prüfung nötig" in JS
    assert "Kein Preis" in JS
    assert 'id="salesQueue"' in JS or "salesQueue" in JS
    assert "queue_status_from_item" in (ROOT / "web" / "scan_session.py").read_text(encoding="utf-8")


def test_18_selective_bulk_publish_only_selection():
    assert "selectedDrafts" in JS
    assert "data-sel-draft" in JS
    assert "Zusammenfassung vor dem Publish" in JS
    assert "function openBulkReviewSheet" in JS
    assert "PublishDraftsBody" in API
    i = JS.index("async function openBulkReviewSheet")
    chunk = JS[i:i + 5500]
    assert "draft_ids" in chunk
    assert "preflight" in chunk.lower()
    assert "/api/app/draft/${r.draft_id}/preflight" in chunk
    assert 'post("/api/app/sales/publish-drafts",' in chunk
    assert 'post("/api/app/sales/publish-drafts")' not in chunk
    assert "{0} Stück auf eBay hochladen" in chunk
    assert "publish_uncertain" not in chunk.lower() or "auto" not in chunk.lower()
    assert 'closest("#bulkPublish")' in JS


def test_19_photo_order_and_main_in_review():
    assert 'elif action == "imgorder"' in API
    assert 'elif action == "imgmain"' in API
    assert 'data-dact="imgswap"' in JS
    assert 'data-dact="imgmain"' in JS
    assert "lr-ph-strip" in JS
    assert "imgorder" in JS


def test_20_discard_decoupled_from_ensure_draft():
    i = JS.index('act === "discard"')
    chunk = JS[i:i + 900]
    assert "_skipEnsureDraft" in chunk
    assert "Listing-Entwurf verwerfen?" in chunk
    assert "Sammlung" in chunk


def test_22_scan_oom_guards():
    """18.08. Contabo: OOM während Freistellen → UI ewig „wird analysiert“."""
    i = API.index("async def analyze_collection_item")
    chunk = API[i:i + 6000]
    assert "cut_task" in chunk
    assert "listing_task" in chunk
    assert "glance_scan" in chunk
    assert "_listing_task" not in chunk
    assert "Stelle Karte frei" in chunk
    assert "analyzer.analyze" in chunk
    assert "Kindprozess" in chunk
    assert "erster_lauf" in API
    assert "scans_retten_einmal" in API
    assert "n_workers = 1 if _production()" in API
    assert "if not _production():" in API
    assert "_spawn(_warm_model())" in API
    # Warmup nur auf dem Mac, nicht auf Contabo
    warm = API.index("if not _production():")
    assert "_spawn(_warm_model())" in API[warm:warm + 80]
    assert "timeout=90.0" in (ROOT / "web" / "cardscan.py").read_text(encoding="utf-8")
    assert "def rembg_max_side" in (ROOT / "web" / "cardscan.py").read_text(encoding="utf-8")
    cs = (ROOT / "web" / "cardscan.py").read_text(encoding="utf-8")
    assert "def _cutout_via_child" in cs
    assert (ROOT / "web" / "cutout_worker.py").is_file()

