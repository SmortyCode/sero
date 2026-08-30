"""Node-gestützte Unit-Tests für frontend/sero-mobile.js."""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "tests" / "_run_sero_mobile.js"


def test_sero_mobile_core():
    r = subprocess.run(
        ["node", str(RUNNER)],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    assert "SERO-MOBILE-OK" in r.stdout
