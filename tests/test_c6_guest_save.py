"""C6: Login erst beim Speichern — Scan und lokaler Entwurf ohne Session."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = (ROOT / "frontend" / "sero.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
CLEAN = (ROOT / "frontend" / "sero-clean.css").read_text(encoding="utf-8")


def test_c6_boot_geht_ohne_session_in_die_app():
    assert "function enterGuestApp" in JS
    assert "function isGuest" in JS
    boot = JS[JS.index("async function boot()"): JS.index("function paintTopAva")]
    assert "enterGuestApp()" in boot
    assert "e.status === 401" in boot
    login_wall = '$("viewLogin").hidden = false'
    assert boot.index("enterGuestApp()") < boot.index(login_wall)


def test_c6_login_nur_beim_speichern_email_only():
    assert "function openSaveLoginSheet" in JS
    assert "function needAccountForSave" in JS
    assert "Anmelden zum Speichern" in JS
    assert "Der Entwurf bleibt auf diesem Gerät." in JS
    assert '"Anmelden zum Speichern":' in JS
    chunk = JS[JS.index("function openSaveLoginSheet"): JS.index("async function fileToGuestDataUrl")]
    assert "if (!isGuest()) return" in chunk
    assert 'L("E-Mail")' in chunk
    assert 'L("Später")' in chunk
    assert 'L("Weiter")' in chunk
    assert "/api/login-code" in chunk
    assert "/api/signup" in chunk
    assert "/api/login-verify" in chunk
    assert "google" not in chunk.lower()
    assert "apple" not in chunk.lower()
    assert "password" not in chunk.lower()
    assert "passwort" not in chunk.lower()
    assert "adminsero" not in chunk.lower()


def test_c6_entwurf_bleibt_lokal():
    assert "function keepGuestDraftFromFiles" in JS
    assert "function applyGuestItems" in JS
    assert "function flushGuestDrafts" in JS
    assert "sero_guest_drafts_v1" in JS
    assert "guest-" in JS
    commit = JS[JS.index("async function commitCamShots"): JS.index("function normalizeItemPhotos")]
    assert "keepGuestDraftFromFiles" in commit
    assert "isGuest()" in commit


def test_c6_flush_nach_login_sichtbar_ohne_datenverlust():
    flush = JS[JS.index("async function flushGuestDrafts"): JS.index("function saveLoginPending")]
    assert "/api/app/collection/items" in flush
    assert "publish" not in flush.lower()
    assert "guestDraftRows()" in flush
    assert "latest.filter" in flush
    assert "Entwürfe werden gespeichert" in flush
    assert "Entwurf konnte nicht gespeichert werden" in flush
    assert "Analyse läuft" in flush
    assert "break" in flush
    assert "kept.push" not in flush
    enter = JS[JS.index("async function enterAppAfterSession"): JS.index("$(\"loginNext\")")]
    assert "flushGuestDrafts" in enter
    assert "Anmeldung fehlgeschlagen" in enter
    boot = JS[JS.index("async function boot()"): JS.index("function paintTopAva")]
    assert "flushGuestDrafts" in boot
    assert ".guest-save-err" in CLEAN
    assert ".guest-save-status" in CLEAN


def test_c6_gate_an_konto_aktionen():
    assert "if (needAccountForSave()) return" in JS
    list_now = JS[JS.index("async function listNow"): JS.index("function listingTippFromItem")]
    assert "needAccountForSave" in list_now
    prep = JS[JS.index("async function startListingPrep"): JS.index("function openQuickListSheet")]
    assert "needAccountForSave" in prep


def test_c6_pins_und_banner():
    assert "sero.js?v=253" in HTML
    assert "sero-clean.css?v=41" in HTML
    assert ".guest-save-bar" in CLEAN
    assert ".guest-save-btn" in CLEAN
    assert "guestSaveBtn" in JS
