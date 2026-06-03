"""Concurrency regression: AgentOrchestrator registry under the threadpool.

FastAPI runs sync handlers in a threadpool, so AgentOrchestrator methods run
concurrently. Two iterate-vs-mutate races existed:

  * find_capable_agents iterates self._capabilities while register_agent /
    unregister_agent mutate its size, and
  * summary / read_model iterate self._plans while create_plan inserts.

Either raised RuntimeError("dictionary changed size during iteration") -- a
spurious 500 on a hot read path. A single lock now guards both dicts: every
iterate site snapshots under the lock and computes on the local copy outside
it. These tests reproduce the crash (they fail pre-fix) and assert the methods
still behave correctly single-threaded.
"""
from __future__ import annotations

import sys
import threading

import pytest

from mcoi_runtime.core.agent_orchestration import AgentOrchestrator


def _clock() -> str:
    return "2026-01-01T00:00:00Z"


@pytest.fixture(autouse=True)
def _force_thread_switches():
    # Amplify thread switching so the iterate-vs-mutate race surfaces reliably.
    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        yield
    finally:
        sys.setswitchinterval(previous)


def test_register_unregister_vs_find_capable_agents_has_no_crash():
    # find_capable_agents iterates self._capabilities; concurrent
    # register_agent / unregister_agent resize it. Pre-fix this raised
    # RuntimeError("dictionary changed size during iteration").
    orch = AgentOrchestrator(clock=_clock)
    errors: list[str] = []
    guard = threading.Lock()
    stop = threading.Event()

    def churn(worker: int) -> None:
        try:
            for i in range(4000):
                agent_id = f"agent-{worker}-{i % 32}"
                orch.register_agent(agent_id, ("llm", "search"))
                orch.unregister_agent(agent_id)
        except BaseException as exc:  # noqa: BLE001 -- the test is the assertion
            with guard:
                errors.append(repr(exc))
        finally:
            stop.set()

    def discover() -> None:
        try:
            while not stop.is_set():
                orch.find_capable_agents(("llm",))
        except BaseException as exc:  # noqa: BLE001 -- the test is the assertion
            with guard:
                errors.append(repr(exc))

    threads = [threading.Thread(target=churn, args=(w,)) for w in range(6)]
    threads += [threading.Thread(target=discover) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == [], f"concurrent registry access raised: {errors[:1]}"


def test_create_plan_vs_summary_has_no_crash():
    # summary iterates self._plans.values() many times; concurrent create_plan
    # inserts. Pre-fix this raised "dictionary changed size during iteration".
    orch = AgentOrchestrator(clock=_clock)
    orch.register_agent("initiator", ("llm",))
    errors: list[str] = []
    guard = threading.Lock()
    stop = threading.Event()

    def creator(worker: int) -> None:
        try:
            for i in range(1500):
                orch.create_plan("initiator", f"goal-{worker}-{i}")
        except BaseException as exc:  # noqa: BLE001 -- the test is the assertion
            with guard:
                errors.append(repr(exc))
        finally:
            stop.set()

    def reader() -> None:
        try:
            while not stop.is_set():
                orch.summary()
                orch.read_model()
        except BaseException as exc:  # noqa: BLE001 -- the test is the assertion
            with guard:
                errors.append(repr(exc))

    threads = [threading.Thread(target=creator, args=(w,)) for w in range(4)]
    threads += [threading.Thread(target=reader) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == [], f"concurrent plan access raised: {errors[:1]}"


def test_single_threaded_registry_behaviour_unchanged():
    orch = AgentOrchestrator(clock=_clock)
    orch.register_agent("a", ("llm", "search"))
    orch.register_agent("b", ("llm", "code"))
    assert orch.agent_count == 2
    assert sorted(orch.find_capable_agents(("llm",))) == ["a", "b"]
    assert orch.find_capable_agents(("search",)) == ["a"]
    orch.unregister_agent("a")
    assert orch.agent_count == 1
    assert orch.find_capable_agents(("search",)) == []

    plan = orch.create_plan("b", "ship it")
    summary = orch.summary()
    assert summary["total_plans"] == 1
    assert summary["active_plans"] == 1
    assert orch.get_plan(plan.plan_id) is plan
