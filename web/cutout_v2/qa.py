"""Hard-Fail-QA und Quality-Score für Cutout-Kandidaten."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from web.cutout_v2.metrics import analyze_cutout
from web.cutout_v2.types import CutoutKind


MIN_FULL_TRANSPARENT = {
    CutoutKind.RAW_CARD: 0.02,
    CutoutKind.SLEEVE_TOPLOADER: 0.02,
    CutoutKind.GRADED_SLAB: 0.02,
    CutoutKind.SEALED_PRODUCT: 0.01,
    CutoutKind.BUNDLE: 0.01,
}

ASPECT_RANGE = {
    CutoutKind.RAW_CARD: (1.15, 1.65),
    CutoutKind.SLEEVE_TOPLOADER: (1.15, 1.75),
    CutoutKind.GRADED_SLAB: (1.48, 2.15),
    CutoutKind.SEALED_PRODUCT: (0.35, 3.5),
    CutoutKind.BUNDLE: (0.35, 3.5),
}


def evaluate_candidate(
    path: Path | str,
    kind: CutoutKind,
    *,
    require_margin: bool = True,
    is_warp_only: bool = False,
    is_original: bool = False,
    gt_path: Path | str | None = None,
) -> dict[str, Any]:
    path = Path(path)
    report = analyze_cutout(path, gt_path=gt_path)
    fails: list[str] = []

    if is_warp_only:
        fails.append("warp_only_not_cutout")
    if is_original:
        fails.append("original_not_cutout")
    if report["mode"] not in ("RGBA", "LA"):
        fails.append("no_alpha_channel")

    ft = report["fully_transparent_frac"]
    min_ft = MIN_FULL_TRANSPARENT.get(kind, 0.01)
    if require_margin and ft < min_ft:
        fails.append("nearly_opaque_canvas")
    if report["fg_frac"] < 0.01:
        fails.append("empty_or_near_empty_mask")
    if report["fg_frac"] > 0.98 and require_margin:
        fails.append("foreground_fills_canvas")
    if require_margin and report["canvas_touch"]:
        fails.append("bbox_touches_canvas")

    aspect = report.get("aspect")
    lo, hi = ASPECT_RANGE.get(kind, (0.2, 5.0))
    if aspect is not None and not (lo <= aspect <= hi):
        fails.append(f"aspect_out_of_range:{aspect}")

    if kind in (CutoutKind.GRADED_SLAB, CutoutKind.SLEEVE_TOPLOADER):
        if report.get("rectangularity", 0) > 0.995 and ft < 0.05:
            fails.append("opaque_min_area_rect_suspect")
    if kind == CutoutKind.GRADED_SLAB and report.get("components", 0) == 0:
        fails.append("slab_no_foreground")

    score = 1.0
    score -= 0.5 if report["canvas_touch"] else 0.0
    score -= max(0.0, 0.3 - ft)
    if aspect is not None:
        mid = (lo + hi) / 2
        score -= min(0.25, abs(aspect - mid) / mid * 0.25)
    if report.get("components", 1) > 4 and kind != CutoutKind.BUNDLE:
        score -= 0.1 * (report["components"] - 4)
    vs = report.get("vs_gt") or {}
    if "iou" in vs:
        score = 0.4 * score + 0.6 * float(vs["iou"])

    return {
        "ok": not fails,
        "hard_fails": fails,
        "quality_score": round(max(0.0, score), 4),
        "metrics": report,
    }
