"""Purpose: canonical memory mesh contracts for durable cumulative intelligence.
Governance scope: memory record, link, promotion, decay, retrieval, and conflict typing.
Dependencies: shared contract base helpers.
Invariants:
  - Every memory record has explicit type, scope, trust level, and provenance.
  - Memory links reference only existing records (enforced by engine, not contract).
  - Promotions carry rationale and supporting evidence IDs.
  - Decay policies are explicit — no silent expiration.
  - Retrieval results are immutable and deterministic.
  - Confidence is bounded [0.0, 1.0].
  - Superseded records remain accessible but are deprioritized in retrieval.
  - Conflict records are explicit — never silently resolved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_int,
    require_positive_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MemoryType(StrEnum):
    """Classification of what a memory record represents."""

    WORKING = "working"
    EPISODIC = "episodic"
    PROCEDURAL = "procedural"
    SEMANTIC = "semantic"
    STRATEGIC = "strategic"
    OBSERVATION = "observation"
    DECISION = "decision"
    OUTCOME = "outcome"
    INCIDENT = "incident"
    COMMUNICATION = "communication"
    ARTIFACT = "artifact"


class MemoryScope(StrEnum):
    """What organizational boundary a memory is scoped to."""

    GLOBAL = "global"
    DOMAIN = "domain"
    FUNCTION = "function"
    TEAM = "team"
    WORKER = "worker"
    JOB = "job"
    GOAL = "goal"
    WORKFLOW = "workflow"
    EVENT = "event"
    OBLIGATION = "obligation"
    PROVIDER = "provider"
    OPERATOR = "operator"


class MemoryTrustLevel(StrEnum):
    """How much the platform trusts a memory record."""

    UNVERIFIED = "unverified"
    OBSERVED = "observed"
    VERIFIED = "verified"
    OPERATOR_CONFIRMED = "operator_confirmed"
    POLICY_BOUND = "policy_bound"
    DERIVED = "derived"


class MemoryLinkRelation(StrEnum):
    """Typed relationship between two memory records."""

    CAUSED_BY = "caused_by"
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    SUPERSEDES = "supersedes"
    DERIVED_FROM = "derived_from"
    RELATED_TO = "related_to"
    PRECEDED_BY = "preceded_by"
    FOLLOWED_BY = "followed_by"


class DecayMode(StrEnum):
    """How a memory record decays over time."""

    NONE = "none"
    TTL = "ttl"
    CONFIDENCE_DECAY = "confidence_decay"
    ACCESS_BASED = "access_based"


class ConflictResolutionState(StrEnum):
    """State of a memory conflict resolution."""

    UNRESOLVED = "unresolved"
    RESOLVED_MANUAL = "resolved_manual"
    RESOLVED_AUTOMATIC = "resolved_automatic"
    ESCALATED = "escalated"


# ---------------------------------------------------------------------------
# Memory records
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MemoryRecord(ContractRecord):
    """A single memory record with explicit type, scope, trust, and provenance.

    The primary unit of the memory mesh. Every record is traceable
    to source IDs (events, obligations, jobs, etc.) and carries
    explicit confidence and trust level.
    """

    memory_id: str
    memory_type: MemoryType
    scope: MemoryScope
    scope_ref_id: str
    trust_level: MemoryTrustLevel
    title: str
    content: Mapping[str, Any]
    source_ids: tuple[str, ...]
    tags: tuple[str, ...] = ()
    confidence: float = 0.5
    created_at: str = ""
    updated_at: str = ""
    expires_at: str | None = None
    supersedes_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "memory_id", require_non_empty_text(self.memory_id, "memory_id"))
        if not isinstance(self.memory_type, MemoryType):
            raise ValueError("memory_type must be a MemoryType value")
        if not isinstance(self.scope, MemoryScope):
            raise ValueError("scope must be a MemoryScope value")
        object.__setattr__(self, "scope_ref_id", require_non_empty_text(self.scope_ref_id, "scope_ref_id"))
        if not isinstance(self.trust_level, MemoryTrustLevel):
            raise ValueError("trust_level must be a MemoryTrustLevel value")
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        if not isinstance(self.content, Mapping):
            raise ValueError("content must be a mapping")
        object.__setattr__(self, "content", freeze_value(self.content))
        object.__setattr__(self, "source_ids", freeze_value(list(self.source_ids)))
        object.__setattr__(self, "tags", freeze_value(list(self.tags)))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        object.__setattr__(self, "updated_at", require_datetime_text(self.updated_at, "updated_at"))
        if self.expires_at is not None:
            object.__setattr__(self, "expires_at", require_datetime_text(self.expires_at, "expires_at"))
        object.__setattr__(self, "supersedes_ids", freeze_value(list(self.supersedes_ids)))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# Memory links
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MemoryLink(ContractRecord):
    """A typed, weighted edge between two memory records."""

    link_id: str
    from_memory_id: str
    to_memory_id: str
    relation: MemoryLinkRelation
    confidence: float = 1.0
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "link_id", require_non_empty_text(self.link_id, "link_id"))
        object.__setattr__(self, "from_memory_id", require_non_empty_text(self.from_memory_id, "from_memory_id"))
        object.__setattr__(self, "to_memory_id", require_non_empty_text(self.to_memory_id, "to_memory_id"))
        if self.from_memory_id == self.to_memory_id:
            raise ValueError("self-referential memory links are prohibited")
        if not isinstance(self.relation, MemoryLinkRelation):
            raise ValueError("relation must be a MemoryLinkRelation value")
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


# ---------------------------------------------------------------------------
# Memory promotion
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MemoryPromotionRecord(ContractRecord):
    """Record of promoting a memory from one type to another.

    E.g., episodic -> procedural, episodic -> semantic, semantic -> strategic.
    Promotions carry rationale and supporting evidence.
    """

    promotion_id: str
    memory_id: str
    from_type: MemoryType
    to_type: MemoryType
    rationale: str
    supporting_ids: tuple[str, ...]
    confidence: float
    promoted_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "promotion_id", require_non_empty_text(self.promotion_id, "promotion_id"))
        object.__setattr__(self, "memory_id", require_non_empty_text(self.memory_id, "memory_id"))
        if not isinstance(self.from_type, MemoryType):
            raise ValueError("from_type must be a MemoryType value")
        if not isinstance(self.to_type, MemoryType):
            raise ValueError("to_type must be a MemoryType value")
        if self.from_type == self.to_type:
            raise ValueError("promotion must change memory type")
        object.__setattr__(self, "rationale", require_non_empty_text(self.rationale, "rationale"))
        object.__setattr__(self, "supporting_ids", freeze_value(list(self.supporting_ids)))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "promoted_at", require_datetime_text(self.promoted_at, "promoted_at"))


# ---------------------------------------------------------------------------
# Memory decay
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MemoryDecayPolicy(ContractRecord):
    """Policy governing how a memory record decays over time.

    Defines TTL, decay mode, refresh rules, and trust floor
    below which a memory is considered unreliable.
    """

    policy_id: str
    memory_type: MemoryType
    decay_mode: DecayMode
    ttl_seconds: int | None = None
    confidence_floor: float = 0.0
    refresh_on_access: bool = False
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", require_non_empty_text(self.policy_id, "policy_id"))
        if not isinstance(self.memory_type, MemoryType):
            raise ValueError("memory_type must be a MemoryType value")
        if not isinstance(self.decay_mode, DecayMode):
            raise ValueError("decay_mode must be a DecayMode value")
        if self.ttl_seconds is not None:
            if not isinstance(self.ttl_seconds, int) or self.ttl_seconds <= 0:
                raise ValueError("ttl_seconds must be a positive integer")
        object.__setattr__(self, "confidence_floor", require_unit_float(self.confidence_floor, "confidence_floor"))
        if not isinstance(self.refresh_on_access, bool):
            raise ValueError("refresh_on_access must be a boolean")
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


# ---------------------------------------------------------------------------
# Memory retrieval
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MemoryRetrievalQuery(ContractRecord):
    """Structured query for memory retrieval.

    Supports filtering by scope, tags, lineage, trust, type, and time.
    """

    query_id: str
    scope: MemoryScope | None = None
    scope_ref_id: str | None = None
    tags: tuple[str, ...] = ()
    lineage_ids: tuple[str, ...] = ()
    trust_floor: float = 0.0
    memory_types: tuple[MemoryType, ...] = ()
    max_results: int = 100
    as_of: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "query_id", require_non_empty_text(self.query_id, "query_id"))
        if self.scope is not None and not isinstance(self.scope, MemoryScope):
            raise ValueError("scope must be a MemoryScope value or None")
        if self.scope_ref_id is not None:
            object.__setattr__(self, "scope_ref_id", require_non_empty_text(self.scope_ref_id, "scope_ref_id"))
        object.__setattr__(self, "tags", freeze_value(list(self.tags)))
        object.__setattr__(self, "lineage_ids", freeze_value(list(self.lineage_ids)))
        object.__setattr__(self, "trust_floor", require_unit_float(self.trust_floor, "trust_floor"))
        object.__setattr__(self, "memory_types", freeze_value(list(self.memory_types)))
        for mt in self.memory_types:
            if not isinstance(mt, MemoryType):
                raise ValueError("each memory_type must be a MemoryType value")
        if not isinstance(self.max_results, int) or self.max_results < 1:
            raise ValueError("max_results must be a positive integer")
        if self.as_of is not None:
            object.__setattr__(self, "as_of", require_datetime_text(self.as_of, "as_of"))


@dataclass(frozen=True, slots=True)
class MemoryRetrievalResult(ContractRecord):
    """Result of a memory retrieval query."""

    query_id: str
    matched_ids: tuple[str, ...]
    total: int
    retrieved_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "query_id", require_non_empty_text(self.query_id, "query_id"))
        object.__setattr__(self, "matched_ids", freeze_value(list(self.matched_ids)))
        object.__setattr__(self, "total", require_non_negative_int(self.total, "total"))
        object.__setattr__(self, "retrieved_at", require_datetime_text(self.retrieved_at, "retrieved_at"))


# ---------------------------------------------------------------------------
# Memory conflicts
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MemoryConflictRecord(ContractRecord):
    """Explicit record of conflicting memory about the same subject.

    Conflicts are surfaced, never silently resolved.
    """

    conflict_id: str
    conflicting_ids: tuple[str, ...]
    reason: str
    resolution_state: ConflictResolutionState
    resolved_by: str | None = None
    resolution_detail: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "conflict_id", require_non_empty_text(self.conflict_id, "conflict_id"))
        if len(self.conflicting_ids) < 2:
            raise ValueError("conflicting_ids must contain at least two IDs")
        object.__setattr__(self, "conflicting_ids", freeze_value(list(self.conflicting_ids)))
        for cid in self.conflicting_ids:
            require_non_empty_text(cid, "conflicting_id")
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        if not isinstance(self.resolution_state, ConflictResolutionState):
            raise ValueError("resolution_state must be a ConflictResolutionState value")
        if self.resolved_by is not None:
            object.__setattr__(self, "resolved_by", require_non_empty_text(self.resolved_by, "resolved_by"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
