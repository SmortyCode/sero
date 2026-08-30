"""Dauerhafte Scan-Metriken und SERO-Effekt-Rechnung (ohne LLM/externe Kosten).

Ein erfolgreicher Scan zählt einmal pro (account_id, item_id). Retries,
Löschen und Verkaufen ändern den Allzeit-Zähler nicht. Kontolöschung räumt
die Zeilen mit ab. Historischer Backfill setzt completed_at auf NULL, damit
alte Stücke nicht fälschlich in „Letzte 7 Tage“ landen.
"""
from __future__ import annotations

import json
import time
from typing import Any

# Aktive Nutzerzeit je erfolgreichem Scan — nicht die technische Analysezeit.
MANUAL_SECONDS_PER_SCAN = 15 * 60  # 15 Minuten von Hand
SERO_SECONDS_PER_SCAN = 2 * 60     # 2 Minuten mit SERO
SAVED_SECONDS_PER_SCAN = MANUAL_SECONDS_PER_SCAN - SERO_SECONDS_PER_SCAN  # 13 Minuten

AVG_MIN_SAMPLES = 3


def ensure_table(conn) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS scan_metrics ("
        "account_id INTEGER NOT NULL, "
        "item_id TEXT NOT NULL, "
        "completed_at REAL, "
        "scan_seconds REAL, "
        "PRIMARY KEY (account_id, item_id))")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_scan_metrics_acc_done "
        "ON scan_metrics (account_id, completed_at)")


def record_success(
    conn,
    account_id: int,
    item_id: str,
    *,
    scan_seconds: float | None = None,
    completed_at: float | None = None,
) -> bool:
    """Idempotent: True wenn neu eingefügt, False bei Retry/Duplikat."""
    if not item_id:
        return False
    cur = conn.execute(
        "INSERT OR IGNORE INTO scan_metrics "
        "(account_id, item_id, completed_at, scan_seconds) VALUES (?, ?, ?, ?)",
        (int(account_id), str(item_id), completed_at, scan_seconds))
    return cur.rowcount > 0


def delete_account_metrics(conn, account_id: int) -> None:
    conn.execute("DELETE FROM scan_metrics WHERE account_id = ?", (int(account_id),))


def backfill_from_collection(conn) -> int:
    """Best-Effort aus vorhandenen Stücken mit gültigem scan_seconds.

    completed_at bleibt NULL → zählt für Allzeit, nicht für 7-Tage-Aktivität.
    Wiederholbar dank INSERT OR IGNORE.
    """
    rows = conn.execute(
        "SELECT account_id, id, data FROM collection_items").fetchall()
    n = 0
    for row in rows:
        aid = row["account_id"] if hasattr(row, "keys") else row[0]
        iid = row["id"] if hasattr(row, "keys") else row[1]
        raw = row["data"] if hasattr(row, "keys") else row[2]
        try:
            data = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        try:
            secs = float(data.get("scan_seconds"))
        except (TypeError, ValueError):
            continue
        if secs <= 0:
            continue
        if record_success(conn, aid, iid, scan_seconds=secs, completed_at=None):
            n += 1
    return n


def impact_from_count(successful_scans: int) -> dict[str, int]:
    n = max(0, int(successful_scans or 0))
    return {
        "successful_scans": n,
        "manual_seconds": n * MANUAL_SECONDS_PER_SCAN,
        "sero_seconds": n * SERO_SECONDS_PER_SCAN,
        "saved_seconds": n * SAVED_SECONDS_PER_SCAN,
    }


def avg_analysis_seconds(conn, account_id: int) -> int | None:
    row = conn.execute(
        "SELECT COUNT(*) AS c, AVG(scan_seconds) AS a FROM scan_metrics "
        "WHERE account_id = ? AND scan_seconds IS NOT NULL AND scan_seconds > 0",
        (int(account_id),)).fetchone()
    if not row:
        return None
    c = int(row["c"] if hasattr(row, "keys") else row[0] or 0)
    if c < AVG_MIN_SAMPLES:
        return None
    avg = row["a"] if hasattr(row, "keys") else row[1]
    if avg is None:
        return None
    return int(round(float(avg)))


def build_impact(conn, account_id: int) -> dict[str, Any]:
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM scan_metrics WHERE account_id = ?",
        (int(account_id),)).fetchone()
    n = int(row["c"] if hasattr(row, "keys") else row[0] or 0)
    out = impact_from_count(n)
    out["avg_analysis_seconds"] = avg_analysis_seconds(conn, account_id)
    return out


def activity_scanned_7d(conn, account_id: int, *, now: float | None = None) -> int:
    cutoff = (now if now is not None else time.time()) - 7 * 86400
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM scan_metrics "
        "WHERE account_id = ? AND completed_at IS NOT NULL AND completed_at >= ?",
        (int(account_id), cutoff)).fetchone()
    return int(row["c"] if hasattr(row, "keys") else row[0] or 0)


def activity_published_7d(conn, chat_ids: list[int], *, now: float | None = None) -> int:
    """Echte Veröffentlichungen der letzten 7 Tage.

    Zählt über unveränderliches published_at im Draft-JSON oder das echte
    listings.created_at (kein Dry-Run). updated_at zählt nicht — Verkaufs-Sync
    darf die 7-Tage-Aktivität nicht aufblähen.
    """
    ids = [int(x) for x in chat_ids if x is not None]
    if not ids:
        return 0
    cutoff = (now if now is not None else time.time()) - 7 * 86400
    placeholders = ",".join("?" * len(ids))
    has_listings = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='listings'"
    ).fetchone()
    if has_listings:
        row = conn.execute(
            f"SELECT COUNT(*) AS c FROM drafts "
            f"WHERE chat_id IN ({placeholders}) AND status = 'published' "
            f"AND ("
            f"  CAST(json_extract(data, '$.published_at') AS REAL) >= ?"
            f"  OR EXISTS ("
            f"    SELECT 1 FROM listings l "
            f"    WHERE l.sku = json_extract(drafts.data, '$.sku') "
            f"      AND IFNULL(l.dry_run, 0) = 0 AND l.created_at >= ?"
            f"  )"
            f")",
            (*ids, cutoff, cutoff)).fetchone()
    else:
        row = conn.execute(
            f"SELECT COUNT(*) AS c FROM drafts "
            f"WHERE chat_id IN ({placeholders}) AND status = 'published' "
            f"AND CAST(json_extract(data, '$.published_at') AS REAL) >= ?",
            (*ids, cutoff)).fetchone()
    return int(row["c"] if hasattr(row, "keys") else row[0] or 0)


def activity_sold_7d(conn, chat_ids: list[int], *, now: float | None = None) -> int:
    """Echte Verkäufe der letzten 7 Tage (ended_reason=Verkauft + sold_at)."""
    ids = [int(x) for x in chat_ids if x is not None]
    if not ids:
        return 0
    cutoff = (now if now is not None else time.time()) - 7 * 86400
    placeholders = ",".join("?" * len(ids))
    row = conn.execute(
        f"SELECT COUNT(*) AS c FROM drafts "
        f"WHERE chat_id IN ({placeholders}) AND status = 'ended' "
        f"AND json_extract(data, '$.ended_reason') = 'Verkauft' "
        f"AND ("
        f"  CAST(json_extract(data, '$.sold_at') AS REAL) >= ?"
        f"  OR ("
        f"    json_extract(data, '$.sold_at') IS NULL"
        f"    AND updated_at >= ?"
        f"  )"
        f")",
        (*ids, cutoff, cutoff)).fetchone()
    return int(row["c"] if hasattr(row, "keys") else row[0] or 0)


def needs_attention(item: dict) -> bool:
    """Handlungsbedarf anhand vorhandener price_state/price_reason/status."""
    if not item or item.get("wishlist"):
        return False
    if item.get("sold") or item.get("draft_status") == "ended":
        return False
    status = item.get("status")
    if status in ("error", "needs_review", "uncertain"):
        return True
    if item.get("price_state") == "unbekannt":
        return True
    if item.get("price_reason") == "BELEGE_ALT":
        return True
    ie = item.get("identity_eval") or {}
    # Widerspruch belegt + nicht pricing_ready: Migrationsfall, kein Doppelzählen
    # als Attention, solange Status ready und Preis sichtbar — Report separat.
    if status == "needs_review" or (
            status != "ready" and ie.get("pricing_ready") is False):
        return True
    if status == "ready" and ie.get("pricing_ready") is False and item.get("price_state") != "belegt":
        return True
    return False


def attention_count(items: list[dict]) -> int:
    return sum(1 for i in items if needs_attention(i))


def format_duration_de(seconds: int | float) -> str:
    """Zentrale deutsche Kurzform: '37 Min', '1 Std', '4 Std 19 Min'."""
    s = max(0, int(round(float(seconds or 0))))
    h, rem = divmod(s, 3600)
    m = rem // 60
    if h == 0:
        return "1 Min" if m == 1 else f"{m} Min"
    if m == 0:
        return "1 Std" if h == 1 else f"{h} Std"
    hs = "1 Std" if h == 1 else f"{h} Std"
    ms = "1 Min" if m == 1 else f"{m} Min"
    return f"{hs} {ms}"
