#!/usr/bin/env python3
"""F7 — isolierter Mikro-Lastcheck (kein Kapazitätsclaim).

Misst nur: wie lange brauchen N parallele Store.kv_get/kv_set auf Temp-SQLite.
Kein HTTP, kein eBay, keine Live-DB. Zahlen sind Maschine-abhängig — keine
SLA-Aussage, kein „SERO hält X Nutzer".
"""
from __future__ import annotations

import statistics
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bot.drafts import Store  # noqa: E402


def main() -> int:
    n_threads = 8
    ops_each = 200
    with tempfile.TemporaryDirectory() as td:
        store = Store(Path(td) / "load.db")
        errors: list[str] = []
        times: list[float] = []

        def worker(i: int) -> None:
            t0 = time.perf_counter()
            try:
                for j in range(ops_each):
                    store.kv_set(f"load_{i}_{j % 20}", {"n": j})
                    store.kv_get(f"load_{i}_{j % 20}")
            except Exception as e:  # noqa: BLE001
                errors.append(str(e))
            times.append(time.perf_counter() - t0)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
        wall0 = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        wall = time.perf_counter() - wall0
        total_ops = n_threads * ops_each * 2
        print(f"threads={n_threads} ops_each={ops_each} total_kv_ops≈{total_ops}")
        print(f"wall_s={wall:.3f} thread_median_s={statistics.median(times):.3f}")
        print(f"approx_ops_per_s={total_ops / wall:.0f}")
        if errors:
            print("errors:", errors[:3])
            return 1
        print("OK — nur Mikro-Messung, kein Produktions-Claim")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
