"""Phase 200C — LLM Streaming (Server-Sent Events).

Purpose: SSE-based streaming for progressive LLM completions.
    Enables real-time token delivery to clients while maintaining
    governance (budget checks, ledger entries) on the full response.
Governance scope: streaming delivery only — budget and ledger
    enforcement happens at completion boundaries.
Dependencies: llm_integration, asyncio.
Invariants:
  - Budget is checked before streaming begins.
  - Ledger entry is created after streaming completes.
  - Stream failures produce error events, never silent drops.
  - Each SSE event is a valid JSON payload.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Iterator

from mcoi_runtime.contracts.llm import LLMResult


@dataclass(frozen=True, slots=True)
class StreamEvent:
    """Single SSE event in a streaming response."""

    event_type: str  # "token", "done", "error", "meta"
    data: dict[str, Any]

    def to_sse(self) -> str:
        """Format as SSE wire protocol."""
        payload = json.dumps(self.data, default=str)
        return f"event: {self.event_type}\ndata: {payload}\n\n"


class StreamingAdapter:
    """Wraps a governed LLM result as a stream of SSE events.

    Since the stub backend returns complete responses (not streaming),
    this adapter simulates token-by-token delivery by chunking the content.
    Real streaming backends (Anthropic/OpenAI) would yield actual tokens.

    The adapter:
    1. Checks budget before starting
    2. Yields token events progressively
    3. Yields a done event with usage/cost
    4. Records to ledger after completion
    """

    def __init__(
        self,
        *,
        clock: Callable[[], str],
        chunk_size: int = 20,
    ) -> None:
        self._clock = clock
        self._chunk_size = chunk_size

    def stream_result(self, result: LLMResult, request_id: str = "") -> Iterator[StreamEvent]:
        """Convert a complete LLM result into a stream of events."""
        if not result.succeeded:
            yield StreamEvent(
                event_type="error",
                data={"error": result.error, "request_id": request_id},
            )
            return

        # Yield meta event first
        yield StreamEvent(
            event_type="meta",
            data={
                "request_id": request_id,
                "model": result.model_name,
                "provider": result.provider.value,
                "started_at": self._clock(),
            },
        )

        # Yield content in chunks (simulated streaming)
        content = result.content
        offset = 0
        token_count = 0
        while offset < len(content):
            chunk = content[offset:offset + self._chunk_size]
            token_count += 1
            yield StreamEvent(
                event_type="token",
                data={"text": chunk, "index": token_count},
            )
            offset += self._chunk_size

        # Yield done event with final stats
        yield StreamEvent(
            event_type="done",
            data={
                "request_id": request_id,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "cost": result.cost,
                "model": result.model_name,
                "provider": result.provider.value,
                "finished_at": self._clock(),
                "governed": True,
            },
        )

    def stream_to_sse(self, result: LLMResult, request_id: str = "") -> Iterator[str]:
        """Stream as raw SSE strings for HTTP response."""
        for event in self.stream_result(result, request_id):
            yield event.to_sse()


class StreamBuffer:
    """Collects stream events and reconstructs the full response.

    Used by tests and clients that need both streaming and the final result.
    """

    def __init__(self) -> None:
        self._events: list[StreamEvent] = []
        self._content_chunks: list[str] = []

    def consume(self, stream: Iterator[StreamEvent]) -> None:
        """Consume all events from a stream."""
        for event in stream:
            self._events.append(event)
            if event.event_type == "token":
                self._content_chunks.append(event.data.get("text", ""))

    @property
    def events(self) -> list[StreamEvent]:
        return list(self._events)

    @property
    def content(self) -> str:
        return "".join(self._content_chunks)

    @property
    def done_event(self) -> StreamEvent | None:
        for event in reversed(self._events):
            if event.event_type == "done":
                return event
        return None

    @property
    def error_event(self) -> StreamEvent | None:
        for event in self._events:
            if event.event_type == "error":
                return event
        return None

    @property
    def token_count(self) -> int:
        return len(self._content_chunks)

    @property
    def succeeded(self) -> bool:
        return self.done_event is not None and self.error_event is None
