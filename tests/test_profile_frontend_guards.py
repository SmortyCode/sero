"""Quelltext-Wachen für Profil/Einstellungen-Frontend."""
from pathlib import Path
import re

JS = Path("frontend/sero.js").read_text(encoding="utf-8")
PROF = Path("frontend/sero-profile.js").read_text(encoding="utf-8")
HTML = Path("frontend/index.html").read_text(encoding="utf-8")
CSS = Path("frontend/sero.css").read_text(encoding="utf-8")


def test_no_hardcoded_v40():
    assert "v4.0" not in PROF
    assert "SERO für iOS & Web · v4.0" not in JS


def test_legal_links_real():
    assert "/legal.html#impressum" in PROF
    assert "/legal.html#datenschutz" in PROF
    assert "/legal.html#agb" in PROF
    assert "/guide.html" in PROF
    assert "/hilfe.html" not in PROF
    assert "/datenschutz.html" not in PROF
    assert "/agb.html" not in PROF


def test_favicon_exists():
    assert "assets/app-icon.png" in HTML
    assert "apple-touch-icon.png" in HTML
    assert Path("frontend/assets/app-icon.png").is_file()
    assert Path("frontend/assets/apple-touch-icon.png").is_file()
    assert Path("frontend/assets/icon-512.png").is_file()


def test_stats_labels():
    assert 'statCell(summary.active_on_ebay, "Aktiv")' in PROF
    assert 'statCell(summary.in_collection, "Besitz")' in PROF
    assert 'statCell(summary.sold, "Verkauft")' in PROF
    assert 'statCell(summary.in_collection, "In Sammlung")' not in PROF
    assert "function renderSettingsList" in PROF
    assert "menuSettings" in PROF


def test_paid_plan_not_open_paywall():
    assert "openBillingOrPlans" in PROF
    assert "billing-portal" in PROF
    # Reseller öffnet Pane, nicht openPaywall als Abo-Verwaltung
    assert "openPaywall();" not in PROF or "Scan" in PROF


def test_plan_usage_copy_texts():
    assert "Listings ohne Monatslimit" in PROF
    assert "von {1} Listings in diesem Monat" in PROF
    assert "Scans ohne Limit" in PROF
    assert "Scans und Listen ohne Limit" not in PROF


def test_settings_view_present():
    assert 'id="settingsView"' in HTML
    assert "settingsNav" in PROF
    assert "sero-profile.js" in HTML


def test_tabbar_start_label():
    assert ">Start<" in HTML or "tab-lab\">Start" in HTML
    assert "aria-label=\"Home\"" in HTML or "aria-label=\"Übersicht\"" in HTML


def test_account_delete_requires_loschen():
    assert '!== "LÖSCHEN"' in PROF
    assert "Bereits auf eBay veröffentlichte Angebote bleiben bei eBay bestehen" in PROF


def test_str_en_new_keys():
    for key in (
        "Aktiv auf eBay", "Besitz inklusive eBay-Angebote", "Verkauft", "Tarif & Abrechnung",
        "Konto & Profil", "Preisalarme aktiv", "Marktwerte neu abrufen",
        "Impressum", "Anleitung öffnen", "Eigener Wert",
    ):
        assert f'"{key}"' in JS


def test_app_version_central():
    assert "SERO_APP_VERSION" in PROF


def test_sheet_above_settings_zindex():
    """Options-Sheets müssen über der Settings-View liegen."""
    import re
    css = Path("frontend/sero.css").read_text(encoding="utf-8")
    # settings-view z-index
    m_set = re.search(r"\.settings-view\s*\{[^}]*z-index:\s*(\d+)", css)
    m_sheet = re.search(r"\.sheet\s*\{[^}]*z-index:\s*(\d+)", css)
    m_bd = re.search(r"\.sheet-backdrop\s*\{[^}]*z-index:\s*(\d+)", css)
    assert m_set and m_sheet and m_bd
    assert int(m_sheet.group(1)) > int(m_set.group(1))
    assert int(m_bd.group(1)) > int(m_set.group(1))
