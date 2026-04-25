"""Governed Tool Use Tests — LLM function calling governance."""

from mcoi_runtime.core.governed_tool_use import (
    GovernedToolRegistry,
    ToolDefinition,
)


def _registry(**kw):
    return GovernedToolRegistry(clock=kw.pop("clock", lambda: "2026-04-07T12:00:00Z"), **kw)


def _tool(name="get_balance", **kw):
    return ToolDefinition(name=name, description=f"Test tool {name}", **kw)


def _executor(name, args):
    return {"result": f"executed {name}", "args": args}


class TestAllowlist:
    def test_registered_tool_allowed(self):
        r = _registry()
        r.register(_tool(), executor=_executor)
        res = r.invoke("get_balance", {})
        assert res.allowed is True
        assert res.result["result"] == "executed get_balance"

    def test_unregistered_tool_denied(self):
        r = _registry()
        res = r.invoke("evil_tool", {})
        assert res.allowed is False
        assert "not registered" in res.error

    def test_disabled_tool_denied(self):
        r = _registry()
        r.register(_tool(enabled=False), executor=_executor)
        res = r.invoke("get_balance", {})
        assert res.allowed is False
        assert "disabled" in res.error


class TestParameterValidation:
    def test_missing_required_param(self):
        r = _registry()
        r.register(_tool(required_params=frozenset({"account_id"})), executor=_executor)
        res = r.invoke("get_balance", {})
        assert res.allowed is False
        assert "account_id" in res.error

    def test_required_param_present(self):
        r = _registry()
        r.register(_tool(required_params=frozenset({"account_id"})), executor=_executor)
        res = r.invoke("get_balance", {"account_id": "123"})
        assert res.allowed is True

    def test_none_value_counts_as_missing(self):
        r = _registry()
        r.register(_tool(required_params=frozenset({"x"})), executor=_executor)
        res = r.invoke("get_balance", {"x": None})
        assert res.allowed is False


class TestSessionLimits:
    def test_limit_enforced(self):
        r = _registry()
        r.register(_tool(max_calls_per_session=2), executor=_executor)
        r.invoke("get_balance", {}, session_id="s1")
        r.invoke("get_balance", {}, session_id="s1")
        res = r.invoke("get_balance", {}, session_id="s1")
        assert res.allowed is False
        assert "limit" in res.error

    def test_limit_per_session(self):
        r = _registry()
        r.register(_tool(max_calls_per_session=1), executor=_executor)
        r.invoke("get_balance", {}, session_id="s1")
        res = r.invoke("get_balance", {}, session_id="s2")
        assert res.allowed is True  # Different session

    def test_zero_means_unlimited(self):
        r = _registry()
        r.register(_tool(max_calls_per_session=0), executor=_executor)
        for _ in range(20):
            r.invoke("get_balance", {}, session_id="s1")
        # Should not raise or deny


class TestApproval:
    def test_requires_approval_denied(self):
        r = _registry()
        r.register(_tool(requires_approval=True), executor=_executor)
        res = r.invoke("get_balance", {})
        assert res.allowed is False
        assert "approval" in res.error


class TestExecution:
    def test_executor_exception_handled(self):
        def bad_executor(name, args):
            raise ValueError("bad input")

        r = _registry()
        r.register(_tool(), executor=bad_executor)
        res = r.invoke("get_balance", {})
        assert res.allowed is True
        assert "ValueError" in res.error

    def test_no_executor_registered(self):
        r = _registry()
        r.register(_tool())  # No executor
        res = r.invoke("get_balance", {})
        assert "no executor" in res.error

    def test_inline_executor(self):
        r = _registry()
        r.register(_tool())
        res = r.invoke("get_balance", {"x": 1}, executor=lambda n, a: {"ok": True})
        assert res.allowed is True
        assert res.result == {"ok": True}


class TestRegistryManagement:
    def test_list_tools(self):
        r = _registry()
        r.register(_tool("a"))
        r.register(_tool("b"))
        r.register(_tool("c", enabled=False))
        assert len(r.list_tools(enabled_only=True)) == 2
        assert len(r.list_tools(enabled_only=False)) == 3

    def test_unregister(self):
        r = _registry()
        r.register(_tool())
        assert r.unregister("get_balance") is True
        assert r.unregister("get_balance") is False

    def test_get_tool(self):
        r = _registry()
        r.register(_tool())
        assert r.get_tool("get_balance") is not None
        assert r.get_tool("nonexistent") is None

    def test_session_usage(self):
        r = _registry()
        r.register(_tool(), executor=_executor)
        r.invoke("get_balance", {}, session_id="s1")
        r.invoke("get_balance", {}, session_id="s1")
        usage = r.session_usage("s1")
        assert usage["get_balance"].call_count == 2

    def test_clear_session(self):
        r = _registry()
        r.register(_tool(), executor=_executor)
        r.invoke("get_balance", {}, session_id="s1")
        r.clear_session("s1")
        assert r.session_usage("s1") == {}

    def test_summary(self):
        r = _registry()
        r.register(_tool(), executor=_executor)
        r.invoke("get_balance", {}, session_id="s1")
        s = r.summary()
        assert s["registered_tools"] == 1
        assert s["total_invocations"] == 1
