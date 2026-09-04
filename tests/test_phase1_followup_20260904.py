"""Phase-1 Follow-up 04.09.2026 — Ghost-Create, Freistellen, Listen-Brücke, PWA."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = (ROOT / "frontend" / "sero.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
API = (ROOT / "web" / "app_api.py").read_text(encoding="utf-8")
SRV = (ROOT / "web" / "server.py").read_text(encoding="utf-8")
MANI = (ROOT / "frontend" / "manifest.webmanifest").read_text(encoding="utf-8")


def test_ghost_create_requires_accepted_photo():
    assert "function captureFilesAccepted" in JS
    assert "function abortFailedCapture" in JS
    assert "function beginCaptureAttempt" in JS
    assert "MIN_CAPTURE_BYTES" in JS
    start = JS.index("function startScanMode")
    chunk = JS[start:start + 400]
    assert "beginCaptureAttempt()" in chunk
    stage = JS[JS.index("async function stageUpload"):JS.index("function openStagedSheet")]
    assert "captureFilesAccepted(files)" in stage
    commit = JS[JS.index("async function commitCamShots"):JS.index("function normalizeItemPhotos")]
    assert "captureFilesAccepted" in commit
    assert "Kein Foto übernommen. Sammlung unverändert." in JS
    cancel = JS[JS.index('el.addEventListener("cancel"'):JS.index("async function commitScanFast")]
    assert "abortFailedCapture" in cancel
    assert "pruefeAblage" in cancel
    assert "len(raw) < 32" in API


def test_cutout_settles_or_fails():
    assert "function waitCutoutSettled" in JS
    assert "CUTOUT_WAIT_MS" in JS
    frei = JS[JS.index("async function freistellenItemPhoto"):JS.index("async function restoreItemPhoto")]
    assert "waitCutoutSettled" in frei
    assert "Freistellen dauert zu lange — Original bleibt." in frei
    assert "Freistellen…" in frei
    assert "btnCutoutRetry" in frei
    assert 'toast(L("Freistellen fertig")' in frei


def test_capture_no_camera_offers_library():
    fb = JS[JS.index("function camFileFallback"):JS.index("function openCamCapture")]
    assert "Keine Kamera an diesem Gerät." in fb
    assert "Aus Mediathek" in fb
    assert "peNoCamLib" in fb
    assert "libraryInput" in fb


def test_collection_draft_bridge_not_connect_wall():
    prep = JS[JS.index("async function startListingPrep"):JS.index("function openQuickListSheet")]
    assert 'openItemDetail(item.id, "sell")' in prep
    assert "showEbayNotConnectedHint({ secondary: true })" in prep
    assert "startScanMode" not in prep
    assert "function openListFromCollection" in JS
    hint = JS[JS.index("function showEbayNotConnectedHint"):JS.index("async function listNow")]
    assert "Beim Entwurf bleiben" in hint
    rend = JS[JS.index("function renderSales"):JS.index("function emptyState")]
    assert "openListFromCollection" in rend
    assert "startScanMode" not in rend


def test_edit_photo_clean_pass():
    assert "function openPhotoEditor" in JS
    assert 'id="photoEditor"' in HTML
    assert 'id="peRestore"' in HTML
    more = JS[JS.index("function openItemMoreMenu"):JS.index("function closeDetail")]
    assert 'L("Foto bearbeiten")' in more
    rail = JS[JS.index("function pePaintRail"):JS.index("function pePaintPanel")]
    assert "cutout" in rail
    assert "disabled" not in rail


def test_pwa_manifest_and_csp_note():
    assert '"id": "/app/"' in MANI
    assert '"description":' in MANI
    assert "unsafe-inline bleibt nötig" in SRV
    assert (ROOT / "deploy" / "nginx-hsts.snippet.conf").is_file()
    hsts = (ROOT / "deploy" / "nginx-hsts.snippet.conf").read_text(encoding="utf-8")
    assert "Strict-Transport-Security" in hsts
    assert "serviceWorker" not in JS


def test_no_auto_publish_from_new_paths():
    assert "confirmPublishDraft" in JS
    prep = JS[JS.index("async function startListingPrep"):JS.index("function openQuickListSheet")]
    assert "confirmPublishDraft" not in prep
    assert "publish-drafts" not in prep
