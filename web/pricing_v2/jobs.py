"""Persistente Preisjobs (KV)."""
from __future__ import annotations

import os
import time
import uuid
from typing import Any

from web.pricing_v2.types import JobStatus, QUERY_PLAN_VERSION


def pricing_v2_enabled(item_id: str | None = None) -> bool:
    from web.pipeline_flags import pricing_v2_enabled as _e
    return _e(item_id)


def pricing_v2_shadow(item_id: str | None = None) -> bool:
    from web.pipeline_flags import pricing_v2_shadow as _s
    return _s(item_id)


def new_job_id() -> str:
    return uuid.uuid4().hex[:16]


def _key(job_id: str) -> str:
    return f"price_job:{job_id}"


def create_job(store, *, item_id: str, account_id: int) -> dict[str, Any]:
    job_id = new_job_id()
    job = {
        "id": job_id,
        "item_id": item_id,
        "account_id": account_id,
        "status": JobStatus.QUEUED.value,
        "created_at": time.time(),
        "updated_at": time.time(),
        "query_plan_version": QUERY_PLAN_VERSION,
        "result": None,
        "last_error": None,
        "attempts": [],
    }
    store.kv_set(_key(job_id), job)
    store.kv_set(f"price_job_item:{item_id}", {"job_id": job_id, "ts": time.time()})
    return job


def get_job(store, job_id: str) -> dict[str, Any] | None:
    return store.kv_get(_key(job_id))


def update_job(store, job_id: str, **fields: Any) -> dict[str, Any] | None:
    job = get_job(store, job_id)
    if not job:
        return None
    job.update(fields)
    job["updated_at"] = time.time()
    store.kv_set(_key(job_id), job)
    return job


def set_status(store, job_id: str, status: JobStatus | str, **extra: Any) -> dict[str, Any] | None:
    st = status.value if isinstance(status, JobStatus) else status
    return update_job(store, job_id, status=st, **extra)
