"""Comprehensive tests for CopilotRuntimeIntegration bridge.

Covers construction validation, all surface-specific copilot methods,
memory mesh attachment, graph attachment, event emission, and end-to-end
integration workflows.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.copilot_runtime import (
    ConversationMode,
    IntentKind,
)
from mcoi_runtime.contracts.memory_mesh import MemoryRecord
from mcoi_runtime.core.copilot_runtime import CopilotRuntimeEngine
from mcoi_runtime.core.copilot_runtime_integration import CopilotRuntimeIntegration
from mcoi_runtime.core.engine_protocol import FixedClock
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine

FIXED_TIME = "2026-01-01T00:00:00+00:00"


@pytest.fixture
def es():
    return EventSpineEngine()


@pytest.fixture
def clock():
    return FixedClock(FIXED_TIME)


@pytest.fixture
def copilot(es, clock):
    return CopilotRuntimeEngine(es, clock=clock)


@pytest.fixture
def mem():
    return MemoryMeshEngine()


@pytest.fixture
def integration(copilot, es, mem):
    return CopilotRuntimeIntegration(copilot, es, mem)


# ===================================================================
# CONSTRUCTION TESTS
# ===================================================================


class TestConstruction:
    def test_valid_construction(self, copilot, es, mem):
        integ = CopilotRuntimeIntegration(copilot, es, mem)
        assert integ is not None

    def test_invalid_copilot_engine(self, es, mem):
        with pytest.raises(RuntimeCoreInvariantError):
            CopilotRuntimeIntegration("not-engine", es, mem)

    def test_invalid_copilot_none(self, es, mem):
        with pytest.raises(RuntimeCoreInvariantError):
            CopilotRuntimeIntegration(None, es, mem)

    def test_invalid_event_spine(self, copilot, mem):
        with pytest.raises(RuntimeCoreInvariantError):
            CopilotRuntimeIntegration(copilot, "not-spine", mem)

    def test_invalid_event_spine_none(self, copilot, mem):
        with pytest.raises(RuntimeCoreInvariantError):
            CopilotRuntimeIntegration(copilot, None, mem)

    def test_invalid_memory_engine(self, copilot, es):
        with pytest.raises(RuntimeCoreInvariantError):
            CopilotRuntimeIntegration(copilot, es, "not-memory")

    def test_invalid_memory_engine_none(self, copilot, es):
        with pytest.raises(RuntimeCoreInvariantError):
            CopilotRuntimeIntegration(copilot, es, None)

    def test_invalid_all_args(self):
        with pytest.raises(RuntimeCoreInvariantError):
            CopilotRuntimeIntegration("a", "b", "c")


# ===================================================================
# SURFACE-SPECIFIC COPILOT METHODS
# ===================================================================


class TestOperatorWorkspace:
    def test_basic_call(self, integration):
        result = integration.copilot_for_operator_workspace("t1", "ws1")
        assert result["tenant_id"] == "t1"
        assert result["source_type"] == "operator_workspace"

    def test_returns_dict(self, integration):
        result = integration.copilot_for_operator_workspace("t1", "ws1")
        assert isinstance(result, dict)

    def test_has_session_id(self, integration):
        result = integration.copilot_for_operator_workspace("t1", "ws1")
        assert "session_id" in result

    def test_has_intent_id(self, integration):
        result = integration.copilot_for_operator_workspace("t1", "ws1")
        assert "intent_id" in result

    def test_default_mode(self, integration):
        result = integration.copilot_for_operator_workspace("t1", "ws1")
        assert result["mode"] == "interactive"

    def test_default_intent_kind(self, integration):
        result = integration.copilot_for_operator_workspace("t1", "ws1")
        assert result["intent_kind"] == "query"

    def test_custom_mode(self, integration):
        result = integration.copilot_for_operator_workspace(
            "t1", "ws1", mode=ConversationMode.GUIDED)
        assert result["mode"] == "guided"

    def test_custom_intent_kind(self, integration):
        result = integration.copilot_for_operator_workspace(
            "t1", "ws1", intent_kind=IntentKind.EXPLAIN)
        assert result["intent_kind"] == "explain"

    def test_custom_session_id(self, integration):
        result = integration.copilot_for_operator_workspace(
            "t1", "ws1", session_id="custom-sess")
        assert result["session_id"] == "custom-sess"

    def test_emits_events(self, integration, es):
        before = es.event_count
        integration.copilot_for_operator_workspace("t1", "ws1")
        assert es.event_count > before


class TestProductConsole:
    def test_basic_call(self, integration):
        result = integration.copilot_for_product_console("t1", "console1")
        assert result["source_type"] == "product_console"

    def test_default_mode_guided(self, integration):
        result = integration.copilot_for_product_console("t1", "console1")
        assert result["mode"] == "guided"

    def test_default_intent_explain(self, integration):
        result = integration.copilot_for_product_console("t1", "console1")
        assert result["intent_kind"] == "explain"

    def test_custom_session_id(self, integration):
        result = integration.copilot_for_product_console(
            "t1", "console1", session_id="pc-sess")
        assert result["session_id"] == "pc-sess"


class TestServiceRequest:
    def test_basic_call(self, integration):
        result = integration.copilot_for_service_request("t1", "sr1")
        assert result["source_type"] == "service_request"

    def test_default_mode_interactive(self, integration):
        result = integration.copilot_for_service_request("t1", "sr1")
        assert result["mode"] == "interactive"

    def test_default_intent_action(self, integration):
        result = integration.copilot_for_service_request("t1", "sr1")
        assert result["intent_kind"] == "action"

    def test_custom_raw_input(self, integration):
        result = integration.copilot_for_service_request(
            "t1", "sr1", raw_input="Custom query")
        assert result["raw_input"] == "Custom query"


class TestCaseRemediation:
    def test_basic_call(self, integration):
        result = integration.copilot_for_case_and_remediation("t1", "case1")
        assert result["source_type"] == "case_remediation"

    def test_default_mode_guided(self, integration):
        result = integration.copilot_for_case_and_remediation("t1", "case1")
        assert result["mode"] == "guided"

    def test_default_intent_summarize(self, integration):
        result = integration.copilot_for_case_and_remediation("t1", "case1")
        assert result["intent_kind"] == "summarize"


class TestCustomerAccount:
    def test_basic_call(self, integration):
        result = integration.copilot_for_customer_account("t1", "cust1")
        assert result["source_type"] == "customer_account"

    def test_default_mode_interactive(self, integration):
        result = integration.copilot_for_customer_account("t1", "cust1")
        assert result["mode"] == "interactive"

    def test_default_intent_query(self, integration):
        result = integration.copilot_for_customer_account("t1", "cust1")
        assert result["intent_kind"] == "query"


class TestExecutiveControl:
    def test_basic_call(self, integration):
        result = integration.copilot_for_executive_control("t1", "dir1")
        assert result["source_type"] == "executive_control"

    def test_default_mode_autonomous(self, integration):
        result = integration.copilot_for_executive_control("t1", "dir1")
        assert result["mode"] == "autonomous"

    def test_default_intent_escalate(self, integration):
        result = integration.copilot_for_executive_control("t1", "dir1")
        assert result["intent_kind"] == "escalate"

    def test_custom_identity_ref(self, integration):
        result = integration.copilot_for_executive_control(
            "t1", "dir1", identity_ref="ceo")
        assert result["status"] == "active"


# ===================================================================
# MEMORY MESH ATTACHMENT
# ===================================================================


class TestMemoryMeshAttachment:
    def test_attach_returns_memory_record(self, integration):
        integration.copilot_for_operator_workspace("t1", "ws1")
        record = integration.attach_copilot_state_to_memory_mesh("scope1")
        assert isinstance(record, MemoryRecord)

    def test_attach_has_correct_scope(self, integration):
        integration.copilot_for_operator_workspace("t1", "ws1")
        record = integration.attach_copilot_state_to_memory_mesh("scope1")
        assert record.scope_ref_id == "scope1"

    def test_attach_emits_event(self, integration, es):
        integration.copilot_for_operator_workspace("t1", "ws1")
        before = es.event_count
        integration.attach_copilot_state_to_memory_mesh("scope1")
        assert es.event_count > before

    def test_attach_content_has_totals(self, integration):
        integration.copilot_for_operator_workspace("t1", "ws1")
        record = integration.attach_copilot_state_to_memory_mesh("scope1")
        content = record.content
        assert "total_sessions" in content
        assert "total_turns" in content
        assert "total_intents" in content

    def test_attach_after_multiple_sessions(self, integration):
        integration.copilot_for_operator_workspace("t1", "ws1")
        integration.copilot_for_product_console("t1", "console1")
        record = integration.attach_copilot_state_to_memory_mesh("scope1")
        assert record.content["total_sessions"] == 2


# ===================================================================
# GRAPH ATTACHMENT
# ===================================================================


class TestGraphAttachment:
    def test_attach_returns_dict(self, integration):
        result = integration.attach_copilot_state_to_graph("scope1")
        assert isinstance(result, dict)

    def test_attach_has_scope_ref_id(self, integration):
        result = integration.attach_copilot_state_to_graph("scope1")
        assert result["scope_ref_id"] == "scope1"

    def test_attach_has_totals(self, integration):
        result = integration.attach_copilot_state_to_graph("scope1")
        for key in ["total_sessions", "total_turns", "total_intents",
                     "total_plans", "total_decisions", "total_responses",
                     "total_violations"]:
            assert key in result

    def test_attach_reflects_state(self, integration):
        integration.copilot_for_operator_workspace("t1", "ws1")
        result = integration.attach_copilot_state_to_graph("scope1")
        assert result["total_sessions"] == 1
        assert result["total_intents"] == 1


# ===================================================================
# END-TO-END INTEGRATION TESTS
# ===================================================================


class TestEndToEnd:
    def test_full_workflow(self, integration, copilot):
        """Full lifecycle: start -> turn -> plan -> decision -> complete."""
        from mcoi_runtime.contracts.copilot_runtime import ActionDisposition

        result = integration.copilot_for_operator_workspace("t1", "ws1")
        sid = result["session_id"]

        copilot.record_turn("tr1", "t1", sid, result["intent_id"],
                            "What is happening?", "Here is the summary")
        copilot.build_action_plan("p1", "t1", sid, result["intent_id"],
                                  "monitoring", "check_status")
        copilot.record_copilot_decision("d1", "t1", sid, "p1",
                                        ActionDisposition.ALLOWED, "Approved")
        copilot.complete_session(sid)

        snap = integration.attach_copilot_state_to_graph("scope1")
        assert snap["total_sessions"] == 1
        assert snap["total_turns"] == 1
        assert snap["total_plans"] == 1
        assert snap["total_decisions"] == 1

    def test_multiple_surfaces_same_tenant(self, integration):
        integration.copilot_for_operator_workspace("t1", "ws1")
        integration.copilot_for_product_console("t1", "console1")
        integration.copilot_for_service_request("t1", "sr1")

        graph = integration.attach_copilot_state_to_graph("scope1")
        assert graph["total_sessions"] == 3
        assert graph["total_intents"] == 3

    def test_different_tenants(self, integration):
        integration.copilot_for_operator_workspace("t1", "ws1")
        integration.copilot_for_operator_workspace("t2", "ws2")

        graph = integration.attach_copilot_state_to_graph("scope1")
        assert graph["total_sessions"] == 2

    def test_memory_and_graph_consistent(self, integration):
        integration.copilot_for_operator_workspace("t1", "ws1")

        mem_record = integration.attach_copilot_state_to_memory_mesh("scope1")
        graph = integration.attach_copilot_state_to_graph("scope1")

        assert mem_record.content["total_sessions"] == graph["total_sessions"]
        assert mem_record.content["total_intents"] == graph["total_intents"]
