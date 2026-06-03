"""Concurrency regression: RequestDeduplicator.check under the threadpool.

check() runs on every request. It iterates self._seen (in _cleanup and the
eviction min()) while a concurrent check() inserts -- which raised
"dictionary changed size during iteration", a spurious 500 on the hot path. A
lock now guards the shared-state section. This test reproduces the crash (it
fails pre-fix) and asserts dedup still works single-threaded.
"""

from __future__ import annotations

import sys
import threading

import pytest

from mcoi_runtime.core.request_dedup import RequestDeduplicator


@pytest.fixture(autouse=True)
def _force_thread_switches():
    # Amplify thread switching so the iterate-vs-mutate race surfaces reliably.
    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        yield
    finally:
        sys.setswitchinterval(previous)


def test_check_concurrent_has_no_dict_mutation_crash():
    # max_entries low so every check past the cap does min(_seen) + del + insert
    # (iterate + size-mutate) -- the collision window.
    dedup = RequestDeduplicator(window_seconds=1e9, max_entries=50)
    errors: list[str] = []
    guard = threading.Lock()

    def worker(w: int) -> None:
        try:
            for i in range(3000):
                dedup.check({"w": w, "i": i, "pad": "xxxxx"}, tenant_id=f"t{w}")
        except BaseException as exc:  # noqa: BLE001 -- the test is the assertion
            with guard:
                errors.append(repr(exc))

    threads = [threading.Thread(target=worker, args=(w,)) for w in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # Pre-fix this raised RuntimeError("dictionary changed size during iteration").
    assert errors == [], f"concurrent check() raised: {errors[:1]}"


def test_dedup_still_detects_duplicates():
    dedup = RequestDeduplicator(window_seconds=1e9)
    first = dedup.check({"a": 1}, tenant_id="t")
    second = dedup.check({"a": 1}, tenant_id="t")
    assert first.is_duplicate is False
    assert second.is_duplicate is True
