"""Tests for the ChangeIntegration bridge.

Covers constructor validation, source-specific change creation,
subsystem application, memory mesh attachment, graph attachment,
event emission, return value schemas, memory determinism, and
golden end-to-end scenarios.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.change_integration import ChangeIntegration
from mcoi_runtime.core.change_runtime import ChangeRuntimeEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.change_runtime import (
    ChangeEvidenceKind,
    ChangeScope,
    ChangeStatus,
    ChangeType,
    RollbackDisposition,
    RolloutMode,
)
from mcoi_runtime.contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)


# =====================================================================
# Fixtures
# =====================================================================


@pytest.fixture
def event_spine():
    return EventSpineEngine()


@pytest.fixture
def memory_engine():
    return MemoryMeshEngine()


@pytest.fixture
def change_engine(event_spine):
    return ChangeRuntimeEngine(event_spine)


@pytest.fixture
def integration(change_engine, event_spine, memory_engine):
    return ChangeIntegration(change_engine, event_spine, memory_engine)


def _two_steps():
    """Helper returning a two-step list."""
    return [
        {"action": "step-a", "description": "first step"},
        {"action": "step-b", "description": "second step"},
    ]


def _three_steps():
    """Helper returning a three-step list."""
    return [
        {"action": "step-a", "description": "first"},
        {"action": "step-b", "description": "second"},
        {"action": "step-c", "description": "third"},
    ]


def _approve(change_engine, change_id):
    """Submit for approval then approve a change."""
    change_engine.submit_for_approval(change_id)
    change_engine.approve_change(
        f"{change_id}-approval", change_id, "test-approver"
    )


# =====================================================================
# 1. Constructor validation
# =====================================================================


class TestConstructorValidation:
    """ChangeIntegration requires correct types for all three engines."""

    def test_valid_construction(self, change_engine, event_spine, memory_engine):
        ci = ChangeIntegration(change_engine, event_spine, memory_engine)
        assert ci is not None

    def test_invalid_change_engine_none(self, event_spine, memory_engine):
        with pytest.raises(RuntimeCoreInvariantError, match="change_engine"):
            ChangeIntegration(None, event_spine, memory_engine)

    def test_invalid_change_engine_string(self, event_spine, memory_engine):
        with pytest.raises(RuntimeCoreInvariantError, match="change_engine"):
            ChangeIntegration("not-an-engine", event_spine, memory_engine)

    def test_invalid_change_engine_int(self, event_spine, memory_engine):
        with pytest.raises(RuntimeCoreInvariantError, match="change_engine"):
            ChangeIntegration(42, event_spine, memory_engine)

    def test_invalid_event_spine_none(self, change_engine, memory_engine):
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            ChangeIntegration(change_engine, None, memory_engine)

    def test_invalid_event_spine_string(self, change_engine, memory_engine):
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            ChangeIntegration(change_engine, "not-spine", memory_engine)

    def test_invalid_event_spine_dict(self, change_engine, memory_engine):
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            ChangeIntegration(change_engine, {}, memory_engine)

    def test_invalid_memory_engine_none(self, change_engine, event_spine):
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            ChangeIntegration(change_engine, event_spine, None)

    def test_invalid_memory_engine_string(self, change_engine, event_spine):
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            ChangeIntegration(change_engine, event_spine, "not-memory")

    def test_invalid_memory_engine_list(self, change_engine, event_spine):
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            ChangeIntegration(change_engine, event_spine, [])

    def test_all_wrong_types(self):
        with pytest.raises(RuntimeCoreInvariantError):
            ChangeIntegration("a", "b", "c")


# =====================================================================
# 2. change_from_optimization
# =====================================================================


class TestChangeFromOptimization:
    """Tests for creating changes from optimization recommendations."""

    def test_basic_no_steps(self, integration):
        result = integration.change_from_optimization(
            "opt-1", "Optimize latency", ChangeType.CONFIGURATION
        )
        assert result["change_id"] == "opt-1"
        assert result["source"] == "optimization"
        assert result["change_type"] == "configuration"
        assert result["rollout_mode"] == "canary"
        assert result["approval_required"] is True
        assert result["plan_id"] is None
        assert result["step_count"] == 0

    def test_with_steps(self, integration):
        result = integration.change_from_optimization(
            "opt-2", "Add fallback", ChangeType.FALLBACK_CHAIN,
            steps=_two_steps(),
        )
        assert result["plan_id"] == "opt-2-plan"
        assert result["step_count"] == 2

    def test_with_recommendation_id(self, integration):
        result = integration.change_from_optimization(
            "opt-3", "Rec change", ChangeType.ROUTING_RULE,
            recommendation_id="rec-42",
        )
        assert result["change_id"] == "opt-3"

    def test_approval_required_false(self, integration):
        result = integration.change_from_optimization(
            "opt-4", "Auto opt", ChangeType.BUDGET_THRESHOLD,
            approval_required=False,
        )
        assert result["approval_required"] is False

    def test_scope_portfolio(self, integration):
        result = integration.change_from_optimization(
            "opt-5", "Portfolio opt", ChangeType.CONNECTOR_PREFERENCE,
            scope=ChangeScope.PORTFOLIO, scope_ref_id="port-1",
        )
        assert result["change_id"] == "opt-5"

    def test_rollout_mode_immediate(self, integration):
        result = integration.change_from_optimization(
            "opt-6", "Immediate opt", ChangeType.SCHEDULE_POLICY,
            rollout_mode=RolloutMode.IMMEDIATE,
        )
        assert result["rollout_mode"] == "immediate"

    def test_rollout_mode_phased(self, integration):
        result = integration.change_from_optimization(
            "opt-7", "Phased opt", ChangeType.ESCALATION_TIMING,
            rollout_mode=RolloutMode.PHASED,
        )
        assert result["rollout_mode"] == "phased"

    def test_with_reason(self, integration):
        result = integration.change_from_optimization(
            "opt-8", "Reason opt", ChangeType.CONFIGURATION,
            reason="Latency improvement",
        )
        assert result["change_id"] == "opt-8"

    def test_three_steps(self, integration):
        result = integration.change_from_optimization(
            "opt-9", "Three step", ChangeType.DOMAIN_PACK_ACTIVATION,
            steps=_three_steps(),
        )
        assert result["step_count"] == 3

    def test_all_change_types(self, integration):
        for i, ct in enumerate(ChangeType):
            result = integration.change_from_optimization(
                f"opt-type-{i}", f"Type {ct.value}", ct,
            )
            assert result["change_type"] == ct.value

    def test_return_keys(self, integration):
        result = integration.change_from_optimization(
            "opt-keys", "Keys test", ChangeType.CONFIGURATION,
        )
        expected_keys = {
            "change_id", "source", "change_type", "rollout_mode",
            "approval_required", "plan_id", "step_count",
        }
        assert set(result.keys()) == expected_keys

    def test_emits_event(self, integration, event_spine):
        before = len(event_spine.list_events())
        integration.change_from_optimization(
            "opt-evt", "Event test", ChangeType.CONFIGURATION,
        )
        after = len(event_spine.list_events())
        assert after > before

    def test_duplicate_change_id_raises(self, integration):
        integration.change_from_optimization(
            "opt-dup", "First", ChangeType.CONFIGURATION,
        )
        with pytest.raises(RuntimeCoreInvariantError):
            integration.change_from_optimization(
                "opt-dup", "Second", ChangeType.CONFIGURATION,
            )


# =====================================================================
# 3. change_from_governance
# =====================================================================


class TestChangeFromGovernance:
    """Tests for creating changes from governance decisions."""

    def test_basic_no_steps(self, integration):
        result = integration.change_from_governance(
            "gov-1", "Policy change", ChangeType.CONFIGURATION,
        )
        assert result["change_id"] == "gov-1"
        assert result["source"] == "governance"
        assert result["approval_required"] is False
        assert result["rollout_mode"] == "immediate"
        assert result["plan_id"] is None
        assert result["step_count"] == 0

    def test_always_no_approval(self, integration):
        result = integration.change_from_governance(
            "gov-2", "Always no approval", ChangeType.BUDGET_THRESHOLD,
        )
        assert result["approval_required"] is False

    def test_with_steps(self, integration):
        result = integration.change_from_governance(
            "gov-3", "Stepped governance", ChangeType.ROUTING_RULE,
            steps=_two_steps(),
        )
        assert result["plan_id"] == "gov-3-plan"
        assert result["step_count"] == 2

    def test_scope_campaign(self, integration):
        result = integration.change_from_governance(
            "gov-4", "Campaign scope", ChangeType.CAMPAIGN_TEMPLATE_PATH,
            scope=ChangeScope.CAMPAIGN, scope_ref_id="camp-1",
        )
        assert result["change_id"] == "gov-4"

    def test_rollout_mode_canary(self, integration):
        result = integration.change_from_governance(
            "gov-5", "Canary governance", ChangeType.FALLBACK_CHAIN,
            rollout_mode=RolloutMode.CANARY,
        )
        assert result["rollout_mode"] == "canary"

    def test_rollout_mode_full(self, integration):
        result = integration.change_from_governance(
            "gov-6", "Full rollout", ChangeType.AVAILABILITY_POLICY,
            rollout_mode=RolloutMode.FULL,
        )
        assert result["rollout_mode"] == "full"

    def test_with_reason(self, integration):
        result = integration.change_from_governance(
            "gov-7", "Reason governance", ChangeType.CONFIGURATION,
            reason="Compliance requirement",
        )
        assert result["change_id"] == "gov-7"

    def test_emits_event(self, integration, event_spine):
        before = len(event_spine.list_events())
        integration.change_from_governance(
            "gov-evt", "Event test", ChangeType.CONFIGURATION,
        )
        after = len(event_spine.list_events())
        assert after > before

    def test_return_keys(self, integration):
        result = integration.change_from_governance(
            "gov-keys", "Keys test", ChangeType.CONFIGURATION,
        )
        expected_keys = {
            "change_id", "source", "change_type", "rollout_mode",
            "approval_required", "plan_id", "step_count",
        }
        assert set(result.keys()) == expected_keys

    def test_all_change_types(self, integration):
        for i, ct in enumerate(ChangeType):
            result = integration.change_from_governance(
                f"gov-type-{i}", f"Type {ct.value}", ct,
            )
            assert result["change_type"] == ct.value
            assert result["approval_required"] is False

    def test_three_steps(self, integration):
        result = integration.change_from_governance(
            "gov-3step", "Three step gov", ChangeType.SCHEDULE_POLICY,
            steps=_three_steps(),
        )
        assert result["step_count"] == 3

    def test_duplicate_raises(self, integration):
        integration.change_from_governance(
            "gov-dup", "First", ChangeType.CONFIGURATION,
        )
        with pytest.raises(RuntimeCoreInvariantError):
            integration.change_from_governance(
                "gov-dup", "Second", ChangeType.CONFIGURATION,
            )


# =====================================================================
# 4. change_from_fault_campaign
# =====================================================================


class TestChangeFromFaultCampaign:
    """Tests for creating changes from fault campaign results."""

    def test_basic_no_steps(self, integration):
        result = integration.change_from_fault_campaign(
            "fc-1", "Fault fix", ChangeType.CONFIGURATION,
        )
        assert result["change_id"] == "fc-1"
        assert result["source"] == "fault_campaign"
        assert result["approval_required"] is True
        assert result["rollout_mode"] == "canary"
        assert result["plan_id"] is None
        assert result["step_count"] == 0

    def test_with_steps(self, integration):
        result = integration.change_from_fault_campaign(
            "fc-2", "Stepped fault", ChangeType.ROUTING_RULE,
            steps=_two_steps(),
        )
        assert result["plan_id"] == "fc-2-plan"
        assert result["step_count"] == 2

    def test_no_approval_required(self, integration):
        result = integration.change_from_fault_campaign(
            "fc-3", "Auto fault fix", ChangeType.FALLBACK_CHAIN,
            approval_required=False,
        )
        assert result["approval_required"] is False

    def test_scope_connector(self, integration):
        result = integration.change_from_fault_campaign(
            "fc-4", "Connector fault", ChangeType.CONNECTOR_PREFERENCE,
            scope=ChangeScope.CONNECTOR, scope_ref_id="conn-1",
        )
        assert result["change_id"] == "fc-4"

    def test_rollout_mode_immediate(self, integration):
        result = integration.change_from_fault_campaign(
            "fc-5", "Immediate fault", ChangeType.CONFIGURATION,
            rollout_mode=RolloutMode.IMMEDIATE,
        )
        assert result["rollout_mode"] == "immediate"

    def test_rollout_mode_partial(self, integration):
        result = integration.change_from_fault_campaign(
            "fc-6", "Partial fault", ChangeType.BUDGET_THRESHOLD,
            rollout_mode=RolloutMode.PARTIAL,
        )
        assert result["rollout_mode"] == "partial"

    def test_with_reason(self, integration):
        result = integration.change_from_fault_campaign(
            "fc-7", "Reason fault", ChangeType.CONFIGURATION,
            reason="Detected failure mode X",
        )
        assert result["change_id"] == "fc-7"

    def test_emits_event(self, integration, event_spine):
        before = len(event_spine.list_events())
        integration.change_from_fault_campaign(
            "fc-evt", "Event test", ChangeType.CONFIGURATION,
        )
        after = len(event_spine.list_events())
        assert after > before

    def test_return_keys(self, integration):
        result = integration.change_from_fault_campaign(
            "fc-keys", "Keys test", ChangeType.CONFIGURATION,
        )
        expected_keys = {
            "change_id", "source", "change_type", "rollout_mode",
            "approval_required", "plan_id", "step_count",
        }
        assert set(result.keys()) == expected_keys

    def test_three_steps(self, integration):
        result = integration.change_from_fault_campaign(
            "fc-3step", "Three step fault", ChangeType.ESCALATION_TIMING,
            steps=_three_steps(),
        )
        assert result["step_count"] == 3

    def test_duplicate_raises(self, integration):
        integration.change_from_fault_campaign(
            "fc-dup", "First", ChangeType.CONFIGURATION,
        )
        with pytest.raises(RuntimeCoreInvariantError):
            integration.change_from_fault_campaign(
                "fc-dup", "Second", ChangeType.CONFIGURATION,
            )


# =====================================================================
# 5. apply_change_to_portfolio
# =====================================================================


class TestApplyChangeToPortfolio:
    """Tests for applying changes to the portfolio subsystem."""

    def test_executes_steps_with_approval(self, integration, change_engine):
        integration.change_from_optimization(
            "ap-1", "Portfolio opt", ChangeType.CONNECTOR_PREFERENCE,
            steps=_two_steps(),
        )
        _approve(change_engine, "ap-1")
        result = integration.apply_change_to_portfolio("ap-1", portfolio_ref_id="pf-100")
        assert result["change_id"] == "ap-1"
        assert result["target"] == "portfolio"
        assert result["portfolio_ref_id"] == "pf-100"
        assert result["steps_executed"] == 2

    def test_governance_no_approval_needed(self, integration):
        integration.change_from_governance(
            "ap-2", "Gov portfolio", ChangeType.CONFIGURATION,
            steps=_two_steps(),
        )
        result = integration.apply_change_to_portfolio("ap-2")
        assert result["steps_executed"] == 2

    def test_no_steps_zero_executed(self, integration):
        integration.change_from_governance(
            "ap-3", "No steps", ChangeType.CONFIGURATION,
        )
        result = integration.apply_change_to_portfolio("ap-3")
        assert result["steps_executed"] == 0

    def test_default_portfolio_ref(self, integration):
        integration.change_from_governance(
            "ap-4", "Def ref", ChangeType.CONFIGURATION,
        )
        result = integration.apply_change_to_portfolio("ap-4")
        assert result["portfolio_ref_id"] == ""

    def test_custom_action(self, integration):
        integration.change_from_governance(
            "ap-5", "Custom action", ChangeType.CONFIGURATION,
        )
        result = integration.apply_change_to_portfolio(
            "ap-5", action="delete"
        )
        assert result["change_id"] == "ap-5"

    def test_emits_event(self, integration, event_spine):
        integration.change_from_governance(
            "ap-evt", "Event test", ChangeType.CONFIGURATION,
        )
        before = len(event_spine.list_events())
        integration.apply_change_to_portfolio("ap-evt")
        after = len(event_spine.list_events())
        assert after > before

    def test_collects_evidence(self, integration, change_engine):
        integration.change_from_governance(
            "ap-ev", "Evidence", ChangeType.CONFIGURATION,
            steps=_two_steps(),
        )
        integration.apply_change_to_portfolio("ap-ev", portfolio_ref_id="pf-e")
        evidence = change_engine.get_evidence("ap-ev")
        assert len(evidence) >= 1
        assert evidence[-1].kind == ChangeEvidenceKind.LOG_ENTRY

    def test_return_keys(self, integration):
        integration.change_from_governance(
            "ap-rk", "Return keys", ChangeType.CONFIGURATION,
        )
        result = integration.apply_change_to_portfolio("ap-rk")
        expected = {"change_id", "target", "portfolio_ref_id", "steps_executed"}
        assert set(result.keys()) == expected


# =====================================================================
# 6. apply_change_to_availability
# =====================================================================


class TestApplyChangeToAvailability:
    """Tests for applying changes to the availability subsystem."""

    def test_executes_steps(self, integration, change_engine):
        integration.change_from_optimization(
            "av-1", "Availability opt", ChangeType.AVAILABILITY_POLICY,
            steps=_two_steps(),
        )
        _approve(change_engine, "av-1")
        result = integration.apply_change_to_availability("av-1", identity_ref_id="id-1")
        assert result["change_id"] == "av-1"
        assert result["target"] == "availability"
        assert result["identity_ref_id"] == "id-1"
        assert result["steps_executed"] == 2

    def test_governance_no_approval(self, integration):
        integration.change_from_governance(
            "av-2", "Gov avail", ChangeType.AVAILABILITY_POLICY,
            steps=_two_steps(),
        )
        result = integration.apply_change_to_availability("av-2")
        assert result["steps_executed"] == 2

    def test_no_steps(self, integration):
        integration.change_from_governance(
            "av-3", "No steps avail", ChangeType.CONFIGURATION,
        )
        result = integration.apply_change_to_availability("av-3")
        assert result["steps_executed"] == 0

    def test_default_identity_ref(self, integration):
        integration.change_from_governance(
            "av-4", "Def ref", ChangeType.CONFIGURATION,
        )
        result = integration.apply_change_to_availability("av-4")
        assert result["identity_ref_id"] == ""

    def test_emits_event(self, integration, event_spine):
        integration.change_from_governance(
            "av-evt", "Event", ChangeType.CONFIGURATION,
        )
        before = len(event_spine.list_events())
        integration.apply_change_to_availability("av-evt")
        after = len(event_spine.list_events())
        assert after > before

    def test_collects_evidence(self, integration, change_engine):
        integration.change_from_governance(
            "av-ev", "Evidence", ChangeType.CONFIGURATION,
            steps=_two_steps(),
        )
        integration.apply_change_to_availability("av-ev", identity_ref_id="id-e")
        evidence = change_engine.get_evidence("av-ev")
        assert len(evidence) >= 1

    def test_return_keys(self, integration):
        integration.change_from_governance(
            "av-rk", "Return keys", ChangeType.CONFIGURATION,
        )
        result = integration.apply_change_to_availability("av-rk")
        expected = {"change_id", "target", "identity_ref_id", "steps_executed"}
        assert set(result.keys()) == expected


# =====================================================================
# 7. apply_change_to_financials
# =====================================================================


class TestApplyChangeToFinancials:
    """Tests for applying changes to the financial subsystem."""

    def test_executes_steps(self, integration, change_engine):
        integration.change_from_optimization(
            "fin-1", "Financial opt", ChangeType.BUDGET_THRESHOLD,
            steps=_two_steps(),
        )
        _approve(change_engine, "fin-1")
        result = integration.apply_change_to_financials("fin-1", budget_ref_id="bud-1")
        assert result["change_id"] == "fin-1"
        assert result["target"] == "financials"
        assert result["budget_ref_id"] == "bud-1"
        assert result["steps_executed"] == 2

    def test_governance_no_approval(self, integration):
        integration.change_from_governance(
            "fin-2", "Gov fin", ChangeType.BUDGET_THRESHOLD,
            steps=_two_steps(),
        )
        result = integration.apply_change_to_financials("fin-2")
        assert result["steps_executed"] == 2

    def test_no_steps(self, integration):
        integration.change_from_governance(
            "fin-3", "No steps fin", ChangeType.CONFIGURATION,
        )
        result = integration.apply_change_to_financials("fin-3")
        assert result["steps_executed"] == 0

    def test_default_budget_ref(self, integration):
        integration.change_from_governance(
            "fin-4", "Def ref", ChangeType.CONFIGURATION,
        )
        result = integration.apply_change_to_financials("fin-4")
        assert result["budget_ref_id"] == ""

    def test_emits_event(self, integration, event_spine):
        integration.change_from_governance(
            "fin-evt", "Event", ChangeType.CONFIGURATION,
        )
        before = len(event_spine.list_events())
        integration.apply_change_to_financials("fin-evt")
        after = len(event_spine.list_events())
        assert after > before

    def test_collects_evidence(self, integration, change_engine):
        integration.change_from_governance(
            "fin-ev", "Evidence", ChangeType.CONFIGURATION,
            steps=_two_steps(),
        )
        integration.apply_change_to_financials("fin-ev", budget_ref_id="bud-e")
        evidence = change_engine.get_evidence("fin-ev")
        assert len(evidence) >= 1

    def test_return_keys(self, integration):
        integration.change_from_governance(
            "fin-rk", "Return keys", ChangeType.CONFIGURATION,
        )
        result = integration.apply_change_to_financials("fin-rk")
        expected = {"change_id", "target", "budget_ref_id", "steps_executed"}
        assert set(result.keys()) == expected


# =====================================================================
# 8. apply_change_to_connector_routing
# =====================================================================


class TestApplyChangeToConnectorRouting:
    """Tests for applying changes to the connector routing subsystem."""

    def test_executes_steps(self, integration, change_engine):
        integration.change_from_optimization(
            "cr-1", "Routing opt", ChangeType.ROUTING_RULE,
            steps=_two_steps(),
        )
        _approve(change_engine, "cr-1")
        result = integration.apply_change_to_connector_routing(
            "cr-1", connector_ref_id="conn-1"
        )
        assert result["change_id"] == "cr-1"
        assert result["target"] == "connector_routing"
        assert result["connector_ref_id"] == "conn-1"
        assert result["steps_executed"] == 2

    def test_governance_no_approval(self, integration):
        integration.change_from_governance(
            "cr-2", "Gov routing", ChangeType.ROUTING_RULE,
            steps=_two_steps(),
        )
        result = integration.apply_change_to_connector_routing("cr-2")
        assert result["steps_executed"] == 2

    def test_no_steps(self, integration):
        integration.change_from_governance(
            "cr-3", "No steps routing", ChangeType.CONFIGURATION,
        )
        result = integration.apply_change_to_connector_routing("cr-3")
        assert result["steps_executed"] == 0

    def test_default_connector_ref(self, integration):
        integration.change_from_governance(
            "cr-4", "Def ref", ChangeType.CONFIGURATION,
        )
        result = integration.apply_change_to_connector_routing("cr-4")
        assert result["connector_ref_id"] == ""

    def test_emits_event(self, integration, event_spine):
        integration.change_from_governance(
            "cr-evt", "Event", ChangeType.CONFIGURATION,
        )
        before = len(event_spine.list_events())
        integration.apply_change_to_connector_routing("cr-evt")
        after = len(event_spine.list_events())
        assert after > before

    def test_collects_evidence(self, integration, change_engine):
        integration.change_from_governance(
            "cr-ev", "Evidence", ChangeType.CONFIGURATION,
            steps=_two_steps(),
        )
        integration.apply_change_to_connector_routing(
            "cr-ev", connector_ref_id="conn-e"
        )
        evidence = change_engine.get_evidence("cr-ev")
        assert len(evidence) >= 1

    def test_return_keys(self, integration):
        integration.change_from_governance(
            "cr-rk", "Return keys", ChangeType.CONFIGURATION,
        )
        result = integration.apply_change_to_connector_routing("cr-rk")
        expected = {"change_id", "target", "connector_ref_id", "steps_executed"}
        assert set(result.keys()) == expected


# =====================================================================
# 9. apply_change_to_domain_pack_resolution
# =====================================================================


class TestApplyChangeToDomainPackResolution:
    """Tests for applying changes to the domain pack resolution subsystem."""

    def test_executes_steps(self, integration, change_engine):
        integration.change_from_optimization(
            "dp-1", "Domain pack opt", ChangeType.DOMAIN_PACK_ACTIVATION,
            steps=_two_steps(),
        )
        _approve(change_engine, "dp-1")
        result = integration.apply_change_to_domain_pack_resolution(
            "dp-1", domain_pack_ref_id="dp-ref-1"
        )
        assert result["change_id"] == "dp-1"
        assert result["target"] == "domain_pack"
        assert result["domain_pack_ref_id"] == "dp-ref-1"
        assert result["steps_executed"] == 2

    def test_governance_no_approval(self, integration):
        integration.change_from_governance(
            "dp-2", "Gov domain", ChangeType.DOMAIN_PACK_ACTIVATION,
            steps=_two_steps(),
        )
        result = integration.apply_change_to_domain_pack_resolution("dp-2")
        assert result["steps_executed"] == 2

    def test_no_steps(self, integration):
        integration.change_from_governance(
            "dp-3", "No steps domain", ChangeType.CONFIGURATION,
        )
        result = integration.apply_change_to_domain_pack_resolution("dp-3")
        assert result["steps_executed"] == 0

    def test_default_domain_pack_ref(self, integration):
        integration.change_from_governance(
            "dp-4", "Def ref", ChangeType.CONFIGURATION,
        )
        result = integration.apply_change_to_domain_pack_resolution("dp-4")
        assert result["domain_pack_ref_id"] == ""

    def test_emits_event(self, integration, event_spine):
        integration.change_from_governance(
            "dp-evt", "Event", ChangeType.CONFIGURATION,
        )
        before = len(event_spine.list_events())
        integration.apply_change_to_domain_pack_resolution("dp-evt")
        after = len(event_spine.list_events())
        assert after > before

    def test_collects_evidence(self, integration, change_engine):
        integration.change_from_governance(
            "dp-ev", "Evidence", ChangeType.CONFIGURATION,
            steps=_two_steps(),
        )
        integration.apply_change_to_domain_pack_resolution(
            "dp-ev", domain_pack_ref_id="dp-e"
        )
        evidence = change_engine.get_evidence("dp-ev")
        assert len(evidence) >= 1

    def test_return_keys(self, integration):
        integration.change_from_governance(
            "dp-rk", "Return keys", ChangeType.CONFIGURATION,
        )
        result = integration.apply_change_to_domain_pack_resolution("dp-rk")
        expected = {"change_id", "target", "domain_pack_ref_id", "steps_executed"}
        assert set(result.keys()) == expected


# =====================================================================
# 10. attach_change_to_memory_mesh
# =====================================================================


class TestAttachChangeToMemoryMesh:
    """Tests for persisting change state to memory mesh."""

    def test_returns_memory_record(self, integration):
        integration.change_from_governance(
            "mem-1", "Memory test", ChangeType.CONFIGURATION,
        )
        mem = integration.attach_change_to_memory_mesh("scope-1")
        assert isinstance(mem, MemoryRecord)

    def test_memory_id_is_deterministic(self, integration):
        integration.change_from_governance(
            "mem-2", "Det test", ChangeType.CONFIGURATION,
        )
        mem = integration.attach_change_to_memory_mesh("scope-det")
        # Creating a new integration with same scope_ref_id should produce same ID
        # (but will raise duplicate - tested separately)
        # For now just check it's a non-empty string
        assert mem.memory_id != ""

    def test_deterministic_across_instances(self):
        """Same scope_ref_id produces same memory_id across different instances."""
        es1 = EventSpineEngine()
        me1 = MemoryMeshEngine()
        ce1 = ChangeRuntimeEngine(es1)
        ci1 = ChangeIntegration(ce1, es1, me1)
        ci1.change_from_governance("m-det-a", "A", ChangeType.CONFIGURATION)
        mem1 = ci1.attach_change_to_memory_mesh("same-scope")

        es2 = EventSpineEngine()
        me2 = MemoryMeshEngine()
        ce2 = ChangeRuntimeEngine(es2)
        ci2 = ChangeIntegration(ce2, es2, me2)
        ci2.change_from_governance("m-det-b", "B", ChangeType.CONFIGURATION)
        mem2 = ci2.attach_change_to_memory_mesh("same-scope")

        assert mem1.memory_id == mem2.memory_id

    def test_content_fields(self, integration):
        integration.change_from_governance(
            "mem-3", "Content test", ChangeType.CONFIGURATION,
        )
        mem = integration.attach_change_to_memory_mesh("scope-content")
        content = mem.content
        assert "scope_ref_id" in content
        assert "total_changes" in content
        assert "total_plans" in content
        assert "total_outcomes" in content

    def test_content_counts_match(self, integration, change_engine):
        integration.change_from_governance(
            "mem-4", "Count test", ChangeType.CONFIGURATION,
            steps=_two_steps(),
        )
        mem = integration.attach_change_to_memory_mesh("scope-count")
        assert mem.content["total_changes"] == change_engine.change_count
        assert mem.content["total_plans"] == change_engine.plan_count
        assert mem.content["total_outcomes"] == change_engine.outcome_count

    def test_memory_type_observation(self, integration):
        integration.change_from_governance(
            "mem-5", "Type test", ChangeType.CONFIGURATION,
        )
        mem = integration.attach_change_to_memory_mesh("scope-type")
        assert mem.memory_type == MemoryType.OBSERVATION

    def test_memory_scope_global(self, integration):
        integration.change_from_governance(
            "mem-6", "Scope test", ChangeType.CONFIGURATION,
        )
        mem = integration.attach_change_to_memory_mesh("scope-global")
        assert mem.scope == MemoryScope.GLOBAL

    def test_trust_level_verified(self, integration):
        integration.change_from_governance(
            "mem-7", "Trust test", ChangeType.CONFIGURATION,
        )
        mem = integration.attach_change_to_memory_mesh("scope-trust")
        assert mem.trust_level == MemoryTrustLevel.VERIFIED

    def test_confidence_one(self, integration):
        integration.change_from_governance(
            "mem-8", "Conf test", ChangeType.CONFIGURATION,
        )
        mem = integration.attach_change_to_memory_mesh("scope-conf")
        assert mem.confidence == 1.0

    def test_tags_present(self, integration):
        integration.change_from_governance(
            "mem-9", "Tags test", ChangeType.CONFIGURATION,
        )
        mem = integration.attach_change_to_memory_mesh("scope-tags")
        assert "change" in mem.tags
        assert "controlled" in mem.tags
        assert "state" in mem.tags

    def test_title_includes_scope_ref(self, integration):
        integration.change_from_governance(
            "mem-10", "Title test", ChangeType.CONFIGURATION,
        )
        mem = integration.attach_change_to_memory_mesh("my-scope-ref")
        assert "my-scope-ref" in mem.title

    def test_source_ids(self, integration):
        integration.change_from_governance(
            "mem-11", "Source ids", ChangeType.CONFIGURATION,
        )
        mem = integration.attach_change_to_memory_mesh("src-scope")
        assert "src-scope" in mem.source_ids

    def test_emits_event(self, integration, event_spine):
        integration.change_from_governance(
            "mem-evt", "Event test", ChangeType.CONFIGURATION,
        )
        before = len(event_spine.list_events())
        integration.attach_change_to_memory_mesh("scope-evt")
        after = len(event_spine.list_events())
        assert after > before


# =====================================================================
# 11. attach_change_to_graph
# =====================================================================


class TestAttachChangeToGraph:
    """Tests for returning change state for operational graph consumption."""

    def test_returns_dict(self, integration):
        integration.change_from_governance(
            "gr-1", "Graph test", ChangeType.CONFIGURATION,
        )
        result = integration.attach_change_to_graph("scope-graph")
        assert isinstance(result, dict)

    def test_correct_keys(self, integration):
        integration.change_from_governance(
            "gr-2", "Keys test", ChangeType.CONFIGURATION,
        )
        result = integration.attach_change_to_graph("scope-keys")
        expected = {"scope_ref_id", "total_changes", "total_plans", "total_outcomes"}
        assert set(result.keys()) == expected

    def test_counts_match_engine(self, integration, change_engine):
        integration.change_from_governance(
            "gr-3", "Count match", ChangeType.CONFIGURATION,
            steps=_two_steps(),
        )
        result = integration.attach_change_to_graph("scope-match")
        assert result["total_changes"] == change_engine.change_count
        assert result["total_plans"] == change_engine.plan_count
        assert result["total_outcomes"] == change_engine.outcome_count

    def test_scope_ref_id_returned(self, integration):
        integration.change_from_governance(
            "gr-4", "Scope ref", ChangeType.CONFIGURATION,
        )
        result = integration.attach_change_to_graph("my-graph-scope")
        assert result["scope_ref_id"] == "my-graph-scope"

    def test_multiple_changes_reflected(self, integration, change_engine):
        integration.change_from_governance(
            "gr-5a", "First", ChangeType.CONFIGURATION,
        )
        integration.change_from_governance(
            "gr-5b", "Second", ChangeType.BUDGET_THRESHOLD,
        )
        result = integration.attach_change_to_graph("multi")
        assert result["total_changes"] == 2

    def test_outcome_count_after_completion(self, integration, change_engine):
        integration.change_from_governance(
            "gr-6", "Complete", ChangeType.CONFIGURATION,
            steps=_two_steps(),
        )
        integration.apply_change_to_portfolio("gr-6")
        change_engine.complete_change("gr-6")
        result = integration.attach_change_to_graph("completed")
        assert result["total_outcomes"] == 1


# =====================================================================
# 12. Return value schemas consistency
# =====================================================================


class TestReturnValueSchemas:
    """All creation methods return consistent dict schemas."""

    def test_optimization_schema(self, integration):
        result = integration.change_from_optimization(
            "schema-opt", "Opt", ChangeType.CONFIGURATION,
        )
        assert isinstance(result["change_id"], str)
        assert isinstance(result["source"], str)
        assert isinstance(result["change_type"], str)
        assert isinstance(result["rollout_mode"], str)
        assert isinstance(result["approval_required"], bool)
        assert result["plan_id"] is None or isinstance(result["plan_id"], str)
        assert isinstance(result["step_count"], int)

    def test_governance_schema(self, integration):
        result = integration.change_from_governance(
            "schema-gov", "Gov", ChangeType.CONFIGURATION,
        )
        assert isinstance(result["change_id"], str)
        assert isinstance(result["source"], str)
        assert isinstance(result["change_type"], str)
        assert isinstance(result["rollout_mode"], str)
        assert isinstance(result["approval_required"], bool)
        assert result["plan_id"] is None or isinstance(result["plan_id"], str)
        assert isinstance(result["step_count"], int)

    def test_fault_campaign_schema(self, integration):
        result = integration.change_from_fault_campaign(
            "schema-fc", "FC", ChangeType.CONFIGURATION,
        )
        assert isinstance(result["change_id"], str)
        assert isinstance(result["source"], str)
        assert isinstance(result["change_type"], str)
        assert isinstance(result["rollout_mode"], str)
        assert isinstance(result["approval_required"], bool)
        assert result["plan_id"] is None or isinstance(result["plan_id"], str)
        assert isinstance(result["step_count"], int)

    def test_portfolio_apply_schema(self, integration):
        integration.change_from_governance(
            "schema-ap", "AP", ChangeType.CONFIGURATION,
        )
        result = integration.apply_change_to_portfolio("schema-ap")
        assert isinstance(result["change_id"], str)
        assert isinstance(result["target"], str)
        assert isinstance(result["portfolio_ref_id"], str)
        assert isinstance(result["steps_executed"], int)

    def test_availability_apply_schema(self, integration):
        integration.change_from_governance(
            "schema-av", "AV", ChangeType.CONFIGURATION,
        )
        result = integration.apply_change_to_availability("schema-av")
        assert isinstance(result["change_id"], str)
        assert isinstance(result["target"], str)
        assert isinstance(result["identity_ref_id"], str)
        assert isinstance(result["steps_executed"], int)

    def test_financials_apply_schema(self, integration):
        integration.change_from_governance(
            "schema-fin", "FIN", ChangeType.CONFIGURATION,
        )
        result = integration.apply_change_to_financials("schema-fin")
        assert isinstance(result["change_id"], str)
        assert isinstance(result["target"], str)
        assert isinstance(result["budget_ref_id"], str)
        assert isinstance(result["steps_executed"], int)

    def test_connector_routing_apply_schema(self, integration):
        integration.change_from_governance(
            "schema-cr", "CR", ChangeType.CONFIGURATION,
        )
        result = integration.apply_change_to_connector_routing("schema-cr")
        assert isinstance(result["change_id"], str)
        assert isinstance(result["target"], str)
        assert isinstance(result["connector_ref_id"], str)
        assert isinstance(result["steps_executed"], int)

    def test_domain_pack_apply_schema(self, integration):
        integration.change_from_governance(
            "schema-dp", "DP", ChangeType.CONFIGURATION,
        )
        result = integration.apply_change_to_domain_pack_resolution("schema-dp")
        assert isinstance(result["change_id"], str)
        assert isinstance(result["target"], str)
        assert isinstance(result["domain_pack_ref_id"], str)
        assert isinstance(result["steps_executed"], int)


# =====================================================================
# 13. Event emission
# =====================================================================


class TestEventEmission:
    """Each bridge method emits at least one event."""

    def test_optimization_event_payload(self, integration, event_spine):
        integration.change_from_optimization(
            "ee-opt", "Opt event", ChangeType.CONFIGURATION,
        )
        events = event_spine.list_events()
        payloads = [e.payload for e in events if e.payload.get("action") == "change_from_optimization"]
        assert len(payloads) >= 1
        assert payloads[-1]["change_id"] == "ee-opt"

    def test_governance_event_payload(self, integration, event_spine):
        integration.change_from_governance(
            "ee-gov", "Gov event", ChangeType.CONFIGURATION,
        )
        events = event_spine.list_events()
        payloads = [e.payload for e in events if e.payload.get("action") == "change_from_governance"]
        assert len(payloads) >= 1
        assert payloads[-1]["change_id"] == "ee-gov"

    def test_fault_campaign_event_payload(self, integration, event_spine):
        integration.change_from_fault_campaign(
            "ee-fc", "FC event", ChangeType.CONFIGURATION,
        )
        events = event_spine.list_events()
        payloads = [e.payload for e in events if e.payload.get("action") == "change_from_fault_campaign"]
        assert len(payloads) >= 1
        assert payloads[-1]["change_id"] == "ee-fc"

    def test_portfolio_event_payload(self, integration, event_spine):
        integration.change_from_governance(
            "ee-ap", "Apply event", ChangeType.CONFIGURATION,
        )
        integration.apply_change_to_portfolio("ee-ap", portfolio_ref_id="pf-ee")
        events = event_spine.list_events()
        payloads = [e.payload for e in events if e.payload.get("action") == "change_applied_to_portfolio"]
        assert len(payloads) >= 1
        assert payloads[-1]["portfolio_ref_id"] == "pf-ee"

    def test_availability_event_payload(self, integration, event_spine):
        integration.change_from_governance(
            "ee-av", "Avail event", ChangeType.CONFIGURATION,
        )
        integration.apply_change_to_availability("ee-av", identity_ref_id="id-ee")
        events = event_spine.list_events()
        payloads = [e.payload for e in events if e.payload.get("action") == "change_applied_to_availability"]
        assert len(payloads) >= 1
        assert payloads[-1]["identity_ref_id"] == "id-ee"

    def test_financials_event_payload(self, integration, event_spine):
        integration.change_from_governance(
            "ee-fin", "Fin event", ChangeType.CONFIGURATION,
        )
        integration.apply_change_to_financials("ee-fin", budget_ref_id="bud-ee")
        events = event_spine.list_events()
        payloads = [e.payload for e in events if e.payload.get("action") == "change_applied_to_financials"]
        assert len(payloads) >= 1
        assert payloads[-1]["budget_ref_id"] == "bud-ee"

    def test_connector_routing_event_payload(self, integration, event_spine):
        integration.change_from_governance(
            "ee-cr", "Routing event", ChangeType.CONFIGURATION,
        )
        integration.apply_change_to_connector_routing("ee-cr", connector_ref_id="conn-ee")
        events = event_spine.list_events()
        payloads = [e.payload for e in events if e.payload.get("action") == "change_applied_to_connector_routing"]
        assert len(payloads) >= 1
        assert payloads[-1]["connector_ref_id"] == "conn-ee"

    def test_domain_pack_event_payload(self, integration, event_spine):
        integration.change_from_governance(
            "ee-dp", "Domain event", ChangeType.CONFIGURATION,
        )
        integration.apply_change_to_domain_pack_resolution("ee-dp", domain_pack_ref_id="dp-ee")
        events = event_spine.list_events()
        payloads = [e.payload for e in events if e.payload.get("action") == "change_applied_to_domain_pack"]
        assert len(payloads) >= 1
        assert payloads[-1]["domain_pack_ref_id"] == "dp-ee"

    def test_memory_mesh_event_payload(self, integration, event_spine):
        integration.change_from_governance(
            "ee-mem", "Mem event", ChangeType.CONFIGURATION,
        )
        integration.attach_change_to_memory_mesh("scope-ee")
        events = event_spine.list_events()
        payloads = [e.payload for e in events if e.payload.get("action") == "change_attached_to_memory"]
        assert len(payloads) >= 1
        assert payloads[-1]["scope_ref_id"] == "scope-ee"


# =====================================================================
# 14. Memory mesh determinism
# =====================================================================


class TestMemoryMeshDeterminism:
    """Same scope_ref_id always produces the same memory_id."""

    def test_same_id_across_fresh_instances(self):
        ids = []
        for i in range(3):
            es = EventSpineEngine()
            me = MemoryMeshEngine()
            ce = ChangeRuntimeEngine(es)
            ci = ChangeIntegration(ce, es, me)
            ci.change_from_governance(f"det-{i}", "Det", ChangeType.CONFIGURATION)
            mem = ci.attach_change_to_memory_mesh("deterministic-scope")
            ids.append(mem.memory_id)
        assert ids[0] == ids[1] == ids[2]

    def test_different_scope_ref_different_id(self, integration):
        integration.change_from_governance(
            "det-diff-a", "A", ChangeType.CONFIGURATION,
        )
        mem_a = integration.attach_change_to_memory_mesh("scope-alpha")

        # Need new memory engine to avoid duplicate
        es2 = EventSpineEngine()
        me2 = MemoryMeshEngine()
        ce2 = ChangeRuntimeEngine(es2)
        ci2 = ChangeIntegration(ce2, es2, me2)
        ci2.change_from_governance("det-diff-b", "B", ChangeType.CONFIGURATION)
        mem_b = ci2.attach_change_to_memory_mesh("scope-beta")

        assert mem_a.memory_id != mem_b.memory_id


# =====================================================================
# 15. Memory mesh duplicate raises
# =====================================================================


class TestMemoryMeshDuplicateRaises:
    """Duplicate memory_id raises on the same MemoryMeshEngine."""

    def test_duplicate_scope_ref_raises(self, integration):
        integration.change_from_governance(
            "dup-mem-1", "First", ChangeType.CONFIGURATION,
        )
        integration.attach_change_to_memory_mesh("dup-scope")
        with pytest.raises(RuntimeCoreInvariantError):
            integration.attach_change_to_memory_mesh("dup-scope")

    def test_different_scope_ref_no_raise(self, integration):
        integration.change_from_governance(
            "dup-mem-2", "First", ChangeType.CONFIGURATION,
        )
        integration.attach_change_to_memory_mesh("scope-x")
        integration.attach_change_to_memory_mesh("scope-y")  # should not raise


# =====================================================================
# 16. Golden end-to-end scenarios
# =====================================================================


class TestGoldenOptimizationFlow:
    """Full optimization -> approve -> apply -> complete -> assess."""

    def test_full_flow(self, integration, change_engine, event_spine):
        # 1. Create change from optimization with steps
        create_result = integration.change_from_optimization(
            "gold-opt-1", "Optimize connector routing",
            ChangeType.ROUTING_RULE,
            recommendation_id="rec-gold-1",
            scope=ChangeScope.CONNECTOR,
            scope_ref_id="conn-gold",
            rollout_mode=RolloutMode.CANARY,
            approval_required=True,
            reason="Reduce latency by 20%",
            steps=_three_steps(),
        )
        assert create_result["source"] == "optimization"
        assert create_result["step_count"] == 3
        assert create_result["approval_required"] is True

        # 2. Submit for approval and approve
        _approve(change_engine, "gold-opt-1")
        assert change_engine.get_change_status("gold-opt-1") == ChangeStatus.APPROVED

        # 3. Apply to connector routing
        apply_result = integration.apply_change_to_connector_routing(
            "gold-opt-1", connector_ref_id="conn-gold"
        )
        assert apply_result["steps_executed"] == 3
        assert change_engine.get_change_status("gold-opt-1") == ChangeStatus.IN_PROGRESS

        # 4. Complete change
        outcome = change_engine.complete_change(
            "gold-opt-1", success=True, improvement_observed=True, improvement_pct=20.0
        )
        assert outcome.success is True
        assert outcome.improvement_pct == 20.0

        # 5. Assess impact
        assessment = change_engine.assess_change_impact(
            "gold-opt-1", "latency_ms", 100.0, 80.0, confidence=0.95
        )
        assert assessment.improvement_pct == pytest.approx(-20.0)

        # 6. Attach to memory mesh
        mem = integration.attach_change_to_memory_mesh("gold-opt-scope")
        assert mem.content["total_changes"] == 1
        assert mem.content["total_outcomes"] == 1

        # 7. Attach to graph
        graph = integration.attach_change_to_graph("gold-opt-scope")
        assert graph["total_changes"] == 1
        assert graph["total_outcomes"] == 1

        # 8. Verify events were emitted
        events = event_spine.list_events()
        assert len(events) > 5

    def test_optimization_with_no_approval(self, integration, change_engine):
        """Optimization with approval_required=False skips approval step."""
        create_result = integration.change_from_optimization(
            "gold-opt-na", "No-approval opt", ChangeType.CONFIGURATION,
            approval_required=False,
            steps=_two_steps(),
        )
        assert create_result["approval_required"] is False

        # Apply directly without approval
        result = integration.apply_change_to_portfolio("gold-opt-na", portfolio_ref_id="pf-na")
        assert result["steps_executed"] == 2

        change_engine.complete_change("gold-opt-na", success=True)
        assert change_engine.get_change_status("gold-opt-na") == ChangeStatus.COMPLETED


class TestGoldenGovernanceFlow:
    """Governance change -> apply -> complete."""

    def test_full_governance_flow(self, integration, change_engine, event_spine):
        # 1. Create governance change with steps
        create_result = integration.change_from_governance(
            "gold-gov-1", "Enforce budget threshold",
            ChangeType.BUDGET_THRESHOLD,
            scope=ChangeScope.GLOBAL,
            rollout_mode=RolloutMode.IMMEDIATE,
            reason="Compliance requirement",
            steps=_two_steps(),
        )
        assert create_result["source"] == "governance"
        assert create_result["approval_required"] is False
        assert create_result["step_count"] == 2

        # 2. Apply directly (no approval needed)
        apply_result = integration.apply_change_to_financials(
            "gold-gov-1", budget_ref_id="budget-gold"
        )
        assert apply_result["steps_executed"] == 2

        # 3. Complete change
        outcome = change_engine.complete_change("gold-gov-1", success=True)
        assert outcome.success is True
        assert change_engine.get_change_status("gold-gov-1") == ChangeStatus.COMPLETED

        # 4. Verify counts
        graph = integration.attach_change_to_graph("gov-gold-scope")
        assert graph["total_changes"] == 1
        assert graph["total_outcomes"] == 1

    def test_governance_multiple_subsystems(self, integration, change_engine):
        """Governance change applied to multiple subsystems."""
        integration.change_from_governance(
            "gold-gov-multi", "Multi-subsystem",
            ChangeType.CONFIGURATION,
            steps=[
                {"action": "step-a", "description": "first"},
                {"action": "step-b", "description": "second"},
                {"action": "step-c", "description": "third"},
                {"action": "step-d", "description": "fourth"},
            ],
        )
        # All steps consumed by first apply
        r1 = integration.apply_change_to_portfolio("gold-gov-multi")
        assert r1["steps_executed"] == 4

        # Subsequent applies find no DRAFT steps
        r2 = integration.apply_change_to_availability("gold-gov-multi")
        assert r2["steps_executed"] == 0

        r3 = integration.apply_change_to_financials("gold-gov-multi")
        assert r3["steps_executed"] == 0


class TestGoldenFaultCampaignRollbackFlow:
    """Fault campaign -> apply -> rollback."""

    def test_fault_campaign_rollback(self, integration, change_engine, event_spine):
        # 1. Create fault campaign change with steps
        create_result = integration.change_from_fault_campaign(
            "gold-fc-1", "Fix detected failure",
            ChangeType.FALLBACK_CHAIN,
            scope=ChangeScope.CONNECTOR,
            scope_ref_id="conn-fault",
            rollout_mode=RolloutMode.CANARY,
            approval_required=True,
            reason="Failure mode detected in campaign X",
            steps=_two_steps(),
        )
        assert create_result["source"] == "fault_campaign"
        assert create_result["approval_required"] is True

        # 2. Approve
        _approve(change_engine, "gold-fc-1")

        # 3. Apply to connector routing
        apply_result = integration.apply_change_to_connector_routing(
            "gold-fc-1", connector_ref_id="conn-fault"
        )
        assert apply_result["steps_executed"] == 2

        # 4. Rollback
        rollback = change_engine.rollback_change(
            "gold-fc-1", reason="Regression detected"
        )
        assert rollback.disposition == RollbackDisposition.TRIGGERED
        assert change_engine.get_change_status("gold-fc-1") == ChangeStatus.ROLLED_BACK

    def test_fault_campaign_no_approval_rollback(self, integration, change_engine):
        """Fault campaign without approval that gets rolled back."""
        integration.change_from_fault_campaign(
            "gold-fc-na", "Auto fault fix",
            ChangeType.CONFIGURATION,
            approval_required=False,
            steps=_two_steps(),
        )
        integration.apply_change_to_availability("gold-fc-na", identity_ref_id="id-fault")
        rollback = change_engine.rollback_change("gold-fc-na", reason="Didn't help")
        assert rollback.disposition == RollbackDisposition.TRIGGERED


class TestGoldenMultipleSubsystemApplications:
    """Applying a single change to multiple subsystems."""

    def test_apply_to_all_five_subsystems(self, integration, change_engine):
        """Create one governance change and apply to all five subsystems in sequence."""
        # Use 5 steps so each subsystem can execute 1 (after the first takes all DRAFT)
        # Actually: all DRAFT steps are consumed on first apply. Subsequent ones get 0.
        integration.change_from_governance(
            "gold-multi", "Multi-subsystem change",
            ChangeType.CONFIGURATION,
            steps=_two_steps(),
        )

        r1 = integration.apply_change_to_portfolio(
            "gold-multi", portfolio_ref_id="pf-multi"
        )
        assert r1["steps_executed"] == 2
        assert r1["target"] == "portfolio"

        r2 = integration.apply_change_to_availability(
            "gold-multi", identity_ref_id="id-multi"
        )
        assert r2["target"] == "availability"
        assert r2["steps_executed"] == 0

        r3 = integration.apply_change_to_financials(
            "gold-multi", budget_ref_id="bud-multi"
        )
        assert r3["target"] == "financials"

        r4 = integration.apply_change_to_connector_routing(
            "gold-multi", connector_ref_id="conn-multi"
        )
        assert r4["target"] == "connector_routing"

        r5 = integration.apply_change_to_domain_pack_resolution(
            "gold-multi", domain_pack_ref_id="dp-multi"
        )
        assert r5["target"] == "domain_pack"

        # Evidence collected for each apply
        evidence = change_engine.get_evidence("gold-multi")
        assert len(evidence) == 5

    def test_multiple_changes_independent(self, integration, change_engine):
        """Multiple independent changes applied to different subsystems."""
        integration.change_from_governance(
            "ind-1", "Portfolio change", ChangeType.CONNECTOR_PREFERENCE,
            steps=[{"action": "pf-step", "description": "portfolio step"}],
        )
        integration.change_from_governance(
            "ind-2", "Financial change", ChangeType.BUDGET_THRESHOLD,
            steps=[{"action": "fin-step", "description": "financial step"}],
        )
        integration.change_from_governance(
            "ind-3", "Routing change", ChangeType.ROUTING_RULE,
            steps=[{"action": "rt-step", "description": "routing step"}],
        )

        r1 = integration.apply_change_to_portfolio("ind-1")
        assert r1["steps_executed"] == 1

        r2 = integration.apply_change_to_financials("ind-2")
        assert r2["steps_executed"] == 1

        r3 = integration.apply_change_to_connector_routing("ind-3")
        assert r3["steps_executed"] == 1

        graph = integration.attach_change_to_graph("ind-scope")
        assert graph["total_changes"] == 3


class TestGoldenPauseResumeFlow:
    """Change that is paused and then resumed."""

    def test_pause_resume_complete(self, integration, change_engine):
        integration.change_from_optimization(
            "gold-pr", "Pause resume", ChangeType.CONFIGURATION,
            steps=_three_steps(),
        )
        _approve(change_engine, "gold-pr")

        # Execute first step to move to IN_PROGRESS
        steps = change_engine.get_steps("gold-pr")
        change_engine.execute_change_step("gold-pr", steps[0].step_id)
        assert change_engine.get_change_status("gold-pr") == ChangeStatus.IN_PROGRESS

        # Pause
        change_engine.pause_change("gold-pr", reason="Investigating side effects")
        assert change_engine.get_change_status("gold-pr") == ChangeStatus.PAUSED

        # Resume
        change_engine.resume_change("gold-pr")
        assert change_engine.get_change_status("gold-pr") == ChangeStatus.IN_PROGRESS

        # Apply remaining steps via integration
        result = integration.apply_change_to_portfolio("gold-pr")
        assert result["steps_executed"] == 2  # 2 remaining DRAFT steps

        # Complete
        change_engine.complete_change("gold-pr", success=True)
        assert change_engine.get_change_status("gold-pr") == ChangeStatus.COMPLETED


class TestGoldenAbortFlow:
    """Change that is aborted after approval."""

    def test_abort_after_approval(self, integration, change_engine):
        integration.change_from_optimization(
            "gold-abort", "Abort test", ChangeType.CONFIGURATION,
            steps=_two_steps(),
        )
        change_engine.submit_for_approval("gold-abort")
        change_engine.abort_change("gold-abort", reason="Requirements changed")
        assert change_engine.get_change_status("gold-abort") == ChangeStatus.ABORTED


class TestGoldenEvidenceAndAssessment:
    """Collecting evidence and assessing impact in a complete flow."""

    def test_evidence_and_assessment(self, integration, change_engine):
        integration.change_from_governance(
            "gold-ea", "Evidence flow", ChangeType.BUDGET_THRESHOLD,
            steps=_two_steps(),
        )

        # Collect baseline evidence
        change_engine.collect_evidence(
            "gold-ea", ChangeEvidenceKind.METRIC_BEFORE,
            metric_name="cost", metric_value=1000.0,
        )

        # Apply
        integration.apply_change_to_financials("gold-ea", budget_ref_id="bud-ea")

        # Collect after evidence
        change_engine.collect_evidence(
            "gold-ea", ChangeEvidenceKind.METRIC_AFTER,
            metric_name="cost", metric_value=800.0,
        )

        # Complete
        change_engine.complete_change(
            "gold-ea", success=True, improvement_observed=True, improvement_pct=20.0,
        )

        # Assess
        assessment = change_engine.assess_change_impact(
            "gold-ea", "cost", 1000.0, 800.0, confidence=0.9,
        )
        assert assessment.improvement_pct == pytest.approx(-20.0)

        # Verify evidence count in outcome
        outcome = change_engine.get_outcome("gold-ea")
        # 3 evidence items: metric_before, LOG_ENTRY from apply, metric_after
        assert outcome.evidence_count == 3

        # Memory attachment with counts
        mem = integration.attach_change_to_memory_mesh("ea-scope")
        assert mem.content["total_outcomes"] == 1


class TestGoldenMixedSourceFlow:
    """Multiple changes from different sources in the same integration."""

    def test_mixed_sources(self, integration, change_engine):
        # Optimization change
        r1 = integration.change_from_optimization(
            "mix-opt", "Opt change", ChangeType.ROUTING_RULE,
            steps=[{"action": "opt-step", "description": "opt"}],
        )
        assert r1["source"] == "optimization"

        # Governance change
        r2 = integration.change_from_governance(
            "mix-gov", "Gov change", ChangeType.BUDGET_THRESHOLD,
            steps=[{"action": "gov-step", "description": "gov"}],
        )
        assert r2["source"] == "governance"

        # Fault campaign change
        r3 = integration.change_from_fault_campaign(
            "mix-fc", "FC change", ChangeType.FALLBACK_CHAIN,
            approval_required=False,
            steps=[{"action": "fc-step", "description": "fc"}],
        )
        assert r3["source"] == "fault_campaign"

        # Apply governance (no approval needed)
        integration.apply_change_to_financials("mix-gov")

        # Apply fault campaign (no approval needed)
        integration.apply_change_to_availability("mix-fc")

        # Approve and apply optimization
        _approve(change_engine, "mix-opt")
        integration.apply_change_to_connector_routing("mix-opt")

        # Complete all
        change_engine.complete_change("mix-gov", success=True)
        change_engine.complete_change("mix-fc", success=True)
        change_engine.complete_change("mix-opt", success=True)

        # Graph should reflect all changes
        graph = integration.attach_change_to_graph("mix-scope")
        assert graph["total_changes"] == 3
        assert graph["total_outcomes"] == 3


class TestGoldenDryRunFlow:
    """Change using DRY_RUN rollout mode."""

    def test_dry_run_mode(self, integration, change_engine):
        result = integration.change_from_optimization(
            "gold-dry", "Dry run test", ChangeType.CONFIGURATION,
            rollout_mode=RolloutMode.DRY_RUN,
            approval_required=False,
            steps=_two_steps(),
        )
        assert result["rollout_mode"] == "dry_run"

        apply_result = integration.apply_change_to_portfolio("gold-dry")
        assert apply_result["steps_executed"] == 2


class TestGoldenScopeVariations:
    """Changes with various scope types."""

    def test_all_scopes(self, integration):
        for i, scope in enumerate(ChangeScope):
            result = integration.change_from_governance(
                f"scope-{i}", f"Scope {scope.value}", ChangeType.CONFIGURATION,
                scope=scope, scope_ref_id=f"ref-{scope.value}",
            )
            assert result["change_id"] == f"scope-{i}"

    def test_scope_does_not_affect_return_schema(self, integration):
        for i, scope in enumerate(ChangeScope):
            result = integration.change_from_governance(
                f"scope-schema-{i}", f"Schema {scope.value}", ChangeType.CONFIGURATION,
                scope=scope,
            )
            assert "change_id" in result
            assert "source" in result
            assert "approval_required" in result


class TestGoldenRolloutModeVariations:
    """Changes with various rollout modes."""

    def test_all_rollout_modes_optimization(self, integration):
        for i, mode in enumerate(RolloutMode):
            result = integration.change_from_optimization(
                f"rm-opt-{i}", f"Mode {mode.value}", ChangeType.CONFIGURATION,
                rollout_mode=mode, approval_required=False,
            )
            assert result["rollout_mode"] == mode.value

    def test_all_rollout_modes_governance(self, integration):
        for i, mode in enumerate(RolloutMode):
            result = integration.change_from_governance(
                f"rm-gov-{i}", f"Mode {mode.value}", ChangeType.CONFIGURATION,
                rollout_mode=mode,
            )
            assert result["rollout_mode"] == mode.value

    def test_all_rollout_modes_fault_campaign(self, integration):
        for i, mode in enumerate(RolloutMode):
            result = integration.change_from_fault_campaign(
                f"rm-fc-{i}", f"Mode {mode.value}", ChangeType.CONFIGURATION,
                rollout_mode=mode, approval_required=False,
            )
            assert result["rollout_mode"] == mode.value
