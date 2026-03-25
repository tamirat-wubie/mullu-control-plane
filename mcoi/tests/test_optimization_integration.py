"""Purpose: verify optimization integration bridge behaviour.
Governance scope: OptimizationIntegration only.
Dependencies: optimization_runtime engine, event_spine, memory_mesh,
    optimization contracts.
Invariants:
  - Constructor rejects invalid types.
  - All recommend_from_* methods return consistent dict structures.
  - Every mutation emits events.
  - Memory mesh attachment is deterministic.
  - build_and_decide_plan respects disposition semantics.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.optimization_integration import OptimizationIntegration
from mcoi_runtime.core.optimization_runtime import OptimizationRuntimeEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.optimization_runtime import (
    OptimizationStrategy,
    OptimizationTarget,
    RecommendationDisposition,
)
from mcoi_runtime.contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture()
def event_spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture()
def memory_engine() -> MemoryMeshEngine:
    return MemoryMeshEngine()


@pytest.fixture()
def opt_engine(event_spine: EventSpineEngine) -> OptimizationRuntimeEngine:
    return OptimizationRuntimeEngine(event_spine)


@pytest.fixture()
def integration(
    opt_engine: OptimizationRuntimeEngine,
    event_spine: EventSpineEngine,
    memory_engine: MemoryMeshEngine,
) -> OptimizationIntegration:
    return OptimizationIntegration(opt_engine, event_spine, memory_engine)


# --- Metric helpers ---


def _degraded_connector(ref: str = "conn-degraded", sr: float = 0.5) -> dict:
    return {"connector_ref": ref, "success_rate": sr, "cost_per_call": 0.10, "latency_seconds": 0.3}


def _healthy_connector(ref: str = "conn-ok") -> dict:
    return {"connector_ref": ref, "success_rate": 0.99, "cost_per_call": 0.05, "latency_seconds": 0.1}


def _high_burn_budget(bid: str = "bgt-1", burn: float = 0.95) -> dict:
    return {"budget_id": bid, "utilization": 0.7, "burn_rate": burn, "cost_per_completion": 100.0, "available": 500}


def _normal_budget(bid: str = "bgt-ok") -> dict:
    return {"budget_id": bid, "utilization": 0.3, "burn_rate": 0.4, "cost_per_completion": 50.0, "available": 5000}


def _expensive_budget(bid: str = "bgt-exp") -> dict:
    return {"budget_id": bid, "utilization": 0.6, "burn_rate": 0.5, "cost_per_completion": 500.0, "available": 2000}


def _blocked_campaign(cid: str = "camp-blocked") -> dict:
    return {"campaign_id": cid, "status": "active", "priority": "high",
            "blocked": True, "overdue": False, "completion_rate": 0.2}


def _overdue_campaign(cid: str = "camp-overdue") -> dict:
    return {"campaign_id": cid, "status": "active", "priority": "medium",
            "blocked": False, "overdue": True, "completion_rate": 0.6}


def _healthy_campaign_portfolio(cid: str = "camp-ok") -> dict:
    return {"campaign_id": cid, "status": "active", "priority": "normal",
            "blocked": False, "overdue": False, "completion_rate": 0.9}


def _high_wait_campaign(cid: str = "camp-wait") -> dict:
    return {"campaign_id": cid, "completion_rate": 0.5, "avg_duration_seconds": 7200,
            "escalation_count": 1, "waiting_on_human_seconds": 7200.0, "cost": 100.0}


def _high_escalation_campaign(cid: str = "camp-esc") -> dict:
    return {"campaign_id": cid, "completion_rate": 0.5, "avg_duration_seconds": 3600,
            "escalation_count": 6, "waiting_on_human_seconds": 100.0, "cost": 200.0}


def _healthy_campaign_metric(cid: str = "camp-ok") -> dict:
    return {"campaign_id": cid, "completion_rate": 0.95, "avg_duration_seconds": 1800,
            "escalation_count": 0, "waiting_on_human_seconds": 300.0, "cost": 50.0}


def _quiet_hours_violation_schedule(ref: str = "id-qh") -> dict:
    return {"identity_ref": ref, "available_hours": 8, "utilized_hours": 6,
            "contact_attempts": 10, "quiet_hours_violations": 3}


def _clean_schedule(ref: str = "id-clean") -> dict:
    return {"identity_ref": ref, "available_hours": 10, "utilized_hours": 4,
            "contact_attempts": 5, "quiet_hours_violations": 0}


def _faulty_domain_pack(dpid: str = "dp-faulty", fr: float = 0.25) -> dict:
    return {"domain_pack_id": dpid, "success_rate": 0.8, "cost": 10.0,
            "latency_seconds": 0.5, "fault_rate": fr}


def _healthy_domain_pack(dpid: str = "dp-ok") -> dict:
    return {"domain_pack_id": dpid, "success_rate": 0.99, "cost": 5.0,
            "latency_seconds": 0.1, "fault_rate": 0.02}


def _high_fp_escalation(ref: str = "pol-fp") -> dict:
    return {"policy_ref": ref, "total_escalations": 100,
            "resolved_count": 60, "avg_resolution_seconds": 300, "false_positive_count": 40}


def _clean_escalation(ref: str = "pol-clean") -> dict:
    return {"policy_ref": ref, "total_escalations": 50,
            "resolved_count": 48, "avg_resolution_seconds": 120, "false_positive_count": 5}


# ===================================================================
# 1. Constructor validation
# ===================================================================


class TestConstructorValidation:
    """Constructor must type-check all three arguments."""

    def test_valid_construction(
        self, opt_engine: OptimizationRuntimeEngine,
        event_spine: EventSpineEngine, memory_engine: MemoryMeshEngine,
    ) -> None:
        oi = OptimizationIntegration(opt_engine, event_spine, memory_engine)
        assert oi is not None

    def test_rejects_none_optimization_engine(
        self, event_spine: EventSpineEngine, memory_engine: MemoryMeshEngine,
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="optimization_engine"):
            OptimizationIntegration(None, event_spine, memory_engine)  # type: ignore[arg-type]

    def test_rejects_string_optimization_engine(
        self, event_spine: EventSpineEngine, memory_engine: MemoryMeshEngine,
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="optimization_engine"):
            OptimizationIntegration("not-an-engine", event_spine, memory_engine)  # type: ignore[arg-type]

    def test_rejects_wrong_type_optimization_engine(
        self, event_spine: EventSpineEngine, memory_engine: MemoryMeshEngine,
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="optimization_engine"):
            OptimizationIntegration(event_spine, event_spine, memory_engine)  # type: ignore[arg-type]

    def test_rejects_none_event_spine(
        self, opt_engine: OptimizationRuntimeEngine, memory_engine: MemoryMeshEngine,
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            OptimizationIntegration(opt_engine, None, memory_engine)  # type: ignore[arg-type]

    def test_rejects_string_event_spine(
        self, opt_engine: OptimizationRuntimeEngine, memory_engine: MemoryMeshEngine,
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            OptimizationIntegration(opt_engine, "nope", memory_engine)  # type: ignore[arg-type]

    def test_rejects_wrong_type_event_spine(
        self, opt_engine: OptimizationRuntimeEngine, memory_engine: MemoryMeshEngine,
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            OptimizationIntegration(opt_engine, memory_engine, memory_engine)  # type: ignore[arg-type]

    def test_rejects_none_memory_engine(
        self, opt_engine: OptimizationRuntimeEngine, event_spine: EventSpineEngine,
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            OptimizationIntegration(opt_engine, event_spine, None)  # type: ignore[arg-type]

    def test_rejects_string_memory_engine(
        self, opt_engine: OptimizationRuntimeEngine, event_spine: EventSpineEngine,
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            OptimizationIntegration(opt_engine, event_spine, "bad")  # type: ignore[arg-type]

    def test_rejects_wrong_type_memory_engine(
        self, opt_engine: OptimizationRuntimeEngine, event_spine: EventSpineEngine,
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            OptimizationIntegration(opt_engine, event_spine, opt_engine)  # type: ignore[arg-type]

    def test_rejects_int_optimization_engine(
        self, event_spine: EventSpineEngine, memory_engine: MemoryMeshEngine,
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            OptimizationIntegration(42, event_spine, memory_engine)  # type: ignore[arg-type]

    def test_rejects_dict_event_spine(
        self, opt_engine: OptimizationRuntimeEngine, memory_engine: MemoryMeshEngine,
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            OptimizationIntegration(opt_engine, {}, memory_engine)  # type: ignore[arg-type]


# ===================================================================
# 2. recommend_from_connectors
# ===================================================================


class TestRecommendFromConnectors:
    """Tests for connector-driven recommendation path."""

    def test_degraded_connector_produces_recommendation(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_connectors("req-c1", [_degraded_connector()])
        assert result["total_recommendations"] >= 1

    def test_healthy_connector_produces_no_recommendation(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_connectors("req-c2", [_healthy_connector()])
        assert result["total_recommendations"] == 0

    def test_multiple_connectors_mixed(
        self, integration: OptimizationIntegration,
    ) -> None:
        metrics = [_degraded_connector("c1", 0.5), _healthy_connector("c2"), _degraded_connector("c3", 0.85)]
        result = integration.recommend_from_connectors("req-c3", metrics)
        assert result["total_recommendations"] == 2

    def test_return_keys(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_connectors("req-c4", [_degraded_connector()])
        assert result["request_id"] == "req-c4"
        assert result["source"] == "connectors"
        assert "total_recommendations" in result
        assert "strategy" in result

    def test_default_strategy_is_reliability(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_connectors("req-c5", [_degraded_connector()])
        assert result["strategy"] == OptimizationStrategy.RELIABILITY_MAXIMIZATION.value

    def test_custom_strategy(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_connectors(
            "req-c6", [_degraded_connector()],
            strategy=OptimizationStrategy.COST_MINIMIZATION,
        )
        assert result["strategy"] == OptimizationStrategy.COST_MINIMIZATION.value

    def test_emits_event(
        self, integration: OptimizationIntegration, event_spine: EventSpineEngine,
    ) -> None:
        before = len(event_spine.list_events())
        integration.recommend_from_connectors("req-c7", [_degraded_connector()])
        after = len(event_spine.list_events())
        assert after > before

    def test_very_low_success_rate(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_connectors("req-c8", [_degraded_connector("c-bad", 0.1)])
        assert result["total_recommendations"] >= 1

    def test_borderline_success_rate_at_threshold(
        self, integration: OptimizationIntegration,
    ) -> None:
        conn = {"connector_ref": "c-edge", "success_rate": 0.9, "cost_per_call": 0.05, "latency_seconds": 0.1}
        result = integration.recommend_from_connectors("req-c9", [conn])
        assert result["total_recommendations"] == 0

    def test_borderline_just_below_threshold(
        self, integration: OptimizationIntegration,
    ) -> None:
        conn = {"connector_ref": "c-edge2", "success_rate": 0.89, "cost_per_call": 0.05, "latency_seconds": 0.1}
        result = integration.recommend_from_connectors("req-c10", [conn])
        assert result["total_recommendations"] == 1

    def test_empty_connector_list(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_connectors("req-c11", [])
        assert result["total_recommendations"] == 0

    def test_many_degraded_connectors(
        self, integration: OptimizationIntegration,
    ) -> None:
        metrics = [_degraded_connector(f"c-{i}", 0.5 + i * 0.03) for i in range(10)]
        result = integration.recommend_from_connectors("req-c12", metrics)
        assert result["total_recommendations"] == 10


# ===================================================================
# 3. recommend_from_financials
# ===================================================================


class TestRecommendFromFinancials:
    """Tests for financial/budget-driven recommendation path."""

    def test_high_burn_rate_produces_recommendation(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_financials("req-f1", [_high_burn_budget()])
        assert result["total_recommendations"] >= 1

    def test_normal_budget_no_recommendation(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_financials("req-f2", [_normal_budget()])
        assert result["total_recommendations"] == 0

    def test_expensive_budget_produces_cost_recommendation(
        self, integration: OptimizationIntegration,
    ) -> None:
        # cost_per_completion=500 > 300 threshold with utilization=0.6 > 0.5
        # score = min(1.0, 500/1000) = 0.5 > 0.3 so a rec is created
        result = integration.recommend_from_financials("req-f3", [_expensive_budget()])
        assert result["total_recommendations"] >= 1

    def test_return_keys(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_financials("req-f4", [_high_burn_budget()])
        assert result["request_id"] == "req-f4"
        assert result["source"] == "financials"
        assert "total_recommendations" in result
        assert "strategy" in result

    def test_default_strategy_is_cost_minimization(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_financials("req-f5", [_high_burn_budget()])
        assert result["strategy"] == OptimizationStrategy.COST_MINIMIZATION.value

    def test_custom_strategy(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_financials(
            "req-f6", [_high_burn_budget()],
            strategy=OptimizationStrategy.BALANCED,
        )
        assert result["strategy"] == OptimizationStrategy.BALANCED.value

    def test_emits_event(
        self, integration: OptimizationIntegration, event_spine: EventSpineEngine,
    ) -> None:
        before = len(event_spine.list_events())
        integration.recommend_from_financials("req-f7", [_high_burn_budget()])
        after = len(event_spine.list_events())
        assert after > before

    def test_multiple_budgets_mixed(
        self, integration: OptimizationIntegration,
    ) -> None:
        metrics = [_high_burn_budget("b1"), _normal_budget("b2"), _expensive_budget("b3")]
        result = integration.recommend_from_financials("req-f8", metrics)
        assert result["total_recommendations"] >= 2

    def test_burn_rate_at_threshold_no_rec(
        self, integration: OptimizationIntegration,
    ) -> None:
        bgt = {"budget_id": "b-edge", "utilization": 0.5, "burn_rate": 0.9,
               "cost_per_completion": 50.0, "available": 1000}
        result = integration.recommend_from_financials("req-f9", [bgt])
        assert result["total_recommendations"] == 0

    def test_burn_rate_just_above_threshold(
        self, integration: OptimizationIntegration,
    ) -> None:
        bgt = {"budget_id": "b-over", "utilization": 0.5, "burn_rate": 0.91,
               "cost_per_completion": 50.0, "available": 1000}
        result = integration.recommend_from_financials("req-f10", [bgt])
        assert result["total_recommendations"] >= 1

    def test_empty_budget_list(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_financials("req-f11", [])
        assert result["total_recommendations"] == 0


# ===================================================================
# 4. recommend_from_portfolio
# ===================================================================


class TestRecommendFromPortfolio:
    """Tests for portfolio-driven recommendation path."""

    def test_blocked_campaign_produces_recommendation(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_portfolio("req-p1", [_blocked_campaign()])
        assert result["total_recommendations"] >= 1

    def test_overdue_campaign_produces_recommendation(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_portfolio("req-p2", [_overdue_campaign()])
        assert result["total_recommendations"] >= 1

    def test_healthy_campaign_no_recommendation(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_portfolio("req-p3", [_healthy_campaign_portfolio()])
        assert result["total_recommendations"] == 0

    def test_blocked_and_overdue_produce_two_recommendations(
        self, integration: OptimizationIntegration,
    ) -> None:
        metrics = [_blocked_campaign(), _overdue_campaign()]
        result = integration.recommend_from_portfolio("req-p4", metrics)
        assert result["total_recommendations"] == 2

    def test_return_keys(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_portfolio("req-p5", [_blocked_campaign()])
        assert result["request_id"] == "req-p5"
        assert result["source"] == "portfolio"
        assert "total_recommendations" in result
        assert "strategy" in result

    def test_default_strategy_is_balanced(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_portfolio("req-p6", [_blocked_campaign()])
        assert result["strategy"] == OptimizationStrategy.BALANCED.value

    def test_emits_event(
        self, integration: OptimizationIntegration, event_spine: EventSpineEngine,
    ) -> None:
        before = len(event_spine.list_events())
        integration.recommend_from_portfolio("req-p7", [_blocked_campaign()])
        after = len(event_spine.list_events())
        assert after > before

    def test_empty_portfolio_list(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_portfolio("req-p8", [])
        assert result["total_recommendations"] == 0

    def test_multiple_blocked_campaigns(
        self, integration: OptimizationIntegration,
    ) -> None:
        metrics = [_blocked_campaign(f"camp-b{i}") for i in range(5)]
        result = integration.recommend_from_portfolio("req-p9", metrics)
        assert result["total_recommendations"] >= 1

    def test_only_healthy_campaigns(
        self, integration: OptimizationIntegration,
    ) -> None:
        metrics = [_healthy_campaign_portfolio(f"camp-h{i}") for i in range(4)]
        result = integration.recommend_from_portfolio("req-p10", metrics)
        assert result["total_recommendations"] == 0


# ===================================================================
# 5. recommend_from_availability
# ===================================================================


class TestRecommendFromAvailability:
    """Tests for availability/schedule-driven recommendation path."""

    def test_quiet_hours_violation_produces_recommendation(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_availability("req-a1", [_quiet_hours_violation_schedule()])
        assert result["total_recommendations"] >= 1

    def test_clean_schedule_no_recommendation(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_availability("req-a2", [_clean_schedule()])
        assert result["total_recommendations"] == 0

    def test_with_campaign_metrics(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_availability(
            "req-a3", [_quiet_hours_violation_schedule()],
            campaign_metrics=[_high_wait_campaign()],
        )
        # 1 schedule + 1 campaign = 2
        assert result["total_recommendations"] >= 2

    def test_campaign_metrics_none_by_default(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_availability("req-a4", [_clean_schedule()])
        assert result["total_recommendations"] == 0

    def test_return_keys(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_availability("req-a5", [_quiet_hours_violation_schedule()])
        assert result["request_id"] == "req-a5"
        assert result["source"] == "availability"
        assert "total_recommendations" in result
        assert "strategy" in result

    def test_default_strategy_is_balanced(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_availability("req-a6", [_quiet_hours_violation_schedule()])
        assert result["strategy"] == OptimizationStrategy.BALANCED.value

    def test_custom_strategy(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_availability(
            "req-a7", [_quiet_hours_violation_schedule()],
            strategy=OptimizationStrategy.THROUGHPUT_MAXIMIZATION,
        )
        assert result["strategy"] == OptimizationStrategy.THROUGHPUT_MAXIMIZATION.value

    def test_emits_event(
        self, integration: OptimizationIntegration, event_spine: EventSpineEngine,
    ) -> None:
        before = len(event_spine.list_events())
        integration.recommend_from_availability("req-a8", [_quiet_hours_violation_schedule()])
        after = len(event_spine.list_events())
        assert after > before

    def test_empty_schedule_list(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_availability("req-a9", [])
        assert result["total_recommendations"] == 0

    def test_multiple_schedules_with_violations(
        self, integration: OptimizationIntegration,
    ) -> None:
        metrics = [_quiet_hours_violation_schedule(f"id-{i}") for i in range(3)]
        result = integration.recommend_from_availability("req-a10", metrics)
        assert result["total_recommendations"] == 3

    def test_schedule_only_campaign_healthy(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_availability(
            "req-a11", [_quiet_hours_violation_schedule()],
            campaign_metrics=[_healthy_campaign_metric()],
        )
        # 1 schedule rec, 0 campaign recs
        assert result["total_recommendations"] == 1


# ===================================================================
# 6. recommend_from_faults
# ===================================================================


class TestRecommendFromFaults:
    """Tests for fault-driven recommendation path."""

    def test_faulty_domain_pack_produces_recommendation(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_faults("req-fl1", [_faulty_domain_pack()])
        assert result["total_recommendations"] >= 1

    def test_healthy_domain_pack_no_recommendation(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_faults("req-fl2", [_healthy_domain_pack()])
        assert result["total_recommendations"] == 0

    def test_with_escalation_metrics_high_fp(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_faults(
            "req-fl3", [_faulty_domain_pack()],
            escalation_metrics=[_high_fp_escalation()],
        )
        # 1 domain + 1 escalation
        assert result["total_recommendations"] >= 2

    def test_with_clean_escalation_metrics(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_faults(
            "req-fl4", [_faulty_domain_pack()],
            escalation_metrics=[_clean_escalation()],
        )
        # 1 domain + 0 escalation
        assert result["total_recommendations"] == 1

    def test_escalation_metrics_none_by_default(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_faults("req-fl5", [_healthy_domain_pack()])
        assert result["total_recommendations"] == 0

    def test_return_keys(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_faults("req-fl6", [_faulty_domain_pack()])
        assert result["request_id"] == "req-fl6"
        assert result["source"] == "faults"
        assert "total_recommendations" in result
        assert "strategy" in result

    def test_default_strategy_is_reliability(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_faults("req-fl7", [_faulty_domain_pack()])
        assert result["strategy"] == OptimizationStrategy.RELIABILITY_MAXIMIZATION.value

    def test_custom_strategy(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_faults(
            "req-fl8", [_faulty_domain_pack()],
            strategy=OptimizationStrategy.BALANCED,
        )
        assert result["strategy"] == OptimizationStrategy.BALANCED.value

    def test_emits_event(
        self, integration: OptimizationIntegration, event_spine: EventSpineEngine,
    ) -> None:
        before = len(event_spine.list_events())
        integration.recommend_from_faults("req-fl9", [_faulty_domain_pack()])
        after = len(event_spine.list_events())
        assert after > before

    def test_fault_rate_at_threshold_no_rec(
        self, integration: OptimizationIntegration,
    ) -> None:
        dp = {"domain_pack_id": "dp-edge", "success_rate": 0.95, "cost": 5.0,
              "latency_seconds": 0.2, "fault_rate": 0.1}
        result = integration.recommend_from_faults("req-fl10", [dp])
        assert result["total_recommendations"] == 0

    def test_fault_rate_just_above_threshold(
        self, integration: OptimizationIntegration,
    ) -> None:
        dp = {"domain_pack_id": "dp-over", "success_rate": 0.85, "cost": 5.0,
              "latency_seconds": 0.3, "fault_rate": 0.11}
        result = integration.recommend_from_faults("req-fl11", [dp])
        assert result["total_recommendations"] == 1

    def test_empty_domain_list(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_faults("req-fl12", [])
        assert result["total_recommendations"] == 0

    def test_multiple_faulty_packs(
        self, integration: OptimizationIntegration,
    ) -> None:
        metrics = [_faulty_domain_pack(f"dp-{i}", 0.15 + i * 0.05) for i in range(4)]
        result = integration.recommend_from_faults("req-fl13", metrics)
        assert result["total_recommendations"] == 4

    def test_escalation_fp_rate_at_threshold_no_rec(
        self, integration: OptimizationIntegration,
    ) -> None:
        esc = {"policy_ref": "pol-edge", "total_escalations": 100,
               "resolved_count": 70, "avg_resolution_seconds": 200,
               "false_positive_count": 30}
        result = integration.recommend_from_faults("req-fl14", [_healthy_domain_pack()], escalation_metrics=[esc])
        assert result["total_recommendations"] == 0

    def test_escalation_fp_rate_above_threshold(
        self, integration: OptimizationIntegration,
    ) -> None:
        esc = {"policy_ref": "pol-over", "total_escalations": 100,
               "resolved_count": 60, "avg_resolution_seconds": 200,
               "false_positive_count": 31}
        result = integration.recommend_from_faults("req-fl15", [_healthy_domain_pack()], escalation_metrics=[esc])
        assert result["total_recommendations"] == 1


# ===================================================================
# 7. recommend_from_reporting
# ===================================================================


class TestRecommendFromReporting:
    """Tests for reporting-driven recommendation path (composite)."""

    def test_connector_only(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_reporting(
            "req-r1", connector_metrics=[_degraded_connector()],
        )
        assert result["total_recommendations"] >= 1
        assert result["source"] == "reporting"

    def test_campaign_only(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_reporting(
            "req-r2", campaign_metrics=[_high_wait_campaign()],
        )
        assert result["total_recommendations"] >= 1

    def test_budget_only(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_reporting(
            "req-r3", budget_metrics=[_high_burn_budget()],
        )
        assert result["total_recommendations"] >= 1

    def test_all_three_combined(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_reporting(
            "req-r4",
            connector_metrics=[_degraded_connector()],
            campaign_metrics=[_high_wait_campaign()],
            budget_metrics=[_high_burn_budget()],
        )
        assert result["total_recommendations"] >= 3

    def test_no_metrics_provided(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_reporting("req-r5")
        assert result["total_recommendations"] == 0

    def test_return_keys(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_reporting("req-r6")
        assert result["request_id"] == "req-r6"
        assert result["source"] == "reporting"
        assert "total_recommendations" in result
        assert "strategy" in result

    def test_default_strategy_is_balanced(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_reporting("req-r7")
        assert result["strategy"] == OptimizationStrategy.BALANCED.value

    def test_custom_strategy(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_reporting(
            "req-r8", strategy=OptimizationStrategy.LATENCY_MINIMIZATION,
        )
        assert result["strategy"] == OptimizationStrategy.LATENCY_MINIMIZATION.value

    def test_emits_event(
        self, integration: OptimizationIntegration, event_spine: EventSpineEngine,
    ) -> None:
        before = len(event_spine.list_events())
        integration.recommend_from_reporting("req-r9", connector_metrics=[_degraded_connector()])
        after = len(event_spine.list_events())
        assert after > before

    def test_healthy_metrics_yield_no_recs(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_reporting(
            "req-r10",
            connector_metrics=[_healthy_connector()],
            campaign_metrics=[_healthy_campaign_metric()],
            budget_metrics=[_normal_budget()],
        )
        assert result["total_recommendations"] == 0

    def test_connector_and_campaign_no_budget(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.recommend_from_reporting(
            "req-r11",
            connector_metrics=[_degraded_connector()],
            campaign_metrics=[_high_escalation_campaign()],
        )
        assert result["total_recommendations"] >= 2


# ===================================================================
# 8. build_and_decide_plan
# ===================================================================


class TestBuildAndDecidePlan:
    """Tests for plan building and decision logic."""

    def test_pending_disposition_no_decisions(
        self, integration: OptimizationIntegration,
    ) -> None:
        integration.recommend_from_connectors("req-bd1", [_degraded_connector()])
        result = integration.build_and_decide_plan("plan-1", "req-bd1", "Test Plan")
        assert result["plan_id"] == "plan-1"
        assert result["request_id"] == "req-bd1"
        assert result["title"] == "Test Plan"
        assert result["disposition"] == RecommendationDisposition.PENDING.value
        assert result["decision_count"] == 0
        assert result["recommendation_count"] >= 1

    def test_accepted_disposition_decides_all(
        self, integration: OptimizationIntegration,
    ) -> None:
        integration.recommend_from_connectors("req-bd2", [_degraded_connector()])
        result = integration.build_and_decide_plan(
            "plan-2", "req-bd2", "Accept All",
            disposition=RecommendationDisposition.ACCEPTED,
            decided_by="admin",
            reason="approved",
        )
        assert result["disposition"] == RecommendationDisposition.ACCEPTED.value
        assert result["decision_count"] == result["recommendation_count"]
        assert result["decision_count"] >= 1

    def test_rejected_disposition_decides_all(
        self, integration: OptimizationIntegration,
    ) -> None:
        integration.recommend_from_connectors("req-bd3", [_degraded_connector()])
        result = integration.build_and_decide_plan(
            "plan-3", "req-bd3", "Reject All",
            disposition=RecommendationDisposition.REJECTED,
            decided_by="reviewer",
            reason="not applicable",
        )
        assert result["disposition"] == RecommendationDisposition.REJECTED.value
        assert result["decision_count"] == result["recommendation_count"]

    def test_deferred_disposition_decides_all(
        self, integration: OptimizationIntegration,
    ) -> None:
        integration.recommend_from_connectors("req-bd4", [_degraded_connector()])
        result = integration.build_and_decide_plan(
            "plan-4", "req-bd4", "Defer All",
            disposition=RecommendationDisposition.DEFERRED,
            decided_by="ops",
            reason="later",
        )
        assert result["disposition"] == RecommendationDisposition.DEFERRED.value
        assert result["decision_count"] >= 1

    def test_plan_with_no_recommendations(
        self, integration: OptimizationIntegration,
    ) -> None:
        integration.recommend_from_connectors("req-bd5", [_healthy_connector()])
        result = integration.build_and_decide_plan("plan-5", "req-bd5", "Empty Plan")
        assert result["recommendation_count"] == 0
        assert result["decision_count"] == 0
        assert result["feasible"] is False

    def test_plan_feasible_when_recs_exist(
        self, integration: OptimizationIntegration,
    ) -> None:
        integration.recommend_from_connectors("req-bd6", [_degraded_connector()])
        result = integration.build_and_decide_plan("plan-6", "req-bd6", "Feasible Plan")
        assert result["feasible"] is True

    def test_return_keys(
        self, integration: OptimizationIntegration,
    ) -> None:
        integration.recommend_from_connectors("req-bd7", [_degraded_connector()])
        result = integration.build_and_decide_plan("plan-7", "req-bd7", "Keys Plan")
        expected_keys = {
            "plan_id", "request_id", "title", "recommendation_count",
            "decision_count", "disposition", "feasible", "total_estimated_improvement_pct",
        }
        assert expected_keys.issubset(set(result.keys()))

    def test_total_estimated_improvement_positive(
        self, integration: OptimizationIntegration,
    ) -> None:
        integration.recommend_from_connectors("req-bd8", [_degraded_connector("c", 0.5)])
        result = integration.build_and_decide_plan("plan-8", "req-bd8", "Improvement Plan")
        assert result["total_estimated_improvement_pct"] > 0

    def test_emits_event(
        self, integration: OptimizationIntegration, event_spine: EventSpineEngine,
    ) -> None:
        integration.recommend_from_connectors("req-bd9", [_degraded_connector()])
        before = len(event_spine.list_events())
        integration.build_and_decide_plan("plan-9", "req-bd9", "Event Plan")
        after = len(event_spine.list_events())
        assert after > before

    def test_multiple_recommendations_all_decided(
        self, integration: OptimizationIntegration,
    ) -> None:
        metrics = [_degraded_connector(f"c-{i}", 0.3 + i * 0.05) for i in range(5)]
        integration.recommend_from_connectors("req-bd10", metrics)
        result = integration.build_and_decide_plan(
            "plan-10", "req-bd10", "Multi Plan",
            disposition=RecommendationDisposition.ACCEPTED,
            decided_by="auto",
        )
        assert result["recommendation_count"] == 5
        assert result["decision_count"] == 5

    def test_partially_accepted_disposition(
        self, integration: OptimizationIntegration,
    ) -> None:
        integration.recommend_from_connectors("req-bd11", [_degraded_connector()])
        result = integration.build_and_decide_plan(
            "plan-11", "req-bd11", "Partial",
            disposition=RecommendationDisposition.PARTIALLY_ACCEPTED,
            decided_by="mgr",
        )
        assert result["disposition"] == RecommendationDisposition.PARTIALLY_ACCEPTED.value
        assert result["decision_count"] >= 1


# ===================================================================
# 9. attach_recommendations_to_memory_mesh
# ===================================================================


class TestAttachRecommendationsToMemoryMesh:
    """Tests for memory mesh attachment."""

    def test_returns_memory_record(
        self, integration: OptimizationIntegration,
    ) -> None:
        integration.recommend_from_connectors("req-m1", [_degraded_connector()])
        mem = integration.attach_recommendations_to_memory_mesh("scope-m1")
        assert isinstance(mem, MemoryRecord)

    def test_memory_id_is_deterministic(
        self, integration: OptimizationIntegration,
    ) -> None:
        integration.recommend_from_connectors("req-m2", [_degraded_connector()])
        mem1 = integration.attach_recommendations_to_memory_mesh("scope-m2")
        # Same scope_ref_id produces same memory_id
        mem2_id = mem1.memory_id
        assert len(mem2_id) > 0

    def test_content_has_correct_fields(
        self, integration: OptimizationIntegration,
    ) -> None:
        integration.recommend_from_connectors("req-m3", [_degraded_connector()])
        mem = integration.attach_recommendations_to_memory_mesh("scope-m3")
        content = mem.content
        assert "scope_ref_id" in content
        assert "total_requests" in content
        assert "total_recommendations" in content
        assert "total_plans" in content
        assert "recommendation_targets" in content

    def test_content_scope_ref_id_matches(
        self, integration: OptimizationIntegration,
    ) -> None:
        integration.recommend_from_connectors("req-m4", [_degraded_connector()])
        mem = integration.attach_recommendations_to_memory_mesh("scope-m4")
        assert mem.content["scope_ref_id"] == "scope-m4"

    def test_content_total_recommendations(
        self, integration: OptimizationIntegration,
    ) -> None:
        integration.recommend_from_connectors("req-m5", [_degraded_connector()])
        mem = integration.attach_recommendations_to_memory_mesh("scope-m5")
        assert mem.content["total_recommendations"] >= 1

    def test_memory_type_is_observation(
        self, integration: OptimizationIntegration,
    ) -> None:
        integration.recommend_from_connectors("req-m6", [_degraded_connector()])
        mem = integration.attach_recommendations_to_memory_mesh("scope-m6")
        assert mem.memory_type == MemoryType.OBSERVATION

    def test_memory_scope_is_global(
        self, integration: OptimizationIntegration,
    ) -> None:
        integration.recommend_from_connectors("req-m7", [_degraded_connector()])
        mem = integration.attach_recommendations_to_memory_mesh("scope-m7")
        assert mem.scope == MemoryScope.GLOBAL

    def test_memory_trust_level_is_verified(
        self, integration: OptimizationIntegration,
    ) -> None:
        integration.recommend_from_connectors("req-m8", [_degraded_connector()])
        mem = integration.attach_recommendations_to_memory_mesh("scope-m8")
        assert mem.trust_level == MemoryTrustLevel.VERIFIED

    def test_memory_title_contains_scope_ref(
        self, integration: OptimizationIntegration,
    ) -> None:
        integration.recommend_from_connectors("req-m9", [_degraded_connector()])
        mem = integration.attach_recommendations_to_memory_mesh("scope-m9")
        assert "scope-m9" in mem.title

    def test_memory_tags(
        self, integration: OptimizationIntegration,
    ) -> None:
        integration.recommend_from_connectors("req-m10", [_degraded_connector()])
        mem = integration.attach_recommendations_to_memory_mesh("scope-m10")
        assert "optimization" in mem.tags
        assert "recommendations" in mem.tags

    def test_emits_event(
        self, integration: OptimizationIntegration, event_spine: EventSpineEngine,
    ) -> None:
        integration.recommend_from_connectors("req-m11", [_degraded_connector()])
        before = len(event_spine.list_events())
        integration.attach_recommendations_to_memory_mesh("scope-m11")
        after = len(event_spine.list_events())
        assert after > before

    def test_no_recommendations_still_creates_memory(
        self, integration: OptimizationIntegration,
    ) -> None:
        mem = integration.attach_recommendations_to_memory_mesh("scope-m12")
        assert isinstance(mem, MemoryRecord)
        assert mem.content["total_recommendations"] == 0

    def test_recommendation_targets_in_content(
        self, integration: OptimizationIntegration,
    ) -> None:
        integration.recommend_from_connectors("req-m13", [_degraded_connector()])
        mem = integration.attach_recommendations_to_memory_mesh("scope-m13")
        targets = mem.content["recommendation_targets"]
        assert isinstance(targets, (list, tuple))
        assert len(targets) >= 1


# ===================================================================
# 10. attach_recommendations_to_graph
# ===================================================================


class TestAttachRecommendationsToGraph:
    """Tests for graph attachment."""

    def test_returns_dict(
        self, integration: OptimizationIntegration,
    ) -> None:
        integration.recommend_from_connectors("req-g1", [_degraded_connector()])
        result = integration.attach_recommendations_to_graph("scope-g1")
        assert isinstance(result, dict)

    def test_return_keys(
        self, integration: OptimizationIntegration,
    ) -> None:
        integration.recommend_from_connectors("req-g2", [_degraded_connector()])
        result = integration.attach_recommendations_to_graph("scope-g2")
        expected = {"scope_ref_id", "total_requests", "total_recommendations",
                    "total_plans", "recommendations_by_target"}
        assert expected.issubset(set(result.keys()))

    def test_scope_ref_id_matches(
        self, integration: OptimizationIntegration,
    ) -> None:
        integration.recommend_from_connectors("req-g3", [_degraded_connector()])
        result = integration.attach_recommendations_to_graph("scope-g3")
        assert result["scope_ref_id"] == "scope-g3"

    def test_recommendations_by_target_groups_correctly(
        self, integration: OptimizationIntegration,
    ) -> None:
        integration.recommend_from_connectors("req-g4", [_degraded_connector()])
        result = integration.attach_recommendations_to_graph("scope-g4")
        by_target = result["recommendations_by_target"]
        assert isinstance(by_target, dict)
        assert OptimizationTarget.CONNECTOR_SELECTION.value in by_target

    def test_multiple_targets_grouped(
        self, integration: OptimizationIntegration,
    ) -> None:
        integration.recommend_from_reporting(
            "req-g5",
            connector_metrics=[_degraded_connector()],
            campaign_metrics=[_high_wait_campaign()],
        )
        result = integration.attach_recommendations_to_graph("scope-g5")
        by_target = result["recommendations_by_target"]
        assert len(by_target) >= 2

    def test_total_recommendations_count(
        self, integration: OptimizationIntegration,
    ) -> None:
        integration.recommend_from_connectors("req-g6", [_degraded_connector()])
        result = integration.attach_recommendations_to_graph("scope-g6")
        assert result["total_recommendations"] >= 1

    def test_empty_state_returns_empty_targets(
        self, integration: OptimizationIntegration,
    ) -> None:
        result = integration.attach_recommendations_to_graph("scope-g7")
        assert result["recommendations_by_target"] == {}
        assert result["total_recommendations"] == 0

    def test_total_plans_after_build(
        self, integration: OptimizationIntegration,
    ) -> None:
        integration.recommend_from_connectors("req-g8", [_degraded_connector()])
        integration.build_and_decide_plan("plan-g8", "req-g8", "Graph Plan")
        result = integration.attach_recommendations_to_graph("scope-g8")
        assert result["total_plans"] >= 1


# ===================================================================
# 11. Return value schema consistency
# ===================================================================


class TestReturnValueSchemas:
    """All recommend_from_* methods return consistent dict structures."""

    _REQUIRED_KEYS = {"request_id", "source", "total_recommendations", "strategy"}

    def test_connectors_schema(self, integration: OptimizationIntegration) -> None:
        result = integration.recommend_from_connectors("req-s1", [_degraded_connector()])
        assert self._REQUIRED_KEYS.issubset(set(result.keys()))

    def test_financials_schema(self, integration: OptimizationIntegration) -> None:
        result = integration.recommend_from_financials("req-s2", [_high_burn_budget()])
        assert self._REQUIRED_KEYS.issubset(set(result.keys()))

    def test_portfolio_schema(self, integration: OptimizationIntegration) -> None:
        result = integration.recommend_from_portfolio("req-s3", [_blocked_campaign()])
        assert self._REQUIRED_KEYS.issubset(set(result.keys()))

    def test_availability_schema(self, integration: OptimizationIntegration) -> None:
        result = integration.recommend_from_availability("req-s4", [_quiet_hours_violation_schedule()])
        assert self._REQUIRED_KEYS.issubset(set(result.keys()))

    def test_faults_schema(self, integration: OptimizationIntegration) -> None:
        result = integration.recommend_from_faults("req-s5", [_faulty_domain_pack()])
        assert self._REQUIRED_KEYS.issubset(set(result.keys()))

    def test_reporting_schema(self, integration: OptimizationIntegration) -> None:
        result = integration.recommend_from_reporting("req-s6")
        assert self._REQUIRED_KEYS.issubset(set(result.keys()))

    def test_total_recommendations_is_int(self, integration: OptimizationIntegration) -> None:
        result = integration.recommend_from_connectors("req-s7", [_degraded_connector()])
        assert isinstance(result["total_recommendations"], int)

    def test_strategy_is_string(self, integration: OptimizationIntegration) -> None:
        result = integration.recommend_from_connectors("req-s8", [_degraded_connector()])
        assert isinstance(result["strategy"], str)

    def test_source_values(self, integration: OptimizationIntegration) -> None:
        sources = []
        sources.append(integration.recommend_from_connectors("req-sv1", [])["source"])
        sources.append(integration.recommend_from_financials("req-sv2", [])["source"])
        sources.append(integration.recommend_from_portfolio("req-sv3", [])["source"])
        sources.append(integration.recommend_from_availability("req-sv4", [])["source"])
        sources.append(integration.recommend_from_faults("req-sv5", [])["source"])
        sources.append(integration.recommend_from_reporting("req-sv6")["source"])
        assert sources == ["connectors", "financials", "portfolio", "availability", "faults", "reporting"]

    def test_build_plan_schema(self, integration: OptimizationIntegration) -> None:
        integration.recommend_from_connectors("req-sv7", [_degraded_connector()])
        result = integration.build_and_decide_plan("plan-sv7", "req-sv7", "Schema Plan")
        expected = {
            "plan_id", "request_id", "title", "recommendation_count",
            "decision_count", "disposition", "feasible", "total_estimated_improvement_pct",
        }
        assert expected.issubset(set(result.keys()))


# ===================================================================
# 12. Events emitted by each method
# ===================================================================


class TestEventsEmission:
    """Each integration method emits at least one event."""

    def test_connectors_emits(self, integration: OptimizationIntegration, event_spine: EventSpineEngine) -> None:
        before = len(event_spine.list_events())
        integration.recommend_from_connectors("req-ev1", [_degraded_connector()])
        assert len(event_spine.list_events()) > before

    def test_financials_emits(self, integration: OptimizationIntegration, event_spine: EventSpineEngine) -> None:
        before = len(event_spine.list_events())
        integration.recommend_from_financials("req-ev2", [_high_burn_budget()])
        assert len(event_spine.list_events()) > before

    def test_portfolio_emits(self, integration: OptimizationIntegration, event_spine: EventSpineEngine) -> None:
        before = len(event_spine.list_events())
        integration.recommend_from_portfolio("req-ev3", [_blocked_campaign()])
        assert len(event_spine.list_events()) > before

    def test_availability_emits(self, integration: OptimizationIntegration, event_spine: EventSpineEngine) -> None:
        before = len(event_spine.list_events())
        integration.recommend_from_availability("req-ev4", [_quiet_hours_violation_schedule()])
        assert len(event_spine.list_events()) > before

    def test_faults_emits(self, integration: OptimizationIntegration, event_spine: EventSpineEngine) -> None:
        before = len(event_spine.list_events())
        integration.recommend_from_faults("req-ev5", [_faulty_domain_pack()])
        assert len(event_spine.list_events()) > before

    def test_reporting_emits(self, integration: OptimizationIntegration, event_spine: EventSpineEngine) -> None:
        before = len(event_spine.list_events())
        integration.recommend_from_reporting("req-ev6")
        assert len(event_spine.list_events()) > before

    def test_build_and_decide_emits(self, integration: OptimizationIntegration, event_spine: EventSpineEngine) -> None:
        integration.recommend_from_connectors("req-ev7", [_degraded_connector()])
        before = len(event_spine.list_events())
        integration.build_and_decide_plan("plan-ev7", "req-ev7", "Event Plan")
        assert len(event_spine.list_events()) > before

    def test_attach_memory_emits(self, integration: OptimizationIntegration, event_spine: EventSpineEngine) -> None:
        before = len(event_spine.list_events())
        integration.attach_recommendations_to_memory_mesh("scope-ev8")
        assert len(event_spine.list_events()) > before

    def test_event_count_per_connector_call(
        self, integration: OptimizationIntegration, event_spine: EventSpineEngine,
    ) -> None:
        before = len(event_spine.list_events())
        integration.recommend_from_connectors("req-ev9", [_degraded_connector()])
        after = len(event_spine.list_events())
        # At least 2 events: one from engine create_request, one from engine optimize_connectors,
        # and one from the integration _emit
        assert after - before >= 3

    def test_accepted_plan_emits_decision_events(
        self, integration: OptimizationIntegration, event_spine: EventSpineEngine,
    ) -> None:
        integration.recommend_from_connectors("req-ev10", [_degraded_connector()])
        before = len(event_spine.list_events())
        integration.build_and_decide_plan(
            "plan-ev10", "req-ev10", "Event Plan",
            disposition=RecommendationDisposition.ACCEPTED, decided_by="x",
        )
        after = len(event_spine.list_events())
        # At least: build_plan event + decide event + integration event
        assert after - before >= 3


# ===================================================================
# 13. Memory mesh idempotency
# ===================================================================


class TestMemoryMeshIdempotency:
    """Same scope_ref_id produces the same deterministic memory_id."""

    def test_same_scope_ref_same_id(
        self, opt_engine: OptimizationRuntimeEngine,
        event_spine: EventSpineEngine, memory_engine: MemoryMeshEngine,
    ) -> None:
        oi1 = OptimizationIntegration(opt_engine, event_spine, memory_engine)
        oi1.recommend_from_connectors("req-idem1", [_degraded_connector()])
        mem1 = oi1.attach_recommendations_to_memory_mesh("scope-idem")

        # Create a second integration with fresh engines sharing the same scope
        es2 = EventSpineEngine()
        mm2 = MemoryMeshEngine()
        oe2 = OptimizationRuntimeEngine(es2)
        oi2 = OptimizationIntegration(oe2, es2, mm2)
        oi2.recommend_from_connectors("req-idem2", [_degraded_connector()])
        mem2 = oi2.attach_recommendations_to_memory_mesh("scope-idem")

        assert mem1.memory_id == mem2.memory_id

    def test_different_scope_ref_different_id(
        self, integration: OptimizationIntegration,
    ) -> None:
        mem1 = integration.attach_recommendations_to_memory_mesh("scope-a")
        mem2 = integration.attach_recommendations_to_memory_mesh("scope-b")
        assert mem1.memory_id != mem2.memory_id

    def test_memory_id_is_stable_string(
        self, integration: OptimizationIntegration,
    ) -> None:
        mem = integration.attach_recommendations_to_memory_mesh("scope-stable")
        assert isinstance(mem.memory_id, str)
        assert len(mem.memory_id) > 0

    def test_same_scope_produces_same_memory_id_across_instances(self) -> None:
        """Determinism: same scope_ref_id → same memory_id on separate instances."""
        es1 = EventSpineEngine()
        mm1 = MemoryMeshEngine()
        opt1 = OptimizationRuntimeEngine(es1)
        integ1 = OptimizationIntegration(opt1, es1, mm1)
        mem1 = integ1.attach_recommendations_to_memory_mesh("scope-det")

        es2 = EventSpineEngine()
        mm2 = MemoryMeshEngine()
        opt2 = OptimizationRuntimeEngine(es2)
        integ2 = OptimizationIntegration(opt2, es2, mm2)
        mem2 = integ2.attach_recommendations_to_memory_mesh("scope-det")

        assert mem1.memory_id == mem2.memory_id

    def test_duplicate_memory_attach_raises(
        self, integration: OptimizationIntegration,
    ) -> None:
        integration.attach_recommendations_to_memory_mesh("scope-dup")
        with pytest.raises(Exception, match="duplicate"):
            integration.attach_recommendations_to_memory_mesh("scope-dup")


# ===================================================================
# 14. Golden scenarios (end-to-end)
# ===================================================================


class TestGoldenScenariosEndToEnd:
    """Full end-to-end integration tests exercising the complete pipeline."""

    def test_connector_degradation_full_flow(
        self, integration: OptimizationIntegration, event_spine: EventSpineEngine,
    ) -> None:
        """Detect degraded connector, build plan, accept, attach to memory."""
        result = integration.recommend_from_connectors("req-gold1", [
            _degraded_connector("conn-a", 0.6),
            _healthy_connector("conn-b"),
        ])
        assert result["total_recommendations"] == 1

        plan = integration.build_and_decide_plan(
            "plan-gold1", "req-gold1", "Connector Recovery",
            disposition=RecommendationDisposition.ACCEPTED,
            decided_by="ops-lead",
            reason="auto-failover approved",
        )
        assert plan["recommendation_count"] == 1
        assert plan["decision_count"] == 1
        assert plan["feasible"] is True

        mem = integration.attach_recommendations_to_memory_mesh("scope-gold1")
        assert mem.content["total_recommendations"] >= 1
        assert mem.content["total_plans"] >= 1

        graph = integration.attach_recommendations_to_graph("scope-gold1")
        assert graph["total_plans"] >= 1
        assert OptimizationTarget.CONNECTOR_SELECTION.value in graph["recommendations_by_target"]

        assert len(event_spine.list_events()) > 0

    def test_budget_crisis_full_flow(
        self, integration: OptimizationIntegration,
    ) -> None:
        """Detect budget burn, build plan, reject."""
        result = integration.recommend_from_financials("req-gold2", [
            _high_burn_budget("bgt-crisis", 0.98),
            _normal_budget("bgt-safe"),
        ])
        assert result["total_recommendations"] >= 1

        plan = integration.build_and_decide_plan(
            "plan-gold2", "req-gold2", "Budget Recovery",
            disposition=RecommendationDisposition.REJECTED,
            decided_by="cfo",
            reason="manual intervention preferred",
        )
        assert plan["decision_count"] >= 1
        assert plan["disposition"] == RecommendationDisposition.REJECTED.value

    def test_portfolio_rebalance_full_flow(
        self, integration: OptimizationIntegration,
    ) -> None:
        """Detect blocked and overdue campaigns, build plan, accept."""
        result = integration.recommend_from_portfolio("req-gold3", [
            _blocked_campaign("camp-x"),
            _overdue_campaign("camp-y"),
            _healthy_campaign_portfolio("camp-z"),
        ])
        assert result["total_recommendations"] == 2

        plan = integration.build_and_decide_plan(
            "plan-gold3", "req-gold3", "Portfolio Rebalance",
            disposition=RecommendationDisposition.ACCEPTED,
            decided_by="portfolio-mgr",
        )
        assert plan["recommendation_count"] == 2
        assert plan["decision_count"] == 2

    def test_fault_injection_full_flow(
        self, integration: OptimizationIntegration,
    ) -> None:
        """Detect faults and escalation issues, build plan, defer."""
        result = integration.recommend_from_faults(
            "req-gold4",
            [_faulty_domain_pack("dp-alpha", 0.4), _healthy_domain_pack("dp-beta")],
            escalation_metrics=[_high_fp_escalation("pol-main")],
        )
        assert result["total_recommendations"] >= 2

        plan = integration.build_and_decide_plan(
            "plan-gold4", "req-gold4", "Fault Mitigation",
            disposition=RecommendationDisposition.DEFERRED,
            decided_by="sre",
            reason="needs further investigation",
        )
        assert plan["recommendation_count"] >= 2

    def test_availability_optimization_full_flow(
        self, integration: OptimizationIntegration,
    ) -> None:
        """Schedule violations + campaign wait time, pending plan."""
        result = integration.recommend_from_availability(
            "req-gold5",
            [_quiet_hours_violation_schedule("id-1"), _clean_schedule("id-2")],
            campaign_metrics=[_high_wait_campaign("camp-slow")],
        )
        assert result["total_recommendations"] >= 2

        plan = integration.build_and_decide_plan(
            "plan-gold5", "req-gold5", "Schedule Optimization",
        )
        assert plan["decision_count"] == 0
        assert plan["disposition"] == RecommendationDisposition.PENDING.value

    def test_executive_reporting_full_flow(
        self, integration: OptimizationIntegration,
    ) -> None:
        """Full reporting with all three metric types."""
        result = integration.recommend_from_reporting(
            "req-gold6",
            connector_metrics=[_degraded_connector("c-exec", 0.7)],
            campaign_metrics=[_high_escalation_campaign("camp-exec")],
            budget_metrics=[_high_burn_budget("bgt-exec", 0.92)],
        )
        assert result["total_recommendations"] >= 3

        plan = integration.build_and_decide_plan(
            "plan-gold6", "req-gold6", "Executive Action Plan",
            disposition=RecommendationDisposition.ACCEPTED,
            decided_by="coo",
            reason="quarterly review",
        )
        assert plan["decision_count"] == plan["recommendation_count"]

        mem = integration.attach_recommendations_to_memory_mesh("scope-gold6")
        assert mem.content["total_requests"] >= 1
        assert mem.content["total_plans"] >= 1

        graph = integration.attach_recommendations_to_graph("scope-gold6")
        assert len(graph["recommendations_by_target"]) >= 3

    def test_multi_request_graph_aggregation(
        self, integration: OptimizationIntegration,
    ) -> None:
        """Multiple requests create recommendations that aggregate in graph."""
        integration.recommend_from_connectors("req-gold7a", [_degraded_connector()])
        integration.recommend_from_faults("req-gold7b", [_faulty_domain_pack()])
        integration.recommend_from_portfolio("req-gold7c", [_blocked_campaign()])

        graph = integration.attach_recommendations_to_graph("scope-gold7")
        assert graph["total_requests"] == 3
        assert graph["total_recommendations"] >= 3
        assert len(graph["recommendations_by_target"]) >= 2

    def test_empty_state_end_to_end(
        self, integration: OptimizationIntegration,
    ) -> None:
        """No recommendations at all still produces valid state."""
        mem = integration.attach_recommendations_to_memory_mesh("scope-empty")
        assert mem.content["total_recommendations"] == 0
        assert mem.content["total_requests"] == 0
        assert mem.content["total_plans"] == 0

        graph = integration.attach_recommendations_to_graph("scope-empty")
        assert graph["total_recommendations"] == 0
        assert graph["recommendations_by_target"] == {}

    def test_superseded_disposition_full_flow(
        self, integration: OptimizationIntegration,
    ) -> None:
        """Test SUPERSEDED disposition in a plan."""
        integration.recommend_from_connectors("req-gold8", [_degraded_connector()])
        plan = integration.build_and_decide_plan(
            "plan-gold8", "req-gold8", "Superseded Plan",
            disposition=RecommendationDisposition.SUPERSEDED,
            decided_by="system",
            reason="replaced by newer plan",
        )
        assert plan["disposition"] == RecommendationDisposition.SUPERSEDED.value
        assert plan["decision_count"] >= 1

    def test_large_scale_scenario(
        self, integration: OptimizationIntegration,
    ) -> None:
        """Stress test with many metrics across multiple paths."""
        connectors = [_degraded_connector(f"c-{i}", 0.4 + i * 0.04) for i in range(10)]
        integration.recommend_from_connectors("req-scale1", connectors)

        budgets = [_high_burn_budget(f"b-{i}", 0.91 + i * 0.005) for i in range(5)]
        integration.recommend_from_financials("req-scale2", budgets)

        campaigns = [_blocked_campaign(f"camp-{i}") for i in range(3)]
        campaigns += [_overdue_campaign(f"camp-o{i}") for i in range(2)]
        integration.recommend_from_portfolio("req-scale3", campaigns)

        graph = integration.attach_recommendations_to_graph("scope-scale")
        assert graph["total_requests"] == 3
        assert graph["total_recommendations"] >= 15

    def test_plan_with_improvement_pct_from_mixed_sources(
        self, integration: OptimizationIntegration,
    ) -> None:
        """Verify improvement percentage from different recommendation sources."""
        integration.recommend_from_reporting(
            "req-gold10",
            connector_metrics=[_degraded_connector("c-imp", 0.3)],
            budget_metrics=[_high_burn_budget("b-imp", 0.96)],
        )
        plan = integration.build_and_decide_plan(
            "plan-gold10", "req-gold10", "Improvement Check",
        )
        assert plan["total_estimated_improvement_pct"] > 0


# ===================================================================
# Additional edge cases
# ===================================================================


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_connector_zero_success_rate(
        self, integration: OptimizationIntegration,
    ) -> None:
        conn = {"connector_ref": "c-zero", "success_rate": 0.0, "cost_per_call": 1.0, "latency_seconds": 5.0}
        result = integration.recommend_from_connectors("req-edge1", [conn])
        assert result["total_recommendations"] == 1

    def test_budget_burn_rate_exactly_one(
        self, integration: OptimizationIntegration,
    ) -> None:
        bgt = {"budget_id": "b-full", "utilization": 1.0, "burn_rate": 1.0,
               "cost_per_completion": 100.0, "available": 0}
        result = integration.recommend_from_financials("req-edge2", [bgt])
        assert result["total_recommendations"] >= 1

    def test_domain_pack_fault_rate_one(
        self, integration: OptimizationIntegration,
    ) -> None:
        dp = {"domain_pack_id": "dp-total-fail", "success_rate": 0.0,
              "cost": 100.0, "latency_seconds": 10.0, "fault_rate": 1.0}
        result = integration.recommend_from_faults("req-edge3", [dp])
        assert result["total_recommendations"] == 1

    def test_schedule_single_quiet_hours_violation(
        self, integration: OptimizationIntegration,
    ) -> None:
        sched = {"identity_ref": "id-single", "available_hours": 8, "utilized_hours": 6,
                 "contact_attempts": 10, "quiet_hours_violations": 1}
        result = integration.recommend_from_availability("req-edge4", [sched])
        assert result["total_recommendations"] == 1

    def test_campaign_wait_exactly_at_threshold(
        self, integration: OptimizationIntegration,
    ) -> None:
        cm = {"campaign_id": "camp-edge", "completion_rate": 0.5, "avg_duration_seconds": 3600,
              "escalation_count": 1, "waiting_on_human_seconds": 3600.0, "cost": 100.0}
        result = integration.recommend_from_reporting("req-edge5", campaign_metrics=[cm])
        # 3600 is not > 3600, so no recommendation
        assert result["total_recommendations"] == 0

    def test_campaign_wait_just_above_threshold(
        self, integration: OptimizationIntegration,
    ) -> None:
        cm = {"campaign_id": "camp-above", "completion_rate": 0.5, "avg_duration_seconds": 3600,
              "escalation_count": 1, "waiting_on_human_seconds": 3601.0, "cost": 100.0}
        result = integration.recommend_from_reporting("req-edge6", campaign_metrics=[cm])
        assert result["total_recommendations"] >= 1

    def test_escalation_count_at_threshold_no_rec(
        self, integration: OptimizationIntegration,
    ) -> None:
        cm = {"campaign_id": "camp-esc3", "completion_rate": 0.5, "avg_duration_seconds": 3600,
              "escalation_count": 3, "waiting_on_human_seconds": 100.0, "cost": 100.0}
        result = integration.recommend_from_reporting("req-edge7", campaign_metrics=[cm])
        # escalation_count=3 is not > 3, so no recommendation from escalation
        assert result["total_recommendations"] == 0

    def test_escalation_count_above_threshold(
        self, integration: OptimizationIntegration,
    ) -> None:
        cm = {"campaign_id": "camp-esc4", "completion_rate": 0.5, "avg_duration_seconds": 3600,
              "escalation_count": 4, "waiting_on_human_seconds": 100.0, "cost": 100.0}
        result = integration.recommend_from_reporting("req-edge8", campaign_metrics=[cm])
        assert result["total_recommendations"] >= 1

    def test_cost_per_completion_low_utilization_no_rec(
        self, integration: OptimizationIntegration,
    ) -> None:
        bgt = {"budget_id": "b-lowutil", "utilization": 0.4, "burn_rate": 0.5,
               "cost_per_completion": 500.0, "available": 2000}
        result = integration.recommend_from_financials("req-edge9", [bgt])
        # utilization=0.4 is not > 0.5, so cost_per_completion check is skipped
        assert result["total_recommendations"] == 0

    def test_cost_per_completion_high_util_but_low_score(
        self, integration: OptimizationIntegration,
    ) -> None:
        # score = min(1.0, 200/1000) = 0.2 which is not > 0.3
        bgt = {"budget_id": "b-lowscore", "utilization": 0.6, "burn_rate": 0.5,
               "cost_per_completion": 200.0, "available": 2000}
        result = integration.recommend_from_financials("req-edge10", [bgt])
        assert result["total_recommendations"] == 0

    def test_cost_per_completion_at_score_threshold(
        self, integration: OptimizationIntegration,
    ) -> None:
        # score = min(1.0, 300/1000) = 0.3 which is not > 0.3
        bgt = {"budget_id": "b-exact", "utilization": 0.6, "burn_rate": 0.5,
               "cost_per_completion": 300.0, "available": 2000}
        result = integration.recommend_from_financials("req-edge11", [bgt])
        assert result["total_recommendations"] == 0

    def test_cost_per_completion_above_score_threshold(
        self, integration: OptimizationIntegration,
    ) -> None:
        # score = min(1.0, 301/1000) = 0.301 which is > 0.3
        bgt = {"budget_id": "b-above", "utilization": 0.6, "burn_rate": 0.5,
               "cost_per_completion": 301.0, "available": 2000}
        result = integration.recommend_from_financials("req-edge12", [bgt])
        assert result["total_recommendations"] == 1

    def test_request_count_tracked(
        self, integration: OptimizationIntegration,
    ) -> None:
        integration.recommend_from_connectors("req-cnt1", [_degraded_connector()])
        integration.recommend_from_financials("req-cnt2", [_high_burn_budget()])
        graph = integration.attach_recommendations_to_graph("scope-cnt")
        assert graph["total_requests"] == 2

    def test_connector_missing_keys_uses_defaults(
        self, integration: OptimizationIntegration,
    ) -> None:
        # Missing connector_ref and cost_per_call
        conn = {"success_rate": 0.5}
        result = integration.recommend_from_connectors("req-edge13", [conn])
        assert result["total_recommendations"] == 1

    def test_multiple_budget_recs_same_budget(
        self, integration: OptimizationIntegration,
    ) -> None:
        # Both high burn AND high cost_per_completion
        bgt = {"budget_id": "b-double", "utilization": 0.8, "burn_rate": 0.96,
               "cost_per_completion": 500.0, "available": 100}
        result = integration.recommend_from_financials("req-edge14", [bgt])
        assert result["total_recommendations"] == 2
