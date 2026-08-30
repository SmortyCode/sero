"""Collection-Revision ändert sich mit Draft-Status; Totals bleiben konsistent."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]

SCRIPT = r'''
import json, time, uuid
from fastapi.testclient import TestClient
from web.server import app, store, signer, ACCOUNT_UID_OFFSET

client = TestClient(app)
acc = store.create_account("rev-test@example.org")
client.cookies.set("listo_session", signer.dumps(acc["id"]))
aid = acc["id"]
uid = ACCOUNT_UID_OFFSET + aid

iid = uuid.uuid4().hex[:12]
did = uuid.uuid4().hex[:12]
now = time.time()
item = {
    "status": "ready", "name": "Testkarte", "quantity": 1,
    "est_value": 100.0, "price_state": "belegt", "price_source": "ebay_sold",
    "photos": [], "category": "Pokemon", "favorite": False, "wishlist": False,
    "tags": [], "draft_id": did, "created_at": now,
}
store._conn.execute(
    "INSERT INTO collection_items (id, account_id, created_at, updated_at, data) VALUES (?,?,?,?,?)",
    (iid, aid, now, now, json.dumps(item)))
store._conn.execute(
    "INSERT INTO drafts (id, chat_id, status, data, created_at, updated_at) VALUES (?,?,?,?,?,?)",
    (did, uid, "dry_run_done", json.dumps({"price": "100.00"}), now, now))
store._conn.commit()

c1 = client.get("/api/app/collection").json()
d1 = client.get("/api/app/dashboard").json()
assert abs(c1["stats"]["total_value"] - d1["total_value"]) < 0.001, (c1["stats"], d1["total_value"])
assert abs(c1["stats"]["total_value"] - c1["history"][-1]["value"]) < 0.001
assert abs(c1["stats"]["total_value"] - d1["history"][-1]["value"]) < 0.001
rev1 = c1["rev"]
v1 = float(c1["stats"]["total_value"])
assert abs(v1 - 100.0) < 0.01, v1

store._conn.execute(
    "UPDATE drafts SET status=?, updated_at=?, data=? WHERE id=?",
    ("published", now + 1, json.dumps({"price": "100.00", "published_at": now}), did))
store._conn.commit()

c2 = client.get("/api/app/collection").json()
d2 = client.get("/api/app/dashboard").json()
assert c2["rev"] != rev1, (rev1, c2["rev"])
assert abs(c2["stats"]["total_value"] - d2["total_value"]) < 0.001
assert abs(c2["stats"]["total_value"] - c2["history"][-1]["value"]) < 0.001
assert abs(float(c2["stats"]["total_value"]) - 0.0) < 0.01

store._conn.execute("UPDATE drafts SET status=? WHERE id=?", ("ended", did))
store._conn.commit()
c3 = client.get("/api/app/collection").json()
assert c3["rev"] != c2["rev"]
assert abs(c3["stats"]["total_value"] - client.get("/api/app/dashboard").json()["total_value"]) < 0.001

# sold mark on item
item2 = json.loads(store._conn.execute(
    "SELECT data FROM collection_items WHERE id=?", (iid,)).fetchone()["data"])
item2["sold_ts"] = now
store._conn.execute(
    "UPDATE collection_items SET data=?, updated_at=? WHERE id=?",
    (json.dumps(item2), now + 2, iid))
store._conn.commit()
c4 = client.get("/api/app/collection").json()
assert abs(float(c4["stats"]["total_value"]) - 0.0) < 0.01
assert c4["rev"] != c3["rev"]

print("REV-OK")
'''


def test_draft_status_changes_revision_and_totals():
    with tempfile.TemporaryDirectory() as td:
        env = {**os.environ, "SERO_DB": str(Path(td) / "rev.db"),
               "SERO_COL_DIR": str(Path(td) / "fotos")}
        r = subprocess.run([sys.executable, "-c", SCRIPT], env=env,
                           cwd=WURZEL, capture_output=True, text=True, timeout=120)
        assert "REV-OK" in r.stdout, f"\nSTDOUT: {r.stdout}\nSTDERR: {r.stderr[-3000:]}"
