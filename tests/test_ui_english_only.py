"""Waechter fuer den Master 30.08. nachmittags: English-only, Hell, drei Reiter.

Die App laeuft nur noch auf Englisch. Der deutsche Text bleibt der Schluessel,
STR_EN legt die Oberflaeche darueber. Faellt ein Schluessel weg, steht die
Stelle wieder deutsch da -- ohne roten Test wuerde das niemand merken.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = (ROOT / "frontend" / "sero.js").read_text(encoding="utf-8")
PROF = (ROOT / "frontend" / "sero-profile.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
CLEAN = (ROOT / "frontend" / "sero-clean.css").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "sero.css").read_text(encoding="utf-8")
MANI = json.loads((ROOT / "frontend" / "manifest.webmanifest").read_text(encoding="utf-8"))

TABELLE = ROOT / "tests" / "_lang_table.json"


def test_sprache_ist_festgenagelt():
    assert 'const LANG = "en";' in JS
    assert "navigator.language" not in JS.split("const STR_EN")[0].split("applyTheme")[-1]
    assert "const _langPref" not in JS
    assert '<html lang="en"' in HTML


def test_sprachauswahl_ist_weg():
    assert "apLang" not in PROF
    assert "langValueLabel" not in PROF
    assert 'pushPane("appear", "Darstellung & Sprache"' not in PROF
    assert 'pushPane("appear", "Darstellung"' in PROF


def test_manifest_englisch():
    assert MANI["lang"] == "en"
    assert "Deine Karten" not in MANI["name"]
    assert MANI["name"] == "SERO — Your cards. Your market."


def test_copy_tabelle_aus_dem_master():
    """Die Wortliste, die Sven vorgegeben hat -- zeichengenau."""
    want = json.loads(TABELLE.read_text(encoding="utf-8"))
    block = JS[JS.index("const STR_EN = {"):JS.index("\nconst L = (s) =>")]
    fehlt = []
    for de, en in want.items():
        # Der letzte Eintrag gewinnt in einem JS-Objektliteral.
        marke = '"%s": "%s"' % (de, en)
        if marke not in block:
            fehlt.append(marke)
    assert not fehlt, "STR_EN weicht vom Master ab: " + ", ".join(fehlt)


def test_verkaufen_fuehrt_zum_listen_nicht_zur_kamera():
    """Fotografieren wohnt allein im Scan-Reiter."""
    assert "function goListItem" in JS
    i = JS.index("function goListItem")
    assert 'switchTab("tabScan")' in JS[i:i + 200]
    verkauf = JS[JS.index("function renderSales"):]
    verkauf = verkauf[:verkauf.index("function emptyState")]
    assert 'L("Stück listen")' in verkauf
    assert 'aktion: "Stück listen"' in verkauf
    assert 'aktion: "Fotografieren"' not in verkauf
    assert "sales-foto-pill" in verkauf


def test_sammlung_kennt_keinen_entwurf():
    assert '["hold", L("Bestand")]' in JS
    assert '["draft", L("Entwurf")]' not in JS
    assert ".gstat.hold" in CSS


def test_scan_home_ohne_tote_knoepfe():
    assert "btnScanBatch" not in JS
    assert "btnScanCollectOnly" not in JS
    assert "Mehrere Produkte scannen" not in HTML
    assert "html.skin-clean #tabScan .page-scroll" in CLEAN
    assert "overflow-x: hidden" in CLEAN


def test_hell_bleibt_hell():
    for sel in (
        "html.skin-clean.force-light .d-hero-title",
        "html.skin-clean.force-light .impact-value",
        "html.skin-clean.force-light .empty.empty-well",
        "html.skin-clean.force-light .login-card input",
        "html.skin-clean.force-light .sales-bulk-bar",
        "html.skin-clean.force-light .d-sell-input",
        "html.skin-clean.force-light .d-seg-sticky",
    ):
        assert sel in CLEAN, sel


def test_kein_sero_schriftzug_in_der_chrome():
    """Splash, Kopfzeile und Reiter tragen nur den fetten Glyph."""
    splash = HTML[HTML.index('id="splash"'):HTML.index("viewLogin")]
    assert "wordmark-sero-chrome.png" in splash
    kopf = HTML[HTML.index('class="topbar"'):HTML.index('id="tabHome"')]
    assert "wordmark-navy.png" in kopf and "wordmark-white.png" in kopf
    assert "SR-Monogramm" not in HTML
    for name in ("wordmark-navy.png", "wordmark-white.png", "wordmark-sero-chrome.png",
                 "app-icon.png", "apple-touch-icon.png",
                 "startup-1170x2532.png", "startup-780x1688.png"):
        assert (ROOT / "frontend" / "assets" / name).is_file(), name


def test_pins_nach_dem_master_hochgezaehlt():
    import re
    for asset, floor in (("sero.js", 258), ("sero.css", 167), ("sero-clean.css", 46),
                         ("sero-profile.js", 25), ("manifest.webmanifest", 9)):
        m = re.search(re.escape(asset) + r"\?v=(\d+)", HTML)
        assert m and int(m.group(1)) >= floor, f"{asset} Pin zu niedrig"
    # Die Logo-Dateien sind neu -- ohne neuen Pin liefert der Cache das alte Bild.
    for asset, floor in (("wordmark-navy.png", 3), ("wordmark-white.png", 3),
                         ("wordmark-sero-chrome.png", 6), ("app-icon.png", 8),
                         ("startup-1170x2532.png", 3)):
        m = re.search(re.escape(asset) + r"\?v=(\d+)", HTML)
        assert m and int(m.group(1)) >= floor, f"{asset} Pin zu niedrig"


def test_kein_loch_ohne_str_en_und_keine_anthrazit_insel():
    """Laeuft den Node-Waechter: STR_EN vollstaendig, Hell wirklich hell."""
    r = subprocess.run(
        ["node", str(ROOT / "tests" / "_ui_en_light_audit.js")],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    if r.returncode != 0:
        sys.stdout.write(r.stdout)
        sys.stderr.write(r.stderr)
    assert r.returncode == 0, r.stderr or r.stdout
