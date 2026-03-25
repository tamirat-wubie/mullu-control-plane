"""Purpose: knowledge search / retrieval / evidence query runtime contracts.
Governance scope: typed descriptors for knowledge queries, filters, evidence
    references, match records, ranked results, query executions, evidence
    bundles, snapshots, violations, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every query references a tenant and scope.
  - Cross-tenant queries are blocked fail-closed.
  - Completed queries cannot be re-executed.
  - All outputs are frozen.
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
    require_non_negative_float,
    require_non_negative_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class QueryStatus(Enum):
    """Status of a knowledge query."""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class QueryScope(Enum):
    """Scope boundary for a query."""
    TENANT = "tenant"
    WORKSPACE = "workspace"
    ENVIRONMENT = "environment"
    SERVICE = "service"
    PROGRAM = "program"
    GLOBAL = "global"


class EvidenceKind(Enum):
    """Kind of evidence referenced."""
    RECORD = "record"
    CASE = "case"
    ASSURANCE = "assurance"
    REPORTING = "reporting"
    ARTIFACT = "artifact"
    MEMORY = "memory"


class MatchDisposition(Enum):
    """Disposition of a match in search results."""
    EXACT = "exact"
    PARTIAL = "partial"
    RELATED = "related"
    EXCLUDED = "excluded"


class RankingStrategy(Enum):
    """Strategy for ranking search results."""
    RELEVANCE = "relevance"
    RECENCY = "recency"
    CONFIDENCE = "confidence"
    SEVERITY = "severity"


class QueryResultStatus(Enum):
    """Status of a query result set."""
    COMPLETE = "complete"
    PARTIAL = "partial"
    EMPTY = "empty"
    TRUNCATED = "truncated"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class KnowledgeQuery(ContractRecord):
    """A typed knowledge query."""

    query_id: str = ""
    tenant_id: str = ""
    scope: QueryScope = QueryScope.TENANT
    scope_ref_id: str = ""
    search_text: str = ""
    status: QueryStatus = QueryStatus.PENDING
    max_results: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "query_id", require_non_empty_text(self.query_id, "query_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.scope, QueryScope):
            raise ValueError("scope must be a QueryScope")
        if not isinstance(self.status, QueryStatus):
            raise ValueError("status must be a QueryStatus")
        object.__setattr__(self, "max_results", require_non_negative_int(self.max_results, "max_results"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class QueryFilter(ContractRecord):
    """A filter applied to a knowledge query."""

    filter_id: str = ""
    query_id: str = ""
    field_name: str = ""
    field_value: str = ""
    evidence_kind: EvidenceKind = EvidenceKind.RECORD
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "filter_id", require_non_empty_text(self.filter_id, "filter_id"))
        object.__setattr__(self, "query_id", require_non_empty_text(self.query_id, "query_id"))
        object.__setattr__(self, "field_name", require_non_empty_text(self.field_name, "field_name"))
        if not isinstance(self.evidence_kind, EvidenceKind):
            raise ValueError("evidence_kind must be an EvidenceKind")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class EvidenceReference(ContractRecord):
    """A reference to a piece of evidence."""

    reference_id: str = ""
    source_id: str = ""
    evidence_kind: EvidenceKind = EvidenceKind.RECORD
    tenant_id: str = ""
    scope_ref_id: str = ""
    title: str = ""
    confidence: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reference_id", require_non_empty_text(self.reference_id, "reference_id"))
        object.__setattr__(self, "source_id", require_non_empty_text(self.source_id, "source_id"))
        if not isinstance(self.evidence_kind, EvidenceKind):
            raise ValueError("evidence_kind must be an EvidenceKind")
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class MatchRecord(ContractRecord):
    """A match from a knowledge search."""

    match_id: str = ""
    query_id: str = ""
    reference_id: str = ""
    disposition: MatchDisposition = MatchDisposition.EXACT
    relevance_score: float = 0.0
    matched_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "match_id", require_non_empty_text(self.match_id, "match_id"))
        object.__setattr__(self, "query_id", require_non_empty_text(self.query_id, "query_id"))
        object.__setattr__(self, "reference_id", require_non_empty_text(self.reference_id, "reference_id"))
        if not isinstance(self.disposition, MatchDisposition):
            raise ValueError("disposition must be a MatchDisposition")
        object.__setattr__(self, "relevance_score", require_unit_float(self.relevance_score, "relevance_score"))
        require_datetime_text(self.matched_at, "matched_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RankedResult(ContractRecord):
    """A ranked result from a knowledge query."""

    result_id: str = ""
    query_id: str = ""
    reference_id: str = ""
    rank: int = 0
    score: float = 0.0
    ranking_strategy: RankingStrategy = RankingStrategy.RELEVANCE
    ranked_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "result_id", require_non_empty_text(self.result_id, "result_id"))
        object.__setattr__(self, "query_id", require_non_empty_text(self.query_id, "query_id"))
        object.__setattr__(self, "reference_id", require_non_empty_text(self.reference_id, "reference_id"))
        object.__setattr__(self, "rank", require_non_negative_int(self.rank, "rank"))
        object.__setattr__(self, "score", require_unit_float(self.score, "score"))
        if not isinstance(self.ranking_strategy, RankingStrategy):
            raise ValueError("ranking_strategy must be a RankingStrategy")
        require_datetime_text(self.ranked_at, "ranked_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class QueryExecutionRecord(ContractRecord):
    """An execution record for a knowledge query."""

    execution_id: str = ""
    query_id: str = ""
    status: QueryResultStatus = QueryResultStatus.COMPLETE
    total_matches: int = 0
    total_results: int = 0
    execution_ms: float = 0.0
    executed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "execution_id", require_non_empty_text(self.execution_id, "execution_id"))
        object.__setattr__(self, "query_id", require_non_empty_text(self.query_id, "query_id"))
        if not isinstance(self.status, QueryResultStatus):
            raise ValueError("status must be a QueryResultStatus")
        object.__setattr__(self, "total_matches", require_non_negative_int(self.total_matches, "total_matches"))
        object.__setattr__(self, "total_results", require_non_negative_int(self.total_results, "total_results"))
        object.__setattr__(self, "execution_ms", require_non_negative_float(self.execution_ms, "execution_ms"))
        require_datetime_text(self.executed_at, "executed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class QuerySnapshot(ContractRecord):
    """Point-in-time knowledge query state snapshot."""

    snapshot_id: str = ""
    total_queries: int = 0
    total_filters: int = 0
    total_references: int = 0
    total_matches: int = 0
    total_results: int = 0
    total_executions: int = 0
    total_bundles: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "total_queries", require_non_negative_int(self.total_queries, "total_queries"))
        object.__setattr__(self, "total_filters", require_non_negative_int(self.total_filters, "total_filters"))
        object.__setattr__(self, "total_references", require_non_negative_int(self.total_references, "total_references"))
        object.__setattr__(self, "total_matches", require_non_negative_int(self.total_matches, "total_matches"))
        object.__setattr__(self, "total_results", require_non_negative_int(self.total_results, "total_results"))
        object.__setattr__(self, "total_executions", require_non_negative_int(self.total_executions, "total_executions"))
        object.__setattr__(self, "total_bundles", require_non_negative_int(self.total_bundles, "total_bundles"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class QueryViolation(ContractRecord):
    """A violation detected in knowledge query processing."""

    violation_id: str = ""
    tenant_id: str = ""
    query_id: str = ""
    operation: str = ""
    reason: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "query_id", require_non_empty_text(self.query_id, "query_id"))
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class EvidenceBundle(ContractRecord):
    """A bundle of evidence assembled from query results."""

    bundle_id: str = ""
    query_id: str = ""
    tenant_id: str = ""
    title: str = ""
    evidence_count: int = 0
    confidence: float = 0.0
    assembled_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "bundle_id", require_non_empty_text(self.bundle_id, "bundle_id"))
        object.__setattr__(self, "query_id", require_non_empty_text(self.query_id, "query_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        object.__setattr__(self, "evidence_count", require_non_negative_int(self.evidence_count, "evidence_count"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        require_datetime_text(self.assembled_at, "assembled_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class KnowledgeQueryClosureReport(ContractRecord):
    """Summary report for knowledge query lifecycle closure."""

    report_id: str = ""
    tenant_id: str = ""
    total_queries: int = 0
    total_executions: int = 0
    total_bundles: int = 0
    total_violations: int = 0
    total_matches: int = 0
    total_results: int = 0
    closed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_queries", require_non_negative_int(self.total_queries, "total_queries"))
        object.__setattr__(self, "total_executions", require_non_negative_int(self.total_executions, "total_executions"))
        object.__setattr__(self, "total_bundles", require_non_negative_int(self.total_bundles, "total_bundles"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        object.__setattr__(self, "total_matches", require_non_negative_int(self.total_matches, "total_matches"))
        object.__setattr__(self, "total_results", require_non_negative_int(self.total_results, "total_results"))
        require_datetime_text(self.closed_at, "closed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class QueryAssessment(ContractRecord):
    """Assessment of knowledge query runtime health."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_queries: int = 0
    total_executions: int = 0
    total_bundles: int = 0
    total_violations: int = 0
    completion_rate: float = 0.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_queries", require_non_negative_int(self.total_queries, "total_queries"))
        object.__setattr__(self, "total_executions", require_non_negative_int(self.total_executions, "total_executions"))
        object.__setattr__(self, "total_bundles", require_non_negative_int(self.total_bundles, "total_bundles"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        object.__setattr__(self, "completion_rate", require_unit_float(self.completion_rate, "completion_rate"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
