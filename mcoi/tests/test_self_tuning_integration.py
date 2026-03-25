"""Comprehensive tests for SelfTuningIntegration bridge.

Covers construction validation, all signal-based improvement methods,
memory mesh attachment, graph attachment, event emission, and end-to-end
integration workflows.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.self_tuning import (
    ImprovementRiskLevel,
    ImprovementStatus,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.self_tuning import SelfTuningEngine
from mcoi_runtime.core.self_tuning_integration import SelfTuningIntegration


# ===================================================================
# Fixtures
# ===================================================================

TENANT = "tenant-1"
TENANT2 = "tenant-2"


@pytest.fixture
def es():
    return EventSpineEngine()


@pytest.fixture
def mem():
    return MemoryMeshEngine()


@pytest.fixture
def tuning(es):
    return SelfTuningEngine(es)


@pytest.fixture
def integration(tuning, es, mem):
    return SelfTuningIntegration(tuning, es, mem)


# ===================================================================
# Construction
# ===================================================================


class TestConstruction:
    def test_valid_construction(self, tuning, es, mem):
        integ = SelfTuningIntegration(tuning, es, mem)
        assert integ is not None

    def test_invalid_tuning_engine(self, es, mem):
        with pytest.raises(RuntimeCoreInvariantError):
            SelfTuningIntegration("not-an-engine", es, mem)

    def test_invalid_event_spine(self, tuning, mem):
        with pytest.raises(RuntimeCoreInvariantError):
            SelfTuningIntegration(tuning, "not-an-es", mem)

    def test_invalid_memory_engine(self, tuning, es):
        with pytest.raises(RuntimeCoreInvariantError):
            SelfTuningIntegration(tuning, es, "not-a-mem")

    def test_none_tuning_engine(self, es, mem):
        with pytest.raises(RuntimeCoreInvariantError):
            SelfTuningIntegration(None, es, mem)

    def test_none_event_spine(self, tuning, mem):
        with pytest.raises(RuntimeCoreInvariantError):
            SelfTuningIntegration(tuning, None, mem)

    def test_none_memory_engine(self, tuning, es):
        with pytest.raises(RuntimeCoreInvariantError):
            SelfTuningIntegration(tuning, es, None)


# ===================================================================
# Observability improvement (LOW risk -> auto-applies)
# ===================================================================


class TestImprovementFromObservability:
    def test_returns_dict(self, integration):
        result = integration.improvement_from_observability(TENANT, "anom-1")
        assert isinstance(result, dict)

    def test_signal_and_proposal_created(self, integration, tuning):
        result = integration.improvement_from_observability(TENANT, "anom-1")
        assert tuning.signal_count == 1
        assert tuning.proposal_count == 1
        assert "signal_id" in result
        assert "proposal_id" in result

    def test_low_risk_auto_applies(self, integration):
        result = integration.improvement_from_observability(TENANT, "anom-1")
        assert result["status"] == "applied"
        assert result["risk_level"] == "low"

    def test_emits_event(self, integration, es):
        before = es.event_count
        integration.improvement_from_observability(TENANT, "anom-1")
        assert es.event_count > before

    def test_custom_description(self, integration, tuning):
        integration.improvement_from_observability(
            TENANT, "anom-1", description="Custom anomaly",
        )
        sig = tuning.get_signal(
            integration.improvement_from_observability(
                TENANT, "anom-2", description="Another one",
            )["signal_id"]
        )
        assert sig.description == "Another one"

    def test_result_keys(self, integration):
        result = integration.improvement_from_observability(TENANT, "anom-1")
        expected_keys = {"signal_id", "proposal_id", "source_type", "tenant_id",
                         "kind", "scope", "risk_level", "status"}
        assert expected_keys == set(result.keys())

    def test_source_type(self, integration):
        result = integration.improvement_from_observability(TENANT, "anom-1")
        assert result["source_type"] == "observability"


# ===================================================================
# Execution failures improvement (LOW risk -> auto-applies)
# ===================================================================


class TestImprovementFromExecutionFailures:
    def test_returns_dict(self, integration):
        result = integration.improvement_from_execution_failures(TENANT, "exec-1")
        assert isinstance(result, dict)

    def test_low_risk_auto_applies(self, integration):
        result = integration.improvement_from_execution_failures(TENANT, "exec-1")
        assert result["status"] == "applied"
        assert result["risk_level"] == "low"

    def test_kind_is_execution(self, integration):
        result = integration.improvement_from_execution_failures(TENANT, "exec-1")
        assert result["kind"] == "execution"

    def test_source_type(self, integration):
        result = integration.improvement_from_execution_failures(TENANT, "exec-1")
        assert result["source_type"] == "execution_failures"


# ===================================================================
# Policy simulation improvement (MEDIUM risk -> requires approval)
# ===================================================================


class TestImprovementFromPolicySimulation:
    def test_returns_dict(self, integration):
        result = integration.improvement_from_policy_simulation(TENANT, "sim-1")
        assert isinstance(result, dict)

    def test_medium_risk_stays_proposed(self, integration):
        result = integration.improvement_from_policy_simulation(TENANT, "sim-1")
        assert result["status"] == "proposed"
        assert result["risk_level"] == "medium"

    def test_kind_is_policy(self, integration):
        result = integration.improvement_from_policy_simulation(TENANT, "sim-1")
        assert result["kind"] == "policy"

    def test_scope_is_tenant(self, integration):
        result = integration.improvement_from_policy_simulation(TENANT, "sim-1")
        assert result["scope"] == "tenant"

    def test_source_type(self, integration):
        result = integration.improvement_from_policy_simulation(TENANT, "sim-1")
        assert result["source_type"] == "policy_simulation"


# ===================================================================
# Forecasting error improvement (LOW risk -> auto-applies)
# ===================================================================


class TestImprovementFromForecastingError:
    def test_returns_dict(self, integration):
        result = integration.improvement_from_forecasting_error(TENANT, "fc-1")
        assert isinstance(result, dict)

    def test_low_risk_auto_applies(self, integration):
        result = integration.improvement_from_forecasting_error(TENANT, "fc-1")
        assert result["status"] == "applied"
        assert result["risk_level"] == "low"

    def test_kind_is_parameter(self, integration):
        result = integration.improvement_from_forecasting_error(TENANT, "fc-1")
        assert result["kind"] == "parameter"

    def test_source_type(self, integration):
        result = integration.improvement_from_forecasting_error(TENANT, "fc-1")
        assert result["source_type"] == "forecasting_error"


# ===================================================================
# Workforce overload improvement (MEDIUM risk -> requires approval)
# ===================================================================


class TestImprovementFromWorkforceOverload:
    def test_returns_dict(self, integration):
        result = integration.improvement_from_workforce_overload(TENANT, "wf-1")
        assert isinstance(result, dict)

    def test_medium_risk_stays_proposed(self, integration):
        result = integration.improvement_from_workforce_overload(TENANT, "wf-1")
        assert result["status"] == "proposed"
        assert result["risk_level"] == "medium"

    def test_kind_is_staffing(self, integration):
        result = integration.improvement_from_workforce_overload(TENANT, "wf-1")
        assert result["kind"] == "staffing"

    def test_source_type(self, integration):
        result = integration.improvement_from_workforce_overload(TENANT, "wf-1")
        assert result["source_type"] == "workforce_overload"


# ===================================================================
# Financial loss improvement (MEDIUM risk -> requires approval)
# ===================================================================


class TestImprovementFromFinancialLoss:
    def test_returns_dict(self, integration):
        result = integration.improvement_from_financial_loss(TENANT, "fin-1")
        assert isinstance(result, dict)

    def test_medium_risk_stays_proposed(self, integration):
        result = integration.improvement_from_financial_loss(TENANT, "fin-1")
        assert result["status"] == "proposed"
        assert result["risk_level"] == "medium"

    def test_kind_is_threshold(self, integration):
        result = integration.improvement_from_financial_loss(TENANT, "fin-1")
        assert result["kind"] == "threshold"

    def test_source_type(self, integration):
        result = integration.improvement_from_financial_loss(TENANT, "fin-1")
        assert result["source_type"] == "financial_loss"


# ===================================================================
# Constitutional violation improvement (CRITICAL risk -> never auto-applies)
# ===================================================================


class TestImprovementFromConstitutionalViolation:
    def test_returns_dict(self, integration):
        result = integration.improvement_from_constitutional_violation(TENANT, "cv-1")
        assert isinstance(result, dict)

    def test_critical_risk_stays_proposed(self, integration):
        result = integration.improvement_from_constitutional_violation(TENANT, "cv-1")
        assert result["status"] == "proposed"
        assert result["risk_level"] == "critical"

    def test_scope_is_constitutional(self, integration):
        result = integration.improvement_from_constitutional_violation(TENANT, "cv-1")
        assert result["scope"] == "constitutional"

    def test_kind_is_policy(self, integration):
        result = integration.improvement_from_constitutional_violation(TENANT, "cv-1")
        assert result["kind"] == "policy"

    def test_source_type(self, integration):
        result = integration.improvement_from_constitutional_violation(TENANT, "cv-1")
        assert result["source_type"] == "constitutional_violation"


# ===================================================================
# Memory mesh attachment
# ===================================================================


class TestAttachToMemoryMesh:
    def test_attach_returns_memory_record(self, integration):
        integration.improvement_from_observability(TENANT, "anom-1")
        record = integration.attach_improvement_state_to_memory_mesh("scope-1")
        assert record is not None
        assert record.memory_id != ""

    def test_attach_adds_to_memory_engine(self, integration, mem):
        integration.improvement_from_observability(TENANT, "anom-1")
        before = mem.memory_count
        integration.attach_improvement_state_to_memory_mesh("scope-1")
        assert mem.memory_count == before + 1

    def test_attach_emits_event(self, integration, es):
        integration.improvement_from_observability(TENANT, "anom-1")
        before = es.event_count
        integration.attach_improvement_state_to_memory_mesh("scope-1")
        assert es.event_count > before

    def test_memory_record_content_has_counts(self, integration):
        integration.improvement_from_observability(TENANT, "anom-1")
        record = integration.attach_improvement_state_to_memory_mesh("scope-1")
        content = record.content
        assert "total_signals" in content
        assert "total_proposals" in content
        assert content["total_signals"] == 1
        assert content["total_proposals"] == 1

    def test_memory_record_tags(self, integration):
        integration.improvement_from_observability(TENANT, "anom-1")
        record = integration.attach_improvement_state_to_memory_mesh("scope-1")
        tags = record.tags
        assert "self_tuning" in tags


# ===================================================================
# Graph attachment
# ===================================================================


class TestAttachToGraph:
    def test_returns_dict(self, integration):
        result = integration.attach_improvement_state_to_graph("scope-1")
        assert isinstance(result, dict)

    def test_graph_has_counts(self, integration):
        integration.improvement_from_observability(TENANT, "anom-1")
        result = integration.attach_improvement_state_to_graph("scope-1")
        assert result["total_signals"] == 1
        assert result["total_proposals"] == 1
        assert result["scope_ref_id"] == "scope-1"

    def test_graph_has_all_keys(self, integration):
        result = integration.attach_improvement_state_to_graph("scope-1")
        expected_keys = {
            "scope_ref_id", "total_signals", "total_proposals",
            "total_adjustments", "total_policy_tunings",
            "total_execution_tunings", "total_decisions",
            "total_violations",
        }
        assert expected_keys == set(result.keys())

    def test_graph_empty_state(self, integration):
        result = integration.attach_improvement_state_to_graph("scope-1")
        assert result["total_signals"] == 0
        assert result["total_proposals"] == 0


# ===================================================================
# End-to-end integration
# ===================================================================


class TestEndToEnd:
    def test_observability_then_memory_attach(self, integration, mem):
        integration.improvement_from_observability(TENANT, "anom-1")
        record = integration.attach_improvement_state_to_memory_mesh("scope-1")
        assert mem.memory_count >= 1
        assert record.content["total_signals"] == 1

    def test_multiple_improvements_then_graph(self, integration):
        integration.improvement_from_observability(TENANT, "anom-1")
        integration.improvement_from_execution_failures(TENANT, "exec-1")
        integration.improvement_from_forecasting_error(TENANT, "fc-1")
        result = integration.attach_improvement_state_to_graph("scope-1")
        assert result["total_signals"] == 3
        assert result["total_proposals"] == 3

    def test_constitutional_then_approve_in_engine(self, integration, tuning):
        result = integration.improvement_from_constitutional_violation(TENANT, "cv-1")
        assert result["status"] == "proposed"
        prop_id = result["proposal_id"]
        approved = tuning.approve_improvement(prop_id)
        assert approved.status == ImprovementStatus.APPROVED

    def test_mixed_risk_levels(self, integration, tuning):
        r1 = integration.improvement_from_observability(TENANT, "anom-1")
        r2 = integration.improvement_from_workforce_overload(TENANT, "wf-1")
        r3 = integration.improvement_from_constitutional_violation(TENANT, "cv-1")
        assert r1["status"] == "applied"  # LOW
        assert r2["status"] == "proposed"  # MEDIUM
        assert r3["status"] == "proposed"  # CRITICAL
        assert tuning.signal_count == 3
        assert tuning.proposal_count == 3

    def test_sequential_ids_unique(self, integration):
        r1 = integration.improvement_from_observability(TENANT, "a-1")
        r2 = integration.improvement_from_observability(TENANT, "a-2")
        assert r1["signal_id"] != r2["signal_id"]
        assert r1["proposal_id"] != r2["proposal_id"]

    def test_multi_tenant_integration(self, integration, tuning):
        integration.improvement_from_observability(TENANT, "anom-1")
        integration.improvement_from_observability(TENANT2, "anom-2")
        assert tuning.signal_count == 2
        sigs_t1 = tuning.signals_for_tenant(TENANT)
        sigs_t2 = tuning.signals_for_tenant(TENANT2)
        assert len(sigs_t1) == 1
        assert len(sigs_t2) == 1

    def test_event_count_accumulates(self, integration, es):
        before = es.event_count
        integration.improvement_from_observability(TENANT, "anom-1")
        integration.improvement_from_execution_failures(TENANT, "exec-1")
        after = es.event_count
        assert after > before + 2  # multiple events per improvement
