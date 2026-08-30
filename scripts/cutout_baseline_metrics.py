#!/usr/bin/env python3
"""Read-only Baseline-Metriken für bestehende *_cut.png (keine Collection-Schreibzugriffe).

Schreibt nur nach tmp/cutout_baseline/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from web.cutout_v2.metrics import analyze_cutout, sha256_file  # noqa: E402

OUT = WURZEL / "tmp" / "cutout_baseline"
COL = WURZEL / "collection_photos"
ANCHORS = ("376e7889dd81", "446ad78526af")


def collect_cut_pngs() -> list[Path]:
    if not COL.exists():
        return []
    paths = sorted(COL.glob("*/*_cut.png"))
    return [p for p in paths if "_w" not in p.name and ".prev" not in p.name]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    nearly_opaque = 0
    canvas_touch = 0
    for p in collect_cut_pngs():
        try:
            m = analyze_cutout(p)
        except Exception as e:  # noqa: BLE001
            rows.append({"path": str(p.relative_to(WURZEL)), "error": str(e)})
            continue
        entry = {
            "id": p.parent.name,
            "path": str(p.relative_to(WURZEL)),
            "source_sha256": sha256_file(p),
            "fully_transparent_frac": m["fully_transparent_frac"],
            "nearly_opaque": m["nearly_opaque"],
            "canvas_touch": m["canvas_touch"],
            "aspect": m["aspect"],
            "components": m["components"],
            "rectangularity": m["rectangularity"],
            "pad": m["pad"],
            "fg_frac": m["fg_frac"],
        }
        if m["nearly_opaque"]:
            nearly_opaque += 1
        if m["canvas_touch"]:
            canvas_touch += 1
        rows.append(entry)

    anchors = {}
    for aid in ANCHORS:
        p = COL / aid / "00_cut.png"
        if p.exists():
            anchors[aid] = analyze_cutout(p)
            anchors[aid]["source_sha256"] = sha256_file(p)

    summary = {
        "n": len(rows),
        "nearly_opaque_lt_1pct_transparent": nearly_opaque,
        "canvas_touch": canvas_touch,
        "anchors": {k: {
            "nearly_opaque": v.get("nearly_opaque"),
            "fully_transparent_frac": v.get("fully_transparent_frac"),
            "canvas_touch": v.get("canvas_touch"),
            "aspect": v.get("aspect"),
        } for k, v in anchors.items()},
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "report.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Geschrieben: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
