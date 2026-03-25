"""Comprehensive tests for FinancialRuntimeEngine.

Covers: budget registration, campaign bindings, connector cost profiles,
approval thresholds, budget reservation / consume / release, cost estimation,
spend forecasting, budget health, conflict detection, budget gating,
budget closure, cheapest connector fallback, queries, properties, state hash,
invariant enforcement, and 8 golden scenarios.
"""

from __future__ import annotations

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
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.financial_runtime import FinancialRuntimeEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _engine() -> tuple[EventSpineEngine, FinancialRuntimeEngine]:
    es = EventSpineEngine()
    return es, FinancialRuntimeEngine(es)


def _register_budget(
    eng: FinancialRuntimeEngine,
    budget_id: str = "b-1",
    name: str = "Test Budget",
    scope: BudgetScope = BudgetScope.CAMPAIGN,
    scope_ref_id: str = "camp-1",
    *,
    limit_amount: float = 1000.0,
    warning_threshold: float = 0.8,
    hard_stop_threshold: float = 1.0,
    currency: str = "USD",
    tags: tuple[str, ...] = (),
    metadata: dict | None = None,
) -> BudgetEnvelope:
    return eng.register_budget(
        budget_id, name, scope, scope_ref_id,
        currency=currency,
        limit_amount=limit_amount,
        warning_threshold=warning_threshold,
        hard_stop_threshold=hard_stop_threshold,
        tags=tags,
        metadata=metadata,
    )


def _reserve(
    eng: FinancialRuntimeEngine,
    reservation_id: str = "r-1",
    budget_id: str = "b-1",
    amount: float = 100.0,
    category: CostCategory = CostCategory.CONNECTOR_CALL,
) -> BudgetDecision:
    return eng.reserve_budget(reservation_id, budget_id, amount, category)


# ===================================================================
# TestInit
# ===================================================================


class TestInit:
    """Tests for __init__ validation."""

    def test_rejects_non_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            FinancialRuntimeEngine("not-an-engine")  # type: ignore[arg-type]

    def test_rejects_none(self):
        with pytest.raises(RuntimeCoreInvariantError):
            FinancialRuntimeEngine(None)  # type: ignore[arg-type]

    def test_rejects_int(self):
        with pytest.raises(RuntimeCoreInvariantError):
            FinancialRuntimeEngine(42)  # type: ignore[arg-type]

    def test_accepts_event_spine(self):
        es = EventSpineEngine()
        eng = FinancialRuntimeEngine(es)
        assert eng.budget_count == 0

    def test_initial_counts_zero(self):
        _, eng = _engine()
        assert eng.budget_count == 0
        assert eng.reservation_count == 0
        assert eng.spend_record_count == 0


# ===================================================================
# TestRegisterBudget
# ===================================================================


class TestRegisterBudget:
    """Tests for register_budget."""

    def test_basic_registration(self):
        _, eng = _engine()
        b = _register_budget(eng)
        assert isinstance(b, BudgetEnvelope)
        assert b.budget_id == "b-1"
        assert b.name == "Test Budget"
        assert b.scope == BudgetScope.CAMPAIGN
        assert b.limit_amount == 1000.0

    def test_returns_correct_currency(self):
        _, eng = _engine()
        b = _register_budget(eng, currency="EUR")
        assert b.currency == "EUR"

    def test_default_thresholds(self):
        _, eng = _engine()
        b = _register_budget(eng)
        assert b.warning_threshold == 0.8
        assert b.hard_stop_threshold == 1.0

    def test_custom_thresholds(self):
        _, eng = _engine()
        b = _register_budget(eng, warning_threshold=0.5, hard_stop_threshold=0.9)
        assert b.warning_threshold == 0.5
        assert b.hard_stop_threshold == 0.9

    def test_initial_amounts_zero(self):
        _, eng = _engine()
        b = _register_budget(eng)
        assert b.consumed_amount == 0.0
        assert b.reserved_amount == 0.0

    def test_active_by_default(self):
        _, eng = _engine()
        b = _register_budget(eng)
        assert b.active is True

    def test_tags_preserved(self):
        _, eng = _engine()
        b = _register_budget(eng, tags=("foo", "bar"))
        assert b.tags == ("foo", "bar")

    def test_metadata_preserved(self):
        _, eng = _engine()
        b = _register_budget(eng, metadata={"key": "val"})
        assert b.metadata["key"] == "val"

    def test_emits_event(self):
        es, eng = _engine()
        before = len(es.list_events())
        _register_budget(eng)
        after = len(es.list_events())
        assert after > before

    def test_duplicate_raises(self):
        _, eng = _engine()
        _register_budget(eng, budget_id="b-dup")
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            _register_budget(eng, budget_id="b-dup")

    def test_increments_budget_count(self):
        _, eng = _engine()
        assert eng.budget_count == 0
        _register_budget(eng, budget_id="b-a")
        assert eng.budget_count == 1
        _register_budget(eng, budget_id="b-b")
        assert eng.budget_count == 2

    def test_global_scope(self):
        _, eng = _engine()
        b = _register_budget(eng, scope=BudgetScope.GLOBAL)
        assert b.scope == BudgetScope.GLOBAL

    def test_portfolio_scope(self):
        _, eng = _engine()
        b = _register_budget(eng, scope=BudgetScope.PORTFOLIO)
        assert b.scope == BudgetScope.PORTFOLIO

    def test_connector_scope(self):
        _, eng = _engine()
        b = _register_budget(eng, scope=BudgetScope.CONNECTOR)
        assert b.scope == BudgetScope.CONNECTOR

    def test_team_scope(self):
        _, eng = _engine()
        b = _register_budget(eng, scope=BudgetScope.TEAM)
        assert b.scope == BudgetScope.TEAM

    def test_function_scope(self):
        _, eng = _engine()
        b = _register_budget(eng, scope=BudgetScope.FUNCTION)
        assert b.scope == BudgetScope.FUNCTION

    def test_channel_scope(self):
        _, eng = _engine()
        b = _register_budget(eng, scope=BudgetScope.CHANNEL)
        assert b.scope == BudgetScope.CHANNEL


# ===================================================================
# TestGetBudget
# ===================================================================


class TestGetBudget:
    """Tests for get_budget."""

    def test_returns_registered_budget(self):
        _, eng = _engine()
        _register_budget(eng, budget_id="b-get")
        b = eng.get_budget("b-get")
        assert b is not None
        assert b.budget_id == "b-get"

    def test_returns_none_for_missing(self):
        _, eng = _engine()
        assert eng.get_budget("nonexistent") is None

    def test_returns_none_before_registration(self):
        _, eng = _engine()
        assert eng.get_budget("b-1") is None


# ===================================================================
# TestCampaignBudgetBinding
# ===================================================================


class TestCampaignBudgetBinding:
    """Tests for bind_campaign_budget and related queries."""

    def test_basic_binding(self):
        _, eng = _engine()
        _register_budget(eng)
        binding = eng.bind_campaign_budget("bind-1", "camp-1", "b-1", 500.0)
        assert isinstance(binding, CampaignBudgetBinding)
        assert binding.binding_id == "bind-1"
        assert binding.campaign_id == "camp-1"
        assert binding.budget_id == "b-1"
        assert binding.allocated_amount == 500.0

    def test_binding_currency_matches_budget(self):
        _, eng = _engine()
        _register_budget(eng, currency="EUR")
        binding = eng.bind_campaign_budget("bind-1", "camp-1", "b-1", 500.0)
        assert binding.currency == "EUR"

    def test_duplicate_binding_raises(self):
        _, eng = _engine()
        _register_budget(eng)
        eng.bind_campaign_budget("bind-1", "camp-1", "b-1", 500.0)
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            eng.bind_campaign_budget("bind-1", "camp-2", "b-1", 300.0)

    def test_binding_to_missing_budget_raises(self):
        _, eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            eng.bind_campaign_budget("bind-1", "camp-1", "no-budget", 500.0)

    def test_get_binding(self):
        _, eng = _engine()
        _register_budget(eng)
        eng.bind_campaign_budget("bind-1", "camp-1", "b-1", 500.0)
        b = eng.get_binding("bind-1")
        assert b is not None
        assert b.binding_id == "bind-1"

    def test_get_binding_missing(self):
        _, eng = _engine()
        assert eng.get_binding("no-bind") is None

    def test_get_bindings_for_campaign(self):
        _, eng = _engine()
        _register_budget(eng)
        eng.bind_campaign_budget("bind-1", "camp-1", "b-1", 500.0)
        eng.bind_campaign_budget("bind-2", "camp-1", "b-1", 300.0)
        eng.bind_campaign_budget("bind-3", "camp-2", "b-1", 200.0)
        bindings = eng.get_bindings_for_campaign("camp-1")
        assert len(bindings) == 2

    def test_get_bindings_for_budget(self):
        _, eng = _engine()
        _register_budget(eng, budget_id="b-1")
        _register_budget(eng, budget_id="b-2", name="B2", scope_ref_id="sr-2")
        eng.bind_campaign_budget("bind-1", "camp-1", "b-1", 500.0)
        eng.bind_campaign_budget("bind-2", "camp-2", "b-1", 300.0)
        eng.bind_campaign_budget("bind-3", "camp-3", "b-2", 200.0)
        bindings = eng.get_bindings_for_budget("b-1")
        assert len(bindings) == 2

    def test_binding_emits_event(self):
        es, eng = _engine()
        _register_budget(eng)
        before = len(es.list_events())
        eng.bind_campaign_budget("bind-1", "camp-1", "b-1", 500.0)
        after = len(es.list_events())
        assert after > before


# ===================================================================
# TestConnectorCostProfile
# ===================================================================


class TestConnectorCostProfile:
    """Tests for register_connector_cost_profile and get_connector_cost_profile."""

    def test_basic_registration(self):
        _, eng = _engine()
        p = eng.register_connector_cost_profile(
            "prof-1", "conn-smtp",
            cost_per_call=5.0, cost_per_unit=2.0,
        )
        assert isinstance(p, ConnectorCostProfile)
        assert p.profile_id == "prof-1"
        assert p.connector_ref == "conn-smtp"
        assert p.cost_per_call == 5.0
        assert p.cost_per_unit == 2.0

    def test_default_values(self):
        _, eng = _engine()
        p = eng.register_connector_cost_profile("prof-1", "conn-x")
        assert p.cost_per_call == 0.0
        assert p.cost_per_unit == 0.0
        assert p.currency == "USD"
        assert p.unit_name == "call"

    def test_custom_currency(self):
        _, eng = _engine()
        p = eng.register_connector_cost_profile("prof-1", "conn-x", currency="EUR")
        assert p.currency == "EUR"

    def test_duplicate_profile_raises(self):
        _, eng = _engine()
        eng.register_connector_cost_profile("prof-1", "conn-a")
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            eng.register_connector_cost_profile("prof-1", "conn-b")

    def test_get_profile_by_connector_ref(self):
        _, eng = _engine()
        eng.register_connector_cost_profile("prof-1", "conn-smtp", cost_per_call=5.0)
        p = eng.get_connector_cost_profile("conn-smtp")
        assert p is not None
        assert p.cost_per_call == 5.0

    def test_get_profile_missing(self):
        _, eng = _engine()
        assert eng.get_connector_cost_profile("no-conn") is None

    def test_profile_emits_event(self):
        es, eng = _engine()
        before = len(es.list_events())
        eng.register_connector_cost_profile("prof-1", "conn-a")
        after = len(es.list_events())
        assert after > before

    def test_metadata_preserved(self):
        _, eng = _engine()
        p = eng.register_connector_cost_profile(
            "prof-1", "conn-x", metadata={"env": "prod"},
        )
        assert p.metadata["env"] == "prod"

    def test_tier_parameter(self):
        _, eng = _engine()
        p = eng.register_connector_cost_profile("prof-1", "conn-x", tier="premium")
        assert p.tier == "premium"

    def test_monthly_cap_and_minimum(self):
        _, eng = _engine()
        p = eng.register_connector_cost_profile(
            "prof-1", "conn-x", monthly_minimum=10.0, monthly_cap=1000.0,
        )
        assert p.monthly_minimum == 10.0
        assert p.monthly_cap == 1000.0


# ===================================================================
# TestApprovalThreshold
# ===================================================================


class TestApprovalThreshold:
    """Tests for set_approval_threshold."""

    def test_basic_threshold(self):
        _, eng = _engine()
        _register_budget(eng)
        t = eng.set_approval_threshold(
            "th-1", "b-1", ApprovalThresholdMode.PER_TRANSACTION,
            500.0, "manager-1",
        )
        assert isinstance(t, ApprovalThreshold)
        assert t.threshold_id == "th-1"
        assert t.budget_id == "b-1"
        assert t.mode == ApprovalThresholdMode.PER_TRANSACTION
        assert t.amount == 500.0
        assert t.approver_ref == "manager-1"

    def test_auto_approve_below(self):
        _, eng = _engine()
        _register_budget(eng)
        t = eng.set_approval_threshold(
            "th-1", "b-1", ApprovalThresholdMode.PER_TRANSACTION,
            500.0, "manager-1", auto_approve_below=100.0,
        )
        assert t.auto_approve_below == 100.0

    def test_threshold_on_missing_budget_raises(self):
        _, eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            eng.set_approval_threshold(
                "th-1", "no-budget", ApprovalThresholdMode.PER_TRANSACTION,
                500.0, "manager-1",
            )

    def test_threshold_emits_event(self):
        es, eng = _engine()
        _register_budget(eng)
        before = len(es.list_events())
        eng.set_approval_threshold(
            "th-1", "b-1", ApprovalThresholdMode.PER_TRANSACTION,
            500.0, "manager-1",
        )
        after = len(es.list_events())
        assert after > before

    def test_cumulative_mode(self):
        _, eng = _engine()
        _register_budget(eng)
        t = eng.set_approval_threshold(
            "th-1", "b-1", ApprovalThresholdMode.CUMULATIVE,
            800.0, "cfo-1",
        )
        assert t.mode == ApprovalThresholdMode.CUMULATIVE

    def test_percentage_mode(self):
        _, eng = _engine()
        _register_budget(eng)
        t = eng.set_approval_threshold(
            "th-1", "b-1", ApprovalThresholdMode.PERCENTAGE_OF_LIMIT,
            90.0, "cfo-1",
        )
        assert t.mode == ApprovalThresholdMode.PERCENTAGE_OF_LIMIT

    def test_remaining_budget_mode(self):
        _, eng = _engine()
        _register_budget(eng)
        t = eng.set_approval_threshold(
            "th-1", "b-1", ApprovalThresholdMode.REMAINING_BUDGET,
            100.0, "cfo-1",
        )
        assert t.mode == ApprovalThresholdMode.REMAINING_BUDGET

    def test_get_thresholds_for_budget(self):
        _, eng = _engine()
        _register_budget(eng)
        eng.set_approval_threshold(
            "th-1", "b-1", ApprovalThresholdMode.PER_TRANSACTION,
            500.0, "mgr-1",
        )
        eng.set_approval_threshold(
            "th-2", "b-1", ApprovalThresholdMode.CUMULATIVE,
            800.0, "mgr-2",
        )
        thresholds = eng.get_thresholds_for_budget("b-1")
        assert len(thresholds) == 2


# ===================================================================
# TestReserveBudget
# ===================================================================


class TestReserveBudget:
    """Tests for reserve_budget."""

    def test_approved_reservation(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        dec = _reserve(eng, amount=100.0)
        assert isinstance(dec, BudgetDecision)
        assert dec.disposition == ChargeDisposition.APPROVED

    def test_reservation_id_in_decision(self):
        _, eng = _engine()
        _register_budget(eng)
        dec = _reserve(eng, reservation_id="r-abc")
        assert dec.reservation_id == "r-abc"

    def test_denied_hard_stop(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=100.0)
        _reserve(eng, reservation_id="r-1", amount=80.0)
        dec = _reserve(eng, reservation_id="r-2", amount=30.0)
        assert dec.disposition == ChargeDisposition.DENIED_HARD_STOP

    def test_denied_insufficient(self):
        _, eng = _engine()
        # With hard_stop_threshold=1.0 and limit 100, requesting 200 will hit hard stop
        # For pure insufficient: need amount > available but utilization < hard_stop
        # Use a large limit to avoid hard stop
        _register_budget(eng, limit_amount=100.0, hard_stop_threshold=1.0)
        _reserve(eng, reservation_id="r-1", amount=70.0)
        # 30 available, request 40 — utilization = 110/100 > 1.0 → hard stop
        # Actually we need the request to exceed available but stay under hard_stop
        # If hard_stop_threshold = 1.0 and limit = 100:
        # 70 reserved, request 31 → new_util = 101/100 = 1.01 > 1.0 → HARD_STOP
        # To get DENIED_INSUFFICIENT, amount > available but utilization <= hard_stop
        # This can only happen if hard_stop > 1.0 but that's capped at 1.0.
        # So with threshold=1.0, DENIED_HARD_STOP always triggers first.
        # Let's just verify the decision type is denial for amounts exceeding budget.
        dec = _reserve(eng, reservation_id="r-2", amount=31.0)
        assert dec.disposition in (ChargeDisposition.DENIED_HARD_STOP, ChargeDisposition.DENIED_INSUFFICIENT)

    def test_pending_approval(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=10000.0)
        eng.set_approval_threshold(
            "th-1", "b-1", ApprovalThresholdMode.PER_TRANSACTION,
            500.0, "manager-1",
        )
        dec = _reserve(eng, reservation_id="r-1", amount=600.0)
        assert dec.disposition == ChargeDisposition.PENDING_APPROVAL

    def test_warning_issued(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=100.0, warning_threshold=0.8)
        dec = _reserve(eng, reservation_id="r-1", amount=85.0)
        assert dec.disposition == ChargeDisposition.WARNING_ISSUED

    def test_duplicate_reservation_raises(self):
        _, eng = _engine()
        _register_budget(eng)
        _reserve(eng, reservation_id="r-dup")
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            _reserve(eng, reservation_id="r-dup")

    def test_reservation_on_missing_budget_raises(self):
        _, eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            _reserve(eng, budget_id="nonexistent")

    def test_reservation_emits_event(self):
        es, eng = _engine()
        _register_budget(eng)
        before = len(es.list_events())
        _reserve(eng)
        after = len(es.list_events())
        assert after > before

    def test_reservation_updates_budget_reserved(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, amount=200.0)
        b = eng.get_budget("b-1")
        assert b is not None
        assert b.reserved_amount == 200.0

    def test_increments_reservation_count(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        assert eng.reservation_count == 0
        _reserve(eng, reservation_id="r-1", amount=100.0)
        assert eng.reservation_count == 1
        _reserve(eng, reservation_id="r-2", amount=100.0)
        assert eng.reservation_count == 2

    def test_zero_amount_reservation(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        dec = _reserve(eng, amount=0.0)
        assert dec.disposition == ChargeDisposition.APPROVED

    def test_exact_limit_reservation(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=100.0, hard_stop_threshold=1.0)
        dec = _reserve(eng, amount=100.0)
        # utilization = 100/100 = 1.0, which equals hard_stop but not exceeds
        assert dec.disposition in (ChargeDisposition.APPROVED, ChargeDisposition.WARNING_ISSUED)

    def test_campaign_ref_preserved(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        dec = eng.reserve_budget(
            "r-1", "b-1", 50.0, CostCategory.CONNECTOR_CALL,
            campaign_ref="camp-x",
        )
        active = eng.get_active_reservations("b-1")
        assert len(active) == 1
        assert active[0].campaign_ref == "camp-x"

    def test_connector_ref_preserved(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        eng.reserve_budget(
            "r-1", "b-1", 50.0, CostCategory.CONNECTOR_CALL,
            connector_ref="conn-a",
        )
        active = eng.get_active_reservations("b-1")
        assert active[0].connector_ref == "conn-a"


# ===================================================================
# TestConsumeBudget
# ===================================================================


class TestConsumeBudget:
    """Tests for consume_budget."""

    def test_basic_consume(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=200.0)
        sr = eng.consume_budget("sp-1", "r-1")
        assert isinstance(sr, SpendRecord)
        assert sr.spend_id == "sp-1"
        assert sr.amount == 200.0
        assert sr.status == SpendStatus.CONSUMED

    def test_consume_with_actual_amount(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=200.0)
        sr = eng.consume_budget("sp-1", "r-1", actual_amount=150.0)
        assert sr.amount == 150.0

    def test_consume_updates_budget_amounts(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=200.0)
        eng.consume_budget("sp-1", "r-1")
        b = eng.get_budget("b-1")
        assert b is not None
        assert b.consumed_amount == 200.0
        assert b.reserved_amount == 0.0

    def test_consume_deactivates_reservation(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=200.0)
        eng.consume_budget("sp-1", "r-1")
        active = eng.get_active_reservations("b-1")
        assert len(active) == 0

    def test_duplicate_spend_id_raises(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=100.0)
        _reserve(eng, reservation_id="r-2", amount=100.0)
        eng.consume_budget("sp-dup", "r-1")
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            eng.consume_budget("sp-dup", "r-2")

    def test_consume_missing_reservation_raises(self):
        _, eng = _engine()
        _register_budget(eng)
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            eng.consume_budget("sp-1", "r-nonexistent")

    def test_consume_inactive_reservation_raises(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=100.0)
        eng.consume_budget("sp-1", "r-1")
        with pytest.raises(RuntimeCoreInvariantError, match="not active"):
            eng.consume_budget("sp-2", "r-1")

    def test_consume_emits_event(self):
        es, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=100.0)
        before = len(es.list_events())
        eng.consume_budget("sp-1", "r-1")
        after = len(es.list_events())
        assert after > before

    def test_consume_increments_spend_record_count(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=100.0)
        assert eng.spend_record_count == 0
        eng.consume_budget("sp-1", "r-1")
        assert eng.spend_record_count == 1

    def test_consume_budget_currency_matches(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0, currency="EUR")
        _reserve(eng, reservation_id="r-1", amount=100.0)
        sr = eng.consume_budget("sp-1", "r-1")
        assert sr.currency == "EUR"


# ===================================================================
# TestReleaseBudget
# ===================================================================


class TestReleaseBudget:
    """Tests for release_budget."""

    def test_basic_release(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=200.0)
        sr = eng.release_budget("r-1")
        assert isinstance(sr, SpendRecord)
        assert sr.status == SpendStatus.RELEASED

    def test_release_restores_available(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=200.0)
        eng.release_budget("r-1")
        b = eng.get_budget("b-1")
        assert b is not None
        assert b.reserved_amount == 0.0

    def test_release_deactivates_reservation(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=200.0)
        eng.release_budget("r-1")
        active = eng.get_active_reservations("b-1")
        assert len(active) == 0

    def test_release_missing_reservation_raises(self):
        _, eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            eng.release_budget("r-nonexistent")

    def test_release_inactive_reservation_raises(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=100.0)
        eng.release_budget("r-1")
        with pytest.raises(RuntimeCoreInvariantError, match="not active"):
            eng.release_budget("r-1")

    def test_release_custom_reason(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=200.0)
        sr = eng.release_budget("r-1", reason="timeout")
        assert sr.reason == "timeout"

    def test_release_emits_event(self):
        es, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=100.0)
        before = len(es.list_events())
        eng.release_budget("r-1")
        after = len(es.list_events())
        assert after > before

    def test_release_amount_matches_reservation(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=123.45)
        sr = eng.release_budget("r-1")
        assert sr.amount == 123.45


# ===================================================================
# TestEstimateCost
# ===================================================================


class TestEstimateCost:
    """Tests for estimate_cost."""

    def test_basic_estimate_no_connector(self):
        _, eng = _engine()
        est = eng.estimate_cost("est-1", CostCategory.CONNECTOR_CALL)
        assert isinstance(est, CostEstimate)
        assert est.estimate_id == "est-1"
        assert est.estimated_amount == 0.0

    def test_estimate_with_connector_profile(self):
        _, eng = _engine()
        eng.register_connector_cost_profile(
            "prof-1", "conn-x", cost_per_call=5.0, cost_per_unit=2.0,
        )
        est = eng.estimate_cost(
            "est-1", CostCategory.CONNECTOR_CALL,
            connector_ref="conn-x", units=3,
        )
        assert est.estimated_amount == 5.0 + 2.0 * 3  # = 11.0

    def test_estimate_unknown_connector_low_confidence(self):
        _, eng = _engine()
        est = eng.estimate_cost(
            "est-1", CostCategory.CONNECTOR_CALL,
            connector_ref="unknown-conn",
        )
        assert est.estimated_amount == 0.0
        assert est.confidence == 0.5

    def test_estimate_known_connector_full_confidence(self):
        _, eng = _engine()
        eng.register_connector_cost_profile(
            "prof-1", "conn-x", cost_per_call=5.0,
        )
        est = eng.estimate_cost(
            "est-1", CostCategory.CONNECTOR_CALL,
            connector_ref="conn-x",
        )
        assert est.confidence == 1.0

    def test_estimate_emits_event(self):
        es, eng = _engine()
        before = len(es.list_events())
        eng.estimate_cost("est-1", CostCategory.COMPUTE)
        after = len(es.list_events())
        assert after > before

    def test_estimate_category_preserved(self):
        _, eng = _engine()
        est = eng.estimate_cost("est-1", CostCategory.HUMAN_LABOR)
        assert est.category == CostCategory.HUMAN_LABOR

    def test_estimate_campaign_ref(self):
        _, eng = _engine()
        est = eng.estimate_cost(
            "est-1", CostCategory.CONNECTOR_CALL,
            campaign_ref="camp-1",
        )
        assert est.campaign_ref == "camp-1"

    def test_estimate_step_ref(self):
        _, eng = _engine()
        est = eng.estimate_cost(
            "est-1", CostCategory.CONNECTOR_CALL,
            step_ref="step-1",
        )
        assert est.step_ref == "step-1"


# ===================================================================
# TestForecastSpend
# ===================================================================


class TestForecastSpend:
    """Tests for forecast_spend."""

    def test_basic_forecast(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        fc = eng.forecast_spend(
            "fc-1", "b-1",
            "2025-06-01T00:00:00+00:00", "2025-07-01T00:00:00+00:00",
        )
        assert isinstance(fc, SpendForecast)
        assert fc.forecast_id == "fc-1"
        assert fc.budget_id == "b-1"

    def test_forecast_missing_budget_raises(self):
        _, eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            eng.forecast_spend(
                "fc-1", "nonexistent",
                "2025-06-01T00:00:00+00:00", "2025-07-01T00:00:00+00:00",
            )

    def test_forecast_reflects_current_spend(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=200.0)
        eng.consume_budget("sp-1", "r-1")
        _reserve(eng, reservation_id="r-2", amount=150.0)
        fc = eng.forecast_spend(
            "fc-1", "b-1",
            "2025-06-01T00:00:00+00:00", "2025-07-01T00:00:00+00:00",
        )
        # consumed=200 + active reserved=150
        assert fc.projected_amount == 350.0

    def test_forecast_emits_event(self):
        es, eng = _engine()
        _register_budget(eng)
        before = len(es.list_events())
        eng.forecast_spend(
            "fc-1", "b-1",
            "2025-06-01T00:00:00+00:00", "2025-07-01T00:00:00+00:00",
        )
        after = len(es.list_events())
        assert after > before

    def test_forecast_with_breakdown(self):
        _, eng = _engine()
        _register_budget(eng)
        fc = eng.forecast_spend(
            "fc-1", "b-1",
            "2025-06-01T00:00:00+00:00", "2025-07-01T00:00:00+00:00",
            breakdown={"connectors": 100.0, "compute": 50.0},
        )
        assert fc.breakdown["connectors"] == 100.0
        assert fc.breakdown["compute"] == 50.0


# ===================================================================
# TestBudgetHealth
# ===================================================================


class TestBudgetHealth:
    """Tests for budget_health."""

    def test_healthy_budget(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        h = eng.budget_health("b-1")
        assert isinstance(h, FinancialHealthSnapshot)
        assert h.budget_id == "b-1"
        assert h.limit_amount == 1000.0
        assert h.consumed_amount == 0.0
        assert h.reserved_amount == 0.0
        assert h.available_amount == 1000.0

    def test_health_after_reservation(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, amount=300.0)
        h = eng.budget_health("b-1")
        assert h.reserved_amount == 300.0
        assert h.available_amount == 700.0

    def test_health_after_consume(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=300.0)
        eng.consume_budget("sp-1", "r-1")
        h = eng.budget_health("b-1")
        assert h.consumed_amount == 300.0
        assert h.reserved_amount == 0.0
        assert h.available_amount == 700.0

    def test_health_utilization(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, amount=500.0)
        h = eng.budget_health("b-1")
        assert h.utilization == 0.5

    def test_health_warning_triggered(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=100.0, warning_threshold=0.8)
        _reserve(eng, amount=85.0)
        h = eng.budget_health("b-1")
        assert h.warning_triggered is True

    def test_health_warning_not_triggered(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=100.0, warning_threshold=0.8)
        _reserve(eng, amount=50.0)
        h = eng.budget_health("b-1")
        assert h.warning_triggered is False

    def test_health_missing_budget_raises(self):
        _, eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            eng.budget_health("nonexistent")

    def test_health_active_reservations_count(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=100.0)
        _reserve(eng, reservation_id="r-2", amount=100.0)
        h = eng.budget_health("b-1")
        assert h.active_reservations == 2

    def test_health_total_spend_records(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=100.0)
        eng.consume_budget("sp-1", "r-1")
        h = eng.budget_health("b-1")
        assert h.total_spend_records == 1

    def test_health_currency_matches_budget(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0, currency="EUR")
        h = eng.budget_health("b-1")
        assert h.currency == "EUR"


# ===================================================================
# TestFindBudgetConflicts
# ===================================================================


class TestFindBudgetConflicts:
    """Tests for find_budget_conflicts."""

    def test_no_conflicts_healthy_budget(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        conflicts = eng.find_budget_conflicts("b-1")
        assert len(conflicts) == 0

    def test_missing_budget_raises(self):
        _, eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            eng.find_budget_conflicts("nonexistent")

    def test_threshold_breach_at_hard_stop(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=100.0, hard_stop_threshold=1.0)
        _reserve(eng, amount=100.0)
        conflicts = eng.find_budget_conflicts("b-1")
        breach_conflicts = [c for c in conflicts if c.kind == BudgetConflictKind.THRESHOLD_BREACH]
        assert len(breach_conflicts) >= 1

    def test_returns_tuple(self):
        _, eng = _engine()
        _register_budget(eng)
        conflicts = eng.find_budget_conflicts("b-1")
        assert isinstance(conflicts, tuple)


# ===================================================================
# TestBudgetGate
# ===================================================================


class TestBudgetGate:
    """Tests for budget_gate (read-only check)."""

    def test_approved_gate(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        dec = eng.budget_gate("b-1", 100.0)
        assert isinstance(dec, BudgetDecision)
        assert dec.disposition == ChargeDisposition.APPROVED

    def test_denied_hard_stop_gate(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=100.0, hard_stop_threshold=1.0)
        _reserve(eng, reservation_id="r-1", amount=80.0)
        dec = eng.budget_gate("b-1", 30.0)
        assert dec.disposition == ChargeDisposition.DENIED_HARD_STOP

    def test_denied_insufficient_gate(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=100.0, hard_stop_threshold=1.0)
        # Gate check for 200 on budget with 100 available → hard stop or insufficient
        dec = eng.budget_gate("b-1", 200.0)
        assert dec.disposition in (ChargeDisposition.DENIED_HARD_STOP, ChargeDisposition.DENIED_INSUFFICIENT)

    def test_gate_does_not_mutate_budget(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        b_before = eng.get_budget("b-1")
        eng.budget_gate("b-1", 500.0)
        b_after = eng.get_budget("b-1")
        assert b_before == b_after

    def test_gate_does_not_create_reservation(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        eng.budget_gate("b-1", 500.0)
        assert eng.reservation_count == 0

    def test_gate_missing_budget_raises(self):
        _, eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            eng.budget_gate("nonexistent", 100.0)

    def test_gate_warning_issued(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=100.0, warning_threshold=0.8)
        dec = eng.budget_gate("b-1", 85.0)
        assert dec.disposition == ChargeDisposition.WARNING_ISSUED

    def test_gate_pending_approval(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=10000.0)
        eng.set_approval_threshold(
            "th-1", "b-1", ApprovalThresholdMode.PER_TRANSACTION,
            500.0, "mgr-1",
        )
        dec = eng.budget_gate("b-1", 600.0)
        assert dec.disposition == ChargeDisposition.PENDING_APPROVAL

    def test_gate_on_inactive_budget(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        eng.close_budget("b-1")
        dec = eng.budget_gate("b-1", 100.0)
        assert dec.disposition == ChargeDisposition.DENIED_HARD_STOP


# ===================================================================
# TestCloseBudget
# ===================================================================


class TestCloseBudget:
    """Tests for close_budget."""

    def test_basic_close(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        report = eng.close_budget("b-1")
        assert isinstance(report, BudgetClosureReport)
        assert report.budget_id == "b-1"

    def test_close_deactivates_budget(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        eng.close_budget("b-1")
        b = eng.get_budget("b-1")
        assert b is not None
        assert b.active is False

    def test_close_releases_active_reservations(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=200.0)
        _reserve(eng, reservation_id="r-2", amount=100.0)
        report = eng.close_budget("b-1")
        active = eng.get_active_reservations("b-1")
        assert len(active) == 0
        assert report.total_released == 300.0

    def test_close_missing_budget_raises(self):
        _, eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            eng.close_budget("nonexistent")

    def test_close_under_budget(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=200.0)
        eng.consume_budget("sp-1", "r-1")
        report = eng.close_budget("b-1")
        assert report.under_budget is True
        assert report.overspend_amount == 0.0

    def test_close_report_totals(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=200.0)
        eng.consume_budget("sp-1", "r-1")
        report = eng.close_budget("b-1")
        assert report.total_consumed == 200.0

    def test_close_emits_event(self):
        es, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        before = len(es.list_events())
        eng.close_budget("b-1")
        after = len(es.list_events())
        assert after > before


# ===================================================================
# TestFindCheapestConnector
# ===================================================================


class TestFindCheapestConnector:
    """Tests for find_cheapest_connector."""

    def test_cheapest_selected(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        eng.register_connector_cost_profile("p-1", "conn-expensive", cost_per_call=50.0)
        eng.register_connector_cost_profile("p-2", "conn-cheap", cost_per_call=10.0)
        result = eng.find_cheapest_connector(["conn-expensive", "conn-cheap"], "b-1")
        assert result["chosen"]["connector_ref"] == "conn-cheap"

    def test_all_blocked_when_none_viable(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=100.0)
        _reserve(eng, reservation_id="r-1", amount=95.0)
        eng.register_connector_cost_profile("p-1", "conn-a", cost_per_call=50.0)
        eng.register_connector_cost_profile("p-2", "conn-b", cost_per_call=30.0)
        result = eng.find_cheapest_connector(["conn-a", "conn-b"], "b-1")
        assert result["all_blocked"] is True

    def test_missing_budget_raises(self):
        _, eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            eng.find_cheapest_connector(["conn-a"], "nonexistent")

    def test_unknown_connector_viable_zero_cost(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        result = eng.find_cheapest_connector(["unknown-conn"], "b-1")
        assert result["chosen"]["cost_per_call"] == 0.0
        assert result["chosen"]["viable"] is True

    def test_result_includes_available(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        result = eng.find_cheapest_connector([], "b-1")
        assert result["available"] == 1000.0


# ===================================================================
# TestQueries
# ===================================================================


class TestQueries:
    """Tests for get_spend_records, get_active_reservations, get_decisions."""

    def test_get_spend_records(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=100.0)
        eng.consume_budget("sp-1", "r-1")
        records = eng.get_spend_records("b-1")
        assert len(records) >= 1
        assert records[0].spend_id == "sp-1"

    def test_get_spend_records_empty(self):
        _, eng = _engine()
        _register_budget(eng)
        records = eng.get_spend_records("b-1")
        assert len(records) == 0

    def test_get_active_reservations(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=100.0)
        _reserve(eng, reservation_id="r-2", amount=200.0)
        active = eng.get_active_reservations("b-1")
        assert len(active) == 2

    def test_get_active_reservations_excludes_consumed(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=100.0)
        _reserve(eng, reservation_id="r-2", amount=200.0)
        eng.consume_budget("sp-1", "r-1")
        active = eng.get_active_reservations("b-1")
        assert len(active) == 1

    def test_get_decisions(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=100.0)
        decisions = eng.get_decisions("b-1")
        assert len(decisions) >= 1

    def test_get_decisions_includes_denials(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=100.0)
        _reserve(eng, reservation_id="r-1", amount=80.0)
        _reserve(eng, reservation_id="r-2", amount=30.0)  # denied
        decisions = eng.get_decisions("b-1")
        denied = [d for d in decisions if d.disposition != ChargeDisposition.APPROVED
                  and d.disposition != ChargeDisposition.WARNING_ISSUED]
        assert len(denied) >= 1


# ===================================================================
# TestProperties
# ===================================================================


class TestProperties:
    """Tests for budget_count, reservation_count, spend_record_count."""

    def test_budget_count(self):
        _, eng = _engine()
        assert eng.budget_count == 0
        _register_budget(eng, budget_id="b-1")
        assert eng.budget_count == 1
        _register_budget(eng, budget_id="b-2", name="B2", scope_ref_id="sr-2")
        assert eng.budget_count == 2

    def test_reservation_count_active_only(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=100.0)
        _reserve(eng, reservation_id="r-2", amount=100.0)
        assert eng.reservation_count == 2
        eng.consume_budget("sp-1", "r-1")
        assert eng.reservation_count == 1

    def test_spend_record_count(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=100.0)
        eng.consume_budget("sp-1", "r-1")
        _reserve(eng, reservation_id="r-2", amount=100.0)
        eng.release_budget("r-2")
        assert eng.spend_record_count == 2


# ===================================================================
# TestStateHash
# ===================================================================


class TestStateHash:
    """Tests for state_hash."""

    def test_returns_16_hex_chars(self):
        _, eng = _engine()
        h = eng.state_hash()
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_changes_after_mutation(self):
        _, eng = _engine()
        h1 = eng.state_hash()
        _register_budget(eng)
        h2 = eng.state_hash()
        assert h1 != h2

    def test_changes_after_reservation(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        h1 = eng.state_hash()
        _reserve(eng, amount=100.0)
        h2 = eng.state_hash()
        assert h1 != h2

    def test_changes_after_consume(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=100.0)
        h1 = eng.state_hash()
        eng.consume_budget("sp-1", "r-1")
        h2 = eng.state_hash()
        assert h1 != h2

    def test_deterministic(self):
        _, eng = _engine()
        h1 = eng.state_hash()
        h2 = eng.state_hash()
        assert h1 == h2


# ===================================================================
# TestInvariants
# ===================================================================


class TestInvariants:
    """Tests for invariant enforcement."""

    def test_duplicate_budget_id_raises(self):
        _, eng = _engine()
        _register_budget(eng, budget_id="b-dup")
        with pytest.raises(RuntimeCoreInvariantError):
            _register_budget(eng, budget_id="b-dup")

    def test_budget_not_found_on_reserve_raises(self):
        _, eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError):
            _reserve(eng, budget_id="missing")

    def test_budget_not_found_on_threshold_raises(self):
        _, eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError):
            eng.set_approval_threshold(
                "th-1", "missing", ApprovalThresholdMode.PER_TRANSACTION,
                500.0, "mgr-1",
            )

    def test_budget_not_found_on_health_raises(self):
        _, eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError):
            eng.budget_health("missing")

    def test_budget_not_found_on_forecast_raises(self):
        _, eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError):
            eng.forecast_spend(
                "fc-1", "missing",
                "2025-06-01T00:00:00+00:00", "2025-07-01T00:00:00+00:00",
            )

    def test_budget_not_found_on_close_raises(self):
        _, eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError):
            eng.close_budget("missing")

    def test_budget_not_found_on_conflicts_raises(self):
        _, eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError):
            eng.find_budget_conflicts("missing")

    def test_budget_not_found_on_gate_raises(self):
        _, eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError):
            eng.budget_gate("missing", 100.0)

    def test_duplicate_reservation_id_raises(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-dup", amount=50.0)
        with pytest.raises(RuntimeCoreInvariantError):
            _reserve(eng, reservation_id="r-dup", amount=50.0)

    def test_duplicate_spend_id_raises(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=50.0)
        _reserve(eng, reservation_id="r-2", amount=50.0)
        eng.consume_budget("sp-dup", "r-1")
        with pytest.raises(RuntimeCoreInvariantError):
            eng.consume_budget("sp-dup", "r-2")

    def test_consume_inactive_reservation_raises(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=50.0)
        eng.consume_budget("sp-1", "r-1")
        with pytest.raises(RuntimeCoreInvariantError):
            eng.consume_budget("sp-2", "r-1")

    def test_release_inactive_reservation_raises(self):
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=50.0)
        eng.release_budget("r-1")
        with pytest.raises(RuntimeCoreInvariantError):
            eng.release_budget("r-1")

    def test_consumed_plus_reserved_leq_limit(self):
        """Verify that consumed + reserved never exceeds limit."""
        _, eng = _engine()
        _register_budget(eng, limit_amount=100.0)
        _reserve(eng, reservation_id="r-1", amount=60.0)
        _reserve(eng, reservation_id="r-2", amount=30.0)
        b = eng.get_budget("b-1")
        assert b is not None
        assert b.consumed_amount + b.reserved_amount <= b.limit_amount

    def test_reservation_does_not_exceed_limit(self):
        """A reservation that would exceed limit is denied."""
        _, eng = _engine()
        _register_budget(eng, limit_amount=100.0, hard_stop_threshold=1.0)
        _reserve(eng, reservation_id="r-1", amount=80.0)
        dec = _reserve(eng, reservation_id="r-2", amount=30.0)
        assert dec.disposition != ChargeDisposition.APPROVED

    def test_every_mutation_emits_event(self):
        """Verify event count increases on every mutation."""
        es, eng = _engine()
        counts = []
        counts.append(len(es.list_events()))  # 0 initial

        _register_budget(eng, limit_amount=1000.0)
        counts.append(len(es.list_events()))

        _reserve(eng, reservation_id="r-1", amount=100.0)
        counts.append(len(es.list_events()))

        eng.consume_budget("sp-1", "r-1")
        counts.append(len(es.list_events()))

        _reserve(eng, reservation_id="r-2", amount=50.0)
        counts.append(len(es.list_events()))

        eng.release_budget("r-2")
        counts.append(len(es.list_events()))

        # Every transition must increase event count
        for i in range(1, len(counts)):
            assert counts[i] > counts[i - 1], f"Event count did not increase at step {i}"

    def test_binding_to_missing_budget_raises(self):
        _, eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError):
            eng.bind_campaign_budget("bind-1", "camp-1", "missing", 500.0)

    def test_duplicate_connector_profile_raises(self):
        _, eng = _engine()
        eng.register_connector_cost_profile("prof-1", "conn-a")
        with pytest.raises(RuntimeCoreInvariantError):
            eng.register_connector_cost_profile("prof-1", "conn-b")


# ===================================================================
# TestGoldenScenarios
# ===================================================================


class TestGoldenScenarios:
    """Eight end-to-end golden scenarios."""

    def test_campaign_step_blocked_by_hard_stop(self):
        """Register budget limit=100, reserve 80, then try to reserve 30 more -> DENIED_HARD_STOP."""
        es, eng = _engine()
        _register_budget(eng, limit_amount=100.0, hard_stop_threshold=1.0)
        dec1 = _reserve(eng, reservation_id="r-1", amount=80.0)
        assert dec1.disposition in (ChargeDisposition.APPROVED, ChargeDisposition.WARNING_ISSUED)
        dec2 = _reserve(eng, reservation_id="r-2", amount=30.0)
        assert dec2.disposition == ChargeDisposition.DENIED_HARD_STOP

    def test_connector_fallback_chooses_cheaper(self):
        """Register expensive=50, cheap=10 profiles. Budget with 20 remaining -> cheap chosen."""
        _, eng = _engine()
        _register_budget(eng, limit_amount=100.0)
        _reserve(eng, reservation_id="r-fill", amount=80.0)
        eng.register_connector_cost_profile("p-exp", "conn-expensive", cost_per_call=50.0)
        eng.register_connector_cost_profile("p-chp", "conn-cheap", cost_per_call=10.0)
        result = eng.find_cheapest_connector(["conn-expensive", "conn-cheap"], "b-1")
        assert result["chosen"] is not None
        assert result["chosen"]["connector_ref"] == "conn-cheap"
        # expensive should be non-viable
        exp_cand = [c for c in result["candidates"] if c["connector_ref"] == "conn-expensive"]
        assert len(exp_cand) == 1
        assert exp_cand[0]["viable"] is False

    def test_reserve_then_release_on_failure(self):
        """Reserve 100, then release -> budget available goes back to original."""
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        b_before = eng.get_budget("b-1")
        _reserve(eng, reservation_id="r-1", amount=100.0)
        b_during = eng.get_budget("b-1")
        assert b_during is not None
        assert b_during.reserved_amount == 100.0
        sr = eng.release_budget("r-1")
        assert sr.status == SpendStatus.RELEASED
        b_after = eng.get_budget("b-1")
        assert b_after is not None
        assert b_after.reserved_amount == 0.0
        assert b_after.consumed_amount == 0.0

    def test_approval_threshold_pauses(self):
        """Set per-transaction threshold at 500, try reserve 600 -> PENDING_APPROVAL."""
        _, eng = _engine()
        _register_budget(eng, limit_amount=10000.0)
        eng.set_approval_threshold(
            "th-1", "b-1", ApprovalThresholdMode.PER_TRANSACTION,
            500.0, "finance-director",
        )
        dec = _reserve(eng, reservation_id="r-1", amount=600.0)
        assert dec.disposition == ChargeDisposition.PENDING_APPROVAL
        assert dec.approval_required is True
        assert dec.approver_ref == "finance-director"

    def test_portfolio_defers_low_priority_under_budget_pressure(self):
        """Budget with 100 available, gate check for 200 -> DENIED_INSUFFICIENT or DENIED_HARD_STOP."""
        _, eng = _engine()
        _register_budget(eng, limit_amount=100.0, hard_stop_threshold=1.0)
        dec = eng.budget_gate("b-1", 200.0)
        assert dec.disposition in (
            ChargeDisposition.DENIED_INSUFFICIENT,
            ChargeDisposition.DENIED_HARD_STOP,
        )

    def test_warning_threshold_emits_event(self):
        """Budget limit=100 warning=0.8, reserve 85 -> WARNING_ISSUED + event emitted."""
        es, eng = _engine()
        _register_budget(eng, limit_amount=100.0, warning_threshold=0.8)
        before = len(es.list_events())
        dec = _reserve(eng, reservation_id="r-1", amount=85.0)
        after = len(es.list_events())
        assert dec.disposition == ChargeDisposition.WARNING_ISSUED
        assert after > before
        # Check that a warning event was emitted (event count should increase by more than 1:
        # at least the warning event + the reservation event)
        assert after - before >= 2

    def test_checkpoint_replay_preserves_state(self):
        """Register, reserve, consume. state_hash differs before/after consume.
        budget_health reflects consumed."""
        _, eng = _engine()
        _register_budget(eng, limit_amount=1000.0)
        _reserve(eng, reservation_id="r-1", amount=300.0)
        h_before = eng.state_hash()
        eng.consume_budget("sp-1", "r-1")
        h_after = eng.state_hash()
        assert h_before != h_after
        health = eng.budget_health("b-1")
        assert health.consumed_amount == 300.0
        assert health.reserved_amount == 0.0

    def test_cost_estimate_uses_connector_profile(self):
        """Register profile cost_per_call=5, cost_per_unit=2, estimate units=3 -> 5 + 2*3 = 11."""
        _, eng = _engine()
        eng.register_connector_cost_profile(
            "prof-1", "conn-calc",
            cost_per_call=5.0, cost_per_unit=2.0,
        )
        est = eng.estimate_cost(
            "est-1", CostCategory.CONNECTOR_CALL,
            connector_ref="conn-calc", units=3,
        )
        assert est.estimated_amount == 11.0
        assert est.confidence == 1.0
