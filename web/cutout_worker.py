"""Eigenes Python für rembg — OOM tötet nicht uvicorn.

Aufruf: python -m web.cutout_worker <quelle> <ziel> [kind]
Exit 0 = Alpha geschrieben, sonst Fehler.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("OMP_NUM_THREADS", "1")


def _slim_onnx_session_options() -> None:
    """ONNX-Arena nicht den ganzen RAM fressen lassen (Contabo 18.08.)."""
    try:
        import onnxruntime as ort
        import rembg.session_factory as sf

        _orig = ort.SessionOptions

        def slim():
            s = _orig()
            s.intra_op_num_threads = 1
            s.inter_op_num_threads = 1
            s.enable_cpu_mem_arena = False
            s.enable_mem_pattern = False
            return s

        ort.SessionOptions = slim  # type: ignore[misc]
        sf.ort.SessionOptions = slim  # type: ignore[misc]
    except Exception:
        pass


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: python -m web.cutout_worker SRC DST [kind]", file=sys.stderr)
        return 2
    src, dst = sys.argv[1], sys.argv[2]
    kind = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] else None
    _slim_onnx_session_options()
    from web.cardscan import _cutout
    ok = _cutout(src, dst, kind)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
