"""Governed Tool Use Tests — LLM function calling governance."""

from mcoi_runtime.contracts import CapabilityContract, CapabilityEffectClass, CapabilityIntentSource
from mcoi_runtime.core.governed_tool_use import (
    GovernedToolRegistry,
    ToolDefinition,
)
from mcoi_runtime.governance.audit.rejected_path_records import RejectedPathRecorder


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

    def test_capability_contract_coverage_reports_synthesized_contracts(self):
        r = _registry()
        r.register(_tool("summarize_doc"))
        r.register(_tool("send_email", declared_effects=("email_sent",), requires_approval=True))

        report = r.capability_contract_coverage()
        body = report.to_dict()

        assert report.complete is True
        assert report.tool_count == 2
        assert report.covered_tool_count == 2
        assert report.explicit_contract_count == 0
        assert report.synthesized_contract_count == 2
        assert body["records"][0]["tool_name"] == "send_email"
        assert body["records"][0]["covered"] is True

    def test_capability_contract_coverage_reports_blocked_contracts(self):
        blocked_contract = CapabilityContract(
            capability="deploy_service",
            layer="runtime_tool",
            cap_level=3,
            gov_tier=1,
            axis_T="current_episode",
            axis_E="bounded_by_budget_ref",
            axis_C="bounded_by_schema",
            axis_R="high",
            axis_V=CapabilityEffectClass.EFFECTFUL,
            precond=("registered",),
            fail_mode=("phi_gov_block",),
            reversible=False,
            intent_source=CapabilityIntentSource.USER_DIRECT,
        )
        r = _registry()
        r.register(_tool("deploy_service", capability_contract=blocked_contract))

        report = r.capability_contract_coverage()
        body = report.to_dict()

        assert report.complete is False
        assert report.tool_count == 1
        assert report.covered_tool_count == 0
        assert report.explicit_contract_count == 1
        assert report.blocked_tool_count == 1
        assert body["issues"][0]["tool_name"] == "deploy_service"
        assert body["issues"][0]["reasons"] == ["governance_tier_below_capability_level"]

    def test_decision_read_model_reports_allowed_and_blocked_tool_decisions(self):
        blocked_contract = CapabilityContract(
            capability="send_email",
            layer="runtime_tool",
            cap_level=1,
            gov_tier=1,
            axis_T="current_episode",
            axis_E="bounded_by_budget_ref",
            axis_C="bounded_by_schema",
            axis_R="medium",
            axis_V=CapabilityEffectClass.EFFECTFUL,
            precond=("registered",),
            fail_mode=("phi_gov_block",),
            reversible=False,
            intent_source=CapabilityIntentSource.USER_DIRECT,
        )
        r = _registry()
        r.register(_tool("summarize_doc"), executor=_executor)
        r.register(_tool("send_email", capability_contract=blocked_contract), executor=_executor)

        allowed = r.invoke("summarize_doc", {}, session_id="s1", tenant_id="tenant-1")
        blocked = r.invoke(
            "send_email",
            {},
            session_id="s1",
            tenant_id="tenant-1",
            intent_source=CapabilityIntentSource.MONITORED_CONTENT,
        )
        body = r.decision_read_model()

        assert allowed.allowed is True
        assert blocked.allowed is False
        assert body["decision_count"] == 2
        assert body["allowed_count"] == 1
        assert body["blocked_count"] == 1
        assert body["records"][0]["stage"] == "executed"
        assert body["records"][0]["effect_class"] == "value_producing"
        assert body["records"][1]["stage"] == "capability_contract"
        assert body["records"][1]["intent_source"] == "monitored_content"
        assert body["records"][1]["reasons"] == ["effectful_action_requires_user_direct_intent_source"]

    def test_decision_read_model_is_bounded(self):
        r = _registry(max_decision_records=2)
        r.register(_tool("a"), executor=_executor)
        r.register(_tool("b"), executor=_executor)
        r.register(_tool("c"), executor=_executor)

        r.invoke("a", {})
        r.invoke("b", {})
        r.invoke("c", {})
        body = r.decision_read_model(limit=10)

        assert body["decision_count"] == 2
        assert body["allowed_count"] == 2
        assert body["blocked_count"] == 0
        assert [record["tool_name"] for record in body["records"]] == ["b", "c"]

    def test_blocked_tool_decision_records_rejected_path_receipt(self):
        recorder = RejectedPathRecorder()
        r = _registry(rejected_path_recorder=recorder)
        r.register(_tool("send_email", declared_effects=("email_sent",)), executor=_executor)

        result = r.invoke(
            "send_email",
            {},
            session_id="session-1",
            tenant_id="tenant-1",
            intent_source=CapabilityIntentSource.MONITORED_CONTENT,
        )
        records = recorder.list_records()

        assert result.allowed is False
        assert len(records) == 1
        assert records[0].record_id.startswith("gci-rejected-path-")
        assert records[0].capability == "send_email"
        assert records[0].actor_id == "session-1"
        assert records[0].occurred_at == "2026-04-07T12:00:00Z"
        assert records[0].reason == "capability_contract:effectful_action_requires_user_direct_intent_source"

    def test_rejected_path_recorder_can_be_bound_after_registry_creation(self):
        recorder = RejectedPathRecorder()
        r = _registry()
        r.bind_rejected_path_recorder(recorder)

        result = r.invoke("unknown_tool", {}, tenant_id="tenant-1")
        records = recorder.list_records()

        assert result.allowed is False
        assert len(records) == 1
        assert records[0].capability == "unknown"
        assert records[0].actor_id == "tenant-1"
        assert records[0].reason == "allowlist:tool_not_registered"
