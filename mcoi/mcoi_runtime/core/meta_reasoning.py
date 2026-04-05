"""Purpose: meta-reasoning core — capability confidence, uncertainty tracking,
health assessment, decision reliability evaluation, and replan recommendations.
Governance scope: meta-reasoning plane core logic only.
Dependencies:
  - mcoi_runtime.contracts.meta_reasoning — all meta-reasoning contracts
  - mcoi_runtime.contracts.simulation — SimulationVerdict
  - mcoi_runtime.contracts.utility — DecisionComparison
  - mcoi_runtime.contracts.provider_routing — RoutingOutcome
  - mcoi_runtime.contracts.decision_learning — DecisionAdjustment
  - mcoi_runtime.core.invariants — stable_identifier, ensure_non_empty_text
Invariants:
  - Confidence derives from historical data, never fabricated.
  - Uncertainty is explicit, never suppressed.
  - Health assessment is deterministic.
  - Escalation recommendations are advisory only.
  - Assessment methods are pure functions of their inputs plus clock.
  - No network, no IO.
"""

from __future__ import annotations

from typing import Callable

from mcoi_runtime.contracts.decision_learning import DecisionAdjustment
from mcoi_runtime.contracts.meta_reasoning import (
    CapabilityConfidence,
    ConfidenceEnvelope,
    DecisionReliability,
    DegradedModeRecord,
    EscalationRecommendation,
    EscalationSeverity,
    HealthStatus,
    MetaReasoningSnapshot,
    ReplanReason,
    ReplanRecommendation,
    SelfHealthSnapshot,
    SubsystemHealth,
    UncertaintyReport,
    UncertaintySource,
)
from mcoi_runtime.contracts.provider_routing import RoutingOutcome
from mcoi_runtime.contracts.simulation import SimulationVerdict, VerdictType
from mcoi_runtime.contracts.utility import DecisionComparison
from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


class MetaReasoningEngine:
    """Capability confidence tracking, uncertainty management, health assessment,
    decision reliability evaluation, and replan recommendations.

    This engine:
    - Tracks historical reliability per capability
    - Records uncertainty explicitly
    - Detects degraded mode based on confidence thresholds
    - Produces escalation recommendations
    - Generates deterministic health snapshots
    - Assesses simulation, utility, provider, and learning reliability
    - Produces replan recommendations when thresholds are breached
    - Generates comprehensive meta-reasoning snapshots
    """

    def __init__(self, *, clock: Callable[[], str], default_threshold: float = 0.5) -> None:
        self._clock = clock
        if not isinstance(default_threshold, (int, float)) or not (0.0 <= default_threshold <= 1.0):
            raise ValueError("default_threshold must be a float in [0.0, 1.0]")
        self._default_threshold = float(default_threshold)
        self._confidence: dict[str, CapabilityConfidence] = {}
        self._thresholds: dict[str, float] = {}
        self._uncertainty: dict[str, UncertaintyReport] = {}
        self._degraded: dict[str, DegradedModeRecord] = {}
        self._escalations: list[EscalationRecommendation] = []

    @property
    def clock(self) -> Callable[[], str]:
        """Public accessor for the injected clock function."""
        return self._clock

    # --- Confidence ---

    def update_confidence(self, confidence: CapabilityConfidence) -> CapabilityConfidence:
        self._confidence[confidence.capability_id] = confidence
        # Check if this triggers degraded mode
        threshold = self._thresholds.get(confidence.capability_id, self._default_threshold)
        if confidence.overall_confidence < threshold:
            if confidence.capability_id not in self._degraded:
                self._degraded[confidence.capability_id] = DegradedModeRecord(
                    record_id=stable_identifier("degraded", {
                        "capability_id": confidence.capability_id,
                        "entered_at": self._clock(),
                    }),
                    capability_id=confidence.capability_id,
                    reason="confidence below threshold",
                    confidence_at_entry=confidence.overall_confidence,
                    threshold=threshold,
                    entered_at=self._clock(),
                )
        else:
            # Exit degraded mode if confidence recovered
            self._degraded.pop(confidence.capability_id, None)
        return confidence

    def get_confidence(self, capability_id: str) -> CapabilityConfidence | None:
        ensure_non_empty_text("capability_id", capability_id)
        return self._confidence.get(capability_id)

    def set_threshold(self, capability_id: str, threshold: float) -> None:
        ensure_non_empty_text("capability_id", capability_id)
        if not isinstance(threshold, (int, float)) or threshold < 0.0 or threshold > 1.0:
            raise RuntimeCoreInvariantError("threshold must be in [0.0, 1.0]")
        self._thresholds[capability_id] = threshold

    def is_degraded(self, capability_id: str) -> bool:
        ensure_non_empty_text("capability_id", capability_id)
        return capability_id in self._degraded

    def list_degraded(self) -> tuple[DegradedModeRecord, ...]:
        return tuple(sorted(self._degraded.values(), key=lambda d: d.capability_id))

    # --- Uncertainty ---

    def report_uncertainty(self, report: UncertaintyReport) -> UncertaintyReport:
        if report.report_id in self._uncertainty:
            raise RuntimeCoreInvariantError("uncertainty report already exists")
        self._uncertainty[report.report_id] = report
        return report

    def list_uncertainty(self) -> tuple[UncertaintyReport, ...]:
        return tuple(sorted(self._uncertainty.values(), key=lambda u: u.report_id))

    # --- Escalation ---

    def recommend_escalation(self, recommendation: EscalationRecommendation) -> EscalationRecommendation:
        self._escalations.append(recommendation)
        return recommendation

    def list_escalation_recommendations(self) -> tuple[EscalationRecommendation, ...]:
        return tuple(self._escalations)

    # --- Health ---

    def assess_health(self, subsystem_checks: tuple[SubsystemHealth, ...]) -> SelfHealthSnapshot:
        """Produce a deterministic health snapshot from subsystem checks."""
        if not subsystem_checks:
            raise RuntimeCoreInvariantError("subsystem_checks must contain at least one item")
        snapshot_id = stable_identifier("health", {
            "subsystems": [s.subsystem for s in subsystem_checks],
        })
        return SelfHealthSnapshot(
            snapshot_id=snapshot_id,
            subsystems=subsystem_checks,
            assessed_at=self._clock(),
        )

    # ------------------------------------------------------------------
    # Decision reliability assessments
    # ------------------------------------------------------------------

    def _make_envelope(
        self,
        subject: str,
        point: float,
        margin: float,
        sample_count: int,
    ) -> ConfidenceEnvelope:
        """Build a ConfidenceEnvelope with clamped bounds."""
        now = self._clock()
        return ConfidenceEnvelope(
            assessment_id=stable_identifier("meta-env", {
                "subject": subject, "point": str(round(point, 6)), "at": now,
            }),
            subject=subject,
            point_estimate=_clamp(point),
            lower_bound=_clamp(point - margin),
            upper_bound=_clamp(point + margin),
            sample_count=sample_count,
            assessed_at=now,
        )

    def _make_reliability(
        self,
        context: str,
        envelope: ConfidenceEnvelope,
        uncertainty_factors: tuple[str, ...],
        dominant_risk: str,
    ) -> DecisionReliability:
        """Build a DecisionReliability with auto-derived recommendation."""
        point = envelope.point_estimate
        if point >= 0.7:
            recommendation = "proceed"
        elif point >= 0.5:
            recommendation = "proceed_with_caution"
        elif point >= 0.3:
            recommendation = "defer_to_review"
        else:
            recommendation = "replan"

        now = self._clock()
        return DecisionReliability(
            reliability_id=stable_identifier("meta-rel", {
                "context": context, "point": str(round(point, 6)), "at": now,
            }),
            decision_context=context,
            confidence_envelope=envelope,
            uncertainty_factors=uncertainty_factors,
            dominant_risk=dominant_risk,
            recommendation=recommendation,
            assessed_at=now,
        )

    def assess_simulation_confidence(
        self,
        verdict: SimulationVerdict,
        *,
        min_confidence: float = 0.6,
    ) -> DecisionReliability:
        """Evaluate whether a simulation verdict's confidence is sufficient.

        A verdict with low confidence or an ESCALATE/ABORT type yields
        a reduced reliability envelope.
        """
        base = verdict.confidence
        # Penalize for high-risk verdict types
        if verdict.verdict_type in (VerdictType.ESCALATE, VerdictType.ABORT):
            base *= 0.5
        elif verdict.verdict_type == VerdictType.APPROVAL_REQUIRED:
            base *= 0.75

        margin = 0.15 if base >= min_confidence else 0.25
        uncertainty: list[str] = []
        if verdict.confidence < min_confidence:
            uncertainty.append("low simulation confidence")
        if verdict.verdict_type in (VerdictType.ESCALATE, VerdictType.ABORT):
            uncertainty.append("high-risk verdict type")

        envelope = self._make_envelope("simulation", base, margin, sample_count=1)
        return self._make_reliability(
            "simulation",
            envelope,
            tuple(uncertainty) if uncertainty else ("none",),
            dominant_risk="simulation may not reflect reality",
        )

    def assess_utility_ambiguity(
        self,
        comparison: DecisionComparison,
        *,
        min_spread: float = 0.1,
    ) -> DecisionReliability:
        """Evaluate whether the utility spread is sufficient to distinguish options.

        A low spread (close scores) means high ambiguity — any choice is
        nearly as good as another, but also nearly as risky.
        """
        option_count = len(comparison.option_utilities)
        # Normalize spread into a confidence signal
        if comparison.spread >= min_spread:
            base = _clamp(0.5 + comparison.spread)
        else:
            base = _clamp(0.3 + comparison.spread)

        margin = 0.1 if comparison.spread >= min_spread else 0.2
        uncertainty: list[str] = []
        if comparison.spread < min_spread:
            uncertainty.append("utility ambiguity detected")

        envelope = self._make_envelope("utility", base, margin, sample_count=option_count)
        return self._make_reliability(
            "utility",
            envelope,
            tuple(uncertainty) if uncertainty else ("none",),
            dominant_risk="options are too similar to reliably distinguish",
        )

    def assess_provider_volatility(
        self,
        outcomes: tuple[RoutingOutcome, ...],
        provider_ids: tuple[str, ...],
        *,
        min_success_rate: float = 0.7,
    ) -> DecisionReliability:
        """Evaluate provider routing stability from outcome history.

        High failure rates across providers signal volatility.
        """
        if not outcomes:
            envelope = self._make_envelope("provider_routing", 0.5, 0.3, sample_count=0)
            return self._make_reliability(
                "provider_routing", envelope,
                ("no routing outcomes recorded",),
                "provider reliability unknown",
            )

        # Per-provider success rates
        counts: dict[str, int] = {}
        successes: dict[str, int] = {}
        for ro in outcomes:
            counts[ro.provider_id] = counts.get(ro.provider_id, 0) + 1
            if ro.success:
                successes[ro.provider_id] = successes.get(ro.provider_id, 0) + 1

        total = len(outcomes)
        total_success = sum(successes.values())
        overall_rate = total_success / total

        uncertainty: list[str] = []
        volatile_providers: list[str] = []
        for pid in provider_ids:
            c = counts.get(pid, 0)
            s = successes.get(pid, 0)
            if c > 0 and s / c < min_success_rate:
                volatile_providers.append(pid)
                uncertainty.append("provider volatility detected")

        base = _clamp(overall_rate)
        margin = 0.1 if not volatile_providers else 0.2
        envelope = self._make_envelope("provider_routing", base, margin, sample_count=total)
        return self._make_reliability(
            "provider_routing", envelope,
            tuple(uncertainty) if uncertainty else ("none",),
            dominant_risk="provider failure may disrupt execution"
            if volatile_providers else "providers stable",
        )

    def assess_learning_reliability(
        self,
        adjustments: tuple[DecisionAdjustment, ...],
        *,
        max_magnitude: float = 0.1,
        min_sample_count: int = 5,
    ) -> DecisionReliability:
        """Evaluate whether learning adjustments are stable or potentially overfitting.

        Large magnitude swings or too few samples signal unreliable learning.
        """
        if not adjustments:
            envelope = self._make_envelope("learning", 0.5, 0.3, sample_count=0)
            return self._make_reliability(
                "learning", envelope,
                ("no adjustments recorded",),
                "learning has no data to evaluate",
            )

        count = len(adjustments)
        magnitudes = [abs(a.delta) for a in adjustments]
        avg_magnitude = sum(magnitudes) / count
        max_observed = max(magnitudes)

        uncertainty: list[str] = []
        if count < min_sample_count:
            uncertainty.append("insufficient learning history")
        if max_observed > max_magnitude:
            uncertainty.append("learning adjustment exceeds limit")
        if avg_magnitude > max_magnitude * 0.5:
            uncertainty.append("learning adjustment instability detected")

        # Derive confidence from stability
        if count >= min_sample_count and avg_magnitude <= max_magnitude * 0.5:
            base = _clamp(0.8 - avg_magnitude)
        elif count >= min_sample_count:
            base = _clamp(0.6 - avg_magnitude)
        else:
            base = _clamp(0.4)

        margin = 0.1 if not uncertainty else 0.2
        envelope = self._make_envelope("learning", base, margin, sample_count=count)
        return self._make_reliability(
            "learning", envelope,
            tuple(uncertainty) if uncertainty else ("none",),
            dominant_risk="learning adjustments may be unstable or overfitting",
        )

    # ------------------------------------------------------------------
    # Replan recommendations
    # ------------------------------------------------------------------

    def check_replan_needed(
        self,
        reliabilities: tuple[DecisionReliability, ...],
        affected_entity_id: str,
        *,
        replan_threshold: float = 0.3,
    ) -> tuple[ReplanRecommendation, ...]:
        """Generate replan recommendations for any reliability below threshold."""
        _CONTEXT_TO_REASON: dict[str, ReplanReason] = {
            "simulation": ReplanReason.CONFIDENCE_TOO_LOW,
            "utility": ReplanReason.AMBIGUITY_TOO_HIGH,
            "provider_routing": ReplanReason.PROVIDER_VOLATILITY,
            "learning": ReplanReason.LEARNING_UNRELIABLE,
        }
        _CONTEXT_TO_SEVERITY: dict[str, EscalationSeverity] = {
            "simulation": EscalationSeverity.HIGH,
            "utility": EscalationSeverity.MEDIUM,
            "provider_routing": EscalationSeverity.MEDIUM,
            "learning": EscalationSeverity.LOW,
        }

        recs: list[ReplanRecommendation] = []
        for rel in reliabilities:
            point = rel.confidence_envelope.point_estimate
            if point < replan_threshold:
                now = self._clock()
                reason = _CONTEXT_TO_REASON.get(
                    rel.decision_context, ReplanReason.CONFIDENCE_TOO_LOW,
                )
                severity = _CONTEXT_TO_SEVERITY.get(
                    rel.decision_context, EscalationSeverity.MEDIUM,
                )
                recs.append(ReplanRecommendation(
                    recommendation_id=stable_identifier("meta-replan", {
                        "context": rel.decision_context,
                        "entity": affected_entity_id,
                        "at": now,
                    }),
                    reason=reason,
                    description="replan threshold breached",
                    affected_entity_id=affected_entity_id,
                    severity=severity,
                    confidence_at_assessment=_clamp(1.0 - point),
                    created_at=now,
                ))
        return tuple(recs)

    # ------------------------------------------------------------------
    # Full meta-reasoning snapshot
    # ------------------------------------------------------------------

    def meta_snapshot(
        self,
        subsystem_checks: tuple[SubsystemHealth, ...],
        *,
        reliabilities: tuple[DecisionReliability, ...] = (),
        replan_recommendations: tuple[ReplanRecommendation, ...] = (),
    ) -> MetaReasoningSnapshot:
        """Produce a comprehensive meta-reasoning snapshot.

        Combines health assessment, degraded capabilities, uncertainties,
        decision reliabilities, replan recommendations, and escalation
        recommendations into a single immutable snapshot.
        """
        health = self.assess_health(subsystem_checks)
        degraded = self.list_degraded()
        uncertainties = self.list_uncertainty()
        escalations = self.list_escalation_recommendations()

        # Derive overall confidence from all reliability assessments
        if reliabilities:
            points = [r.confidence_envelope.point_estimate for r in reliabilities]
            overall = _clamp(sum(points) / len(points))
        else:
            overall = 0.5  # neutral when no assessments available

        # Penalize for degraded capabilities
        if degraded:
            overall = _clamp(overall - 0.1 * len(degraded))
        # Penalize for active uncertainties
        if uncertainties:
            overall = _clamp(overall - 0.05 * len(uncertainties))

        now = self._clock()
        return MetaReasoningSnapshot(
            snapshot_id=stable_identifier("meta-snap", {
                "health_id": health.snapshot_id,
                "reliabilities": len(reliabilities),
                "at": now,
            }),
            captured_at=now,
            health=health,
            degraded_capabilities=degraded,
            active_uncertainties=uncertainties,
            decision_reliabilities=reliabilities,
            replan_recommendations=replan_recommendations,
            escalation_recommendations=escalations,
            overall_confidence=round(overall, 4),
        )
