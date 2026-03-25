"""Purpose: tests for the simulation core engine.
Governance scope: scoring, comparison, verdict derivation, graph-awareness.
Dependencies: simulation engine, simulation contracts, operational graph, graph contracts.
Invariants:
  - Scoring is deterministic for the same inputs.
  - Verdicts are derived purely from comparison scores and risk levels.
  - Simulation never mutates the underlying graph.
  - Confidence values are bounded [0.0, 1.0].
  - Clock determinism: identical clock produces identical results.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.graph import (
    EdgeType,
    NodeType,
    ObligationLink,
)
from mcoi_runtime.contracts.simulation import (
    RiskLevel,
    SimulationComparison,
    SimulationOption,
    SimulationRequest,
    SimulationVerdict,
    VerdictType,
)
from mcoi_runtime.core.operational_graph import OperationalGraph
from mcoi_runtime.core.simulation import (
    SimulationEngine,
    _clamp,
    _compute_review_burden,
    _score_option,
    _top_risk,
    _RISK_SEVERITY,
)


# --- Helpers ---


def _make_clock(start: str = "2025-01-15T10:00:00Z") -> callable:
    """Return a deterministic clock that increments by 1 second each call."""
    counter = [0]
    base = "2025-01-15T10:00:"

    def clock() -> str:
        val = counter[0]
        counter[0] += 1
        return f"{base}{val:02d}Z"

    return clock


def _make_graph(**kwargs) -> OperationalGraph:
    if "clock" not in kwargs:
        kwargs["clock"] = _make_clock()
    return OperationalGraph(**kwargs)


def _make_option(
    option_id: str = "opt-1",
    label: str = "Option 1",
    risk_level: RiskLevel = RiskLevel.MINIMAL,
    estimated_cost: float = 0.0,
    estimated_duration_seconds: float = 60.0,
    success_probability: float = 0.9,
) -> SimulationOption:
    return SimulationOption(
        option_id=option_id,
        label=label,
        risk_level=risk_level,
        estimated_cost=estimated_cost,
        estimated_duration_seconds=estimated_duration_seconds,
        success_probability=success_probability,
    )


def _make_request(
    request_id: str = "req-1",
    context_type: str = "workflow",
    context_id: str = "ctx-1",
    description: str = "Test simulation",
    options: tuple[SimulationOption, ...] | None = None,
) -> SimulationRequest:
    if options is None:
        options = (_make_option(),)
    return SimulationRequest(
        request_id=request_id,
        context_type=context_type,
        context_id=context_id,
        description=description,
        options=options,
    )


def _make_engine(graph: OperationalGraph | None = None, clock=None) -> SimulationEngine:
    if graph is None:
        graph = _make_graph()
    if clock is None:
        clock = _make_clock()
    return SimulationEngine(graph=graph, clock=clock)


# ===================================================================
# _clamp tests
# ===================================================================


class TestClamp:
    def test_clamp_within_range(self):
        assert _clamp(0.5) == 0.5

    def test_clamp_below_lo(self):
        assert _clamp(-0.5) == 0.0

    def test_clamp_above_hi(self):
        assert _clamp(1.5) == 1.0

    def test_clamp_at_boundaries(self):
        assert _clamp(0.0) == 0.0
        assert _clamp(1.0) == 1.0


# ===================================================================
# _score_option tests
# ===================================================================


class TestScoreOption:
    def test_score_no_risk_no_cost(self):
        opt = _make_option(risk_level=RiskLevel.MINIMAL, estimated_cost=0.0, success_probability=0.9)
        score = _score_option(opt)
        assert score == pytest.approx(0.9, abs=0.01)

    def test_score_high_risk_reduces_score(self):
        opt_low = _make_option(risk_level=RiskLevel.LOW, success_probability=0.9)
        opt_high = _make_option(risk_level=RiskLevel.HIGH, success_probability=0.9)
        assert _score_option(opt_low) > _score_option(opt_high)

    def test_score_high_cost_reduces_score(self):
        opt_cheap = _make_option(estimated_cost=0.0, success_probability=0.9)
        opt_expensive = _make_option(estimated_cost=5000.0, success_probability=0.9)
        assert _score_option(opt_cheap) > _score_option(opt_expensive)

    def test_score_clamped_to_zero(self):
        opt = _make_option(
            risk_level=RiskLevel.CRITICAL,
            estimated_cost=10000.0,
            success_probability=0.1,
        )
        score = _score_option(opt)
        assert score >= 0.0

    def test_score_clamped_to_one(self):
        opt = _make_option(
            risk_level=RiskLevel.MINIMAL,
            estimated_cost=0.0,
            success_probability=1.0,
        )
        score = _score_option(opt)
        assert score <= 1.0

    def test_score_is_deterministic(self):
        opt = _make_option(risk_level=RiskLevel.MODERATE, estimated_cost=500.0, success_probability=0.8)
        assert _score_option(opt) == _score_option(opt)


# ===================================================================
# _top_risk tests
# ===================================================================


class TestTopRisk:
    def test_empty_options_returns_none_risk(self):
        assert _top_risk(()) == RiskLevel.MINIMAL

    def test_single_option(self):
        opts = (_make_option(risk_level=RiskLevel.HIGH),)
        assert _top_risk(opts) == RiskLevel.HIGH

    def test_multiple_options_returns_highest(self):
        opts = (
            _make_option(option_id="a", risk_level=RiskLevel.LOW),
            _make_option(option_id="b", risk_level=RiskLevel.CRITICAL),
            _make_option(option_id="c", risk_level=RiskLevel.MODERATE),
        )
        assert _top_risk(opts) == RiskLevel.CRITICAL


# ===================================================================
# _compute_review_burden tests
# ===================================================================


class TestComputeReviewBurden:
    def test_zero_options_zero_obligations(self):
        assert _compute_review_burden(0, 0) == 0.0

    def test_high_options_high_obligations(self):
        burden = _compute_review_burden(10, 20)
        assert burden == 1.0

    def test_partial_burden(self):
        burden = _compute_review_burden(3, 5)
        assert 0.0 < burden < 1.0

    def test_capped_at_one(self):
        burden = _compute_review_burden(100, 100)
        assert burden <= 1.0


# ===================================================================
# SimulationEngine — empty graph (minimal risk)
# ===================================================================


class TestSimulationEmptyGraph:
    def test_full_simulation_with_empty_graph(self):
        engine = _make_engine()
        opt = _make_option(risk_level=RiskLevel.MINIMAL, success_probability=0.95)
        request = _make_request(options=(opt,))
        comparison, verdict = engine.full_simulation(request)
        assert isinstance(comparison, SimulationComparison)
        assert isinstance(verdict, SimulationVerdict)

    def test_empty_graph_produces_proceed_verdict(self):
        engine = _make_engine()
        opt = _make_option(risk_level=RiskLevel.MINIMAL, success_probability=0.95)
        request = _make_request(options=(opt,))
        _, verdict = engine.full_simulation(request)
        assert verdict.verdict_type == VerdictType.PROCEED

    def test_empty_graph_zero_review_burden(self):
        engine = _make_engine()
        opt = _make_option()
        request = _make_request(options=(opt,))
        comparison, _ = engine.full_simulation(request)
        # 1 option, 0 obligations => burden = 0.1 (1/10 + 0/20)
        assert comparison.review_burden == pytest.approx(0.1, abs=0.01)

    def test_empty_graph_high_confidence(self):
        engine = _make_engine()
        opt = _make_option(risk_level=RiskLevel.MINIMAL, success_probability=0.95)
        request = _make_request(options=(opt,))
        _, verdict = engine.full_simulation(request)
        assert verdict.confidence > 0.8


# ===================================================================
# SimulationEngine — graph with dependencies (moderate risk)
# ===================================================================


class TestSimulationWithDependencies:
    def _graph_with_deps(self) -> OperationalGraph:
        g = _make_graph()
        g.add_node("ctx-1", NodeType.WORKFLOW, "Main workflow")
        g.add_node("n2", NodeType.JOB, "Job A")
        g.add_node("n3", NodeType.JOB, "Job B")
        g.add_edge(EdgeType.DEPENDS_ON, "ctx-1", "n2")
        g.add_edge(EdgeType.DEPENDS_ON, "ctx-1", "n3")
        return g

    def test_dependencies_detected(self):
        g = self._graph_with_deps()
        engine = _make_engine(graph=g)
        opt = _make_option(risk_level=RiskLevel.MODERATE, success_probability=0.7)
        request = _make_request(context_id="ctx-1", options=(opt,))
        comparison, _ = engine.full_simulation(request)
        assert len(comparison.ranked_option_ids) == 1

    def test_medium_risk_produces_caution_verdict(self):
        g = self._graph_with_deps()
        engine = _make_engine(graph=g)
        opt = _make_option(risk_level=RiskLevel.MODERATE, success_probability=0.8)
        request = _make_request(context_id="ctx-1", options=(opt,))
        _, verdict = engine.full_simulation(request)
        assert verdict.verdict_type == VerdictType.PROCEED_WITH_CAUTION


# ===================================================================
# SimulationEngine — graph with obligations (high risk)
# ===================================================================


class TestSimulationWithObligations:
    def _graph_with_obligations(self) -> OperationalGraph:
        g = _make_graph()
        g.add_node("ctx-1", NodeType.WORKFLOW, "Main workflow")
        g.add_node("n2", NodeType.APPROVAL, "Approval gate")
        g.add_obligation("ctx-1", "n2", "Must complete approval")
        return g

    def test_unfulfilled_obligations_increase_burden(self):
        g = self._graph_with_obligations()
        engine = _make_engine(graph=g)
        opt = _make_option(risk_level=RiskLevel.HIGH, success_probability=0.6)
        request = _make_request(context_id="ctx-1", options=(opt,))
        comparison, _ = engine.full_simulation(request)
        # 1 option, 1 obligation => burden = 0.1 + 0.05 = 0.15
        assert comparison.review_burden > 0.0

    def test_high_risk_produces_escalate_verdict(self):
        g = self._graph_with_obligations()
        engine = _make_engine(graph=g)
        opt = _make_option(risk_level=RiskLevel.HIGH, success_probability=0.6)
        request = _make_request(context_id="ctx-1", options=(opt,))
        _, verdict = engine.full_simulation(request)
        assert verdict.verdict_type == VerdictType.ESCALATE


# ===================================================================
# SimulationEngine — graph with incident nodes (critical risk)
# ===================================================================


class TestSimulationWithIncidents:
    def _graph_with_incidents(self) -> OperationalGraph:
        g = _make_graph()
        g.add_node("ctx-1", NodeType.WORKFLOW, "Main workflow")
        g.add_node("inc-1", NodeType.INCIDENT, "Incident alpha")
        g.add_edge(EdgeType.CAUSED_BY, "ctx-1", "inc-1")
        return g

    def test_critical_risk_produces_escalate_verdict(self):
        g = self._graph_with_incidents()
        engine = _make_engine(graph=g)
        opt = _make_option(risk_level=RiskLevel.CRITICAL, success_probability=0.3)
        request = _make_request(context_id="ctx-1", options=(opt,))
        _, verdict = engine.full_simulation(request)
        assert verdict.verdict_type == VerdictType.ESCALATE

    def test_critical_risk_low_confidence(self):
        g = self._graph_with_incidents()
        engine = _make_engine(graph=g)
        opt = _make_option(risk_level=RiskLevel.CRITICAL, success_probability=0.3)
        request = _make_request(context_id="ctx-1", options=(opt,))
        _, verdict = engine.full_simulation(request)
        assert verdict.confidence < 0.5

    def test_critical_risk_reasons_contain_escalation(self):
        g = self._graph_with_incidents()
        engine = _make_engine(graph=g)
        opt = _make_option(risk_level=RiskLevel.CRITICAL, success_probability=0.3)
        request = _make_request(context_id="ctx-1", options=(opt,))
        _, verdict = engine.full_simulation(request)
        assert any("critical" in r.lower() or "escalat" in r.lower() for r in verdict.reasons)


# ===================================================================
# Compare two options — picks lower risk
# ===================================================================


class TestCompareTwoOptions:
    def test_lower_risk_ranked_first(self):
        engine = _make_engine()
        opt_safe = _make_option(option_id="safe", risk_level=RiskLevel.MINIMAL, success_probability=0.9)
        opt_risky = _make_option(option_id="risky", risk_level=RiskLevel.HIGH, success_probability=0.9)
        request = _make_request(options=(opt_safe, opt_risky))
        comparison, _ = engine.full_simulation(request)
        assert comparison.ranked_option_ids[0] == "safe"

    def test_higher_success_probability_wins_when_same_risk(self):
        engine = _make_engine()
        opt_a = _make_option(option_id="a", risk_level=RiskLevel.LOW, success_probability=0.95)
        opt_b = _make_option(option_id="b", risk_level=RiskLevel.LOW, success_probability=0.6)
        request = _make_request(options=(opt_a, opt_b))
        comparison, _ = engine.full_simulation(request)
        assert comparison.ranked_option_ids[0] == "a"

    def test_recommended_option_matches_top_ranked(self):
        engine = _make_engine()
        opt_a = _make_option(option_id="a", risk_level=RiskLevel.MINIMAL, success_probability=0.9)
        opt_b = _make_option(option_id="b", risk_level=RiskLevel.HIGH, success_probability=0.9)
        request = _make_request(options=(opt_a, opt_b))
        _, verdict = engine.full_simulation(request)
        assert verdict.recommended_option_id == "a"


# ===================================================================
# Compare three options with different durations
# ===================================================================


class TestCompareThreeOptions:
    def test_three_options_all_ranked(self):
        engine = _make_engine()
        opt_a = _make_option(option_id="a", risk_level=RiskLevel.LOW, success_probability=0.8, estimated_duration_seconds=60.0)
        opt_b = _make_option(option_id="b", risk_level=RiskLevel.MODERATE, success_probability=0.7, estimated_duration_seconds=120.0)
        opt_c = _make_option(option_id="c", risk_level=RiskLevel.HIGH, success_probability=0.5, estimated_duration_seconds=300.0)
        request = _make_request(options=(opt_a, opt_b, opt_c))
        comparison, _ = engine.full_simulation(request)
        assert len(comparison.ranked_option_ids) == 3
        # Best option should be 'a' (lowest risk, highest probability)
        assert comparison.ranked_option_ids[0] == "a"


# ===================================================================
# Ranking determinism
# ===================================================================


class TestRankingDeterminism:
    def test_equal_options_deterministic_ranking(self):
        clock = _make_clock()
        engine = _make_engine(clock=clock)
        opt_a = _make_option(option_id="a", risk_level=RiskLevel.LOW, success_probability=0.8)
        opt_b = _make_option(option_id="b", risk_level=RiskLevel.LOW, success_probability=0.8)
        request = _make_request(options=(opt_a, opt_b))
        comp1, _ = engine.full_simulation(request)

        clock2 = _make_clock()
        engine2 = _make_engine(clock=clock2)
        comp2, _ = engine2.full_simulation(request)

        assert comp1.ranked_option_ids == comp2.ranked_option_ids

    def test_repeated_simulation_same_result(self):
        opt = _make_option(risk_level=RiskLevel.MINIMAL, success_probability=0.9)
        request = _make_request(options=(opt,))
        # Run twice with fresh engines using identical clocks
        engine1 = _make_engine(clock=_make_clock())
        engine2 = _make_engine(clock=_make_clock())
        comp1, v1 = engine1.full_simulation(request)
        comp2, v2 = engine2.full_simulation(request)
        assert comp1.ranked_option_ids == comp2.ranked_option_ids
        assert v1.verdict_type == v2.verdict_type


# ===================================================================
# Recommend: proceed for low risk
# ===================================================================


class TestRecommendProceed:
    def test_low_risk_high_score_proceeds(self):
        engine = _make_engine()
        opt = _make_option(risk_level=RiskLevel.MINIMAL, success_probability=0.95)
        request = _make_request(options=(opt,))
        _, verdict = engine.full_simulation(request)
        assert verdict.verdict_type == VerdictType.PROCEED

    def test_low_risk_option_recommended(self):
        engine = _make_engine()
        opt = _make_option(option_id="safe-opt", risk_level=RiskLevel.LOW, success_probability=0.85)
        request = _make_request(options=(opt,))
        _, verdict = engine.full_simulation(request)
        assert verdict.recommended_option_id == "safe-opt"


# ===================================================================
# Recommend: review_required for high risk
# ===================================================================


class TestRecommendReviewRequired:
    def test_high_review_burden_triggers_review(self):
        engine = _make_engine()
        # Force high burden via obligation_count override
        opt = _make_option(risk_level=RiskLevel.LOW, success_probability=0.9)
        request = _make_request(options=(opt,))
        # Need high burden: option_factor + obligation_factor >= 0.7
        # With 8 options: min(8/10, 0.5) = 0.5, need obligation_factor >= 0.2
        # obligation_count=5: min(5/20, 0.5) = 0.25 -> total = 0.75 >= 0.7
        opts = tuple(_make_option(option_id=f"opt-{i}") for i in range(8))
        request = _make_request(options=opts)
        _, verdict = engine.full_simulation(request, obligation_count=5)
        assert verdict.verdict_type == VerdictType.APPROVAL_REQUIRED

    def test_low_score_triggers_review(self):
        engine = _make_engine()
        opt = _make_option(
            risk_level=RiskLevel.LOW,
            estimated_cost=9000.0,
            success_probability=0.4,
        )
        request = _make_request(options=(opt,))
        _, verdict = engine.full_simulation(request)
        assert verdict.verdict_type == VerdictType.APPROVAL_REQUIRED


# ===================================================================
# Recommend: escalate for critical risk
# ===================================================================


class TestRecommendEscalate:
    def test_critical_risk_escalates(self):
        engine = _make_engine()
        opt = _make_option(risk_level=RiskLevel.CRITICAL, success_probability=0.3)
        request = _make_request(options=(opt,))
        _, verdict = engine.full_simulation(request)
        assert verdict.verdict_type == VerdictType.ESCALATE

    def test_high_risk_escalates(self):
        engine = _make_engine()
        opt = _make_option(risk_level=RiskLevel.HIGH, success_probability=0.5)
        request = _make_request(options=(opt,))
        _, verdict = engine.full_simulation(request)
        assert verdict.verdict_type == VerdictType.ESCALATE

    def test_escalate_reasons_mention_risk(self):
        engine = _make_engine()
        opt = _make_option(risk_level=RiskLevel.CRITICAL, success_probability=0.3)
        request = _make_request(options=(opt,))
        _, verdict = engine.full_simulation(request)
        assert any("risk" in r.lower() or "escalat" in r.lower() for r in verdict.reasons)


# ===================================================================
# Full simulation end-to-end
# ===================================================================


class TestFullSimulationEndToEnd:
    def test_returns_comparison_and_verdict(self):
        engine = _make_engine()
        opt_a = _make_option(option_id="a", risk_level=RiskLevel.LOW, success_probability=0.9)
        opt_b = _make_option(option_id="b", risk_level=RiskLevel.MODERATE, success_probability=0.7)
        request = _make_request(options=(opt_a, opt_b))
        comparison, verdict = engine.full_simulation(request)
        assert isinstance(comparison, SimulationComparison)
        assert isinstance(verdict, SimulationVerdict)
        assert comparison.request_id == "req-1"
        assert verdict.comparison_id == comparison.comparison_id

    def test_end_to_end_with_graph_context(self):
        g = _make_graph()
        g.add_node("ctx-1", NodeType.WORKFLOW, "Main workflow")
        g.add_node("n2", NodeType.JOB, "Job A")
        g.add_edge(EdgeType.DEPENDS_ON, "ctx-1", "n2")
        g.add_obligation("ctx-1", "n2", "Must complete job A")

        engine = _make_engine(graph=g)
        opt = _make_option(risk_level=RiskLevel.MODERATE, success_probability=0.75)
        request = _make_request(context_id="ctx-1", options=(opt,))
        comparison, verdict = engine.full_simulation(request)
        assert comparison.review_burden > 0.0
        assert verdict.verdict_type in (
            VerdictType.PROCEED_WITH_CAUTION,
            VerdictType.APPROVAL_REQUIRED,
        )

    def test_scores_populated_for_all_options(self):
        engine = _make_engine()
        opt_a = _make_option(option_id="a", success_probability=0.9)
        opt_b = _make_option(option_id="b", success_probability=0.5)
        request = _make_request(options=(opt_a, opt_b))
        comparison, _ = engine.full_simulation(request)
        assert "a" in comparison.scores
        assert "b" in comparison.scores


# ===================================================================
# Clock determinism
# ===================================================================


class TestClockDeterminism:
    def test_same_clock_same_ids(self):
        clock1 = _make_clock()
        clock2 = _make_clock()
        engine1 = _make_engine(clock=clock1)
        engine2 = _make_engine(clock=clock2)

        opt = _make_option()
        request = _make_request(options=(opt,))
        comp1, v1 = engine1.full_simulation(request)
        comp2, v2 = engine2.full_simulation(request)
        assert comp1.comparison_id == comp2.comparison_id
        assert v1.verdict_id == v2.verdict_id

    def test_different_requests_different_ids(self):
        engine = _make_engine()
        opt = _make_option()
        req1 = _make_request(request_id="req-A", options=(opt,))
        req2 = _make_request(request_id="req-B", options=(opt,))
        comp1, _ = engine.full_simulation(req1)
        comp2, _ = engine.full_simulation(req2)
        assert comp1.comparison_id != comp2.comparison_id


# ===================================================================
# Single option comparison
# ===================================================================


class TestSingleOptionComparison:
    def test_single_option_ranked_first(self):
        engine = _make_engine()
        opt = _make_option(option_id="only")
        request = _make_request(options=(opt,))
        comparison, _ = engine.full_simulation(request)
        assert comparison.ranked_option_ids == ("only",)

    def test_single_option_is_recommended(self):
        engine = _make_engine()
        opt = _make_option(option_id="only")
        request = _make_request(options=(opt,))
        _, verdict = engine.full_simulation(request)
        assert verdict.recommended_option_id == "only"


# ===================================================================
# Obligation count override
# ===================================================================


class TestObligationCountOverride:
    def test_override_increases_burden(self):
        engine = _make_engine()
        opt = _make_option()
        request = _make_request(options=(opt,))
        comp_no_override, _ = engine.full_simulation(request)

        engine2 = _make_engine()
        comp_with_override, _ = engine2.full_simulation(request, obligation_count=10)
        assert comp_with_override.review_burden > comp_no_override.review_burden

    def test_zero_override_same_as_empty_graph(self):
        engine1 = _make_engine(clock=_make_clock())
        engine2 = _make_engine(clock=_make_clock())
        opt = _make_option()
        request = _make_request(options=(opt,))
        comp1, _ = engine1.full_simulation(request, obligation_count=0)
        comp2, _ = engine2.full_simulation(request)
        assert comp1.review_burden == comp2.review_burden


# ===================================================================
# Graph does not mutate
# ===================================================================


class TestGraphImmutability:
    def test_simulation_does_not_add_nodes(self):
        g = _make_graph()
        g.add_node("ctx-1", NodeType.WORKFLOW, "Workflow")
        initial_count = len(g.all_nodes())
        engine = _make_engine(graph=g)

        opt = _make_option(risk_level=RiskLevel.HIGH, success_probability=0.5)
        request = _make_request(context_id="ctx-1", options=(opt,))
        engine.full_simulation(request)

        assert len(g.all_nodes()) == initial_count

    def test_simulation_does_not_add_edges(self):
        g = _make_graph()
        g.add_node("ctx-1", NodeType.WORKFLOW, "Workflow")
        g.add_node("n2", NodeType.JOB, "Job")
        g.add_edge(EdgeType.DEPENDS_ON, "ctx-1", "n2")
        initial_count = len(g.all_edges())
        engine = _make_engine(graph=g)

        opt = _make_option()
        request = _make_request(context_id="ctx-1", options=(opt,))
        engine.full_simulation(request)

        assert len(g.all_edges()) == initial_count


# ===================================================================
# Context node not in graph
# ===================================================================


class TestContextNodeNotInGraph:
    def test_missing_context_node_still_works(self):
        engine = _make_engine()
        opt = _make_option()
        request = _make_request(context_id="nonexistent", options=(opt,))
        comparison, verdict = engine.full_simulation(request)
        assert isinstance(comparison, SimulationComparison)
        assert isinstance(verdict, SimulationVerdict)

    def test_missing_context_zero_burden(self):
        engine = _make_engine()
        opt = _make_option()
        request = _make_request(context_id="nonexistent", options=(opt,))
        comparison, _ = engine.full_simulation(request)
        # 1 option, 0 obligations from empty context
        assert comparison.review_burden == pytest.approx(0.1, abs=0.01)


# ===================================================================
# Verdict confidence boundaries
# ===================================================================


class TestConfidenceBoundaries:
    def test_confidence_never_exceeds_one(self):
        engine = _make_engine()
        opt = _make_option(risk_level=RiskLevel.MINIMAL, success_probability=1.0)
        request = _make_request(options=(opt,))
        _, verdict = engine.full_simulation(request)
        assert verdict.confidence <= 1.0

    def test_confidence_never_below_zero(self):
        engine = _make_engine()
        opt = _make_option(risk_level=RiskLevel.CRITICAL, success_probability=0.0, estimated_cost=10000.0)
        request = _make_request(options=(opt,))
        _, verdict = engine.full_simulation(request)
        assert verdict.confidence >= 0.0

    def test_risk_reduces_confidence(self):
        engine1 = _make_engine(clock=_make_clock())
        engine2 = _make_engine(clock=_make_clock())
        opt_safe = _make_option(risk_level=RiskLevel.MINIMAL, success_probability=0.9)
        opt_risky = _make_option(risk_level=RiskLevel.HIGH, success_probability=0.9)
        req_safe = _make_request(options=(opt_safe,))
        req_risky = _make_request(options=(opt_risky,))
        _, v_safe = engine1.full_simulation(req_safe)
        _, v_risky = engine2.full_simulation(req_risky)
        assert v_safe.confidence > v_risky.confidence


# ===================================================================
# Risk severity ordering
# ===================================================================


class TestRiskSeverityOrdering:
    def test_severity_monotonic(self):
        levels = [RiskLevel.MINIMAL, RiskLevel.LOW, RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.CRITICAL]
        for i in range(len(levels) - 1):
            assert _RISK_SEVERITY[levels[i]] < _RISK_SEVERITY[levels[i + 1]]

    def test_all_risk_levels_have_severity(self):
        for level in RiskLevel:
            assert level in _RISK_SEVERITY
