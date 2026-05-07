"""Tests for mcoi.mcoi_runtime.core.financial_integration.FinancialIntegration.

Covers: constructor validation, all reservation methods (campaign step,
connector call, communication, artifact parsing, provider routing),
budget binding, governance/portfolio gating, memory mesh attachment,
graph attachment, event emission, and disposition serialization.

Target: 100+ tests across 13 test classes.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.financial_runtime import FinancialRuntimeEngine
from mcoi_runtime.core.financial_integration import FinancialIntegration
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.financial_runtime import (
    BudgetScope,
    CostCategory,
    ChargeDisposition,
    ApprovalThresholdMode,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _setup(*, limit=1000.0, budget_id="b1", scope_ref="camp-1"):
    es = EventSpineEngine()
    fe = FinancialRuntimeEngine(es)
    mm = MemoryMeshEngine()
    fi = FinancialIntegration(fe, es, mm)
    fe.register_budget(
        budget_id, "Test Budget", BudgetScope.CAMPAIGN, scope_ref,
        limit_amount=limit,
    )
    return fi, fe, es, mm


def _setup_with_approval(*, limit=1000.0, budget_id="b1", scope_ref="camp-1",
                          threshold_amount=100.0, approver="mgr-1"):
    """Set up with an approval threshold so requests >= threshold need approval."""
    fi, fe, es, mm = _setup(limit=limit, budget_id=budget_id, scope_ref=scope_ref)
    fe.set_approval_threshold(
        "thr-1", budget_id, ApprovalThresholdMode.PER_TRANSACTION,
        threshold_amount, approver,
    )
    return fi, fe, es, mm


def _setup_with_connector_profile(*, limit=1000.0, budget_id="b1",
                                   scope_ref="camp-1", connector_ref="conn-A",
                                   cost_per_call=5.0, cost_per_unit=2.0):
    fi, fe, es, mm = _setup(limit=limit, budget_id=budget_id, scope_ref=scope_ref)
    fe.register_connector_cost_profile(
        "prof-1", connector_ref,
        cost_per_call=cost_per_call,
        cost_per_unit=cost_per_unit,
    )
    return fi, fe, es, mm


# ===================================================================
# 1. TestConstructorValidation
# ===================================================================


class TestConstructorValidation:
    """FinancialIntegration.__init__ must reject wrong types."""

    def test_wrong_type_financial_engine_string(self):
        with pytest.raises(RuntimeCoreInvariantError):
            FinancialIntegration("not-an-engine", EventSpineEngine(), MemoryMeshEngine())

    def test_wrong_type_financial_engine_int(self):
        with pytest.raises(RuntimeCoreInvariantError):
            FinancialIntegration(42, EventSpineEngine(), MemoryMeshEngine())

    def test_wrong_type_financial_engine_none(self):
        with pytest.raises(RuntimeCoreInvariantError):
            FinancialIntegration(None, EventSpineEngine(), MemoryMeshEngine())

    def test_wrong_type_event_spine_string(self):
        es = EventSpineEngine()
        fe = FinancialRuntimeEngine(es)
        with pytest.raises(RuntimeCoreInvariantError):
            FinancialIntegration(fe, "not-a-spine", MemoryMeshEngine())

    def test_wrong_type_event_spine_int(self):
        es = EventSpineEngine()
        fe = FinancialRuntimeEngine(es)
        with pytest.raises(RuntimeCoreInvariantError):
            FinancialIntegration(fe, 123, MemoryMeshEngine())

    def test_wrong_type_event_spine_none(self):
        es = EventSpineEngine()
        fe = FinancialRuntimeEngine(es)
        with pytest.raises(RuntimeCoreInvariantError):
            FinancialIntegration(fe, None, MemoryMeshEngine())

    def test_wrong_type_memory_engine_string(self):
        es = EventSpineEngine()
        fe = FinancialRuntimeEngine(es)
        with pytest.raises(RuntimeCoreInvariantError):
            FinancialIntegration(fe, es, "not-a-memory")

    def test_wrong_type_memory_engine_int(self):
        es = EventSpineEngine()
        fe = FinancialRuntimeEngine(es)
        with pytest.raises(RuntimeCoreInvariantError):
            FinancialIntegration(fe, es, 999)

    def test_wrong_type_memory_engine_none(self):
        es = EventSpineEngine()
        fe = FinancialRuntimeEngine(es)
        with pytest.raises(RuntimeCoreInvariantError):
            FinancialIntegration(fe, es, None)

    def test_valid_construction(self):
        es = EventSpineEngine()
        fe = FinancialRuntimeEngine(es)
        mm = MemoryMeshEngine()
        fi = FinancialIntegration(fe, es, mm)
        assert fi is not None


# ===================================================================
# 2. TestReserveForCampaignStep
# ===================================================================


class TestReserveForCampaignStep:

    def test_approved_case(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_campaign_step("b1", "camp-1", "step-1", 100.0)
        assert result["approved"] is True

    def test_approved_returns_reservation_id(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_campaign_step("b1", "camp-1", "step-1", 100.0)
        assert result["reservation_id"] != ""

    def test_denied_case_exceeds_budget(self):
        fi, fe, es, mm = _setup(limit=50.0)
        result = fi.reserve_for_campaign_step("b1", "camp-1", "step-1", 100.0)
        assert result["approved"] is False

    def test_denied_reservation_id_empty(self):
        fi, fe, es, mm = _setup(limit=50.0)
        result = fi.reserve_for_campaign_step("b1", "camp-1", "step-1", 100.0)
        assert result["reservation_id"] == ""

    def test_all_return_keys_present(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_campaign_step("b1", "camp-1", "step-1", 50.0)
        expected_keys = {
            "budget_id", "campaign_ref", "step_ref", "reservation_id",
            "disposition", "requested_amount", "available_amount",
            "reason", "approved", "approval_required",
        }
        assert expected_keys <= set(result.keys())

    def test_budget_id_echoed(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_campaign_step("b1", "camp-1", "step-1", 50.0)
        assert result["budget_id"] == "b1"

    def test_campaign_ref_echoed(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_campaign_step("b1", "camp-X", "step-1", 50.0)
        assert result["campaign_ref"] == "camp-X"

    def test_step_ref_echoed(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_campaign_step("b1", "camp-1", "step-7", 50.0)
        assert result["step_ref"] == "step-7"

    def test_requested_amount_echoed(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_campaign_step("b1", "camp-1", "step-1", 123.45)
        assert result["requested_amount"] == 123.45

    def test_disposition_is_string(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_campaign_step("b1", "camp-1", "step-1", 50.0)
        assert isinstance(result["disposition"], str)
        assert not isinstance(result["disposition"], ChargeDisposition)

    def test_custom_category(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_campaign_step(
            "b1", "camp-1", "step-1", 10.0,
            category=CostCategory.COMMUNICATION,
        )
        assert result["approved"] is True

    def test_emits_events(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        before = len(es.list_events())
        fi.reserve_for_campaign_step("b1", "camp-1", "step-1", 50.0)
        after = len(es.list_events())
        assert after > before


# ===================================================================
# 3. TestReserveForConnectorCall
# ===================================================================


class TestReserveForConnectorCall:

    def test_approved_without_profile(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_connector_call("b1", "conn-X")
        assert result["approved"] is True
        # No profile => estimated_amount == 0
        assert result["estimated_amount"] == 0.0

    def test_approved_with_profile(self):
        fi, fe, es, mm = _setup_with_connector_profile(
            limit=1000.0, connector_ref="conn-A",
            cost_per_call=5.0, cost_per_unit=2.0,
        )
        result = fi.reserve_for_connector_call("b1", "conn-A", units=3)
        assert result["approved"] is True
        # cost_per_call(5) + cost_per_unit(2) * 3 = 11
        assert result["estimated_amount"] == 11.0

    def test_cost_estimation_integration_with_units(self):
        fi, fe, es, mm = _setup_with_connector_profile(
            limit=1000.0, connector_ref="conn-A",
            cost_per_call=10.0, cost_per_unit=5.0,
        )
        result = fi.reserve_for_connector_call("b1", "conn-A", units=10)
        assert result["estimated_amount"] == 60.0  # 10 + 5*10

    def test_denied_with_profile_exceeds_budget(self):
        fi, fe, es, mm = _setup_with_connector_profile(
            limit=5.0, connector_ref="conn-A",
            cost_per_call=10.0, cost_per_unit=0.0,
        )
        result = fi.reserve_for_connector_call("b1", "conn-A")
        assert result["approved"] is False

    def test_all_return_keys_present(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_connector_call("b1", "conn-X")
        expected_keys = {
            "budget_id", "connector_ref", "estimated_amount",
            "reservation_id", "disposition", "available_amount",
            "reason", "approved",
        }
        assert expected_keys <= set(result.keys())

    def test_connector_ref_echoed(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_connector_call("b1", "conn-Z")
        assert result["connector_ref"] == "conn-Z"

    def test_with_campaign_and_step_refs(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_connector_call(
            "b1", "conn-X", campaign_ref="camp-1", step_ref="step-5",
        )
        assert result["approved"] is True

    def test_disposition_is_string(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_connector_call("b1", "conn-X")
        assert isinstance(result["disposition"], str)

    def test_emits_events(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        before = len(es.list_events())
        fi.reserve_for_connector_call("b1", "conn-X")
        after = len(es.list_events())
        assert after > before


# ===================================================================
# 4. TestReserveForCommunication
# ===================================================================


class TestReserveForCommunication:

    def test_approved(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_communication("b1", "email", 10.0)
        assert result["approved"] is True

    def test_denied(self):
        fi, fe, es, mm = _setup(limit=5.0)
        result = fi.reserve_for_communication("b1", "sms", 50.0)
        assert result["approved"] is False

    def test_all_return_keys(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_communication("b1", "push", 10.0)
        expected_keys = {"budget_id", "channel", "reservation_id",
                         "disposition", "approved", "reason"}
        assert expected_keys <= set(result.keys())

    def test_channel_echoed(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_communication("b1", "slack", 5.0)
        assert result["channel"] == "slack"

    def test_budget_id_echoed(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_communication("b1", "email", 5.0)
        assert result["budget_id"] == "b1"

    def test_disposition_is_string(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_communication("b1", "email", 5.0)
        assert isinstance(result["disposition"], str)

    def test_approved_has_nonempty_reservation_id(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_communication("b1", "email", 5.0)
        assert result["reservation_id"] != ""

    def test_denied_has_empty_reservation_id(self):
        fi, fe, es, mm = _setup(limit=5.0)
        result = fi.reserve_for_communication("b1", "email", 50.0)
        assert result["reservation_id"] == ""

    def test_with_campaign_ref(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_communication("b1", "email", 5.0, campaign_ref="camp-2")
        assert result["approved"] is True


# ===================================================================
# 5. TestReserveForArtifactParsing
# ===================================================================


class TestReserveForArtifactParsing:

    def test_approved(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_artifact_parsing("b1", "doc-1", 20.0)
        assert result["approved"] is True

    def test_denied(self):
        fi, fe, es, mm = _setup(limit=10.0)
        result = fi.reserve_for_artifact_parsing("b1", "doc-1", 50.0)
        assert result["approved"] is False

    def test_all_return_keys(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_artifact_parsing("b1", "doc-1", 10.0)
        expected_keys = {"budget_id", "artifact_ref", "reservation_id",
                         "disposition", "approved", "reason"}
        assert expected_keys <= set(result.keys())

    def test_artifact_ref_echoed(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_artifact_parsing("b1", "pdf-99", 10.0)
        assert result["artifact_ref"] == "pdf-99"

    def test_disposition_is_string(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_artifact_parsing("b1", "doc-1", 10.0)
        assert isinstance(result["disposition"], str)

    def test_approved_reservation_id_nonempty(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_artifact_parsing("b1", "doc-1", 10.0)
        assert result["reservation_id"] != ""

    def test_denied_reservation_id_empty(self):
        fi, fe, es, mm = _setup(limit=5.0)
        result = fi.reserve_for_artifact_parsing("b1", "doc-1", 50.0)
        assert result["reservation_id"] == ""

    def test_with_campaign_ref(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_artifact_parsing("b1", "doc-1", 10.0, campaign_ref="camp-3")
        assert result["approved"] is True


# ===================================================================
# 6. TestReserveForProviderRouting
# ===================================================================


class TestReserveForProviderRouting:

    def test_approved(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_provider_routing("b1", "prov-1", 30.0)
        assert result["approved"] is True

    def test_denied(self):
        fi, fe, es, mm = _setup(limit=10.0)
        result = fi.reserve_for_provider_routing("b1", "prov-1", 50.0)
        assert result["approved"] is False

    def test_all_return_keys(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_provider_routing("b1", "prov-1", 10.0)
        expected_keys = {"budget_id", "provider_ref", "reservation_id",
                         "disposition", "approved", "reason"}
        assert expected_keys <= set(result.keys())

    def test_provider_ref_echoed(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_provider_routing("b1", "prov-X", 10.0)
        assert result["provider_ref"] == "prov-X"

    def test_disposition_is_string(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_provider_routing("b1", "prov-1", 10.0)
        assert isinstance(result["disposition"], str)

    def test_approved_reservation_id_nonempty(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_provider_routing("b1", "prov-1", 10.0)
        assert result["reservation_id"] != ""

    def test_denied_reservation_id_empty(self):
        fi, fe, es, mm = _setup(limit=5.0)
        result = fi.reserve_for_provider_routing("b1", "prov-1", 50.0)
        assert result["reservation_id"] == ""

    def test_with_campaign_ref(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_provider_routing("b1", "prov-1", 10.0, campaign_ref="camp-9")
        assert result["approved"] is True


# ===================================================================
# 7. TestBindBudgetToCampaign
# ===================================================================


class TestBindBudgetToCampaign:

    def test_creates_binding(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.bind_budget_to_campaign("b1", "camp-1", 500.0)
        assert result["binding_id"] != ""

    def test_all_return_keys_present(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.bind_budget_to_campaign("b1", "camp-1", 500.0)
        expected_keys = {"binding_id", "budget_id", "campaign_id",
                         "allocated_amount", "currency"}
        assert expected_keys <= set(result.keys())

    def test_budget_id_echoed(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.bind_budget_to_campaign("b1", "camp-1", 500.0)
        assert result["budget_id"] == "b1"

    def test_campaign_id_echoed(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.bind_budget_to_campaign("b1", "camp-99", 500.0)
        assert result["campaign_id"] == "camp-99"

    def test_allocated_amount_echoed(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.bind_budget_to_campaign("b1", "camp-1", 777.0)
        assert result["allocated_amount"] == 777.0

    def test_currency_present(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.bind_budget_to_campaign("b1", "camp-1", 500.0)
        assert result["currency"] == "USD"

    def test_emits_event(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        before = len(es.list_events())
        fi.bind_budget_to_campaign("b1", "camp-1", 500.0)
        after = len(es.list_events())
        assert after > before


# ===================================================================
# 8. TestBudgetGateForGovernance
# ===================================================================


class TestBudgetGateForGovernance:

    def test_approved(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.budget_gate_for_governance("b1", 100.0, "deploy action")
        assert result["allowed"] is True

    def test_denied_exceeds_limit(self):
        fi, fe, es, mm = _setup(limit=50.0)
        result = fi.budget_gate_for_governance("b1", 100.0, "big action")
        assert result["allowed"] is False

    def test_warning_case(self):
        fi, fe, es, mm = _setup(limit=100.0)
        # 85% utilization triggers warning (default threshold 0.8)
        result = fi.budget_gate_for_governance("b1", 85.0, "near limit")
        assert result["allowed"] is True
        assert result["disposition"] == "warning_issued"

    def test_approval_required_case(self):
        fi, fe, es, mm = _setup_with_approval(
            limit=1000.0, threshold_amount=50.0, approver="mgr-1",
        )
        result = fi.budget_gate_for_governance("b1", 200.0, "big spend")
        assert result["approval_required"] is True

    def test_all_return_keys_present(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.budget_gate_for_governance("b1", 50.0, "test")
        expected_keys = {
            "budget_id", "action_description", "disposition", "allowed",
            "requested_amount", "available_amount", "reason", "approval_required",
        }
        assert expected_keys <= set(result.keys())

    def test_action_description_echoed(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.budget_gate_for_governance("b1", 50.0, "my-action")
        assert result["action_description"] == "my-action"

    def test_requested_amount_echoed(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.budget_gate_for_governance("b1", 42.0)
        assert result["requested_amount"] == 42.0

    def test_disposition_is_string(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.budget_gate_for_governance("b1", 10.0)
        assert isinstance(result["disposition"], str)

    def test_emits_event(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        before = len(es.list_events())
        fi.budget_gate_for_governance("b1", 50.0, "test")
        after = len(es.list_events())
        assert after > before


# ===================================================================
# 9. TestBudgetGateForPortfolio
# ===================================================================


class TestBudgetGateForPortfolio:

    def test_all_feasible(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.budget_gate_for_portfolio(
            "b1", ["camp-1", "camp-2"], [100.0, 200.0],
        )
        assert result["all_feasible"] is True
        assert result["total_requested"] == 300.0

    def test_not_feasible(self):
        fi, fe, es, mm = _setup(limit=100.0)
        result = fi.budget_gate_for_portfolio(
            "b1", ["camp-1", "camp-2"], [80.0, 80.0],
        )
        assert result["all_feasible"] is False

    def test_mismatched_list_lengths_raises(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        with pytest.raises(RuntimeCoreInvariantError):
            fi.budget_gate_for_portfolio("b1", ["camp-1", "camp-2"], [100.0])

    def test_mismatched_list_lengths_more_amounts(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        with pytest.raises(RuntimeCoreInvariantError):
            fi.budget_gate_for_portfolio("b1", ["camp-1"], [100.0, 200.0])

    def test_empty_lists(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.budget_gate_for_portfolio("b1", [], [])
        assert result["all_feasible"] is True
        assert result["total_requested"] == 0.0

    def test_all_return_keys_present(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.budget_gate_for_portfolio(
            "b1", ["camp-1"], [50.0],
        )
        expected_keys = {
            "budget_id", "total_requested", "disposition", "all_feasible",
            "available_amount", "reason", "per_campaign", "approval_required",
        }
        assert expected_keys <= set(result.keys())

    def test_per_campaign_list(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.budget_gate_for_portfolio(
            "b1", ["camp-A", "camp-B", "camp-C"], [10.0, 20.0, 30.0],
        )
        assert len(result["per_campaign"]) == 3
        assert result["per_campaign"][0]["campaign_id"] == "camp-A"
        assert result["per_campaign"][1]["estimated_amount"] == 20.0

    def test_disposition_is_string(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.budget_gate_for_portfolio("b1", ["c1"], [10.0])
        assert isinstance(result["disposition"], str)

    def test_emits_event(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        before = len(es.list_events())
        fi.budget_gate_for_portfolio("b1", ["c1"], [10.0])
        after = len(es.list_events())
        assert after > before

    def test_single_campaign(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.budget_gate_for_portfolio("b1", ["camp-only"], [500.0])
        assert result["total_requested"] == 500.0
        assert len(result["per_campaign"]) == 1


# ===================================================================
# 10. TestAttachToMemoryMesh
# ===================================================================


class TestAttachToMemoryMesh:

    def test_creates_memory_record(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        mem = fi.attach_financial_record_to_memory_mesh("b1")
        assert mem is not None
        assert mem.memory_id != ""

    def test_deterministic_id(self):
        """The memory_id is derived from stable_identifier with no timestamp."""
        fi1, fe1, es1, mm1 = _setup(limit=1000.0)
        fi2, fe2, es2, mm2 = _setup(limit=1000.0)
        mem1 = fi1.attach_financial_record_to_memory_mesh("b1")
        mem2 = fi2.attach_financial_record_to_memory_mesh("b1")
        assert mem1.memory_id == mem2.memory_id

    def test_memory_id_is_stable(self):
        """Same budget_id always produces same memory_id."""
        fi, fe, es, mm = _setup(limit=1000.0)
        mem = fi.attach_financial_record_to_memory_mesh("b1")
        from mcoi_runtime.core.invariants import stable_identifier
        expected_id = stable_identifier("mem-fin", {"id": "b1"})
        assert mem.memory_id == expected_id

    def test_duplicate_raises(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        fi.attach_financial_record_to_memory_mesh("b1")
        with pytest.raises(Exception):
            fi.attach_financial_record_to_memory_mesh("b1")

    def test_content_contains_budget_info(self):
        fi, fe, es, mm = _setup(limit=500.0)
        mem = fi.attach_financial_record_to_memory_mesh("b1")
        content = mem.content
        assert content["budget_id"] == "b1"
        assert content["limit_amount"] == 500.0

    def test_memory_has_financial_tags(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        mem = fi.attach_financial_record_to_memory_mesh("b1")
        assert "financial" in mem.tags
        assert "budget" in mem.tags

    def test_emits_event(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        before = len(es.list_events())
        fi.attach_financial_record_to_memory_mesh("b1")
        after = len(es.list_events())
        assert after > before

    def test_memory_scope_ref_id_is_budget_id(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        mem = fi.attach_financial_record_to_memory_mesh("b1")
        assert mem.scope_ref_id == "b1"


# ===================================================================
# 11. TestAttachToGraph
# ===================================================================


class TestAttachToGraph:

    def test_all_keys_present(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.attach_financial_record_to_graph("b1")
        expected_keys = {
            "budget_id", "name", "scope", "limit_amount",
            "consumed_amount", "reserved_amount", "available_amount",
            "utilization", "currency", "active",
            "warning_triggered", "hard_stop_triggered",
            "conflicts", "bindings", "active_reservations",
        }
        assert expected_keys <= set(result.keys())

    def test_reflects_budget_state_initial(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.attach_financial_record_to_graph("b1")
        assert result["budget_id"] == "b1"
        assert result["limit_amount"] == 1000.0
        assert result["consumed_amount"] == 0.0
        assert result["available_amount"] == 1000.0
        assert result["active"] is True

    def test_reflects_budget_state_after_reservation(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        fi.reserve_for_campaign_step("b1", "camp-1", "step-1", 200.0)
        result = fi.attach_financial_record_to_graph("b1")
        assert result["reserved_amount"] == 200.0
        assert result["available_amount"] == 800.0

    def test_name_and_scope_present(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.attach_financial_record_to_graph("b1")
        assert result["name"] == "Test Budget"
        assert result["scope"] == "campaign"

    def test_currency(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.attach_financial_record_to_graph("b1")
        assert result["currency"] == "USD"

    def test_conflicts_count(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.attach_financial_record_to_graph("b1")
        assert isinstance(result["conflicts"], int)
        assert result["conflicts"] == 0

    def test_bindings_count_after_binding(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        fi.bind_budget_to_campaign("b1", "camp-1", 500.0)
        result = fi.attach_financial_record_to_graph("b1")
        assert result["bindings"] == 1

    def test_active_reservations_count(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        fi.reserve_for_campaign_step("b1", "camp-1", "step-1", 50.0)
        fi.reserve_for_communication("b1", "email", 10.0)
        result = fi.attach_financial_record_to_graph("b1")
        assert result["active_reservations"] == 2

    def test_utilization_initially_zero(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.attach_financial_record_to_graph("b1")
        assert result["utilization"] == 0.0

    def test_warning_triggered_false_initially(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.attach_financial_record_to_graph("b1")
        assert result["warning_triggered"] is False

    def test_hard_stop_triggered_false_initially(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.attach_financial_record_to_graph("b1")
        assert result["hard_stop_triggered"] is False


# ===================================================================
# 12. TestEventEmission
# ===================================================================


class TestEventEmission:
    """Every bridge method should emit at least one event."""

    def test_reserve_for_campaign_step_emits(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        before = len(es.list_events())
        fi.reserve_for_campaign_step("b1", "camp-1", "step-1", 50.0)
        assert len(es.list_events()) > before

    def test_reserve_for_connector_call_emits(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        before = len(es.list_events())
        fi.reserve_for_connector_call("b1", "conn-X")
        assert len(es.list_events()) > before

    def test_reserve_for_communication_emits(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        before = len(es.list_events())
        fi.reserve_for_communication("b1", "email", 10.0)
        assert len(es.list_events()) > before

    def test_reserve_for_artifact_parsing_emits(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        before = len(es.list_events())
        fi.reserve_for_artifact_parsing("b1", "doc-1", 10.0)
        assert len(es.list_events()) > before

    def test_reserve_for_provider_routing_emits(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        before = len(es.list_events())
        fi.reserve_for_provider_routing("b1", "prov-1", 10.0)
        assert len(es.list_events()) > before

    def test_bind_budget_to_campaign_emits(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        before = len(es.list_events())
        fi.bind_budget_to_campaign("b1", "camp-1", 500.0)
        assert len(es.list_events()) > before

    def test_budget_gate_for_governance_emits(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        before = len(es.list_events())
        fi.budget_gate_for_governance("b1", 50.0, "test")
        assert len(es.list_events()) > before

    def test_budget_gate_for_portfolio_emits(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        before = len(es.list_events())
        fi.budget_gate_for_portfolio("b1", ["c1"], [10.0])
        assert len(es.list_events()) > before

    def test_attach_financial_record_to_memory_mesh_emits(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        before = len(es.list_events())
        fi.attach_financial_record_to_memory_mesh("b1")
        assert len(es.list_events()) > before

    def test_denied_reservation_still_emits(self):
        fi, fe, es, mm = _setup(limit=5.0)
        before = len(es.list_events())
        fi.reserve_for_campaign_step("b1", "camp-1", "step-1", 100.0)
        assert len(es.list_events()) > before

    def test_denied_governance_gate_still_emits(self):
        fi, fe, es, mm = _setup(limit=5.0)
        before = len(es.list_events())
        fi.budget_gate_for_governance("b1", 100.0)
        assert len(es.list_events()) > before


# ===================================================================
# 13. TestDispositionSerialization
# ===================================================================


class TestDispositionSerialization:
    """All disposition fields must be plain strings, never enum instances."""

    def test_campaign_step_approved_disposition_type(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_campaign_step("b1", "camp-1", "step-1", 10.0)
        assert isinstance(result["disposition"], str)
        assert not isinstance(result["disposition"], ChargeDisposition)

    def test_campaign_step_denied_disposition_type(self):
        fi, fe, es, mm = _setup(limit=5.0)
        result = fi.reserve_for_campaign_step("b1", "camp-1", "step-1", 100.0)
        assert isinstance(result["disposition"], str)
        assert not isinstance(result["disposition"], ChargeDisposition)

    def test_connector_call_disposition_type(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_connector_call("b1", "conn-X")
        assert isinstance(result["disposition"], str)
        assert not isinstance(result["disposition"], ChargeDisposition)

    def test_communication_disposition_type(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_communication("b1", "email", 5.0)
        assert isinstance(result["disposition"], str)
        assert not isinstance(result["disposition"], ChargeDisposition)

    def test_artifact_parsing_disposition_type(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_artifact_parsing("b1", "doc-1", 5.0)
        assert isinstance(result["disposition"], str)
        assert not isinstance(result["disposition"], ChargeDisposition)

    def test_provider_routing_disposition_type(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_provider_routing("b1", "prov-1", 5.0)
        assert isinstance(result["disposition"], str)
        assert not isinstance(result["disposition"], ChargeDisposition)

    def test_governance_gate_disposition_type(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.budget_gate_for_governance("b1", 10.0)
        assert isinstance(result["disposition"], str)
        assert not isinstance(result["disposition"], ChargeDisposition)

    def test_portfolio_gate_disposition_type(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.budget_gate_for_portfolio("b1", ["c1"], [10.0])
        assert isinstance(result["disposition"], str)
        assert not isinstance(result["disposition"], ChargeDisposition)

    def test_approved_disposition_value(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.budget_gate_for_governance("b1", 10.0)
        assert result["disposition"] == "approved"

    def test_denied_hard_stop_disposition_value(self):
        fi, fe, es, mm = _setup(limit=10.0)
        result = fi.budget_gate_for_governance("b1", 100.0)
        assert result["disposition"] in ("denied_hard_stop", "denied_insufficient")

    def test_warning_issued_disposition_value(self):
        fi, fe, es, mm = _setup(limit=100.0)
        result = fi.budget_gate_for_governance("b1", 85.0)
        assert result["disposition"] == "warning_issued"

    def test_pending_approval_disposition_value(self):
        fi, fe, es, mm = _setup_with_approval(
            limit=1000.0, threshold_amount=50.0, approver="mgr-1",
        )
        result = fi.budget_gate_for_governance("b1", 200.0)
        assert result["disposition"] == "pending_approval"


class TestBoundedContracts:
    def test_campaign_step_reservation_reason_redacts_step_ref(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_campaign_step("b1", "camp-1", "step-secret", 100.0)
        reservation = fe.get_active_reservations("b1")[0]
        assert result["step_ref"] == "step-secret"
        assert reservation.reason == "campaign step budget reservation"
        assert "step-secret" not in reservation.reason

    def test_connector_reservation_reason_redacts_connector_ref(self):
        fi, fe, es, mm = _setup_with_connector_profile(limit=1000.0, connector_ref="conn-secret")
        result = fi.reserve_for_connector_call("b1", "conn-secret", units=2)
        reservation = fe.get_active_reservations("b1")[0]
        assert result["connector_ref"] == "conn-secret"
        assert reservation.reason == "connector call budget reservation"
        assert "conn-secret" not in reservation.reason

    def test_communication_reservation_reason_redacts_channel(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_communication("b1", "slack-secret", 10.0)
        reservation = fe.get_active_reservations("b1")[0]
        assert result["channel"] == "slack-secret"
        assert reservation.reason == "communication budget reservation"
        assert "slack-secret" not in reservation.reason

    def test_artifact_reservation_reason_redacts_artifact_ref(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_artifact_parsing("b1", "artifact-secret", 10.0)
        reservation = fe.get_active_reservations("b1")[0]
        assert result["artifact_ref"] == "artifact-secret"
        assert reservation.reason == "artifact parsing budget reservation"
        assert "artifact-secret" not in reservation.reason

    def test_provider_reservation_reason_redacts_provider_ref(self):
        fi, fe, es, mm = _setup(limit=1000.0)
        result = fi.reserve_for_provider_routing("b1", "provider-secret", 10.0)
        reservation = fe.get_active_reservations("b1")[0]
        assert result["provider_ref"] == "provider-secret"
        assert reservation.reason == "provider routing budget reservation"
        assert "provider-secret" not in reservation.reason

    def test_memory_title_redacts_budget_id(self):
        fi, fe, es, mm = _setup(limit=1000.0, budget_id="budget-secret")
        mem = fi.attach_financial_record_to_memory_mesh("budget-secret")
        assert mem.title == "Financial state"
        assert "budget-secret" not in mem.title
