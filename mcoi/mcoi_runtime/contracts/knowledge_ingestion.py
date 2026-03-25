"""Purpose: canonical knowledge ingestion contract mapping.
Governance scope: knowledge source, procedure candidate, method pattern,
    best practice, failure pattern, lesson, verification, and promotion typing.
Dependencies: docs/26_knowledge_ingestion.md, shared contract base helpers.
Invariants:
  - Every extracted artifact carries explicit source provenance.
  - Confidence values are bounded to [0.0, 1.0] with mandatory reason.
  - Lifecycle follows candidate -> provisional -> verified -> trusted -> deprecated -> blocked.
  - Missing parts are surfaced explicitly; no fabrication.
  - Blocked knowledge MUST NOT be promoted.
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
    require_non_empty_tuple,
    require_unit_float,
)


# --- Classification enums ---


class KnowledgeSourceType(StrEnum):
    DOCUMENT = "document"
    RUNBOOK = "runbook"
    SKILL_RUN = "skill_run"
    WORKFLOW_RUN = "workflow_run"
    INCIDENT = "incident"
    EMAIL_THREAD = "email_thread"
    CODE_REVIEW = "code_review"
    OPERATOR_NOTE = "operator_note"


class KnowledgeLifecycle(StrEnum):
    CANDIDATE = "candidate"
    PROVISIONAL = "provisional"
    VERIFIED = "verified"
    TRUSTED = "trusted"
    DEPRECATED = "deprecated"
    BLOCKED = "blocked"


class KnowledgeScope(StrEnum):
    LOCAL = "local"
    TEAM = "team"
    ORGANIZATION = "organization"


# --- Value objects ---


@dataclass(frozen=True, slots=True)
class ConfidenceLevel(ContractRecord):
    """A typed confidence value with reason and assessment timestamp."""

    value: float
    reason: str
    assessed_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", require_unit_float(self.value, "value"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        object.__setattr__(self, "assessed_at", require_datetime_text(self.assessed_at, "assessed_at"))


@dataclass(frozen=True, slots=True)
class ProcedureStep(ContractRecord):
    """One atomic step within a procedure candidate."""

    step_order: int
    description: str
    skill_id: str | None = None
    requires_approval: bool = False
    verification_point: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.step_order, int) or self.step_order < 0:
            raise ValueError("step_order must be a non-negative integer")
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))
        if self.skill_id is not None:
            object.__setattr__(
                self, "skill_id",
                require_non_empty_text(self.skill_id, "skill_id"),
            )
        if not isinstance(self.requires_approval, bool):
            raise ValueError("requires_approval must be a boolean")
        if not isinstance(self.verification_point, bool):
            raise ValueError("verification_point must be a boolean")


# --- Contract types ---


@dataclass(frozen=True, slots=True)
class KnowledgeSource(ContractRecord):
    """Identity and metadata for an ingestion source."""

    source_id: str
    source_type: KnowledgeSourceType
    reference_id: str
    description: str
    created_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", require_non_empty_text(self.source_id, "source_id"))
        if not isinstance(self.source_type, KnowledgeSourceType):
            raise ValueError("source_type must be a KnowledgeSourceType value")
        object.__setattr__(self, "reference_id", require_non_empty_text(self.reference_id, "reference_id"))
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class ProcedureCandidate(ContractRecord):
    """A procedure extracted from a source with steps and explicitly marked gaps."""

    candidate_id: str
    source_id: str
    name: str
    steps: tuple[ProcedureStep, ...]
    created_at: str
    preconditions: tuple[str, ...] = ()
    postconditions: tuple[str, ...] = ()
    missing_parts: tuple[str, ...] = ()
    confidence: ConfidenceLevel | None = None
    lifecycle: KnowledgeLifecycle = KnowledgeLifecycle.CANDIDATE

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_id", require_non_empty_text(self.candidate_id, "candidate_id"))
        object.__setattr__(self, "source_id", require_non_empty_text(self.source_id, "source_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        frozen_steps = freeze_value(list(self.steps))
        if not frozen_steps:
            raise ValueError("steps must contain at least one ProcedureStep")
        for idx, step in enumerate(frozen_steps):
            if not isinstance(step, ProcedureStep):
                raise ValueError(f"steps[{idx}] must be a ProcedureStep instance")
        object.__setattr__(self, "steps", frozen_steps)
        object.__setattr__(self, "preconditions", freeze_value(list(self.preconditions)))
        object.__setattr__(self, "postconditions", freeze_value(list(self.postconditions)))
        object.__setattr__(self, "missing_parts", freeze_value(list(self.missing_parts)))
        if self.confidence is not None and not isinstance(self.confidence, ConfidenceLevel):
            raise ValueError("confidence must be a ConfidenceLevel instance or None")
        if not isinstance(self.lifecycle, KnowledgeLifecycle):
            raise ValueError("lifecycle must be a KnowledgeLifecycle value")
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class MethodPattern(ContractRecord):
    """A reusable method pattern extracted across one or more sources."""

    pattern_id: str
    source_ids: tuple[str, ...]
    name: str
    description: str
    applicability: str
    steps: tuple[str, ...]
    created_at: str
    confidence: ConfidenceLevel | None = None
    lifecycle: KnowledgeLifecycle = KnowledgeLifecycle.CANDIDATE

    def __post_init__(self) -> None:
        object.__setattr__(self, "pattern_id", require_non_empty_text(self.pattern_id, "pattern_id"))
        object.__setattr__(self, "source_ids", require_non_empty_tuple(self.source_ids, "source_ids"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))
        object.__setattr__(self, "applicability", require_non_empty_text(self.applicability, "applicability"))
        object.__setattr__(self, "steps", require_non_empty_tuple(self.steps, "steps"))
        if self.confidence is not None and not isinstance(self.confidence, ConfidenceLevel):
            raise ValueError("confidence must be a ConfidenceLevel instance or None")
        if not isinstance(self.lifecycle, KnowledgeLifecycle):
            raise ValueError("lifecycle must be a KnowledgeLifecycle value")
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class BestPracticeRecord(ContractRecord):
    """A best practice with conditions and recommendations."""

    practice_id: str
    source_ids: tuple[str, ...]
    name: str
    description: str
    conditions: tuple[str, ...]
    recommendations: tuple[str, ...]
    created_at: str
    confidence: ConfidenceLevel | None = None
    lifecycle: KnowledgeLifecycle = KnowledgeLifecycle.CANDIDATE

    def __post_init__(self) -> None:
        object.__setattr__(self, "practice_id", require_non_empty_text(self.practice_id, "practice_id"))
        object.__setattr__(self, "source_ids", require_non_empty_tuple(self.source_ids, "source_ids"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))
        object.__setattr__(self, "conditions", require_non_empty_tuple(self.conditions, "conditions"))
        object.__setattr__(self, "recommendations", require_non_empty_tuple(self.recommendations, "recommendations"))
        if self.confidence is not None and not isinstance(self.confidence, ConfidenceLevel):
            raise ValueError("confidence must be a ConfidenceLevel instance or None")
        if not isinstance(self.lifecycle, KnowledgeLifecycle):
            raise ValueError("lifecycle must be a KnowledgeLifecycle value")
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class FailurePattern(ContractRecord):
    """A failure mode with trigger conditions and recommended response."""

    pattern_id: str
    source_ids: tuple[str, ...]
    name: str
    trigger_conditions: tuple[str, ...]
    failure_mode: str
    recommended_response: str
    created_at: str
    confidence: ConfidenceLevel | None = None
    lifecycle: KnowledgeLifecycle = KnowledgeLifecycle.CANDIDATE

    def __post_init__(self) -> None:
        object.__setattr__(self, "pattern_id", require_non_empty_text(self.pattern_id, "pattern_id"))
        object.__setattr__(self, "source_ids", require_non_empty_tuple(self.source_ids, "source_ids"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(self, "trigger_conditions", require_non_empty_tuple(self.trigger_conditions, "trigger_conditions"))
        object.__setattr__(self, "failure_mode", require_non_empty_text(self.failure_mode, "failure_mode"))
        object.__setattr__(self, "recommended_response", require_non_empty_text(self.recommended_response, "recommended_response"))
        if self.confidence is not None and not isinstance(self.confidence, ConfidenceLevel):
            raise ValueError("confidence must be a ConfidenceLevel instance or None")
        if not isinstance(self.lifecycle, KnowledgeLifecycle):
            raise ValueError("lifecycle must be a KnowledgeLifecycle value")
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class LessonRecord(ContractRecord):
    """A single lesson learned from a source."""

    lesson_id: str
    source_id: str
    context: str
    action_taken: str
    outcome: str
    lesson: str
    created_at: str
    confidence: ConfidenceLevel | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "lesson_id", require_non_empty_text(self.lesson_id, "lesson_id"))
        object.__setattr__(self, "source_id", require_non_empty_text(self.source_id, "source_id"))
        object.__setattr__(self, "context", require_non_empty_text(self.context, "context"))
        object.__setattr__(self, "action_taken", require_non_empty_text(self.action_taken, "action_taken"))
        object.__setattr__(self, "outcome", require_non_empty_text(self.outcome, "outcome"))
        object.__setattr__(self, "lesson", require_non_empty_text(self.lesson, "lesson"))
        if self.confidence is not None and not isinstance(self.confidence, ConfidenceLevel):
            raise ValueError("confidence must be a ConfidenceLevel instance or None")
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class KnowledgeVerificationResult(ContractRecord):
    """The outcome of verifying a piece of extracted knowledge."""

    knowledge_id: str
    verified: bool
    verifier_id: str
    verification_method: str
    notes: str
    verified_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "knowledge_id", require_non_empty_text(self.knowledge_id, "knowledge_id"))
        if not isinstance(self.verified, bool):
            raise ValueError("verified must be a boolean")
        object.__setattr__(self, "verifier_id", require_non_empty_text(self.verifier_id, "verifier_id"))
        object.__setattr__(self, "verification_method", require_non_empty_text(self.verification_method, "verification_method"))
        if not isinstance(self.notes, str):
            raise ValueError("notes must be a string")
        object.__setattr__(self, "verified_at", require_datetime_text(self.verified_at, "verified_at"))


@dataclass(frozen=True, slots=True)
class KnowledgePromotionDecision(ContractRecord):
    """The decision to promote knowledge from one lifecycle stage to another."""

    knowledge_id: str
    from_lifecycle: KnowledgeLifecycle
    to_lifecycle: KnowledgeLifecycle
    reason: str
    decided_by: str
    decided_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "knowledge_id", require_non_empty_text(self.knowledge_id, "knowledge_id"))
        if not isinstance(self.from_lifecycle, KnowledgeLifecycle):
            raise ValueError("from_lifecycle must be a KnowledgeLifecycle value")
        if not isinstance(self.to_lifecycle, KnowledgeLifecycle):
            raise ValueError("to_lifecycle must be a KnowledgeLifecycle value")
        if self.from_lifecycle == self.to_lifecycle:
            raise ValueError("from_lifecycle and to_lifecycle must be different")
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        object.__setattr__(self, "decided_by", require_non_empty_text(self.decided_by, "decided_by"))
        object.__setattr__(self, "decided_at", require_datetime_text(self.decided_at, "decided_at"))
