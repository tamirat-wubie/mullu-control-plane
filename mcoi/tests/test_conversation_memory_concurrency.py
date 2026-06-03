"""Concurrency regression: ConversationStore under the threadpool.

list_conversations / summary iterate self._conversations while a concurrent
get_or_create inserts and delete pops -- which raised
"dictionary changed size during iteration", a spurious 500 on the hot path. A
lock now guards the iterate-snapshot and the size-mutating sections. This test
reproduces the crash (it fails pre-fix) and asserts the store still works
single-threaded.
"""

from __future__ import annotations

import sys
import threading

import pytest

from mcoi_runtime.core.conversation_memory import ConversationStore


@pytest.fixture(autouse=True)
def _force_thread_switches():
    # Amplify thread switching so the iterate-vs-mutate race surfaces reliably.
    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        yield
    finally:
        sys.setswitchinterval(previous)


def test_concurrent_iterate_and_mutate_has_no_dict_crash():
    # Each writer uses distinct keys so the dict keeps growing while readers
    # iterate -- the collision window for "changed size during iteration".
    store = ConversationStore(clock=lambda: "")
    errors: list[str] = []
    guard = threading.Lock()

    def writer(w: int) -> None:
        try:
            for i in range(2000):
                cid = f"w{w}-c{i}"
                store.get_or_create(cid, tenant_id=f"t{w}")
                # Pop a now-stale key to also exercise the size-shrink path.
                store.delete(f"w{w}-c{i - 1}")
        except BaseException as exc:  # noqa: BLE001 -- the test is the assertion
            with guard:
                errors.append(repr(exc))

    def reader(w: int) -> None:
        try:
            for _ in range(2000):
                store.list_conversations()
                store.summary()
        except BaseException as exc:  # noqa: BLE001 -- the test is the assertion
            with guard:
                errors.append(repr(exc))

    threads: list[threading.Thread] = []
    for w in range(4):
        threads.append(threading.Thread(target=writer, args=(w,)))
        threads.append(threading.Thread(target=reader, args=(w,)))
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # Pre-fix this raised RuntimeError("dictionary changed size during iteration").
    assert errors == [], f"concurrent ConversationStore access raised: {errors[:1]}"


def test_store_basic_operations_single_threaded():
    store = ConversationStore(clock=lambda: "")
    conv = store.get_or_create("c1", tenant_id="t1")
    conv.add_user("hello")
    # get_or_create is idempotent on an existing id.
    assert store.get_or_create("c1") is conv
    assert store.get("c1") is conv
    assert store.count == 1
    store.get_or_create("c2", tenant_id="t2")
    assert store.count == 2
    assert [c.conversation_id for c in store.list_conversations()] == ["c1", "c2"]
    assert [c.conversation_id for c in store.list_conversations(tenant_id="t1")] == ["c1"]
    assert store.summary() == {"conversations": 2, "total_messages": 1}
    assert store.delete("c1") is True
    assert store.delete("c1") is False
    assert store.count == 1
