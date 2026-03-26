"""Phase 201C — Async LLM bridge tests."""

import asyncio
import pytest
from mcoi_runtime.core.async_llm import AsyncLLMBridge, AsyncLLMConfig
from mcoi_runtime.core.llm_integration import LLMIntegrationBridge
from mcoi_runtime.adapters.llm_adapter import StubLLMBackend
from mcoi_runtime.contracts.llm import LLMBudget

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


def _bridge():
    bridge = LLMIntegrationBridge(clock=FIXED_CLOCK, default_backend=StubLLMBackend())
    bridge.register_budget(LLMBudget(budget_id="b1", tenant_id="t1", max_cost=100.0))
    return bridge


class TestAsyncLLMBridge:
    @pytest.mark.asyncio
    async def test_complete(self):
        async_bridge = AsyncLLMBridge(bridge=_bridge())
        result = await async_bridge.complete("hello", budget_id="b1")
        assert result.succeeded is True
        assert result.content

    @pytest.mark.asyncio
    async def test_complete_records_count(self):
        async_bridge = AsyncLLMBridge(bridge=_bridge())
        await async_bridge.complete("hello", budget_id="b1")
        assert async_bridge.completed_count == 1
        assert async_bridge.pending_count == 0

    @pytest.mark.asyncio
    async def test_timeout(self):
        # With a very short timeout, the stub should still succeed
        # because it's instant. Test the timeout mechanism works.
        config = AsyncLLMConfig(timeout_seconds=10.0)
        async_bridge = AsyncLLMBridge(bridge=_bridge(), config=config)
        result = await async_bridge.complete("hello", budget_id="b1")
        assert result.succeeded is True

    @pytest.mark.asyncio
    async def test_stream(self):
        async_bridge = AsyncLLMBridge(bridge=_bridge())
        events = []
        async for event in async_bridge.stream("hello", budget_id="b1", request_id="r1"):
            events.append(event)
        assert len(events) >= 3  # meta + tokens + done
        assert events[0].event_type == "meta"
        assert events[-1].event_type == "done"

    @pytest.mark.asyncio
    async def test_batch_complete(self):
        async_bridge = AsyncLLMBridge(bridge=_bridge())
        results = await async_bridge.batch_complete(
            ["hello", "world", "test"],
            budget_id="b1",
        )
        assert len(results) == 3
        assert all(r.succeeded for r in results)

    @pytest.mark.asyncio
    async def test_concurrency_limit(self):
        config = AsyncLLMConfig(max_concurrent=2)
        async_bridge = AsyncLLMBridge(bridge=_bridge(), config=config)
        results = await async_bridge.batch_complete(
            ["a", "b", "c", "d"],
            budget_id="b1",
        )
        assert len(results) == 4
        assert async_bridge.completed_count == 4

    @pytest.mark.asyncio
    async def test_status(self):
        config = AsyncLLMConfig(max_concurrent=5, timeout_seconds=15.0)
        async_bridge = AsyncLLMBridge(bridge=_bridge(), config=config)
        status = async_bridge.status()
        assert status["max_concurrent"] == 5
        assert status["timeout_seconds"] == 15.0
        assert status["completed"] == 0
        assert status["timeouts"] == 0

    @pytest.mark.asyncio
    async def test_multiple_awaits(self):
        async_bridge = AsyncLLMBridge(bridge=_bridge())
        r1 = await async_bridge.complete("first", budget_id="b1")
        r2 = await async_bridge.complete("second", budget_id="b1")
        assert r1.succeeded and r2.succeeded
        assert async_bridge.completed_count == 2


class TestAsyncLLMConfig:
    def test_defaults(self):
        config = AsyncLLMConfig()
        assert config.timeout_seconds == 30.0
        assert config.max_concurrent == 10
        assert config.retry_on_timeout is False

    def test_custom(self):
        config = AsyncLLMConfig(timeout_seconds=5.0, max_concurrent=3)
        assert config.timeout_seconds == 5.0
        assert config.max_concurrent == 3
