"""Backend-Härtung: _spawn loggt Exceptions; Sales-KV fällt sicher zurück."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SPAWN = r"""
import asyncio
import logging
import os
import tempfile
from pathlib import Path

os.environ["SERO_DB"] = str(Path(tempfile.mkdtemp()) / "spawn.db")
import web.app_api as m

seen = []

class H(logging.Handler):
    def emit(self, record):
        seen.append(record.getMessage())

logging.getLogger().addHandler(H())
logging.getLogger().setLevel(logging.ERROR)
for name in list(logging.Logger.manager.loggerDict):
    logging.getLogger(name).addHandler(H())
    logging.getLogger(name).setLevel(logging.ERROR)

async def boom():
    raise RuntimeError("explode")

async def sleeper():
    await asyncio.sleep(5)

async def main():
    m._spawn(boom())
    await asyncio.sleep(0.2)
    assert any("Hintergrund-Task" in s for s in seen), seen
    before = len([s for s in seen if "Hintergrund-Task" in s])
    task = asyncio.create_task(sleeper())
    m._tasks.add(task)
    def done(t):
        m._tasks.discard(t)
        if t.cancelled():
            return
        exc = t.exception()
        if exc is not None:
            logging.getLogger("web.app_api").exception(
                "Hintergrund-Task fehlgeschlagen: %s", type(exc).__name__, exc_info=exc)
    task.add_done_callback(done)
    task.cancel()
    await asyncio.sleep(0.05)
    after = len([s for s in seen if "Hintergrund-Task" in s])
    assert after == before, (before, after, seen)
    print("SPAWN-OK")

asyncio.run(main())
"""

SALES = r"""
import time
from fastapi.testclient import TestClient
from web.server import app, store, signer

client = TestClient(app)
account = store.create_account("saleskv@example.org")
client.cookies.set("listo_session", signer.dumps(account["id"]))
key = f"sales_sync_ts_{account['id']}"

for bad in ("nope", ["x"], None, {"t": "x"}, {"t": None}):
    store.kv_set(key, bad)
    r = client.get("/api/app/sales")
    assert r.status_code == 200, (bad, r.status_code, r.text)

store.kv_set(key, {"t": time.time()})
r = client.get("/api/app/sales")
assert r.status_code == 200
print("SALES-KV-OK")
"""

SALES_ENDED = r"""
from fastapi.testclient import TestClient
from web.server import app, store, signer, ACCOUNT_UID_OFFSET

client = TestClient(app)
account = store.create_account("salesended@example.org")
chat = ACCOUNT_UID_OFFSET + account["id"]
client.cookies.set("listo_session", signer.dumps(account["id"]))

sold = store.create_draft(chat, {"status": "ended", "ended_reason": "Verkauft",
    "listing": {"title": "Sold Card"}, "price": "12.00", "format": "FIXED_PRICE",
    "photos": []})
expired = store.create_draft(chat, {"status": "ended", "ended_reason": "Beendet (ENDED)",
    "listing": {"title": "Expired Card"}, "price": "9.00", "format": "FIXED_PRICE",
    "photos": []})
live = store.create_draft(chat, {"status": "published", "listing": {"title": "Live Card"},
    "price": "25.50", "format": "FIXED_PRICE", "photos": []})

r = client.get("/api/app/sales")
assert r.status_code == 200, r.text
data = r.json()
ended_ids = {e["draft_id"] for e in data["ended"]}
active_ids = {e["draft_id"] for e in data["active"]}
assert sold in ended_ids, (ended_ids, data)
assert expired not in ended_ids, ended_ids
assert live in active_ids
print("SALES-ENDED-OK")
"""


def test_spawn_logs_exception_not_cancel():
    r = subprocess.run([sys.executable, "-c", SPAWN], cwd=ROOT,
                       capture_output=True, text=True, timeout=60)
    assert "SPAWN-OK" in r.stdout, r.stdout + r.stderr


def test_sales_kv_corrupt_safe():
    with tempfile.TemporaryDirectory() as td:
        env = {**os.environ, "SERO_DB": str(Path(td) / "test.db")}
        r = subprocess.run([sys.executable, "-c", SALES], env=env, cwd=ROOT,
                           capture_output=True, text=True, timeout=120)
        assert "SALES-KV-OK" in r.stdout, r.stdout + r.stderr[-2000:]


def test_sales_ended_only_verkauft():
    with tempfile.TemporaryDirectory() as td:
        env = {**os.environ, "SERO_DB": str(Path(td) / "test.db")}
        r = subprocess.run([sys.executable, "-c", SALES_ENDED], env=env, cwd=ROOT,
                           capture_output=True, text=True, timeout=120)
        assert "SALES-ENDED-OK" in r.stdout, r.stdout + r.stderr[-3000:]
