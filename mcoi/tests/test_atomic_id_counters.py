"""AtomicCounter + thread-safe id minting across the in-memory managers.

FastAPI runs sync handlers in a threadpool. Managers that minted ids from a plain
``self._counter += 1; f"x-{self._counter}"`` could emit DUPLICATE ids under
concurrency (a read-modify-write race). They now mint via ``AtomicCounter.next()``
(agent_chain, agent_memory, agent_workflow, batch_pipeline, chat_workflow,
conversation_memory, tool_use, scheduler). AgentMemoryStore stands in for the
family end-to-end; the AtomicCounter unit tests pin the primitive itself.
"""

from __future__ import annotations

import threading

from mcoi_runtime.core.agent_memory import AgentMemoryStore
from mcoi_runtime.core.concurrency import AtomicCounter


def test_atomic_counter_unique_under_threads():
    counter = AtomicCounter()
    collected: list[int] = []
    guard = threading.Lock()

    def worker() -> None:
        local = [counter.next() for _ in range(1000)]
        with guard:
            collected.extend(local)

    threads = [threading.Thread(target=worker) for _ in range(16)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(collected) == 16000
    assert len(set(collected)) == 16000  # no lost increments -> no duplicates
    assert counter.value == 16000
    assert min(collected) == 1 and max(collected) == 16000


def test_atomic_counter_start_and_value():
    counter = AtomicCounter(start=10)
    assert counter.value == 10
    assert counter.next() == 11
    assert counter.value == 11


def test_agent_memory_concurrent_store_emits_unique_ids():
    store = AgentMemoryStore(clock=lambda: "2026-01-01T00:00:00Z")
    collected: list[str] = []
    guard = threading.Lock()

    def worker() -> None:
        local = [
            store.store(
                agent_id="a1", tenant_id="t1", category="note", content=f"c{i}"
            ).memory_id
            for i in range(100)
        ]
        with guard:
            collected.extend(local)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(collected) == 800
    assert len(set(collected)) == 800  # no duplicate mem-N ids under concurrency
