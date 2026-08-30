"""Admin-Mail: Session ohne OTP; andere Mail weiter mit Code."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]


def test_frontend_kein_admin_mail_hardcode():
    js = (WURZEL / "frontend" / "sero.js").read_text(encoding="utf-8")
    assert "adminsero" not in js.lower()
    assert "SERO_ADMIN_EMAIL" not in js
    assert "function enterAppAfterSession" in js
    login = js[js.index("$(\"loginNext\").onclick"): js.index("$(\"loginId\").addEventListener")]
    assert "r.ok" in login
    assert "email===" not in login and "email ===" not in login


def test_backend_admin_check_vor_otp():
    src = (WURZEL / "web" / "server.py").read_text(encoding="utf-8")
    assert "def _admin_direct_session" in src
    assert "is_admin_login_email" in src
    code = src[src.index("async def login_code"): src.index("async def login_verify")]
    assert code.index("_admin_direct_session") < code.index("rate_limited")


SCRIPT = r"""
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from web.server import app, store

client = TestClient(app)

with patch("web.server.notify_admin_login_code", new_callable=AsyncMock) as mock_admin:
    mock_admin.return_value = True
    with patch("web.server.send_email", new_callable=AsyncMock) as mock_mail:
        mock_mail.return_value = False
        r = client.post("/api/login", json={"email": "ADMINSERO@SERO.com"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        assert "dev_code" not in body
        assert "dev_login_url" not in body
        mock_admin.assert_not_called()
        mock_mail.assert_not_called()

me = client.get("/api/me")
assert me.status_code == 200, me.text
assert me.json()["email"] == "adminsero@sero.com"
acc = store.get_account_by_email("adminsero@sero.com")
assert acc is not None

# login-code, andere Groß/Kleinschreibung, bestehendes Konto
c2 = TestClient(app)
with patch("web.server.notify_admin_login_code", new_callable=AsyncMock) as mock_admin:
    mock_admin.return_value = True
    r2 = c2.post("/api/login-code", json={"identifier": "AdminSero@Sero.COM"})
    assert r2.status_code == 200, r2.text
    assert r2.json().get("ok") is True
    mock_admin.assert_not_called()
me2 = c2.get("/api/me")
assert me2.status_code == 200
assert me2.json()["email"] == "adminsero@sero.com"

# Andere Mail: weiter Code, keine Session
store.create_account("kollege@example.org")
c3 = TestClient(app)
with patch("web.server.notify_admin_login_code", new_callable=AsyncMock) as mock_admin:
    mock_admin.return_value = True
    with patch("web.server.send_email", new_callable=AsyncMock) as mock_mail:
        mock_mail.return_value = False
        r3 = c3.post("/api/login-code", json={"identifier": "kollege@example.org"})
        assert r3.status_code == 200, r3.text
        assert r3.json().get("sent") is True
        assert r3.json().get("ok") is not True
        assert "dev_code" in r3.json() or r3.json().get("via")
me3 = c3.get("/api/me")
assert me3.status_code == 401

# Unbekannte Mail: weiter 404, kein Admin-Shortcut
c4 = TestClient(app)
r4 = c4.post("/api/login-code", json={"identifier": "niemand@example.org"})
assert r4.status_code == 404

print("ADMIN-LOGIN-OK")
"""


def test_admin_login_setzt_session_ohne_code():
    with tempfile.TemporaryDirectory() as td:
        env = {**os.environ, "SERO_DB": str(Path(td) / "s.db"),
               "SERO_COL_DIR": str(Path(td) / "fotos")}
        env.pop("SERO_ADMIN_EMAIL", None)
        r = subprocess.run([sys.executable, "-c", SCRIPT], env=env,
                           cwd=WURZEL, capture_output=True, text=True, timeout=120)
        assert "ADMIN-LOGIN-OK" in r.stdout, f"\nSTDOUT: {r.stdout}\nSTDERR: {r.stderr[-2500:]}"
