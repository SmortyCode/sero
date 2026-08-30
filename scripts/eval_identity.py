#!/usr/bin/env python3
"""Identity-Eval: Offline-Fixtures + Live nur mit SERO_EVAL_LIVE=1.

Offline (Default):
  - Manifest mit analysis/card_info/expect_* Feldern
  - keine externen Kosten, deterministisch

Live nur mit Opt-in:
  - SERO_EVAL_LIVE=1
  - niemals in CI
  - keine Preisabfrage, keine eBay-Aktion, keine Collection-Änderung
  - aktuell: bricht ab, bis ein begrenzter Bildpfad verdrahtet ist

Report: Produkttyp, Name, Nummer, Set, Sprache, Plattform/Region, Grading,
Anteil ready / needs_review / falsche sichere Erkennungen.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from web.identity import (  # noqa: E402
    evaluate_identity,
    identity_from_item,
    normalize_legacy_analysis,
)


def _field(ident, name: str):
    fv = getattr(ident, name, None)
    return None if fv is None else fv.value


def evaluate_row(row: dict) -> dict:
    item = {
        "analysis": row.get("analysis") or {},
        "card_info": row.get("card_info") or {},
        "graded": row.get("graded") or {},
        "name": row.get("name"),
        "category": row.get("category"),
    }
    if item["card_info"] or item["graded"]:
        ident = identity_from_item(item)
    else:
        ident = normalize_legacy_analysis(item["analysis"])
    ev = evaluate_identity(ident)
    got = {
        "kind": ident.kind.value if ident.kind else None,
        "name": _field(ident, "name"),
        "number": _field(ident, "number"),
        "set_name": _field(ident, "set_name"),
        "language": _field(ident, "language"),
        "platform": _field(ident, "platform"),
        "region": _field(ident, "region"),
        "grader": _field(ident, "grader"),
        "grade": _field(ident, "grade"),
        "pricing_ready": ev.pricing_ready,
        "recognition_state": ev.recognition_state.value,
        "blocking": [r.value for r in ev.blocking_reasons],
    }
    expect = row.get("expect") or {}
    field_ok = {}
    for k, exp in expect.items():
        if k in ("pricing_ready", "recognition_state"):
            continue
        field_ok[k] = (str(got.get(k) or "").lower() == str(exp or "").lower())
    wrong_safe = False
    if expect.get("pricing_ready") is False and got["pricing_ready"]:
        wrong_safe = True
    if expect.get("recognition_state") == "needs_review" and got["pricing_ready"]:
        wrong_safe = True
    ready_ok = True
    if "expect_pricing_ready" in row:
        ready_ok = bool(got["pricing_ready"]) == bool(row["expect_pricing_ready"])
    elif "pricing_ready" in expect:
        ready_ok = bool(got["pricing_ready"]) == bool(expect["pricing_ready"])
    return {
        "id": row.get("id"),
        "got": got,
        "field_ok": field_ok,
        "ready_ok": ready_ok,
        "wrong_safe": wrong_safe,
    }


def main(argv: list[str]) -> int:
    live = os.environ.get("SERO_EVAL_LIVE", "0").strip() == "1"
    if len(argv) < 2:
        print("Usage: python scripts/eval_identity.py manifest.json")
        print("       SERO_EVAL_LIVE=1 …  # nur mit verdrahtetem Live-Pfad")
        return 2
    if live:
        print("SERO_EVAL_LIVE=1: Live-Erkennung noch nicht verdrahtet. "
              "Kein Netzaufruf, keine Preis-/eBay-Aktion.")
        return 3

    manifest = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    results = [evaluate_row(row) for row in manifest]
    states = Counter(r["got"]["recognition_state"] for r in results)
    wrong_safe = sum(1 for r in results if r["wrong_safe"])
    fail = sum(1 for r in results if (not r["ready_ok"]) or r["wrong_safe"]
               or (r["field_ok"] and not all(r["field_ok"].values())))
    ok = len(results) - fail

    print("=== Identity Eval (offline) ===")
    print(f"n={len(results)} ok={ok} fail={fail}")
    print(f"recognition_state: {dict(states)}")
    print(f"falsche sichere Erkennungen (worst metric): {wrong_safe}")
    for r in results:
        status = "OK" if r["ready_ok"] and not r["wrong_safe"] and all(
            r["field_ok"].values() or [True]) else "FAIL"
        print(f"{status} {r['id']}: ready={r['got']['pricing_ready']} "
              f"state={r['got']['recognition_state']} "
              f"set={r['got']['set_name']} lang={r['got']['language']}")
    return 1 if fail or wrong_safe else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
