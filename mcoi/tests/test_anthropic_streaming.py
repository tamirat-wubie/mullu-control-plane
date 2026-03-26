"""Phase 211B — Anthropic streaming adapter tests."""

import pytest
from mcoi_runtime.adapters.anthropic_streaming import (
    AnthropicStreamingAdapter, StreamChunk,
)

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


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
