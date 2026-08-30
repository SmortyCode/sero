"""Phase B/C: Magic-Link und eBay-Callback landen in /app/; Flag-Logik."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent


def test_safe_post_auth_path_unit():
    """Direkter Import ohne Store-Bindung an Live-DB."""
    # Nur die Hilfsfunktion — ohne web.server Import (der legt Store an).
    quelle = (WURZEL / "web" / "server.py").read_text(encoding="utf-8")
    assert "def safe_post_auth_path" in quelle
    assert 'startswith("/app")' in quelle
    assert "onboarding.html" in quelle
    assert ":// in path" in quelle or '"://" in path' in quelle


REDIRECT_TEST = r"""
from fastapi.testclient import TestClient
from web.server import app, store, signer, safe_post_auth_path, with_query_flag

assert safe_post_auth_path("https://evil.test/") == "/app/"
assert safe_post_auth_path("//evil.test") == "/app/"
assert safe_post_auth_path("/onboarding.html") == "/onboarding.html"
assert safe_post_auth_path("/app/?x=1") == "/app/?x=1"
assert with_query_flag("/app/", "ebay", "ok") == "/app/?ebay=ok"

client = TestClient(app)
acc = store.create_account("redirect@example.org")
code = store.create_link_code(acc["id"], "login")
r = client.get(f"/auth/{code}", follow_redirects=False)
assert r.status_code in (302, 303, 307)
loc = r.headers["location"]
assert loc.startswith("/app/"), loc
assert "logged_in=1" in loc
assert "Listo" not in loc and "ListingPunk" not in loc

# eBay-Callback ohne gültigen State
r = client.get("/callback/ebay?code=x&state=bad", follow_redirects=False)
assert r.status_code in (302, 303, 307)
assert r.headers["location"].startswith("/app/")
assert "ebay=invalid" in r.headers["location"]

# connect/ebay speichert next in state (Anmeldung nötig)
client.cookies.set("listo_session", signer.dumps(acc["id"]))
r = client.get("/connect/ebay?next=/onboarding.html", follow_redirects=False)
assert r.status_code in (302, 303, 307)
# geht zu eBay — Location enthält state=
assert "state=" in r.headers.get("location", "")

# Callback setzt Session-Cookie (OAuth oft in anderem Tab/Safari)
from unittest.mock import AsyncMock, patch
state = signer.dumps({"a": acc["id"], "t": 1, "n": "/app/"})
with patch("web.server._store_ebay_token", new_callable=AsyncMock):
    r = client.get(f"/callback/ebay?code=tok&state={state}", follow_redirects=False)
assert r.status_code in (302, 303, 307)
assert "ebay=ok" in r.headers["location"]
assert "listo_session" in r.cookies

print("REDIRECT-OK")
"""


def test_auth_und_ebay_redirects_zur_app():
    with tempfile.TemporaryDirectory() as td:
        env = {**os.environ, "SERO_DB": str(Path(td) / "redir.db")}
        r = subprocess.run([sys.executable, "-c", REDIRECT_TEST], env=env,
                           cwd=WURZEL, capture_output=True, text=True, timeout=120)
        assert "REDIRECT-OK" in r.stdout, f"\nSTDOUT: {r.stdout}\nSTDERR: {r.stderr[-3000:]}"


def test_sero_fluss_ohne_listo_branding_in_server():
    q = (WURZEL / "web" / "server.py").read_text(encoding="utf-8")
    assert 'title="SERO"' in q
    assert 'RedirectResponse("/onboarding.html?logged_in=1")' not in q
    assert 'RedirectResponse("/onboarding.html?ebay=ok")' not in q
    assert "safe_post_auth_path" in q


FLAG_TEST = r"""
import time
from fastapi.testclient import TestClient
from web.server import app, store, signer, ACCOUNT_UID_OFFSET, _store_ebay_token
from bot.ebay.auth import _token_key

client = TestClient(app)
acc = store.create_account("flag@example.org")
uid = ACCOUNT_UID_OFFSET + acc["id"]
client.cookies.set("listo_session", signer.dumps(acc["id"]))

# Flag setzen wie Sales-Sync bei 403
store.kv_set(f"ebay_fulfillment_fehlt_{uid}", {"ts": time.time(), "detail": "403"})
# Token vortäuschen
store.kv_set(_token_key(uid), {"access_token": "x", "refresh_token": "y", "expires_at": time.time() + 3600})

r = client.get("/api/me")
assert r.status_code == 200
assert r.json()["ebay_needs_reconnect"] is True

# Quelltext-Wache: _store_ebay_token löscht Flag NICHT mehr
import inspect
from web import server as srv
src = inspect.getsource(srv._store_ebay_token)
# Kommentar darf Flag erwähnen — aber kein kv_set/DELETE darauf
assert "kv_set(f\"ebay_fulfillment_fehlt_" not in src
assert "DELETE FROM kv WHERE key" not in src

# Erfolgspfad: DELETE wie sync_sales_status
with store._lock:
    store._conn.execute("DELETE FROM kv WHERE key = ?", (f"ebay_fulfillment_fehlt_{uid}",))
    store._conn.commit()
r = client.get("/api/me")
assert r.json()["ebay_needs_reconnect"] is False

print("FLAG-OK")
"""


def test_fulfillment_flag_nur_nach_orders_erfolg():
    with tempfile.TemporaryDirectory() as td:
        env = {**os.environ, "SERO_DB": str(Path(td) / "flag.db")}
        r = subprocess.run([sys.executable, "-c", FLAG_TEST], env=env,
                           cwd=WURZEL, capture_output=True, text=True, timeout=120)
        assert "FLAG-OK" in r.stdout, f"\nSTDOUT: {r.stdout}\nSTDERR: {r.stderr[-3000:]}"


def test_consent_enthaelt_fulfillment_scope():
    from bot.config import USER_SCOPES, SCOPE_FULFILLMENT
    assert SCOPE_FULFILLMENT in USER_SCOPES
    auth = (WURZEL / "bot" / "ebay" / "auth.py").read_text(encoding="utf-8")
    assert "USER_SCOPES" in auth


def test_ui_reconnect_button_klar():
    js = (WURZEL / "frontend" / "sero.js").read_text(encoding="utf-8")
    assert "eBay neu verbinden" in js
    assert "goEbayConnect" in js
    assert "/connect/ebay?next=" in js
    assert "salesReconnectBtn" in js
    assert "openEbayConnectSheet" in js
    assert "ebayPasteUrl" in js
    assert "ebayConnectCheck" in js
    assert "ebay_token_at" in (WURZEL / "web" / "server.py").read_text(encoding="utf-8")
    # Verkauf und Profil: derselbe Sheet-Einstieg
    assert "salesReconnectBtn" in js and "openEbayConnectSheet(state.me" in js
    assert "onboarding.html" not in js.split("function openSetupSheet")[1].split("function openEbayConnectSheet")[0]
    assert "set_session" in (WURZEL / "web" / "server.py").read_text(encoding="utf-8")
    # Callback muss Session setzen (Quelltext-Wache)
    cb = (WURZEL / "web" / "server.py").read_text(encoding="utf-8")
    assert "async def callback_ebay" in cb
    assert "set_session(resp, account[\"id\"])" in cb or "set_session(resp, account['id'])" in cb
    assert "ebay_token_at_" in cb
