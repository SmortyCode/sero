"""CutoutPipelineV2 — Kandidaten, QA, atomare Auswahl."""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path

from web.cutout_v2.adapters import adapters_for_kind, run_legacy_rembg
from web.cutout_v2.qa import evaluate_candidate
from web.cutout_v2.storage import (
    atomic_replace,
    cache_key,
    candidate_temp_path,
    file_sha256,
    shadow_dir,
    write_sidecar,
)
from web.cutout_v2.types import (
    PIPELINE_VERSION,
    CutoutKind,
    CutoutRequest,
    CutoutResult,
    CutoutStatus,
)

log = logging.getLogger("sero.cutout_v2")
_CUTOUT_LOCK = threading.Lock()


def flags(item_id: str | None = None) -> dict[str, bool]:
    from web.pipeline_flags import cutout_v2_enabled, cutout_v2_shadow
    return {
        "v2": cutout_v2_enabled(item_id),
        "shadow": cutout_v2_shadow(item_id),
    }


def run_cutout(request: CutoutRequest) -> CutoutResult:
    """Eine öffentliche Einstiegsfunktion für alle Aufrufer."""
    t0 = time.monotonic()
    src = Path(request.source_path)
    if not src.exists():
        return CutoutResult(
            status=CutoutStatus.FAILED.value,
            selected_path=None,
            route="missing_source",
            model=None,
            model_revision=None,
            model_sha256=None,
            source_sha256="",
            quality_score=None,
            fallback_reason="source_missing",
            runtime_ms=0,
            hard_fails=["source_missing"],
        )

    source_sha = file_sha256(src)
    kind = request.confirmed_kind
    dest = Path(request.output_path) if request.output_path else src.with_name(src.stem + "_cut.png")
    route = f"{kind.value}:{request.mode}"
    attempts: list[dict] = []
    best: dict | None = None
    best_path: Path | None = None

    with _CUTOUT_LOCK:
        available = adapters_for_kind(kind)
        if not available:
            return CutoutResult(
                status=CutoutStatus.NEEDS_REVIEW.value,
                selected_path=None,
                route=route,
                model=None,
                model_revision=None,
                model_sha256=None,
                source_sha256=source_sha,
                quality_score=None,
                fallback_reason="no_available_adapter",
                runtime_ms=int((time.monotonic() - t0) * 1000),
                hard_fails=["no_available_adapter"],
            )

        for i, adapter in enumerate(available):
            tmp = candidate_temp_path(dest, i)
            try:
                ok, used = run_legacy_rembg(src, tmp, kind)
            except Exception as e:  # noqa: BLE001
                log.warning("cutout_v2 adapter %s failed: %s", adapter.name, e)
                attempts.append({"model": adapter.name, "ok": False, "error": str(e)})
                continue
            if not ok or not tmp.exists():
                attempts.append({"model": used.name, "ok": False, "error": "adapter_false"})
                if tmp.exists():
                    try:
                        tmp.unlink()
                    except OSError:
                        pass
                continue

            ev = evaluate_candidate(tmp, kind, require_margin=True)
            att = {
                "model": used.name,
                "model_revision": used.revision,
                "ok": ev["ok"],
                "quality_score": ev["quality_score"],
                "hard_fails": ev["hard_fails"],
                "tmp": str(tmp),
            }
            attempts.append(att)
            if not ev["ok"]:
                try:
                    tmp.unlink()
                except OSError:
                    pass
                continue
            if best is None or ev["quality_score"] >= best["quality_score"]:
                if best_path and best_path.exists() and best_path != tmp:
                    try:
                        best_path.unlink()
                    except OSError:
                        pass
                best = att
                best_path = tmp
            else:
                try:
                    tmp.unlink()
                except OSError:
                    pass

        runtime = int((time.monotonic() - t0) * 1000)
        if best is None or best_path is None:
            fails = []
            for a in attempts:
                fails.extend(a.get("hard_fails") or [])
            return CutoutResult(
                status=CutoutStatus.NEEDS_REVIEW.value,
                selected_path=None,
                route=route,
                model=attempts[0]["model"] if attempts else None,
                model_revision=None,
                model_sha256=None,
                source_sha256=source_sha,
                quality_score=None,
                checks={"attempts": len(attempts)},
                attempts=attempts,
                fallback_reason="all_candidates_failed_qa",
                runtime_ms=runtime,
                hard_fails=list(dict.fromkeys(fails)) or ["all_candidates_failed_qa"],
            )

        ck = cache_key(
            source_sha, kind, request.pipeline_version or PIPELINE_VERSION,
            best.get("model_revision"), None,
        )

        if dest.exists() and not request.allow_replace_worse:
            prev_ev = evaluate_candidate(dest, kind, require_margin=True)
            if prev_ev["ok"] and prev_ev["quality_score"] > best["quality_score"]:
                try:
                    best_path.unlink()
                except OSError:
                    pass
                return CutoutResult(
                    status=CutoutStatus.SUCCESS.value,
                    selected_path=dest,
                    route=route,
                    model=best["model"],
                    model_revision=best.get("model_revision"),
                    model_sha256=None,
                    source_sha256=source_sha,
                    quality_score=prev_ev["quality_score"],
                    checks=prev_ev["metrics"],
                    attempts=attempts,
                    fallback_reason="kept_better_existing",
                    runtime_ms=runtime,
                    cache_key=ck,
                )

        fl = flags(request.item_id)
        if fl["shadow"] and not fl["v2"]:
            sdir = shadow_dir(request.item_id, src.stem)
            shadow_out = sdir / "result_cut.png"
            atomic_replace(best_path, shadow_out, keep_prev=True)
            meta = {
                "cache_key": ck,
                "kind": kind.value,
                "pipeline_version": request.pipeline_version,
                "model": best["model"],
                "quality_score": best["quality_score"],
                "source_sha256": source_sha,
                "attempts": attempts,
            }
            write_sidecar(shadow_out, meta)
            return CutoutResult(
                status=CutoutStatus.SUCCESS.value,
                selected_path=shadow_out,
                route=route + ":shadow",
                model=best["model"],
                model_revision=best.get("model_revision"),
                model_sha256=None,
                source_sha256=source_sha,
                quality_score=best["quality_score"],
                checks={"shadow": True},
                attempts=attempts,
                runtime_ms=runtime,
                cache_key=ck,
            )

        atomic_replace(best_path, dest, keep_prev=True)
        write_sidecar(dest, {
            "cache_key": ck,
            "kind": kind.value,
            "pipeline_version": request.pipeline_version,
            "model": best["model"],
            "quality_score": best["quality_score"],
            "source_sha256": source_sha,
        })
        return CutoutResult(
            status=CutoutStatus.SUCCESS.value,
            selected_path=dest,
            route=route,
            model=best["model"],
            model_revision=best.get("model_revision"),
            model_sha256=None,
            source_sha256=source_sha,
            quality_score=best["quality_score"],
            checks={},
            attempts=attempts,
            runtime_ms=runtime,
            cache_key=ck,
        )
