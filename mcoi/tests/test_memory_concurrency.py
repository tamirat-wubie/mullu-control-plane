"""Concurrency regression: WorkingMemory + EpisodicMemory under the threadpool.

FastAPI runs sync handlers in a threadpool, and the Stage-C CognitiveLearner
(MULLU_COGNITIVE_LOOP_LEARN) plus the CLI cognitive loop both admit episodic
entries from outside the engine. Before the engine-level locks, thread-safety
on these dicts was provided ONLY by CognitiveLearner._lock for that one
consumer; any second consumer raced directly on the engine's _entries / _order.

Three iterate-vs-mutate races were latent on these engines:

  * EpisodicMemory.list_entries iterates self._order to look up entries in
    self._entries while a concurrent admit appends to _order and inserts into
    _entries -- on a future code path that iterates _entries directly (debug
    dump, persistence walker, async consumer) or under PEP 703 free-threaded
    CPython, could raise RuntimeError("dictionary changed size during
    iteration") or briefly observe an entry_id in _order whose MemoryEntry is
    not yet present in _entries.
  * WorkingMemory.list_entries iterates self._entries while a concurrent
    store / remove / clear mutates its size -- same "dictionary changed size
    during iteration" failure mode.
  * WorkingMemory capacity check (store) was a non-atomic check-then-write:
    by definition multiple stores can pass the len < max check before any
    runs the insert, overflowing past max_entries.

A single lock now guards each engine's mutations and snapshots every iteration
under that lock. On CPython 3.13 (current default) the GIL narrows these race
windows enough that they do not always surface on a smoke run -- the engine-
level lock is the canonical campaign pattern (mirrored from #1261/#1262/#1264)
that makes the safety guarantee robust against (a) future consumers iterating
the raw _entries dict, (b) PEP 703 free-threaded CPython, (c) multi-process
workers, and (d) any future engine method that lengthens the read path. These
tests stress the contention patterns and assert single-threaded behaviour is
unchanged.
"""
from __future__ import annotations

import sys
import threading

import pytest

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory import (
    EpisodicMemory,
    MemoryEntry,
    MemoryTier,
    WorkingMemory,
)


@pytest.fixture(autouse=True)
def _force_thread_switches():
    # Amplify thread switching so the iterate-vs-mutate race surfaces reliably.
    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        yield
    finally:
        sys.setswitchinterval(previous)


def _episodic_entry(entry_id: str) -> MemoryEntry:
    return MemoryEntry(
        entry_id=entry_id,
        tier=MemoryTier.EPISODIC,
        category="outcome",
        content={"capability_id": "llm.completion", "succeeded": True},
        source_ids=(entry_id,),
    )


def _working_entry(entry_id: str) -> MemoryEntry:
    return MemoryEntry(
        entry_id=entry_id,
        tier=MemoryTier.WORKING,
        category="session",
        content={"turn": entry_id},
    )


def test_episodic_admit_vs_list_entries_has_no_crash():
    # list_entries iterates self._order to index into self._entries;
    # concurrent admit appends to _order and inserts into _entries. Pre-fix
    # this raised RuntimeError("dictionary changed size during iteration")
    # or KeyError when _order referenced an entry_id not yet in _entries.
    episodic = EpisodicMemory()
    errors: list[str] = []
    guard = threading.Lock()
    stop = threading.Event()

    def admitter(worker: int) -> None:
        try:
            for i in range(2000):
                episodic.admit(_episodic_entry(f"e-{worker}-{i}"))
        except BaseException as exc:  # noqa: BLE001 -- the test is the assertion
            with guard:
                errors.append(repr(exc))
        finally:
            stop.set()

    def reader() -> None:
        try:
            while not stop.is_set():
                episodic.list_entries()
        except BaseException as exc:  # noqa: BLE001 -- the test is the assertion
            with guard:
                errors.append(repr(exc))

    threads = [threading.Thread(target=admitter, args=(w,)) for w in range(4)]
    threads += [threading.Thread(target=reader) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == [], f"concurrent episodic access raised: {errors[:1]}"


def test_episodic_admit_vs_get_has_no_crash():
    # get() reads self._entries.get(...); concurrent admit mutates self._entries.
    # Plain dict.get on a mutating dict is generally safe in CPython under the
    # GIL, but if any future change adds work inside the read path (e.g. an
    # iteration over _order) the lock keeps it safe.
    episodic = EpisodicMemory()
    errors: list[str] = []
    guard = threading.Lock()
    stop = threading.Event()

    def admitter(worker: int) -> None:
        try:
            for i in range(2000):
                episodic.admit(_episodic_entry(f"e-{worker}-{i}"))
        except BaseException as exc:  # noqa: BLE001 -- the test is the assertion
            with guard:
                errors.append(repr(exc))
        finally:
            stop.set()

    def reader(worker: int) -> None:
        try:
            while not stop.is_set():
                episodic.get(f"e-{worker}-0")
                _ = episodic.size
        except BaseException as exc:  # noqa: BLE001 -- the test is the assertion
            with guard:
                errors.append(repr(exc))

    threads = [threading.Thread(target=admitter, args=(w,)) for w in range(4)]
    threads += [threading.Thread(target=reader, args=(w,)) for w in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == [], f"concurrent episodic access raised: {errors[:1]}"


def test_working_memory_store_remove_vs_list_entries_has_no_crash():
    # list_entries iterates self._entries.values(); concurrent store / remove
    # mutate its size. Pre-fix this raised "dictionary changed size during
    # iteration" reliably under the amplified switch interval.
    working = WorkingMemory(max_entries=10_000)
    errors: list[str] = []
    guard = threading.Lock()
    stop = threading.Event()

    def churn(worker: int) -> None:
        try:
            for i in range(2000):
                entry_id = f"w-{worker}-{i % 64}"
                working.store(_working_entry(entry_id))
                if i % 3 == 0:
                    working.remove(entry_id)
        except BaseException as exc:  # noqa: BLE001 -- the test is the assertion
            with guard:
                errors.append(repr(exc))
        finally:
            stop.set()

    def reader() -> None:
        try:
            while not stop.is_set():
                working.list_entries()
                _ = working.size
        except BaseException as exc:  # noqa: BLE001 -- the test is the assertion
            with guard:
                errors.append(repr(exc))

    threads = [threading.Thread(target=churn, args=(w,)) for w in range(4)]
    threads += [threading.Thread(target=reader) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == [], f"concurrent working-memory access raised: {errors[:1]}"


def test_working_memory_capacity_check_then_write_is_atomic():
    # Pre-fix the capacity check was a non-atomic check-then-write: a Barrier
    # synchronises N threads at the critical instant, so all observe len < max
    # in lock-step and all proceed to insert, blowing past max_entries. With
    # the lock, the check and the insert run atomically so the ceiling holds.
    max_entries = 4
    n_threads = 16
    barrier = threading.Barrier(n_threads)
    working = WorkingMemory(max_entries=max_entries)
    errors: list[BaseException] = []
    guard = threading.Lock()

    def worker(thread_id: int) -> None:
        try:
            barrier.wait()
            working.store(_working_entry(f"cap-{thread_id}"))
        except RuntimeCoreInvariantError:
            # Capacity rejection is the desired outcome for over-the-limit
            # threads; the rejection means the gate held.
            pass
        except BaseException as exc:  # noqa: BLE001 -- the test is the assertion
            with guard:
                errors.append(exc)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == [], f"working memory raised: {errors[:1]}"
    # The exact bound must hold: never more than max_entries despite the
    # Barrier-synchronised stampede. Pre-lock this asserts ~n_threads > 4.
    assert working.size <= max_entries, f"capacity ceiling broken: size={working.size} > max={max_entries}"


def test_single_threaded_episodic_behaviour_unchanged():
    episodic = EpisodicMemory()
    a = episodic.admit(_episodic_entry("a"))
    b = episodic.admit(_episodic_entry("b"))
    assert episodic.size == 2
    assert episodic.get("a") is a
    assert episodic.get("b") is b
    assert episodic.get("missing") is None
    listed = episodic.list_entries()
    assert [e.entry_id for e in listed] == ["a", "b"]
    # Duplicate admission still rejected.
    with pytest.raises(Exception):
        episodic.admit(_episodic_entry("a"))


def test_single_threaded_working_behaviour_unchanged():
    working = WorkingMemory(max_entries=3)
    working.store(_working_entry("a"))
    working.store(_working_entry("b"))
    assert working.size == 2
    listed = working.list_entries()
    assert [e.entry_id for e in listed] == ["a", "b"]
    assert working.remove("a") is True
    assert working.remove("a") is False
    assert working.size == 1
    working.store(_working_entry("c"))
    working.store(_working_entry("d"))
    # Capacity exceeded.
    with pytest.raises(Exception):
        working.store(_working_entry("e"))
    cleared = working.clear()
    assert cleared == 3
    assert working.size == 0
