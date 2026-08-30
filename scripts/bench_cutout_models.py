#!/usr/bin/env python3
"""Schreibt Adapter-Status in docs/cutout_model_benchmark.md (keine ungeprüften Defaults)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from web.cutout_v2.adapters import ALL_ADAPTERS, ADAPTER_BRIA_RMBG  # noqa: E402

OUT = WURZEL / "tmp" / "cutout_bench"
OUT.mkdir(parents=True, exist_ok=True)

rows = []
for a in ALL_ADAPTERS:
    rows.append({
        **a.identity(),
        "notes": a.notes,
        "prod_default_allowed": a.available and a.license_status == "commercial_ok" and a.name != ADAPTER_BRIA_RMBG.name,
    })
(OUT / "adapters.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
print(json.dumps(rows, indent=2))
assert any(r["model"] == "bria-rmbg-2.0" and not r["available"] for r in rows)
print("BRIA blockiert OK")
