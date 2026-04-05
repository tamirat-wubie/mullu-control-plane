"""Comprehensive tests for OptimizationRuntimeEngine.

Covers: constructor validation, create_request, add_constraint, all seven
optimize_* families, build_plan, estimate_impact, decide_recommendation,
queries, properties, state_hash, event emission, and 8 golden scenarios.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.optimization_runtime import OptimizationRuntimeEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.optimization_runtime import (
    OptimizationCandidate,
    OptimizationConstraint,
    OptimizationImpactEstimate,
    OptimizationPlan,
    OptimizationRecommendation,
    OptimizationRequest,
    OptimizationResult,
    OptimizationScope,
    OptimizationStrategy,
    OptimizationTarget,
    RecommendationDecision,
    RecommendationDisposition,
    RecommendationSeverity,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def es() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture
def engine(es: EventSpineEngine) -> OptimizationRuntimeEngine:
    return OptimizationRuntimeEngine(es)


def _make_request(engine: OptimizationRuntimeEngine, rid: str = "req-1",
                  target: OptimizationTarget = OptimizationTarget.CONNECTOR_SELECTION,
                  **kwargs) -> OptimizationRequest:
    return engine.create_request(rid, target, **kwargs)


# ===================================================================
# 1. Constructor validation
# ===================================================================


class TestConstructor:
    def test_accepts_event_spine(self, es):
        eng = OptimizationRuntimeEngine(es)
        assert eng.request_count == 0

    def test_rejects_none(self):
        with pytest.raises(RuntimeCoreInvariantError):
            OptimizationRuntimeEngine(None)

    def test_rejects_string(self):
        with pytest.raises(RuntimeCoreInvariantError):
            OptimizationRuntimeEngine("not-an-engine")

    def test_rejects_dict(self):
        with pytest.raises(RuntimeCoreInvariantError):
            OptimizationRuntimeEngine({})

    def test_rejects_int(self):
        with pytest.raises(RuntimeCoreInvariantError):
            OptimizationRuntimeEngine(42)

    def test_rejects_list(self):
        with pytest.raises(RuntimeCoreInvariantError):
            OptimizationRuntimeEngine([])

    def test_initial_counts_are_zero(self, engine):
        assert engine.request_count == 0
        assert engine.recommendation_count == 0
        assert engine.plan_count == 0


# ===================================================================
# 2. create_request
# ===================================================================


class TestCreateRequest:
    def test_basic_creation(self, engine):
        req = _make_request(engine)
        assert isinstance(req, OptimizationRequest)
        assert req.request_id == "req-1"
        assert req.target == OptimizationTarget.CONNECTOR_SELECTION

    def test_default_strategy(self, engine):
        req = _make_request(engine)
        assert req.strategy == OptimizationStrategy.BALANCED

    def test_custom_strategy(self, engine):
        req = _make_request(engine, strategy=OptimizationStrategy.COST_MINIMIZATION)
        assert req.strategy == OptimizationStrategy.COST_MINIMIZATION

    def test_default_scope(self, engine):
        req = _make_request(engine)
        assert req.scope == OptimizationScope.GLOBAL

    def test_custom_scope(self, engine):
        req = _make_request(engine, scope=OptimizationScope.CAMPAIGN)
        assert req.scope == OptimizationScope.CAMPAIGN

    def test_default_priority(self, engine):
        req = _make_request(engine)
        assert req.priority == "normal"

    def test_custom_priority(self, engine):
        req = _make_request(engine, priority="high")
        assert req.priority == "high"

    def test_default_max_candidates(self, engine):
        req = _make_request(engine)
        assert req.max_candidates == 10

    def test_custom_max_candidates(self, engine):
        req = _make_request(engine, max_candidates=5)
        assert req.max_candidates == 5

    def test_scope_ref_id_defaults_to_request_id(self, engine):
        req = _make_request(engine)
        assert req.scope_ref_id == "req-1"

    def test_custom_scope_ref_id(self, engine):
        req = _make_request(engine, scope_ref_id="my-scope")
        assert req.scope_ref_id == "my-scope"

    def test_reason(self, engine):
        req = _make_request(engine, reason="testing")
        assert req.reason == "testing"

    def test_metadata(self, engine):
        req = _make_request(engine, metadata={"key": "value"})
        assert req.metadata["key"] == "value"

    def test_duplicate_raises(self, engine):
        _make_request(engine, rid="dup-1")
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            _make_request(engine, rid="dup-1")

    def test_request_count_increments(self, engine):
        assert engine.request_count == 0
        _make_request(engine, rid="r1")
        assert engine.request_count == 1
        _make_request(engine, rid="r2")
        assert engine.request_count == 2

    def test_all_targets(self, engine):
        for i, t in enumerate(OptimizationTarget):
            req = engine.create_request(f"t-{i}", t)
            assert req.target == t

    def test_all_strategies(self, engine):
        for i, s in enumerate(OptimizationStrategy):
            req = engine.create_request(f"s-{i}", OptimizationTarget.CAMPAIGN_COST, strategy=s)
            assert req.strategy == s

    def test_created_at_populated(self, engine):
        req = _make_request(engine)
        assert req.created_at != ""

    def test_get_request_returns_created(self, engine):
        _make_request(engine, rid="x")
        assert engine.get_request("x") is not None
        assert engine.get_request("x").request_id == "x"

    def test_get_request_missing_returns_none(self, engine):
        assert engine.get_request("nope") is None

    def test_event_emitted_on_create(self, engine, es):
        before = len(es.list_events())
        _make_request(engine)
        after = len(es.list_events())
        assert after > before


# ===================================================================
# 3. add_constraint
# ===================================================================


class TestAddConstraint:
    def test_basic_add(self, engine):
        _make_request(engine)
        c = engine.add_constraint("c1", "req-1", "budget_limit")
        assert isinstance(c, OptimizationConstraint)
        assert c.constraint_id == "c1"

    def test_missing_request_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.add_constraint("c1", "nonexistent", "limit")

    def test_constraint_fields(self, engine):
        _make_request(engine)
        c = engine.add_constraint("c1", "req-1", "cost_cap",
                                  field_name="cost", operator="<=", value="100")
        assert c.field_name == "cost"
        assert c.operator == "<="
        assert c.value == "100"

    def test_hard_default_true(self, engine):
        _make_request(engine)
        c = engine.add_constraint("c1", "req-1", "limit")
        assert c.hard is True

    def test_soft_constraint(self, engine):
        _make_request(engine)
        c = engine.add_constraint("c1", "req-1", "preference", hard=False)
        assert c.hard is False

    def test_get_constraints(self, engine):
        _make_request(engine)
        engine.add_constraint("c1", "req-1", "a")
        engine.add_constraint("c2", "req-1", "b")
        constraints = engine.get_constraints("req-1")
        assert isinstance(constraints, tuple)
        assert len(constraints) == 2

    def test_get_constraints_empty(self, engine):
        _make_request(engine)
        assert engine.get_constraints("req-1") == ()

    def test_multiple_constraints_on_request(self, engine):
        _make_request(engine)
        for i in range(5):
            engine.add_constraint(f"c{i}", "req-1", f"type-{i}")
        assert len(engine.get_constraints("req-1")) == 5


# ===================================================================
# 4. optimize_connectors
# ===================================================================


class TestOptimizeConnectors:
    def test_success_rate_below_09_generates_rec(self, engine):
        _make_request(engine)
        recs = engine.optimize_connectors("req-1", [
            {"connector_ref": "conn-a", "success_rate": 0.85, "cost_per_call": 0.5, "latency_seconds": 1.0},
        ])
        assert len(recs) == 1
        assert "degraded connector" in recs[0].title.lower()

    def test_success_rate_at_09_no_rec(self, engine):
        _make_request(engine)
        recs = engine.optimize_connectors("req-1", [
            {"connector_ref": "conn-a", "success_rate": 0.9, "cost_per_call": 0.5, "latency_seconds": 1.0},
        ])
        assert len(recs) == 0

    def test_success_rate_above_09_no_rec(self, engine):
        _make_request(engine)
        recs = engine.optimize_connectors("req-1", [
            {"connector_ref": "conn-a", "success_rate": 0.95, "cost_per_call": 0.5, "latency_seconds": 1.0},
        ])
        assert len(recs) == 0

    def test_success_rate_below_07_is_urgent(self, engine):
        _make_request(engine)
        recs = engine.optimize_connectors("req-1", [
            {"connector_ref": "conn-a", "success_rate": 0.65, "cost_per_call": 0.5, "latency_seconds": 1.0},
        ])
        assert recs[0].severity == RecommendationSeverity.URGENT

    def test_success_rate_between_07_and_09_is_recommended(self, engine):
        _make_request(engine)
        recs = engine.optimize_connectors("req-1", [
            {"connector_ref": "conn-a", "success_rate": 0.8, "cost_per_call": 0.5, "latency_seconds": 1.0},
        ])
        assert recs[0].severity == RecommendationSeverity.RECOMMENDED

    def test_multiple_connectors_mixed(self, engine):
        _make_request(engine)
        recs = engine.optimize_connectors("req-1", [
            {"connector_ref": "good", "success_rate": 0.95, "cost_per_call": 1.0, "latency_seconds": 0.5},
            {"connector_ref": "bad", "success_rate": 0.5, "cost_per_call": 2.0, "latency_seconds": 2.0},
            {"connector_ref": "ok", "success_rate": 0.88, "cost_per_call": 0.8, "latency_seconds": 1.0},
        ])
        assert len(recs) == 2  # bad and ok
        refs = [r.scope_ref_id for r in recs]
        assert "bad" in refs
        assert "ok" in refs

    def test_empty_metrics_no_recs(self, engine):
        _make_request(engine)
        recs = engine.optimize_connectors("req-1", [])
        assert len(recs) == 0

    def test_score_is_unit_float(self, engine):
        _make_request(engine)
        recs = engine.optimize_connectors("req-1", [
            {"connector_ref": "c", "success_rate": 0.0, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])
        assert 0.0 <= recs[0].score <= 1.0

    def test_target_is_connector_selection(self, engine):
        _make_request(engine)
        recs = engine.optimize_connectors("req-1", [
            {"connector_ref": "c", "success_rate": 0.5, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])
        assert recs[0].target == OptimizationTarget.CONNECTOR_SELECTION

    def test_missing_request_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.optimize_connectors("nope", [])

    def test_recommendation_count_increases(self, engine):
        _make_request(engine)
        assert engine.recommendation_count == 0
        engine.optimize_connectors("req-1", [
            {"connector_ref": "c", "success_rate": 0.5, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])
        assert engine.recommendation_count == 1

    def test_event_emitted(self, engine, es):
        _make_request(engine)
        before = len(es.list_events())
        engine.optimize_connectors("req-1", [
            {"connector_ref": "c", "success_rate": 0.5, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])
        assert len(es.list_events()) > before


# ===================================================================
# 5. optimize_portfolio
# ===================================================================


class TestOptimizePortfolio:
    def test_blocked_campaigns_generate_rec(self, engine):
        _make_request(engine, target=OptimizationTarget.PORTFOLIO_BALANCE)
        recs = engine.optimize_portfolio("req-1", [
            {"campaign_id": "c1", "blocked": True, "overdue": False},
        ])
        assert len(recs) == 1
        assert "blocked" in recs[0].title.lower()

    def test_overdue_campaigns_generate_rec(self, engine):
        _make_request(engine, target=OptimizationTarget.PORTFOLIO_BALANCE)
        recs = engine.optimize_portfolio("req-1", [
            {"campaign_id": "c1", "blocked": False, "overdue": True},
        ])
        assert len(recs) == 1
        assert recs[0].severity == RecommendationSeverity.URGENT

    def test_both_blocked_and_overdue(self, engine):
        _make_request(engine, target=OptimizationTarget.PORTFOLIO_BALANCE)
        recs = engine.optimize_portfolio("req-1", [
            {"campaign_id": "c1", "blocked": True, "overdue": True},
        ])
        assert len(recs) == 2

    def test_no_issues_no_recs(self, engine):
        _make_request(engine, target=OptimizationTarget.PORTFOLIO_BALANCE)
        recs = engine.optimize_portfolio("req-1", [
            {"campaign_id": "c1", "blocked": False, "overdue": False},
        ])
        assert len(recs) == 0

    def test_many_blocked_is_urgent(self, engine):
        _make_request(engine, target=OptimizationTarget.PORTFOLIO_BALANCE)
        recs = engine.optimize_portfolio("req-1", [
            {"campaign_id": f"c{i}", "blocked": True, "overdue": False}
            for i in range(5)
        ])
        blocked_recs = [r for r in recs if "blocked" in r.title.lower()]
        assert blocked_recs[0].severity == RecommendationSeverity.URGENT

    def test_two_blocked_is_recommended(self, engine):
        _make_request(engine, target=OptimizationTarget.PORTFOLIO_BALANCE)
        recs = engine.optimize_portfolio("req-1", [
            {"campaign_id": "c1", "blocked": True, "overdue": False},
            {"campaign_id": "c2", "blocked": True, "overdue": False},
        ])
        blocked_recs = [r for r in recs if "blocked" in r.title.lower()]
        assert blocked_recs[0].severity == RecommendationSeverity.RECOMMENDED

    def test_empty_metrics_no_recs(self, engine):
        _make_request(engine, target=OptimizationTarget.PORTFOLIO_BALANCE)
        recs = engine.optimize_portfolio("req-1", [])
        assert len(recs) == 0

    def test_missing_request_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.optimize_portfolio("nope", [])

    def test_event_emitted(self, engine, es):
        _make_request(engine, target=OptimizationTarget.PORTFOLIO_BALANCE)
        before = len(es.list_events())
        engine.optimize_portfolio("req-1", [
            {"campaign_id": "c1", "blocked": True, "overdue": False},
        ])
        assert len(es.list_events()) > before


# ===================================================================
# 6. optimize_budget_allocation
# ===================================================================


class TestOptimizeBudgetAllocation:
    def test_burn_rate_above_09_generates_rec(self, engine):
        _make_request(engine, target=OptimizationTarget.BUDGET_ALLOCATION)
        recs = engine.optimize_budget_allocation("req-1", [
            {"budget_id": "b1", "burn_rate": 0.92, "cost_per_completion": 0.0, "utilization": 0.3},
        ])
        assert len(recs) == 1
        assert "burn" in recs[0].title.lower()

    def test_burn_rate_at_09_no_rec(self, engine):
        _make_request(engine, target=OptimizationTarget.BUDGET_ALLOCATION)
        recs = engine.optimize_budget_allocation("req-1", [
            {"budget_id": "b1", "burn_rate": 0.9, "cost_per_completion": 0.0, "utilization": 0.0},
        ])
        assert len(recs) == 0

    def test_burn_rate_above_095_is_critical(self, engine):
        _make_request(engine, target=OptimizationTarget.BUDGET_ALLOCATION)
        recs = engine.optimize_budget_allocation("req-1", [
            {"budget_id": "b1", "burn_rate": 0.97, "cost_per_completion": 0.0, "utilization": 0.0},
        ])
        burn_recs = [r for r in recs if "burn" in r.title.lower()]
        assert burn_recs[0].severity == RecommendationSeverity.CRITICAL

    def test_burn_rate_091_to_095_is_urgent(self, engine):
        _make_request(engine, target=OptimizationTarget.BUDGET_ALLOCATION)
        recs = engine.optimize_budget_allocation("req-1", [
            {"budget_id": "b1", "burn_rate": 0.93, "cost_per_completion": 0.0, "utilization": 0.0},
        ])
        burn_recs = [r for r in recs if "burn" in r.title.lower()]
        assert burn_recs[0].severity == RecommendationSeverity.URGENT

    def test_high_cpc_with_utilization_above_05(self, engine):
        _make_request(engine, target=OptimizationTarget.BUDGET_ALLOCATION)
        recs = engine.optimize_budget_allocation("req-1", [
            {"budget_id": "b1", "burn_rate": 0.5, "cost_per_completion": 500, "utilization": 0.6},
        ])
        assert len(recs) == 1
        assert "cost" in recs[0].title.lower()

    def test_high_cpc_low_utilization_no_rec(self, engine):
        _make_request(engine, target=OptimizationTarget.BUDGET_ALLOCATION)
        recs = engine.optimize_budget_allocation("req-1", [
            {"budget_id": "b1", "burn_rate": 0.5, "cost_per_completion": 500, "utilization": 0.4},
        ])
        assert len(recs) == 0

    def test_low_cpc_high_util_no_rec_below_score_threshold(self, engine):
        _make_request(engine, target=OptimizationTarget.BUDGET_ALLOCATION)
        # cpc=100 -> score = 100/1000 = 0.1 which is <= 0.3, no rec
        recs = engine.optimize_budget_allocation("req-1", [
            {"budget_id": "b1", "burn_rate": 0.5, "cost_per_completion": 100, "utilization": 0.6},
        ])
        assert len(recs) == 0

    def test_both_burn_and_cpc_trigger(self, engine):
        _make_request(engine, target=OptimizationTarget.BUDGET_ALLOCATION)
        recs = engine.optimize_budget_allocation("req-1", [
            {"budget_id": "b1", "burn_rate": 0.95, "cost_per_completion": 500, "utilization": 0.7},
        ])
        assert len(recs) == 2

    def test_below_all_thresholds_no_recs(self, engine):
        _make_request(engine, target=OptimizationTarget.BUDGET_ALLOCATION)
        recs = engine.optimize_budget_allocation("req-1", [
            {"budget_id": "b1", "burn_rate": 0.5, "cost_per_completion": 10, "utilization": 0.3},
        ])
        assert len(recs) == 0

    def test_multiple_budgets(self, engine):
        _make_request(engine, target=OptimizationTarget.BUDGET_ALLOCATION)
        recs = engine.optimize_budget_allocation("req-1", [
            {"budget_id": "b1", "burn_rate": 0.95, "cost_per_completion": 0, "utilization": 0.0},
            {"budget_id": "b2", "burn_rate": 0.96, "cost_per_completion": 0, "utilization": 0.0},
        ])
        assert len(recs) == 2

    def test_empty_metrics_no_recs(self, engine):
        _make_request(engine, target=OptimizationTarget.BUDGET_ALLOCATION)
        recs = engine.optimize_budget_allocation("req-1", [])
        assert len(recs) == 0

    def test_missing_request_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.optimize_budget_allocation("nope", [])

    def test_event_emitted(self, engine, es):
        _make_request(engine, target=OptimizationTarget.BUDGET_ALLOCATION)
        before = len(es.list_events())
        engine.optimize_budget_allocation("req-1", [
            {"budget_id": "b1", "burn_rate": 0.95, "cost_per_completion": 0, "utilization": 0.0},
        ])
        assert len(es.list_events()) > before


# ===================================================================
# 7. optimize_campaigns
# ===================================================================


class TestOptimizeCampaigns:
    def test_woh_above_3600_generates_rec(self, engine):
        _make_request(engine, target=OptimizationTarget.CAMPAIGN_DURATION)
        recs = engine.optimize_campaigns("req-1", [
            {"campaign_id": "c1", "waiting_on_human_seconds": 7200, "escalation_count": 0, "cost": 100},
        ])
        assert len(recs) == 1
        assert "wait" in recs[0].title.lower()

    def test_woh_at_3600_no_rec(self, engine):
        _make_request(engine, target=OptimizationTarget.CAMPAIGN_DURATION)
        recs = engine.optimize_campaigns("req-1", [
            {"campaign_id": "c1", "waiting_on_human_seconds": 3600, "escalation_count": 0, "cost": 100},
        ])
        assert len(recs) == 0

    def test_woh_below_3600_no_rec(self, engine):
        _make_request(engine, target=OptimizationTarget.CAMPAIGN_DURATION)
        recs = engine.optimize_campaigns("req-1", [
            {"campaign_id": "c1", "waiting_on_human_seconds": 1800, "escalation_count": 0, "cost": 100},
        ])
        assert len(recs) == 0

    def test_escalation_above_3_generates_rec(self, engine):
        _make_request(engine, target=OptimizationTarget.CAMPAIGN_DURATION)
        recs = engine.optimize_campaigns("req-1", [
            {"campaign_id": "c1", "waiting_on_human_seconds": 0, "escalation_count": 5, "cost": 100},
        ])
        assert len(recs) == 1
        assert "escalation" in recs[0].title.lower()

    def test_escalation_at_3_no_rec(self, engine):
        _make_request(engine, target=OptimizationTarget.CAMPAIGN_DURATION)
        recs = engine.optimize_campaigns("req-1", [
            {"campaign_id": "c1", "waiting_on_human_seconds": 0, "escalation_count": 3, "cost": 100},
        ])
        assert len(recs) == 0

    def test_escalation_above_5_is_urgent(self, engine):
        _make_request(engine, target=OptimizationTarget.CAMPAIGN_DURATION)
        recs = engine.optimize_campaigns("req-1", [
            {"campaign_id": "c1", "waiting_on_human_seconds": 0, "escalation_count": 7, "cost": 100},
        ])
        esc_recs = [r for r in recs if "escalation" in r.title.lower()]
        assert esc_recs[0].severity == RecommendationSeverity.URGENT

    def test_escalation_4_is_recommended(self, engine):
        _make_request(engine, target=OptimizationTarget.CAMPAIGN_DURATION)
        recs = engine.optimize_campaigns("req-1", [
            {"campaign_id": "c1", "waiting_on_human_seconds": 0, "escalation_count": 4, "cost": 100},
        ])
        esc_recs = [r for r in recs if "escalation" in r.title.lower()]
        assert esc_recs[0].severity == RecommendationSeverity.RECOMMENDED

    def test_both_woh_and_escalation(self, engine):
        _make_request(engine, target=OptimizationTarget.CAMPAIGN_DURATION)
        recs = engine.optimize_campaigns("req-1", [
            {"campaign_id": "c1", "waiting_on_human_seconds": 7200, "escalation_count": 5, "cost": 100},
        ])
        assert len(recs) == 2

    def test_below_both_thresholds_no_recs(self, engine):
        _make_request(engine, target=OptimizationTarget.CAMPAIGN_DURATION)
        recs = engine.optimize_campaigns("req-1", [
            {"campaign_id": "c1", "waiting_on_human_seconds": 100, "escalation_count": 1, "cost": 50},
        ])
        assert len(recs) == 0

    def test_empty_metrics_no_recs(self, engine):
        _make_request(engine, target=OptimizationTarget.CAMPAIGN_DURATION)
        recs = engine.optimize_campaigns("req-1", [])
        assert len(recs) == 0

    def test_missing_request_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.optimize_campaigns("nope", [])

    def test_event_emitted(self, engine, es):
        _make_request(engine, target=OptimizationTarget.CAMPAIGN_DURATION)
        before = len(es.list_events())
        engine.optimize_campaigns("req-1", [
            {"campaign_id": "c1", "waiting_on_human_seconds": 7200, "escalation_count": 0, "cost": 0},
        ])
        assert len(es.list_events()) > before


# ===================================================================
# 8. optimize_schedule
# ===================================================================


class TestOptimizeSchedule:
    def test_qhv_above_zero_generates_rec(self, engine):
        _make_request(engine, target=OptimizationTarget.SCHEDULE_EFFICIENCY)
        recs = engine.optimize_schedule("req-1", [
            {"identity_ref": "id-1", "quiet_hours_violations": 3},
        ])
        assert len(recs) == 1
        assert "quiet" in recs[0].title.lower()

    def test_qhv_zero_no_rec(self, engine):
        _make_request(engine, target=OptimizationTarget.SCHEDULE_EFFICIENCY)
        recs = engine.optimize_schedule("req-1", [
            {"identity_ref": "id-1", "quiet_hours_violations": 0},
        ])
        assert len(recs) == 0

    def test_multiple_identities(self, engine):
        _make_request(engine, target=OptimizationTarget.SCHEDULE_EFFICIENCY)
        recs = engine.optimize_schedule("req-1", [
            {"identity_ref": "id-1", "quiet_hours_violations": 2},
            {"identity_ref": "id-2", "quiet_hours_violations": 0},
            {"identity_ref": "id-3", "quiet_hours_violations": 5},
        ])
        assert len(recs) == 2

    def test_target_is_channel_routing(self, engine):
        _make_request(engine, target=OptimizationTarget.SCHEDULE_EFFICIENCY)
        recs = engine.optimize_schedule("req-1", [
            {"identity_ref": "id-1", "quiet_hours_violations": 1},
        ])
        assert recs[0].target == OptimizationTarget.CHANNEL_ROUTING

    def test_empty_metrics_no_recs(self, engine):
        _make_request(engine, target=OptimizationTarget.SCHEDULE_EFFICIENCY)
        recs = engine.optimize_schedule("req-1", [])
        assert len(recs) == 0

    def test_missing_request_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.optimize_schedule("nope", [])

    def test_score_capped_at_1(self, engine):
        _make_request(engine, target=OptimizationTarget.SCHEDULE_EFFICIENCY)
        recs = engine.optimize_schedule("req-1", [
            {"identity_ref": "id-1", "quiet_hours_violations": 100},
        ])
        assert recs[0].score <= 1.0

    def test_event_emitted(self, engine, es):
        _make_request(engine, target=OptimizationTarget.SCHEDULE_EFFICIENCY)
        before = len(es.list_events())
        engine.optimize_schedule("req-1", [
            {"identity_ref": "id-1", "quiet_hours_violations": 1},
        ])
        assert len(es.list_events()) > before


# ===================================================================
# 9. optimize_escalation
# ===================================================================


class TestOptimizeEscalation:
    def test_fp_rate_above_03_generates_rec(self, engine):
        _make_request(engine, target=OptimizationTarget.ESCALATION_POLICY)
        recs = engine.optimize_escalation("req-1", [
            {"policy_ref": "pol-1", "total_escalations": 10, "false_positive_count": 5},
        ])
        assert len(recs) == 1
        assert "false positive" in recs[0].title.lower()

    def test_fp_rate_at_03_no_rec(self, engine):
        _make_request(engine, target=OptimizationTarget.ESCALATION_POLICY)
        recs = engine.optimize_escalation("req-1", [
            {"policy_ref": "pol-1", "total_escalations": 10, "false_positive_count": 3},
        ])
        assert len(recs) == 0

    def test_fp_rate_below_03_no_rec(self, engine):
        _make_request(engine, target=OptimizationTarget.ESCALATION_POLICY)
        recs = engine.optimize_escalation("req-1", [
            {"policy_ref": "pol-1", "total_escalations": 10, "false_positive_count": 2},
        ])
        assert len(recs) == 0

    def test_zero_total_escalations_no_rec(self, engine):
        _make_request(engine, target=OptimizationTarget.ESCALATION_POLICY)
        recs = engine.optimize_escalation("req-1", [
            {"policy_ref": "pol-1", "total_escalations": 0, "false_positive_count": 0},
        ])
        assert len(recs) == 0

    def test_multiple_policies(self, engine):
        _make_request(engine, target=OptimizationTarget.ESCALATION_POLICY)
        recs = engine.optimize_escalation("req-1", [
            {"policy_ref": "pol-1", "total_escalations": 10, "false_positive_count": 5},
            {"policy_ref": "pol-2", "total_escalations": 10, "false_positive_count": 1},
            {"policy_ref": "pol-3", "total_escalations": 20, "false_positive_count": 12},
        ])
        assert len(recs) == 2

    def test_target_is_escalation_policy(self, engine):
        _make_request(engine, target=OptimizationTarget.ESCALATION_POLICY)
        recs = engine.optimize_escalation("req-1", [
            {"policy_ref": "pol-1", "total_escalations": 10, "false_positive_count": 5},
        ])
        assert recs[0].target == OptimizationTarget.ESCALATION_POLICY

    def test_empty_metrics_no_recs(self, engine):
        _make_request(engine, target=OptimizationTarget.ESCALATION_POLICY)
        recs = engine.optimize_escalation("req-1", [])
        assert len(recs) == 0

    def test_missing_request_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.optimize_escalation("nope", [])

    def test_event_emitted(self, engine, es):
        _make_request(engine, target=OptimizationTarget.ESCALATION_POLICY)
        before = len(es.list_events())
        engine.optimize_escalation("req-1", [
            {"policy_ref": "pol-1", "total_escalations": 10, "false_positive_count": 5},
        ])
        assert len(es.list_events()) > before


# ===================================================================
# 10. optimize_domain_pack_selection
# ===================================================================


class TestOptimizeDomainPackSelection:
    def test_fault_rate_above_01_generates_rec(self, engine):
        _make_request(engine, target=OptimizationTarget.DOMAIN_PACK_SELECTION)
        recs = engine.optimize_domain_pack_selection("req-1", [
            {"domain_pack_id": "dp-1", "fault_rate": 0.2},
        ])
        assert len(recs) == 1
        assert "domain pack" in recs[0].title.lower()

    def test_fault_rate_at_01_no_rec(self, engine):
        _make_request(engine, target=OptimizationTarget.DOMAIN_PACK_SELECTION)
        recs = engine.optimize_domain_pack_selection("req-1", [
            {"domain_pack_id": "dp-1", "fault_rate": 0.1},
        ])
        assert len(recs) == 0

    def test_fault_rate_below_01_no_rec(self, engine):
        _make_request(engine, target=OptimizationTarget.DOMAIN_PACK_SELECTION)
        recs = engine.optimize_domain_pack_selection("req-1", [
            {"domain_pack_id": "dp-1", "fault_rate": 0.05},
        ])
        assert len(recs) == 0

    def test_fault_rate_above_03_is_urgent(self, engine):
        _make_request(engine, target=OptimizationTarget.DOMAIN_PACK_SELECTION)
        recs = engine.optimize_domain_pack_selection("req-1", [
            {"domain_pack_id": "dp-1", "fault_rate": 0.35},
        ])
        assert recs[0].severity == RecommendationSeverity.URGENT

    def test_fault_rate_between_01_and_03_is_recommended(self, engine):
        _make_request(engine, target=OptimizationTarget.DOMAIN_PACK_SELECTION)
        recs = engine.optimize_domain_pack_selection("req-1", [
            {"domain_pack_id": "dp-1", "fault_rate": 0.2},
        ])
        assert recs[0].severity == RecommendationSeverity.RECOMMENDED

    def test_target_is_fault_avoidance(self, engine):
        _make_request(engine, target=OptimizationTarget.DOMAIN_PACK_SELECTION)
        recs = engine.optimize_domain_pack_selection("req-1", [
            {"domain_pack_id": "dp-1", "fault_rate": 0.2},
        ])
        assert recs[0].target == OptimizationTarget.FAULT_AVOIDANCE

    def test_multiple_packs(self, engine):
        _make_request(engine, target=OptimizationTarget.DOMAIN_PACK_SELECTION)
        recs = engine.optimize_domain_pack_selection("req-1", [
            {"domain_pack_id": "dp-1", "fault_rate": 0.2},
            {"domain_pack_id": "dp-2", "fault_rate": 0.05},
            {"domain_pack_id": "dp-3", "fault_rate": 0.5},
        ])
        assert len(recs) == 2

    def test_empty_metrics_no_recs(self, engine):
        _make_request(engine, target=OptimizationTarget.DOMAIN_PACK_SELECTION)
        recs = engine.optimize_domain_pack_selection("req-1", [])
        assert len(recs) == 0

    def test_score_capped_at_1(self, engine):
        _make_request(engine, target=OptimizationTarget.DOMAIN_PACK_SELECTION)
        recs = engine.optimize_domain_pack_selection("req-1", [
            {"domain_pack_id": "dp-1", "fault_rate": 5.0},
        ])
        assert recs[0].score <= 1.0

    def test_missing_request_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.optimize_domain_pack_selection("nope", [])

    def test_event_emitted(self, engine, es):
        _make_request(engine, target=OptimizationTarget.DOMAIN_PACK_SELECTION)
        before = len(es.list_events())
        engine.optimize_domain_pack_selection("req-1", [
            {"domain_pack_id": "dp-1", "fault_rate": 0.2},
        ])
        assert len(es.list_events()) > before


# ===================================================================
# 11. build_plan
# ===================================================================


class TestBuildPlan:
    def test_basic_build(self, engine):
        _make_request(engine)
        engine.optimize_connectors("req-1", [
            {"connector_ref": "c1", "success_rate": 0.5, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])
        plan = engine.build_plan("plan-1", "req-1", "Connector Fix Plan")
        assert isinstance(plan, OptimizationPlan)
        assert plan.plan_id == "plan-1"
        assert plan.title == "Connector Fix Plan"

    def test_plan_has_recommendation_ids(self, engine):
        _make_request(engine)
        engine.optimize_connectors("req-1", [
            {"connector_ref": "c1", "success_rate": 0.5, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])
        plan = engine.build_plan("plan-1", "req-1", "Plan")
        assert len(plan.recommendation_ids) == 1

    def test_plan_sorted_by_score_desc(self, engine):
        _make_request(engine)
        engine.optimize_connectors("req-1", [
            {"connector_ref": "low", "success_rate": 0.85, "cost_per_call": 1.0, "latency_seconds": 1.0},
            {"connector_ref": "high", "success_rate": 0.3, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])
        plan = engine.build_plan("plan-1", "req-1", "Plan")
        recs = engine.get_recommendations("req-1")
        # The plan's first rec_id should correspond to the highest score
        plan_rec_ids = list(plan.recommendation_ids)
        scores = [r.score for r in recs if r.recommendation_id in plan_rec_ids]
        # build_plan sorts by score desc, so first rec id should have highest score
        first_rec = next(r for r in recs if r.recommendation_id == plan_rec_ids[0])
        last_rec = next(r for r in recs if r.recommendation_id == plan_rec_ids[-1])
        assert first_rec.score >= last_rec.score

    def test_no_recs_empty_plan(self, engine):
        _make_request(engine)
        engine.optimize_connectors("req-1", [
            {"connector_ref": "c1", "success_rate": 0.95, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])
        plan = engine.build_plan("plan-1", "req-1", "Empty Plan")
        assert len(plan.recommendation_ids) == 0
        assert plan.feasible is False

    def test_feasible_when_recs_exist(self, engine):
        _make_request(engine)
        engine.optimize_connectors("req-1", [
            {"connector_ref": "c1", "success_rate": 0.5, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])
        plan = engine.build_plan("plan-1", "req-1", "Plan")
        assert plan.feasible is True

    def test_total_improvement(self, engine):
        _make_request(engine)
        engine.optimize_connectors("req-1", [
            {"connector_ref": "c1", "success_rate": 0.5, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])
        plan = engine.build_plan("plan-1", "req-1", "Plan")
        assert plan.total_estimated_improvement_pct > 0

    def test_missing_request_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.build_plan("plan-1", "nope", "Plan")

    def test_plan_count_increments(self, engine):
        _make_request(engine, rid="r1")
        _make_request(engine, rid="r2")
        assert engine.plan_count == 0
        engine.build_plan("p1", "r1", "P1")
        assert engine.plan_count == 1
        engine.build_plan("p2", "r2", "P2")
        assert engine.plan_count == 2

    def test_event_emitted(self, engine, es):
        _make_request(engine)
        before = len(es.list_events())
        engine.build_plan("plan-1", "req-1", "Plan")
        assert len(es.list_events()) > before

    def test_plan_with_constraints(self, engine):
        _make_request(engine)
        engine.add_constraint("c1", "req-1", "cost_cap", hard=True)
        engine.optimize_connectors("req-1", [
            {"connector_ref": "c1", "success_rate": 0.5, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])
        plan = engine.build_plan("plan-1", "req-1", "Plan")
        assert plan is not None


# ===================================================================
# 12. estimate_impact
# ===================================================================


class TestEstimateImpact:
    def _make_rec(self, engine):
        _make_request(engine)
        recs = engine.optimize_connectors("req-1", [
            {"connector_ref": "c1", "success_rate": 0.5, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])
        return recs[0].recommendation_id

    def test_basic_impact(self, engine):
        rec_id = self._make_rec(engine)
        impact = engine.estimate_impact(rec_id, "success_rate", 0.5, 0.9)
        assert isinstance(impact, OptimizationImpactEstimate)
        assert impact.metric_name == "success_rate"

    def test_improvement_calculation(self, engine):
        rec_id = self._make_rec(engine)
        impact = engine.estimate_impact(rec_id, "success_rate", 0.5, 0.9)
        # improvement = (0.9 - 0.5) / 0.5 * 100 = 80%
        assert abs(impact.improvement_pct - 80.0) < 0.01

    def test_improvement_negative(self, engine):
        rec_id = self._make_rec(engine)
        impact = engine.estimate_impact(rec_id, "cost", 100.0, 80.0)
        # improvement = (80 - 100) / 100 * 100 = -20%
        assert abs(impact.improvement_pct - (-20.0)) < 0.01

    def test_current_value_zero(self, engine):
        rec_id = self._make_rec(engine)
        impact = engine.estimate_impact(rec_id, "metric", 0.0, 10.0)
        assert impact.improvement_pct == 0.0

    def test_default_confidence(self, engine):
        rec_id = self._make_rec(engine)
        impact = engine.estimate_impact(rec_id, "m", 1.0, 2.0)
        assert impact.confidence == 0.8

    def test_custom_confidence(self, engine):
        rec_id = self._make_rec(engine)
        impact = engine.estimate_impact(rec_id, "m", 1.0, 2.0, confidence=0.5)
        assert impact.confidence == 0.5

    def test_default_risk_level(self, engine):
        rec_id = self._make_rec(engine)
        impact = engine.estimate_impact(rec_id, "m", 1.0, 2.0)
        assert impact.risk_level == "low"

    def test_custom_risk_level(self, engine):
        rec_id = self._make_rec(engine)
        impact = engine.estimate_impact(rec_id, "m", 1.0, 2.0, risk_level="high")
        assert impact.risk_level == "high"

    def test_unknown_rec_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.estimate_impact("bad-rec", "m", 1.0, 2.0)

    def test_projected_value_stored(self, engine):
        rec_id = self._make_rec(engine)
        impact = engine.estimate_impact(rec_id, "m", 10.0, 15.0)
        assert impact.current_value == 10.0
        assert impact.projected_value == 15.0

    def test_estimate_id_populated(self, engine):
        rec_id = self._make_rec(engine)
        impact = engine.estimate_impact(rec_id, "m", 1.0, 2.0)
        assert impact.estimate_id != ""


# ===================================================================
# 13. decide_recommendation
# ===================================================================


class TestDecideRecommendation:
    def _make_rec(self, engine):
        _make_request(engine)
        recs = engine.optimize_connectors("req-1", [
            {"connector_ref": "c1", "success_rate": 0.5, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])
        return recs[0].recommendation_id

    def test_accept_recommendation(self, engine):
        rec_id = self._make_rec(engine)
        dec = engine.decide_recommendation("d1", rec_id, RecommendationDisposition.ACCEPTED)
        assert isinstance(dec, RecommendationDecision)
        assert dec.disposition == RecommendationDisposition.ACCEPTED

    def test_reject_recommendation(self, engine):
        rec_id = self._make_rec(engine)
        dec = engine.decide_recommendation("d1", rec_id, RecommendationDisposition.REJECTED)
        assert dec.disposition == RecommendationDisposition.REJECTED

    def test_defer_recommendation(self, engine):
        rec_id = self._make_rec(engine)
        dec = engine.decide_recommendation("d1", rec_id, RecommendationDisposition.DEFERRED)
        assert dec.disposition == RecommendationDisposition.DEFERRED

    def test_partially_accepted(self, engine):
        rec_id = self._make_rec(engine)
        dec = engine.decide_recommendation("d1", rec_id, RecommendationDisposition.PARTIALLY_ACCEPTED)
        assert dec.disposition == RecommendationDisposition.PARTIALLY_ACCEPTED

    def test_superseded(self, engine):
        rec_id = self._make_rec(engine)
        dec = engine.decide_recommendation("d1", rec_id, RecommendationDisposition.SUPERSEDED)
        assert dec.disposition == RecommendationDisposition.SUPERSEDED

    def test_decided_by(self, engine):
        rec_id = self._make_rec(engine)
        dec = engine.decide_recommendation("d1", rec_id, RecommendationDisposition.ACCEPTED,
                                           decided_by="operator-1")
        assert dec.decided_by == "operator-1"

    def test_reason(self, engine):
        rec_id = self._make_rec(engine)
        dec = engine.decide_recommendation("d1", rec_id, RecommendationDisposition.REJECTED,
                                           reason="too expensive")
        assert dec.reason == "too expensive"

    def test_unknown_rec_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.decide_recommendation("d1", "bad-rec", RecommendationDisposition.ACCEPTED)

    def test_event_emitted(self, engine, es):
        rec_id = self._make_rec(engine)
        before = len(es.list_events())
        engine.decide_recommendation("d1", rec_id, RecommendationDisposition.ACCEPTED)
        assert len(es.list_events()) > before

    def test_decision_id(self, engine):
        rec_id = self._make_rec(engine)
        dec = engine.decide_recommendation("d1", rec_id, RecommendationDisposition.ACCEPTED)
        assert dec.decision_id == "d1"

    def test_decided_at_populated(self, engine):
        rec_id = self._make_rec(engine)
        dec = engine.decide_recommendation("d1", rec_id, RecommendationDisposition.ACCEPTED)
        assert dec.decided_at != ""


# ===================================================================
# 14. Queries
# ===================================================================


class TestQueries:
    def test_get_recommendations_returns_tuple(self, engine):
        _make_request(engine)
        engine.optimize_connectors("req-1", [
            {"connector_ref": "c1", "success_rate": 0.5, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])
        result = engine.get_recommendations("req-1")
        assert isinstance(result, tuple)
        assert len(result) == 1

    def test_get_recommendations_empty_for_unknown_request(self, engine):
        result = engine.get_recommendations("nonexistent")
        assert result == ()

    def test_get_recommendations_matches_request(self, engine):
        _make_request(engine, rid="r1")
        _make_request(engine, rid="r2")
        engine.optimize_connectors("r1", [
            {"connector_ref": "c1", "success_rate": 0.5, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])
        engine.optimize_connectors("r2", [
            {"connector_ref": "c2", "success_rate": 0.6, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])
        r1_recs = engine.get_recommendations("r1")
        r2_recs = engine.get_recommendations("r2")
        assert len(r1_recs) == 1
        assert len(r2_recs) == 1
        assert r1_recs[0].request_id == "r1"
        assert r2_recs[0].request_id == "r2"

    def test_get_plan_returns_plan(self, engine):
        _make_request(engine)
        engine.build_plan("plan-1", "req-1", "Plan")
        plan = engine.get_plan("plan-1")
        assert plan is not None
        assert plan.plan_id == "plan-1"

    def test_get_plan_missing_returns_none(self, engine):
        assert engine.get_plan("nope") is None

    def test_get_all_recommendations(self, engine):
        _make_request(engine, rid="r1")
        _make_request(engine, rid="r2")
        engine.optimize_connectors("r1", [
            {"connector_ref": "c1", "success_rate": 0.5, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])
        engine.optimize_connectors("r2", [
            {"connector_ref": "c2", "success_rate": 0.6, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])
        all_recs = engine.get_all_recommendations()
        assert isinstance(all_recs, tuple)
        assert len(all_recs) == 2

    def test_get_all_recommendations_empty(self, engine):
        assert engine.get_all_recommendations() == ()

    def test_get_decisions_returns_tuple(self, engine):
        _make_request(engine)
        recs = engine.optimize_connectors("req-1", [
            {"connector_ref": "c1", "success_rate": 0.5, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])
        engine.decide_recommendation("d1", recs[0].recommendation_id,
                                     RecommendationDisposition.ACCEPTED)
        decisions = engine.get_decisions()
        assert isinstance(decisions, tuple)
        assert len(decisions) == 1

    def test_get_decisions_empty(self, engine):
        assert engine.get_decisions() == ()

    def test_get_decisions_multiple(self, engine):
        _make_request(engine)
        recs = engine.optimize_connectors("req-1", [
            {"connector_ref": "c1", "success_rate": 0.5, "cost_per_call": 1.0, "latency_seconds": 1.0},
            {"connector_ref": "c2", "success_rate": 0.6, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])
        for i, r in enumerate(recs):
            engine.decide_recommendation(f"d{i}", r.recommendation_id,
                                         RecommendationDisposition.ACCEPTED)
        assert len(engine.get_decisions()) == 2


# ===================================================================
# 15. Properties
# ===================================================================


class TestProperties:
    def test_request_count_initial(self, engine):
        assert engine.request_count == 0

    def test_request_count_after_creates(self, engine):
        for i in range(5):
            _make_request(engine, rid=f"r{i}")
        assert engine.request_count == 5

    def test_recommendation_count_initial(self, engine):
        assert engine.recommendation_count == 0

    def test_recommendation_count_after_optimize(self, engine):
        _make_request(engine)
        engine.optimize_connectors("req-1", [
            {"connector_ref": "c1", "success_rate": 0.5, "cost_per_call": 1.0, "latency_seconds": 1.0},
            {"connector_ref": "c2", "success_rate": 0.6, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])
        assert engine.recommendation_count == 2

    def test_plan_count_initial(self, engine):
        assert engine.plan_count == 0

    def test_plan_count_after_build(self, engine):
        _make_request(engine, rid="r1")
        _make_request(engine, rid="r2")
        engine.build_plan("p1", "r1", "P1")
        engine.build_plan("p2", "r2", "P2")
        assert engine.plan_count == 2


# ===================================================================
# 16. state_hash
# ===================================================================


class TestStateHash:
    def test_state_hash_is_string(self, engine):
        h = engine.state_hash()
        assert isinstance(h, str)

    def test_state_hash_deterministic(self, engine):
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_state_hash_changes_with_request(self, engine):
        h1 = engine.state_hash()
        _make_request(engine)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_state_hash_changes_with_recommendation(self, engine):
        _make_request(engine)
        h1 = engine.state_hash()
        engine.optimize_connectors("req-1", [
            {"connector_ref": "c1", "success_rate": 0.5, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])
        h2 = engine.state_hash()
        assert h1 != h2

    def test_state_hash_changes_with_plan(self, engine):
        _make_request(engine)
        h1 = engine.state_hash()
        engine.build_plan("p1", "req-1", "Plan")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_state_hash_changes_with_decision(self, engine):
        _make_request(engine)
        recs = engine.optimize_connectors("req-1", [
            {"connector_ref": "c1", "success_rate": 0.5, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])
        h1 = engine.state_hash()
        engine.decide_recommendation("d1", recs[0].recommendation_id,
                                     RecommendationDisposition.ACCEPTED)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_state_hash_length(self, engine):
        h = engine.state_hash()
        assert len(h) == 64

    def test_state_hash_hex(self, engine):
        h = engine.state_hash()
        int(h, 16)  # should not raise


# ===================================================================
# 17. Events emitted for all mutations
# ===================================================================


class TestEventEmission:
    def test_create_request_emits(self, engine, es):
        before = len(es.list_events())
        _make_request(engine)
        assert len(es.list_events()) > before

    def test_optimize_connectors_emits(self, engine, es):
        _make_request(engine)
        before = len(es.list_events())
        engine.optimize_connectors("req-1", [])
        assert len(es.list_events()) > before

    def test_optimize_portfolio_emits(self, engine, es):
        _make_request(engine, target=OptimizationTarget.PORTFOLIO_BALANCE)
        before = len(es.list_events())
        engine.optimize_portfolio("req-1", [])
        assert len(es.list_events()) > before

    def test_optimize_budget_emits(self, engine, es):
        _make_request(engine, target=OptimizationTarget.BUDGET_ALLOCATION)
        before = len(es.list_events())
        engine.optimize_budget_allocation("req-1", [])
        assert len(es.list_events()) > before

    def test_optimize_campaigns_emits(self, engine, es):
        _make_request(engine, target=OptimizationTarget.CAMPAIGN_DURATION)
        before = len(es.list_events())
        engine.optimize_campaigns("req-1", [])
        assert len(es.list_events()) > before

    def test_optimize_schedule_emits(self, engine, es):
        _make_request(engine, target=OptimizationTarget.SCHEDULE_EFFICIENCY)
        before = len(es.list_events())
        engine.optimize_schedule("req-1", [])
        assert len(es.list_events()) > before

    def test_optimize_escalation_emits(self, engine, es):
        _make_request(engine, target=OptimizationTarget.ESCALATION_POLICY)
        before = len(es.list_events())
        engine.optimize_escalation("req-1", [])
        assert len(es.list_events()) > before

    def test_optimize_domain_pack_emits(self, engine, es):
        _make_request(engine, target=OptimizationTarget.DOMAIN_PACK_SELECTION)
        before = len(es.list_events())
        engine.optimize_domain_pack_selection("req-1", [])
        assert len(es.list_events()) > before

    def test_build_plan_emits(self, engine, es):
        _make_request(engine)
        before = len(es.list_events())
        engine.build_plan("p1", "req-1", "Plan")
        assert len(es.list_events()) > before

    def test_decide_recommendation_emits(self, engine, es):
        _make_request(engine)
        recs = engine.optimize_connectors("req-1", [
            {"connector_ref": "c1", "success_rate": 0.5, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])
        before = len(es.list_events())
        engine.decide_recommendation("d1", recs[0].recommendation_id,
                                     RecommendationDisposition.ACCEPTED)
        assert len(es.list_events()) > before

    def test_total_event_count_full_pipeline(self, engine, es):
        """All mutating operations should emit at least one event each."""
        _make_request(engine)
        engine.optimize_connectors("req-1", [
            {"connector_ref": "c1", "success_rate": 0.5, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])
        recs = engine.get_recommendations("req-1")
        engine.build_plan("p1", "req-1", "Plan")
        engine.estimate_impact(recs[0].recommendation_id, "m", 1.0, 2.0)
        engine.decide_recommendation("d1", recs[0].recommendation_id,
                                     RecommendationDisposition.ACCEPTED)
        # create_request=1, optimize_connectors=1, build_plan=1, decide=1 = at least 4
        assert len(es.list_events()) >= 4


# ===================================================================
# 18. Golden scenarios
# ===================================================================


class TestGoldenScenario1DegradedConnector:
    """Degraded connector KPI recommends alternate."""

    def test_degraded_connector_recommends_replacement(self, engine):
        req = engine.create_request("gs1", OptimizationTarget.CONNECTOR_SELECTION)
        recs = engine.optimize_connectors("gs1", [
            {"connector_ref": "sms-provider-a", "success_rate": 0.60, "cost_per_call": 0.05, "latency_seconds": 2.0},
            {"connector_ref": "sms-provider-b", "success_rate": 0.95, "cost_per_call": 0.08, "latency_seconds": 0.5},
        ])
        assert len(recs) == 1
        assert recs[0].severity == RecommendationSeverity.URGENT
        assert "sms-provider-a" in recs[0].scope_ref_id

    def test_degraded_connector_plan(self, engine):
        engine.create_request("gs1", OptimizationTarget.CONNECTOR_SELECTION)
        engine.optimize_connectors("gs1", [
            {"connector_ref": "sms-provider-a", "success_rate": 0.60, "cost_per_call": 0.05, "latency_seconds": 2.0},
        ])
        plan = engine.build_plan("gs1-plan", "gs1", "Replace degraded SMS connector")
        assert plan.feasible is True
        assert len(plan.recommendation_ids) == 1
        assert plan.total_estimated_improvement_pct > 0

    def test_degraded_connector_impact(self, engine):
        engine.create_request("gs1", OptimizationTarget.CONNECTOR_SELECTION)
        recs = engine.optimize_connectors("gs1", [
            {"connector_ref": "sms-provider-a", "success_rate": 0.60, "cost_per_call": 0.05, "latency_seconds": 2.0},
        ])
        impact = engine.estimate_impact(recs[0].recommendation_id, "success_rate", 0.60, 0.95)
        assert impact.improvement_pct > 50


class TestGoldenScenario2BlockedPortfolio:
    """Blocked portfolio recommends rebalance."""

    def test_blocked_portfolio_recommends_rebalance(self, engine):
        engine.create_request("gs2", OptimizationTarget.PORTFOLIO_BALANCE)
        recs = engine.optimize_portfolio("gs2", [
            {"campaign_id": "camp-1", "blocked": True, "overdue": False},
            {"campaign_id": "camp-2", "blocked": True, "overdue": False},
            {"campaign_id": "camp-3", "blocked": True, "overdue": False},
            {"campaign_id": "camp-4", "blocked": False, "overdue": False},
        ])
        assert len(recs) == 1
        assert recs[0].action == "rebalance_portfolio"
        assert recs[0].severity == RecommendationSeverity.URGENT

    def test_blocked_portfolio_plan(self, engine):
        engine.create_request("gs2", OptimizationTarget.PORTFOLIO_BALANCE)
        engine.optimize_portfolio("gs2", [
            {"campaign_id": "c1", "blocked": True, "overdue": False},
            {"campaign_id": "c2", "blocked": True, "overdue": False},
            {"campaign_id": "c3", "blocked": True, "overdue": False},
        ])
        plan = engine.build_plan("gs2-plan", "gs2", "Portfolio rebalance")
        assert plan.feasible is True


class TestGoldenScenario3BudgetBurn:
    """Budget burn recommends cheaper path."""

    def test_budget_burn_recommends_reduce(self, engine):
        engine.create_request("gs3", OptimizationTarget.BUDGET_ALLOCATION)
        recs = engine.optimize_budget_allocation("gs3", [
            {"budget_id": "dept-marketing", "burn_rate": 0.96, "cost_per_completion": 800, "utilization": 0.7},
        ])
        # Should get burn rec (critical) and cost rec (advisory)
        assert len(recs) == 2
        burn_recs = [r for r in recs if "burn" in r.title.lower()]
        assert burn_recs[0].severity == RecommendationSeverity.CRITICAL

    def test_budget_burn_plan_and_decide(self, engine):
        engine.create_request("gs3", OptimizationTarget.BUDGET_ALLOCATION)
        engine.optimize_budget_allocation("gs3", [
            {"budget_id": "dept-marketing", "burn_rate": 0.96, "cost_per_completion": 800, "utilization": 0.7},
        ])
        plan = engine.build_plan("gs3-plan", "gs3", "Budget remediation")
        assert plan.feasible is True
        for rid in plan.recommendation_ids:
            engine.decide_recommendation(f"d-{rid[:8]}", rid, RecommendationDisposition.ACCEPTED,
                                         decided_by="cfo", reason="approved")
        assert len(engine.get_decisions()) == 2


class TestGoldenScenario4WaitingOnHuman:
    """Waiting-on-human recommends different window/channel."""

    def test_woh_recommends_adjust_window(self, engine):
        engine.create_request("gs4", OptimizationTarget.CAMPAIGN_DURATION)
        recs = engine.optimize_campaigns("gs4", [
            {"campaign_id": "onboarding-q1", "waiting_on_human_seconds": 14400,
             "escalation_count": 1, "cost": 500},
        ])
        assert len(recs) == 1
        assert "contact_window" in recs[0].action
        assert recs[0].target == OptimizationTarget.SCHEDULE_EFFICIENCY

    def test_woh_impact_estimate(self, engine):
        engine.create_request("gs4", OptimizationTarget.CAMPAIGN_DURATION)
        recs = engine.optimize_campaigns("gs4", [
            {"campaign_id": "onboarding-q1", "waiting_on_human_seconds": 14400,
             "escalation_count": 1, "cost": 500},
        ])
        impact = engine.estimate_impact(recs[0].recommendation_id,
                                        "waiting_on_human_seconds", 14400, 3600)
        assert impact.improvement_pct < 0  # reduction is negative improvement in raw terms
        assert impact.current_value == 14400


class TestGoldenScenario5RepeatedEscalations:
    """Repeated escalations recommend stricter routing."""

    def test_escalations_recommend_stricter_routing(self, engine):
        engine.create_request("gs5", OptimizationTarget.ESCALATION_POLICY)
        recs = engine.optimize_escalation("gs5", [
            {"policy_ref": "default-esc", "total_escalations": 50, "false_positive_count": 25},
        ])
        assert len(recs) == 1
        assert "adjust_escalation_threshold" in recs[0].action
        assert recs[0].score == 0.5

    def test_escalation_with_campaign_data(self, engine):
        engine.create_request("gs5", OptimizationTarget.ESCALATION_POLICY)
        recs_esc = engine.optimize_escalation("gs5", [
            {"policy_ref": "p1", "total_escalations": 20, "false_positive_count": 10},
        ])
        # Also check campaigns with high escalation counts
        engine.create_request("gs5b", OptimizationTarget.CAMPAIGN_DURATION)
        recs_camp = engine.optimize_campaigns("gs5b", [
            {"campaign_id": "c1", "waiting_on_human_seconds": 0, "escalation_count": 8, "cost": 200},
        ])
        assert len(recs_esc) == 1
        assert len(recs_camp) == 1
        assert recs_camp[0].severity == RecommendationSeverity.URGENT


class TestGoldenScenario6FaultResults:
    """Fault results recommend avoiding unstable path."""

    def test_faults_recommend_avoidance(self, engine):
        engine.create_request("gs6", OptimizationTarget.DOMAIN_PACK_SELECTION)
        recs = engine.optimize_domain_pack_selection("gs6", [
            {"domain_pack_id": "legacy-crm-v1", "fault_rate": 0.45, "success_rate": 0.55},
        ])
        assert len(recs) == 1
        assert recs[0].severity == RecommendationSeverity.URGENT
        assert "avoid_domain_pack" in recs[0].action
        assert recs[0].target == OptimizationTarget.FAULT_AVOIDANCE

    def test_faults_plan(self, engine):
        engine.create_request("gs6", OptimizationTarget.DOMAIN_PACK_SELECTION)
        engine.optimize_domain_pack_selection("gs6", [
            {"domain_pack_id": "legacy-crm-v1", "fault_rate": 0.45},
        ])
        plan = engine.build_plan("gs6-plan", "gs6", "Avoid legacy CRM")
        assert plan.feasible is True
        assert plan.total_estimated_improvement_pct > 0


class TestGoldenScenario7ReplayDeterminism:
    """Replay preserves determinism -- same inputs produce same state_hash."""

    def _run_pipeline(self, engine):
        engine.create_request("det-1", OptimizationTarget.CONNECTOR_SELECTION,
                              strategy=OptimizationStrategy.RELIABILITY_MAXIMIZATION)
        engine.optimize_connectors("det-1", [
            {"connector_ref": "a", "success_rate": 0.5, "cost_per_call": 1.0, "latency_seconds": 1.0},
            {"connector_ref": "b", "success_rate": 0.95, "cost_per_call": 2.0, "latency_seconds": 0.5},
        ])
        engine.build_plan("det-plan", "det-1", "Determinism test")

    def test_same_inputs_same_request_count(self):
        es1 = EventSpineEngine()
        eng1 = OptimizationRuntimeEngine(es1)
        self._run_pipeline(eng1)

        es2 = EventSpineEngine()
        eng2 = OptimizationRuntimeEngine(es2)
        self._run_pipeline(eng2)

        assert eng1.request_count == eng2.request_count

    def test_same_inputs_same_recommendation_count(self):
        es1 = EventSpineEngine()
        eng1 = OptimizationRuntimeEngine(es1)
        self._run_pipeline(eng1)

        es2 = EventSpineEngine()
        eng2 = OptimizationRuntimeEngine(es2)
        self._run_pipeline(eng2)

        assert eng1.recommendation_count == eng2.recommendation_count

    def test_same_inputs_same_plan_count(self):
        es1 = EventSpineEngine()
        eng1 = OptimizationRuntimeEngine(es1)
        self._run_pipeline(eng1)

        es2 = EventSpineEngine()
        eng2 = OptimizationRuntimeEngine(es2)
        self._run_pipeline(eng2)

        assert eng1.plan_count == eng2.plan_count

    def test_same_plan_feasibility(self):
        es1 = EventSpineEngine()
        eng1 = OptimizationRuntimeEngine(es1)
        self._run_pipeline(eng1)

        es2 = EventSpineEngine()
        eng2 = OptimizationRuntimeEngine(es2)
        self._run_pipeline(eng2)

        p1 = eng1.get_plan("det-plan")
        p2 = eng2.get_plan("det-plan")
        assert p1.feasible == p2.feasible

    def test_same_recommendation_scores(self):
        es1 = EventSpineEngine()
        eng1 = OptimizationRuntimeEngine(es1)
        self._run_pipeline(eng1)

        es2 = EventSpineEngine()
        eng2 = OptimizationRuntimeEngine(es2)
        self._run_pipeline(eng2)

        recs1 = sorted(eng1.get_all_recommendations(), key=lambda r: r.recommendation_id)
        recs2 = sorted(eng2.get_all_recommendations(), key=lambda r: r.recommendation_id)
        for r1, r2 in zip(recs1, recs2):
            assert r1.score == r2.score


class TestGoldenScenario8FullPipeline:
    """Dashboard + optimization produce action plan (full pipeline)."""

    def test_full_pipeline(self, engine, es):
        # 1. Create optimization request
        req = engine.create_request(
            "pipeline-1", OptimizationTarget.CONNECTOR_SELECTION,
            strategy=OptimizationStrategy.BALANCED,
            reason="Monthly optimization review",
        )
        assert engine.request_count == 1

        # 2. Add constraints
        engine.add_constraint("budget-cap", "pipeline-1", "budget",
                              field_name="cost", operator="<=", value="1000")
        assert len(engine.get_constraints("pipeline-1")) == 1

        # 3. Run connector optimization
        conn_recs = engine.optimize_connectors("pipeline-1", [
            {"connector_ref": "email-sendgrid", "success_rate": 0.65, "cost_per_call": 0.01, "latency_seconds": 0.3},
            {"connector_ref": "email-ses", "success_rate": 0.98, "cost_per_call": 0.005, "latency_seconds": 0.2},
            {"connector_ref": "sms-twilio", "success_rate": 0.88, "cost_per_call": 0.07, "latency_seconds": 1.0},
        ])
        assert len(conn_recs) == 2  # sendgrid and twilio

        # 4. Build plan
        plan = engine.build_plan("pipeline-plan", "pipeline-1", "Monthly connector optimization")
        assert plan.feasible is True
        assert len(plan.recommendation_ids) == 2

        # 5. Estimate impact for each rec
        for rec in conn_recs:
            impact = engine.estimate_impact(
                rec.recommendation_id, "success_rate",
                current_value=0.7, projected_value=0.95,
            )
            assert impact.improvement_pct > 0

        # 6. Decide on recommendations
        engine.decide_recommendation(
            "dec-1", conn_recs[0].recommendation_id,
            RecommendationDisposition.ACCEPTED,
            decided_by="ops-lead",
            reason="Replace degraded connector immediately",
        )
        engine.decide_recommendation(
            "dec-2", conn_recs[1].recommendation_id,
            RecommendationDisposition.DEFERRED,
            decided_by="ops-lead",
            reason="Monitor for another week",
        )

        # 7. Verify final state
        assert engine.recommendation_count == 2
        assert engine.plan_count == 1
        decisions = engine.get_decisions()
        assert len(decisions) == 2
        accepted = [d for d in decisions if d.disposition == RecommendationDisposition.ACCEPTED]
        deferred = [d for d in decisions if d.disposition == RecommendationDisposition.DEFERRED]
        assert len(accepted) == 1
        assert len(deferred) == 1

        # 8. Verify events were emitted for all operations
        all_events = es.list_events()
        assert len(all_events) >= 5  # create, optimize, plan, decide x2

    def test_multi_domain_pipeline(self, engine, es):
        """Pipeline combining multiple optimization domains."""
        # Connector optimization
        engine.create_request("multi-conn", OptimizationTarget.CONNECTOR_SELECTION)
        conn_recs = engine.optimize_connectors("multi-conn", [
            {"connector_ref": "c1", "success_rate": 0.5, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])

        # Portfolio optimization
        engine.create_request("multi-port", OptimizationTarget.PORTFOLIO_BALANCE)
        port_recs = engine.optimize_portfolio("multi-port", [
            {"campaign_id": "camp-1", "blocked": True, "overdue": True},
        ])

        # Budget optimization
        engine.create_request("multi-budget", OptimizationTarget.BUDGET_ALLOCATION)
        budget_recs = engine.optimize_budget_allocation("multi-budget", [
            {"budget_id": "b1", "burn_rate": 0.97, "cost_per_completion": 500, "utilization": 0.7},
        ])

        # Schedule optimization
        engine.create_request("multi-sched", OptimizationTarget.SCHEDULE_EFFICIENCY)
        sched_recs = engine.optimize_schedule("multi-sched", [
            {"identity_ref": "id-1", "quiet_hours_violations": 3},
        ])

        # Build plans for each
        engine.build_plan("p-conn", "multi-conn", "Connector plan")
        engine.build_plan("p-port", "multi-port", "Portfolio plan")
        engine.build_plan("p-budget", "multi-budget", "Budget plan")
        engine.build_plan("p-sched", "multi-sched", "Schedule plan")

        assert engine.request_count == 4
        assert engine.plan_count == 4
        total_recs = engine.get_all_recommendations()
        assert len(total_recs) >= 5  # at least one per domain + extras

    def test_pipeline_state_hash_stability(self, engine):
        """State hash is stable once pipeline completes."""
        engine.create_request("stable", OptimizationTarget.CONNECTOR_SELECTION)
        engine.optimize_connectors("stable", [
            {"connector_ref": "c1", "success_rate": 0.5, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])
        engine.build_plan("stable-plan", "stable", "Stable plan")
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        h3 = engine.state_hash()
        assert h1 == h2 == h3


# ===================================================================
# Additional edge cases
# ===================================================================


class TestEdgeCases:
    def test_optimize_connectors_default_values(self, engine):
        """Missing keys in metrics dict should use defaults."""
        _make_request(engine)
        recs = engine.optimize_connectors("req-1", [{}])
        # success_rate defaults to 1.0 via .get(..., 1.0), so no rec
        assert len(recs) == 0

    def test_optimize_portfolio_default_values(self, engine):
        _make_request(engine, target=OptimizationTarget.PORTFOLIO_BALANCE)
        recs = engine.optimize_portfolio("req-1", [{}])
        assert len(recs) == 0

    def test_optimize_budget_default_values(self, engine):
        _make_request(engine, target=OptimizationTarget.BUDGET_ALLOCATION)
        recs = engine.optimize_budget_allocation("req-1", [{}])
        assert len(recs) == 0

    def test_optimize_campaigns_default_values(self, engine):
        _make_request(engine, target=OptimizationTarget.CAMPAIGN_DURATION)
        recs = engine.optimize_campaigns("req-1", [{}])
        assert len(recs) == 0

    def test_optimize_schedule_default_values(self, engine):
        _make_request(engine, target=OptimizationTarget.SCHEDULE_EFFICIENCY)
        recs = engine.optimize_schedule("req-1", [{}])
        assert len(recs) == 0

    def test_optimize_escalation_default_values(self, engine):
        _make_request(engine, target=OptimizationTarget.ESCALATION_POLICY)
        recs = engine.optimize_escalation("req-1", [{}])
        assert len(recs) == 0

    def test_optimize_domain_pack_default_values(self, engine):
        _make_request(engine, target=OptimizationTarget.DOMAIN_PACK_SELECTION)
        recs = engine.optimize_domain_pack_selection("req-1", [{}])
        assert len(recs) == 0

    def test_connector_score_formula(self, engine):
        """score = max(0, min(1, 1 - success_rate))"""
        _make_request(engine)
        recs = engine.optimize_connectors("req-1", [
            {"connector_ref": "c", "success_rate": 0.3, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])
        assert abs(recs[0].score - 0.7) < 0.01

    def test_connector_estimated_improvement(self, engine):
        _make_request(engine)
        recs = engine.optimize_connectors("req-1", [
            {"connector_ref": "c", "success_rate": 0.5, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])
        # estimated_improvement_pct = (1 - 0.5) * 100 = 50
        assert abs(recs[0].estimated_improvement_pct - 50.0) < 0.01

    def test_connector_cost_delta(self, engine):
        _make_request(engine)
        recs = engine.optimize_connectors("req-1", [
            {"connector_ref": "c", "success_rate": 0.5, "cost_per_call": 2.0, "latency_seconds": 1.0},
        ])
        # estimated_cost_delta = -cost * (1 - sr) = -2.0 * 0.5 = -1.0
        assert abs(recs[0].estimated_cost_delta - (-1.0)) < 0.01

    def test_recommendations_are_immutable(self, engine):
        _make_request(engine)
        recs = engine.optimize_connectors("req-1", [
            {"connector_ref": "c", "success_rate": 0.5, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])
        with pytest.raises(AttributeError):
            recs[0].score = 999

    def test_plan_recommendation_ids_are_tuple(self, engine):
        _make_request(engine)
        engine.optimize_connectors("req-1", [
            {"connector_ref": "c", "success_rate": 0.5, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])
        plan = engine.build_plan("p1", "req-1", "Plan")
        assert isinstance(plan.recommendation_ids, tuple)

    def test_get_recommendations_returns_immutable_tuple(self, engine):
        _make_request(engine)
        engine.optimize_connectors("req-1", [
            {"connector_ref": "c", "success_rate": 0.5, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])
        result = engine.get_recommendations("req-1")
        assert isinstance(result, tuple)

    def test_get_all_recommendations_returns_immutable_tuple(self, engine):
        result = engine.get_all_recommendations()
        assert isinstance(result, tuple)

    def test_get_decisions_returns_immutable_tuple(self, engine):
        result = engine.get_decisions()
        assert isinstance(result, tuple)

    def test_large_number_of_connectors(self, engine):
        _make_request(engine)
        metrics = [
            {"connector_ref": f"c{i}", "success_rate": 0.3 + i * 0.01,
             "cost_per_call": 1.0, "latency_seconds": 1.0}
            for i in range(50)
        ]
        recs = engine.optimize_connectors("req-1", metrics)
        # All with sr < 0.9 should generate recs. sr starts at 0.3, steps 0.01
        # 0.3 + i*0.01 < 0.9 => i < 60, so all 50 should trigger
        assert len(recs) == 50

    def test_request_frozen(self, engine):
        req = _make_request(engine)
        with pytest.raises(AttributeError):
            req.request_id = "changed"

    def test_constraint_frozen(self, engine):
        _make_request(engine)
        c = engine.add_constraint("c1", "req-1", "type")
        with pytest.raises(AttributeError):
            c.constraint_id = "changed"

    def test_plan_frozen(self, engine):
        _make_request(engine)
        plan = engine.build_plan("p1", "req-1", "Plan")
        with pytest.raises(AttributeError):
            plan.plan_id = "changed"

    def test_decision_frozen(self, engine):
        _make_request(engine)
        recs = engine.optimize_connectors("req-1", [
            {"connector_ref": "c", "success_rate": 0.5, "cost_per_call": 1.0, "latency_seconds": 1.0},
        ])
        dec = engine.decide_recommendation("d1", recs[0].recommendation_id,
                                           RecommendationDisposition.ACCEPTED)
        with pytest.raises(AttributeError):
            dec.decision_id = "changed"


class TestBoundedContracts:
    def test_duplicate_request_redacts_request_id(self, engine):
        _make_request(engine, rid="dup-secret")
        with pytest.raises(RuntimeCoreInvariantError) as excinfo:
            _make_request(engine, rid="dup-secret")
        assert "already exists" in str(excinfo.value)
        assert "dup-secret" not in str(excinfo.value)

    def test_missing_constraint_request_redacts_request_id(self, engine):
        with pytest.raises(RuntimeCoreInvariantError) as excinfo:
            engine.add_constraint("c1", "missing-secret", "limit")
        assert "not found" in str(excinfo.value)
        assert "missing-secret" not in str(excinfo.value)

    def test_connector_recommendation_redacts_ref_and_rate(self, engine):
        _make_request(engine)
        rec = engine.optimize_connectors("req-1", [
            {"connector_ref": "connector-secret", "success_rate": 0.41, "cost_per_call": 2.5, "latency_seconds": 1.0},
        ])[0]
        combined = " ".join((rec.title, rec.description, rec.rationale))
        assert "connector-secret" not in combined
        assert "41%" not in combined

    def test_portfolio_recommendation_redacts_counts(self, engine):
        _make_request(engine, target=OptimizationTarget.PORTFOLIO_BALANCE)
        rec = engine.optimize_portfolio("req-1", [
            {"campaign_id": f"blocked-{i}", "blocked": True, "overdue": False}
            for i in range(4)
        ])[0]
        combined = " ".join((rec.title, rec.description, rec.rationale))
        assert "4 blocked" not in combined
        assert "4 campaigns" not in combined

    def test_budget_recommendation_redacts_id_and_values(self, engine):
        _make_request(engine, target=OptimizationTarget.BUDGET_ALLOCATION)
        rec = engine.optimize_budget_allocation("req-1", [
            {"budget_id": "budget-secret", "burn_rate": 0.97, "cost_per_completion": 500, "utilization": 0.8},
        ])[0]
        combined = " ".join((rec.title, rec.description, rec.rationale))
        assert "budget-secret" not in combined
        assert "97%" not in combined
        assert "500.00" not in combined

    def test_campaign_recommendation_redacts_id_and_wait_value(self, engine):
        _make_request(engine, target=OptimizationTarget.CAMPAIGN_DURATION)
        rec = engine.optimize_campaigns("req-1", [
            {"campaign_id": "campaign-secret", "waiting_on_human_seconds": 7200, "escalation_count": 0, "cost": 100},
        ])[0]
        combined = " ".join((rec.title, rec.description, rec.rationale))
        assert "campaign-secret" not in combined
        assert "2.0h" not in combined

    def test_schedule_recommendation_redacts_identity_and_count(self, engine):
        _make_request(engine, target=OptimizationTarget.CHANNEL_ROUTING)
        rec = engine.optimize_schedule("req-1", [
            {"identity_ref": "identity-secret", "available_hours": 8, "utilized_hours": 4, "contact_attempts": 10, "quiet_hours_violations": 4},
        ])[0]
        combined = " ".join((rec.title, rec.description, rec.rationale))
        assert "identity-secret" not in combined
        assert "4 quiet hours" not in combined

    def test_escalation_recommendation_redacts_policy_and_rate(self, engine):
        _make_request(engine, target=OptimizationTarget.ESCALATION_POLICY)
        rec = engine.optimize_escalation("req-1", [
            {"policy_ref": "policy-secret", "total_escalations": 10, "resolved_count": 6, "avg_resolution_seconds": 100, "false_positive_count": 5},
        ])[0]
        combined = " ".join((rec.title, rec.description, rec.rationale))
        assert "policy-secret" not in combined
        assert "50%" not in combined

    def test_domain_pack_recommendation_redacts_pack_and_rate(self, engine):
        _make_request(engine, target=OptimizationTarget.FAULT_AVOIDANCE)
        rec = engine.optimize_domain_pack_selection("req-1", [
            {"domain_pack_id": "pack-secret", "success_rate": 0.6, "cost": 50, "latency_seconds": 1.0, "fault_rate": 0.45},
        ])[0]
        combined = " ".join((rec.title, rec.description, rec.rationale))
        assert "pack-secret" not in combined
        assert "45%" not in combined

    def test_estimate_impact_redacts_recommendation_id(self, engine):
        with pytest.raises(RuntimeCoreInvariantError) as excinfo:
            engine.estimate_impact("bad-rec-secret", "m", 1.0, 2.0)
        assert "not found" in str(excinfo.value)
        assert "bad-rec-secret" not in str(excinfo.value)

    def test_decide_recommendation_redacts_recommendation_id(self, engine):
        with pytest.raises(RuntimeCoreInvariantError) as excinfo:
            engine.decide_recommendation("d1", "bad-rec-secret", RecommendationDisposition.ACCEPTED)
        assert "not found" in str(excinfo.value)
        assert "bad-rec-secret" not in str(excinfo.value)
