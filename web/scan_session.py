"""ScanSession — Scanner-Batch-Queue (ohne eBay-Calls).

Persistenz über Store-KV (`scan_session_{account_id}`).
UI-Status der Queue: Bereit / Prüfung nötig / Kein Preis / Fehler (+ Analysiert).
"""
from __future__ import annotations

from typing import Any

# Erlaubte Zustände einer Session (Scanner-first Plan P3)
SESSION_STATES = (
    "idle",
    "capturing",
    "analyzing",
    "review",
    "queued",
    "done",
    "error",
)

# Anzeige-Status eines Queue-Eintrags (Listings-UI)
QUEUE_STATUSES = (
    "analyzing",
    "ready",
    "needs_review",
    "no_price",
    "error",
)

DEFAULT_SESSION = {
    "state": "idle",
    "items": [],          # [{item_id, draft_id?, status, title?, photo?}]
    "batch_queue": [],    # draft_ids wartend auf Review/Publish
    "updated_at": None,
}


def normalize_session(raw: dict[str, Any] | None) -> dict[str, Any]:
    s = dict(DEFAULT_SESSION)
    if isinstance(raw, dict):
        st = (raw.get("state") or "idle").strip()
        s["state"] = st if st in SESSION_STATES else "idle"
        items = []
        for it in (raw.get("items") or [])[:50]:
            if not isinstance(it, dict):
                continue
            iid = str(it.get("item_id") or "").strip()
            if not iid:
                continue
            stq = (it.get("status") or "analyzing").strip()
            if stq not in QUEUE_STATUSES:
                stq = "analyzing"
            items.append({
                "item_id": iid,
                "draft_id": (str(it["draft_id"]) if it.get("draft_id") else None),
                "status": stq,
                "title": (str(it.get("title") or "")[:120] or None),
                "photo": (str(it.get("photo") or "")[:240] or None),
            })
        s["items"] = items
        s["batch_queue"] = [str(x) for x in (raw.get("batch_queue") or [])[:50]]
        s["updated_at"] = raw.get("updated_at")
    return s


def session_key(account_id: int | str) -> str:
    return f"scan_session_{account_id}"


def queue_status_from_item(item: dict[str, Any] | None,
                           draft: dict[str, Any] | None = None) -> str:
    """Ableitung des Queue-Labels aus Sammlungsstück + optionalem Entwurf."""
    it = item or {}
    d = draft or {}
    ist = (it.get("status") or "").strip()
    dst = (d.get("status") or "").strip()
    if ist in ("analyzing", "downloading", "waiting") or dst in (
            "analyzing", "downloading", "waiting"):
        return "analyzing"
    if ist in ("error",) or dst in ("error",):
        return "error"
    if ist in ("uncertain", "needs_review") or dst in (
            "uncertain", "needs_review", "publish_uncertain"):
        return "needs_review"
    if it.get("question") or d.get("question") or d.get("app_pending"):
        return "needs_review"
    # Preis: Entwurf hat Listenpreis, sonst Marktwert am Stück
    price = d.get("price")
    try:
        price_f = float(str(price).replace(",", ".")) if price not in (None, "") else 0.0
    except (TypeError, ValueError):
        price_f = 0.0
    if price_f <= 0:
        ev = it.get("est_value")
        try:
            ev_f = float(str(ev).replace(",", ".")) if ev not in (None, "") else 0.0
        except (TypeError, ValueError):
            ev_f = 0.0
        ps = (it.get("price_state") or "").strip()
        if ev_f <= 0 or ps == "unbekannt":
            if ist in ("ready", "listed", "") or dst in ("ready", "draft", "preset", ""):
                return "no_price"
    if dst in ("ready", "draft", "preset", "dry_run_done") or ist == "ready":
        return "ready"
    if ist == "ready" or dst == "ready":
        return "ready"
    return "analyzing"


def merge_queue_items(existing: list[dict[str, Any]],
                      new_ids: list[str]) -> list[dict[str, Any]]:
    """Neue item_ids vorn anhängen, Duplikate behalten den alten Eintrag."""
    seen = {str(x.get("item_id")) for x in existing if isinstance(x, dict)}
    out = list(existing)
    for iid in new_ids:
        sid = str(iid)
        if sid in seen:
            continue
        out.insert(0, {"item_id": sid, "draft_id": None, "status": "analyzing",
                       "title": None, "photo": None})
        seen.add(sid)
    return out[:50]
