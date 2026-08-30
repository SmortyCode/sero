"""Atomare Speicherung und Cache-Keys für Cutout-Kandidaten."""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from web.cutout_v2.types import CutoutKind


def file_sha256(path: Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cache_key(
    source_sha256: str,
    kind: CutoutKind,
    pipeline_version: str,
    model_revision: str | None,
    model_sha256: str | None,
) -> str:
    raw = "|".join([
        source_sha256,
        kind.value,
        pipeline_version,
        model_revision or "",
        model_sha256 or "",
    ])
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def atomic_replace(tmp: Path, dest: Path, *, keep_prev: bool = True) -> None:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if keep_prev and dest.exists():
        prev = dest.with_name(dest.stem + ".prev.png")
        try:
            if prev.exists():
                prev.unlink()
            dest.replace(prev)
        except OSError:
            pass
    os.replace(str(tmp), str(dest))


def candidate_temp_path(dest: Path, attempt: int) -> Path:
    dest = Path(dest)
    return dest.with_name(
        f".{dest.stem}.cand{attempt}.{os.getpid()}.{int(time.time()*1000)}.png")


def write_sidecar(dest: Path, meta: dict[str, Any]) -> None:
    side = Path(dest).with_suffix(Path(dest).suffix + ".cutout_v2.json")
    side.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


def shadow_dir(item_id: str | None, stem: str) -> Path:
    root = Path(__file__).resolve().parent.parent.parent / "tmp" / "cutout_shadow"
    part = item_id or "_anon"
    d = root / part / stem
    d.mkdir(parents=True, exist_ok=True)
    return d
