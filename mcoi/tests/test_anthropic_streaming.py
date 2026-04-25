"""Phase 211B — Anthropic streaming adapter tests."""

from types import SimpleNamespace

from mcoi_runtime.adapters.anthropic_streaming import (
    AnthropicStreamingAdapter, StreamChunk,
)


def FIXED_CLOCK():
    return "2026-03-26T12:00:00Z"


class TestAnthropicStreamingAdapter:
    def test_stub_streaming(self):
        adapter = AnthropicStreamingAdapter(clock=FIXED_CLOCK)
        assert adapter.is_available is False
        chunks = list(adapter.stream_completion("hello"))
        assert len(chunks) >= 2  # Content chunks + final
        assert chunks[-1].is_final is True

    def test_stub_content(self):
        adapter = AnthropicStreamingAdapter(clock=FIXED_CLOCK)
        chunks = list(adapter.stream_completion("test prompt"))
        content = "".join(c.text for c in chunks if not c.is_final)
        assert "stub" in content.lower()

    def test_stub_final_has_tokens(self):
        adapter = AnthropicStreamingAdapter(clock=FIXED_CLOCK)
        chunks = list(adapter.stream_completion("hello world"))
        final = chunks[-1]
        assert final.is_final is True
        assert final.input_tokens >= 0
        assert final.output_tokens >= 0

    def test_stream_to_events(self):
        adapter = AnthropicStreamingAdapter(clock=FIXED_CLOCK)
        events = list(adapter.stream_to_events("test", request_id="r1"))
        assert events[0].event_type == "meta"
        assert events[-1].event_type == "done"
        assert any(e.event_type == "token" for e in events)

    def test_events_meta_has_provider(self):
        adapter = AnthropicStreamingAdapter(clock=FIXED_CLOCK)
        events = list(adapter.stream_to_events("test"))
        meta = events[0]
        assert meta.data["provider"] == "stub"
        assert meta.data["streaming"] is True

    def test_events_done_has_cost(self):
        adapter = AnthropicStreamingAdapter(clock=FIXED_CLOCK)
        events = list(adapter.stream_to_events("test"))
        done = events[-1]
        assert done.data["governed"] is True
        assert "cost" in done.data

    def test_events_carry_budget_reservation_and_settlement(self):
        adapter = AnthropicStreamingAdapter(clock=FIXED_CLOCK)
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

        adapter = NativeUsageAdapter(clock=FIXED_CLOCK)
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

        adapter = NativeUsageAdapter(clock=FIXED_CLOCK)
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
        adapter = AnthropicStreamingAdapter(clock=FIXED_CLOCK)
        result = adapter.to_result("test prompt")
        assert result.content
        assert result.succeeded is True

    def test_to_result_provider(self):
        adapter = AnthropicStreamingAdapter(clock=FIXED_CLOCK)
        result = adapter.to_result("test")
        from mcoi_runtime.contracts.llm import LLMProvider
        assert result.provider == LLMProvider.STUB

    def test_with_fake_key(self):
        # No real SDK = still stub
        adapter = AnthropicStreamingAdapter(api_key="fake-key", clock=FIXED_CLOCK)
        # Will be available only if anthropic SDK is installed
        chunks = list(adapter.stream_completion("test"))
        assert len(chunks) >= 1

    def test_custom_model(self):
        adapter = AnthropicStreamingAdapter(
            default_model="claude-haiku-4-5-20251001", clock=FIXED_CLOCK,
        )
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
