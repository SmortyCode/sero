"""CutoutPipelineV2 — gemeinsamer Freistell-Kern für Scan, Recrop, Render, Telegram.

Feature-Flags:
  SERO_CUTOUT_V2=1         — Produktionspfad über run_cutout
  SERO_CUTOUT_V2_SHADOW=1  — parallel schreiben nach tmp/cutout_shadow/, Legacy bleibt
"""
from __future__ import annotations

from web.cutout_v2.pipeline import run_cutout
from web.cutout_v2.types import (
    CutoutKind,
    CutoutRequest,
    CutoutResult,
    CutoutStatus,
    KindSource,
    PIPELINE_VERSION,
)

__all__ = [
    "PIPELINE_VERSION",
    "CutoutKind",
    "CutoutRequest",
    "CutoutResult",
    "CutoutStatus",
    "KindSource",
    "run_cutout",
]
