"""Purpose: meta-reasoning core — capability confidence, uncertainty tracking, health assessment.
Governance scope: meta-reasoning plane core logic only.
Dependencies: meta-reasoning contracts, invariant helpers.
Invariants:
  - Confidence derives from historical data, never fabricated.
  - Uncertainty is explicit, never suppressed.
  - Health assessment is deterministic.
  - Escalation recommendations are advisory only.
"""

from __future__ import annotations

from typing import Callable

from mcoi_runtime.contracts.meta_reasoning import (
    CapabilityConfidence,
    DegradedModeRecord,
    EscalationRecommendation,
    EscalationSeverity,
    HealthStatus,
    SelfHealthSnapshot,
    SubsystemHealth,
    UncertaintyReport,
    UncertaintySource,
)
from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier


class MetaReasoningEngine:
    """Capability confidence tracking, uncertainty management, and health assessment.

    This engine:
    - Tracks historical reliability per capability
    - Records uncertainty explicitly
    - Detects degraded mode based on confidence thresholds
    - Produces escalation recommendations
    - Generates deterministic health snapshots
    """

    def __init__(self, *, clock: Callable[[], str], default_threshold: float = 0.5) -> None:
        self._clock = clock
        self._default_threshold = default_threshold
        self._confidence: dict[str, CapabilityConfidence] = {}
        self._thresholds: dict[str, float] = {}
        self._uncertainty: dict[str, UncertaintyReport] = {}
        self._degraded: dict[str, DegradedModeRecord] = {}
        self._escalations: list[EscalationRecommendation] = []

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
                    reason=f"confidence {confidence.overall_confidence:.4f} below threshold {threshold}",
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
            raise RuntimeCoreInvariantError(f"uncertainty report already exists: {report.report_id}")
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
