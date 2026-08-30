#!/usr/bin/env python3
"""Gold-/Referenz-Eval für Cutouts.

- Nutzt tests/fixtures/cutout_gold/manifest.json (Fallback: cutout_refs.json)
- Ruft jedes Profil mit korrektem kind auf
- Erfolg = QA bestanden (+ optional GT-Metriken), nicht nur „Datei existiert"
- Multi-BG-Render; SHA256-Schutz der Quellen
- Schreibt nur nach tmp/cutout_eval/
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from web.cutout_v2.metrics import (  # noqa: E402
    analyze_cutout,
    render_preview_set,
    sha256_file,
)
from web.cutout_v2.qa import evaluate_candidate  # noqa: E402
from web.cutout_v2.types import CutoutKind, CutoutRequest, KindSource  # noqa: E402
from web.cutout_v2.pipeline import run_cutout  # noqa: E402

OUT = WURZEL / "tmp" / "cutout_eval"
GOLD = WURZEL / "tests/fixtures/cutout_gold/manifest.json"
REFS = WURZEL / "tests/fixtures/cutout_refs.json"


def load_cases() -> list[dict]:
    if GOLD.exists():
        return json.loads(GOLD.read_text(encoding="utf-8"))["cases"]
    refs = json.loads(REFS.read_text(encoding="utf-8"))["refs"]
    out = []
    for r in refs:
        out.append({
            "id": r["id"],
            "kind": "graded_slab" if r.get("raw") else "sealed_product",
            "source_path": r.get("raw"),
            "source_sha256": None,
            "gt_alpha_path": r["photo"] if r.get("has_alpha") else None,
            "approved": bool(r.get("has_alpha")),
        })
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report = []
    ok_all = True
    for case in load_cases():
        cid = case["id"]
        dest = OUT / cid
        dest.mkdir(parents=True, exist_ok=True)
        src_rel = case.get("source_path")
        if not src_rel:
            # Nur Baseline/GT prüfen
            base = case.get("baseline_cut_path") or case.get("gt_alpha_path")
            if not base:
                report.append({"id": cid, "ok": False, "reason": "no_source"})
                ok_all = False
                continue
            p = WURZEL / base
            if case.get("source_sha256") and p.exists():
                got = sha256_file(p)
                # bei GT-Pfad ist sha die des GT, ok
            kind = CutoutKind(case["kind"])
            ev = evaluate_candidate(p, kind, require_margin=True,
                                    gt_path=(WURZEL / case["gt_alpha_path"]) if case.get("gt_alpha_path") else None)
            render_preview_set(p, dest)
            entry = {"id": cid, "ok": ev["ok"], "hard_fails": ev["hard_fails"],
                     "quality_score": ev["quality_score"], "metrics": ev["metrics"],
                     "mode": "baseline_only"}
            report.append(entry)
            if not ev["ok"]:
                ok_all = False
            print(f"-> {cid} baseline_only ok={ev['ok']} fails={ev['hard_fails']}")
            continue

        src = WURZEL / src_rel
        if not src.exists():
            report.append({"id": cid, "ok": False, "reason": "source_missing"})
            ok_all = False
            continue
        expected = case.get("source_sha256")
        if expected:
            got = sha256_file(src)
            if got != expected:
                report.append({"id": cid, "ok": False, "reason": "sha256_mismatch",
                               "expected": expected, "got": got})
                ok_all = False
                print(f"-> {cid} SHA256 MISMATCH")
                continue

        kind = CutoutKind(case["kind"])
        out_cut = dest / "result_cut.png"
        result = run_cutout(CutoutRequest(
            source_path=src,
            confirmed_kind=kind,
            kind_source=KindSource.CONFIRMED.value,
            output_path=out_cut,
            item_id=cid,
            allow_replace_worse=True,
        ))
        success = result.status == "SUCCESS" and out_cut.exists()
        metrics = analyze_cutout(out_cut, gt_path=(WURZEL / case["gt_alpha_path"]) if case.get("gt_alpha_path") and (WURZEL / case["gt_alpha_path"]).exists() else None) if out_cut.exists() else {}
        if out_cut.exists():
            render_preview_set(out_cut, dest)
        entry = {
            "id": cid,
            "ok": success,
            "status": result.status,
            "hard_fails": result.hard_fails,
            "quality_score": result.quality_score,
            "route": result.route,
            "model": result.model,
            "runtime_ms": result.runtime_ms,
            "metrics": metrics,
        }
        report.append(entry)
        if not success:
            ok_all = False
        print(f"-> {cid} status={result.status} score={result.quality_score} fails={result.hard_fails}")

    (OUT / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nFertig: {OUT} ok_all={ok_all}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
