"""Purpose: meta-reasoning integration bridge — connects the meta-reasoning engine
to simulation, utility, provider routing, learning, recovery, and dashboard subsystems.
Governance scope: meta-reasoning invocation for goal decomposition, workflow selection,
    runbook execution, recovery choice, approval recommendation, escalation timing,
    and provider routing.
Dependencies: meta-reasoning engine, simulation contracts, utility contracts,
    provider routing contracts, decision learning contracts.
Invariants:
  - Bridge methods are stateless static helpers.
  - Each method composes existing engine calls.
  - No graph mutation. No side effects beyond engine-internal state.
  - Assessment output is advisory only — never auto-executes.
  - All scores are bounded [0.0, 1.0] and auditable.
"""

from __future__ import annotations

from .invariants import stable_identifier
from mcoi_runtime.contracts.decision_learning import DecisionAdjustment
from mcoi_runtime.contracts.meta_reasoning import (
    DecisionReliability,
    EscalationRecommendation,
    EscalationSeverity,
    MetaReasoningSnapshot,
    ReplanRecommendation,
    SubsystemHealth,
    UncertaintyReport,
    UncertaintySource,
)
from mcoi_runtime.contracts.provider_routing import RoutingOutcome
from mcoi_runtime.contracts.simulation import SimulationVerdict
from mcoi_runtime.contracts.utility import DecisionComparison
from .meta_reasoning import MetaReasoningEngine


class MetaReasoningBridge:
    """Static methods bridging meta-reasoning assessments to platform decision points.

    Provides convenience methods for:
    - Assessing all reliability pillars before a high-stakes decision
    - Checking if a goal or workflow needs replanning
    - Generating a full meta-reasoning snapshot for dashboards
    - Assessing provider stability before routing
    - Evaluating recovery confidence before choosing a recovery path
    - Generating escalation recommendations from reliability data
    """

    @staticmethod
    def assess_decision_pillars(
        engine: MetaReasoningEngine,
        *,
        sim_verdict: SimulationVerdict | None = None,
        util_comparison: DecisionComparison | None = None,
        routing_outcomes: tuple[RoutingOutcome, ...] = (),
        provider_ids: tuple[str, ...] = (),
        learning_adjustments: tuple[DecisionAdjustment, ...] = (),
        min_confidence: float = 0.6,
        min_spread: float = 0.1,
        min_success_rate: float = 0.7,
    ) -> tuple[DecisionReliability, ...]:
        """Run all applicable assessment methods and return the reliability tuple.

        Each pillar is evaluated only if its input data is provided.
        Returns a tuple of 0–4 DecisionReliability records.
        """
        reliabilities: list[DecisionReliability] = []

        if sim_verdict is not None:
            reliabilities.append(
                engine.assess_simulation_confidence(
                    sim_verdict, min_confidence=min_confidence,
                )
            )

        if util_comparison is not None:
            reliabilities.append(
                engine.assess_utility_ambiguity(
                    util_comparison, min_spread=min_spread,
                )
            )

        if routing_outcomes:
            reliabilities.append(
                engine.assess_provider_volatility(
                    routing_outcomes, provider_ids,
                    min_success_rate=min_success_rate,
                )
            )

        if learning_adjustments:
            reliabilities.append(
                engine.assess_learning_reliability(learning_adjustments)
            )

        return tuple(reliabilities)

    @staticmethod
    def assess_and_replan(
        engine: MetaReasoningEngine,
        affected_entity_id: str,
        *,
        sim_verdict: SimulationVerdict | None = None,
        util_comparison: DecisionComparison | None = None,
        routing_outcomes: tuple[RoutingOutcome, ...] = (),
        provider_ids: tuple[str, ...] = (),
        learning_adjustments: tuple[DecisionAdjustment, ...] = (),
        replan_threshold: float = 0.3,
    ) -> tuple[tuple[DecisionReliability, ...], tuple[ReplanRecommendation, ...]]:
        """Assess decision pillars and check if replanning is needed.

        Returns:
            A tuple of (reliabilities, replan_recommendations).
            replan_recommendations is non-empty if any pillar falls below threshold.
        """
        reliabilities = MetaReasoningBridge.assess_decision_pillars(
            engine,
            sim_verdict=sim_verdict,
            util_comparison=util_comparison,
            routing_outcomes=routing_outcomes,
            provider_ids=provider_ids,
            learning_adjustments=learning_adjustments,
        )

        replans = engine.check_replan_needed(
            reliabilities,
            affected_entity_id,
            replan_threshold=replan_threshold,
        )

        return reliabilities, replans

    @staticmethod
    def full_meta_snapshot(
        engine: MetaReasoningEngine,
        subsystem_checks: tuple[SubsystemHealth, ...],
        *,
        sim_verdict: SimulationVerdict | None = None,
        util_comparison: DecisionComparison | None = None,
        routing_outcomes: tuple[RoutingOutcome, ...] = (),
        provider_ids: tuple[str, ...] = (),
        learning_adjustments: tuple[DecisionAdjustment, ...] = (),
        affected_entity_id: str = "system",
        replan_threshold: float = 0.3,
    ) -> MetaReasoningSnapshot:
        """Generate a comprehensive meta-reasoning snapshot.

        Runs all assessment pillars, checks for replanning, then delegates
        to the engine's meta_snapshot for full assembly.  This is the
        single-call entry point for dashboard integration.
        """
        reliabilities, replans = MetaReasoningBridge.assess_and_replan(
            engine,
            affected_entity_id,
            sim_verdict=sim_verdict,
            util_comparison=util_comparison,
            routing_outcomes=routing_outcomes,
            provider_ids=provider_ids,
            learning_adjustments=learning_adjustments,
            replan_threshold=replan_threshold,
        )

        return engine.meta_snapshot(
            subsystem_checks,
            reliabilities=reliabilities,
            replan_recommendations=replans,
        )

    @staticmethod
    def assess_before_routing(
        engine: MetaReasoningEngine,
        routing_outcomes: tuple[RoutingOutcome, ...],
        provider_ids: tuple[str, ...],
        *,
        min_success_rate: float = 0.7,
    ) -> DecisionReliability:
        """Assess provider stability before routing a new request.

        Convenience wrapper for assess_provider_volatility.
        """
        return engine.assess_provider_volatility(
            routing_outcomes, provider_ids,
            min_success_rate=min_success_rate,
        )

    @staticmethod
    def assess_before_recovery(
        engine: MetaReasoningEngine,
        sim_verdict: SimulationVerdict,
        *,
        min_confidence: float = 0.6,
    ) -> DecisionReliability:
        """Assess simulation confidence before choosing a recovery path.

        Convenience wrapper for assess_simulation_confidence applied
        to recovery-context simulation verdicts.
        """
        return engine.assess_simulation_confidence(
            sim_verdict, min_confidence=min_confidence,
        )

    @staticmethod
    def escalate_from_reliability(
        engine: MetaReasoningEngine,
        reliabilities: tuple[DecisionReliability, ...],
        affected_ids: tuple[str, ...],
        *,
        escalation_threshold: float = 0.3,
    ) -> tuple[EscalationRecommendation, ...]:
        """Generate and record escalation recommendations for low-reliability pillars.

        Any reliability below escalation_threshold triggers an escalation.
        """
        _CONTEXT_TO_SEVERITY: dict[str, EscalationSeverity] = {
            "simulation": EscalationSeverity.HIGH,
            "utility": EscalationSeverity.MEDIUM,
            "provider_routing": EscalationSeverity.MEDIUM,
            "learning": EscalationSeverity.LOW,
        }
        results: list[EscalationRecommendation] = []
        for rel in reliabilities:
            point = rel.confidence_envelope.point_estimate
            if point < escalation_threshold:

                now = engine.clock()
                severity = _CONTEXT_TO_SEVERITY.get(
                    rel.decision_context, EscalationSeverity.MEDIUM,
                )
                rec = EscalationRecommendation(
                    recommendation_id=stable_identifier("meta-esc", {
                        "context": rel.decision_context,
                        "at": now,
                    }),
                    reason=(
                        f"{rel.decision_context} confidence {point:.2f} "
                        f"below escalation threshold {escalation_threshold}"
                    ),
                    severity=severity,
                    affected_ids=affected_ids,
                    suggested_action=f"review {rel.decision_context} before proceeding",
                    created_at=now,
                )
                engine.recommend_escalation(rec)
                results.append(rec)

        return tuple(results)

    @staticmethod
    def report_uncertainty_from_reliability(
        engine: MetaReasoningEngine,
        reliabilities: tuple[DecisionReliability, ...],
        affected_ids: tuple[str, ...],
        *,
        uncertainty_threshold: float = 0.5,
    ) -> tuple[UncertaintyReport, ...]:
        """Generate and record uncertainty reports for reliabilities below threshold.

        Any reliability below uncertainty_threshold is surfaced as an
        explicit uncertainty report.
        """
        reports: list[UncertaintyReport] = []
        for rel in reliabilities:
            point = rel.confidence_envelope.point_estimate
            if point < uncertainty_threshold:

                now = engine.clock()
                report = UncertaintyReport(
                    report_id=stable_identifier("meta-unc", {
                        "context": rel.decision_context,
                        "at": now,
                    }),
                    subject=rel.decision_context,
                    source=UncertaintySource.LOW_CONFIDENCE,
                    description=(
                        f"{rel.decision_context} reliability {point:.2f} "
                        f"below uncertainty threshold {uncertainty_threshold}"
                    ),
                    affected_ids=affected_ids,
                    created_at=now,
                )
                engine.report_uncertainty(report)
                reports.append(report)

        return tuple(reports)
