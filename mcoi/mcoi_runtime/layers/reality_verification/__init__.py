"""Purpose: L2 reality verification for digital-state claims.
Governance scope: detect digital state versus reality state divergence.
Dependencies: shared contract base helpers.
Invariants:
  - Verification compares at least one digital observation with one reality observation.
  - Divergence blocks verified closure until new sensing reconciles the claim.
  - Results are deterministic for identical observation sets.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from mcoi_runtime.contracts._base import ContractRecord, require_non_empty_text, require_unit_float


class RealityVerificationStatus(StrEnum):
    VERIFIED = "verified"
    DIVERGED = "diverged"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True, slots=True)
class RealityObservation(ContractRecord):
    source: str
    claim: str
    state: str
    confidence: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "source", require_non_empty_text(self.source, "source"))
        object.__setattr__(self, "claim", require_non_empty_text(self.claim, "claim"))
        object.__setattr__(self, "state", require_non_empty_text(self.state, "state"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))


@dataclass(frozen=True, slots=True)
class RealityVerificationResult(ContractRecord):
    status: RealityVerificationStatus
    claim: str
    digital_state: str
    reality_state: str
    confidence_delta: float
    reasons: tuple[str, ...]


def verify_reality_state(
    *,
    claim: str,
    digital_observation: RealityObservation | None,
    reality_observation: RealityObservation | None,
) -> RealityVerificationResult:
    """Compare digital state against reality state before verified closure."""
    normalized_claim = require_non_empty_text(claim, "claim")
    if digital_observation is None or reality_observation is None:
        return RealityVerificationResult(
            status=RealityVerificationStatus.INSUFFICIENT_EVIDENCE,
            claim=normalized_claim,
            digital_state=digital_observation.state if digital_observation else "",
            reality_state=reality_observation.state if reality_observation else "",
            confidence_delta=0.0,
            reasons=("digital_and_reality_observations_required",),
        )
    confidence_delta = abs(digital_observation.confidence - reality_observation.confidence)
    if digital_observation.state != reality_observation.state:
        return RealityVerificationResult(
            status=RealityVerificationStatus.DIVERGED,
            claim=normalized_claim,
            digital_state=digital_observation.state,
            reality_state=reality_observation.state,
            confidence_delta=confidence_delta,
            reasons=("digital_state_not_equal_reality_state",),
        )
    return RealityVerificationResult(
        status=RealityVerificationStatus.VERIFIED,
        claim=normalized_claim,
        digital_state=digital_observation.state,
        reality_state=reality_observation.state,
        confidence_delta=confidence_delta,
        reasons=("digital_and_reality_state_match",),
    )
