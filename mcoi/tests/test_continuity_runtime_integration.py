"""Comprehensive pytest tests for ContinuityRuntimeIntegration bridge.

Tests cover constructor validation, disruption creation helpers,
binding helpers, memory mesh attachment, graph attachment, and
event emission invariants.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.continuity_runtime_integration import ContinuityRuntimeIntegration
from mcoi_runtime.core.continuity_runtime import ContinuityRuntimeEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.continuity_runtime import ContinuityScope, DisruptionSeverity
from mcoi_runtime.contracts.memory_mesh import MemoryRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engines():
    es = EventSpineEngine()
    ce = ContinuityRuntimeEngine(es)
    mm = MemoryMeshEngine()
    return ce, es, mm


@pytest.fixture
def integration(engines):
    ce, es, mm = engines
    return ContinuityRuntimeIntegration(ce, es, mm)


def _register_plan(ce: ContinuityRuntimeEngine, plan_id: str = "plan-1",
                   name: str = "DR Plan", tenant_id: str = "t-1"):
    """Helper to register a continuity plan on the engine."""
    return ce.register_continuity_plan(plan_id, name, tenant_id)


# ===================================================================
# 1. Constructor validation
# ===================================================================


class TestConstructorValidation:
    """Validate that the constructor type-checks all three arguments."""

    def test_valid_construction(self, engines):
        ce, es, mm = engines
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        assert bridge is not None

    def test_wrong_continuity_engine_type_raises(self, engines):
        _, es, mm = engines
        with pytest.raises(RuntimeCoreInvariantError, match="continuity_engine"):
            ContinuityRuntimeIntegration("not-an-engine", es, mm)

    def test_wrong_event_spine_type_raises(self, engines):
        ce, _, mm = engines
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            ContinuityRuntimeIntegration(ce, "not-a-spine", mm)

    def test_wrong_memory_engine_type_raises(self, engines):
        ce, es, _ = engines
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            ContinuityRuntimeIntegration(ce, es, "not-a-mesh")

    def test_none_continuity_engine_raises(self, engines):
        _, es, mm = engines
        with pytest.raises(RuntimeCoreInvariantError):
            ContinuityRuntimeIntegration(None, es, mm)

    def test_none_event_spine_raises(self, engines):
        ce, _, mm = engines
        with pytest.raises(RuntimeCoreInvariantError):
            ContinuityRuntimeIntegration(ce, None, mm)

    def test_none_memory_engine_raises(self, engines):
        ce, es, _ = engines
        with pytest.raises(RuntimeCoreInvariantError):
            ContinuityRuntimeIntegration(ce, es, None)

    def test_dict_as_continuity_engine_raises(self, engines):
        _, es, mm = engines
        with pytest.raises(RuntimeCoreInvariantError):
            ContinuityRuntimeIntegration({}, es, mm)


# ===================================================================
# 2. continuity_from_asset_failure
# ===================================================================


class TestContinuityFromAssetFailure:
    """Tests for recording disruptions from asset failures."""

    def test_returns_dict(self, integration):
        result = integration.continuity_from_asset_failure(
            "d-asset-1", "t-1", "asset-abc"
        )
        assert isinstance(result, dict)

    def test_contains_asset_ref(self, integration):
        result = integration.continuity_from_asset_failure(
            "d-asset-2", "t-1", "asset-xyz"
        )
        assert result["asset_ref"] == "asset-xyz"

    def test_scope_is_asset(self, integration):
        result = integration.continuity_from_asset_failure(
            "d-asset-3", "t-1", "asset-1"
        )
        assert result["scope"] == ContinuityScope.ASSET.value

    def test_source_type_is_asset_failure(self, integration):
        result = integration.continuity_from_asset_failure(
            "d-asset-4", "t-1", "asset-1"
        )
        assert result["source_type"] == "asset_failure"

    def test_default_severity_is_high(self, integration):
        result = integration.continuity_from_asset_failure(
            "d-asset-5", "t-1", "asset-1"
        )
        assert result["severity"] == DisruptionSeverity.HIGH.value

    def test_custom_severity(self, integration):
        result = integration.continuity_from_asset_failure(
            "d-asset-6", "t-1", "asset-1",
            severity=DisruptionSeverity.CRITICAL,
        )
        assert result["severity"] == DisruptionSeverity.CRITICAL.value

    def test_disruption_id_preserved(self, integration):
        result = integration.continuity_from_asset_failure(
            "d-asset-7", "t-1", "asset-1"
        )
        assert result["disruption_id"] == "d-asset-7"

    def test_tenant_id_preserved(self, integration):
        result = integration.continuity_from_asset_failure(
            "d-asset-8", "t-2", "asset-1"
        )
        assert result["tenant_id"] == "t-2"

    def test_duplicate_disruption_id_raises(self, integration):
        integration.continuity_from_asset_failure("d-dup", "t-1", "a-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            integration.continuity_from_asset_failure("d-dup", "t-1", "a-2")

    def test_emits_event(self, engines):
        ce, es, mm = engines
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        before = es.event_count
        bridge.continuity_from_asset_failure("d-evt-1", "t-1", "asset-1")
        # record_disruption emits 1 + integration emits 1 = 2 new events
        assert es.event_count > before


# ===================================================================
# 3. continuity_from_connector_failure
# ===================================================================


class TestContinuityFromConnectorFailure:
    """Tests for recording disruptions from connector failures."""

    def test_returns_dict(self, integration):
        result = integration.continuity_from_connector_failure(
            "d-conn-1", "t-1", "conn-abc"
        )
        assert isinstance(result, dict)

    def test_contains_connector_ref(self, integration):
        result = integration.continuity_from_connector_failure(
            "d-conn-2", "t-1", "conn-xyz"
        )
        assert result["connector_ref"] == "conn-xyz"

    def test_scope_is_connector(self, integration):
        result = integration.continuity_from_connector_failure(
            "d-conn-3", "t-1", "conn-1"
        )
        assert result["scope"] == ContinuityScope.CONNECTOR.value

    def test_source_type_is_connector_failure(self, integration):
        result = integration.continuity_from_connector_failure(
            "d-conn-4", "t-1", "conn-1"
        )
        assert result["source_type"] == "connector_failure"

    def test_default_severity_is_high(self, integration):
        result = integration.continuity_from_connector_failure(
            "d-conn-5", "t-1", "conn-1"
        )
        assert result["severity"] == DisruptionSeverity.HIGH.value

    def test_custom_severity_low(self, integration):
        result = integration.continuity_from_connector_failure(
            "d-conn-6", "t-1", "conn-1",
            severity=DisruptionSeverity.LOW,
        )
        assert result["severity"] == DisruptionSeverity.LOW.value

    def test_emits_event(self, engines):
        ce, es, mm = engines
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        before = es.event_count
        bridge.continuity_from_connector_failure("d-conn-evt", "t-1", "conn-1")
        assert es.event_count > before


# ===================================================================
# 4. continuity_from_environment_degradation
# ===================================================================


class TestContinuityFromEnvironmentDegradation:
    """Tests for recording disruptions from environment degradation."""

    def test_returns_dict(self, integration):
        result = integration.continuity_from_environment_degradation(
            "d-env-1", "t-1", "env-prod"
        )
        assert isinstance(result, dict)

    def test_contains_environment_ref(self, integration):
        result = integration.continuity_from_environment_degradation(
            "d-env-2", "t-1", "env-staging"
        )
        assert result["environment_ref"] == "env-staging"

    def test_scope_is_environment(self, integration):
        result = integration.continuity_from_environment_degradation(
            "d-env-3", "t-1", "env-1"
        )
        assert result["scope"] == ContinuityScope.ENVIRONMENT.value

    def test_source_type_is_environment_degradation(self, integration):
        result = integration.continuity_from_environment_degradation(
            "d-env-4", "t-1", "env-1"
        )
        assert result["source_type"] == "environment_degradation"

    def test_default_severity_is_medium(self, integration):
        result = integration.continuity_from_environment_degradation(
            "d-env-5", "t-1", "env-1"
        )
        assert result["severity"] == DisruptionSeverity.MEDIUM.value

    def test_custom_severity_critical(self, integration):
        result = integration.continuity_from_environment_degradation(
            "d-env-6", "t-1", "env-1",
            severity=DisruptionSeverity.CRITICAL,
        )
        assert result["severity"] == DisruptionSeverity.CRITICAL.value

    def test_emits_event(self, engines):
        ce, es, mm = engines
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        before = es.event_count
        bridge.continuity_from_environment_degradation("d-env-evt", "t-1", "env-1")
        assert es.event_count > before

    def test_custom_description(self, integration):
        result = integration.continuity_from_environment_degradation(
            "d-env-7", "t-1", "env-1",
            description="Network partition detected",
        )
        assert result["disruption_id"] == "d-env-7"


# ===================================================================
# 5. continuity_from_fault_campaign
# ===================================================================


class TestContinuityFromFaultCampaign:
    """Tests for recording disruptions from fault campaigns."""

    def test_returns_dict(self, integration):
        result = integration.continuity_from_fault_campaign(
            "d-fc-1", "t-1", "campaign-chaos"
        )
        assert isinstance(result, dict)

    def test_contains_campaign_ref(self, integration):
        result = integration.continuity_from_fault_campaign(
            "d-fc-2", "t-1", "campaign-injection"
        )
        assert result["campaign_ref"] == "campaign-injection"

    def test_scope_is_service(self, integration):
        result = integration.continuity_from_fault_campaign(
            "d-fc-3", "t-1", "campaign-1"
        )
        assert result["scope"] == ContinuityScope.SERVICE.value

    def test_source_type_is_fault_campaign(self, integration):
        result = integration.continuity_from_fault_campaign(
            "d-fc-4", "t-1", "campaign-1"
        )
        assert result["source_type"] == "fault_campaign"

    def test_default_severity_is_medium(self, integration):
        result = integration.continuity_from_fault_campaign(
            "d-fc-5", "t-1", "campaign-1"
        )
        assert result["severity"] == DisruptionSeverity.MEDIUM.value

    def test_custom_severity_high(self, integration):
        result = integration.continuity_from_fault_campaign(
            "d-fc-6", "t-1", "campaign-1",
            severity=DisruptionSeverity.HIGH,
        )
        assert result["severity"] == DisruptionSeverity.HIGH.value

    def test_emits_event(self, engines):
        ce, es, mm = engines
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        before = es.event_count
        bridge.continuity_from_fault_campaign("d-fc-evt", "t-1", "campaign-1")
        assert es.event_count > before


# ===================================================================
# 6. bind_continuity_to_service_request
# ===================================================================


class TestBindContinuityToServiceRequest:
    """Tests for binding a continuity plan to a service request."""

    def test_returns_dict(self, engines):
        ce, es, mm = engines
        _register_plan(ce, "plan-bind-sr-1")
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        result = bridge.bind_continuity_to_service_request("plan-bind-sr-1", "sr-1")
        assert isinstance(result, dict)

    def test_contains_service_request_ref(self, engines):
        ce, es, mm = engines
        _register_plan(ce, "plan-bind-sr-2")
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        result = bridge.bind_continuity_to_service_request("plan-bind-sr-2", "sr-abc")
        assert result["service_request_ref"] == "sr-abc"

    def test_binding_type_is_service_request(self, engines):
        ce, es, mm = engines
        _register_plan(ce, "plan-bind-sr-3")
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        result = bridge.bind_continuity_to_service_request("plan-bind-sr-3", "sr-1")
        assert result["binding_type"] == "service_request"

    def test_plan_id_preserved(self, engines):
        ce, es, mm = engines
        _register_plan(ce, "plan-bind-sr-4")
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        result = bridge.bind_continuity_to_service_request("plan-bind-sr-4", "sr-1")
        assert result["plan_id"] == "plan-bind-sr-4"

    def test_plan_name_present(self, engines):
        ce, es, mm = engines
        _register_plan(ce, "plan-bind-sr-5", name="My DR Plan")
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        result = bridge.bind_continuity_to_service_request("plan-bind-sr-5", "sr-1")
        assert result["name"] == "My DR Plan"

    def test_status_present(self, engines):
        ce, es, mm = engines
        _register_plan(ce, "plan-bind-sr-6")
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        result = bridge.bind_continuity_to_service_request("plan-bind-sr-6", "sr-1")
        assert "status" in result

    def test_unknown_plan_raises(self, integration):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown plan_id"):
            integration.bind_continuity_to_service_request("nonexistent", "sr-1")

    def test_emits_event(self, engines):
        ce, es, mm = engines
        _register_plan(ce, "plan-bind-sr-evt")
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        before = es.event_count
        bridge.bind_continuity_to_service_request("plan-bind-sr-evt", "sr-1")
        assert es.event_count > before


# ===================================================================
# 7. bind_continuity_to_program
# ===================================================================


class TestBindContinuityToProgram:
    """Tests for binding a continuity plan to a program."""

    def test_returns_dict(self, engines):
        ce, es, mm = engines
        _register_plan(ce, "plan-bind-pg-1")
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        result = bridge.bind_continuity_to_program("plan-bind-pg-1", "prog-1")
        assert isinstance(result, dict)

    def test_contains_program_ref(self, engines):
        ce, es, mm = engines
        _register_plan(ce, "plan-bind-pg-2")
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        result = bridge.bind_continuity_to_program("plan-bind-pg-2", "prog-abc")
        assert result["program_ref"] == "prog-abc"

    def test_binding_type_is_program(self, engines):
        ce, es, mm = engines
        _register_plan(ce, "plan-bind-pg-3")
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        result = bridge.bind_continuity_to_program("plan-bind-pg-3", "prog-1")
        assert result["binding_type"] == "program"

    def test_plan_id_preserved(self, engines):
        ce, es, mm = engines
        _register_plan(ce, "plan-bind-pg-4")
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        result = bridge.bind_continuity_to_program("plan-bind-pg-4", "prog-1")
        assert result["plan_id"] == "plan-bind-pg-4"

    def test_unknown_plan_raises(self, integration):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown plan_id"):
            integration.bind_continuity_to_program("nonexistent", "prog-1")

    def test_emits_event(self, engines):
        ce, es, mm = engines
        _register_plan(ce, "plan-bind-pg-evt")
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        before = es.event_count
        bridge.bind_continuity_to_program("plan-bind-pg-evt", "prog-1")
        assert es.event_count > before


# ===================================================================
# 8. attach_continuity_to_memory_mesh
# ===================================================================


class TestAttachContinuityToMemoryMesh:
    """Tests for persisting continuity state to memory mesh."""

    def test_returns_memory_record(self, integration):
        result = integration.attach_continuity_to_memory_mesh("scope-mm-1")
        assert isinstance(result, MemoryRecord)

    def test_tags_contain_continuity(self, integration):
        result = integration.attach_continuity_to_memory_mesh("scope-mm-2")
        assert "continuity" in result.tags

    def test_tags_contain_disaster_recovery(self, integration):
        result = integration.attach_continuity_to_memory_mesh("scope-mm-3")
        assert "disaster_recovery" in result.tags

    def test_tags_contain_failover(self, integration):
        result = integration.attach_continuity_to_memory_mesh("scope-mm-4")
        assert "failover" in result.tags

    def test_tags_are_exactly_three(self, integration):
        result = integration.attach_continuity_to_memory_mesh("scope-mm-5")
        assert len(result.tags) == 3

    def test_scope_ref_id_preserved(self, integration):
        result = integration.attach_continuity_to_memory_mesh("scope-mm-6")
        assert result.scope_ref_id == "scope-mm-6"

    def test_content_has_total_plans(self, integration):
        result = integration.attach_continuity_to_memory_mesh("scope-mm-7")
        assert "total_plans" in result.content

    def test_content_has_total_disruptions(self, integration):
        result = integration.attach_continuity_to_memory_mesh("scope-mm-8")
        assert "total_disruptions" in result.content

    def test_content_has_total_failovers(self, integration):
        result = integration.attach_continuity_to_memory_mesh("scope-mm-9")
        assert "total_failovers" in result.content

    def test_content_has_total_recovery_plans(self, integration):
        result = integration.attach_continuity_to_memory_mesh("scope-mm-10")
        assert "total_recovery_plans" in result.content

    def test_content_has_total_executions(self, integration):
        result = integration.attach_continuity_to_memory_mesh("scope-mm-11")
        assert "total_executions" in result.content

    def test_content_has_total_objectives(self, integration):
        result = integration.attach_continuity_to_memory_mesh("scope-mm-12")
        assert "total_objectives" in result.content

    def test_content_has_total_verifications(self, integration):
        result = integration.attach_continuity_to_memory_mesh("scope-mm-13")
        assert "total_verifications" in result.content

    def test_content_has_total_violations(self, integration):
        result = integration.attach_continuity_to_memory_mesh("scope-mm-14")
        assert "total_violations" in result.content

    def test_counts_match_engine_zero_state(self, engines):
        ce, es, mm = engines
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        result = bridge.attach_continuity_to_memory_mesh("scope-zero")
        assert result.content["total_plans"] == 0
        assert result.content["total_disruptions"] == 0
        assert result.content["total_failovers"] == 0

    def test_counts_reflect_registered_plan(self, engines):
        ce, es, mm = engines
        _register_plan(ce, "plan-mm-count")
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        result = bridge.attach_continuity_to_memory_mesh("scope-count")
        assert result.content["total_plans"] == 1

    def test_counts_reflect_disruption(self, engines):
        ce, es, mm = engines
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        bridge.continuity_from_asset_failure("d-mm-c", "t-1", "asset-1")
        result = bridge.attach_continuity_to_memory_mesh("scope-d-count")
        assert result.content["total_disruptions"] == 1

    def test_duplicate_scope_ref_raises(self, integration):
        integration.attach_continuity_to_memory_mesh("scope-dup")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            integration.attach_continuity_to_memory_mesh("scope-dup")

    def test_memory_engine_count_increases(self, engines):
        ce, es, mm = engines
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        before = mm.memory_count
        bridge.attach_continuity_to_memory_mesh("scope-mc")
        assert mm.memory_count == before + 1

    def test_emits_event(self, engines):
        ce, es, mm = engines
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        before = es.event_count
        bridge.attach_continuity_to_memory_mesh("scope-evt")
        assert es.event_count > before

    def test_title_is_bounded(self, integration):
        result = integration.attach_continuity_to_memory_mesh("scope-title-check")
        assert result.title == "Continuity state"
        assert "scope-title-check" not in result.title
        assert result.scope_ref_id == "scope-title-check"

    def test_confidence_is_one(self, integration):
        result = integration.attach_continuity_to_memory_mesh("scope-conf")
        assert result.confidence == 1.0


# ===================================================================
# 9. attach_continuity_to_graph
# ===================================================================


class TestAttachContinuityToGraph:
    """Tests for returning continuity state for the operational graph."""

    def test_returns_dict(self, integration):
        result = integration.attach_continuity_to_graph("scope-g-1")
        assert isinstance(result, dict)

    def test_contains_scope_ref_id(self, integration):
        result = integration.attach_continuity_to_graph("scope-g-2")
        assert result["scope_ref_id"] == "scope-g-2"

    def test_contains_total_plans(self, integration):
        result = integration.attach_continuity_to_graph("scope-g-3")
        assert "total_plans" in result

    def test_contains_total_recovery_plans(self, integration):
        result = integration.attach_continuity_to_graph("scope-g-4")
        assert "total_recovery_plans" in result

    def test_contains_total_disruptions(self, integration):
        result = integration.attach_continuity_to_graph("scope-g-5")
        assert "total_disruptions" in result

    def test_contains_total_failovers(self, integration):
        result = integration.attach_continuity_to_graph("scope-g-6")
        assert "total_failovers" in result

    def test_contains_total_executions(self, integration):
        result = integration.attach_continuity_to_graph("scope-g-7")
        assert "total_executions" in result

    def test_contains_total_objectives(self, integration):
        result = integration.attach_continuity_to_graph("scope-g-8")
        assert "total_objectives" in result

    def test_contains_total_verifications(self, integration):
        result = integration.attach_continuity_to_graph("scope-g-9")
        assert "total_verifications" in result

    def test_contains_total_violations(self, integration):
        result = integration.attach_continuity_to_graph("scope-g-10")
        assert "total_violations" in result

    def test_zero_counts_on_empty_engine(self, integration):
        result = integration.attach_continuity_to_graph("scope-g-zero")
        assert result["total_plans"] == 0
        assert result["total_disruptions"] == 0
        assert result["total_failovers"] == 0
        assert result["total_executions"] == 0

    def test_counts_reflect_plan(self, engines):
        ce, es, mm = engines
        _register_plan(ce, "plan-graph-count")
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        result = bridge.attach_continuity_to_graph("scope-g-count")
        assert result["total_plans"] == 1

    def test_counts_reflect_disruption(self, engines):
        ce, es, mm = engines
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        bridge.continuity_from_connector_failure("d-graph-c", "t-1", "conn-1")
        result = bridge.attach_continuity_to_graph("scope-g-d")
        assert result["total_disruptions"] == 1


# ===================================================================
# 10. Event emission — cross-cutting
# ===================================================================


class TestEventEmission:
    """Verify that every public method emits at least one event."""

    def test_asset_failure_increases_event_count(self, engines):
        ce, es, mm = engines
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        before = es.event_count
        bridge.continuity_from_asset_failure("d-ee-1", "t-1", "a-1")
        assert es.event_count >= before + 2  # record_disruption + integration emit

    def test_connector_failure_increases_event_count(self, engines):
        ce, es, mm = engines
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        before = es.event_count
        bridge.continuity_from_connector_failure("d-ee-2", "t-1", "c-1")
        assert es.event_count >= before + 2

    def test_environment_degradation_increases_event_count(self, engines):
        ce, es, mm = engines
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        before = es.event_count
        bridge.continuity_from_environment_degradation("d-ee-3", "t-1", "e-1")
        assert es.event_count >= before + 2

    def test_fault_campaign_increases_event_count(self, engines):
        ce, es, mm = engines
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        before = es.event_count
        bridge.continuity_from_fault_campaign("d-ee-4", "t-1", "fc-1")
        assert es.event_count >= before + 2

    def test_bind_service_request_increases_event_count(self, engines):
        ce, es, mm = engines
        _register_plan(ce, "plan-ee-sr")
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        before = es.event_count
        bridge.bind_continuity_to_service_request("plan-ee-sr", "sr-1")
        assert es.event_count >= before + 1

    def test_bind_program_increases_event_count(self, engines):
        ce, es, mm = engines
        _register_plan(ce, "plan-ee-pg")
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        before = es.event_count
        bridge.bind_continuity_to_program("plan-ee-pg", "prog-1")
        assert es.event_count >= before + 1

    def test_memory_mesh_attach_increases_event_count(self, engines):
        ce, es, mm = engines
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        before = es.event_count
        bridge.attach_continuity_to_memory_mesh("scope-ee-mm")
        assert es.event_count >= before + 1

    def test_multiple_operations_accumulate_events(self, engines):
        ce, es, mm = engines
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        before = es.event_count
        bridge.continuity_from_asset_failure("d-multi-1", "t-1", "a-1")
        bridge.continuity_from_connector_failure("d-multi-2", "t-1", "c-1")
        bridge.continuity_from_environment_degradation("d-multi-3", "t-1", "e-1")
        bridge.continuity_from_fault_campaign("d-multi-4", "t-1", "fc-1")
        # Each disruption method: 1 engine emit + 1 integration emit = 2; 4 methods = 8
        assert es.event_count >= before + 8


# ===================================================================
# 11. Additional edge-case and integration tests
# ===================================================================


class TestEdgeCases:
    """Miscellaneous edge-case and integration scenarios."""

    def test_graph_does_not_emit_event(self, engines):
        """attach_continuity_to_graph is a pure read -- no event emitted."""
        ce, es, mm = engines
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        before = es.event_count
        bridge.attach_continuity_to_graph("scope-no-evt")
        assert es.event_count == before

    def test_graph_can_be_called_repeatedly_same_scope(self, integration):
        r1 = integration.attach_continuity_to_graph("scope-repeat")
        r2 = integration.attach_continuity_to_graph("scope-repeat")
        assert r1 == r2

    def test_all_severity_levels_accepted_for_asset_failure(self, engines):
        ce, es, mm = engines
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        for i, sev in enumerate(DisruptionSeverity):
            result = bridge.continuity_from_asset_failure(
                f"d-sev-{i}", "t-1", "a-1", severity=sev
            )
            assert result["severity"] == sev.value

    def test_description_kwarg_does_not_appear_in_result(self, integration):
        result = integration.continuity_from_asset_failure(
            "d-desc-1", "t-1", "a-1", description="custom desc"
        )
        # description is not part of the returned dict keys
        assert "description" not in result

    def test_memory_mesh_content_scope_ref_id_matches(self, integration):
        rec = integration.attach_continuity_to_memory_mesh("scope-content-check")
        assert rec.content["scope_ref_id"] == "scope-content-check"

    def test_bind_service_request_after_disruption(self, engines):
        ce, es, mm = engines
        _register_plan(ce, "plan-after-d")
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        bridge.continuity_from_asset_failure("d-before-bind", "t-1", "a-1")
        result = bridge.bind_continuity_to_service_request("plan-after-d", "sr-post")
        assert result["binding_type"] == "service_request"

    def test_bind_program_after_disruption(self, engines):
        ce, es, mm = engines
        _register_plan(ce, "plan-after-d-2")
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        bridge.continuity_from_connector_failure("d-before-bind-2", "t-1", "c-1")
        result = bridge.bind_continuity_to_program("plan-after-d-2", "prog-post")
        assert result["binding_type"] == "program"

    def test_graph_counts_after_multiple_disruptions(self, engines):
        ce, es, mm = engines
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        bridge.continuity_from_asset_failure("d-g-1", "t-1", "a-1")
        bridge.continuity_from_connector_failure("d-g-2", "t-1", "c-1")
        bridge.continuity_from_environment_degradation("d-g-3", "t-1", "e-1")
        result = bridge.attach_continuity_to_graph("scope-multi-d")
        assert result["total_disruptions"] == 3

    def test_memory_mesh_counts_after_plan_and_disruption(self, engines):
        ce, es, mm = engines
        _register_plan(ce, "plan-mm-pd")
        bridge = ContinuityRuntimeIntegration(ce, es, mm)
        bridge.continuity_from_fault_campaign("d-mm-pd", "t-1", "fc-1")
        rec = bridge.attach_continuity_to_memory_mesh("scope-pd")
        assert rec.content["total_plans"] == 1
        assert rec.content["total_disruptions"] == 1
