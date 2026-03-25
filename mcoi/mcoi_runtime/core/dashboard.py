"""Purpose: operator dashboard engine — aggregates state from multiple
subsystems into dashboard snapshots for operator visibility.
Governance scope: dashboard snapshot generation only.
Dependencies:
  - mcoi_runtime.contracts.dashboard — DecisionSummary, ProviderRoutingSummary,
    LearningInsight, DashboardSnapshot
  - mcoi_runtime.contracts.decision_learning — DecisionOutcomeRecord,
    DecisionAdjustment
  - mcoi_runtime.contracts.provider_routing — RoutingOutcome
  - mcoi_runtime.core.invariants — stable_identifier
Invariants:
  - Dashboard engine is stateless — it reads data passed to it.
  - No mutation of any engine state.
  - No network, no IO.
  - Clock injected for determinism.
  - Snapshot generation is a pure function of its inputs.
"""

from __future__ import annotations

from typing import Callable

from mcoi_runtime.contracts.dashboard import (
    DashboardSnapshot,
    DecisionSummary,
    LearningInsight,
    MetaReasoningSummary,
    ProviderRoutingSummary,
    ReliabilityPillarSummary,
    WorldStateSummary,
)
from mcoi_runtime.contracts.world_state import WorldStateSnapshot
from mcoi_runtime.contracts.decision_learning import (
    DecisionAdjustment,
    DecisionOutcomeRecord,
)
from mcoi_runtime.contracts.meta_reasoning import MetaReasoningSnapshot
from mcoi_runtime.contracts.provider_routing import RoutingOutcome
from .invariants import stable_identifier


class DashboardEngine:
    """Pure aggregator that builds dashboard snapshots from subsystem data.

    This engine owns no state. Every method is a pure function of its inputs
    plus the injected clock (used only for deterministic IDs and timestamps).
    """

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock

    # ------------------------------------------------------------------
    # Decision summaries
    # ------------------------------------------------------------------

    def build_decision_summaries(
        self,
        outcomes: tuple[DecisionOutcomeRecord, ...],
        adjustments: tuple[DecisionAdjustment, ...],
        *,
        max_recent: int = 10,
    ) -> tuple[DecisionSummary, ...]:
        """Build decision summaries from outcome records and adjustments.

        Returns the last *max_recent* entries, most recent first.
        """
        # Index adjustments by comparison_id for fast lookup.
        # DecisionAdjustment does not carry a comparison_id directly,
        # so we match via created_at proximity to the outcome's recorded_at.
        # However, the spec says to match by comparison_id.  Adjustments
        # don't have comparison_id — instead we correlate via the
        # outcome's recorded_at window.  For a clean approach we build
        # descriptive weight-change strings from all adjustments whose
        # created_at matches the outcome's recorded_at (same learning cycle).
        adjustments_by_time: dict[str, list[DecisionAdjustment]] = {}
        for adj in adjustments:
            adjustments_by_time.setdefault(adj.created_at, []).append(adj)

        summaries: list[DecisionSummary] = []
        for outcome in outcomes:
            # Find adjustments that share the same timestamp (same cycle).
            cycle_adjustments = adjustments_by_time.get(outcome.recorded_at, [])
            weight_changes: list[str] = []
            for adj in cycle_adjustments:
                sign = "+" if adj.delta >= 0 else ""
                weight_changes.append(
                    f"{adj.target_factor_kind}: {sign}{adj.delta:.6f}"
                )

            now = self._clock()
            decision_id = stable_identifier("dash-dec", {
                "outcome_id": outcome.outcome_id,
                "generated_at": now,
            })

            summaries.append(
                DecisionSummary(
                    decision_id=decision_id,
                    comparison_id=outcome.comparison_id,
                    chosen_option_id=outcome.chosen_option_id,
                    quality=outcome.quality.value,
                    actual_cost=outcome.actual_cost,
                    estimated_cost=0.0,
                    weight_changes=tuple(weight_changes),
                    decided_at=outcome.recorded_at,
                ),
            )

        # Most recent first, then trim to max_recent.
        summaries.reverse()
        return tuple(summaries[:max_recent])

    # ------------------------------------------------------------------
    # Provider routing summaries
    # ------------------------------------------------------------------

    def build_provider_summaries(
        self,
        routing_outcomes: tuple[RoutingOutcome, ...],
        preferences: dict[str, float],
        provider_ids: tuple[str, ...],
        health_scores: dict[str, float],
        *,
        context_type: str = "aggregate",
    ) -> tuple[ProviderRoutingSummary, ...]:
        """Build per-provider routing summaries from outcome data.

        *preferences* maps provider_id -> preference_score.
        *health_scores* maps provider_id -> health_score.
        """
        # Pre-aggregate counts per provider.
        routing_counts: dict[str, int] = {}
        success_counts: dict[str, int] = {}
        failure_counts: dict[str, int] = {}

        for ro in routing_outcomes:
            routing_counts[ro.provider_id] = routing_counts.get(ro.provider_id, 0) + 1
            if ro.success:
                success_counts[ro.provider_id] = success_counts.get(ro.provider_id, 0) + 1
            else:
                failure_counts[ro.provider_id] = failure_counts.get(ro.provider_id, 0) + 1

        summaries: list[ProviderRoutingSummary] = []
        for pid in provider_ids:
            summaries.append(
                ProviderRoutingSummary(
                    provider_id=pid,
                    context_type=context_type,
                    preference_score=preferences.get(pid, 0.5),
                    health_score=health_scores.get(pid, 0.3),
                    routing_count=routing_counts.get(pid, 0),
                    success_count=success_counts.get(pid, 0),
                    failure_count=failure_counts.get(pid, 0),
                ),
            )

        return tuple(summaries)

    # ------------------------------------------------------------------
    # Learning insights
    # ------------------------------------------------------------------

    def build_learning_insights(
        self,
        learned_adjustments: dict[str, float],
    ) -> tuple[LearningInsight, ...]:
        """Derive learning insights from cumulative factor-weight deltas.

        For each factor_kind -> cumulative_delta:
        - direction = "improving"  if delta >  0.001
        - direction = "declining"  if delta < -0.001
        - direction = "stable"     otherwise
        """
        insights: list[LearningInsight] = []
        for factor_kind in sorted(learned_adjustments):
            delta = learned_adjustments[factor_kind]

            if delta > 0.001:
                direction = "improving"
            elif delta < -0.001:
                direction = "declining"
            else:
                direction = "stable"

            insight_id = stable_identifier("dash-insight", {
                "factor_kind": factor_kind,
                "delta": str(round(delta, 6)),
            })

            explanation = (
                f"Factor '{factor_kind}' has shifted by {delta:+.6f} "
                f"across recorded adjustments ({direction})."
            )

            insights.append(
                LearningInsight(
                    insight_id=insight_id,
                    factor_kind=factor_kind,
                    cumulative_delta=round(delta, 6),
                    direction=direction,
                    sample_count=0,
                    explanation=explanation,
                ),
            )

        return tuple(insights)

    # ------------------------------------------------------------------
    # Meta-reasoning summary
    # ------------------------------------------------------------------

    def build_meta_reasoning_summary(
        self,
        meta_snapshot: MetaReasoningSnapshot,
    ) -> MetaReasoningSummary:
        """Build a dashboard-ready meta-reasoning summary from a MetaReasoningSnapshot.

        Extracts confidence envelope display, dominant uncertainty, counts,
        per-pillar breakdowns, and overall recommendation.
        """
        # Per-pillar summaries
        pillars: list[ReliabilityPillarSummary] = []
        for rel in meta_snapshot.decision_reliabilities:
            pillars.append(ReliabilityPillarSummary(
                pillar=rel.decision_context,
                confidence=rel.confidence_envelope.point_estimate,
                recommendation=rel.recommendation,
                dominant_risk=rel.dominant_risk,
            ))

        # Confidence display: "0.72 [0.55 – 0.89]" or just "0.50" if no pillars
        if meta_snapshot.decision_reliabilities:
            # Use the first reliability's envelope for display range
            all_lower = min(
                r.confidence_envelope.lower_bound
                for r in meta_snapshot.decision_reliabilities
            )
            all_upper = max(
                r.confidence_envelope.upper_bound
                for r in meta_snapshot.decision_reliabilities
            )
            confidence_display = (
                f"{meta_snapshot.overall_confidence:.2f} "
                f"[{all_lower:.2f} \u2013 {all_upper:.2f}]"
            )
        else:
            confidence_display = f"{meta_snapshot.overall_confidence:.2f}"

        # Dominant uncertainty
        if meta_snapshot.active_uncertainties:
            dominant_uncertainty = meta_snapshot.active_uncertainties[0].description
        elif meta_snapshot.decision_reliabilities:
            # Pick the lowest-confidence pillar's risk
            worst = min(
                meta_snapshot.decision_reliabilities,
                key=lambda r: r.confidence_envelope.point_estimate,
            )
            dominant_uncertainty = worst.dominant_risk
        else:
            dominant_uncertainty = "none identified"

        # Overall recommendation from pillar consensus
        if meta_snapshot.replan_recommendations:
            recommendation = "replan"
        elif meta_snapshot.escalation_recommendations:
            recommendation = "escalate"
        elif pillars:
            # Use the worst pillar's recommendation
            worst_pillar = min(pillars, key=lambda p: p.confidence)
            recommendation = worst_pillar.recommendation
        else:
            recommendation = "proceed"

        now = self._clock()
        summary_id = stable_identifier("dash-meta", {
            "snap_id": meta_snapshot.snapshot_id,
            "generated_at": now,
        })

        return MetaReasoningSummary(
            summary_id=summary_id,
            overall_confidence=meta_snapshot.overall_confidence,
            confidence_display=confidence_display,
            dominant_uncertainty=dominant_uncertainty,
            degraded_count=len(meta_snapshot.degraded_capabilities),
            replan_count=len(meta_snapshot.replan_recommendations),
            escalation_count=len(meta_snapshot.escalation_recommendations),
            recommendation=recommendation,
            pillars=tuple(pillars),
            assessed_at=now,
        )

    # ------------------------------------------------------------------
    # World-state summary
    # ------------------------------------------------------------------

    def build_world_state_summary(
        self,
        ws_snapshot: WorldStateSnapshot,
        *,
        conflict_set_count: int = 0,
        violation_count: int = 0,
        recommendation: str = "healthy",
    ) -> WorldStateSummary:
        """Build a dashboard-ready world-state summary from a WorldStateSnapshot.

        Caller supplies conflict_set_count and violation_count from the
        WorldStateBridge health assessment (the snapshot alone doesn't
        contain grouped conflict sets or expected-vs-actual results).
        """
        if ws_snapshot.entity_count > 0:
            conf_display = f"{ws_snapshot.overall_confidence:.2f}"
        else:
            conf_display = "0.00 (empty)"

        now = self._clock()
        summary_id = stable_identifier("dash-ws", {
            "snap_id": ws_snapshot.snapshot_id,
            "generated_at": now,
        })

        return WorldStateSummary(
            summary_id=summary_id,
            entity_count=ws_snapshot.entity_count,
            relation_count=ws_snapshot.relation_count,
            derived_fact_count=len(ws_snapshot.derived_facts),
            unresolved_contradiction_count=len(ws_snapshot.unresolved_contradictions),
            conflict_set_count=conflict_set_count,
            expected_state_count=len(ws_snapshot.expected_states),
            violation_count=violation_count,
            overall_confidence=ws_snapshot.overall_confidence,
            confidence_display=conf_display,
            recommendation=recommendation,
            assessed_at=now,
        )

    # ------------------------------------------------------------------
    # Full snapshot
    # ------------------------------------------------------------------

    def snapshot(
        self,
        outcomes: tuple[DecisionOutcomeRecord, ...],
        adjustments: tuple[DecisionAdjustment, ...],
        routing_outcomes: tuple[RoutingOutcome, ...],
        preferences: dict[str, float],
        provider_ids: tuple[str, ...],
        health_scores: dict[str, float],
        learned_adjustments: dict[str, float],
        total_decisions: int,
        total_routing_decisions: int,
        *,
        context_type: str = "aggregate",
        meta_snapshot: MetaReasoningSnapshot | None = None,
        world_state_summary: WorldStateSummary | None = None,
    ) -> DashboardSnapshot:
        """Assemble a complete dashboard snapshot from subsystem data.

        This is the primary entry point for operators.  It delegates to
        the ``build_*`` helpers and packages results into a single
        :class:`DashboardSnapshot`.
        """
        decision_summaries = self.build_decision_summaries(outcomes, adjustments)
        provider_summaries = self.build_provider_summaries(
            routing_outcomes, preferences, provider_ids, health_scores,
            context_type=context_type,
        )
        learning_insights = self.build_learning_insights(learned_adjustments)

        meta_summary: MetaReasoningSummary | None = None
        if meta_snapshot is not None:
            meta_summary = self.build_meta_reasoning_summary(meta_snapshot)

        now = self._clock()
        snapshot_id = stable_identifier("dash-snap", {
            "total_decisions": total_decisions,
            "total_routing": total_routing_decisions,
            "generated_at": now,
        })

        return DashboardSnapshot(
            snapshot_id=snapshot_id,
            captured_at=now,
            total_decisions=total_decisions,
            total_routing_decisions=total_routing_decisions,
            recent_decisions=decision_summaries,
            provider_summaries=provider_summaries,
            learning_insights=learning_insights,
            meta_reasoning=meta_summary,
            world_state=world_state_summary,
        )
