"""Phase 214C — Graceful shutdown tests."""

import threading

import pytest
from mcoi_runtime.core.graceful_shutdown import ShutdownManager


class TestShutdownManager:
    def test_register_and_execute(self):
        mgr = ShutdownManager()
        mgr.register("save", lambda: {"saved": True})
        result = mgr.execute()
        assert result.hooks_run == 1
        assert result.hooks_succeeded == 1

    def test_priority_order(self):
        mgr = ShutdownManager()
        order = []
        mgr.register("low", lambda: (order.append("low"), {})[1], priority=1)
        mgr.register("high", lambda: (order.append("high"), {})[1], priority=100)
        mgr.register("mid", lambda: (order.append("mid"), {})[1], priority=50)
        mgr.execute()
        assert order == ["high", "mid", "low"]

    def test_equal_priority_hooks_run_lifo(self):
        mgr = ShutdownManager()
        order: list[str] = []
        mgr.register("first", lambda: (order.append("first"), {})[1], priority=10)
        mgr.register("second", lambda: (order.append("second"), {})[1], priority=10)
        mgr.register("third", lambda: (order.append("third"), {})[1], priority=10)

        result = mgr.execute()

        assert order == ["third", "second", "first"]
        assert mgr.hook_names() == ["third", "second", "first"]
        assert result.hooks_run == 3

    def test_hook_failure(self):
        mgr = ShutdownManager()
        mgr.register("ok", lambda: {"ok": True})
        mgr.register("fail", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        result = mgr.execute()
        failed_result = next(item for item in result.results if item["hook"] == "fail")
        assert result.hooks_succeeded == 1
        assert result.hooks_failed == 1
        assert failed_result["error"] == "shutdown hook error (RuntimeError)"
        assert "boom" not in failed_result["error"]

    def test_is_shutdown(self):
        mgr = ShutdownManager()
        assert mgr.is_shutdown is False
        mgr.execute()
        assert mgr.is_shutdown is True

    def test_hook_names(self):
        mgr = ShutdownManager()
        mgr.register("b", lambda: {}, priority=1)
        mgr.register("a", lambda: {}, priority=10)
        assert mgr.hook_names() == ["a", "b"]

    def test_summary(self):
        mgr = ShutdownManager()
        mgr.register("x", lambda: {})
        s = mgr.summary()
        assert s["hooks"] == 1
        assert s["shutdown_complete"] is False

    def test_register_rejects_invalid_hook_contracts(self):
        mgr = ShutdownManager()
        mgr.register("valid", lambda: {})

        with pytest.raises(ValueError, match="name"):
            mgr.register("", lambda: {})
        with pytest.raises(ValueError, match="unique"):
            mgr.register("valid", lambda: {})
        with pytest.raises(ValueError, match="callable"):
            mgr.register("not-callable", None)
        with pytest.raises(ValueError, match="priority"):
            mgr.register("bad-priority", lambda: {}, priority=True)
        with pytest.raises(ValueError, match="timeout_seconds"):
            mgr.register("bad-timeout", lambda: {}, timeout_seconds=0)
        assert mgr.hook_count == 1
        assert mgr.hook_names() == ["valid"]
        assert mgr.summary()["shutdown_complete"] is False

    def test_hook_result_cannot_override_manager_status_fields(self):
        mgr = ShutdownManager()
        mgr.register(
            "save-state",
            lambda: {"hook": "spoofed", "status": "spoofed", "saved": True},
        )

        result = mgr.execute()
        hook_result = result.results[0]

        assert hook_result["hook"] == "save-state"
        assert hook_result["status"] == "ok"
        assert hook_result["saved"] is True

    def test_hook_non_dict_result_is_bounded_error(self):
        mgr = ShutdownManager()
        mgr.register("bad-result", lambda: "raw-secret-value")

        result = mgr.execute()
        hook_result = result.results[0]

        assert result.hooks_succeeded == 0
        assert result.hooks_failed == 1
        assert hook_result["hook"] == "bad-result"
        assert hook_result["status"] == "error"
        assert hook_result["error"] == "shutdown hook error (TypeError)"
        assert "raw-secret-value" not in str(hook_result)

    def test_execute_is_idempotent_and_registration_closes(self):
        mgr = ShutdownManager()
        calls: list[str] = []
        mgr.register("persist", lambda: (calls.append("persist"), {"persisted": True})[1])

        first = mgr.execute()
        second = mgr.execute()

        with pytest.raises(RuntimeError, match="registration closed"):
            mgr.register("late", lambda: {})
        assert first is second
        assert calls == ["persist"]
        assert mgr.summary()["shutdown_started"] is True
        assert mgr.summary()["shutdown_complete"] is True

    def test_hook_can_observe_shutdown_summary_without_deadlock(self):
        mgr = ShutdownManager()
        observed: list[dict[str, object]] = []
        mgr.register(
            "observe",
            lambda: (observed.append(mgr.summary()), {"observed": True})[1],
            timeout_seconds=0.2,
        )

        result = mgr.execute()

        assert result.hooks_succeeded == 1
        assert observed[0]["shutdown_started"] is True
        assert observed[0]["shutdown_complete"] is False

    def test_slow_hook_times_out_without_blocking_later_hooks(self):
        mgr = ShutdownManager()
        release = threading.Event()
        order: list[str] = []

        def slow_hook():
            order.append("slow")
            release.wait(timeout=1.0)
            return {"released": release.is_set()}

        def fast_hook():
            order.append("fast")
            return {"done": True}

        mgr.register("slow", slow_hook, priority=100, timeout_seconds=0.01)
        mgr.register("fast", fast_hook, priority=1)

        result = mgr.execute()
        release.set()
        timed_out = next(item for item in result.results if item["hook"] == "slow")
        fast = next(item for item in result.results if item["hook"] == "fast")

        assert order == ["slow", "fast"]
        assert result.hooks_succeeded == 1
        assert result.hooks_failed == 1
        assert timed_out["error"] == "shutdown hook timeout"
        assert fast["status"] == "ok"
