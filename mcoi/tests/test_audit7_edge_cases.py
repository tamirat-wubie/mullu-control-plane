"""Edge case tests for Holistic Audit #7 fixes.

Covers:
  - Plan items must be PlanItem instances
  - ReactionRule rejects empty conditions
  - ApprovalRequest validates expires_at when present
  - BenchmarkResult validates executed_at when present
  - OperationalGraph returns immutable tuples from query methods
  - DecisionLearning returns immutable mapping from get_learned_factor_adjustments
  - Rust maf-agent sample_count u64 parity (structural — tested in Rust suite)
"""

from __future__ import annotations

import pytest
from types import MappingProxyType

# ── Contract imports ──────────────────────────────────────────────

from mcoi_runtime.contracts.plan import Plan, PlanItem
from mcoi_runtime.contracts.reaction import (
    BackpressureStrategy,
    ReactionCondition,
    ReactionRule,
    ReactionTarget,
    ReactionTargetKind,
)
from mcoi_runtime.contracts.approval import (
    ApprovalRequest,
    ApprovalScope,
    ApprovalScopeType,
)
from mcoi_runtime.contracts.benchmark import (
    BenchmarkMetric,
    BenchmarkOutcome,
    BenchmarkResult,
    MetricKind,
)

# ── Core imports ──────────────────────────────────────────────────

from mcoi_runtime.core.operational_graph import OperationalGraph
from mcoi_runtime.contracts.graph import NodeType, EdgeType

NOW = "2025-01-01T00:00:00+00:00"


# =====================================================================
# Plan — items must be PlanItem instances
# =====================================================================


def _make_plan_item(item_id: str = "item-1") -> PlanItem:
    return PlanItem(item_id=item_id, description="Do a thing")


class TestPlanItemValidation:
    """Plan.__post_init__ must reject non-PlanItem objects in items tuple."""

    def test_valid_plan_items_accepted(self) -> None:
        plan = Plan(
            plan_id="p-1",
            goal_id="g-1",
            state_hash="abc123",
            registry_hash="def456",
            items=(_make_plan_item(),),
        )
        assert plan.items[0].item_id == "item-1"

    def test_plan_rejects_dict_in_items(self) -> None:
        with pytest.raises(ValueError, match="must be a PlanItem instance"):
            Plan(
                plan_id="p-1",
                goal_id="g-1",
                state_hash="abc123",
                registry_hash="def456",
                items=({"item_id": "fake", "description": "nope"},),  # type: ignore[arg-type]
            )

    def test_plan_rejects_string_in_items(self) -> None:
        with pytest.raises(ValueError, match="must be a PlanItem instance"):
            Plan(
                plan_id="p-1",
                goal_id="g-1",
                state_hash="abc123",
                registry_hash="def456",
                items=("not-a-plan-item",),  # type: ignore[arg-type]
            )

    def test_plan_rejects_none_in_items(self) -> None:
        with pytest.raises(ValueError, match="must be a PlanItem instance"):
            Plan(
                plan_id="p-1",
                goal_id="g-1",
                state_hash="abc123",
                registry_hash="def456",
                items=(None,),  # type: ignore[arg-type]
            )

    def test_plan_rejects_mixed_valid_invalid(self) -> None:
        with pytest.raises(ValueError, match="must be a PlanItem instance"):
            Plan(
                plan_id="p-1",
                goal_id="g-1",
                state_hash="abc123",
                registry_hash="def456",
                items=(_make_plan_item(), "bad"),  # type: ignore[arg-type]
            )


# =====================================================================
# ReactionRule — empty conditions guard
# =====================================================================


def _make_condition(cid: str = "c-1") -> ReactionCondition:
    return ReactionCondition(
        condition_id=cid,
        field_path="payload.status",
        operator="eq",
        expected_value="active",
    )


def _make_target() -> ReactionTarget:
    return ReactionTarget(
        target_id="t-1",
        kind=ReactionTargetKind.NOTIFY,
        target_ref_id="ref-1",
        parameters={},
    )


class TestReactionRuleEmptyConditions:
    """ReactionRule must reject empty conditions tuple."""

    def test_valid_conditions_accepted(self) -> None:
        rule = ReactionRule(
            rule_id="r-1",
            name="test-rule",
            event_type="status_changed",
            conditions=(_make_condition(),),
            target=_make_target(),
            created_at=NOW,
        )
        assert len(rule.conditions) == 1

    def test_empty_conditions_rejected(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            ReactionRule(
                rule_id="r-1",
                name="test-rule",
                event_type="status_changed",
                conditions=(),
                target=_make_target(),
                created_at=NOW,
            )

    def test_conditions_must_be_tuple(self) -> None:
        with pytest.raises(ValueError, match="must be a tuple"):
            ReactionRule(
                rule_id="r-1",
                name="test-rule",
                event_type="status_changed",
                conditions=[_make_condition()],  # type: ignore[arg-type]
                target=_make_target(),
                created_at=NOW,
            )


# =====================================================================
# ApprovalRequest — expires_at validation
# =====================================================================


def _make_approval_scope() -> ApprovalScope:
    return ApprovalScope(
        scope_type=ApprovalScopeType.EXECUTION,
        target_id="target-1",
    )


class TestApprovalExpiresAtValidation:
    """ApprovalRequest must validate expires_at when present."""

    def test_none_expires_at_accepted(self) -> None:
        req = ApprovalRequest(
            request_id="ar-1",
            requester_id="user-1",
            scope=_make_approval_scope(),
            reason="testing",
            requested_at="2025-01-01T00:00:00Z",
            expires_at=None,
        )
        assert req.expires_at is None

    def test_valid_expires_at_accepted(self) -> None:
        req = ApprovalRequest(
            request_id="ar-1",
            requester_id="user-1",
            scope=_make_approval_scope(),
            reason="testing",
            requested_at="2025-01-01T00:00:00Z",
            expires_at="2025-01-02T00:00:00Z",
        )
        assert req.expires_at == "2025-01-02T00:00:00Z"

    def test_invalid_expires_at_rejected(self) -> None:
        with pytest.raises(ValueError):
            ApprovalRequest(
                request_id="ar-1",
                requester_id="user-1",
                scope=_make_approval_scope(),
                reason="testing",
                requested_at="2025-01-01T00:00:00Z",
                expires_at="not-a-date",
            )

    def test_empty_string_expires_at_rejected(self) -> None:
        with pytest.raises(ValueError):
            ApprovalRequest(
                request_id="ar-1",
                requester_id="user-1",
                scope=_make_approval_scope(),
                reason="testing",
                requested_at="2025-01-01T00:00:00Z",
                expires_at="",
            )


# =====================================================================
# BenchmarkResult — executed_at validation
# =====================================================================


def _make_metric() -> BenchmarkMetric:
    return BenchmarkMetric(
        metric_id="m-1",
        kind=MetricKind.ACCURACY,
        name="acc",
        value=0.9,
        threshold=0.8,
        passed=True,
    )


class TestBenchmarkExecutedAtValidation:
    """BenchmarkResult must validate executed_at when non-empty."""

    def test_empty_executed_at_rejected(self) -> None:
        with pytest.raises(ValueError):
            BenchmarkResult(
                result_id="br-1",
                scenario_id="sc-1",
                outcome=BenchmarkOutcome.PASS,
                metrics=(_make_metric(),),
                actual_properties={},
                executed_at="",
            )

    def test_valid_executed_at_accepted(self) -> None:
        result = BenchmarkResult(
            result_id="br-1",
            scenario_id="sc-1",
            outcome=BenchmarkOutcome.PASS,
            metrics=(_make_metric(),),
            actual_properties={},
            executed_at="2025-06-01T12:00:00Z",
        )
        assert result.executed_at == "2025-06-01T12:00:00Z"

    def test_invalid_executed_at_rejected(self) -> None:
        with pytest.raises(ValueError):
            BenchmarkResult(
                result_id="br-1",
                scenario_id="sc-1",
                outcome=BenchmarkOutcome.PASS,
                metrics=(_make_metric(),),
                actual_properties={},
                executed_at="garbage",
            )


# =====================================================================
# OperationalGraph — immutable tuple returns
# =====================================================================


def _make_clock() -> str:
    return "2025-01-01T00:00:00Z"


class TestOperationalGraphImmutableReturns:
    """Query methods must return tuples, not lists."""

    def test_query_by_type_returns_tuple(self) -> None:
        graph = OperationalGraph(clock=_make_clock)
        graph.add_node(node_id="n-1", node_type=NodeType.GOAL, label="g1")
        result = graph.query_by_type(NodeType.GOAL)
        assert isinstance(result, tuple)

    def test_query_by_type_empty_returns_tuple(self) -> None:
        graph = OperationalGraph(clock=_make_clock)
        result = graph.query_by_type(NodeType.GOAL)
        assert isinstance(result, tuple)
        assert len(result) == 0

    def test_get_outgoing_edges_returns_tuple(self) -> None:
        graph = OperationalGraph(clock=_make_clock)
        n1 = graph.add_node(node_id="n-1", node_type=NodeType.GOAL, label="g1")
        n2 = graph.add_node(node_id="n-2", node_type=NodeType.JOB, label="j1")
        graph.add_edge(
            edge_type=EdgeType.DEPENDS_ON,
            source_id=n1.node_id,
            target_id=n2.node_id,
        )
        result = graph.get_outgoing_edges(n1.node_id)
        assert isinstance(result, tuple)
        assert len(result) == 1

    def test_get_incoming_edges_returns_tuple(self) -> None:
        graph = OperationalGraph(clock=_make_clock)
        n1 = graph.add_node(node_id="n-1", node_type=NodeType.GOAL, label="g1")
        n2 = graph.add_node(node_id="n-2", node_type=NodeType.JOB, label="j1")
        graph.add_edge(
            edge_type=EdgeType.DEPENDS_ON,
            source_id=n1.node_id,
            target_id=n2.node_id,
        )
        result = graph.get_incoming_edges(n2.node_id)
        assert isinstance(result, tuple)
        assert len(result) == 1

    def test_get_neighbors_returns_tuple(self) -> None:
        graph = OperationalGraph(clock=_make_clock)
        n1 = graph.add_node(node_id="n-1", node_type=NodeType.GOAL, label="g1")
        n2 = graph.add_node(node_id="n-2", node_type=NodeType.JOB, label="j1")
        graph.add_edge(
            edge_type=EdgeType.DEPENDS_ON,
            source_id=n1.node_id,
            target_id=n2.node_id,
        )
        result = graph.get_neighbors(n1.node_id)
        assert isinstance(result, tuple)
        assert n2.node_id in result

    def test_find_obligations_returns_tuple(self) -> None:
        graph = OperationalGraph(clock=_make_clock)
        n1 = graph.add_node(node_id="n-1", node_type=NodeType.GOAL, label="g1")
        result = graph.find_obligations(n1.node_id)
        assert isinstance(result, tuple)
        assert len(result) == 0


# =====================================================================
# DecisionLearning — immutable mapping return
# =====================================================================


class TestDecisionLearningImmutableReturn:
    """get_learned_factor_adjustments must return an immutable mapping."""

    def test_returns_mapping_proxy(self) -> None:
        from mcoi_runtime.core.decision_learning import DecisionLearningEngine

        engine = DecisionLearningEngine(clock=_make_clock)
        result = engine.get_learned_factor_adjustments()
        assert isinstance(result, MappingProxyType)

    def test_empty_adjustments_returns_empty_immutable(self) -> None:
        from mcoi_runtime.core.decision_learning import DecisionLearningEngine

        engine = DecisionLearningEngine(clock=_make_clock)
        result = engine.get_learned_factor_adjustments()
        assert len(result) == 0
        with pytest.raises(TypeError):
            result["new_key"] = 1.0  # type: ignore[index]

    def test_immutable_mapping_rejects_mutation(self) -> None:
        from mcoi_runtime.core.decision_learning import DecisionLearningEngine

        engine = DecisionLearningEngine(clock=_make_clock)
        result = engine.get_learned_factor_adjustments()
        with pytest.raises(TypeError):
            result["anything"] = 0.5  # type: ignore[index]
