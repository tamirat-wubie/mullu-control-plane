"""Purpose: golden scenario tests for simulation runtime integration.
Governance scope: end-to-end simulation scenarios only.
Dependencies: simulation engine, simulation contracts, operational graph, simulation bridge.
Invariants: all scenarios are deterministic, no network, no IO.

Golden scenarios:
1. Goal with two workflow options — lower-risk option recommended
2. Incident recovery — escalation recommended for critical risk
3. Approval simulation — proceed recommended for safe action
4. Dense graph with many obligations — high review burden detected
5. Empty graph simulation — minimal risk, proceed
6. Single option simulation — deterministic verdict
"""

from __future__ import annotations

from mcoi_runtime.contracts.graph import EdgeType, NodeType
from mcoi_runtime.contracts.simulation import (
    RiskLevel,
    SimulationComparison,
    SimulationOption,
    SimulationRequest,
    SimulationVerdict,
    VerdictType,
)
from mcoi_runtime.core.operational_graph import OperationalGraph
from mcoi_runtime.core.simulation import SimulationEngine
from mcoi_runtime.core.simulation_integration import SimulationBridge
from mcoi_runtime.app.view_models import SimulationSummaryView
from mcoi_runtime.app.console import render_simulation_summary


def _make_clock() -> callable:
    """Return a clock that produces unique but deterministic timestamps."""
    counter = [0]

    def clock() -> str:
        counter[0] += 1
        return f"2026-03-20T12:00:{counter[0]:02d}+00:00"

    return clock


def _make_graph_and_engine() -> tuple[OperationalGraph, SimulationEngine]:
    clock = _make_clock()
    graph = OperationalGraph(clock=clock)
    engine = SimulationEngine(graph=graph, clock=clock)
    return graph, engine


# ---------------------------------------------------------------------------
# Scenario 1: Goal with two workflow options — lower-risk option recommended
# ---------------------------------------------------------------------------


class TestGoldenScenario1GoalWorkflowSelection:
    """Goal simulation: two workflow options, lower-risk is recommended."""

    def test_lower_risk_option_is_ranked_first(self) -> None:
        graph, engine = _make_graph_and_engine()
        graph.add_node("goal-s1", NodeType.GOAL, "Deploy new service")

        low = SimulationOption(
            option_id="wf-blue-green",
            label="Blue-green deployment",
            risk_level=RiskLevel.LOW,
            estimated_cost=200.0,
            estimated_duration_seconds=120.0,
            success_probability=0.92,
        )
        high = SimulationOption(
            option_id="wf-in-place",
            label="In-place deployment",
            risk_level=RiskLevel.MODERATE,
            estimated_cost=50.0,
            estimated_duration_seconds=30.0,
            success_probability=0.7,
        )

        comparison, verdict = SimulationBridge.simulate_before_goal(
            engine, graph, "goal-s1", [low, high],
        )

        assert comparison.ranked_option_ids[0] == "wf-blue-green"
        assert verdict.recommended_option_id == "wf-blue-green"
        assert verdict.verdict_type in (VerdictType.PROCEED, VerdictType.PROCEED_WITH_CAUTION)

    def test_scores_reflect_risk_difference(self) -> None:
        graph, engine = _make_graph_and_engine()
        graph.add_node("goal-s1b", NodeType.GOAL, "Score check")

        low = SimulationOption(
            option_id="opt-a",
            label="Low risk",
            risk_level=RiskLevel.LOW,
            estimated_cost=100.0,
            estimated_duration_seconds=60.0,
            success_probability=0.9,
        )
        high = SimulationOption(
            option_id="opt-b",
            label="High risk",
            risk_level=RiskLevel.HIGH,
            estimated_cost=100.0,
            estimated_duration_seconds=60.0,
            success_probability=0.9,
        )

        comparison, _ = SimulationBridge.simulate_before_goal(
            engine, graph, "goal-s1b", [low, high],
        )

        assert comparison.scores["opt-a"] > comparison.scores["opt-b"]

    def test_view_model_reflects_recommendation(self) -> None:
        graph, engine = _make_graph_and_engine()
        graph.add_node("goal-s1c", NodeType.GOAL, "View model scenario")

        options = [
            SimulationOption(
                option_id="opt-safe", label="Safe", risk_level=RiskLevel.MINIMAL,
                estimated_cost=10.0, estimated_duration_seconds=5.0, success_probability=0.99,
            ),
            SimulationOption(
                option_id="opt-risky", label="Risky", risk_level=RiskLevel.MODERATE,
                estimated_cost=500.0, estimated_duration_seconds=120.0, success_probability=0.7,
            ),
        ]
        comparison, verdict = SimulationBridge.simulate_before_goal(
            engine, graph, "goal-s1c", options,
        )
        view = SimulationSummaryView.from_result(comparison, verdict)

        assert view.recommended_option_id == "opt-safe"
        assert view.option_count == 2


# ---------------------------------------------------------------------------
# Scenario 2: Incident recovery — escalation for critical risk
# ---------------------------------------------------------------------------


class TestGoldenScenario2IncidentRecovery:
    """Incident recovery: critical risk triggers escalation."""

    def test_escalation_for_critical_risk(self) -> None:
        graph, engine = _make_graph_and_engine()
        graph.add_node("inc-s2", NodeType.INCIDENT, "Database corruption")

        restart = SimulationOption(
            option_id="recovery-restart",
            label="Restart from backup",
            risk_level=RiskLevel.CRITICAL,
            estimated_cost=8000.0,
            estimated_duration_seconds=3600.0,
            success_probability=0.4,
        )
        manual = SimulationOption(
            option_id="recovery-manual",
            label="Manual repair",
            risk_level=RiskLevel.HIGH,
            estimated_cost=5000.0,
            estimated_duration_seconds=7200.0,
            success_probability=0.6,
        )

        comparison, verdict = SimulationBridge.simulate_before_recovery(
            engine, graph, "inc-s2", [restart, manual],
        )

        assert verdict.verdict_type == VerdictType.ESCALATE
        assert comparison.top_risk_level == RiskLevel.CRITICAL

    def test_escalation_verdict_has_reasons(self) -> None:
        graph, engine = _make_graph_and_engine()
        graph.add_node("inc-s2b", NodeType.INCIDENT, "Service down")

        options = [
            SimulationOption(
                option_id="opt-crit", label="Critical path",
                risk_level=RiskLevel.CRITICAL,
                estimated_cost=9000.0, estimated_duration_seconds=600.0,
                success_probability=0.3,
            ),
        ]
        comparison, verdict = SimulationBridge.simulate_before_recovery(
            engine, graph, "inc-s2b", options,
        )

        assert len(verdict.reasons) > 0
        assert any("critical" in r.lower() or "escalat" in r.lower() for r in verdict.reasons)

    def test_recovery_with_connected_obligations(self) -> None:
        graph, engine = _make_graph_and_engine()
        graph.add_node("inc-s2c", NodeType.INCIDENT, "Outage")
        graph.add_node("sla-node", NodeType.JOB, "SLA obligation")
        graph.add_obligation("inc-s2c", "sla-node", "restore within SLA")

        options = [
            SimulationOption(
                option_id="opt-fast", label="Fast recovery",
                risk_level=RiskLevel.MODERATE,
                estimated_cost=3000.0, estimated_duration_seconds=300.0,
                success_probability=0.85,
            ),
        ]
        comparison, verdict = SimulationBridge.simulate_before_recovery(
            engine, graph, "inc-s2c", options,
        )

        assert isinstance(comparison, SimulationComparison)
        assert isinstance(verdict, SimulationVerdict)


# ---------------------------------------------------------------------------
# Scenario 3: Approval simulation — proceed for safe action
# ---------------------------------------------------------------------------


class TestGoldenScenario3ApprovalSimulation:
    """Approval simulation: proceed for safe action."""

    def test_proceed_for_safe_approval(self) -> None:
        graph, engine = _make_graph_and_engine()
        graph.add_node("act-s3", NodeType.APPROVAL, "Enable feature flag")

        approve = SimulationOption(
            option_id="opt-approve",
            label="Approve",
            risk_level=RiskLevel.MINIMAL,
            estimated_cost=0.0,
            estimated_duration_seconds=1.0,
            success_probability=1.0,
        )
        reject = SimulationOption(
            option_id="opt-reject",
            label="Reject",
            risk_level=RiskLevel.MINIMAL,
            estimated_cost=0.0,
            estimated_duration_seconds=1.0,
            success_probability=1.0,
        )
        escalate = SimulationOption(
            option_id="opt-escalate",
            label="Escalate to lead",
            risk_level=RiskLevel.LOW,
            estimated_cost=100.0,
            estimated_duration_seconds=3600.0,
            success_probability=0.9,
        )

        comparison, verdict = SimulationBridge.simulate_before_approval(
            engine, graph, "act-s3", [approve, reject, escalate],
        )

        assert verdict.verdict_type == VerdictType.PROCEED
        assert comparison.top_risk_level in (RiskLevel.MINIMAL, RiskLevel.LOW)

    def test_approval_three_options_all_ranked(self) -> None:
        graph, engine = _make_graph_and_engine()
        graph.add_node("act-s3b", NodeType.APPROVAL, "Config change")

        options = [
            SimulationOption(
                option_id="a", label="Approve", risk_level=RiskLevel.MINIMAL,
                estimated_cost=0.0, estimated_duration_seconds=0.0, success_probability=1.0,
            ),
            SimulationOption(
                option_id="r", label="Reject", risk_level=RiskLevel.MINIMAL,
                estimated_cost=0.0, estimated_duration_seconds=0.0, success_probability=0.95,
            ),
            SimulationOption(
                option_id="e", label="Escalate", risk_level=RiskLevel.MODERATE,
                estimated_cost=200.0, estimated_duration_seconds=600.0, success_probability=0.8,
            ),
        ]
        comparison, verdict = SimulationBridge.simulate_before_approval(
            engine, graph, "act-s3b", options,
        )

        assert len(comparison.ranked_option_ids) == 3
        assert set(comparison.ranked_option_ids) == {"a", "r", "e"}


# ---------------------------------------------------------------------------
# Scenario 4: Dense graph with many obligations — high review burden
# ---------------------------------------------------------------------------


class TestGoldenScenario4DenseGraph:
    """Dense graph: many obligations trigger high review burden."""

    def test_high_review_burden_detected(self) -> None:
        graph, engine = _make_graph_and_engine()
        graph.add_node("goal-s4", NodeType.GOAL, "Complex deployment")

        # Build a dense graph with many obligations
        for i in range(15):
            nid = f"dep-{i}"
            graph.add_node(nid, NodeType.JOB, f"Dependency {i}")
            graph.add_obligation("goal-s4", nid, f"obligation-{i}")

        options = [
            SimulationOption(
                option_id="opt-dense",
                label="Complex path",
                risk_level=RiskLevel.MODERATE,
                estimated_cost=1000.0,
                estimated_duration_seconds=300.0,
                success_probability=0.75,
            ),
        ]
        comparison, verdict = SimulationBridge.simulate_before_goal(
            engine, graph, "goal-s4", options,
        )

        # With 15 unfulfilled obligations and 1 option, review burden should be significant
        assert comparison.review_burden > 0.0
        # The verdict should reflect the burden/risk
        assert verdict.verdict_type in (
            VerdictType.PROCEED_WITH_CAUTION,
            VerdictType.APPROVAL_REQUIRED,
            VerdictType.ESCALATE,
        )

    def test_review_burden_increases_with_more_obligations(self) -> None:
        # Small graph
        graph1, engine1 = _make_graph_and_engine()
        graph1.add_node("g1", NodeType.GOAL, "Small")
        graph1.add_node("d1", NodeType.JOB, "Dep")
        graph1.add_obligation("g1", "d1", "single obligation")

        # Large graph
        graph2, engine2 = _make_graph_and_engine()
        graph2.add_node("g2", NodeType.GOAL, "Large")
        for i in range(20):
            nid = f"dep-{i}"
            graph2.add_node(nid, NodeType.JOB, f"Dep {i}")
            graph2.add_obligation("g2", nid, f"obligation-{i}")

        options = [
            SimulationOption(
                option_id="opt-x", label="Path",
                risk_level=RiskLevel.LOW,
                estimated_cost=100.0, estimated_duration_seconds=60.0,
                success_probability=0.9,
            ),
        ]

        c1, _ = SimulationBridge.simulate_before_goal(engine1, graph1, "g1", options)
        c2, _ = SimulationBridge.simulate_before_goal(engine2, graph2, "g2", options)

        assert c2.review_burden > c1.review_burden

    def test_view_model_shows_risk_for_dense_graph(self) -> None:
        graph, engine = _make_graph_and_engine()
        graph.add_node("goal-s4c", NodeType.GOAL, "Dense view")
        for i in range(10):
            nid = f"node-{i}"
            graph.add_node(nid, NodeType.JOB, f"Job {i}")
            graph.add_obligation("goal-s4c", nid, f"obligation-{i}")

        options = [
            SimulationOption(
                option_id="opt-y", label="Path",
                risk_level=RiskLevel.HIGH,
                estimated_cost=5000.0, estimated_duration_seconds=600.0,
                success_probability=0.5,
            ),
        ]
        comparison, verdict = SimulationBridge.simulate_before_goal(
            engine, graph, "goal-s4c", options,
        )
        view = SimulationSummaryView.from_result(comparison, verdict)

        assert view.top_risk_level == "high"


# ---------------------------------------------------------------------------
# Scenario 5: Empty graph simulation — minimal risk, proceed
# ---------------------------------------------------------------------------


class TestGoldenScenario5EmptyGraph:
    """Empty graph: minimal risk, proceed verdict."""

    def test_empty_graph_proceed(self) -> None:
        graph, engine = _make_graph_and_engine()
        # No nodes in graph; context_id won't be found

        options = [
            SimulationOption(
                option_id="opt-empty",
                label="Simple action",
                risk_level=RiskLevel.MINIMAL,
                estimated_cost=0.0,
                estimated_duration_seconds=5.0,
                success_probability=0.99,
            ),
        ]
        comparison, verdict = SimulationBridge.simulate_before_goal(
            engine, graph, "nonexistent-goal", options,
        )

        assert verdict.verdict_type == VerdictType.PROCEED
        assert verdict.confidence > 0.9
        assert comparison.top_risk_level == RiskLevel.MINIMAL

    def test_empty_graph_low_review_burden(self) -> None:
        graph, engine = _make_graph_and_engine()

        options = [
            SimulationOption(
                option_id="opt-trivial",
                label="Trivial",
                risk_level=RiskLevel.MINIMAL,
                estimated_cost=0.0,
                estimated_duration_seconds=1.0,
                success_probability=1.0,
            ),
        ]
        comparison, _ = SimulationBridge.simulate_before_goal(
            engine, graph, "missing", options,
        )

        assert comparison.review_burden < 0.2

    def test_empty_graph_render(self) -> None:
        graph, engine = _make_graph_and_engine()
        options = [
            SimulationOption(
                option_id="opt-render-empty",
                label="Render test",
                risk_level=RiskLevel.MINIMAL,
                estimated_cost=0.0,
                estimated_duration_seconds=1.0,
                success_probability=1.0,
            ),
        ]
        comparison, verdict = SimulationBridge.simulate_before_goal(
            engine, graph, "no-goal", options,
        )
        view = SimulationSummaryView.from_result(comparison, verdict)
        output = render_simulation_summary(view)

        assert "proceed" in output.lower()
        assert "minimal" in output.lower()


# ---------------------------------------------------------------------------
# Scenario 6: Single option simulation — deterministic verdict
# ---------------------------------------------------------------------------


class TestGoldenScenario6SingleOption:
    """Single option: deterministic verdict."""

    def test_single_option_deterministic(self) -> None:
        graph, engine = _make_graph_and_engine()
        graph.add_node("goal-s6", NodeType.GOAL, "Single path")

        option = SimulationOption(
            option_id="only-option",
            label="The only way",
            risk_level=RiskLevel.LOW,
            estimated_cost=500.0,
            estimated_duration_seconds=120.0,
            success_probability=0.88,
        )
        comparison, verdict = SimulationBridge.simulate_before_goal(
            engine, graph, "goal-s6", [option],
        )

        assert len(comparison.ranked_option_ids) == 1
        assert comparison.ranked_option_ids[0] == "only-option"
        assert verdict.recommended_option_id == "only-option"

    def test_single_option_repeated_is_identical(self) -> None:
        """Running the same single-option simulation twice yields same verdict type."""
        option = SimulationOption(
            option_id="sole-opt",
            label="Sole path",
            risk_level=RiskLevel.LOW,
            estimated_cost=200.0,
            estimated_duration_seconds=60.0,
            success_probability=0.9,
        )

        graph1, engine1 = _make_graph_and_engine()
        graph1.add_node("g-rep", NodeType.GOAL, "Repeat")
        _, v1 = SimulationBridge.simulate_before_goal(engine1, graph1, "g-rep", [option])

        graph2, engine2 = _make_graph_and_engine()
        graph2.add_node("g-rep", NodeType.GOAL, "Repeat")
        _, v2 = SimulationBridge.simulate_before_goal(engine2, graph2, "g-rep", [option])

        assert v1.verdict_type == v2.verdict_type
        assert v1.recommended_option_id == v2.recommended_option_id
        assert v1.confidence == v2.confidence

    def test_single_safe_option_always_proceed(self) -> None:
        graph, engine = _make_graph_and_engine()

        option = SimulationOption(
            option_id="safe-single",
            label="Safe action",
            risk_level=RiskLevel.MINIMAL,
            estimated_cost=0.0,
            estimated_duration_seconds=1.0,
            success_probability=1.0,
        )
        _, verdict = SimulationBridge.simulate_before_goal(
            engine, graph, "any-goal", [option],
        )

        assert verdict.verdict_type == VerdictType.PROCEED

    def test_single_critical_option_always_escalate(self) -> None:
        graph, engine = _make_graph_and_engine()

        option = SimulationOption(
            option_id="crit-single",
            label="Critical action",
            risk_level=RiskLevel.CRITICAL,
            estimated_cost=9999.0,
            estimated_duration_seconds=9999.0,
            success_probability=0.1,
        )
        _, verdict = SimulationBridge.simulate_before_goal(
            engine, graph, "any-goal", [option],
        )

        assert verdict.verdict_type == VerdictType.ESCALATE
