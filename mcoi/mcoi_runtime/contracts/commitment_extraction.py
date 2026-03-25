"""Purpose: canonical commitment extraction contracts.
Governance scope: commitment candidates, approval/rejection signals,
    deadline signals, owner signals, escalation signals, extraction results,
    routing decisions, and promotion records.
Dependencies: shared contract base helpers.
Invariants:
  - Every commitment candidate has explicit type, confidence, and disposition.
  - Extraction results are immutable structured outputs.
  - Ambiguous commitments fail-closed (AMBIGUOUS disposition, no obligation).
  - Promotion records link candidate to obligation.
  - All fields validated at construction time.
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
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CommitmentType(StrEnum):
    """What kind of commitment was extracted."""

    TASK = "task"
    APPROVAL = "approval"
    REVIEW = "review"
    FOLLOW_UP = "follow_up"
    ESCALATION = "escalation"
    DELIVERY = "delivery"
    ACKNOWLEDGEMENT = "acknowledgement"
    DEADLINE = "deadline"
    UNKNOWN = "unknown"


class CommitmentSourceType(StrEnum):
    """Where the commitment signal originated."""

    MESSAGE = "message"
    CALL_TRANSCRIPT = "call_transcript"
    ARTIFACT = "artifact"
    OPERATOR_NOTE = "operator_note"
    BENCHMARK = "benchmark"
    POLICY_DECISION = "policy_decision"


class ExtractionConfidenceLevel(StrEnum):
    """Qualitative confidence band for extraction."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERIFIED = "verified"


class CommitmentDisposition(StrEnum):
    """Current disposition of a commitment candidate."""

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    AMBIGUOUS = "ambiguous"
    BLOCKED = "blocked"


# ---------------------------------------------------------------------------
# Commitment candidate
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CommitmentCandidate(ContractRecord):
    """A single extracted commitment candidate from source text."""

    commitment_id: str
    source_type: CommitmentSourceType
    source_ref_id: str
    commitment_type: CommitmentType
    text_span: str
    normalized_text: str
    proposed_owner_id: str = ""
    proposed_due_at: str = ""
    confidence: float = 0.5
    confidence_level: ExtractionConfidenceLevel = ExtractionConfidenceLevel.MEDIUM
    disposition: CommitmentDisposition = CommitmentDisposition.PROPOSED
    reason: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "commitment_id", require_non_empty_text(self.commitment_id, "commitment_id"))
        if not isinstance(self.source_type, CommitmentSourceType):
            raise ValueError("source_type must be a CommitmentSourceType value")
        object.__setattr__(self, "source_ref_id", require_non_empty_text(self.source_ref_id, "source_ref_id"))
        if not isinstance(self.commitment_type, CommitmentType):
            raise ValueError("commitment_type must be a CommitmentType value")
        object.__setattr__(self, "text_span", require_non_empty_text(self.text_span, "text_span"))
        object.__setattr__(self, "normalized_text", require_non_empty_text(self.normalized_text, "normalized_text"))
        if not isinstance(self.confidence_level, ExtractionConfidenceLevel):
            raise ValueError("confidence_level must be an ExtractionConfidenceLevel value")
        if not isinstance(self.disposition, CommitmentDisposition):
            raise ValueError("disposition must be a CommitmentDisposition value")
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# Approval signal
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ApprovalSignal(ContractRecord):
    """Extracted approval or rejection signal."""

    signal_id: str
    source_ref_id: str
    approved: bool
    text_span: str
    confidence: float = 0.8
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "signal_id", require_non_empty_text(self.signal_id, "signal_id"))
        object.__setattr__(self, "source_ref_id", require_non_empty_text(self.source_ref_id, "source_ref_id"))
        if not isinstance(self.approved, bool):
            raise ValueError("approved must be a boolean")
        object.__setattr__(self, "text_span", require_non_empty_text(self.text_span, "text_span"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


# ---------------------------------------------------------------------------
# Deadline signal
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DeadlineSignal(ContractRecord):
    """Extracted deadline mention."""

    signal_id: str
    source_ref_id: str
    text_span: str
    normalized_deadline: str
    confidence: float = 0.7
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "signal_id", require_non_empty_text(self.signal_id, "signal_id"))
        object.__setattr__(self, "source_ref_id", require_non_empty_text(self.source_ref_id, "source_ref_id"))
        object.__setattr__(self, "text_span", require_non_empty_text(self.text_span, "text_span"))
        object.__setattr__(self, "normalized_deadline", require_non_empty_text(self.normalized_deadline, "normalized_deadline"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


# ---------------------------------------------------------------------------
# Owner signal
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class OwnerSignal(ContractRecord):
    """Extracted owner/assignee mention."""

    signal_id: str
    source_ref_id: str
    text_span: str
    normalized_owner: str
    confidence: float = 0.7
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "signal_id", require_non_empty_text(self.signal_id, "signal_id"))
        object.__setattr__(self, "source_ref_id", require_non_empty_text(self.source_ref_id, "source_ref_id"))
        object.__setattr__(self, "text_span", require_non_empty_text(self.text_span, "text_span"))
        object.__setattr__(self, "normalized_owner", require_non_empty_text(self.normalized_owner, "normalized_owner"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


# ---------------------------------------------------------------------------
# Escalation signal
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EscalationSignal(ContractRecord):
    """Extracted escalation instruction."""

    signal_id: str
    source_ref_id: str
    text_span: str
    target_description: str
    urgency: str = "normal"
    confidence: float = 0.7
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "signal_id", require_non_empty_text(self.signal_id, "signal_id"))
        object.__setattr__(self, "source_ref_id", require_non_empty_text(self.source_ref_id, "source_ref_id"))
        object.__setattr__(self, "text_span", require_non_empty_text(self.text_span, "text_span"))
        object.__setattr__(self, "target_description", require_non_empty_text(self.target_description, "target_description"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


# ---------------------------------------------------------------------------
# Commitment extraction result
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CommitmentExtractionResult(ContractRecord):
    """Complete structured result of extracting commitments from a source."""

    result_id: str
    source_type: CommitmentSourceType
    source_ref_id: str
    candidates: tuple[CommitmentCandidate, ...] = ()
    approvals: tuple[ApprovalSignal, ...] = ()
    deadlines: tuple[DeadlineSignal, ...] = ()
    owners: tuple[OwnerSignal, ...] = ()
    escalations: tuple[EscalationSignal, ...] = ()
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "result_id", require_non_empty_text(self.result_id, "result_id"))
        if not isinstance(self.source_type, CommitmentSourceType):
            raise ValueError("source_type must be a CommitmentSourceType value")
        object.__setattr__(self, "source_ref_id", require_non_empty_text(self.source_ref_id, "source_ref_id"))
        object.__setattr__(self, "candidates", freeze_value(list(self.candidates)))
        for c in self.candidates:
            if not isinstance(c, CommitmentCandidate):
                raise ValueError("each candidate must be a CommitmentCandidate")
        object.__setattr__(self, "approvals", freeze_value(list(self.approvals)))
        for a in self.approvals:
            if not isinstance(a, ApprovalSignal):
                raise ValueError("each approval must be an ApprovalSignal")
        object.__setattr__(self, "deadlines", freeze_value(list(self.deadlines)))
        for d in self.deadlines:
            if not isinstance(d, DeadlineSignal):
                raise ValueError("each deadline must be a DeadlineSignal")
        object.__setattr__(self, "owners", freeze_value(list(self.owners)))
        for o in self.owners:
            if not isinstance(o, OwnerSignal):
                raise ValueError("each owner must be an OwnerSignal")
        object.__setattr__(self, "escalations", freeze_value(list(self.escalations)))
        for e in self.escalations:
            if not isinstance(e, EscalationSignal):
                raise ValueError("each escalation must be an EscalationSignal")
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


# ---------------------------------------------------------------------------
# Commitment routing decision
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CommitmentRoutingDecision(ContractRecord):
    """Routing decision for an extracted commitment candidate."""

    decision_id: str
    commitment_id: str
    routed_to_identity_id: str
    routed_to_obligation_id: str = ""
    reason: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "commitment_id", require_non_empty_text(self.commitment_id, "commitment_id"))
        object.__setattr__(self, "routed_to_identity_id", require_non_empty_text(self.routed_to_identity_id, "routed_to_identity_id"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


# ---------------------------------------------------------------------------
# Commitment promotion record
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CommitmentPromotionRecord(ContractRecord):
    """Record of promoting a commitment candidate to an obligation."""

    promotion_id: str
    commitment_id: str
    obligation_id: str
    promoted_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "promotion_id", require_non_empty_text(self.promotion_id, "promotion_id"))
        object.__setattr__(self, "commitment_id", require_non_empty_text(self.commitment_id, "commitment_id"))
        object.__setattr__(self, "obligation_id", require_non_empty_text(self.obligation_id, "obligation_id"))
        object.__setattr__(self, "promoted_at", require_datetime_text(self.promoted_at, "promoted_at"))
