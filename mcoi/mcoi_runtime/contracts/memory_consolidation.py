"""Purpose: strategic memory consolidation / long-horizon personalization contracts.
Governance scope: typed descriptors for memory candidates, consolidation decisions,
    retention rules, personalization profiles, memory conflicts, consolidation
    batches, assessments, violations, snapshots, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every record references a tenant.
  - All outputs are frozen and traceable.
  - Consolidation status transitions are governed by batch processing.
  - Conflict resolution must be explicitly completed.
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


class ConsolidationStatus(Enum):
    """Lifecycle status of a memory consolidation candidate."""
    CANDIDATE = "candidate"
    PROMOTED = "promoted"
    DEMOTED = "demoted"
    MERGED = "merged"
    EXPIRED = "expired"
    REJECTED = "rejected"


class MemoryImportance(Enum):
    """Importance level for memory candidates."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    EPHEMERAL = "ephemeral"


class RetentionDisposition(Enum):
    """Retention disposition for memory consolidation."""
    RETAIN = "retain"
    DEMOTE = "demote"
    EXPIRE = "expire"
    ARCHIVE = "archive"
    DELETE = "delete"


class PersonalizationScope(Enum):
    """Scope of personalization for memory."""
    USER = "user"
    ACCOUNT = "account"
    TENANT = "tenant"
    ORGANIZATION = "organization"
    GLOBAL = "global"


class ConflictResolutionMode(Enum):
    """Mode for resolving memory conflicts."""
    NEWER_WINS = "newer_wins"
    OLDER_WINS = "older_wins"
    MERGE = "merge"
    MANUAL = "manual"
    REJECT = "reject"


class MemoryRiskLevel(Enum):
    """Risk level associated with memory consolidation."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MemoryCandidate(ContractRecord):
    """A candidate memory for consolidation."""

    candidate_id: str = ""
    tenant_id: str = ""
    source_ref: str = ""
    content_summary: str = ""
    importance: MemoryImportance = MemoryImportance.MEDIUM
    status: ConsolidationStatus = ConsolidationStatus.CANDIDATE
    occurrence_count: int = 0
    first_seen_at: str = ""
    last_seen_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_id", require_non_empty_text(self.candidate_id, "candidate_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "source_ref", require_non_empty_text(self.source_ref, "source_ref"))
        object.__setattr__(self, "content_summary", require_non_empty_text(self.content_summary, "content_summary"))
        if not isinstance(self.importance, MemoryImportance):
            raise ValueError("importance must be a MemoryImportance")
        if not isinstance(self.status, ConsolidationStatus):
            raise ValueError("status must be a ConsolidationStatus")
        object.__setattr__(self, "occurrence_count", require_non_negative_int(self.occurrence_count, "occurrence_count"))
        require_datetime_text(self.first_seen_at, "first_seen_at")
        require_datetime_text(self.last_seen_at, "last_seen_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ConsolidationDecision(ContractRecord):
    """A consolidation decision for a memory candidate."""

    decision_id: str = ""
    tenant_id: str = ""
    candidate_ref: str = ""
    disposition: ConsolidationStatus = ConsolidationStatus.CANDIDATE
    reason: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "candidate_ref", require_non_empty_text(self.candidate_ref, "candidate_ref"))
        if not isinstance(self.disposition, ConsolidationStatus):
            raise ValueError("disposition must be a ConsolidationStatus")
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RetentionRule(ContractRecord):
    """A retention rule for memory consolidation."""

    rule_id: str = ""
    tenant_id: str = ""
    scope: PersonalizationScope = PersonalizationScope.USER
    disposition: RetentionDisposition = RetentionDisposition.RETAIN
    max_age_days: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "rule_id", require_non_empty_text(self.rule_id, "rule_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.scope, PersonalizationScope):
            raise ValueError("scope must be a PersonalizationScope")
        if not isinstance(self.disposition, RetentionDisposition):
            raise ValueError("disposition must be a RetentionDisposition")
        object.__setattr__(self, "max_age_days", require_non_negative_int(self.max_age_days, "max_age_days"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PersonalizationProfile(ContractRecord):
    """A personalization profile built from consolidated memories."""

    profile_id: str = ""
    tenant_id: str = ""
    identity_ref: str = ""
    scope: PersonalizationScope = PersonalizationScope.USER
    preference_count: int = 0
    confidence: float = 1.0
    updated_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", require_non_empty_text(self.profile_id, "profile_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "identity_ref", require_non_empty_text(self.identity_ref, "identity_ref"))
        if not isinstance(self.scope, PersonalizationScope):
            raise ValueError("scope must be a PersonalizationScope")
        object.__setattr__(self, "preference_count", require_non_negative_int(self.preference_count, "preference_count"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        require_datetime_text(self.updated_at, "updated_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class MemoryConflict(ContractRecord):
    """A conflict detected between two memory candidates."""

    conflict_id: str = ""
    tenant_id: str = ""
    candidate_a_ref: str = ""
    candidate_b_ref: str = ""
    resolution_mode: ConflictResolutionMode = ConflictResolutionMode.NEWER_WINS
    resolved: bool = False
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "conflict_id", require_non_empty_text(self.conflict_id, "conflict_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "candidate_a_ref", require_non_empty_text(self.candidate_a_ref, "candidate_a_ref"))
        object.__setattr__(self, "candidate_b_ref", require_non_empty_text(self.candidate_b_ref, "candidate_b_ref"))
        if not isinstance(self.resolution_mode, ConflictResolutionMode):
            raise ValueError("resolution_mode must be a ConflictResolutionMode")
        if not isinstance(self.resolved, bool):
            raise ValueError("resolved must be a bool")
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ConsolidationBatch(ContractRecord):
    """A batch of consolidation processing results."""

    batch_id: str = ""
    tenant_id: str = ""
    candidate_count: int = 0
    promoted_count: int = 0
    demoted_count: int = 0
    merged_count: int = 0
    processed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "batch_id", require_non_empty_text(self.batch_id, "batch_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "candidate_count", require_non_negative_int(self.candidate_count, "candidate_count"))
        object.__setattr__(self, "promoted_count", require_non_negative_int(self.promoted_count, "promoted_count"))
        object.__setattr__(self, "demoted_count", require_non_negative_int(self.demoted_count, "demoted_count"))
        object.__setattr__(self, "merged_count", require_non_negative_int(self.merged_count, "merged_count"))
        require_datetime_text(self.processed_at, "processed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ConsolidationAssessment(ContractRecord):
    """Assessment of consolidation effectiveness for a tenant."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_candidates: int = 0
    total_promoted: int = 0
    total_demoted: int = 0
    consolidation_rate: float = 1.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_candidates", require_non_negative_int(self.total_candidates, "total_candidates"))
        object.__setattr__(self, "total_promoted", require_non_negative_int(self.total_promoted, "total_promoted"))
        object.__setattr__(self, "total_demoted", require_non_negative_int(self.total_demoted, "total_demoted"))
        object.__setattr__(self, "consolidation_rate", require_unit_float(self.consolidation_rate, "consolidation_rate"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class MemoryConsolidationViolation(ContractRecord):
    """A violation detected in the memory consolidation lifecycle."""

    violation_id: str = ""
    tenant_id: str = ""
    operation: str = ""
    reason: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class MemoryConsolidationSnapshot(ContractRecord):
    """Point-in-time snapshot of memory consolidation state."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_candidates: int = 0
    total_decisions: int = 0
    total_profiles: int = 0
    total_conflicts: int = 0
    total_batches: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_candidates", require_non_negative_int(self.total_candidates, "total_candidates"))
        object.__setattr__(self, "total_decisions", require_non_negative_int(self.total_decisions, "total_decisions"))
        object.__setattr__(self, "total_profiles", require_non_negative_int(self.total_profiles, "total_profiles"))
        object.__setattr__(self, "total_conflicts", require_non_negative_int(self.total_conflicts, "total_conflicts"))
        object.__setattr__(self, "total_batches", require_non_negative_int(self.total_batches, "total_batches"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class MemoryConsolidationClosureReport(ContractRecord):
    """Final closure report for memory consolidation lifecycle."""

    report_id: str = ""
    tenant_id: str = ""
    total_candidates: int = 0
    total_decisions: int = 0
    total_profiles: int = 0
    total_conflicts: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_candidates", require_non_negative_int(self.total_candidates, "total_candidates"))
        object.__setattr__(self, "total_decisions", require_non_negative_int(self.total_decisions, "total_decisions"))
        object.__setattr__(self, "total_profiles", require_non_negative_int(self.total_profiles, "total_profiles"))
        object.__setattr__(self, "total_conflicts", require_non_negative_int(self.total_conflicts, "total_conflicts"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
