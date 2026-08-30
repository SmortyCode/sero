"""Einfache Cutout-Job-Status-Hilfen (UI queued/running/…)."""
from __future__ import annotations

import time
import uuid
from typing import Any


def new_job_id() -> str:
    return uuid.uuid4().hex[:16]


def job_record(status: str, **extra: Any) -> dict[str, Any]:
    return {"status": status, "updated_at": time.time(), **extra}
