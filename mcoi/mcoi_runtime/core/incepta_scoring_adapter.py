"""Public Incepta Sigma and InceptaMesh scoring adapter.

Purpose: score InceptaDive-M axis findings through the audited Sigma/Mesh
resonance and true-delta line without exposing proprietary M internals.
Governance scope: lineage separation, Mesh denominator guard, graded
confidence, suppression accounting, and recommendation-only outputs.
Dependencies: dataclasses, runtime invariant helpers, and axis traversal types.
Invariants: scoring never approves execution, never emits false absolutes, and
uses max(k-j, 1) for production memory-kernel denominators.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from mcoi_runtime.core.inceptadive_axis_traversal import AxisFinding, DeltaType
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier


class PromotionRecommendation(StrEnum):
    """Allowed scoring recommendations."""

    PROMOTE_CANDIDATE = "promote_candidate"
    REPAIR_REQUIRED = "repair_required"
    CANDIDATE_ONLY = "candidate_only"


@dataclass(frozen=True)
class ResonanceLinks:
    """Inputs to the public resonance kernel."""

    structural_match: float
    causal_coherence: float
    mfidel_judgment: float
    min_alignment: float

    def __post_init__(self) -> None:
        for name, value in self.to_dict().items():
            if not 0.0 <= value <= 1.0:
                raise RuntimeCoreInvariantError(f"resonance input out of range: {name}")

    def to_dict(self) -> dict[str, float]:
        """Return JSON-compatible resonance links."""

        return {
            "structural_match": self.structural_match,
            "causal_coherence": self.causal_coherence,
            "mfidel_judgment": self.mfidel_judgment,
            "min_alignment": self.min_alignment,
        }


@dataclass(frozen=True)
class ScoringInput:
    """Input contract for one finding score."""

    finding: AxisFinding
    layer_index: int
    semantic_delta_magnitude: float
    resonance_links: ResonanceLinks
    observer_penalty: float = 0.0
    history_penalty: float = 0.0
    prior_deltas: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if self.layer_index < 1:
            raise RuntimeCoreInvariantError("layer_index must be positive")
        if self.semantic_delta_magnitude < 0.0:
            raise RuntimeCoreInvariantError("semantic_delta_magnitude must be non-negative")
        if self.observer_penalty < 0.0 or self.history_penalty < 0.0:
            raise RuntimeCoreInvariantError("penalties must be non-negative")


@dataclass(frozen=True)
class InceptaScore:
    """Audited score for an axis finding."""

    score_id: str
    finding_id: str
    true_delta_score: float
    resonance_score: float
    suppression_adjusted_score: float
    confidence_grade: str
    promotion_recommendation: PromotionRecommendation
    repair_recommendation: str
    denominator_guard_applied: bool

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible scoring receipt."""

        return {
            "score_id": self.score_id,
            "finding_id": self.finding_id,
            "true_delta_score": self.true_delta_score,
            "resonance_score": self.resonance_score,
            "suppression_adjusted_score": self.suppression_adjusted_score,
            "confidence_grade": self.confidence_grade,
            "promotion_recommendation": self.promotion_recommendation.value,
            "repair_recommendation": self.repair_recommendation,
            "denominator_guard_applied": self.denominator_guard_applied,
            "execution_approval": False,
        }


def resonance_score(links: ResonanceLinks) -> float:
    """Return the public resonance kernel score."""

    base = 0.4 * links.structural_match + 0.3 * links.causal_coherence + 0.3 * links.mfidel_judgment
    return base * (1.0 - 0.3 * (1.0 - links.min_alignment))


def score_axis_finding(scoring_input: ScoringInput) -> InceptaScore:
    """Score one axis finding with production Mesh denominator guarding."""

    finding = scoring_input.finding
    resonance = resonance_score(scoring_input.resonance_links)
    suppression_adjusted = resonance * (1.0 - finding.suppression.mean)
    base_delta = (
        suppression_adjusted
        * scoring_input.semantic_delta_magnitude
        / ((1.0 + scoring_input.history_penalty) * (1.0 + scoring_input.observer_penalty))
    )
    memory_kernel = 0.0
    guard_applied = False
    for prior_layer, prior_delta in enumerate(scoring_input.prior_deltas, start=1):
        denominator = scoring_input.layer_index - prior_layer
        guarded_denominator = max(denominator, 1)
        guard_applied = guard_applied or guarded_denominator != denominator
        memory_kernel += (prior_delta * resonance) / guarded_denominator
    true_delta = base_delta + memory_kernel
    recommendation = _recommend(finding, suppression_adjusted)
    repair = finding.repair_requirement if recommendation == PromotionRecommendation.REPAIR_REQUIRED else ""
    score_id = stable_identifier(
        "incepta-score",
        {
            "finding_id": finding.finding_id,
            "true_delta_score": round(true_delta, 8),
            "suppression_adjusted_score": round(suppression_adjusted, 8),
        },
    )
    return InceptaScore(
        score_id=score_id,
        finding_id=finding.finding_id,
        true_delta_score=true_delta,
        resonance_score=resonance,
        suppression_adjusted_score=suppression_adjusted,
        confidence_grade=_confidence_grade(suppression_adjusted),
        promotion_recommendation=recommendation,
        repair_recommendation=repair,
        denominator_guard_applied=guard_applied,
    )


def _recommend(finding: AxisFinding, suppression_adjusted_score: float) -> PromotionRecommendation:
    if finding.delta_type == DeltaType.FRACTURE or finding.repair_requirement:
        return PromotionRecommendation.REPAIR_REQUIRED
    if suppression_adjusted_score >= 0.72 and finding.evidence_refs:
        return PromotionRecommendation.PROMOTE_CANDIDATE
    return PromotionRecommendation.CANDIDATE_ONLY


def _confidence_grade(value: float) -> str:
    if value >= 0.85:
        return "A"
    if value >= 0.7:
        return "B"
    if value >= 0.5:
        return "C"
    return "D"
