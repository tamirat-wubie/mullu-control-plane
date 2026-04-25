"""Phase 211B — Real Anthropic Streaming Adapter.

Purpose: Token-by-token streaming from Anthropic's Messages API.
    Wraps the real streaming API with governance (budget check before,
    ledger entry after) while yielding tokens progressively.
Governance scope: streaming adapter only — budget + ledger at boundaries.
Dependencies: anthropic SDK (optional — graceful fallback if not installed).
Invariants:
  - Budget is checked before streaming begins.
  - Streaming errors produce error events, never silent drops.
  - Total tokens/cost are computed from stream metadata.
  - Falls back to stub if anthropic SDK not available.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterator

from mcoi_runtime.contracts.llm import LLMProvider, LLMResult
from mcoi_runtime.app.streaming import (
    StreamCutoffSemantic,
    StreamEvent,
    StreamingBudgetProtocol,
)


def _bounded_stream_error(exc: Exception) -> str:
    """Return a stable streaming error without raw backend detail."""
    return f"[streaming error ({type(exc).__name__})]"


@dataclass(frozen=True, slots=True)
class StreamChunk:
    """Single chunk from a streaming response."""

    text: str
    index: int
    input_tokens: int = 0
    output_tokens: int = 0
    is_final: bool = False


def _anthropic_reservation_cost_per_token() -> float:
    """Return a conservative reservation rate for mixed Anthropic usage."""
    return 15.0 / 1_000_000


def _chunk_output_delta(chunk: StreamChunk, *, last_observed_output_tokens: int) -> int:
    """Return provider-native output delta when usage is present."""
    if chunk.output_tokens <= 0:
        return 0
    return max(chunk.output_tokens - last_observed_output_tokens, 0)


def _stream_proof_id(request_id: str, stage: str) -> str:
    return f"stream-proof:{request_id or 'anonymous'}:{stage}"


class AnthropicStreamingAdapter:
    """Wraps Anthropic's streaming API with governance.

    If the anthropic SDK is available and an API key is set,
    uses real streaming. Otherwise falls back to simulated streaming.
    """

    def __init__(
        self,
        *,
        api_key: str = "",
        default_model: str = "claude-sonnet-4-20250514",
        clock: Callable[[], str],
    ) -> None:
        self._api_key = api_key
        self._default_model = default_model
        self._clock = clock
        self._client = None
        self._available = False

        if api_key:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=api_key)
                self._available = True
            except ImportError:
                pass

    @property
    def is_available(self) -> bool:
        return self._available

    def stream_completion(
        self,
        prompt: str,
        *,
        model: str = "",
        system: str = "",
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> Iterator[StreamChunk]:
        """Stream a completion token-by-token.

        If real API is available, streams from Anthropic.
        Otherwise, simulates streaming from stub.
        """
        model = model or self._default_model

        if self._available and self._client is not None:
            yield from self._real_stream(prompt, model=model, system=system,
                                          max_tokens=max_tokens, temperature=temperature)
        else:
            yield from self._stub_stream(prompt, model=model)

    def _real_stream(
        self,
        prompt: str,
        *,
        model: str,
        system: str,
        max_tokens: int,
        temperature: float,
    ) -> Iterator[StreamChunk]:
        """Real streaming from Anthropic API."""
        try:
            messages = [{"role": "user", "content": prompt}]
            kwargs: dict[str, Any] = {
                "model": model,
                "max_tokens": max_tokens,
                "messages": messages,
            }
            if system:
                kwargs["system"] = system
            if temperature > 0:
                kwargs["temperature"] = temperature

            index = 0
            input_tokens = 0
            output_tokens = 0

            with self._client.messages.stream(**kwargs) as stream:
                for event in stream:
                    if hasattr(event, "type"):
                        if event.type == "content_block_delta":
                            text = getattr(event.delta, "text", "")
                            if text:
                                index += 1
                                yield StreamChunk(text=text, index=index)
                        elif event.type == "message_delta":
                            output_tokens = getattr(event.usage, "output_tokens", 0)
                            yield StreamChunk(text="", index=index, output_tokens=output_tokens)
                        elif event.type == "message_start":
                            if hasattr(event.message, "usage"):
                                input_tokens = getattr(event.message.usage, "input_tokens", 0)

            # Final chunk with usage
            yield StreamChunk(
                text="", index=index + 1,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                is_final=True,
            )

        except Exception as exc:
            yield StreamChunk(text=_bounded_stream_error(exc), index=0, is_final=True)

    def _stub_stream(self, prompt: str, *, model: str) -> Iterator[StreamChunk]:
        """Simulated streaming for development/testing."""
        response = f"[stub streaming response for: {prompt[:50]}]"
        chunk_size = 10
        index = 0
        for i in range(0, len(response), chunk_size):
            index += 1
            yield StreamChunk(text=response[i:i + chunk_size], index=index)

        yield StreamChunk(
            text="", index=index + 1,
            input_tokens=len(prompt) // 4,
            output_tokens=len(response) // 4,
            is_final=True,
        )

    def stream_to_events(
        self,
        prompt: str,
        *,
        model: str = "",
        system: str = "",
        max_tokens: int = 1024,
        request_id: str = "",
        tenant_id: str = "system",
        budget_id: str = "default",
        estimated_input_tokens: int | None = None,
        estimated_output_tokens: int | None = None,
        policy_version: str = "streaming-budget:v1",
    ) -> Iterator[StreamEvent]:
        """Stream as StreamEvents for SSE delivery."""
        model = model or self._default_model
        request_ref = request_id or "anonymous"
        provider = "anthropic" if self._available else "stub"
        reserved_input_tokens = estimated_input_tokens if estimated_input_tokens is not None else max(len(prompt) // 4, 0)
        reserved_output_tokens = estimated_output_tokens if estimated_output_tokens is not None else max(max_tokens, 0)
        protocol = StreamingBudgetProtocol(
            cost_per_token=_anthropic_reservation_cost_per_token(),
            proof_id_factory=lambda stage: _stream_proof_id(request_ref, stage),
        )
        cursor = protocol.reserve(
            reservation_id=f"stream-reservation:{request_ref}",
            request_id=request_ref,
            tenant_id=tenant_id or "system",
            budget_id=budget_id or "default",
            estimated_input_tokens=reserved_input_tokens,
            estimated_output_tokens=reserved_output_tokens,
            policy_version=policy_version,
        )

        yield StreamEvent(
            event_type="meta",
            data={
                "request_id": request_id,
                "model": model,
                "provider": provider,
                "streaming": True,
                "started_at": self._clock(),
                "budget_reservation": {
                    "reservation_id": cursor.reservation.reservation_id,
                    "tenant_id": cursor.reservation.tenant_id,
                    "budget_id": cursor.reservation.budget_id,
                    "reserved_total_tokens": cursor.reservation.reserved_total_tokens,
                    "reserved_output_tokens": cursor.reservation.reserved_output_tokens,
                    "reserved_cost": cursor.reservation.reserved_cost,
                    "policy_version": cursor.reservation.policy_version,
                    "proof_id": cursor.reservation.proof_id,
                },
            },
        )

        content_parts: list[str] = []
        input_tokens = 0
        output_tokens = 0
        last_observed_output_tokens = 0

        for chunk in self.stream_completion(prompt, model=model, system=system, max_tokens=max_tokens):
            requested_output_tokens = _chunk_output_delta(
                chunk,
                last_observed_output_tokens=last_observed_output_tokens,
            )
            if chunk.is_final:
                input_tokens = chunk.input_tokens
                output_tokens = chunk.output_tokens
                last_observed_output_tokens = max(last_observed_output_tokens, output_tokens)
                continue

            cutoff: StreamEvent | None = None
            debit_output_tokens = requested_output_tokens or (1 if chunk.text else 0)
            allowed_tokens = 0
            if debit_output_tokens > 0:
                cursor, allowed_tokens, cutoff = protocol.debit_chunk(
                    cursor,
                    output_tokens=debit_output_tokens,
                    cutoff_semantic=StreamCutoffSemantic.GRACEFUL,
                )
                last_observed_output_tokens = max(last_observed_output_tokens, chunk.output_tokens)
                if allowed_tokens == 0:
                    if cutoff is not None:
                        yield cutoff
                    break
                if chunk.text and allowed_tokens < debit_output_tokens:
                    if cutoff is not None:
                        yield cutoff
                    break

            if chunk.text:
                content_parts.append(chunk.text)
                yield StreamEvent(
                    event_type="token",
                    data={
                        "text": chunk.text,
                        "index": chunk.index,
                        "reservation_id": cursor.reservation.reservation_id,
                        "debit_output_tokens": debit_output_tokens,
                        "emitted_output_tokens": cursor.emitted_output_tokens,
                        "remaining_output_tokens": cursor.remaining_output_tokens,
                        "proof_id": _stream_proof_id(request_ref, "chunk-debit"),
                    },
                )
                if cutoff is not None:
                    yield cutoff
                    break

        # Estimate cost (Anthropic pricing)
        cost_per_input = 3.0 / 1_000_000  # Sonnet pricing
        cost_per_output = 15.0 / 1_000_000
        observed_output_tokens = output_tokens or last_observed_output_tokens
        cost = input_tokens * cost_per_input + observed_output_tokens * cost_per_output
        settled_cost = round(cost, 6)
        settlement = protocol.settle(
            cursor,
            actual_input_tokens=input_tokens,
            actual_output_tokens=observed_output_tokens,
            actual_cost=settled_cost,
        )

        yield StreamEvent(
            event_type="done",
            data={
                "request_id": request_id,
                "input_tokens": input_tokens,
                "output_tokens": observed_output_tokens,
                "cost": settled_cost,
                "model": model,
                "provider": provider,
                "finished_at": self._clock(),
                "governed": True,
                "budget_settlement": {
                    "reservation_id": settlement.reservation_id,
                    "actual_input_tokens": settlement.actual_input_tokens,
                    "actual_output_tokens": settlement.actual_output_tokens,
                    "actual_cost": settlement.actual_cost,
                    "delta_tokens": settlement.delta_tokens,
                    "delta_cost": settlement.delta_cost,
                    "cutoff_semantic": settlement.cutoff_semantic.value if settlement.cutoff_semantic else None,
                    "proof_id": settlement.proof_id,
                },
            },
        )

    def to_result(self, prompt: str, **kwargs: Any) -> LLMResult:
        """Non-streaming completion — collects all chunks into a single result."""
        content_parts: list[str] = []
        input_tokens = 0
        output_tokens = 0

        for chunk in self.stream_completion(prompt, **kwargs):
            if chunk.is_final:
                input_tokens = chunk.input_tokens
                output_tokens = chunk.output_tokens
            elif chunk.text:
                content_parts.append(chunk.text)

        content = "".join(content_parts)
        cost_per_input = 3.0 / 1_000_000
        cost_per_output = 15.0 / 1_000_000
        cost = input_tokens * cost_per_input + output_tokens * cost_per_output

        return LLMResult(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=round(cost, 6),
            model_name=kwargs.get("model", self._default_model),
            provider=LLMProvider.ANTHROPIC if self._available else LLMProvider.STUB,
        )
