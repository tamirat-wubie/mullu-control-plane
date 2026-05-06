"""Phase 211B — Anthropic streaming adapter tests."""

from types import SimpleNamespace

import pytest

from mcoi_runtime.adapters.anthropic_streaming import (
    AnthropicStreamingAdapter, StreamChunk,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


def FIXED_CLOCK():
    return "2026-03-26T12:00:00Z"


def _stub_adapter(**kwargs):
    return AnthropicStreamingAdapter(
        clock=FIXED_CLOCK,
        allow_stub_fallback=True,
        **kwargs,
    )


class TestAnthropicStreamingAdapter:
    def test_stub_streaming(self):
        adapter = _stub_adapter()
        assert adapter.is_available is False
        assert adapter.stub_fallback_enabled is True
        chunks = list(adapter.stream_completion("hello"))
        assert len(chunks) >= 2  # Content chunks + final
        assert chunks[-1].is_final is True

    def test_stub_content(self):
        adapter = _stub_adapter()
        chunks = list(adapter.stream_completion("test prompt"))
        content = "".join(c.text for c in chunks if not c.is_final)
        assert "stub" in content.lower()

    def test_stub_final_has_tokens(self):
        adapter = _stub_adapter()
        chunks = list(adapter.stream_completion("hello world"))
        final = chunks[-1]
        assert final.is_final is True
        assert final.input_tokens >= 0
        assert final.output_tokens >= 0

    def test_stream_to_events(self):
        adapter = _stub_adapter()
        events = list(adapter.stream_to_events("test", request_id="r1"))
        assert events[0].event_type == "meta"
        assert events[-1].event_type == "done"
        assert any(e.event_type == "token" for e in events)

    def test_events_meta_has_provider(self):
        adapter = _stub_adapter()
        events = list(adapter.stream_to_events("test"))
        meta = events[0]
        assert meta.data["provider"] == "stub"
        assert meta.data["streaming"] is True

    def test_events_done_has_cost(self):
        adapter = _stub_adapter()
        events = list(adapter.stream_to_events("test"))
        done = events[-1]
        assert done.data["governed"] is True
        assert "cost" in done.data

    def test_events_carry_budget_reservation_and_settlement(self):
        adapter = _stub_adapter()
        events = list(adapter.stream_to_events(
            "test",
            request_id="r-budget",
            tenant_id="tenant-alpha",
            budget_id="budget-stream",
            estimated_input_tokens=2,
            estimated_output_tokens=4,
        ))

        meta = events[0]
        done = events[-1]
        assert meta.data["budget_reservation"]["tenant_id"] == "tenant-alpha"
        assert meta.data["budget_reservation"]["budget_id"] == "budget-stream"
        assert meta.data["budget_reservation"]["proof_id"] == "stream-proof:r-budget:precharge"
        assert done.data["budget_settlement"]["proof_id"] == "stream-proof:r-budget:final-reconcile"

    def test_provider_native_output_delta_debits_stream_tokens(self):
        class NativeUsageAdapter(AnthropicStreamingAdapter):
            def stream_completion(self, *args, **kwargs):
                yield StreamChunk(text="alpha", index=1, output_tokens=2)
                yield StreamChunk(text=" beta", index=2, output_tokens=3)
                yield StreamChunk(text="", index=3, input_tokens=5, output_tokens=3, is_final=True)

        adapter = NativeUsageAdapter(clock=FIXED_CLOCK, allow_stub_fallback=True)
        events = list(adapter.stream_to_events(
            "test",
            request_id="r-native",
            estimated_input_tokens=1,
            estimated_output_tokens=3,
        ))
        tokens = [event for event in events if event.event_type == "token"]

        assert tokens[0].data["debit_output_tokens"] == 2
        assert tokens[0].data["emitted_output_tokens"] == 2
        assert tokens[1].data["debit_output_tokens"] == 1
        assert events[-1].data["budget_settlement"]["actual_output_tokens"] == 3

    def test_provider_native_output_delta_hard_cuts_before_overrun_text(self):
        class NativeUsageAdapter(AnthropicStreamingAdapter):
            def stream_completion(self, *args, **kwargs):
                yield StreamChunk(text="alpha", index=1, output_tokens=2)
                yield StreamChunk(text=" blocked", index=2, output_tokens=5)
                yield StreamChunk(text="", index=3, input_tokens=5, output_tokens=5, is_final=True)

        adapter = NativeUsageAdapter(clock=FIXED_CLOCK, allow_stub_fallback=True)
        events = list(adapter.stream_to_events(
            "test",
            request_id="r-cut",
            estimated_input_tokens=1,
            estimated_output_tokens=3,
        ))
        token_text = "".join(event.data["text"] for event in events if event.event_type == "token")
        cutoff = next(event for event in events if event.event_type == "cutoff")

        assert "blocked" not in token_text
        assert cutoff.data["semantic"] == "graceful"
        assert cutoff.data["emitted_output_tokens"] == 3
        assert events[-1].data["budget_settlement"]["cutoff_semantic"] == "graceful"

    def test_to_result(self):
        adapter = _stub_adapter()
        result = adapter.to_result("test prompt")
        assert result.content
        assert result.succeeded is True

    def test_to_result_provider(self):
        adapter = _stub_adapter()
        result = adapter.to_result("test")
        from mcoi_runtime.contracts.llm import LLMProvider
        assert result.provider == LLMProvider.STUB

    def test_without_available_client_fails_closed_without_stub_opt_in(self):
        adapter = AnthropicStreamingAdapter(clock=FIXED_CLOCK)

        with pytest.raises(RuntimeCoreInvariantError, match="explicit stub fallback"):
            list(adapter.stream_completion("test"))

    def test_with_fake_key_uses_explicit_stub_fallback_when_sdk_unavailable(self):
        adapter = AnthropicStreamingAdapter(api_key="fake-key", clock=FIXED_CLOCK)
        if adapter.is_available:
            pytest.skip("anthropic SDK is installed in this environment")

        with pytest.raises(RuntimeCoreInvariantError, match="explicit stub fallback"):
            list(adapter.stream_completion("test"))

        stub_adapter = _stub_adapter(api_key="fake-key")
        chunks = list(stub_adapter.stream_completion("test"))
        assert len(chunks) >= 1

    def test_custom_model(self):
        adapter = _stub_adapter(default_model="claude-haiku-4-5-20251001")
        events = list(adapter.stream_to_events("test"))
        meta = events[0]
        assert meta.data["model"] == "claude-haiku-4-5-20251001"

    def test_streaming_error_is_bounded(self):
        class CrashingMessages:
            def stream(self, **kwargs):
                raise RuntimeError("secret streaming failure")

        adapter = AnthropicStreamingAdapter(api_key="fake-key", clock=FIXED_CLOCK)
        adapter._available = True
        adapter._client = SimpleNamespace(messages=CrashingMessages())

        chunks = list(adapter.stream_completion("test"))

        assert len(chunks) == 1
        assert chunks[0].is_final is True
        assert chunks[0].text == "[streaming error (RuntimeError)]"
        assert "secret streaming failure" not in chunks[0].text
