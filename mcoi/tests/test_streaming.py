"""Phase 200C — Streaming adapter tests."""

import pytest
from mcoi_runtime.app.streaming import StreamBuffer, StreamEvent, StreamingAdapter
from mcoi_runtime.contracts.llm import LLMProvider, LLMResult

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


def _result(content="hello world response", succeeded=True, error=""):
    return LLMResult(
        content=content,
        input_tokens=10,
        output_tokens=5,
        cost=0.001,
        model_name="test-model",
        provider=LLMProvider.STUB,
        finished=succeeded,
        error=error,
    )


class TestStreamEvent:
    def test_to_sse(self):
        event = StreamEvent(event_type="token", data={"text": "hello"})
        sse = event.to_sse()
        assert "event: token\n" in sse
        assert '"text": "hello"' in sse
        assert sse.endswith("\n\n")

    def test_frozen(self):
        event = StreamEvent(event_type="token", data={"text": "hi"})
        with pytest.raises(AttributeError):
            event.event_type = "done"


class TestStreamingAdapter:
    def test_stream_success(self):
        adapter = StreamingAdapter(clock=FIXED_CLOCK, chunk_size=5)
        events = list(adapter.stream_result(_result(), request_id="r1"))

        # Should have: meta + N tokens + done
        event_types = [e.event_type for e in events]
        assert event_types[0] == "meta"
        assert event_types[-1] == "done"
        assert "token" in event_types
        assert events[-1].data["governed"] is True

    def test_stream_error(self):
        result = _result(content="", succeeded=False, error="budget exhausted")
        adapter = StreamingAdapter(clock=FIXED_CLOCK)
        events = list(adapter.stream_result(result, request_id="r2"))
        assert len(events) == 1
        assert events[0].event_type == "error"
        assert "budget" in events[0].data["error"]

    def test_stream_reconstructs_content(self):
        original = "The quick brown fox jumps over the lazy dog"
        adapter = StreamingAdapter(clock=FIXED_CLOCK, chunk_size=10)
        buf = StreamBuffer()
        buf.consume(adapter.stream_result(_result(content=original)))
        assert buf.content == original
        assert buf.succeeded is True

    def test_stream_token_count(self):
        content = "abcdefghijklmnopqrst"  # 20 chars
        adapter = StreamingAdapter(clock=FIXED_CLOCK, chunk_size=5)
        buf = StreamBuffer()
        buf.consume(adapter.stream_result(_result(content=content)))
        assert buf.token_count == 4  # 20/5 = 4 chunks

    def test_stream_to_sse_format(self):
        adapter = StreamingAdapter(clock=FIXED_CLOCK, chunk_size=100)
        sse_strings = list(adapter.stream_to_sse(_result()))
        assert all(isinstance(s, str) for s in sse_strings)
        assert all(s.endswith("\n\n") for s in sse_strings)

    def test_meta_event_has_model_info(self):
        adapter = StreamingAdapter(clock=FIXED_CLOCK)
        events = list(adapter.stream_result(_result()))
        meta = events[0]
        assert meta.event_type == "meta"
        assert meta.data["model"] == "test-model"
        assert meta.data["provider"] == "stub"

    def test_done_event_has_cost(self):
        adapter = StreamingAdapter(clock=FIXED_CLOCK)
        events = list(adapter.stream_result(_result()))
        done = events[-1]
        assert done.event_type == "done"
        assert done.data["cost"] == 0.001
        assert done.data["input_tokens"] == 10
        assert done.data["output_tokens"] == 5

    def test_empty_content(self):
        adapter = StreamingAdapter(clock=FIXED_CLOCK)
        buf = StreamBuffer()
        buf.consume(adapter.stream_result(_result(content="")))
        assert buf.content == ""
        assert buf.succeeded is True
        assert buf.token_count == 0

    def test_request_id_propagated(self):
        adapter = StreamingAdapter(clock=FIXED_CLOCK)
        events = list(adapter.stream_result(_result(), request_id="req-42"))
        meta = events[0]
        done = events[-1]
        assert meta.data["request_id"] == "req-42"
        assert done.data["request_id"] == "req-42"


class TestStreamBuffer:
    def test_empty_buffer(self):
        buf = StreamBuffer()
        assert buf.content == ""
        assert buf.token_count == 0
        assert buf.done_event is None
        assert buf.error_event is None
        assert buf.succeeded is False

    def test_consume_success_stream(self):
        adapter = StreamingAdapter(clock=FIXED_CLOCK)
        buf = StreamBuffer()
        buf.consume(adapter.stream_result(_result()))
        assert buf.content
        assert buf.succeeded is True
        assert buf.done_event is not None
        assert buf.error_event is None

    def test_consume_error_stream(self):
        adapter = StreamingAdapter(clock=FIXED_CLOCK)
        buf = StreamBuffer()
        buf.consume(adapter.stream_result(_result(succeeded=False, error="fail")))
        assert buf.content == ""
        assert buf.succeeded is False
        assert buf.error_event is not None

    def test_events_list(self):
        adapter = StreamingAdapter(clock=FIXED_CLOCK, chunk_size=5)
        buf = StreamBuffer()
        buf.consume(adapter.stream_result(_result(content="12345")))
        assert len(buf.events) >= 3  # meta + 1 token + done
