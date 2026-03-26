"""Phase 214C — Graceful shutdown tests."""

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

    def test_hook_failure(self):
        mgr = ShutdownManager()
        mgr.register("ok", lambda: {"ok": True})
        mgr.register("fail", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        result = mgr.execute()
        assert result.hooks_succeeded == 1
        assert result.hooks_failed == 1

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
