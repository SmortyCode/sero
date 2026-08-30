"""Unit-Tests für Cutout-Metriken und QA-Hard-Fails (synthetisch, ohne rembg)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from web.cutout_v2.metrics import (
    analyze_cutout,
    binary_mask,
    boundary_f1,
    dice,
    iou,
    sad_mse,
)
from web.cutout_v2.qa import evaluate_candidate
from web.cutout_v2.routing import resolve_kind
from web.cutout_v2.types import CutoutKind, KindResolveState, KindSource


def _rgba(tmp_path: Path, name: str, alpha: np.ndarray) -> Path:
    h, w = alpha.shape
    rgb = np.full((h, w, 3), 40, dtype=np.uint8)
    a = (np.clip(alpha, 0, 1) * 255).astype(np.uint8)
    arr = np.dstack([rgb, a])
    p = tmp_path / name
    Image.fromarray(arr, "RGBA").save(p)
    return p


def test_iou_dice_perfect():
    m = np.zeros((20, 20), dtype=bool)
    m[5:15, 5:15] = True
    assert iou(m, m) == 1.0
    assert dice(m, m) == 1.0


def test_boundary_f1_and_sad():
    a = np.zeros((30, 30), dtype=bool)
    b = np.zeros((30, 30), dtype=bool)
    a[5:25, 5:25] = True
    b[6:26, 6:26] = True
    assert 0.0 < boundary_f1(a, b) <= 1.0
    aa = a.astype(float)
    bb = b.astype(float)
    sad, mse = sad_mse(aa, bb)
    assert sad > 0 and mse > 0


def test_nearly_opaque_hard_fail(tmp_path):
    alpha = np.ones((200, 120), dtype=np.float64)
    p = _rgba(tmp_path, "opaque.png", alpha)
    ev = evaluate_candidate(p, CutoutKind.GRADED_SLAB)
    assert not ev["ok"]
    assert "nearly_opaque_canvas" in ev["hard_fails"] or "bbox_touches_canvas" in ev["hard_fails"]


def test_good_margin_passes(tmp_path):
    alpha = np.zeros((200, 120), dtype=np.float64)
    alpha[20:180, 15:105] = 1.0
    p = _rgba(tmp_path, "ok.png", alpha)
    ev = evaluate_candidate(p, CutoutKind.GRADED_SLAB)
    assert ev["ok"], ev["hard_fails"]
    assert ev["quality_score"] > 0.5


def test_warp_only_never_success(tmp_path):
    alpha = np.zeros((200, 120), dtype=np.float64)
    alpha[20:180, 15:105] = 1.0
    p = _rgba(tmp_path, "warp.png", alpha)
    ev = evaluate_candidate(p, CutoutKind.GRADED_SLAB, is_warp_only=True)
    assert not ev["ok"]
    assert "warp_only_not_cutout" in ev["hard_fails"]


def test_anchor_opaque_file_fails_qa():
    p = Path("collection_photos/376e7889dd81/00_cut.png")
    if not p.exists():
        pytest.skip("Ankerbild fehlt lokal")
    ev = evaluate_candidate(p, CutoutKind.GRADED_SLAB)
    # Audit: praktisch opak → muss Hard-Fail haben
    assert not ev["ok"]
    assert any(x in ev["hard_fails"] for x in (
        "nearly_opaque_canvas", "bbox_touches_canvas", "foreground_fills_canvas",
        "opaque_min_area_rect_suspect",
    )), ev["hard_fails"]


def test_graded_routing_confirmed():
    kind, src, state, conf = resolve_kind(item={"graded": True, "graded_info": {"grader": "CGC"}})
    assert kind == CutoutKind.GRADED_SLAB
    assert src == KindSource.CONFIRMED
    assert state == KindResolveState.CONFIRMED
    assert conf == 1.0


def test_vision_error_not_product():
    kind, src, state, conf = resolve_kind(vision_error=True)
    assert kind is None
    assert state == KindResolveState.VISION_ERROR
