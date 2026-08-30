"""Optionale Playwright-Tests. Skip ohne playwright-Paket.

Abnahme-Screenshots (Fake-Auth, Temp-DB, kein Port 3000, kein eBay-Publish):
  PLAYWRIGHT_BROWSERS_PATH=~/Library/Caches/ms-playwright \\
    ./.venv/bin/python -m pytest tests/test_playwright_mobile.py -q -k shots
→ tmp/scanner_first_shots/
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SHOT_DIR = ROOT / "tmp" / "scanner_first_shots"
ACCOUNT_UID_OFFSET = 10 ** 15

pw = pytest.importorskip("playwright.sync_api", reason="playwright nicht installiert")


def test_camera_click_is_sync_source():
    js = (ROOT / "frontend" / "sero.js").read_text(encoding="utf-8")
    i = js.index("const weiter = (welcher)")
    chunk = js[i:i + 350]
    assert "inp.click()" in chunk
    assert chunk.index("inp.click()") < chunk.index("closeSheet()")
    assert "setTimeout" not in chunk


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    assert port != 3000
    return port


def _skip_if_no_chromium(exc: BaseException) -> None:
    msg = str(exc)
    if "Executable doesn't exist" in msg or "playwright install" in msg.lower():
        pytest.skip(f"Chromium fehlt (externer Blocker): {msg[:120]}")


@pytest.fixture(scope="module")
def app_server():
    port = _free_port()
    td = tempfile.mkdtemp(prefix="sero-pw-")
    db = str(Path(td) / "pw.db")
    col = str(Path(td) / "col")
    Path(col).mkdir()
    env = {**os.environ, "SERO_DB": db, "SERO_COL_DIR": col}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "web.server:app",
         "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    base = "http://127.0.0.1:%d" % port
    for _ in range(60):
        try:
            urllib.request.urlopen(base + "/app/", timeout=0.5)
            break
        except Exception:
            if proc.poll() is not None:
                out = proc.stdout.read() if proc.stdout else ""
                raise RuntimeError("Server tot: " + out[-2000:])
            time.sleep(0.15)
    else:
        proc.kill()
        raise RuntimeError("Server startete nicht")
    yield base, db
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def test_gesture_helper_in_page(app_server):
    base, _db = app_server
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(base + "/app/", wait_until="domcontentloaded", timeout=30000)
            page.add_script_tag(path=str(ROOT / "frontend" / "sero-mobile.js"))
            ok = page.evaluate("""() => {
              const SM = window.SeroMobile;
              if (!SM) return false;
              if (SM.gestures.shouldAllowTabSwipe({dx:80,dy:10,sheetOpen:true})) return false;
              const chip = { closest: (s) => s.includes('.chips') ? {} : null };
              if (SM.gestures.shouldAllowTabSwipe({dx:80,dy:10,target:chip})) return false;
              return SM.gestures.shouldAllowTabSwipe({dx:80,dy:10}) === true;
            }""")
            assert ok
            browser.close()
    except Exception as e:
        _skip_if_no_chromium(e)
        raise


def _seed_account_and_draft(db_path: str) -> tuple[str, str]:
    """Fake-Konto + ready-Entwurf in der Temp-DB. Session-Cookie via web_secret."""
    from itsdangerous import URLSafeTimedSerializer

    from bot.drafts import Store

    store = Store(Path(db_path))
    secret = store.kv_get("web_secret")
    assert secret, "Server hat noch kein web_secret gesetzt"
    signer = URLSafeTimedSerializer(secret, salt="listo-session")
    account = store.create_account("shots@example.org")
    uid = ACCOUNT_UID_OFFSET + account["id"]
    # 1×1 PNG als Platzhalter — kein echtes Foto, nur Review-Struktur
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f"
        b"\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    photo = Path(db_path).parent / "shot.png"
    photo.write_bytes(png)
    draft_id = store.create_draft(uid, {
        "status": "ready",
        "sku": "SERO-SHOT1",
        "price": "12.50",
        "format": "FIXED_PRICE",
        "auction_days": 7,
        "quantity": 1,
        "category_id": "183454",
        "category_name": "Sammelkarten",
        "revision": 0,
        "photos": [str(photo)],
        "listing": {
            "title": "Pikachu Base Set #58 EN — Abnahme-Fixture",
            "description_html": "<p>Fixture für Listing-Review A–D. Kein Live-Publish.</p>",
            "condition": "USED_EXCELLENT",
            "aspects": {"Spiel": ["Pokémon"], "Set": ["Base Set"]},
        },
        "required_aspects": ["Spiel", "Set"],
    })
    cookie = signer.dumps(account["id"])
    return cookie, draft_id


def _boot_app(page, base: str, cookie: str, theme: str) -> None:
    page.context.add_cookies([{
        "name": "listo_session",
        "value": cookie,
        "url": base,
        "httpOnly": True,
        "sameSite": "Lax",
    }])
    # Theme + Tour + DE vor erstem Paint — kein zweites Argument bei add_init_script
    page.add_init_script(f"""
      try {{
        localStorage.setItem('sero_theme', {theme!r});
        localStorage.setItem('sero_lang', 'de');
        localStorage.setItem('sero_tour_v3_shots@example.org', '1');
        localStorage.setItem('sero_tour', '1');
      }} catch (e) {{}}
    """)
    page.goto(base + "/app/", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_function(
        """() => {
          const app = document.getElementById('viewApp');
          return app && !app.hidden;
        }""",
        timeout=20000,
    )
    page.wait_for_timeout(600)
    # Tour/Splash wegräumen falls doch noch da
    page.evaluate("""() => {
      document.querySelectorAll('.party.tour').forEach((el) => el.remove());
      const sp = document.getElementById('splash');
      if (sp) { sp.classList.add('gone'); sp.hidden = true; }
    }""")


def _shot(page, name: str) -> Path:
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SHOT_DIR / f"{name}.png"
    page.screenshot(path=str(path), full_page=False)
    return path


def test_scanner_first_acceptance_shots(app_server):
    """Mobile Abnahme: Kernzustände ohne Login-UI-Hürde und ohne eBay-Mutation."""
    base, db = app_server
    from playwright.sync_api import sync_playwright

    try:
        cookie, draft_id = _seed_account_and_draft(db)
    except Exception as e:
        pytest.fail(f"Fixture-Seed fehlgeschlagen: {e}")

    viewports = [
        ("390x844", {"width": 390, "height": 844}),
        ("320x568", {"width": 320, "height": 568}),
        ("844x390", {"width": 844, "height": 390}),
    ]
    themes = ("light", "dark")
    written: list[str] = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            # Gast ohne Cookie: App, nicht Login-Wand (C6)
            for theme in themes:
                context = browser.new_context(
                    viewport={"width": 390, "height": 844},
                    color_scheme="dark" if theme == "dark" else "light",
                    locale="de-DE",
                )
                page = context.new_page()
                page.add_init_script(
                    f"try {{ localStorage.setItem('sero_theme', {theme!r});"
                    f" localStorage.setItem('sero_lang', 'de'); }} catch (e) {{}}"
                )
                page.goto(base + "/app/", wait_until="domcontentloaded", timeout=30000)
                page.wait_for_selector("#viewApp:not([hidden])", timeout=15000)
                page.wait_for_timeout(400)
                written.append(_shot(page, f"guest_{theme}_390x844").name)
                context.close()

            for vp_name, vp in viewports:
                for theme in themes:
                    # Prefix: nur 390 bekommt alle Zustände; andere Viewports Kernset
                    core_only = vp_name != "390x844"
                    context = browser.new_context(
                        viewport=vp,
                        color_scheme="dark" if theme == "dark" else "light",
                        locale="de-DE",
                    )
                    page = context.new_page()
                    _boot_app(page, base, cookie, theme)
                    tag = f"{theme}_{vp_name}"

                    # Start / Scanner-first Hero
                    page.evaluate("() => switchTab('tabHome')")
                    page.wait_for_timeout(500)
                    page.wait_for_selector(".home-sell-hero, #homeScanOne", timeout=10000)
                    written.append(_shot(page, f"start_hero_{tag}").name)

                    # Scanner-Tab
                    page.evaluate("() => switchTab('tabScan')")
                    page.wait_for_timeout(400)
                    page.wait_for_selector("#tabScan:not([hidden])")
                    written.append(_shot(page, f"scanner_{tag}").name)

                    if not core_only:
                        # Scan-Modusauswahl (Long-Press / contextmenu)
                        page.locator("#btnCamera").dispatch_event("contextmenu")
                        page.wait_for_selector("#smSingle, .scan-mode-list", timeout=5000)
                        page.wait_for_timeout(300)
                        written.append(_shot(page, f"scan_mode_{tag}").name)
                        page.evaluate("""() => {
                          if (typeof closeSheet === 'function') closeSheet();
                          document.querySelectorAll('.sheet-wrap,.sheet-backdrop,#sheet')
                            .forEach((el) => { try { el.remove(); } catch (e) {} });
                        }""")
                        page.wait_for_timeout(200)

                    # Listings mit Entwürfen (Fixture)
                    page.evaluate("() => switchTab('tabSales')")
                    page.wait_for_timeout(700)
                    page.evaluate("""() => {
                      if (typeof state !== 'undefined') {
                        state.salesBucket = 'draft';
                        state._salesBucketTouched = true;
                        if (typeof renderSales === 'function') renderSales();
                      }
                    }""")
                    page.wait_for_timeout(400)
                    written.append(_shot(page, f"listings_drafts_{tag}").name)

                    if not core_only:
                        # Listing-Review A–D
                        page.evaluate(
                            """(id) => { if (typeof openDraftDetail === 'function') openDraftDetail(id); }""",
                            draft_id,
                        )
                        page.wait_for_selector("#detail:not([hidden])", timeout=10000)
                        page.wait_for_selector("#lr-photos, #lr-product, .lr-sec", timeout=10000)
                        page.wait_for_timeout(500)
                        written.append(_shot(page, f"listing_review_{tag}").name)
                        page.evaluate("""() => {
                          const d = document.getElementById('detail');
                          if (d) d.hidden = true;
                          if (typeof state !== 'undefined') state.detail = null;
                        }""")

                    context.close()

            # Listings leer: zweites Konto ohne Entwürfe
            from itsdangerous import URLSafeTimedSerializer

            from bot.drafts import Store

            store = Store(Path(db))
            secret = store.kv_get("web_secret")
            signer = URLSafeTimedSerializer(secret, salt="listo-session")
            empty_acc = store.create_account("shots-empty@example.org")
            empty_cookie = signer.dumps(empty_acc["id"])
            for theme in themes:
                context = browser.new_context(
                    viewport={"width": 390, "height": 844},
                    color_scheme="dark" if theme == "dark" else "light",
                    locale="de-DE",
                )
                page = context.new_page()
                page.context.add_cookies([{
                    "name": "listo_session", "value": empty_cookie,
                    "url": base, "httpOnly": True, "sameSite": "Lax",
                }])
                page.add_init_script(f"""
                  try {{
                    localStorage.setItem('sero_theme', {theme!r});
                    localStorage.setItem('sero_lang', 'de');
                    localStorage.setItem('sero_tour_v3_shots-empty@example.org', '1');
                    localStorage.setItem('sero_tour', '1');
                  }} catch (e) {{}}
                """)
                page.goto(base + "/app/", wait_until="domcontentloaded", timeout=30000)
                page.wait_for_function(
                    "() => { const a = document.getElementById('viewApp'); return a && !a.hidden; }",
                    timeout=20000,
                )
                page.wait_for_timeout(500)
                page.evaluate("""() => {
                  document.querySelectorAll('.party.tour').forEach((el) => el.remove());
                  const sp = document.getElementById('splash');
                  if (sp) { sp.classList.add('gone'); sp.hidden = true; }
                  switchTab('tabSales');
                }""")
                page.wait_for_timeout(700)
                written.append(_shot(page, f"listings_empty_{theme}_390x844").name)
                context.close()

            browser.close()
    except Exception as e:
        _skip_if_no_chromium(e)
        raise

    assert len(written) >= 10, f"Zu wenige Screenshots: {written}"
    manifest = SHOT_DIR / "MANIFEST.txt"
    manifest.write_text(
        "Scanner-first Abnahme-Screenshots (Fake-Auth, Temp-DB, kein eBay)\n"
        + "\n".join(sorted(written)) + "\n",
        encoding="utf-8",
    )


def test_price_sheet_same_instance_headless(app_server):
    """Preis-Dialog: gleiche Instanz, kein Recede unter dem Detail (kein Live-Publish)."""
    base, db = app_server
    from playwright.sync_api import sync_playwright

    cookie, draft_id = _seed_account_and_draft(db)
    try:
        with sync_playwright() as p:
            browser = None
            try:
                browser = p.webkit.launch(headless=True)
            except Exception:
                browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 390, "height": 844},
                locale="de-DE",
            )
            page = context.new_page()
            _boot_app(page, base, cookie, "dark")
            page.evaluate(f"() => openDraftDetail({draft_id!r})")
            page.wait_for_selector("#lr-price, #detailBody .price-tap", timeout=15000)
            recede_before = page.evaluate("() => document.getElementById('viewApp').classList.contains('recede')")
            page.click("#lr-price")
            page.wait_for_selector("#sheetField", timeout=8000)
            recede_after = page.evaluate("() => document.getElementById('viewApp').classList.contains('recede')")
            page.evaluate("() => { const e = document.getElementById('sheetField'); if (e) e.dataset.keep = '1'; }")
            page.evaluate("""() => {
              if (typeof openInput === 'function') {
                openInput({ title: 'Preis festlegen', value: '12,50', mode: 'decimal' }, () => {});
              }
            }""")
            keep = page.evaluate("() => (document.getElementById('sheetField') || {}).dataset.keep")
            browser.close()
    except Exception as e:
        _skip_if_no_chromium(e)
        raise
    assert recede_before is False
    assert recede_after is False
    assert keep == "1"

