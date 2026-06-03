"""Concurrency regression: GovernedToolRegistry tool registry under threadpool.

FastAPI runs sync handlers in a threadpool. list_tools, summary, and
capability_contract_coverage iterate self._tools while register / unregister
mutate its size, which raised RuntimeError("dictionary changed size during
iteration") -- a spurious 500 on a read path. The registry lock now guards the
tool mutations and the reads snapshot under it. This test reproduces the crash
(it fails pre-fix) and asserts the reads still behave correctly single-threaded.
"""
from __future__ import annotations

import sys
import threading

import pytest

from mcoi_runtime.core.governed_tool_use import (
    GovernedToolRegistry,
    ToolDefinition,
)


def _registry() -> GovernedToolRegistry:
    return GovernedToolRegistry(clock=lambda: "2026-01-01T00:00:00Z")


def _tool(name: str, *, enabled: bool = True) -> ToolDefinition:
    return ToolDefinition(name=name, description=f"tool {name}", enabled=enabled)


@pytest.fixture(autouse=True)
def _force_thread_switches():
    # Amplify thread switching so the iterate-vs-mutate race surfaces reliably.
    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        yield
    finally:
        sys.setswitchinterval(previous)


def test_register_unregister_vs_reads_has_no_crash():
    registry = _registry()
    errors: list[str] = []
    guard = threading.Lock()
    stop = threading.Event()

    def churn(worker: int) -> None:
        try:
            for i in range(4000):
                name = f"tool-{worker}-{i % 32}"
                registry.register(_tool(name))
                registry.unregister(name)
        except BaseException as exc:  # noqa: BLE001 -- the test is the assertion
            with guard:
                errors.append(repr(exc))
        finally:
            stop.set()

    def reader() -> None:
        try:
            while not stop.is_set():
                registry.list_tools()
                registry.summary()
                registry.capability_contract_coverage()
        except BaseException as exc:  # noqa: BLE001 -- the test is the assertion
            with guard:
                errors.append(repr(exc))

    threads = [threading.Thread(target=churn, args=(w,)) for w in range(5)]
    threads += [threading.Thread(target=reader) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == [], f"concurrent tool registry access raised: {errors[:1]}"


def test_single_threaded_tool_reads_unchanged():
    registry = _registry()
    registry.register(_tool("alpha"))
    registry.register(_tool("beta", enabled=False))
    assert registry.tool_count == 2

    all_tools = registry.list_tools(enabled_only=False)
    assert sorted(t.name for t in all_tools) == ["alpha", "beta"]
    enabled_tools = registry.list_tools()
    assert [t.name for t in enabled_tools] == ["alpha"]

    summary = registry.summary()
    assert summary["registered_tools"] == 2
    assert summary["enabled_tools"] == 1

    assert registry.unregister("alpha") is True
    assert registry.unregister("alpha") is False
    assert registry.tool_count == 1
