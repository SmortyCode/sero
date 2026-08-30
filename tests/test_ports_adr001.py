"""ADR-001 F1 — Ports importierbar; keine Live-Umschaltung."""
from __future__ import annotations

from pathlib import Path

from web.ports import EbayPublishPort, FakeEbay, PhotoPort, QueuePort, StorePort


def test_ports_protokolle_importierbar():
    assert StorePort
    assert PhotoPort
    assert QueuePort
    assert EbayPublishPort
    fake = FakeEbay()
    assert fake.publish_calls == 0


def test_kein_postgres_s3_worker_in_produktion():
    """F2–F5: Big-Bang nicht eingezogen (ADR-001)."""
    root = Path(__file__).resolve().parent.parent
    cfg = (root / "bot" / "config.py").read_text(encoding="utf-8")
    assert "postgresql://" not in cfg.lower()
    env_ex = (root / ".env.production.example").read_text(encoding="utf-8")
    assert "SERO_STORE_BACKEND=sqlite" in env_ex
    assert "ADR-001" in env_ex
    assert "NICHT aktiv" in env_ex
