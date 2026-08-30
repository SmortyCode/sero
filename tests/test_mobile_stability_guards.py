"""Quelltext-Wachen für Mobile-Stabilität (P0/P1)."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = (ROOT / "frontend" / "sero.js").read_text(encoding="utf-8")
MOB = (ROOT / "frontend" / "sero-mobile.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "sero.css").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def test_sero_mobile_geladen():
    assert "sero-mobile.js" in HTML
    assert "SeroMobile" in MOB
    assert "shouldAllowTabSwipe" in MOB
    assert "makeLatestWins" in MOB
    assert "installViewportController" in MOB


def test_keine_user_scalable_no():
    assert "user-scalable=no" not in HTML


def test_sheet_fit_behaelt_max_height():
    block = CSS.split(".sheet.sheet-fit", 1)[1][:240]
    assert "max-height: none" not in block
    assert "var(--vv-height" in CSS
    assert "overscroll-behavior-y: contain" in CSS


def test_kamera_synchron_ohne_timer():
    assert "setTimeout(() => $(welcher).click()" not in JS
    assert "if (inp) inp.click()" in JS


def test_latest_wins_und_supersede():
    assert "dashWins.begin()" in JS
    assert "colWins.begin()" in JS
    assert "salesWins.begin()" in JS
    assert "superseded" in JS


def test_collection_chunked():
    assert "SM.COL_CHUNK" in JS or "COL_CHUNK" in JS
    assert "col-sentinel" in JS
    assert "IntersectionObserver" in JS


def test_gesten_nutzen_sero_mobile():
    assert "SM.gestures.shouldAllowTabSwipe" in JS
    assert ".chips" in MOB


def test_android_back_controller():
    assert "resolveBackAction" in MOB
    assert "installBackController" in MOB
    assert "installBackController" in JS
    assert "App verlassen?" in JS
    assert '"publishing"' in JS or "publishing" in JS
    assert 'doAction(d.id, kind, b.dataset.v)' in JS
    assert "Upload läuft gerade" in JS
    assert "isDraftUploadBusy" in JS


def test_login_code_ueberlebt_app_wechsel():
    """Zurück aus Telegram darf den Code-Schritt nicht per Reload killen."""
    assert "reloadIfSessionLost" in JS
    assert "saveLoginPending" in JS
    assert "restoreLoginPending" in JS
    assert "sero_login_pending" in JS
    assert "onLoginScreen() || !state.me" in JS
    # Kein blindes location.reload bei 401 mehr in Collection/Dashboard
    assert "if (e.status === 401) location.reload()" not in JS


def test_offline_foto_text_ehrlich():
    assert "solange die App geöffnet" in JS


def test_title_assets_versioniert():
    assert "TITLE_V" in JS
    assert "assets/titles/sammlung.png?v=" in HTML
    assert re.search(r"sero\.css\?v=(\d+)", HTML)
    assert re.search(r"sero\.js\?v=(\d+)", HTML)


def test_localstorage_nur_adapter_oder_clear():
    for ln in JS.splitlines():
        if "localStorage." not in ln:
            continue
        assert (
            "getItem" in ln or "setItem" in ln or "removeItem" in ln or "clear()" in ln
        ), ln
