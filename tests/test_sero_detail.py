"""Node-Tests fuer frontend/sero-detail.js — Notes und Konfidenz, lokal."""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "tests" / "_run_sero_detail.js"
JS = ROOT / "frontend" / "sero-detail.js"


def test_sero_detail_logic():
    r = subprocess.run(
        ["node", str(RUNNER)],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    assert "SERO-DETAIL-OK" in r.stdout


def test_sero_detail_kein_courtyard_kein_angebot():
    txt = JS.read_text(encoding="utf-8")
    low = txt.lower()
    assert "courtyard" not in low
    assert "accept offer" not in low
    assert "accept top offer" not in low
    assert "highest offer" not in low
    assert "cancel listing" not in low
    assert "priceCardModel" in txt
    assert "MIN_COMPS_FOR_PRICE" in txt
    raw = JS.read_bytes()[:24]
    assert raw.startswith(b"/* SERO"), raw[:24]
