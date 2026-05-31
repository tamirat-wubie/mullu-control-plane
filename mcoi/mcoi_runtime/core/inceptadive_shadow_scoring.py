"""Scoring helpers for the InceptaDive Shadow Pass.

Purpose: score shadow findings with bounded suppression and priority signals while
preserving the public/audited Sigma/Mesh production guard.
Governance scope: scoring is advisory only and cannot approve, mutate, promote,
or execute any action.
Dependencies: dataclasses and shared shadow types.
Invariants: suppression lowers confidence, high execution risk raises priority,
and the Mesh denominator guard prevents zero-division in memory-kernel style
calculations.
"""

from __future__ import annotations

from dataclasses import dataclass

from mcoi_runtime.core.inceptadive_shadow_types import ShadowFinding, ShadowSeverity, severity_rank
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


@dataclass(frozen=True)
class ShadowSuppressionVector:
    """Seven suppression factors for shadow findings.

    Each value must be bounded between 0.0 and 1.0, where 0.0 means no
    suppression pressure and 1.0 means maximum suppression pressure.
    """

    evidence_weakness: float = 0.0
    contradiction_pressure: float = 0.0
    staleness: float = 0.0
    scope_mismatch: float = 0.0
    source_authority_weakness: float = 0.0
    privacy_or_safety_risk: float = 0.0
    execution_risk: float = 0.0

    def __post_init__(self) -> None:
        for field_name, value in self.to_dict().items():
            if not 0.0 <= value <= 1.0:
                raise RuntimeCoreInvariantError(field_name + " must be between 0 and 1")

    def to_dict(self) -> dict[str, float]:
        return {
            "evidence_weakness": self.evidence_weakness,
            "contradiction_pressure": self.contradiction_pressure,
            "staleness": self.staleness,
            "scope_mismatch": self.scope_mismatch,
            "source_authority_weakness": self.source_authority_weakness,
            "privacy_or_safety_risk": self.privacy_or_safety_risk,
            "execution_risk": self.execution_risk,
        }

    @property
    def average(self) -> float:
        values = tuple(self.to_dict().values())
        return sum(values) / len(values)

    @property
    def maximum(self) -> float:
        return max(self.to_dict().values())


@dataclass(frozen=True)
class ShadowFindingScore:
    """Advisory score for one shadow finding."""

    confidence: float
    suppression_score: float
    priority: float
    recommended_severity: ShadowSeverity

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise RuntimeCoreInvariantError("confidence must be between 0 and 1")
        if not 0.0 <= self.suppression_score <= 1.0:
            raise RuntimeCoreInvariantError("suppression_score must be between 0 and 1")
        if not 0.0 <= self.priority <= 1.0:
            raise RuntimeCoreInvariantError("priority must be between 0 and 1")

    def to_dict(self) -> dict[str, object]:
        return {
            "confidence": self.confidence,
            "suppression_score": self.suppression_score,
            "priority": self.priority,
            "recommended_severity": self.recommended_severity.value,
        }


def safe_memory_denominator(k: int, j: int) -> int:
    """Return the production-safe Mesh denominator guard.

    This is the applied guard for Sigma/Mesh-style memory-kernel references:
    max(k - j, 1). It prevents the direct Sigma division-by-zero edge.
    """

    return max(k - j, 1)


def score_shadow_finding(
    finding: ShadowFinding,
    suppression: ShadowSuppressionVector | None = None,
    *,
    evidence_strength: float = 1.0,
    resonance_score: float = 0.5,
    governance_fidelity: float = 0.5,
) -> ShadowFindingScore:
    """Score one shadow finding without changing its governance authority."""

    if not 0.0 <= evidence_strength <= 1.0:
        raise RuntimeCoreInvariantError("evidence_strength must be between 0 and 1")
    if not 0.0 <= resonance_score <= 1.0:
        raise RuntimeCoreInvariantError("resonance_score must be between 0 and 1")
    if not 0.0 <= governance_fidelity <= 1.0:
        raise RuntimeCoreInvariantError("governance_fidelity must be between 0 and 1")

    vector = suppression or default_suppression_for_finding(finding)
    severity_component = severity_rank(finding.severity) / severity_rank(ShadowSeverity.CRITICAL)
    suppression_score = _bounded((vector.average * 0.7) + (vector.maximum * 0.3))
    base_confidence = (finding.confidence + evidence_strength + resonance_score + governance_fidelity) / 4
    confidence = _bounded(base_confidence * (1.0 - suppression_score))
    priority = _bounded((severity_component * 0.55) + (vector.execution_risk * 0.25) + (vector.contradiction_pressure * 0.2))
    return ShadowFindingScore(
        confidence=round(confidence, 6),
        suppression_score=round(suppression_score, 6),
        priority=round(priority, 6),
        recommended_severity=_recommended_severity(finding.severity, vector, priority),
    )


def default_suppression_for_finding(finding: ShadowFinding) -> ShadowSuppressionVector:
    """Create a deterministic default suppression vector from a finding."""

    evidence_weakness = 0.25 if not finding.evidence_refs and finding.repair_required else 0.0
    contradiction_pressure = 0.8 if "contradiction" in finding.kind.value else 0.0
    privacy_or_safety_risk = 0.7 if "unsafe" in finding.kind.value else 0.0
    execution_risk = 0.85 if severity_rank(finding.severity) >= severity_rank(ShadowSeverity.HIGH) else 0.15
    return ShadowSuppressionVector(
        evidence_weakness=evidence_weakness,
        contradiction_pressure=contradiction_pressure,
        staleness=0.0,
        scope_mismatch=0.3 if "scope" in finding.kind.value else 0.0,
        source_authority_weakness=0.0,
        privacy_or_safety_risk=privacy_or_safety_risk,
        execution_risk=execution_risk,
    )


def _recommended_severity(
    original: ShadowSeverity,
    vector: ShadowSuppressionVector,
    priority: float,
) -> ShadowSeverity:
    if vector.execution_risk >= 0.9 or priority >= 0.9:
        return ShadowSeverity.CRITICAL
    if vector.execution_risk >= 0.7 or priority >= 0.7:
        return ShadowSeverity.HIGH
    if vector.contradiction_pressure >= 0.5 or priority >= 0.45:
        return ShadowSeverity.MEDIUM
    return original


def _bounded(value: float) -> float:
    return min(1.0, max(0.0, value))
