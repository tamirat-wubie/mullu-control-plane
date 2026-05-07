"""Phase 215C — Task queue tests."""

import pytest
from mcoi_runtime.core.task_queue import TaskQueue

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


class TestTaskQueue:
    def test_submit_and_pop(self):
        q = TaskQueue(clock=FIXED_CLOCK)
        q.submit("t1", {"data": "hello"})
        task = q.pop()
        assert task is not None
        assert task.task_id == "t1"

    def test_priority_order(self):
        q = TaskQueue(clock=FIXED_CLOCK)
        q.submit("low", {}, priority=1)
        q.submit("high", {}, priority=10)
        q.submit("mid", {}, priority=5)
        assert q.pop().task_id == "high"
        assert q.pop().task_id == "mid"
        assert q.pop().task_id == "low"

    def test_pop_empty(self):
        q = TaskQueue(clock=FIXED_CLOCK)
        assert q.pop() is None

    def test_peek(self):
        q = TaskQueue(clock=FIXED_CLOCK)
        q.submit("t1", {}, priority=5)
        assert q.peek().task_id == "t1"
        assert q.depth == 1  # Not removed

    def test_max_depth(self):
        q = TaskQueue(clock=FIXED_CLOCK, max_depth=2)
        q.submit("t1", {})
        q.submit("t2", {})
        with pytest.raises(ValueError, match="queue full"):
            q.submit("t3", {})

    def test_max_depth_error_is_bounded(self):
        q = TaskQueue(clock=FIXED_CLOCK, max_depth=2)
        q.submit("t1", {})
        q.submit("t2", {})
        with pytest.raises(ValueError, match="queue full") as excinfo:
            q.submit("t3", {})
        assert str(excinfo.value) == "queue full"
        assert "2" not in str(excinfo.value)

    def test_process_one(self):
        q = TaskQueue(clock=FIXED_CLOCK)
        q.submit("t1", {"x": 1})
        result = q.process_one(lambda payload: {"result": payload["x"] + 1})
        assert result is not None
        assert result.succeeded is True
        assert result.output["result"] == 2

    def test_process_empty(self):
        q = TaskQueue(clock=FIXED_CLOCK)
        assert q.process_one(lambda p: {}) is None

    def test_process_failure(self):
        q = TaskQueue(clock=FIXED_CLOCK)
        q.submit("t1", {})
        result = q.process_one(lambda p: (_ for _ in ()).throw(RuntimeError("fail")))
        assert result.succeeded is False
        assert result.error == "task handler error (RuntimeError)"
        assert "fail" not in result.error

    def test_process_timeout_failure_is_sanitized(self):
        q = TaskQueue(clock=FIXED_CLOCK)
        q.submit("t1", {})
        result = q.process_one(lambda p: (_ for _ in ()).throw(TimeoutError("secret timeout detail")))
        assert result.succeeded is False
        assert result.error == "task timeout (TimeoutError)"
        assert "secret timeout detail" not in result.error

    def test_record_result_sanitizes_manual_error(self):
        q = TaskQueue(clock=FIXED_CLOCK)
        result = q.record_result("t1", {}, succeeded=False, error="secret manual detail")
        assert result.succeeded is False
        assert result.error == "task failed"
        assert "secret manual detail" not in result.error

    def test_get_result(self):
        q = TaskQueue(clock=FIXED_CLOCK)
        q.submit("t1", {})
        q.process_one(lambda p: {"done": True})
        result = q.get_result("t1")
        assert result is not None
        assert result.output["done"] is True

    def test_summary(self):
        q = TaskQueue(clock=FIXED_CLOCK)
        q.submit("t1", {})
        q.process_one(lambda p: {})
        s = q.summary()
        assert s["submitted"] == 1
        assert s["processed"] == 1
        assert s["depth"] == 0
