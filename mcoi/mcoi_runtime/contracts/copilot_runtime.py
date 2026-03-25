"""Purpose: copilot runtime contracts.
Governance scope: typed descriptors for conversational assistant / copilot
    sessions, intents, turns, action plans, decisions, evidence-backed
    responses, violations, snapshots, assessments, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every record references a tenant.
  - All outputs are frozen and traceable.
  - Risk-level gates action disposition.
  - HIGH/CRITICAL actions are escalated, not auto-allowed.
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


class ConversationMode(Enum):
    """Mode of conversation interaction."""
    INTERACTIVE = "interactive"
    GUIDED = "guided"
    AUTONOMOUS = "autonomous"
    READ_ONLY = "read_only"


class IntentKind(Enum):
    """Category of user intent."""
    QUERY = "query"
    EXPLAIN = "explain"
    SUMMARIZE = "summarize"
    ACTION = "action"
    DRAFT = "draft"
    ESCALATE = "escalate"


class CopilotStatus(Enum):
    """Lifecycle status of a copilot session."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    TERMINATED = "terminated"


class ActionDisposition(Enum):
    """Disposition of a planned action."""
    ALLOWED = "allowed"
    DENIED = "denied"
    ESCALATED = "escalated"
    DEFERRED = "deferred"


class ResponseMode(Enum):
    """Mode of copilot response generation."""
    EVIDENCE_BACKED = "evidence_backed"
    SYNTHESIS = "synthesis"
    DIRECT = "direct"
    FALLBACK = "fallback"


class ConversationRiskLevel(Enum):
    """Risk level for a conversational action."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ConversationSession(ContractRecord):
    """A copilot conversation session."""

    session_id: str = ""
    tenant_id: str = ""
    identity_ref: str = ""
    mode: ConversationMode = ConversationMode.INTERACTIVE
    status: CopilotStatus = CopilotStatus.ACTIVE
    turn_count: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "session_id", require_non_empty_text(self.session_id, "session_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "identity_ref", require_non_empty_text(self.identity_ref, "identity_ref"))
        if not isinstance(self.mode, ConversationMode):
            raise ValueError("mode must be a ConversationMode")
        if not isinstance(self.status, CopilotStatus):
            raise ValueError("status must be a CopilotStatus")
        object.__setattr__(self, "turn_count", require_non_negative_int(self.turn_count, "turn_count"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class IntentRecord(ContractRecord):
    """A classified user intent within a session."""

    intent_id: str = ""
    tenant_id: str = ""
    session_ref: str = ""
    kind: IntentKind = IntentKind.QUERY
    raw_input: str = ""
    classified_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "intent_id", require_non_empty_text(self.intent_id, "intent_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "session_ref", require_non_empty_text(self.session_ref, "session_ref"))
        if not isinstance(self.kind, IntentKind):
            raise ValueError("kind must be an IntentKind")
        object.__setattr__(self, "raw_input", require_non_empty_text(self.raw_input, "raw_input"))
        require_datetime_text(self.classified_at, "classified_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ConversationTurn(ContractRecord):
    """A single turn in a copilot conversation."""

    turn_id: str = ""
    tenant_id: str = ""
    session_ref: str = ""
    intent_ref: str = ""
    user_input: str = ""
    assistant_output: str = ""
    response_mode: ResponseMode = ResponseMode.DIRECT
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "turn_id", require_non_empty_text(self.turn_id, "turn_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "session_ref", require_non_empty_text(self.session_ref, "session_ref"))
        object.__setattr__(self, "intent_ref", require_non_empty_text(self.intent_ref, "intent_ref"))
        object.__setattr__(self, "user_input", require_non_empty_text(self.user_input, "user_input"))
        object.__setattr__(self, "assistant_output", require_non_empty_text(self.assistant_output, "assistant_output"))
        if not isinstance(self.response_mode, ResponseMode):
            raise ValueError("response_mode must be a ResponseMode")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ActionPlan(ContractRecord):
    """A planned action from a copilot session."""

    plan_id: str = ""
    tenant_id: str = ""
    session_ref: str = ""
    intent_ref: str = ""
    target_runtime: str = ""
    operation: str = ""
    risk_level: ConversationRiskLevel = ConversationRiskLevel.LOW
    disposition: ActionDisposition = ActionDisposition.ALLOWED
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", require_non_empty_text(self.plan_id, "plan_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "session_ref", require_non_empty_text(self.session_ref, "session_ref"))
        object.__setattr__(self, "intent_ref", require_non_empty_text(self.intent_ref, "intent_ref"))
        object.__setattr__(self, "target_runtime", require_non_empty_text(self.target_runtime, "target_runtime"))
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        if not isinstance(self.risk_level, ConversationRiskLevel):
            raise ValueError("risk_level must be a ConversationRiskLevel")
        if not isinstance(self.disposition, ActionDisposition):
            raise ValueError("disposition must be an ActionDisposition")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CopilotDecision(ContractRecord):
    """A decision made by the copilot on an action plan."""

    decision_id: str = ""
    tenant_id: str = ""
    session_ref: str = ""
    plan_ref: str = ""
    disposition: ActionDisposition = ActionDisposition.ALLOWED
    reason: str = ""
    evidence_refs: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "session_ref", require_non_empty_text(self.session_ref, "session_ref"))
        object.__setattr__(self, "plan_ref", require_non_empty_text(self.plan_ref, "plan_ref"))
        if not isinstance(self.disposition, ActionDisposition):
            raise ValueError("disposition must be an ActionDisposition")
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        # evidence_refs can be empty
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class EvidenceBackedResponse(ContractRecord):
    """A response backed by evidence from the copilot."""

    response_id: str = ""
    tenant_id: str = ""
    session_ref: str = ""
    turn_ref: str = ""
    content: str = ""
    evidence_count: int = 0
    confidence: float = 1.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "response_id", require_non_empty_text(self.response_id, "response_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "session_ref", require_non_empty_text(self.session_ref, "session_ref"))
        object.__setattr__(self, "turn_ref", require_non_empty_text(self.turn_ref, "turn_ref"))
        object.__setattr__(self, "content", require_non_empty_text(self.content, "content"))
        object.__setattr__(self, "evidence_count", require_non_negative_int(self.evidence_count, "evidence_count"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ConversationViolation(ContractRecord):
    """A violation detected in the copilot lifecycle."""

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
class CopilotSnapshot(ContractRecord):
    """Point-in-time snapshot of copilot runtime state."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_sessions: int = 0
    total_turns: int = 0
    total_intents: int = 0
    total_plans: int = 0
    total_decisions: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_sessions", require_non_negative_int(self.total_sessions, "total_sessions"))
        object.__setattr__(self, "total_turns", require_non_negative_int(self.total_turns, "total_turns"))
        object.__setattr__(self, "total_intents", require_non_negative_int(self.total_intents, "total_intents"))
        object.__setattr__(self, "total_plans", require_non_negative_int(self.total_plans, "total_plans"))
        object.__setattr__(self, "total_decisions", require_non_negative_int(self.total_decisions, "total_decisions"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CopilotAssessment(ContractRecord):
    """Assessment of copilot effectiveness for a tenant."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_sessions: int = 0
    total_actions_allowed: int = 0
    total_actions_denied: int = 0
    success_rate: float = 1.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_sessions", require_non_negative_int(self.total_sessions, "total_sessions"))
        object.__setattr__(self, "total_actions_allowed", require_non_negative_int(self.total_actions_allowed, "total_actions_allowed"))
        object.__setattr__(self, "total_actions_denied", require_non_negative_int(self.total_actions_denied, "total_actions_denied"))
        object.__setattr__(self, "success_rate", require_unit_float(self.success_rate, "success_rate"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CopilotClosureReport(ContractRecord):
    """Final closure report for copilot lifecycle."""

    report_id: str = ""
    tenant_id: str = ""
    total_sessions: int = 0
    total_turns: int = 0
    total_plans: int = 0
    total_decisions: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_sessions", require_non_negative_int(self.total_sessions, "total_sessions"))
        object.__setattr__(self, "total_turns", require_non_negative_int(self.total_turns, "total_turns"))
        object.__setattr__(self, "total_plans", require_non_negative_int(self.total_plans, "total_plans"))
        object.__setattr__(self, "total_decisions", require_non_negative_int(self.total_decisions, "total_decisions"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
