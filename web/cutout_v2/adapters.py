"""Modelladapter mit gepinnter Revision und Lizenzstatus."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from web.cutout_v2.types import CutoutKind


@dataclass(frozen=True)
class ModelAdapter:
    name: str
    revision: str
    weight_sha256: str | None
    license_status: str
    available: bool
    notes: str = ""

    def identity(self) -> dict:
        return {
            "model": self.name,
            "model_revision": self.revision,
            "model_sha256": self.weight_sha256,
            "license_status": self.license_status,
            "available": self.available,
        }


ADAPTER_BIREFNET_GENERAL = ModelAdapter(
    name="birefnet-general",
    revision="rembg-pinned",
    weight_sha256=None,
    license_status="commercial_ok",
    available=True,
    notes="Baseline Rohkarte/Produkt",
)
ADAPTER_ISNET_SLAB = ModelAdapter(
    name="isnet-general-use",
    revision="rembg-pinned",
    weight_sha256=None,
    license_status="commercial_ok",
    available=True,
    notes="Baseline Graded/Slab",
)
ADAPTER_BIREFNET_HR_MATTING = ModelAdapter(
    name="birefnet-hr-matting",
    revision="unavailable",
    weight_sha256=None,
    license_status="unknown",
    available=False,
    notes="Bevorzugter Self-Host-Kandidat; Weights fehlen",
)
ADAPTER_TRANSPARENT_BG = ModelAdapter(
    name="inspyrenet-transparent-background",
    revision="unavailable",
    weight_sha256=None,
    license_status="unknown",
    available=False,
)
ADAPTER_BEN2 = ModelAdapter(
    name="ben2-base",
    revision="unavailable",
    weight_sha256=None,
    license_status="unknown",
    available=False,
)
ADAPTER_SAM2_VITMATTE = ModelAdapter(
    name="sam2-vitmatte",
    revision="unavailable",
    weight_sha256=None,
    license_status="unknown",
    available=False,
    notes="Slab-Fallback Stub",
)
ADAPTER_PICSART = ModelAdapter(
    name="picsart",
    revision="api",
    weight_sha256=None,
    license_status="commercial_ok",
    available=bool(os.environ.get("SERO_PICSART_KEY")),
    notes="Feature-Flag + Key nötig; kein Key im Repo",
)
ADAPTER_PHOTOROOM = ModelAdapter(
    name="photoroom",
    revision="api",
    weight_sha256=None,
    license_status="commercial_ok",
    available=bool(os.environ.get("SERO_PHOTOROOM_KEY")),
    notes="Feature-Flag + Key nötig; kein Key im Repo",
)
ADAPTER_BRIA_RMBG = ModelAdapter(
    name="bria-rmbg-2.0",
    revision="blocked",
    weight_sha256=None,
    license_status="non_commercial",
    available=False,
    notes="CC BY-NC 4.0 — nicht als kommerzieller Standard",
)

ALL_ADAPTERS = [
    ADAPTER_BIREFNET_GENERAL,
    ADAPTER_ISNET_SLAB,
    ADAPTER_BIREFNET_HR_MATTING,
    ADAPTER_TRANSPARENT_BG,
    ADAPTER_BEN2,
    ADAPTER_SAM2_VITMATTE,
    ADAPTER_PICSART,
    ADAPTER_PHOTOROOM,
    ADAPTER_BRIA_RMBG,
]


def adapters_for_kind(kind: CutoutKind) -> list[ModelAdapter]:
    if kind == CutoutKind.GRADED_SLAB:
        chain = [ADAPTER_ISNET_SLAB, ADAPTER_BIREFNET_GENERAL, ADAPTER_SAM2_VITMATTE]
    elif kind in (CutoutKind.RAW_CARD, CutoutKind.SLEEVE_TOPLOADER):
        chain = [ADAPTER_BIREFNET_GENERAL, ADAPTER_BIREFNET_HR_MATTING, ADAPTER_TRANSPARENT_BG]
    else:
        # Alltagsstücke: isnet als normaler Background-Remover (kein BiRefNet).
        chain = [ADAPTER_ISNET_SLAB, ADAPTER_TRANSPARENT_BG, ADAPTER_BEN2]
    return [a for a in chain if a.available and a.license_status == "commercial_ok"]


def run_legacy_rembg(source: Path, dest: Path, kind: CutoutKind) -> tuple[bool, ModelAdapter]:
    from web import cardscan
    from web.cutout_v2.types import cutout_kind_to_legacy

    adapter = (
        ADAPTER_ISNET_SLAB
        if kind in (CutoutKind.GRADED_SLAB, CutoutKind.SEALED_PRODUCT, CutoutKind.BUNDLE)
        else ADAPTER_BIREFNET_GENERAL
    )
    legacy = cutout_kind_to_legacy(kind)
    ok = bool(cardscan._cutout(str(source), str(dest), legacy))
    return ok, adapter
