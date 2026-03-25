"""Purpose: research workflow runtime contracts.
Governance scope: typed descriptors for hypotheses, studies, experiments,
    literature, evidence synthesis, peer review, assessments, and snapshots.
Dependencies: _base contract utilities.
Invariants:
  - Every research artifact references a tenant.
  - Evidence-free synthesis is never marked verified.
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
    require_non_negative_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ResearchStatus(Enum):
    """Overall status of a research effort."""
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    CANCELLED = "cancelled"


class HypothesisStatus(Enum):
    """Status of a hypothesis."""
    PROPOSED = "proposed"
    UNDER_TEST = "under_test"
    SUPPORTED = "supported"
    REFUTED = "refuted"
    INCONCLUSIVE = "inconclusive"


class StudyStatus(Enum):
    """Status of a study protocol."""
    DRAFT = "draft"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ExperimentStatus(Enum):
    """Status of an experiment run."""
    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EvidenceStrength(Enum):
    """Strength of evidence."""
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    CONTRADICTORY = "contradictory"


class PublicationDisposition(Enum):
    """Disposition of a publication/report."""
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    ACCEPTED = "accepted"
    PUBLISHED = "published"
    REJECTED = "rejected"
    RETRACTED = "retracted"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HypothesisRecord(ContractRecord):
    """A research hypothesis."""

    hypothesis_id: str = ""
    tenant_id: str = ""
    question_ref: str = ""
    statement: str = ""
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    confidence: float = 0.0
    evidence_count: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "hypothesis_id", require_non_empty_text(self.hypothesis_id, "hypothesis_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "question_ref", require_non_empty_text(self.question_ref, "question_ref"))
        object.__setattr__(self, "statement", require_non_empty_text(self.statement, "statement"))
        if not isinstance(self.status, HypothesisStatus):
            raise ValueError("status must be a HypothesisStatus")
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "evidence_count", require_non_negative_int(self.evidence_count, "evidence_count"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ResearchQuestion(ContractRecord):
    """A research question driving investigation."""

    question_id: str = ""
    tenant_id: str = ""
    title: str = ""
    description: str = ""
    status: ResearchStatus = ResearchStatus.DRAFT
    hypothesis_count: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "question_id", require_non_empty_text(self.question_id, "question_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))
        if not isinstance(self.status, ResearchStatus):
            raise ValueError("status must be a ResearchStatus")
        object.__setattr__(self, "hypothesis_count", require_non_negative_int(self.hypothesis_count, "hypothesis_count"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class StudyProtocol(ContractRecord):
    """A study protocol governing experiment design."""

    study_id: str = ""
    tenant_id: str = ""
    title: str = ""
    hypothesis_ref: str = ""
    status: StudyStatus = StudyStatus.DRAFT
    experiment_count: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "study_id", require_non_empty_text(self.study_id, "study_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        object.__setattr__(self, "hypothesis_ref", require_non_empty_text(self.hypothesis_ref, "hypothesis_ref"))
        if not isinstance(self.status, StudyStatus):
            raise ValueError("status must be a StudyStatus")
        object.__setattr__(self, "experiment_count", require_non_negative_int(self.experiment_count, "experiment_count"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ExperimentRun(ContractRecord):
    """A single experiment run within a study."""

    experiment_id: str = ""
    tenant_id: str = ""
    study_ref: str = ""
    status: ExperimentStatus = ExperimentStatus.PLANNED
    result_summary: str = ""
    confidence: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "experiment_id", require_non_empty_text(self.experiment_id, "experiment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "study_ref", require_non_empty_text(self.study_ref, "study_ref"))
        if not isinstance(self.status, ExperimentStatus):
            raise ValueError("status must be an ExperimentStatus")
        object.__setattr__(self, "result_summary", require_non_empty_text(self.result_summary, "result_summary"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class LiteraturePacket(ContractRecord):
    """A literature review packet."""

    packet_id: str = ""
    tenant_id: str = ""
    hypothesis_ref: str = ""
    title: str = ""
    source_count: int = 0
    relevance_score: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "packet_id", require_non_empty_text(self.packet_id, "packet_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "hypothesis_ref", require_non_empty_text(self.hypothesis_ref, "hypothesis_ref"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        object.__setattr__(self, "source_count", require_non_negative_int(self.source_count, "source_count"))
        object.__setattr__(self, "relevance_score", require_unit_float(self.relevance_score, "relevance_score"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class EvidenceSynthesis(ContractRecord):
    """A synthesis of evidence from experiments and literature."""

    synthesis_id: str = ""
    tenant_id: str = ""
    hypothesis_ref: str = ""
    strength: EvidenceStrength = EvidenceStrength.WEAK
    experiment_count: int = 0
    literature_count: int = 0
    contradiction_count: int = 0
    confidence: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "synthesis_id", require_non_empty_text(self.synthesis_id, "synthesis_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "hypothesis_ref", require_non_empty_text(self.hypothesis_ref, "hypothesis_ref"))
        if not isinstance(self.strength, EvidenceStrength):
            raise ValueError("strength must be an EvidenceStrength")
        object.__setattr__(self, "experiment_count", require_non_negative_int(self.experiment_count, "experiment_count"))
        object.__setattr__(self, "literature_count", require_non_negative_int(self.literature_count, "literature_count"))
        object.__setattr__(self, "contradiction_count", require_non_negative_int(self.contradiction_count, "contradiction_count"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PeerReviewRecord(ContractRecord):
    """A peer review of research output."""

    review_id: str = ""
    tenant_id: str = ""
    target_ref: str = ""
    reviewer_ref: str = ""
    disposition: PublicationDisposition = PublicationDisposition.IN_REVIEW
    comments: str = ""
    confidence: float = 0.0
    reviewed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "review_id", require_non_empty_text(self.review_id, "review_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "target_ref", require_non_empty_text(self.target_ref, "target_ref"))
        object.__setattr__(self, "reviewer_ref", require_non_empty_text(self.reviewer_ref, "reviewer_ref"))
        if not isinstance(self.disposition, PublicationDisposition):
            raise ValueError("disposition must be a PublicationDisposition")
        object.__setattr__(self, "comments", require_non_empty_text(self.comments, "comments"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        require_datetime_text(self.reviewed_at, "reviewed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ResearchAssessment(ContractRecord):
    """Assessment of research progress and quality."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_questions: int = 0
    total_hypotheses: int = 0
    total_experiments: int = 0
    total_syntheses: int = 0
    total_reviews: int = 0
    completion_rate: float = 0.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_questions", require_non_negative_int(self.total_questions, "total_questions"))
        object.__setattr__(self, "total_hypotheses", require_non_negative_int(self.total_hypotheses, "total_hypotheses"))
        object.__setattr__(self, "total_experiments", require_non_negative_int(self.total_experiments, "total_experiments"))
        object.__setattr__(self, "total_syntheses", require_non_negative_int(self.total_syntheses, "total_syntheses"))
        object.__setattr__(self, "total_reviews", require_non_negative_int(self.total_reviews, "total_reviews"))
        object.__setattr__(self, "completion_rate", require_unit_float(self.completion_rate, "completion_rate"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ResearchSnapshot(ContractRecord):
    """Point-in-time snapshot of research runtime state."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_questions: int = 0
    total_hypotheses: int = 0
    total_studies: int = 0
    total_experiments: int = 0
    total_literature: int = 0
    total_syntheses: int = 0
    total_reviews: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_questions", require_non_negative_int(self.total_questions, "total_questions"))
        object.__setattr__(self, "total_hypotheses", require_non_negative_int(self.total_hypotheses, "total_hypotheses"))
        object.__setattr__(self, "total_studies", require_non_negative_int(self.total_studies, "total_studies"))
        object.__setattr__(self, "total_experiments", require_non_negative_int(self.total_experiments, "total_experiments"))
        object.__setattr__(self, "total_literature", require_non_negative_int(self.total_literature, "total_literature"))
        object.__setattr__(self, "total_syntheses", require_non_negative_int(self.total_syntheses, "total_syntheses"))
        object.__setattr__(self, "total_reviews", require_non_negative_int(self.total_reviews, "total_reviews"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ResearchClosureReport(ContractRecord):
    """Closure report for research runtime."""

    report_id: str = ""
    tenant_id: str = ""
    total_questions: int = 0
    total_hypotheses: int = 0
    total_studies: int = 0
    total_experiments: int = 0
    total_syntheses: int = 0
    total_reviews: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_questions", require_non_negative_int(self.total_questions, "total_questions"))
        object.__setattr__(self, "total_hypotheses", require_non_negative_int(self.total_hypotheses, "total_hypotheses"))
        object.__setattr__(self, "total_studies", require_non_negative_int(self.total_studies, "total_studies"))
        object.__setattr__(self, "total_experiments", require_non_negative_int(self.total_experiments, "total_experiments"))
        object.__setattr__(self, "total_syntheses", require_non_negative_int(self.total_syntheses, "total_syntheses"))
        object.__setattr__(self, "total_reviews", require_non_negative_int(self.total_reviews, "total_reviews"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
