"""Purpose: ontology / semantic alignment runtime contracts.
Governance scope: typed descriptors for concepts, relations, schema mappings,
    entity alignments, semantic conflicts, decisions, assessments, and snapshots.
Dependencies: _base contract utilities.
Invariants:
  - Every ontology artifact references a tenant.
  - All outputs are frozen.
  - Canonical forms are non-empty strings.
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


class OntologyStatus(Enum):
    """Overall status of an ontology concept."""
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"
    DRAFT = "draft"


class ConceptKind(Enum):
    """Kind of ontology concept."""
    ENTITY = "entity"
    ATTRIBUTE = "attribute"
    RELATION = "relation"
    ACTION = "action"
    EVENT = "event"
    QUALIFIER = "qualifier"


class MappingDisposition(Enum):
    """Disposition of a schema mapping."""
    EXACT = "exact"
    BROADER = "broader"
    NARROWER = "narrower"
    RELATED = "related"
    UNMATCHED = "unmatched"


class AlignmentStrength(Enum):
    """Strength of an entity alignment."""
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    TENTATIVE = "tentative"


class SemanticConflictStatus(Enum):
    """Status of a semantic conflict."""
    DETECTED = "detected"
    RESOLVED = "resolved"
    DEFERRED = "deferred"
    ACCEPTED = "accepted"


class OntologyRiskLevel(Enum):
    """Risk level for ontology operations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ConceptRecord(ContractRecord):
    """An ontology concept."""

    concept_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    kind: ConceptKind = ConceptKind.ENTITY
    canonical_form: str = ""
    status: OntologyStatus = OntologyStatus.DRAFT
    created_at: str = ""
    metadata: Any = field(default_factory=lambda: freeze_value({}))

    def __post_init__(self) -> None:
        require_non_empty_text(self.concept_id, "concept_id")
        require_non_empty_text(self.tenant_id, "tenant_id")
        require_non_empty_text(self.display_name, "display_name")
        require_non_empty_text(self.canonical_form, "canonical_form")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class ConceptRelation(ContractRecord):
    """A relation between two ontology concepts."""

    relation_id: str = ""
    tenant_id: str = ""
    parent_ref: str = ""
    child_ref: str = ""
    kind: ConceptKind = ConceptKind.RELATION
    strength: AlignmentStrength = AlignmentStrength.STRONG
    created_at: str = ""
    metadata: Any = field(default_factory=lambda: freeze_value({}))

    def __post_init__(self) -> None:
        require_non_empty_text(self.relation_id, "relation_id")
        require_non_empty_text(self.tenant_id, "tenant_id")
        require_non_empty_text(self.parent_ref, "parent_ref")
        require_non_empty_text(self.child_ref, "child_ref")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class SchemaMapping(ContractRecord):
    """A mapping between two schemas."""

    mapping_id: str = ""
    tenant_id: str = ""
    source_schema: str = ""
    target_schema: str = ""
    disposition: MappingDisposition = MappingDisposition.EXACT
    field_count: int = 0
    created_at: str = ""
    metadata: Any = field(default_factory=lambda: freeze_value({}))

    def __post_init__(self) -> None:
        require_non_empty_text(self.mapping_id, "mapping_id")
        require_non_empty_text(self.tenant_id, "tenant_id")
        require_non_empty_text(self.source_schema, "source_schema")
        require_non_empty_text(self.target_schema, "target_schema")
        require_non_negative_int(self.field_count, "field_count")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class EntityAlignment(ContractRecord):
    """An alignment between two entities."""

    alignment_id: str = ""
    tenant_id: str = ""
    source_ref: str = ""
    target_ref: str = ""
    strength: AlignmentStrength = AlignmentStrength.STRONG
    confidence: float = 1.0
    created_at: str = ""
    metadata: Any = field(default_factory=lambda: freeze_value({}))

    def __post_init__(self) -> None:
        require_non_empty_text(self.alignment_id, "alignment_id")
        require_non_empty_text(self.tenant_id, "tenant_id")
        require_non_empty_text(self.source_ref, "source_ref")
        require_non_empty_text(self.target_ref, "target_ref")
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class SemanticConflict(ContractRecord):
    """A detected semantic conflict between two concepts."""

    conflict_id: str = ""
    tenant_id: str = ""
    concept_a_ref: str = ""
    concept_b_ref: str = ""
    status: SemanticConflictStatus = SemanticConflictStatus.DETECTED
    reason: str = ""
    detected_at: str = ""
    metadata: Any = field(default_factory=lambda: freeze_value({}))

    def __post_init__(self) -> None:
        require_non_empty_text(self.conflict_id, "conflict_id")
        require_non_empty_text(self.tenant_id, "tenant_id")
        require_non_empty_text(self.concept_a_ref, "concept_a_ref")
        require_non_empty_text(self.concept_b_ref, "concept_b_ref")
        require_non_empty_text(self.reason, "reason")
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class OntologyDecision(ContractRecord):
    """A decision on an ontology conflict."""

    decision_id: str = ""
    tenant_id: str = ""
    conflict_ref: str = ""
    disposition: str = ""
    reason: str = ""
    decided_at: str = ""
    metadata: Any = field(default_factory=lambda: freeze_value({}))

    def __post_init__(self) -> None:
        require_non_empty_text(self.decision_id, "decision_id")
        require_non_empty_text(self.tenant_id, "tenant_id")
        require_non_empty_text(self.conflict_ref, "conflict_ref")
        require_non_empty_text(self.disposition, "disposition")
        require_non_empty_text(self.reason, "reason")
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class OntologyAssessment(ContractRecord):
    """An assessment of the ontology state."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_concepts: int = 0
    total_mappings: int = 0
    total_conflicts: int = 0
    alignment_score: float = 1.0
    assessed_at: str = ""
    metadata: Any = field(default_factory=lambda: freeze_value({}))

    def __post_init__(self) -> None:
        require_non_empty_text(self.assessment_id, "assessment_id")
        require_non_empty_text(self.tenant_id, "tenant_id")
        require_non_negative_int(self.total_concepts, "total_concepts")
        require_non_negative_int(self.total_mappings, "total_mappings")
        require_non_negative_int(self.total_conflicts, "total_conflicts")
        object.__setattr__(self, "alignment_score", require_unit_float(self.alignment_score, "alignment_score"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class OntologyViolation(ContractRecord):
    """A detected ontology governance violation."""

    violation_id: str = ""
    tenant_id: str = ""
    operation: str = ""
    reason: str = ""
    detected_at: str = ""
    metadata: Any = field(default_factory=lambda: freeze_value({}))

    def __post_init__(self) -> None:
        require_non_empty_text(self.violation_id, "violation_id")
        require_non_empty_text(self.tenant_id, "tenant_id")
        require_non_empty_text(self.operation, "operation")
        require_non_empty_text(self.reason, "reason")
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class OntologySnapshot(ContractRecord):
    """A point-in-time ontology state snapshot."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_concepts: int = 0
    total_relations: int = 0
    total_mappings: int = 0
    total_alignments: int = 0
    total_conflicts: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Any = field(default_factory=lambda: freeze_value({}))

    def __post_init__(self) -> None:
        require_non_empty_text(self.snapshot_id, "snapshot_id")
        require_non_empty_text(self.tenant_id, "tenant_id")
        require_non_negative_int(self.total_concepts, "total_concepts")
        require_non_negative_int(self.total_relations, "total_relations")
        require_non_negative_int(self.total_mappings, "total_mappings")
        require_non_negative_int(self.total_alignments, "total_alignments")
        require_non_negative_int(self.total_conflicts, "total_conflicts")
        require_non_negative_int(self.total_violations, "total_violations")
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class OntologyClosureReport(ContractRecord):
    """A closure report for ontology state."""

    report_id: str = ""
    tenant_id: str = ""
    total_concepts: int = 0
    total_mappings: int = 0
    total_alignments: int = 0
    total_conflicts: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Any = field(default_factory=lambda: freeze_value({}))

    def __post_init__(self) -> None:
        require_non_empty_text(self.report_id, "report_id")
        require_non_empty_text(self.tenant_id, "tenant_id")
        require_non_negative_int(self.total_concepts, "total_concepts")
        require_non_negative_int(self.total_mappings, "total_mappings")
        require_non_negative_int(self.total_alignments, "total_alignments")
        require_non_negative_int(self.total_conflicts, "total_conflicts")
        require_non_negative_int(self.total_violations, "total_violations")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
