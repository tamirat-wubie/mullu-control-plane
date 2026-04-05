"""Purpose: verify simulation integration bridge, view model, and console rendering.
Governance scope: simulation integration tests only.
Dependencies: simulation engine, simulation contracts, operational graph, view models, console.
Invariants: all tests are deterministic, no network, no IO.
"""

from __future__ import annotations

from mcoi_runtime.app.console import render_simulation_summary
from mcoi_runtime.app.view_models import SimulationSummaryView
from mcoi_runtime.contracts.graph import NodeType
from mcoi_runtime.contracts.simulation import (
    RiskLevel,
    SimulationComparison,
    SimulationOption,
    SimulationVerdict,
    VerdictType,
)
from mcoi_runtime.core.operational_graph import OperationalGraph
from mcoi_runtime.core.simulation import SimulationEngine
from mcoi_runtime.core.simulation_integration import SimulationBridge


def _make_clock() -> callable:
    """Return a clock that produces unique but deterministic timestamps."""
    counter = [0]

    def clock() -> str:
        counter[0] += 1
        return f"2026-03-20T00:00:{counter[0]:02d}+00:00"

    return clock


def _make_graph_and_engine() -> tuple[OperationalGraph, SimulationEngine]:
    """Create a graph and engine with a deterministic clock."""
    clock = _make_clock()
    graph = OperationalGraph(clock=clock)
    engine = SimulationEngine(graph=graph, clock=clock)
    return graph, engine


def _low_risk_option(option_id: str = "opt-low") -> SimulationOption:
    return SimulationOption(
        option_id=option_id,
        label="Low risk path",
        risk_level=RiskLevel.LOW,
        estimated_cost=100.0,
        estimated_duration_seconds=60.0,
        success_probability=0.95,
    )


def _high_risk_option(option_id: str = "opt-high") -> SimulationOption:
    return SimulationOption(
        option_id=option_id,
        label="High risk path",
        risk_level=RiskLevel.HIGH,
        estimated_cost=5000.0,
        estimated_duration_seconds=300.0,
        success_probability=0.6,
    )


def _critical_risk_option(option_id: str = "opt-critical") -> SimulationOption:
    return SimulationOption(
        option_id=option_id,
        label="Critical risk path",
        risk_level=RiskLevel.CRITICAL,
        estimated_cost=9000.0,
        estimated_duration_seconds=600.0,
        success_probability=0.3,
    )


def _medium_risk_option(option_id: str = "opt-medium") -> SimulationOption:
    return SimulationOption(
        option_id=option_id,
        label="Medium risk path",
        risk_level=RiskLevel.MODERATE,
        estimated_cost=2000.0,
        estimated_duration_seconds=120.0,
        success_probability=0.8,
    )


def _safe_option(option_id: str = "opt-safe") -> SimulationOption:
    return SimulationOption(
        option_id=option_id,
        label="Safe path",
        risk_level=RiskLevel.MINIMAL,
        estimated_cost=10.0,
        estimated_duration_seconds=10.0,
        success_probability=0.99,
    )


# ---------------------------------------------------------------------------
# simulate_before_goal tests
# ---------------------------------------------------------------------------


class TestSimulateBeforeGoal:
    """Tests for SimulationBridge.simulate_before_goal."""

    def test_produces_comparison_and_verdict(self) -> None:
        graph, engine = _make_graph_and_engine()
        graph.add_node("goal-1", NodeType.GOAL, "Deploy service")

        options = [_low_risk_option(), _high_risk_option()]
        comparison, verdict = SimulationBridge.simulate_before_goal(
            engine, graph, "goal-1", options,
        )

        assert isinstance(comparison, SimulationComparison)
        assert isinstance(verdict, SimulationVerdict)
        assert len(comparison.ranked_option_ids) == 2

    def test_recommends_lower_risk_option(self) -> None:
        graph, engine = _make_graph_and_engine()
        graph.add_node("goal-2", NodeType.GOAL, "Scale workers")

        low = _low_risk_option()
        high = _high_risk_option()
        comparison, verdict = SimulationBridge.simulate_before_goal(
            engine, graph, "goal-2", [low, high],
        )

        # Low risk option should score higher and be recommended
        assert verdict.recommended_option_id == "opt-low"
        assert comparison.ranked_option_ids[0] == "opt-low"

    def test_goal_not_in_graph_still_works(self) -> None:
        graph, engine = _make_graph_and_engine()
        # Goal node not added to graph — should still simulate
        options = [_low_risk_option()]
        comparison, verdict = SimulationBridge.simulate_before_goal(
            engine, graph, "missing-goal", options,
        )
        assert isinstance(comparison, SimulationComparison)
        assert isinstance(verdict, SimulationVerdict)

    def test_request_id_prefix_is_goal(self) -> None:
        graph, engine = _make_graph_and_engine()
        graph.add_node("goal-3", NodeType.GOAL, "Test goal")
        options = [_safe_option()]
        comparison, verdict = SimulationBridge.simulate_before_goal(
            engine, graph, "goal-3", options,
        )
        assert comparison.request_id.startswith("sim-req-goal-")

    def test_goal_request_description_is_bounded(self) -> None:
        graph, engine = _make_graph_and_engine()
        graph.add_node("goal-bounded", NodeType.GOAL, "Deploy service")
        captured: dict[str, str] = {}
        original = engine.full_simulation

        def capture(request, *args, **kwargs):
            captured["description"] = request.description
            return original(request, *args, **kwargs)

        engine.full_simulation = capture
        SimulationBridge.simulate_before_goal(
            engine, graph, "goal-bounded", [_safe_option()],
        )

        assert captured["description"] == "Goal simulation"
        assert "goal-bounded" not in captured["description"]
        assert "Deploy service" not in captured["description"]


# ---------------------------------------------------------------------------
# simulate_before_recovery tests
# ---------------------------------------------------------------------------


class TestSimulateBeforeRecovery:
    """Tests for SimulationBridge.simulate_before_recovery."""

    def test_produces_comparison_and_verdict(self) -> None:
        graph, engine = _make_graph_and_engine()
        graph.add_node("inc-1", NodeType.INCIDENT, "Server outage")

        options = [_medium_risk_option(), _critical_risk_option()]
        comparison, verdict = SimulationBridge.simulate_before_recovery(
            engine, graph, "inc-1", options,
        )

        assert isinstance(comparison, SimulationComparison)
        assert isinstance(verdict, SimulationVerdict)
        assert len(comparison.ranked_option_ids) == 2

    def test_escalation_for_critical_risk(self) -> None:
        graph, engine = _make_graph_and_engine()
        graph.add_node("inc-2", NodeType.INCIDENT, "Data breach")

        options = [_critical_risk_option(), _medium_risk_option()]
        comparison, verdict = SimulationBridge.simulate_before_recovery(
            engine, graph, "inc-2", options,
        )

        # Critical risk should trigger escalation verdict
        assert verdict.verdict_type == VerdictType.ESCALATE

    def test_request_id_prefix_is_recovery(self) -> None:
        graph, engine = _make_graph_and_engine()
        graph.add_node("inc-3", NodeType.INCIDENT, "Test incident")
        options = [_low_risk_option()]
        comparison, verdict = SimulationBridge.simulate_before_recovery(
            engine, graph, "inc-3", options,
        )
        assert comparison.request_id.startswith("sim-req-recovery-")

    def test_recovery_request_description_is_bounded(self) -> None:
        graph, engine = _make_graph_and_engine()
        graph.add_node("inc-bounded", NodeType.INCIDENT, "Server outage")
        captured: dict[str, str] = {}
        original = engine.full_simulation

        def capture(request, *args, **kwargs):
            captured["description"] = request.description
            return original(request, *args, **kwargs)

        engine.full_simulation = capture
        SimulationBridge.simulate_before_recovery(
            engine, graph, "inc-bounded", [_low_risk_option()],
        )

        assert captured["description"] == "Recovery simulation"
        assert "inc-bounded" not in captured["description"]
        assert "Server outage" not in captured["description"]


# ---------------------------------------------------------------------------
# simulate_before_approval tests
# ---------------------------------------------------------------------------


class TestSimulateBeforeApproval:
    """Tests for SimulationBridge.simulate_before_approval."""

    def test_produces_comparison_and_verdict(self) -> None:
        graph, engine = _make_graph_and_engine()
        graph.add_node("action-1", NodeType.APPROVAL, "Deploy to prod")

        approve = _safe_option("opt-approve")
        reject = SimulationOption(
            option_id="opt-reject",
            label="Reject action",
            risk_level=RiskLevel.MINIMAL,
            estimated_cost=0.0,
            estimated_duration_seconds=0.0,
            success_probability=1.0,
        )
        escalate = _medium_risk_option("opt-escalate")

        comparison, verdict = SimulationBridge.simulate_before_approval(
            engine, graph, "action-1", [approve, reject, escalate],
        )

        assert isinstance(comparison, SimulationComparison)
        assert isinstance(verdict, SimulationVerdict)
        assert len(comparison.ranked_option_ids) == 3

    def test_proceed_for_safe_action(self) -> None:
        graph, engine = _make_graph_and_engine()
        graph.add_node("action-2", NodeType.APPROVAL, "Minor config change")

        approve = _safe_option("opt-approve")
        reject = SimulationOption(
            option_id="opt-reject",
            label="Reject",
            risk_level=RiskLevel.MINIMAL,
            estimated_cost=0.0,
            estimated_duration_seconds=0.0,
            success_probability=1.0,
        )

        comparison, verdict = SimulationBridge.simulate_before_approval(
            engine, graph, "action-2", [approve, reject],
        )

        assert verdict.verdict_type == VerdictType.PROCEED

    def test_request_id_prefix_is_approval(self) -> None:
        graph, engine = _make_graph_and_engine()
        graph.add_node("action-3", NodeType.APPROVAL, "Test action")
        options = [_safe_option()]
        comparison, verdict = SimulationBridge.simulate_before_approval(
            engine, graph, "action-3", options,
        )
        assert comparison.request_id.startswith("sim-req-approval-")

    def test_approval_request_description_is_bounded(self) -> None:
        graph, engine = _make_graph_and_engine()
        graph.add_node("action-bounded", NodeType.APPROVAL, "Deploy to prod")
        captured: dict[str, str] = {}
        original = engine.full_simulation

        def capture(request, *args, **kwargs):
            captured["description"] = request.description
            return original(request, *args, **kwargs)

        engine.full_simulation = capture
        SimulationBridge.simulate_before_approval(
            engine, graph, "action-bounded", [_safe_option("opt-approve")],
        )

        assert captured["description"] == "Approval simulation"
        assert "action-bounded" not in captured["description"]
        assert "Deploy to prod" not in captured["description"]


# ---------------------------------------------------------------------------
# SimulationSummaryView tests
# ---------------------------------------------------------------------------


class TestSimulationSummaryView:
    """Tests for the SimulationSummaryView view model."""

    def test_from_result_basic(self) -> None:
        graph, engine = _make_graph_and_engine()
        graph.add_node("goal-vm", NodeType.GOAL, "View model test")
        options = [_low_risk_option(), _high_risk_option()]
        comparison, verdict = SimulationBridge.simulate_before_goal(
            engine, graph, "goal-vm", options,
        )

        view = SimulationSummaryView.from_result(comparison, verdict)

        assert view.request_id == comparison.request_id
        assert view.option_count == 2
        assert view.recommended_option_id == verdict.recommended_option_id
        assert view.verdict_type == verdict.verdict_type.value
        assert 0.0 <= view.confidence <= 1.0
        assert view.top_risk_level == comparison.top_risk_level.value

    def test_from_result_single_option(self) -> None:
        graph, engine = _make_graph_and_engine()
        graph.add_node("goal-single", NodeType.GOAL, "Single option")
        options = [_safe_option()]
        comparison, verdict = SimulationBridge.simulate_before_goal(
            engine, graph, "goal-single", options,
        )

        view = SimulationSummaryView.from_result(comparison, verdict)
        assert view.option_count == 1
        assert view.recommended_option_id == "opt-safe"

    def test_view_is_frozen(self) -> None:
        graph, engine = _make_graph_and_engine()
        graph.add_node("goal-frozen", NodeType.GOAL, "Frozen test")
        options = [_safe_option()]
        comparison, verdict = SimulationBridge.simulate_before_goal(
            engine, graph, "goal-frozen", options,
        )
        view = SimulationSummaryView.from_result(comparison, verdict)

        try:
            view.confidence = 0.0  # type: ignore[misc]
            assert False, "Should have raised"
        except AttributeError:
            pass  # Expected: frozen dataclass


# ---------------------------------------------------------------------------
# Console rendering tests
# ---------------------------------------------------------------------------


class TestRenderSimulationSummary:
    """Tests for render_simulation_summary."""

    def test_renders_all_fields(self) -> None:
        graph, engine = _make_graph_and_engine()
        graph.add_node("goal-render", NodeType.GOAL, "Render test")
        options = [_low_risk_option(), _high_risk_option()]
        comparison, verdict = SimulationBridge.simulate_before_goal(
            engine, graph, "goal-render", options,
        )
        view = SimulationSummaryView.from_result(comparison, verdict)

        output = render_simulation_summary(view)

        assert "=== Simulation Summary ===" in output
        assert "request_id:" in output
        assert "option_count:" in output
        assert "recommended_option:" in output
        assert "verdict_type:" in output
        assert "confidence:" in output
        assert "top_risk_level:" in output

    def test_render_is_deterministic(self) -> None:
        graph1, engine1 = _make_graph_and_engine()
        graph1.add_node("goal-det", NodeType.GOAL, "Determinism")
        graph2, engine2 = _make_graph_and_engine()
        graph2.add_node("goal-det", NodeType.GOAL, "Determinism")

        options = [_safe_option()]

        c1, v1 = SimulationBridge.simulate_before_goal(engine1, graph1, "goal-det", options)
        c2, v2 = SimulationBridge.simulate_before_goal(engine2, graph2, "goal-det", options)

        view1 = SimulationSummaryView.from_result(c1, v1)
        view2 = SimulationSummaryView.from_result(c2, v2)

        # Same inputs produce same view values (IDs differ but structure matches)
        assert view1.option_count == view2.option_count
        assert view1.verdict_type == view2.verdict_type
        assert view1.confidence == view2.confidence
        assert view1.top_risk_level == view2.top_risk_level
