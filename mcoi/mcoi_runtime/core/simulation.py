"""Purpose: simulation engine — compares options, scores them, and produces verdicts.
Governance scope: graph-based simulation logic only. No execution, no network, no mutation.
Dependencies: simulation contracts, operational graph, core invariants.
Invariants:
  - Scoring is deterministic for the same inputs.
  - Verdicts are derived purely from comparison scores and risk levels.
  - Simulation never mutates the underlying graph.
  - Confidence values are bounded [0.0, 1.0].
  - No side effects. No IO.
"""

from __future__ import annotations

from typing import Callable

from mcoi_runtime.contracts.simulation import (
    RiskLevel,
    SimulationComparison,
    SimulationOption,
    SimulationRequest,
    SimulationVerdict,
    VerdictType,
)
from .invariants import stable_identifier
from .operational_graph import OperationalGraph


# Ordered risk levels for comparison (index = severity)
_RISK_SEVERITY: dict[RiskLevel, int] = {
    RiskLevel.MINIMAL: 0,
    RiskLevel.LOW: 1,
    RiskLevel.MODERATE: 2,
    RiskLevel.HIGH: 3,
    RiskLevel.CRITICAL: 4,
}

# Threshold constants
_HIGH_REVIEW_BURDEN = 0.7


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _score_option(option: SimulationOption) -> float:
    """Score an option based on success probability, cost, and risk.

    Higher score = better option.
    """
    risk_penalty = _RISK_SEVERITY.get(option.risk_level, 0) * 0.15
    cost_penalty = min(option.estimated_cost / 10000.0, 0.3)
    score = option.success_probability - risk_penalty - cost_penalty
    return _clamp(score)


def _top_risk(options: tuple[SimulationOption, ...]) -> RiskLevel:
    """Return the highest risk level among options."""
    if not options:
        return RiskLevel.MINIMAL
    return max(options, key=lambda o: _RISK_SEVERITY.get(o.risk_level, 0)).risk_level


def _compute_review_burden(
    option_count: int,
    obligation_count: int,
) -> float:
    """Compute review burden from number of options and obligations.

    Returns a value in [0.0, 1.0].
    """
    option_factor = min(option_count / 10.0, 0.5)
    obligation_factor = min(obligation_count / 20.0, 0.5)
    return min(1.0, option_factor + obligation_factor)


class SimulationEngine:
    """Graph-aware simulation engine for action risk analysis and recommendation.

    Analyzes the current operational graph to score options, compare them,
    and produce recommendation verdicts.  Never mutates the graph.
    """

    def __init__(self, *, graph: OperationalGraph, clock: Callable[[], str]) -> None:
        self._graph = graph
        self._clock = clock

    # ------------------------------------------------------------------
    # Graph analysis helpers
    # ------------------------------------------------------------------

    def _count_unfulfilled_obligations(self, context_node_ids: list[str]) -> int:
        """Count unfulfilled obligations touching any of the given nodes."""
        seen: set[str] = set()
        count = 0
        for nid in context_node_ids:
            for obl in self._graph.find_obligations(nid, fulfilled=False):
                if obl.edge_id not in seen:
                    seen.add(obl.edge_id)
                    count += 1
        return count

    def _collect_context_node_ids(self, context_id: str) -> list[str]:
        """Collect context node and its immediate connected node IDs."""
        node = self._graph.get_node(context_id)
        if node is None:
            return []
        result = [context_id]
        for neighbor_id in self._graph.get_neighbors(context_id):
            result.append(neighbor_id)
        return result

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def full_simulation(
        self,
        request: SimulationRequest,
        *,
        obligation_count: int | None = None,
    ) -> tuple[SimulationComparison, SimulationVerdict]:
        """Run a full simulation: score, compare, and verdict.

        Args:
            request: The simulation request with options to compare.
            obligation_count: Override for obligation count. If None,
                count is derived from the graph using context_id.

        Returns:
            A tuple of (comparison, verdict).
        """
        # Defensive: require at least one option
        if not request.options:
            raise ValueError("simulation requires at least one option")

        # Derive obligation count from graph if not provided
        if obligation_count is None:
            context_nodes = self._collect_context_node_ids(request.context_id)
            obligation_count = self._count_unfulfilled_obligations(context_nodes)

        # Score each option
        scores: dict[str, float] = {}
        for option in request.options:
            scores[option.option_id] = _score_option(option)

        ranked_ids = sorted(scores, key=lambda oid: (-scores[oid], oid))
        top_risk = _top_risk(request.options)
        review_burden = _compute_review_burden(len(request.options), obligation_count)

        now = self._clock()
        comparison_id = stable_identifier("sim-cmp", {
            "request_id": request.request_id,
            "option_count": str(len(request.options)),
            "created_at": now,
        })
        comparison = SimulationComparison(
            comparison_id=comparison_id,
            request_id=request.request_id,
            ranked_option_ids=tuple(ranked_ids),
            scores=scores,
            top_risk_level=top_risk,
            review_burden=review_burden,
        )

        verdict = self._derive_verdict(comparison, scores, top_risk, review_burden)
        return comparison, verdict

    def _derive_verdict(
        self,
        comparison: SimulationComparison,
        scores: dict[str, float],
        top_risk: RiskLevel,
        review_burden: float,
    ) -> SimulationVerdict:
        """Derive a verdict from comparison results."""
        best_id = comparison.ranked_option_ids[0]
        best_score = scores[best_id]
        reasons: list[str] = []

        # Determine verdict type
        risk_severity = _RISK_SEVERITY.get(top_risk, 0)
        if risk_severity >= _RISK_SEVERITY[RiskLevel.CRITICAL]:
            verdict_type = VerdictType.ESCALATE
            reasons.append("critical risk detected — escalation required")
        elif review_burden >= _HIGH_REVIEW_BURDEN:
            verdict_type = VerdictType.APPROVAL_REQUIRED
            reasons.append(f"high review burden ({review_burden:.2f})")
        elif risk_severity >= _RISK_SEVERITY[RiskLevel.HIGH]:
            verdict_type = VerdictType.ESCALATE
            reasons.append("high risk detected — escalation recommended")
        elif risk_severity >= _RISK_SEVERITY[RiskLevel.MODERATE]:
            verdict_type = VerdictType.PROCEED_WITH_CAUTION
            reasons.append("medium risk — proceed with caution")
        elif best_score < 0.5:
            verdict_type = VerdictType.APPROVAL_REQUIRED
            reasons.append(f"low confidence score ({best_score:.2f})")
        else:
            verdict_type = VerdictType.PROCEED
            reasons.append("acceptable risk and confidence")

        # Confidence is the best score adjusted by risk
        confidence = _clamp(best_score - (risk_severity * 0.05))

        reasons.append(f"recommended option: {best_id} (score={best_score:.2f})")

        now = self._clock()
        verdict_id = stable_identifier("sim-verdict", {
            "comparison_id": comparison.comparison_id,
            "created_at": now,
        })
        return SimulationVerdict(
            verdict_id=verdict_id,
            comparison_id=comparison.comparison_id,
            verdict_type=verdict_type,
            recommended_option_id=best_id,
            confidence=confidence,
            reasons=tuple(reasons),
        )
