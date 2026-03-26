"""Phase 201C — Async LLM Completion Bridge.

Purpose: Asyncio-native LLM completion for non-blocking server operations.
    Wraps the synchronous LLMIntegrationBridge with async interfaces
    while maintaining full governance (budget, ledger).
Governance scope: async LLM wiring only.
Dependencies: llm_integration, asyncio.
Invariants:
  - Async calls maintain same governance as sync (budget + ledger).
  - Concurrent calls are independently budgeted.
  - Timeout enforcement prevents runaway LLM calls.
  - Results are identical to sync bridge for same inputs.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, AsyncIterator, Callable

from mcoi_runtime.contracts.llm import LLMResult
from mcoi_runtime.core.llm_integration import LLMIntegrationBridge
from mcoi_runtime.app.streaming import StreamBuffer, StreamEvent, StreamingAdapter


@dataclass(frozen=True, slots=True)
class AsyncLLMConfig:
    """Configuration for async LLM operations."""

    timeout_seconds: float = 30.0
    max_concurrent: int = 10
    retry_on_timeout: bool = False


class AsyncLLMBridge:
    """Async wrapper around the governed LLM integration bridge.

    Runs sync LLM calls in a thread pool executor to avoid blocking
    the asyncio event loop. Maintains all governance constraints.
    """

    def __init__(
        self,
        *,
        bridge: LLMIntegrationBridge,
        streaming_adapter: StreamingAdapter | None = None,
        config: AsyncLLMConfig | None = None,
    ) -> None:
        self._bridge = bridge
        self._streaming = streaming_adapter
        self._config = config or AsyncLLMConfig()
        self._semaphore = asyncio.Semaphore(self._config.max_concurrent)
        self._pending_count = 0
        self._completed_count = 0
        self._timeout_count = 0

    async def complete(
        self,
        prompt: str,
        *,
        model_name: str = "claude-sonnet-4-20250514",
        backend_name: str = "default",
        system: str = "",
        max_tokens: int = 1024,
        temperature: float = 0.0,
        tenant_id: str = "",
        budget_id: str = "",
        timeout: float | None = None,
    ) -> LLMResult:
        """Async governed LLM completion.

        Runs the sync bridge in a thread pool to avoid blocking.
        Respects concurrency limits and timeout.
        """
        effective_timeout = timeout or self._config.timeout_seconds

        async with self._semaphore:
            self._pending_count += 1
            try:
                loop = asyncio.get_running_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: self._bridge.complete(
                            prompt,
                            model_name=model_name,
                            backend_name=backend_name,
                            system=system,
                            max_tokens=max_tokens,
                            temperature=temperature,
                            tenant_id=tenant_id,
                            budget_id=budget_id,
                        ),
                    ),
                    timeout=effective_timeout,
                )
                self._completed_count += 1
                return result
            except asyncio.TimeoutError:
                self._timeout_count += 1
                from mcoi_runtime.contracts.llm import LLMProvider
                return LLMResult(
                    content="",
                    input_tokens=0,
                    output_tokens=0,
                    cost=0.0,
                    model_name=model_name,
                    provider=LLMProvider.STUB,
                    finished=False,
                    error=f"timeout after {effective_timeout}s",
                )
            finally:
                self._pending_count -= 1

    async def stream(
        self,
        prompt: str,
        *,
        model_name: str = "claude-sonnet-4-20250514",
        backend_name: str = "default",
        system: str = "",
        max_tokens: int = 1024,
        temperature: float = 0.0,
        tenant_id: str = "",
        budget_id: str = "",
        request_id: str = "",
    ) -> AsyncIterator[StreamEvent]:
        """Async streaming LLM completion.

        Yields StreamEvents progressively.
        """
        result = await self.complete(
            prompt,
            model_name=model_name,
            backend_name=backend_name,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            tenant_id=tenant_id,
            budget_id=budget_id,
        )

        if self._streaming is None:
            self._streaming = StreamingAdapter(clock=self._bridge._clock)

        for event in self._streaming.stream_result(result, request_id=request_id):
            yield event

    async def batch_complete(
        self,
        prompts: list[str],
        *,
        model_name: str = "claude-sonnet-4-20250514",
        backend_name: str = "default",
        system: str = "",
        max_tokens: int = 1024,
        tenant_id: str = "",
        budget_id: str = "",
    ) -> list[LLMResult]:
        """Run multiple completions concurrently.

        Respects semaphore — at most max_concurrent running at once.
        """
        tasks = [
            self.complete(
                prompt,
                model_name=model_name,
                backend_name=backend_name,
                system=system,
                max_tokens=max_tokens,
                tenant_id=tenant_id,
                budget_id=budget_id,
            )
            for prompt in prompts
        ]
        return list(await asyncio.gather(*tasks))

    @property
    def pending_count(self) -> int:
        return self._pending_count

    @property
    def completed_count(self) -> int:
        return self._completed_count

    @property
    def timeout_count(self) -> int:
        return self._timeout_count

    def status(self) -> dict[str, Any]:
        return {
            "pending": self._pending_count,
            "completed": self._completed_count,
            "timeouts": self._timeout_count,
            "max_concurrent": self._config.max_concurrent,
            "timeout_seconds": self._config.timeout_seconds,
        }
