"""ScanSession / Queue-Status — ohne eBay, ohne Store."""
from __future__ import annotations

from web.scan_session import (
    QUEUE_STATUSES,
    merge_queue_items,
    normalize_session,
    queue_status_from_item,
)


def test_normalize_defaults_and_filters():
    s = normalize_session(None)
    assert s["state"] == "idle"
    assert s["items"] == []
    assert s["batch_queue"] == []

    s2 = normalize_session({
        "state": "hacker",
        "items": [
            {"item_id": "a1", "status": "ready", "title": "Glurak"},
            {"item_id": "", "status": "ready"},
            "nope",
            {"item_id": "b2", "status": "weird"},
        ],
        "batch_queue": [1, "d9"],
    })
    assert s2["state"] == "idle"
    assert len(s2["items"]) == 2
    assert s2["items"][0]["status"] == "ready"
    assert s2["items"][1]["status"] == "analyzing"
    assert s2["batch_queue"] == ["1", "d9"]


def test_queue_status_mapping():
    assert queue_status_from_item({"status": "analyzing"}) == "analyzing"
    assert queue_status_from_item({"status": "error"}) == "error"
    assert queue_status_from_item({"status": "uncertain"}) == "needs_review"
    assert queue_status_from_item({"status": "ready", "question": "Welche?"}) == "needs_review"
    assert queue_status_from_item({"status": "ready", "price_state": "unbekannt"}) == "no_price"
    assert queue_status_from_item(
        {"status": "ready"}, {"status": "ready", "price": "12.50"}) == "ready"
    assert "ready" in QUEUE_STATUSES


def test_merge_queue_prepends_unique():
    cur = [{"item_id": "a", "status": "ready"}]
    out = merge_queue_items(cur, ["b", "a", "c"])
    assert [x["item_id"] for x in out] == ["c", "b", "a"]
    assert out[0]["status"] == "analyzing"
