#!/usr/bin/env python3
"""Dry-Run Migration alter Katalog-Keys → Identity-Key v2.

Default: --dry-run (keine Schreibzugriffe auf card_prices).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--apply", action="store_true", help="Nur mit ausdrücklicher Freigabe")
    args = ap.parse_args()
    dry = not args.apply

    # Keine Live-DB ohne SERO_DB
    db = os.environ.get("SERO_DB")
    report = {
        "dry_run": dry,
        "db": db or "(nicht gesetzt — Abbruch)",
        "collisions": [],
        "migratable": [],
        "skipped_ref_only": [],
        "note": "Ohne volle Identitätsübereinstimmung keine Übernahme von game:ref_id",
    }
    if not db:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1

    from bot.store import Store
    from web.pricing_v2.keys import alias_ref, identity_key_v2, price_key_v2

    store = Store(db)
    rows = store._conn.execute("SELECT card_key, payload FROM cards").fetchall() if False else []
    # Schema-kompatibel lesen
    try:
        cards = store._conn.execute("SELECT * FROM cards").fetchall()
    except Exception as e:
        report["error"] = str(e)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1

    by_new: dict[str, list[str]] = {}
    for row in cards:
        d = dict(row)
        card = {
            "game": d.get("game"),
            "name": d.get("name"),
            "number": d.get("number"),
            "set_name": d.get("set_name"),
            "language": d.get("language"),
            "edition": d.get("edition"),
            "ref_id": d.get("ref_id"),
        }
        old = d.get("card_key") or d.get("key")
        new = identity_key_v2(card)
        if old and str(old).startswith(str(card.get("game") or "") + ":") and card.get("ref_id"):
            report["skipped_ref_only"].append({
                "old": old,
                "alias": alias_ref(card),
                "proposed": new or None,
                "reason": "ref_id_only_needs_full_identity",
            })
            continue
        if not new:
            continue
        by_new.setdefault(new, []).append(str(old))
        report["migratable"].append({"old": old, "new": new, "price_key": price_key_v2(card)})

    for nk, olds in by_new.items():
        if len(set(olds)) > 1:
            report["collisions"].append({"new": nk, "olds": sorted(set(olds))})

    out = Path("tmp/identity_key_migration_dry_run.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "dry_run": dry,
        "migratable": len(report["migratable"]),
        "collisions": len(report["collisions"]),
        "skipped_ref_only": len(report["skipped_ref_only"]),
        "out": str(out),
    }, indent=2))
    if args.apply:
        print("APPLY nicht implementiert — erst Freigabe + Kollisionsreview")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
