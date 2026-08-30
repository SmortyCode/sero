"""App-Signup: Username + Code-Pfad an Admin (ohne echtes Telegram)."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

WURZEL = Path(__file__).resolve().parents[1]

SCRIPT = r'''
import os
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from web.server import app, store

client = TestClient(app)

with patch("web.server.notify_admin_login_code", new_callable=AsyncMock) as mock_admin:
    mock_admin.return_value = True
    with patch("web.server.send_email", new_callable=AsyncMock) as mock_mail:
        mock_mail.return_value = False
        r = client.post("/api/signup", json={
            "email": "kollege@example.org",
            "username": "kollege.test",
        })
assert r.status_code == 200, r.text
body = r.json()
assert body.get("sent") is True
acc = store.get_account_by_email("kollege@example.org")
assert acc and acc.get("username") == "kollege.test"

# Doppel-Signup abweisen
r2 = client.post("/api/signup", json={
    "email": "kollege@example.org",
    "username": "andere",
})
assert r2.status_code == 409

# Username-Format
r3 = client.post("/api/signup", json={"email": "x@y.de", "username": "ab"})
assert r3.status_code == 400

print("SIGNUP-OK")
'''


def test_signup_with_username():
    with tempfile.TemporaryDirectory() as td:
        env = {**os.environ, "SERO_DB": str(Path(td) / "s.db"),
               "SERO_COL_DIR": str(Path(td) / "fotos"),
               "ALLOWED_USER_ID": "12345"}
        r = subprocess.run([sys.executable, "-c", SCRIPT], env=env,
                           cwd=WURZEL, capture_output=True, text=True, timeout=120)
        assert "SIGNUP-OK" in r.stdout, f"\nSTDOUT: {r.stdout}\nSTDERR: {r.stderr[-2500:]}"
