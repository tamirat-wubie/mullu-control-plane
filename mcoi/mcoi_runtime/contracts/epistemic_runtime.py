"""Purpose: epistemic governance / knowledge trust runtime contracts.
Governance scope: typed descriptors for knowledge claims, evidence sources,
    trust assessments, source reliability, claim conflicts, epistemic decisions,
    assessments, violations, snapshots, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every record references a tenant.
  - All outputs are frozen and traceable.
  - Confidence and reliability scores are unit floats [0.0, 1.0].
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class KnowledgeStatus(Enum):
    """Lifecycle status of a knowledge claim."""
    OBSERVED = "observed"
    INFERRED = "inferred"
    SIMULATED = "simulated"
    REPORTED = "reported"
    PROVEN = "proven"
    RETRACTED = "retracted"


class EvidenceOrigin(Enum):
    """Origin category of an evidence source."""
    DIRECT_OBSERVATION = "direct_observation"
    INSTRUMENT = "instrument"
    HUMAN_REPORT = "human_report"
    SYSTEM_LOG = "system_log"
    INFERENCE = "inference"
    SIMULATION = "simulation"
    EXTERNAL_SOURCE = "external_source"


class TrustLevel(Enum):
    """Trust level assigned to a claim or assessment."""
    VERIFIED = "verified"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    UNTRUSTED = "untrusted"
    UNKNOWN = "unknown"


class AssertionMode(Enum):
    """Mode of a knowledge assertion."""
    FACTUAL = "factual"
    HYPOTHETICAL = "hypothetical"
    CONDITIONAL = "conditional"
    SPECULATIVE = "speculative"


class ConflictDisposition(Enum):
    """Disposition of a claim conflict."""
    UNRESOLVED = "unresolved"
    FIRST_WINS = "first_wins"
    SECOND_WINS = "second_wins"
    MERGED = "merged"
    DEFERRED = "deferred"


class EpistemicRiskLevel(Enum):
    """Risk level for epistemic assessments."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class KnowledgeClaim(ContractRecord):
    """A knowledge claim registered in the epistemic runtime."""
    claim_id: str
    tenant_id: str
    content: str
    status: KnowledgeStatus
    assertion_mode: AssertionMode
    trust_level: TrustLevel
    source_ref: str
    confidence: float
    created_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.claim_id, "claim_id")
        require_non_empty_text(self.tenant_id, "tenant_id")
        require_non_empty_text(self.content, "content")
        if not isinstance(self.status, KnowledgeStatus):
            raise ValueError("status must be a KnowledgeStatus")
        if not isinstance(self.assertion_mode, AssertionMode):
            raise ValueError("assertion_mode must be an AssertionMode")
        if not isinstance(self.trust_level, TrustLevel):
            raise ValueError("trust_level must be a TrustLevel")
        require_non_empty_text(self.source_ref, "source_ref")
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class EvidenceSource(ContractRecord):
    """An evidence source registered in the epistemic runtime."""
    source_id: str
    tenant_id: str
    display_name: str
    origin: EvidenceOrigin
    reliability_score: float
    claim_count: int
    created_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.source_id, "source_id")
        require_non_empty_text(self.tenant_id, "tenant_id")
        require_non_empty_text(self.display_name, "display_name")
        if not isinstance(self.origin, EvidenceOrigin):
            raise ValueError("origin must be an EvidenceOrigin")
        object.__setattr__(self, "reliability_score", require_unit_float(self.reliability_score, "reliability_score"))
        object.__setattr__(self, "claim_count", require_non_negative_int(self.claim_count, "claim_count"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class TrustAssessment(ContractRecord):
    """Trust assessment combining claim confidence and source reliability."""
    assessment_id: str
    tenant_id: str
    claim_ref: str
    source_ref: str
    trust_level: TrustLevel
    confidence: float
    basis: str
    assessed_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.assessment_id, "assessment_id")
        require_non_empty_text(self.tenant_id, "tenant_id")
        require_non_empty_text(self.claim_ref, "claim_ref")
        require_non_empty_text(self.source_ref, "source_ref")
        if not isinstance(self.trust_level, TrustLevel):
            raise ValueError("trust_level must be a TrustLevel")
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        require_non_empty_text(self.basis, "basis")
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class SourceReliabilityRecord(ContractRecord):
    """Record of a source reliability update."""
    record_id: str
    tenant_id: str
    source_ref: str
    previous_score: float
    updated_score: float
    reason: str
    updated_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.record_id, "record_id")
        require_non_empty_text(self.tenant_id, "tenant_id")
        require_non_empty_text(self.source_ref, "source_ref")
        object.__setattr__(self, "previous_score", require_unit_float(self.previous_score, "previous_score"))
        object.__setattr__(self, "updated_score", require_unit_float(self.updated_score, "updated_score"))
        require_non_empty_text(self.reason, "reason")
        require_datetime_text(self.updated_at, "updated_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class ClaimConflict(ContractRecord):
    """Conflict between two knowledge claims."""
    conflict_id: str
    tenant_id: str
    claim_a_ref: str
    claim_b_ref: str
    disposition: ConflictDisposition
    resolution_basis: str
    detected_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.conflict_id, "conflict_id")
        require_non_empty_text(self.tenant_id, "tenant_id")
        require_non_empty_text(self.claim_a_ref, "claim_a_ref")
        require_non_empty_text(self.claim_b_ref, "claim_b_ref")
        if not isinstance(self.disposition, ConflictDisposition):
            raise ValueError("disposition must be a ConflictDisposition")
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class EpistemicDecision(ContractRecord):
    """A decision made in the epistemic runtime."""
    decision_id: str
    tenant_id: str
    claim_ref: str
    disposition: str
    reason: str
    decided_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.decision_id, "decision_id")
        require_non_empty_text(self.tenant_id, "tenant_id")
        require_non_empty_text(self.claim_ref, "claim_ref")
        require_non_empty_text(self.disposition, "disposition")
        require_non_empty_text(self.reason, "reason")
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class EpistemicAssessment(ContractRecord):
    """Aggregate epistemic assessment for a tenant."""
    assessment_id: str
    tenant_id: str
    total_claims: int
    total_sources: int
    total_conflicts: int
    avg_trust: float
    assessed_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.assessment_id, "assessment_id")
        require_non_empty_text(self.tenant_id, "tenant_id")
        object.__setattr__(self, "total_claims", require_non_negative_int(self.total_claims, "total_claims"))
        object.__setattr__(self, "total_sources", require_non_negative_int(self.total_sources, "total_sources"))
        object.__setattr__(self, "total_conflicts", require_non_negative_int(self.total_conflicts, "total_conflicts"))
        object.__setattr__(self, "avg_trust", require_unit_float(self.avg_trust, "avg_trust"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class EpistemicViolation(ContractRecord):
    """A violation detected in the epistemic runtime."""
    violation_id: str
    tenant_id: str
    operation: str
    reason: str
    detected_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.violation_id, "violation_id")
        require_non_empty_text(self.tenant_id, "tenant_id")
        require_non_empty_text(self.operation, "operation")
        require_non_empty_text(self.reason, "reason")
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class EpistemicSnapshot(ContractRecord):
    """Point-in-time snapshot of epistemic runtime state."""
    snapshot_id: str
    tenant_id: str
    total_claims: int
    total_sources: int
    total_assessments: int
    total_conflicts: int
    total_reliability_updates: int
    total_violations: int
    captured_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.snapshot_id, "snapshot_id")
        require_non_empty_text(self.tenant_id, "tenant_id")
        object.__setattr__(self, "total_claims", require_non_negative_int(self.total_claims, "total_claims"))
        object.__setattr__(self, "total_sources", require_non_negative_int(self.total_sources, "total_sources"))
        object.__setattr__(self, "total_assessments", require_non_negative_int(self.total_assessments, "total_assessments"))
        object.__setattr__(self, "total_conflicts", require_non_negative_int(self.total_conflicts, "total_conflicts"))
        object.__setattr__(self, "total_reliability_updates", require_non_negative_int(self.total_reliability_updates, "total_reliability_updates"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class EpistemicClosureReport(ContractRecord):
    """Final closure report for epistemic runtime."""
    report_id: str
    tenant_id: str
    total_claims: int
    total_sources: int
    total_conflicts: int
    total_violations: int
    created_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.report_id, "report_id")
        require_non_empty_text(self.tenant_id, "tenant_id")
        object.__setattr__(self, "total_claims", require_non_negative_int(self.total_claims, "total_claims"))
        object.__setattr__(self, "total_sources", require_non_negative_int(self.total_sources, "total_sources"))
        object.__setattr__(self, "total_conflicts", require_non_negative_int(self.total_conflicts, "total_conflicts"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
