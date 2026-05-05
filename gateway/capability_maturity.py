"""Capability maturity assessment.

Purpose: derive bounded capability maturity from explicit evidence flags.
Governance scope: capability readiness, promotion claims, recovery evidence,
    worker evidence, and autonomy controls.
Dependencies: dataclasses and canonical command-spine hashing.
Invariants:
  - Maturity is derived from explicit evidence, never declared directly.
  - Effect-bearing production claims require live write evidence.
  - Production readiness requires worker deployment and recovery evidence.
  - C7 autonomy requires bounded autonomy controls.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any

from gateway.command_spine import canonical_hash


MATURITY_LEVELS = ("C0", "C1", "C2", "C3", "C4", "C5", "C6", "C7")


@dataclass(frozen=True, slots=True)
class CapabilityMaturityEvidence:
    """Evidence inputs for one capability maturity assessment."""

    capability_id: str
    schema_valid: bool = False
    policy_bound: bool = False
    mock_eval_passed: bool = False
    sandbox_receipt_valid: bool = False
    live_read_receipt_valid: bool = False
    live_write_receipt_valid: bool = False
    worker_deployment_bound: bool = False
    recovery_evidence_present: bool = False
    autonomy_controls_bounded: bool = False
    effect_bearing: bool = False
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.capability_id.strip():
            raise ValueError("capability_id_required")
        object.__setattr__(self, "capability_id", self.capability_id.strip())
        object.__setattr__(self, "evidence_refs", tuple(str(ref) for ref in self.evidence_refs))


@dataclass(frozen=True, slots=True)
class CapabilityMaturityAssessment:
    """Derived readiness assessment for one capability."""

    assessment_id: str
    capability_id: str
    maturity_level: str
    production_ready: bool
    autonomy_ready: bool
    blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    assessment_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.maturity_level not in MATURITY_LEVELS:
            raise ValueError("maturity_level_invalid")
        if self.production_ready and self.maturity_level not in {"C6", "C7"}:
            raise ValueError("production_requires_C6_or_C7")
        if self.autonomy_ready and self.maturity_level != "C7":
            raise ValueError("autonomy_requires_C7")
        if self.autonomy_ready and not self.production_ready:
            raise ValueError("autonomy_requires_production_readiness")
        object.__setattr__(self, "blockers", tuple(str(blocker) for blocker in self.blockers))
        object.__setattr__(self, "evidence_refs", tuple(str(ref) for ref in self.evidence_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))


class CapabilityMaturityAssessor:
    """Derive maturity from evidence flags and block overclaims."""

    def assess(self, evidence: CapabilityMaturityEvidence) -> CapabilityMaturityAssessment:
        """Return a deterministic maturity assessment for one capability."""
        production_blockers = _production_blockers(evidence)
        autonomy_blockers = _autonomy_blockers(evidence, production_blockers)
        maturity_level = _maturity_level(evidence)
        production_ready = not production_blockers and maturity_level in {"C6", "C7"}
        autonomy_ready = production_ready and evidence.autonomy_controls_bounded
        assessment = CapabilityMaturityAssessment(
            assessment_id="pending",
            capability_id=evidence.capability_id,
            maturity_level=maturity_level,
            production_ready=production_ready,
            autonomy_ready=autonomy_ready,
            blockers=tuple(dict.fromkeys((*production_blockers, *autonomy_blockers))),
            evidence_refs=evidence.evidence_refs,
            metadata={
                "effect_bearing": evidence.effect_bearing,
                "assessment_is_not_promotion": True,
            },
        )
        assessment_hash = canonical_hash(asdict(assessment))
        return replace(
            assessment,
            assessment_id=f"capability-maturity-{assessment_hash[:16]}",
            assessment_hash=assessment_hash,
        )


def _maturity_level(evidence: CapabilityMaturityEvidence) -> str:
    if not evidence.schema_valid:
        return "C0"
    if not evidence.policy_bound:
        return "C1"
    if not evidence.mock_eval_passed:
        return "C2"
    if not evidence.sandbox_receipt_valid:
        return "C3"
    if not evidence.live_read_receipt_valid:
        return "C4"
    if evidence.effect_bearing and not evidence.live_write_receipt_valid:
        return "C4"
    if not evidence.worker_deployment_bound or not evidence.recovery_evidence_present:
        return "C5"
    if not evidence.autonomy_controls_bounded:
        return "C6"
    return "C7"


def _production_blockers(evidence: CapabilityMaturityEvidence) -> tuple[str, ...]:
    blockers: list[str] = []
    if not evidence.schema_valid:
        blockers.append("schema_evidence_missing")
    if not evidence.policy_bound:
        blockers.append("policy_evidence_missing")
    if not evidence.mock_eval_passed:
        blockers.append("eval_evidence_missing")
    if not evidence.sandbox_receipt_valid:
        blockers.append("sandbox_receipt_missing")
    if not evidence.live_read_receipt_valid:
        blockers.append("live_read_receipt_missing")
    if evidence.effect_bearing and not evidence.live_write_receipt_valid:
        blockers.append("effect_bearing_production_requires_live_write")
    if not evidence.worker_deployment_bound:
        blockers.append("worker_deployment_evidence_missing")
    if not evidence.recovery_evidence_present:
        blockers.append("recovery_evidence_missing")
    return tuple(blockers)


def _autonomy_blockers(
    evidence: CapabilityMaturityEvidence,
    production_blockers: tuple[str, ...],
) -> tuple[str, ...]:
    blockers: list[str] = []
    if production_blockers and evidence.autonomy_controls_bounded:
        blockers.append("autonomy_requires_production_readiness")
    if not evidence.autonomy_controls_bounded:
        blockers.append("autonomy_controls_missing")
    return tuple(blockers)
