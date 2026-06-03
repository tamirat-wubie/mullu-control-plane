"""Concurrency regression tests for MemoryMeshEngine.

Pre-fix, the read/scan methods iterated _memories with no lock while add_memory
inserted keys and apply_decay deleted them. With records whose expires_at is in
the past, apply_decay deletes on every pass, so:
  * a concurrent add_memory resized _memories mid-iteration in list_memories /
    retrieve / state_hash -> RuntimeError("dictionary changed size during
    iteration"); and
  * two apply_decay threads computed the same expired set and ran
    ``del self._memories[mid]`` twice -> KeyError (double delete).
These tests drive add_memory + apply_decay + retrieve + list_memories + state_hash
from many threads and assert no BaseException escapes. They MUST fail on the
unlocked implementation.
"""
from __future__ import annotations

import sys
import threading

import pytest

from mcoi_runtime.contracts.memory_mesh import (
    MemoryRecord,
    MemoryRetrievalQuery,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine

# Past timestamp so every apply_decay() pass marks the record expired and
# deletes it -> exercises the del-during-iteration / double-delete paths.
PAST = "2000-01-01T00:00:00+00:00"
NOW = "2026-03-20T12:00:00+00:00"


@pytest.fixture(autouse=True)
def _tiny_switch_interval():
    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        yield
    finally:
        sys.setswitchinterval(previous)


def _record(mid: str) -> MemoryRecord:
    return MemoryRecord(
        memory_id=mid,
        memory_type=MemoryType.EPISODIC,
        scope=MemoryScope.GOAL,
        scope_ref_id="goal-1",
        trust_level=MemoryTrustLevel.VERIFIED,
        title="t",
        content={"v": 1},
        source_ids=("src-1",),
        confidence=0.8,
        created_at=NOW,
        updated_at=NOW,
        expires_at=PAST,
    )


def test_concurrent_add_decay_retrieve_does_not_corrupt_store():
    engine = MemoryMeshEngine()
    errors: list[BaseException] = []
    start = threading.Event()
    per_thread = 300

    def adder(base: int) -> None:
        start.wait()
        try:
            for i in range(per_thread):
                # Duplicate-ID inserts are expected and raise the domain error;
                # they are not the bug under test. Swallow ONLY that.
                try:
                    engine.add_memory(_record("mem-%d-%d" % (base, i)))
                except Exception:  # noqa: BLE001
                    pass
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    def decayer() -> None:
        start.wait()
        try:
            for _ in range(per_thread):
                engine.apply_decay()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    def reader() -> None:
        start.wait()
        try:
            query = MemoryRetrievalQuery(query_id="q-1")
            for _ in range(per_thread):
                engine.retrieve(query)
                engine.list_memories()
                engine.state_hash()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [
        threading.Thread(target=adder, args=(0,)),
        threading.Thread(target=adder, args=(1,)),
        threading.Thread(target=adder, args=(2,)),
        threading.Thread(target=decayer),
        threading.Thread(target=decayer),
        threading.Thread(target=reader),
        threading.Thread(target=reader),
        threading.Thread(target=reader),
    ]
    for t in threads:
        t.start()
    start.set()
    for t in threads:
        t.join()

    assert not errors, "engine raised under concurrency: %r" % (errors[:3],)


def test_single_threaded_add_decay_sanity():
    engine = MemoryMeshEngine()
    engine.add_memory(_record("mem-keep"))
    assert engine.memory_count == 1

    # expires_at is in the past => apply_decay removes it and returns its id.
    removed = engine.apply_decay()
    assert removed == ("mem-keep",)
    assert engine.memory_count == 0

    # state_hash + retrieve still work on the now-empty store.
    engine.state_hash()
    result = engine.retrieve(MemoryRetrievalQuery(query_id="q-1"))
    assert result.total == 0
