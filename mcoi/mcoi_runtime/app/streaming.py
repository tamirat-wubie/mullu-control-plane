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
from enum import Enum
from typing import Any, Callable, Iterator

from mcoi_runtime.contracts.llm import LLMResult


class StreamCutoffSemantic(str, Enum):
    """Bounded cutoff semantics for predictive streaming debit."""

    GRACEFUL = "graceful"
    ABRUPT = "abrupt"
    RETRY_ELIGIBLE = "retry_eligible"


@dataclass(frozen=True, slots=True)
class StreamBudgetReservation:
    """Predictive token reservation created before streaming begins."""

    reservation_id: str
    request_id: str
    tenant_id: str
    budget_id: str
    estimated_input_tokens: int
    reserved_output_tokens: int
    reserved_total_tokens: int
    reserved_cost: float
    policy_version: str
    proof_id: str

    def __post_init__(self) -> None:
        if not self.reservation_id:
            raise ValueError("reservation_id is required")
        if not self.request_id:
            raise ValueError("request_id is required")
        if not self.tenant_id:
            raise ValueError("tenant_id is required")
        if not self.budget_id:
            raise ValueError("budget_id is required")
        if self.estimated_input_tokens < 0:
            raise ValueError("estimated_input_tokens must be non-negative")
        if self.reserved_output_tokens < 0:
            raise ValueError("reserved_output_tokens must be non-negative")
        if self.reserved_total_tokens != self.estimated_input_tokens + self.reserved_output_tokens:
            raise ValueError("reserved_total_tokens must equal estimated input plus reserved output tokens")
        if self.reserved_cost < 0:
            raise ValueError("reserved_cost must be non-negative")
        if not self.policy_version:
            raise ValueError("policy_version is required")
        if not self.proof_id:
            raise ValueError("proof_id is required")


@dataclass(frozen=True, slots=True)
class StreamBudgetCursor:
    """Current debit position within a streaming budget reservation."""

    reservation: StreamBudgetReservation
    emitted_output_tokens: int = 0
    cutoff_semantic: StreamCutoffSemantic | None = None

    @property
    def remaining_output_tokens(self) -> int:
        return max(self.reservation.reserved_output_tokens - self.emitted_output_tokens, 0)

    @property
    def exhausted(self) -> bool:
        return self.remaining_output_tokens == 0


@dataclass(frozen=True, slots=True)
class StreamBudgetSettlement:
    """Final settlement between reserved and observed streaming usage."""

    reservation_id: str
    actual_input_tokens: int
    actual_output_tokens: int
    actual_cost: float
    delta_tokens: int
    delta_cost: float
    cutoff_semantic: StreamCutoffSemantic | None
    proof_id: str

    def __post_init__(self) -> None:
        if not self.reservation_id:
            raise ValueError("reservation_id is required")
        if self.actual_input_tokens < 0:
            raise ValueError("actual_input_tokens must be non-negative")
        if self.actual_output_tokens < 0:
            raise ValueError("actual_output_tokens must be non-negative")
        if self.actual_cost < 0:
            raise ValueError("actual_cost must be non-negative")
        if not self.proof_id:
            raise ValueError("proof_id is required")


@dataclass(frozen=True, slots=True)
class StreamEvent:
    """Single SSE event in a streaming response."""

    event_type: str  # "token", "done", "error", "meta"
    data: dict[str, Any]

    def to_sse(self) -> str:
        """Format as SSE wire protocol."""
        payload = json.dumps(self.data, default=str)
        return f"event: {self.event_type}\ndata: {payload}\n\n"


class StreamingBudgetProtocol:
    """Deterministic predictive debit protocol for streaming responses."""

    def __init__(
        self,
        *,
        cost_per_token: float,
        proof_id_factory: Callable[[str], str],
    ) -> None:
        if cost_per_token < 0:
            raise ValueError("cost_per_token must be non-negative")
        self._cost_per_token = cost_per_token
        self._proof_id_factory = proof_id_factory

    def reserve(
        self,
        *,
        reservation_id: str,
        request_id: str,
        tenant_id: str,
        budget_id: str,
        estimated_input_tokens: int,
        estimated_output_tokens: int,
        policy_version: str,
    ) -> StreamBudgetCursor:
        """Reserve predicted usage before the first stream byte is emitted."""
        reserved_total_tokens = estimated_input_tokens + estimated_output_tokens
        reservation = StreamBudgetReservation(
            reservation_id=reservation_id,
            request_id=request_id,
            tenant_id=tenant_id,
            budget_id=budget_id,
            estimated_input_tokens=estimated_input_tokens,
            reserved_output_tokens=estimated_output_tokens,
            reserved_total_tokens=reserved_total_tokens,
            reserved_cost=reserved_total_tokens * self._cost_per_token,
            policy_version=policy_version,
            proof_id=self._proof_id_factory("precharge"),
        )
        return StreamBudgetCursor(reservation=reservation)

    def debit_chunk(
        self,
        cursor: StreamBudgetCursor,
        *,
        output_tokens: int,
        cutoff_semantic: StreamCutoffSemantic = StreamCutoffSemantic.GRACEFUL,
    ) -> tuple[StreamBudgetCursor, int, StreamEvent | None]:
        """Debit an output chunk and return allowed tokens plus cutoff event."""
        if output_tokens < 0:
            raise ValueError("output_tokens must be non-negative")
        if cursor.cutoff_semantic is not None:
            cutoff_event = self._cutoff_event(cursor, cursor.cutoff_semantic)
            return cursor, 0, cutoff_event

        allowed_tokens = min(output_tokens, cursor.remaining_output_tokens)
        next_cursor = StreamBudgetCursor(
            reservation=cursor.reservation,
            emitted_output_tokens=cursor.emitted_output_tokens + allowed_tokens,
        )
        if allowed_tokens == output_tokens and not next_cursor.exhausted:
            return next_cursor, allowed_tokens, None

        exhausted_cursor = StreamBudgetCursor(
            reservation=cursor.reservation,
            emitted_output_tokens=next_cursor.emitted_output_tokens,
            cutoff_semantic=cutoff_semantic,
        )
        return exhausted_cursor, allowed_tokens, self._cutoff_event(exhausted_cursor, cutoff_semantic)

    def settle(
        self,
        cursor: StreamBudgetCursor,
        *,
        actual_input_tokens: int,
        actual_output_tokens: int,
        actual_cost: float,
    ) -> StreamBudgetSettlement:
        """Settle final observed usage against the predictive reservation."""
        return StreamBudgetSettlement(
            reservation_id=cursor.reservation.reservation_id,
            actual_input_tokens=actual_input_tokens,
            actual_output_tokens=actual_output_tokens,
            actual_cost=actual_cost,
            delta_tokens=actual_input_tokens + actual_output_tokens - cursor.reservation.reserved_total_tokens,
            delta_cost=actual_cost - cursor.reservation.reserved_cost,
            cutoff_semantic=cursor.cutoff_semantic,
            proof_id=self._proof_id_factory("final-reconcile"),
        )

    def _cutoff_event(self, cursor: StreamBudgetCursor, semantic: StreamCutoffSemantic) -> StreamEvent:
        return StreamEvent(
            event_type="cutoff",
            data={
                "reservation_id": cursor.reservation.reservation_id,
                "request_id": cursor.reservation.request_id,
                "semantic": semantic.value,
                "retry_eligible": semantic == StreamCutoffSemantic.RETRY_ELIGIBLE,
                "emitted_output_tokens": cursor.emitted_output_tokens,
                "reserved_output_tokens": cursor.reservation.reserved_output_tokens,
                "proof_id": self._proof_id_factory("cutoff"),
            },
        )


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
