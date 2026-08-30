#!/usr/bin/env python3
"""Read-only Vorschau: belegt/spanne vs. identity nicht pricing_ready.

Nutzt standardmäßig eine Kopie oder -readonly gegen die angegebene DB.
Schreibt KEINE Änderungen. Keine Netz-/Preis-/eBay-Aufrufe.

  python scripts/preview_identity_price_inconsistencies.py [pfad/zu/data.db]
  # Default: ~/ebay-bot/data.db read-only URI
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from web.identity import evaluate_identity, identity_from_item  # noqa: E402


def main(argv: list[str]) -> int:
    db = Path(argv[1]) if len(argv) > 1 else ROOT / "data.db"
    if not db.exists():
        print(f"DB fehlt: {db}")
        return 2
    uri = f"file:{db}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, account_id, data FROM collection_items"
    ).fetchall()
    widerspruch = []
    needs_review_candidates = []
    for r in rows:
        try:
            data = json.loads(r["data"] or "{}")
        except json.JSONDecodeError:
            continue
        data["id"] = r["id"]
        state = data.get("price_state")
        if state not in ("belegt", "spanne"):
            continue
        ev = evaluate_identity(identity_from_item(data))
        if not ev.pricing_ready:
            widerspruch.append({
                "account_id": r["account_id"],
                "item_id": r["id"],
                "name": (data.get("name") or "")[:80],
                "price_state": state,
                "price_source": data.get("price_source"),
                "est_value": data.get("est_value"),
                "blocking": [x.value for x in ev.blocking_reasons],
                "recognition_state": ev.recognition_state.value,
            })
        if data.get("status") == "ready" and not ev.pricing_ready:
            needs_review_candidates.append(r["id"])
    print(f"DB: {db}")
    print(f"Items gesamt: {len(rows)}")
    print(f"Widerspruch price_state belegt|spanne + !pricing_ready: {len(widerspruch)}")
    print(f"ready + !pricing_ready (Kandidaten needs_review): {len(needs_review_candidates)}")
    print("--- Vorschau (max 40) ---")
    for w in widerspruch[:40]:
        print(json.dumps(w, ensure_ascii=False))
    print("--- Migrationsvorschau (keine Ausführung) ---")
    print("Vorgeschlagene Aktion nach Freigabe:")
    print("  1) identity_eval neu berechnen und speichern")
    print("  2) status=needs_review nur wenn Nutzer Freigabe gibt")
    print("  3) price_state=belegt bei !pricing_ready NICHT still belassen")
    print("  4) KEINE Massen-Neuerkennung / KEINE Preis-API in dieser Migration")
    print("Keine Änderungen geschrieben.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
