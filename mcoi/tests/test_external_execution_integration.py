"""Tests for ExternalExecutionIntegration bridge.

Covers constructor validation, all 6 bridge methods, memory mesh attachment,
graph attachment, event emission, and golden-path scenarios.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.external_execution import ExternalExecutionEngine
from mcoi_runtime.core.external_execution_integration import ExternalExecutionIntegration
from mcoi_runtime.contracts.external_execution import (
    ExecutionKind,
    ExecutionRiskLevel,
    SandboxDisposition,
)
from mcoi_runtime.contracts.memory_mesh import MemoryRecord
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TENANT = "tenant-exi-test"
TARGET = "target-exi-test"


@pytest.fixture()
def engines():
    """Return (event_spine, exec_engine, memory_engine) tuple."""
    es = EventSpineEngine()
    ee = ExternalExecutionEngine(es)
    mm = MemoryMeshEngine()
    return es, ee, mm


@pytest.fixture()
def bridge(engines):
    """Return a fully wired ExternalExecutionIntegration with a pre-registered target."""
    es, ee, mm = engines
    ee.register_target(TARGET, TENANT, "Test Target")
    return ExternalExecutionIntegration(ee, es, mm)


@pytest.fixture()
def bridge_with_engines(engines):
    """Return (bridge, es, ee, mm) for tests that need direct engine access."""
    es, ee, mm = engines
    ee.register_target(TARGET, TENANT, "Test Target")
    b = ExternalExecutionIntegration(ee, es, mm)
    return b, es, ee, mm


# ---------------------------------------------------------------------------
# TestConstructorValidation
# ---------------------------------------------------------------------------

class TestConstructorValidation:
    """7 tests: constructor type checks for all three engines."""

    def test_valid_construction(self, engines):
        es, ee, mm = engines
        bridge = ExternalExecutionIntegration(ee, es, mm)
        assert bridge is not None

    def test_rejects_none_execution_engine(self, engines):
        es, _, mm = engines
        with pytest.raises(RuntimeCoreInvariantError):
            ExternalExecutionIntegration(None, es, mm)

    def test_rejects_string_execution_engine(self, engines):
        es, _, mm = engines
        with pytest.raises(RuntimeCoreInvariantError):
            ExternalExecutionIntegration("not-an-engine", es, mm)

    def test_rejects_none_event_spine(self, engines):
        _, ee, mm = engines
        with pytest.raises(RuntimeCoreInvariantError):
            ExternalExecutionIntegration(ee, None, mm)

    def test_rejects_string_event_spine(self, engines):
        _, ee, mm = engines
        with pytest.raises(RuntimeCoreInvariantError):
            ExternalExecutionIntegration(ee, "not-spine", mm)

    def test_rejects_none_memory_engine(self, engines):
        es, ee, _ = engines
        with pytest.raises(RuntimeCoreInvariantError):
            ExternalExecutionIntegration(ee, es, None)

    def test_rejects_wrong_type_memory_engine(self, engines):
        es, ee, _ = engines
        with pytest.raises(RuntimeCoreInvariantError):
            ExternalExecutionIntegration(ee, es, 42)


# ---------------------------------------------------------------------------
# TestExecuteFromServiceRequest
# ---------------------------------------------------------------------------

class TestExecuteFromServiceRequest:
    """10 tests for execute_from_service_request bridge method."""

    def test_returns_dict(self, bridge):
        r = bridge.execute_from_service_request("req-sr-1", TENANT, TARGET)
        assert isinstance(r, dict)

    def test_has_eight_keys(self, bridge):
        r = bridge.execute_from_service_request("req-sr-2", TENANT, TARGET)
        assert len(r) == 8

    def test_source_type(self, bridge):
        r = bridge.execute_from_service_request("req-sr-3", TENANT, TARGET)
        assert r["source_type"] == "service_request"

    def test_request_id_preserved(self, bridge):
        r = bridge.execute_from_service_request("req-sr-4", TENANT, TARGET)
        assert r["request_id"] == "req-sr-4"

    def test_tenant_id_preserved(self, bridge):
        r = bridge.execute_from_service_request("req-sr-5", TENANT, TARGET)
        assert r["tenant_id"] == TENANT

    def test_target_id_preserved(self, bridge):
        r = bridge.execute_from_service_request("req-sr-6", TENANT, TARGET)
        assert r["target_id"] == TARGET

    def test_default_service_ref(self, bridge):
        r = bridge.execute_from_service_request("req-sr-7", TENANT, TARGET)
        assert r["service_ref"] == "none"

    def test_custom_service_ref(self, bridge):
        r = bridge.execute_from_service_request("req-sr-8", TENANT, TARGET, service_ref="svc-abc")
        assert r["service_ref"] == "svc-abc"

    def test_status_is_pending(self, bridge):
        r = bridge.execute_from_service_request("req-sr-9", TENANT, TARGET)
        assert r["status"] == "pending"

    def test_default_sandbox_and_risk(self, bridge):
        r = bridge.execute_from_service_request("req-sr-10", TENANT, TARGET)
        assert r["sandbox"] == "sandboxed"
        assert r["risk_level"] == "low"


# ---------------------------------------------------------------------------
# TestExecuteFromOrchestrationStep
# ---------------------------------------------------------------------------

class TestExecuteFromOrchestrationStep:
    """8 tests for execute_from_orchestration_step bridge method."""

    def test_returns_dict(self, bridge):
        r = bridge.execute_from_orchestration_step("req-os-1", TENANT, TARGET)
        assert isinstance(r, dict)

    def test_has_eight_keys(self, bridge):
        r = bridge.execute_from_orchestration_step("req-os-2", TENANT, TARGET)
        assert len(r) == 8

    def test_source_type(self, bridge):
        r = bridge.execute_from_orchestration_step("req-os-3", TENANT, TARGET)
        assert r["source_type"] == "orchestration_step"

    def test_default_step_ref(self, bridge):
        r = bridge.execute_from_orchestration_step("req-os-4", TENANT, TARGET)
        assert r["step_ref"] == "none"

    def test_custom_step_ref(self, bridge):
        r = bridge.execute_from_orchestration_step("req-os-5", TENANT, TARGET, step_ref="step-7")
        assert r["step_ref"] == "step-7"

    def test_default_kind_is_agent(self, bridge):
        r = bridge.execute_from_orchestration_step("req-os-6", TENANT, TARGET)
        # Default kind for orchestration_step is AGENT -> status pending, sandbox isolated
        assert r["sandbox"] == "isolated"

    def test_default_risk_medium(self, bridge):
        r = bridge.execute_from_orchestration_step("req-os-7", TENANT, TARGET)
        assert r["risk_level"] == "medium"

    def test_request_id_in_result(self, bridge):
        r = bridge.execute_from_orchestration_step("req-os-8", TENANT, TARGET)
        assert r["request_id"] == "req-os-8"


# ---------------------------------------------------------------------------
# TestExecuteFromRemediation
# ---------------------------------------------------------------------------

class TestExecuteFromRemediation:
    """8 tests for execute_from_remediation bridge method."""

    def test_returns_dict(self, bridge):
        r = bridge.execute_from_remediation("req-rm-1", TENANT, TARGET)
        assert isinstance(r, dict)

    def test_has_eight_keys(self, bridge):
        r = bridge.execute_from_remediation("req-rm-2", TENANT, TARGET)
        assert len(r) == 8

    def test_source_type(self, bridge):
        r = bridge.execute_from_remediation("req-rm-3", TENANT, TARGET)
        assert r["source_type"] == "remediation"

    def test_default_remediation_ref(self, bridge):
        r = bridge.execute_from_remediation("req-rm-4", TENANT, TARGET)
        assert r["remediation_ref"] == "none"

    def test_custom_remediation_ref(self, bridge):
        r = bridge.execute_from_remediation("req-rm-5", TENANT, TARGET, remediation_ref="rem-x")
        assert r["remediation_ref"] == "rem-x"

    def test_default_sandbox_sandboxed(self, bridge):
        r = bridge.execute_from_remediation("req-rm-6", TENANT, TARGET)
        assert r["sandbox"] == "sandboxed"

    def test_default_risk_medium(self, bridge):
        r = bridge.execute_from_remediation("req-rm-7", TENANT, TARGET)
        assert r["risk_level"] == "medium"

    def test_custom_overrides(self, bridge):
        r = bridge.execute_from_remediation(
            "req-rm-8", TENANT, TARGET,
            kind=ExecutionKind.AGENT,
            sandbox=SandboxDisposition.ISOLATED,
            risk_level=ExecutionRiskLevel.HIGH,
        )
        assert r["sandbox"] == "isolated"
        assert r["risk_level"] == "high"


# ---------------------------------------------------------------------------
# TestExecuteFromProcurementNeed
# ---------------------------------------------------------------------------

class TestExecuteFromProcurementNeed:
    """8 tests for execute_from_procurement_need bridge method."""

    def test_returns_dict(self, bridge):
        r = bridge.execute_from_procurement_need("req-pn-1", TENANT, TARGET)
        assert isinstance(r, dict)

    def test_has_eight_keys(self, bridge):
        r = bridge.execute_from_procurement_need("req-pn-2", TENANT, TARGET)
        assert len(r) == 8

    def test_source_type(self, bridge):
        r = bridge.execute_from_procurement_need("req-pn-3", TENANT, TARGET)
        assert r["source_type"] == "procurement_need"

    def test_default_procurement_ref(self, bridge):
        r = bridge.execute_from_procurement_need("req-pn-4", TENANT, TARGET)
        assert r["procurement_ref"] == "none"

    def test_custom_procurement_ref(self, bridge):
        r = bridge.execute_from_procurement_need("req-pn-5", TENANT, TARGET, procurement_ref="proc-99")
        assert r["procurement_ref"] == "proc-99"

    def test_default_sandbox_restricted(self, bridge):
        r = bridge.execute_from_procurement_need("req-pn-6", TENANT, TARGET)
        assert r["sandbox"] == "restricted"

    def test_default_risk_low(self, bridge):
        r = bridge.execute_from_procurement_need("req-pn-7", TENANT, TARGET)
        assert r["risk_level"] == "low"

    def test_tenant_and_target_preserved(self, bridge):
        r = bridge.execute_from_procurement_need("req-pn-8", TENANT, TARGET)
        assert r["tenant_id"] == TENANT
        assert r["target_id"] == TARGET


# ---------------------------------------------------------------------------
# TestExecuteFromMarketplaceAction
# ---------------------------------------------------------------------------

class TestExecuteFromMarketplaceAction:
    """8 tests for execute_from_marketplace_action bridge method."""

    def test_returns_dict(self, bridge):
        r = bridge.execute_from_marketplace_action("req-ma-1", TENANT, TARGET)
        assert isinstance(r, dict)

    def test_has_eight_keys(self, bridge):
        r = bridge.execute_from_marketplace_action("req-ma-2", TENANT, TARGET)
        assert len(r) == 8

    def test_source_type(self, bridge):
        r = bridge.execute_from_marketplace_action("req-ma-3", TENANT, TARGET)
        assert r["source_type"] == "marketplace_action"

    def test_default_marketplace_ref(self, bridge):
        r = bridge.execute_from_marketplace_action("req-ma-4", TENANT, TARGET)
        assert r["marketplace_ref"] == "none"

    def test_custom_marketplace_ref(self, bridge):
        r = bridge.execute_from_marketplace_action("req-ma-5", TENANT, TARGET, marketplace_ref="mkt-42")
        assert r["marketplace_ref"] == "mkt-42"

    def test_default_sandbox_sandboxed(self, bridge):
        r = bridge.execute_from_marketplace_action("req-ma-6", TENANT, TARGET)
        assert r["sandbox"] == "sandboxed"

    def test_default_risk_low(self, bridge):
        r = bridge.execute_from_marketplace_action("req-ma-7", TENANT, TARGET)
        assert r["risk_level"] == "low"

    def test_custom_kind_override(self, bridge):
        r = bridge.execute_from_marketplace_action(
            "req-ma-8", TENANT, TARGET,
            kind=ExecutionKind.TOOL,
        )
        assert r["status"] == "pending"


# ---------------------------------------------------------------------------
# TestExecuteFromOperatorWorkspace
# ---------------------------------------------------------------------------

class TestExecuteFromOperatorWorkspace:
    """8 tests for execute_from_operator_workspace bridge method."""

    def test_returns_dict(self, bridge):
        r = bridge.execute_from_operator_workspace("req-ow-1", TENANT, TARGET)
        assert isinstance(r, dict)

    def test_has_eight_keys(self, bridge):
        r = bridge.execute_from_operator_workspace("req-ow-2", TENANT, TARGET)
        assert len(r) == 8

    def test_source_type(self, bridge):
        r = bridge.execute_from_operator_workspace("req-ow-3", TENANT, TARGET)
        assert r["source_type"] == "operator_workspace"

    def test_default_workspace_ref(self, bridge):
        r = bridge.execute_from_operator_workspace("req-ow-4", TENANT, TARGET)
        assert r["workspace_ref"] == "none"

    def test_custom_workspace_ref(self, bridge):
        r = bridge.execute_from_operator_workspace("req-ow-5", TENANT, TARGET, workspace_ref="ws-7")
        assert r["workspace_ref"] == "ws-7"

    def test_default_sandbox_sandboxed(self, bridge):
        r = bridge.execute_from_operator_workspace("req-ow-6", TENANT, TARGET)
        assert r["sandbox"] == "sandboxed"

    def test_default_risk_low(self, bridge):
        r = bridge.execute_from_operator_workspace("req-ow-7", TENANT, TARGET)
        assert r["risk_level"] == "low"

    def test_request_id_round_trips(self, bridge):
        r = bridge.execute_from_operator_workspace("req-ow-8", TENANT, TARGET)
        assert r["request_id"] == "req-ow-8"


# ---------------------------------------------------------------------------
# TestAttachExecutionStateToMemoryMesh
# ---------------------------------------------------------------------------

class TestAttachExecutionStateToMemoryMesh:
    """9 tests for attach_execution_state_to_memory_mesh."""

    def test_returns_memory_record(self, bridge):
        rec = bridge.attach_execution_state_to_memory_mesh("scope-mm-1")
        assert isinstance(rec, MemoryRecord)

    def test_memory_id_is_nonempty(self, bridge):
        rec = bridge.attach_execution_state_to_memory_mesh("scope-mm-2")
        assert len(rec.memory_id) > 0

    def test_scope_ref_id_preserved(self, bridge):
        rec = bridge.attach_execution_state_to_memory_mesh("scope-mm-3")
        assert rec.scope_ref_id == "scope-mm-3"

    def test_tags_contain_required(self, bridge):
        rec = bridge.attach_execution_state_to_memory_mesh("scope-mm-4")
        assert "external_execution" in rec.tags
        assert "tool_execution" in rec.tags
        assert "agent_execution" in rec.tags

    def test_content_has_seven_keys(self, bridge):
        rec = bridge.attach_execution_state_to_memory_mesh("scope-mm-5")
        expected_keys = {
            "total_targets", "total_requests", "total_receipts",
            "total_results", "total_failures", "total_traces",
            "total_violations",
        }
        assert set(rec.content.keys()) == expected_keys

    def test_content_targets_count(self, bridge_with_engines):
        b, _, ee, _ = bridge_with_engines
        rec = b.attach_execution_state_to_memory_mesh("scope-mm-6")
        assert rec.content["total_targets"] == ee.target_count

    def test_memory_is_added_to_mesh(self, bridge_with_engines):
        b, _, _, mm = bridge_with_engines
        before = mm.memory_count
        b.attach_execution_state_to_memory_mesh("scope-mm-7")
        assert mm.memory_count == before + 1

    def test_content_reflects_requests(self, bridge_with_engines):
        b, _, ee, _ = bridge_with_engines
        b.execute_from_service_request("req-mm-8a", TENANT, TARGET)
        rec = b.attach_execution_state_to_memory_mesh("scope-mm-8")
        assert rec.content["total_requests"] == ee.request_count

    def test_title_is_bounded(self, bridge):
        rec = bridge.attach_execution_state_to_memory_mesh("scope-mm-9")
        assert rec.title == "External execution state"
        assert "scope-mm-9" not in rec.title
        assert rec.scope_ref_id == "scope-mm-9"


# ---------------------------------------------------------------------------
# TestAttachExecutionStateToGraph
# ---------------------------------------------------------------------------

class TestAttachExecutionStateToGraph:
    """6 tests for attach_execution_state_to_graph."""

    def test_returns_dict(self, bridge):
        g = bridge.attach_execution_state_to_graph("scope-g-1")
        assert isinstance(g, dict)

    def test_has_eight_keys(self, bridge):
        g = bridge.attach_execution_state_to_graph("scope-g-2")
        assert len(g) == 8

    def test_scope_ref_id_preserved(self, bridge):
        g = bridge.attach_execution_state_to_graph("scope-g-3")
        assert g["scope_ref_id"] == "scope-g-3"

    def test_all_count_keys_present(self, bridge):
        g = bridge.attach_execution_state_to_graph("scope-g-4")
        for key in (
            "total_targets", "total_requests", "total_receipts",
            "total_results", "total_failures", "total_traces",
            "total_violations",
        ):
            assert key in g

    def test_counts_reflect_engine_state(self, bridge_with_engines):
        b, _, ee, _ = bridge_with_engines
        b.execute_from_service_request("req-g-5a", TENANT, TARGET)
        g = b.attach_execution_state_to_graph("scope-g-5")
        assert g["total_targets"] == ee.target_count
        assert g["total_requests"] == ee.request_count

    def test_zero_counts_when_fresh(self, bridge_with_engines):
        b, _, _, _ = bridge_with_engines
        g = b.attach_execution_state_to_graph("scope-g-6")
        # target already registered, so total_targets >= 1
        assert g["total_targets"] >= 1
        assert g["total_receipts"] == 0
        assert g["total_failures"] == 0
        assert g["total_results"] == 0
        assert g["total_traces"] == 0
        assert g["total_violations"] == 0


# ---------------------------------------------------------------------------
# TestEventEmission + TestGoldenPath
# ---------------------------------------------------------------------------

class TestEventEmission:
    """Tests verifying events are emitted by bridge methods."""

    def test_service_request_emits_events(self, bridge_with_engines):
        b, es, _, _ = bridge_with_engines
        before = es.event_count
        b.execute_from_service_request("req-ev-1", TENANT, TARGET)
        assert es.event_count > before

    def test_orchestration_step_emits_events(self, bridge_with_engines):
        b, es, _, _ = bridge_with_engines
        before = es.event_count
        b.execute_from_orchestration_step("req-ev-2", TENANT, TARGET)
        assert es.event_count > before

    def test_remediation_emits_events(self, bridge_with_engines):
        b, es, _, _ = bridge_with_engines
        before = es.event_count
        b.execute_from_remediation("req-ev-3", TENANT, TARGET)
        assert es.event_count > before

    def test_procurement_emits_events(self, bridge_with_engines):
        b, es, _, _ = bridge_with_engines
        before = es.event_count
        b.execute_from_procurement_need("req-ev-4", TENANT, TARGET)
        assert es.event_count > before

    def test_marketplace_emits_events(self, bridge_with_engines):
        b, es, _, _ = bridge_with_engines
        before = es.event_count
        b.execute_from_marketplace_action("req-ev-5", TENANT, TARGET)
        assert es.event_count > before

    def test_operator_workspace_emits_events(self, bridge_with_engines):
        b, es, _, _ = bridge_with_engines
        before = es.event_count
        b.execute_from_operator_workspace("req-ev-6", TENANT, TARGET)
        assert es.event_count > before

    def test_memory_mesh_attach_emits_event(self, bridge_with_engines):
        b, es, _, _ = bridge_with_engines
        before = es.event_count
        b.attach_execution_state_to_memory_mesh("scope-ev-7")
        assert es.event_count > before


class TestGoldenPath:
    """End-to-end golden path: call all methods, verify cumulative state."""

    def test_full_golden_path(self, bridge_with_engines):
        b, es, ee, mm = bridge_with_engines
        initial_events = es.event_count

        # Call all 6 bridge methods
        r1 = b.execute_from_service_request("gp-1", TENANT, TARGET)
        r2 = b.execute_from_orchestration_step("gp-2", TENANT, TARGET)
        r3 = b.execute_from_remediation("gp-3", TENANT, TARGET)
        r4 = b.execute_from_procurement_need("gp-4", TENANT, TARGET)
        r5 = b.execute_from_marketplace_action("gp-5", TENANT, TARGET)
        r6 = b.execute_from_operator_workspace("gp-6", TENANT, TARGET)

        # All returned dicts with correct source_types
        assert r1["source_type"] == "service_request"
        assert r2["source_type"] == "orchestration_step"
        assert r3["source_type"] == "remediation"
        assert r4["source_type"] == "procurement_need"
        assert r5["source_type"] == "marketplace_action"
        assert r6["source_type"] == "operator_workspace"

        # Engine has 6 requests
        assert ee.request_count == 6

        # Memory mesh
        mem = b.attach_execution_state_to_memory_mesh("gp-scope")
        assert mem.content["total_requests"] == 6
        assert mem.content["total_targets"] == 1

        # Graph
        g = b.attach_execution_state_to_graph("gp-scope-g")
        assert g["total_requests"] == 6
        assert g["total_targets"] == 1

        # Events were emitted (at least 1 per bridge method + engine internal events)
        assert es.event_count > initial_events
