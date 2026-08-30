"""Getypte Strukturen für CutoutPipelineV2."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


PIPELINE_VERSION = "cutout-v2.0.0"


class CutoutKind(str, Enum):
    RAW_CARD = "raw_card"
    SLEEVE_TOPLOADER = "sleeve_toploader"
    GRADED_SLAB = "graded_slab"
    SEALED_PRODUCT = "sealed_product"
    BUNDLE = "bundle"


class CutoutStatus(str, Enum):
    SUCCESS = "SUCCESS"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    FAILED = "FAILED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    VALIDATING = "VALIDATING"


class KindSource(str, Enum):
    CONFIRMED = "confirmed"
    PERSISTED = "persisted"
    GEOMETRY = "geometry"
    VISION = "vision"
    UNSPECIFIED = "unspecified"


class KindResolveState(str, Enum):
    CONFIRMED = "CONFIRMED"
    INFERRED = "INFERRED"
    UNCERTAIN = "UNCERTAIN"
    VISION_ERROR = "VISION_ERROR"


@dataclass(frozen=True)
class CutoutRequest:
    source_path: Path
    confirmed_kind: CutoutKind
    kind_source: str
    expected_geometry: dict[str, Any] | None = None
    pipeline_version: str = PIPELINE_VERSION
    output_path: Path | None = None
    item_id: str | None = None
    mode: str = "studio_catalog"
    allow_replace_worse: bool = False


@dataclass
class CutoutResult:
    status: str
    selected_path: Path | None
    route: str
    model: str | None
    model_revision: str | None
    model_sha256: str | None
    source_sha256: str
    quality_score: float | None
    checks: dict[str, Any] = field(default_factory=dict)
    attempts: list[dict[str, Any]] = field(default_factory=list)
    fallback_reason: str | None = None
    runtime_ms: int = 0
    cache_key: str | None = None
    hard_fails: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "selected_path": str(self.selected_path) if self.selected_path else None,
            "route": self.route,
            "model": self.model,
            "model_revision": self.model_revision,
            "model_sha256": self.model_sha256,
            "source_sha256": self.source_sha256,
            "quality_score": self.quality_score,
            "checks": self.checks,
            "attempts": self.attempts,
            "fallback_reason": self.fallback_reason,
            "runtime_ms": self.runtime_ms,
            "cache_key": self.cache_key,
            "hard_fails": self.hard_fails,
        }


def legacy_kind_to_cutout(kind: str | None) -> CutoutKind | None:
    if kind is None:
        return None
    m = {
        "raw": CutoutKind.RAW_CARD,
        "sleeve": CutoutKind.SLEEVE_TOPLOADER,
        "slab": CutoutKind.GRADED_SLAB,
        "other": CutoutKind.SEALED_PRODUCT,
        "product": CutoutKind.SEALED_PRODUCT,
        "bundle": CutoutKind.BUNDLE,
        "raw_card": CutoutKind.RAW_CARD,
        "sleeve_toploader": CutoutKind.SLEEVE_TOPLOADER,
        "graded_slab": CutoutKind.GRADED_SLAB,
        "sealed_product": CutoutKind.SEALED_PRODUCT,
    }
    return m.get(kind)


def cutout_kind_to_legacy(kind: CutoutKind) -> str:
    return {
        CutoutKind.RAW_CARD: "raw",
        CutoutKind.SLEEVE_TOPLOADER: "sleeve",
        CutoutKind.GRADED_SLAB: "slab",
        CutoutKind.SEALED_PRODUCT: "other",
        CutoutKind.BUNDLE: "other",
    }[kind]
