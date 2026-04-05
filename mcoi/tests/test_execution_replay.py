"""Phase 207D — Execution replay tests."""

import pytest
from mcoi_runtime.core.execution_replay import ReplayExecutor, ReplayRecorder

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


class TestReplayRecorder:
    def test_start_and_record(self):
        rec = ReplayRecorder(clock=FIXED_CLOCK)
        rec.start_trace("t1")
        frame = rec.record_frame("t1", "llm.complete", {"prompt": "hi"}, {"content": "hello"}, 50.0)
        assert frame.operation == "llm.complete"
        assert frame.sequence == 1
        assert frame.frame_hash

    def test_complete_trace(self):
        rec = ReplayRecorder(clock=FIXED_CLOCK)
        rec.start_trace("t1")
        rec.record_frame("t1", "a", {"x": 1}, {"y": 2})
        rec.record_frame("t1", "b", {"x": 3}, {"y": 4})
        trace = rec.complete_trace("t1")
        assert len(trace.frames) == 2
        assert trace.trace_hash
        assert trace.total_duration_ms >= 0

    def test_duplicate_start(self):
        rec = ReplayRecorder(clock=FIXED_CLOCK)
        rec.start_trace("t1")
        with pytest.raises(ValueError, match="^trace already started$") as excinfo:
            rec.start_trace("t1")
        assert "t1" not in str(excinfo.value)

    def test_record_without_start(self):
        rec = ReplayRecorder(clock=FIXED_CLOCK)
        with pytest.raises(ValueError, match="^trace not started$") as excinfo:
            rec.record_frame("t1", "a", {}, {})
        assert "t1" not in str(excinfo.value)

    def test_max_frames(self):
        rec = ReplayRecorder(clock=FIXED_CLOCK, max_frames=3)
        rec.start_trace("t1")
        rec.record_frame("t1", "a", {}, {})
        rec.record_frame("t1", "b", {}, {})
        rec.record_frame("t1", "c", {}, {})
        with pytest.raises(ValueError, match="^trace exceeded max frames$") as excinfo:
            rec.record_frame("t1", "d", {}, {})
        assert "t1" not in str(excinfo.value)
        assert "3" not in str(excinfo.value)

    def test_complete_missing_trace_is_bounded(self):
        rec = ReplayRecorder(clock=FIXED_CLOCK)
        with pytest.raises(ValueError, match="^trace not found$") as excinfo:
            rec.complete_trace("t1")
        assert "t1" not in str(excinfo.value)

    def test_get_trace(self):
        rec = ReplayRecorder(clock=FIXED_CLOCK)
        rec.start_trace("t1")
        rec.record_frame("t1", "a", {}, {})
        rec.complete_trace("t1")
        trace = rec.get_trace("t1")
        assert trace is not None
        assert trace.trace_id == "t1"

    def test_get_missing_trace(self):
        rec = ReplayRecorder(clock=FIXED_CLOCK)
        assert rec.get_trace("nonexistent") is None

    def test_list_traces(self):
        rec = ReplayRecorder(clock=FIXED_CLOCK)
        for i in range(3):
            rec.start_trace(f"t{i}")
            rec.record_frame(f"t{i}", "a", {}, {})
            rec.complete_trace(f"t{i}")
        assert len(rec.list_traces()) == 3

    def test_counts(self):
        rec = ReplayRecorder(clock=FIXED_CLOCK)
        rec.start_trace("t1")
        assert rec.active_count == 1
        rec.record_frame("t1", "a", {}, {})
        rec.complete_trace("t1")
        assert rec.completed_count == 1
        assert rec.active_count == 0

    def test_summary(self):
        rec = ReplayRecorder(clock=FIXED_CLOCK)
        rec.start_trace("t1")
        rec.record_frame("t1", "a", {}, {})
        rec.complete_trace("t1")
        summary = rec.summary()
        assert summary["completed"] == 1
        assert summary["total_frames"] == 1


class TestReplayExecutor:
    def test_replay_match(self):
        rec = ReplayRecorder(clock=FIXED_CLOCK)
        rec.start_trace("t1")
        rec.record_frame("t1", "add", {"a": 1, "b": 2}, {"result": 3})
        trace = rec.complete_trace("t1")

        executor = ReplayExecutor(operations={
            "add": lambda data: {"result": data["a"] + data["b"]},
        })
        results = executor.replay(trace)
        assert results[0]["matched"] is True

    def test_replay_mismatch(self):
        rec = ReplayRecorder(clock=FIXED_CLOCK)
        rec.start_trace("t1")
        rec.record_frame("t1", "add", {"a": 1, "b": 2}, {"result": 3})
        trace = rec.complete_trace("t1")

        executor = ReplayExecutor(operations={
            "add": lambda data: {"result": 999},  # Wrong answer
        })
        results = executor.replay(trace)
        assert results[0]["matched"] is False

    def test_replay_unknown_op(self):
        rec = ReplayRecorder(clock=FIXED_CLOCK)
        rec.start_trace("t1")
        rec.record_frame("t1", "unknown_op", {}, {})
        trace = rec.complete_trace("t1")

        executor = ReplayExecutor(operations={})
        results = executor.replay(trace)
        assert results[0]["matched"] is False
        assert results[0]["reason"] == "unknown operation"
        assert "unknown_op" not in results[0]["reason"]

    def test_verify(self):
        rec = ReplayRecorder(clock=FIXED_CLOCK)
        rec.start_trace("t1")
        rec.record_frame("t1", "echo", {"msg": "hi"}, {"msg": "hi"})
        trace = rec.complete_trace("t1")

        executor = ReplayExecutor(operations={
            "echo": lambda data: {"msg": data["msg"]},
        })
        all_ok, matched, total = executor.verify(trace)
        assert all_ok is True
        assert matched == 1
        assert total == 1

    def test_replay_exception_is_sanitized(self):
        rec = ReplayRecorder(clock=FIXED_CLOCK)
        rec.start_trace("t1")
        rec.record_frame("t1", "explode", {"msg": "hi"}, {"msg": "hi"})
        trace = rec.complete_trace("t1")

        executor = ReplayExecutor(operations={
            "explode": lambda data: (_ for _ in ()).throw(RuntimeError("secret replay failure")),
        })
        results = executor.replay(trace)
        assert results[0]["matched"] is False
        assert results[0]["reason"] == "replay operation error (RuntimeError)"
        assert "secret replay failure" not in results[0]["reason"]
