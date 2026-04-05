"""Tests for financial / cost / budget runtime contracts.

Covers all 6 enums and 12 dataclasses in
``mcoi_runtime.contracts.financial_runtime``.
"""

from __future__ import annotations

import dataclasses

import pytest

from mcoi_runtime.contracts.financial_runtime import (
    ApprovalThreshold,
    ApprovalThresholdMode,
    BudgetClosureReport,
    BudgetConflict,
    BudgetConflictKind,
    BudgetDecision,
    BudgetEnvelope,
    BudgetReservation,
    BudgetScope,
    CampaignBudgetBinding,
    ChargeDisposition,
    ConnectorCostProfile,
    CostCategory,
    CostEstimate,
    FinancialHealthSnapshot,
    SpendForecast,
    SpendRecord,
    SpendStatus,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DT = "2025-01-01T00:00:00+00:00"
DT2 = "2025-06-15T12:30:00+00:00"
BAD_DT = "not-a-datetime"


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def _budget(**overrides) -> BudgetEnvelope:
    defaults = dict(
        budget_id="bud-1",
        name="Q1 budget",
        scope=BudgetScope.CAMPAIGN,
        scope_ref_id="camp-1",
        currency="USD",
        limit_amount=1000.0,
        reserved_amount=100.0,
        consumed_amount=200.0,
        warning_threshold=0.8,
        hard_stop_threshold=1.0,
        active=True,
        tags=("marketing",),
        created_at=DT,
        updated_at=DT,
        metadata={"region": "us-east"},
    )
    defaults.update(overrides)
    return BudgetEnvelope(**defaults)


def _spend(**overrides) -> SpendRecord:
    defaults = dict(
        spend_id="sp-1",
        budget_id="bud-1",
        category=CostCategory.CONNECTOR_CALL,
        status=SpendStatus.CONSUMED,
        amount=50.0,
        currency="USD",
        campaign_ref="camp-1",
        step_ref="step-1",
        connector_ref="conn-1",
        reason="API call",
        created_at=DT,
    )
    defaults.update(overrides)
    return SpendRecord(**defaults)


def _estimate(**overrides) -> CostEstimate:
    defaults = dict(
        estimate_id="est-1",
        category=CostCategory.COMPUTE,
        estimated_amount=10.0,
        currency="USD",
        confidence=0.9,
        connector_ref="conn-1",
        campaign_ref="camp-1",
        step_ref="step-1",
        created_at=DT,
    )
    defaults.update(overrides)
    return CostEstimate(**defaults)


def _profile(**overrides) -> ConnectorCostProfile:
    defaults = dict(
        profile_id="prof-1",
        connector_ref="conn-1",
        cost_per_call=0.01,
        cost_per_unit=0.005,
        currency="USD",
        unit_name="call",
        monthly_minimum=0.0,
        monthly_cap=500.0,
        tier="standard",
        created_at=DT,
        metadata={"vendor": "acme"},
    )
    defaults.update(overrides)
    return ConnectorCostProfile(**defaults)


def _binding(**overrides) -> CampaignBudgetBinding:
    defaults = dict(
        binding_id="bind-1",
        campaign_id="camp-1",
        budget_id="bud-1",
        allocated_amount=500.0,
        consumed_amount=100.0,
        currency="USD",
        active=True,
        created_at=DT,
    )
    defaults.update(overrides)
    return CampaignBudgetBinding(**defaults)


def _threshold(**overrides) -> ApprovalThreshold:
    defaults = dict(
        threshold_id="thr-1",
        budget_id="bud-1",
        mode=ApprovalThresholdMode.PER_TRANSACTION,
        amount=100.0,
        currency="USD",
        approver_ref="approver-1",
        auto_approve_below=50.0,
        created_at=DT,
    )
    defaults.update(overrides)
    return ApprovalThreshold(**defaults)


def _reservation(**overrides) -> BudgetReservation:
    defaults = dict(
        reservation_id="res-1",
        budget_id="bud-1",
        amount=75.0,
        currency="USD",
        category=CostCategory.CONNECTOR_CALL,
        campaign_ref="camp-1",
        step_ref="step-1",
        connector_ref="conn-1",
        active=True,
        reason="hold for API call",
        created_at=DT,
        expires_at=DT2,
    )
    defaults.update(overrides)
    return BudgetReservation(**defaults)


def _forecast(**overrides) -> SpendForecast:
    defaults = dict(
        forecast_id="fc-1",
        budget_id="bud-1",
        projected_amount=800.0,
        currency="USD",
        period_start=DT,
        period_end=DT2,
        confidence=0.85,
        breakdown={"connector_call": 500.0, "compute": 300.0},
        created_at=DT,
    )
    defaults.update(overrides)
    return SpendForecast(**defaults)


def _conflict(**overrides) -> BudgetConflict:
    defaults = dict(
        conflict_id="conf-1",
        budget_id="bud-1",
        kind=BudgetConflictKind.OVER_LIMIT,
        description="Exceeded limit",
        severity=3,
        detected_at=DT,
    )
    defaults.update(overrides)
    return BudgetConflict(**defaults)


def _decision(**overrides) -> BudgetDecision:
    defaults = dict(
        decision_id="dec-1",
        budget_id="bud-1",
        disposition=ChargeDisposition.APPROVED,
        requested_amount=50.0,
        available_amount=900.0,
        currency="USD",
        reason="within limits",
        reservation_id="res-1",
        approval_required=False,
        approver_ref="",
        decided_at=DT,
    )
    defaults.update(overrides)
    return BudgetDecision(**defaults)


def _snapshot(**overrides) -> FinancialHealthSnapshot:
    defaults = dict(
        snapshot_id="snap-1",
        budget_id="bud-1",
        limit_amount=1000.0,
        consumed_amount=300.0,
        reserved_amount=100.0,
        available_amount=600.0,
        utilization=0.4,
        currency="USD",
        warning_triggered=False,
        hard_stop_triggered=False,
        active_reservations=2,
        total_spend_records=15,
        captured_at=DT,
    )
    defaults.update(overrides)
    return FinancialHealthSnapshot(**defaults)


def _closure(**overrides) -> BudgetClosureReport:
    defaults = dict(
        report_id="rpt-1",
        budget_id="bud-1",
        limit_amount=1000.0,
        total_consumed=800.0,
        total_released=50.0,
        total_reservations=5,
        total_spend_records=20,
        currency="USD",
        under_budget=True,
        overspend_amount=0.0,
        warnings_issued=2,
        hard_stops_triggered=0,
        closed_at=DT,
    )
    defaults.update(overrides)
    return BudgetClosureReport(**defaults)


# ===================================================================
# Enum tests
# ===================================================================


class TestBudgetScope:
    def test_member_count(self):
        assert len(BudgetScope) == 7

    def test_values(self):
        expected = {"global", "portfolio", "campaign", "connector", "channel", "team", "function"}
        assert {m.value for m in BudgetScope} == expected


class TestCostCategory:
    def test_member_count(self):
        assert len(CostCategory) == 8

    def test_values(self):
        expected = {
            "connector_call", "communication", "artifact_parsing",
            "provider_routing", "compute", "human_labor", "escalation", "overhead",
        }
        assert {m.value for m in CostCategory} == expected


class TestSpendStatus:
    def test_member_count(self):
        assert len(SpendStatus) == 5

    def test_values(self):
        expected = {"reserved", "consumed", "released", "cancelled", "refunded"}
        assert {m.value for m in SpendStatus} == expected


class TestApprovalThresholdMode:
    def test_member_count(self):
        assert len(ApprovalThresholdMode) == 4

    def test_values(self):
        expected = {"per_transaction", "cumulative", "percentage_of_limit", "remaining_budget"}
        assert {m.value for m in ApprovalThresholdMode} == expected


class TestChargeDisposition:
    def test_member_count(self):
        assert len(ChargeDisposition) == 6

    def test_values(self):
        expected = {
            "approved", "denied_hard_stop", "denied_insufficient",
            "pending_approval", "warning_issued", "fallback_suggested",
        }
        assert {m.value for m in ChargeDisposition} == expected


class TestBudgetConflictKind:
    def test_member_count(self):
        assert len(BudgetConflictKind) == 6

    def test_values(self):
        expected = {
            "over_limit", "currency_mismatch", "double_reservation",
            "orphaned_reservation", "negative_balance", "threshold_breach",
        }
        assert {m.value for m in BudgetConflictKind} == expected


# ===================================================================
# BudgetEnvelope
# ===================================================================


class TestBudgetEnvelope:
    def test_valid_construction(self):
        b = _budget()
        assert b.budget_id == "bud-1"
        assert b.name == "Q1 budget"
        assert b.scope is BudgetScope.CAMPAIGN
        assert b.currency == "USD"
        assert b.limit_amount == 1000.0
        assert b.active is True

    def test_id_empty_raises(self):
        with pytest.raises(ValueError, match="budget_id"):
            _budget(budget_id="")

    def test_name_empty_raises(self):
        with pytest.raises(ValueError, match="name"):
            _budget(name="")

    def test_scope_ref_id_empty_raises(self):
        with pytest.raises(ValueError, match="scope_ref_id"):
            _budget(scope_ref_id="")

    def test_frozen_immutability(self):
        b = _budget()
        with pytest.raises(dataclasses.FrozenInstanceError):
            b.budget_id = "other"  # type: ignore[misc]

    def test_to_dict_preserves_enum(self):
        d = _budget().to_dict()
        assert d["scope"] is BudgetScope.CAMPAIGN

    def test_to_dict_all_keys(self):
        d = _budget().to_dict()
        expected_keys = {
            "budget_id", "name", "scope", "scope_ref_id", "currency",
            "limit_amount", "reserved_amount", "consumed_amount",
            "warning_threshold", "hard_stop_threshold", "active", "tags",
            "created_at", "updated_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_consumed_plus_reserved_exceeds_limit_raises(self):
        with pytest.raises(ValueError) as exc:
            _budget(consumed_amount=600.0, reserved_amount=500.0, limit_amount=1000.0)
        assert str(exc.value) == "consumed and reserved amounts exceed limit"
        assert "600.0" not in str(exc.value)
        assert "500.0" not in str(exc.value)
        assert "1000.0" not in str(exc.value)

    def test_consumed_plus_reserved_equals_limit_ok(self):
        b = _budget(consumed_amount=500.0, reserved_amount=500.0, limit_amount=1000.0)
        assert b.consumed_amount + b.reserved_amount == b.limit_amount

    def test_warning_exceeds_hard_stop_raises(self):
        with pytest.raises(ValueError) as exc:
            _budget(warning_threshold=0.95, hard_stop_threshold=0.9)
        assert str(exc.value) == "warning threshold must not exceed hard stop threshold"
        assert "0.95" not in str(exc.value)
        assert "0.9" not in str(exc.value)

    def test_warning_equals_hard_stop_ok(self):
        b = _budget(warning_threshold=0.9, hard_stop_threshold=0.9)
        assert b.warning_threshold == b.hard_stop_threshold

    def test_negative_limit_raises(self):
        with pytest.raises(ValueError, match="limit_amount"):
            _budget(limit_amount=-1.0)

    def test_negative_reserved_raises(self):
        with pytest.raises(ValueError, match="reserved_amount"):
            _budget(reserved_amount=-1.0)

    def test_negative_consumed_raises(self):
        with pytest.raises(ValueError, match="consumed_amount"):
            _budget(consumed_amount=-1.0)

    def test_currency_lowercase_raises(self):
        with pytest.raises(ValueError) as exc:
            _budget(currency="usd")
        assert str(exc.value) == "currency must be a 3-letter uppercase code"
        assert "usd" not in str(exc.value)

    def test_currency_two_letters_raises(self):
        with pytest.raises(ValueError, match="currency"):
            _budget(currency="US")

    def test_currency_four_letters_raises(self):
        with pytest.raises(ValueError, match="currency"):
            _budget(currency="USDD")

    def test_currency_digits_raises(self):
        with pytest.raises(ValueError, match="currency"):
            _budget(currency="12A")

    def test_bad_created_at_raises(self):
        with pytest.raises(ValueError, match="created_at"):
            _budget(created_at=BAD_DT)

    def test_bad_updated_at_raises(self):
        with pytest.raises(ValueError, match="updated_at"):
            _budget(updated_at=BAD_DT)

    def test_metadata_frozen(self):
        b = _budget()
        with pytest.raises(TypeError):
            b.metadata["new"] = "val"  # type: ignore[index]

    def test_tags_in_dict_are_list(self):
        d = _budget().to_dict()
        assert isinstance(d["tags"], list)

    def test_all_scopes_accepted(self):
        for scope in BudgetScope:
            b = _budget(scope=scope)
            assert b.scope is scope


# ===================================================================
# SpendRecord
# ===================================================================


class TestSpendRecord:
    def test_valid_construction(self):
        s = _spend()
        assert s.spend_id == "sp-1"
        assert s.category is CostCategory.CONNECTOR_CALL
        assert s.status is SpendStatus.CONSUMED
        assert s.amount == 50.0

    def test_id_empty_raises(self):
        with pytest.raises(ValueError, match="spend_id"):
            _spend(spend_id="")

    def test_budget_id_empty_raises(self):
        with pytest.raises(ValueError, match="budget_id"):
            _spend(budget_id="")

    def test_frozen_immutability(self):
        s = _spend()
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.spend_id = "other"  # type: ignore[misc]

    def test_to_dict_preserves_enum(self):
        d = _spend().to_dict()
        assert d["category"] is CostCategory.CONNECTOR_CALL
        assert d["status"] is SpendStatus.CONSUMED

    def test_to_dict_all_keys(self):
        d = _spend().to_dict()
        expected_keys = {
            "spend_id", "budget_id", "category", "status", "amount",
            "currency", "campaign_ref", "step_ref", "connector_ref",
            "reason", "created_at",
        }
        assert set(d.keys()) == expected_keys

    def test_negative_amount_raises(self):
        with pytest.raises(ValueError, match="amount"):
            _spend(amount=-1.0)

    def test_currency_lowercase_raises(self):
        with pytest.raises(ValueError, match="currency"):
            _spend(currency="usd")

    def test_bad_created_at_raises(self):
        with pytest.raises(ValueError, match="created_at"):
            _spend(created_at=BAD_DT)

    def test_all_categories_accepted(self):
        for cat in CostCategory:
            s = _spend(category=cat)
            assert s.category is cat

    def test_all_statuses_accepted(self):
        for st in SpendStatus:
            s = _spend(status=st)
            assert s.status is st


# ===================================================================
# CostEstimate
# ===================================================================


class TestCostEstimate:
    def test_valid_construction(self):
        e = _estimate()
        assert e.estimate_id == "est-1"
        assert e.category is CostCategory.COMPUTE
        assert e.confidence == 0.9

    def test_id_empty_raises(self):
        with pytest.raises(ValueError, match="estimate_id"):
            _estimate(estimate_id="")

    def test_frozen_immutability(self):
        e = _estimate()
        with pytest.raises(dataclasses.FrozenInstanceError):
            e.estimate_id = "other"  # type: ignore[misc]

    def test_to_dict_preserves_enum(self):
        d = _estimate().to_dict()
        assert d["category"] is CostCategory.COMPUTE

    def test_to_dict_all_keys(self):
        d = _estimate().to_dict()
        expected_keys = {
            "estimate_id", "category", "estimated_amount", "currency",
            "confidence", "connector_ref", "campaign_ref", "step_ref", "created_at",
        }
        assert set(d.keys()) == expected_keys

    def test_negative_amount_raises(self):
        with pytest.raises(ValueError, match="estimated_amount"):
            _estimate(estimated_amount=-0.01)

    def test_confidence_above_one_raises(self):
        with pytest.raises(ValueError, match="confidence"):
            _estimate(confidence=1.1)

    def test_confidence_below_zero_raises(self):
        with pytest.raises(ValueError, match="confidence"):
            _estimate(confidence=-0.1)

    def test_confidence_zero_ok(self):
        e = _estimate(confidence=0.0)
        assert e.confidence == 0.0

    def test_confidence_one_ok(self):
        e = _estimate(confidence=1.0)
        assert e.confidence == 1.0

    def test_currency_lowercase_raises(self):
        with pytest.raises(ValueError, match="currency"):
            _estimate(currency="eur")

    def test_bad_created_at_raises(self):
        with pytest.raises(ValueError, match="created_at"):
            _estimate(created_at=BAD_DT)


# ===================================================================
# ConnectorCostProfile
# ===================================================================


class TestConnectorCostProfile:
    def test_valid_construction(self):
        p = _profile()
        assert p.profile_id == "prof-1"
        assert p.connector_ref == "conn-1"
        assert p.cost_per_call == 0.01

    def test_id_empty_raises(self):
        with pytest.raises(ValueError, match="profile_id"):
            _profile(profile_id="")

    def test_connector_ref_empty_raises(self):
        with pytest.raises(ValueError, match="connector_ref"):
            _profile(connector_ref="")

    def test_frozen_immutability(self):
        p = _profile()
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.profile_id = "other"  # type: ignore[misc]

    def test_to_dict_all_keys(self):
        d = _profile().to_dict()
        expected_keys = {
            "profile_id", "connector_ref", "cost_per_call", "cost_per_unit",
            "currency", "unit_name", "monthly_minimum", "monthly_cap",
            "tier", "created_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_negative_cost_per_call_raises(self):
        with pytest.raises(ValueError, match="cost_per_call"):
            _profile(cost_per_call=-0.01)

    def test_negative_cost_per_unit_raises(self):
        with pytest.raises(ValueError, match="cost_per_unit"):
            _profile(cost_per_unit=-1.0)

    def test_negative_monthly_minimum_raises(self):
        with pytest.raises(ValueError, match="monthly_minimum"):
            _profile(monthly_minimum=-1.0)

    def test_negative_monthly_cap_raises(self):
        with pytest.raises(ValueError, match="monthly_cap"):
            _profile(monthly_cap=-1.0)

    def test_currency_lowercase_raises(self):
        with pytest.raises(ValueError, match="currency"):
            _profile(currency="gbp")

    def test_bad_created_at_raises(self):
        with pytest.raises(ValueError, match="created_at"):
            _profile(created_at=BAD_DT)

    def test_unit_name_empty_raises(self):
        with pytest.raises(ValueError, match="unit_name"):
            _profile(unit_name="")

    def test_metadata_frozen(self):
        p = _profile()
        with pytest.raises(TypeError):
            p.metadata["new"] = "val"  # type: ignore[index]


# ===================================================================
# CampaignBudgetBinding
# ===================================================================


class TestCampaignBudgetBinding:
    def test_valid_construction(self):
        b = _binding()
        assert b.binding_id == "bind-1"
        assert b.campaign_id == "camp-1"
        assert b.active is True

    def test_id_empty_raises(self):
        with pytest.raises(ValueError, match="binding_id"):
            _binding(binding_id="")

    def test_campaign_id_empty_raises(self):
        with pytest.raises(ValueError, match="campaign_id"):
            _binding(campaign_id="")

    def test_budget_id_empty_raises(self):
        with pytest.raises(ValueError, match="budget_id"):
            _binding(budget_id="")

    def test_frozen_immutability(self):
        b = _binding()
        with pytest.raises(dataclasses.FrozenInstanceError):
            b.binding_id = "other"  # type: ignore[misc]

    def test_to_dict_all_keys(self):
        d = _binding().to_dict()
        expected_keys = {
            "binding_id", "campaign_id", "budget_id", "allocated_amount",
            "consumed_amount", "currency", "active", "created_at",
        }
        assert set(d.keys()) == expected_keys

    def test_consumed_exceeds_allocated_raises(self):
        with pytest.raises(ValueError) as exc:
            _binding(consumed_amount=600.0, allocated_amount=500.0)
        assert str(exc.value) == "consumed amount must not exceed allocated amount"
        assert "600.0" not in str(exc.value)
        assert "500.0" not in str(exc.value)

    def test_consumed_equals_allocated_ok(self):
        b = _binding(consumed_amount=500.0, allocated_amount=500.0)
        assert b.consumed_amount == b.allocated_amount

    def test_negative_allocated_raises(self):
        with pytest.raises(ValueError, match="allocated_amount"):
            _binding(allocated_amount=-1.0)

    def test_negative_consumed_raises(self):
        with pytest.raises(ValueError, match="consumed_amount"):
            _binding(consumed_amount=-1.0)

    def test_currency_lowercase_raises(self):
        with pytest.raises(ValueError, match="currency"):
            _binding(currency="usd")

    def test_bad_created_at_raises(self):
        with pytest.raises(ValueError, match="created_at"):
            _binding(created_at=BAD_DT)


# ===================================================================
# ApprovalThreshold
# ===================================================================


class TestApprovalThreshold:
    def test_valid_construction(self):
        t = _threshold()
        assert t.threshold_id == "thr-1"
        assert t.mode is ApprovalThresholdMode.PER_TRANSACTION
        assert t.amount == 100.0
        assert t.auto_approve_below == 50.0

    def test_id_empty_raises(self):
        with pytest.raises(ValueError, match="threshold_id"):
            _threshold(threshold_id="")

    def test_budget_id_empty_raises(self):
        with pytest.raises(ValueError, match="budget_id"):
            _threshold(budget_id="")

    def test_approver_ref_empty_raises(self):
        with pytest.raises(ValueError, match="approver_ref"):
            _threshold(approver_ref="")

    def test_frozen_immutability(self):
        t = _threshold()
        with pytest.raises(dataclasses.FrozenInstanceError):
            t.threshold_id = "other"  # type: ignore[misc]

    def test_to_dict_preserves_enum(self):
        d = _threshold().to_dict()
        assert d["mode"] is ApprovalThresholdMode.PER_TRANSACTION

    def test_to_dict_all_keys(self):
        d = _threshold().to_dict()
        expected_keys = {
            "threshold_id", "budget_id", "mode", "amount", "currency",
            "approver_ref", "auto_approve_below", "created_at",
        }
        assert set(d.keys()) == expected_keys

    def test_auto_approve_exceeds_amount_raises(self):
        with pytest.raises(ValueError) as exc:
            _threshold(auto_approve_below=150.0, amount=100.0)
        assert str(exc.value) == "auto-approve threshold must not exceed approval amount"
        assert "150.0" not in str(exc.value)
        assert "100.0" not in str(exc.value)

    def test_auto_approve_equals_amount_ok(self):
        t = _threshold(auto_approve_below=100.0, amount=100.0)
        assert t.auto_approve_below == t.amount

    def test_negative_amount_raises(self):
        with pytest.raises(ValueError, match="amount"):
            _threshold(amount=-1.0)

    def test_negative_auto_approve_raises(self):
        with pytest.raises(ValueError, match="auto_approve_below"):
            _threshold(auto_approve_below=-1.0)

    def test_currency_lowercase_raises(self):
        with pytest.raises(ValueError, match="currency"):
            _threshold(currency="usd")

    def test_bad_created_at_raises(self):
        with pytest.raises(ValueError, match="created_at"):
            _threshold(created_at=BAD_DT)

    def test_all_modes_accepted(self):
        for mode in ApprovalThresholdMode:
            t = _threshold(mode=mode)
            assert t.mode is mode


# ===================================================================
# BudgetReservation
# ===================================================================


class TestBudgetReservation:
    def test_valid_construction(self):
        r = _reservation()
        assert r.reservation_id == "res-1"
        assert r.budget_id == "bud-1"
        assert r.amount == 75.0
        assert r.active is True

    def test_id_empty_raises(self):
        with pytest.raises(ValueError, match="reservation_id"):
            _reservation(reservation_id="")

    def test_budget_id_empty_raises(self):
        with pytest.raises(ValueError, match="budget_id"):
            _reservation(budget_id="")

    def test_frozen_immutability(self):
        r = _reservation()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.reservation_id = "other"  # type: ignore[misc]

    def test_to_dict_preserves_enum(self):
        d = _reservation().to_dict()
        assert d["category"] is CostCategory.CONNECTOR_CALL

    def test_to_dict_all_keys(self):
        d = _reservation().to_dict()
        expected_keys = {
            "reservation_id", "budget_id", "amount", "currency", "category",
            "campaign_ref", "step_ref", "connector_ref", "active", "reason",
            "created_at", "expires_at",
        }
        assert set(d.keys()) == expected_keys

    def test_negative_amount_raises(self):
        with pytest.raises(ValueError, match="amount"):
            _reservation(amount=-1.0)

    def test_currency_lowercase_raises(self):
        with pytest.raises(ValueError, match="currency"):
            _reservation(currency="usd")

    def test_bad_created_at_raises(self):
        with pytest.raises(ValueError, match="created_at"):
            _reservation(created_at=BAD_DT)

    def test_all_categories_accepted(self):
        for cat in CostCategory:
            r = _reservation(category=cat)
            assert r.category is cat


# ===================================================================
# SpendForecast
# ===================================================================


class TestSpendForecast:
    def test_valid_construction(self):
        f = _forecast()
        assert f.forecast_id == "fc-1"
        assert f.projected_amount == 800.0
        assert f.confidence == 0.85

    def test_id_empty_raises(self):
        with pytest.raises(ValueError, match="forecast_id"):
            _forecast(forecast_id="")

    def test_budget_id_empty_raises(self):
        with pytest.raises(ValueError, match="budget_id"):
            _forecast(budget_id="")

    def test_frozen_immutability(self):
        f = _forecast()
        with pytest.raises(dataclasses.FrozenInstanceError):
            f.forecast_id = "other"  # type: ignore[misc]

    def test_to_dict_all_keys(self):
        d = _forecast().to_dict()
        expected_keys = {
            "forecast_id", "budget_id", "projected_amount", "currency",
            "period_start", "period_end", "confidence", "breakdown", "created_at",
        }
        assert set(d.keys()) == expected_keys

    def test_negative_projected_raises(self):
        with pytest.raises(ValueError, match="projected_amount"):
            _forecast(projected_amount=-1.0)

    def test_confidence_above_one_raises(self):
        with pytest.raises(ValueError, match="confidence"):
            _forecast(confidence=1.1)

    def test_confidence_below_zero_raises(self):
        with pytest.raises(ValueError, match="confidence"):
            _forecast(confidence=-0.1)

    def test_period_start_after_end_raises(self):
        with pytest.raises(ValueError) as exc:
            _forecast(period_start=DT2, period_end=DT)
        assert str(exc.value) == "period_start must be before period_end"
        assert DT2 not in str(exc.value)
        assert DT not in str(exc.value)

    def test_period_start_equals_end_raises(self):
        with pytest.raises(ValueError) as exc:
            _forecast(period_start=DT, period_end=DT)
        assert str(exc.value) == "period_start must be before period_end"
        assert DT not in str(exc.value)

    def test_bad_period_start_raises(self):
        with pytest.raises(ValueError, match="period_start"):
            _forecast(period_start=BAD_DT)

    def test_bad_period_end_raises(self):
        with pytest.raises(ValueError, match="period_end"):
            _forecast(period_end=BAD_DT)

    def test_currency_lowercase_raises(self):
        with pytest.raises(ValueError, match="currency"):
            _forecast(currency="usd")

    def test_bad_created_at_raises(self):
        with pytest.raises(ValueError, match="created_at"):
            _forecast(created_at=BAD_DT)

    def test_breakdown_frozen(self):
        f = _forecast()
        with pytest.raises(TypeError):
            f.breakdown["new"] = 1.0  # type: ignore[index]


# ===================================================================
# BudgetConflict
# ===================================================================


class TestBudgetConflict:
    def test_valid_construction(self):
        c = _conflict()
        assert c.conflict_id == "conf-1"
        assert c.kind is BudgetConflictKind.OVER_LIMIT
        assert c.severity == 3

    def test_id_empty_raises(self):
        with pytest.raises(ValueError, match="conflict_id"):
            _conflict(conflict_id="")

    def test_budget_id_empty_raises(self):
        with pytest.raises(ValueError, match="budget_id"):
            _conflict(budget_id="")

    def test_frozen_immutability(self):
        c = _conflict()
        with pytest.raises(dataclasses.FrozenInstanceError):
            c.conflict_id = "other"  # type: ignore[misc]

    def test_to_dict_preserves_enum(self):
        d = _conflict().to_dict()
        assert d["kind"] is BudgetConflictKind.OVER_LIMIT

    def test_to_dict_all_keys(self):
        d = _conflict().to_dict()
        expected_keys = {
            "conflict_id", "budget_id", "kind", "description", "severity",
            "detected_at",
        }
        assert set(d.keys()) == expected_keys

    def test_negative_severity_raises(self):
        with pytest.raises(ValueError, match="severity"):
            _conflict(severity=-1)

    def test_bad_detected_at_raises(self):
        with pytest.raises(ValueError, match="detected_at"):
            _conflict(detected_at=BAD_DT)

    def test_all_kinds_accepted(self):
        for kind in BudgetConflictKind:
            c = _conflict(kind=kind)
            assert c.kind is kind

    def test_severity_zero_ok(self):
        c = _conflict(severity=0)
        assert c.severity == 0


# ===================================================================
# BudgetDecision
# ===================================================================


class TestBudgetDecision:
    def test_valid_construction(self):
        d = _decision()
        assert d.decision_id == "dec-1"
        assert d.disposition is ChargeDisposition.APPROVED
        assert d.approval_required is False

    def test_id_empty_raises(self):
        with pytest.raises(ValueError, match="decision_id"):
            _decision(decision_id="")

    def test_budget_id_empty_raises(self):
        with pytest.raises(ValueError, match="budget_id"):
            _decision(budget_id="")

    def test_frozen_immutability(self):
        d = _decision()
        with pytest.raises(dataclasses.FrozenInstanceError):
            d.decision_id = "other"  # type: ignore[misc]

    def test_to_dict_preserves_enum(self):
        d = _decision().to_dict()
        assert d["disposition"] is ChargeDisposition.APPROVED

    def test_to_dict_all_keys(self):
        d = _decision().to_dict()
        expected_keys = {
            "decision_id", "budget_id", "disposition", "requested_amount",
            "available_amount", "currency", "reason", "reservation_id",
            "approval_required", "approver_ref", "decided_at",
        }
        assert set(d.keys()) == expected_keys

    def test_approval_required_without_approver_raises(self):
        with pytest.raises(ValueError, match="approver_ref"):
            _decision(approval_required=True, approver_ref="")

    def test_approval_required_with_approver_ok(self):
        d = _decision(approval_required=True, approver_ref="approver-1")
        assert d.approval_required is True
        assert d.approver_ref == "approver-1"

    def test_negative_requested_raises(self):
        with pytest.raises(ValueError, match="requested_amount"):
            _decision(requested_amount=-1.0)

    def test_negative_available_raises(self):
        with pytest.raises(ValueError, match="available_amount"):
            _decision(available_amount=-1.0)

    def test_currency_lowercase_raises(self):
        with pytest.raises(ValueError, match="currency"):
            _decision(currency="usd")

    def test_bad_decided_at_raises(self):
        with pytest.raises(ValueError, match="decided_at"):
            _decision(decided_at=BAD_DT)

    def test_all_dispositions_accepted(self):
        for disp in ChargeDisposition:
            d = _decision(disposition=disp)
            assert d.disposition is disp


# ===================================================================
# FinancialHealthSnapshot
# ===================================================================


class TestFinancialHealthSnapshot:
    def test_valid_construction(self):
        s = _snapshot()
        assert s.snapshot_id == "snap-1"
        assert s.utilization == 0.4
        assert s.warning_triggered is False

    def test_id_empty_raises(self):
        with pytest.raises(ValueError, match="snapshot_id"):
            _snapshot(snapshot_id="")

    def test_budget_id_empty_raises(self):
        with pytest.raises(ValueError, match="budget_id"):
            _snapshot(budget_id="")

    def test_frozen_immutability(self):
        s = _snapshot()
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.snapshot_id = "other"  # type: ignore[misc]

    def test_to_dict_all_keys(self):
        d = _snapshot().to_dict()
        expected_keys = {
            "snapshot_id", "budget_id", "limit_amount", "consumed_amount",
            "reserved_amount", "available_amount", "utilization", "currency",
            "warning_triggered", "hard_stop_triggered", "active_reservations",
            "total_spend_records", "captured_at",
        }
        assert set(d.keys()) == expected_keys

    def test_negative_limit_raises(self):
        with pytest.raises(ValueError, match="limit_amount"):
            _snapshot(limit_amount=-1.0)

    def test_negative_consumed_raises(self):
        with pytest.raises(ValueError, match="consumed_amount"):
            _snapshot(consumed_amount=-1.0)

    def test_negative_reserved_raises(self):
        with pytest.raises(ValueError, match="reserved_amount"):
            _snapshot(reserved_amount=-1.0)

    def test_negative_available_raises(self):
        with pytest.raises(ValueError, match="available_amount"):
            _snapshot(available_amount=-1.0)

    def test_utilization_above_one_raises(self):
        with pytest.raises(ValueError, match="utilization"):
            _snapshot(utilization=1.1)

    def test_utilization_below_zero_raises(self):
        with pytest.raises(ValueError, match="utilization"):
            _snapshot(utilization=-0.1)

    def test_utilization_zero_ok(self):
        s = _snapshot(utilization=0.0)
        assert s.utilization == 0.0

    def test_utilization_one_ok(self):
        s = _snapshot(utilization=1.0)
        assert s.utilization == 1.0

    def test_negative_active_reservations_raises(self):
        with pytest.raises(ValueError, match="active_reservations"):
            _snapshot(active_reservations=-1)

    def test_negative_total_spend_records_raises(self):
        with pytest.raises(ValueError, match="total_spend_records"):
            _snapshot(total_spend_records=-1)

    def test_currency_lowercase_raises(self):
        with pytest.raises(ValueError, match="currency"):
            _snapshot(currency="usd")

    def test_currency_two_letters_raises(self):
        with pytest.raises(ValueError, match="currency"):
            _snapshot(currency="US")

    def test_currency_four_letters_raises(self):
        with pytest.raises(ValueError, match="currency"):
            _snapshot(currency="USDD")

    def test_currency_digits_raises(self):
        with pytest.raises(ValueError, match="currency"):
            _snapshot(currency="12A")

    def test_bad_captured_at_raises(self):
        with pytest.raises(ValueError, match="captured_at"):
            _snapshot(captured_at=BAD_DT)


# ===================================================================
# BudgetClosureReport
# ===================================================================


class TestBudgetClosureReport:
    def test_valid_construction(self):
        r = _closure()
        assert r.report_id == "rpt-1"
        assert r.under_budget is True
        assert r.overspend_amount == 0.0

    def test_id_empty_raises(self):
        with pytest.raises(ValueError, match="report_id"):
            _closure(report_id="")

    def test_budget_id_empty_raises(self):
        with pytest.raises(ValueError, match="budget_id"):
            _closure(budget_id="")

    def test_frozen_immutability(self):
        r = _closure()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.report_id = "other"  # type: ignore[misc]

    def test_to_dict_all_keys(self):
        d = _closure().to_dict()
        expected_keys = {
            "report_id", "budget_id", "limit_amount", "total_consumed",
            "total_released", "total_reservations", "total_spend_records",
            "currency", "under_budget", "overspend_amount", "warnings_issued",
            "hard_stops_triggered", "closed_at",
        }
        assert set(d.keys()) == expected_keys

    def test_negative_limit_raises(self):
        with pytest.raises(ValueError, match="limit_amount"):
            _closure(limit_amount=-1.0)

    def test_negative_total_consumed_raises(self):
        with pytest.raises(ValueError, match="total_consumed"):
            _closure(total_consumed=-1.0)

    def test_negative_total_released_raises(self):
        with pytest.raises(ValueError, match="total_released"):
            _closure(total_released=-1.0)

    def test_negative_overspend_raises(self):
        with pytest.raises(ValueError, match="overspend_amount"):
            _closure(overspend_amount=-1.0)

    def test_negative_total_reservations_raises(self):
        with pytest.raises(ValueError, match="total_reservations"):
            _closure(total_reservations=-1)

    def test_negative_total_spend_records_raises(self):
        with pytest.raises(ValueError, match="total_spend_records"):
            _closure(total_spend_records=-1)

    def test_negative_warnings_issued_raises(self):
        with pytest.raises(ValueError, match="warnings_issued"):
            _closure(warnings_issued=-1)

    def test_negative_hard_stops_triggered_raises(self):
        with pytest.raises(ValueError, match="hard_stops_triggered"):
            _closure(hard_stops_triggered=-1)

    def test_currency_lowercase_raises(self):
        with pytest.raises(ValueError, match="currency"):
            _closure(currency="usd")

    def test_currency_two_letters_raises(self):
        with pytest.raises(ValueError, match="currency"):
            _closure(currency="US")

    def test_currency_four_letters_raises(self):
        with pytest.raises(ValueError, match="currency"):
            _closure(currency="USDD")

    def test_currency_digits_raises(self):
        with pytest.raises(ValueError, match="currency"):
            _closure(currency="12A")

    def test_bad_closed_at_raises(self):
        with pytest.raises(ValueError, match="closed_at"):
            _closure(closed_at=BAD_DT)

    def test_under_budget_false_ok(self):
        r = _closure(under_budget=False, overspend_amount=50.0)
        assert r.under_budget is False
        assert r.overspend_amount == 50.0


# ===================================================================
# Cross-cutting currency validation
# ===================================================================


class TestCurrencyValidation:
    """Verify currency validation consistently across all currency-bearing types."""

    @pytest.mark.parametrize("bad_currency", ["usd", "US", "USDD", "12A", "a", ""])
    def test_budget_envelope_rejects(self, bad_currency):
        with pytest.raises(ValueError, match="currency"):
            _budget(currency=bad_currency)

    @pytest.mark.parametrize("bad_currency", ["usd", "US", "USDD", "12A"])
    def test_spend_record_rejects(self, bad_currency):
        with pytest.raises(ValueError, match="currency"):
            _spend(currency=bad_currency)

    @pytest.mark.parametrize("bad_currency", ["usd", "US", "USDD", "12A"])
    def test_cost_estimate_rejects(self, bad_currency):
        with pytest.raises(ValueError, match="currency"):
            _estimate(currency=bad_currency)

    @pytest.mark.parametrize("bad_currency", ["usd", "US", "USDD", "12A"])
    def test_connector_profile_rejects(self, bad_currency):
        with pytest.raises(ValueError, match="currency"):
            _profile(currency=bad_currency)

    @pytest.mark.parametrize("bad_currency", ["usd", "US", "USDD", "12A"])
    def test_binding_rejects(self, bad_currency):
        with pytest.raises(ValueError, match="currency"):
            _binding(currency=bad_currency)

    @pytest.mark.parametrize("bad_currency", ["usd", "US", "USDD", "12A"])
    def test_threshold_rejects(self, bad_currency):
        with pytest.raises(ValueError, match="currency"):
            _threshold(currency=bad_currency)

    @pytest.mark.parametrize("bad_currency", ["usd", "US", "USDD", "12A"])
    def test_reservation_rejects(self, bad_currency):
        with pytest.raises(ValueError, match="currency"):
            _reservation(currency=bad_currency)

    @pytest.mark.parametrize("bad_currency", ["usd", "US", "USDD", "12A"])
    def test_forecast_rejects(self, bad_currency):
        with pytest.raises(ValueError, match="currency"):
            _forecast(currency=bad_currency)

    @pytest.mark.parametrize("bad_currency", ["usd", "US", "USDD", "12A"])
    def test_decision_rejects(self, bad_currency):
        with pytest.raises(ValueError, match="currency"):
            _decision(currency=bad_currency)

    @pytest.mark.parametrize("bad_currency", ["usd", "US", "USDD", "12A"])
    def test_snapshot_rejects(self, bad_currency):
        with pytest.raises(ValueError, match="currency"):
            _snapshot(currency=bad_currency)

    @pytest.mark.parametrize("bad_currency", ["usd", "US", "USDD", "12A"])
    def test_closure_rejects(self, bad_currency):
        with pytest.raises(ValueError, match="currency"):
            _closure(currency=bad_currency)

    @pytest.mark.parametrize("good_currency", ["USD", "EUR", "GBP", "JPY", "CHF"])
    def test_valid_currencies_accepted(self, good_currency):
        b = _budget(currency=good_currency)
        assert b.currency == good_currency
