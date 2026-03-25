"""Purpose: canonical autonomy mode contract mapping.
Governance scope: autonomy mode, decision, constraint, and violation typing.
Dependencies: shared contract base helpers.
Invariants:
  - Every runtime invocation has an explicit autonomy mode.
  - Mode boundaries are enforced before dispatch, not after.
  - Violations are typed and surfaced, never silently swallowed.
  - Unknown or ambiguous action classes fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_non_empty_text, require_non_negative_int


class AutonomyMode(StrEnum):
    OBSERVE_ONLY = "observe_only"
    SUGGEST_ONLY = "suggest_only"
    APPROVAL_REQUIRED = "approval_required"
    BOUNDED_AUTONOMOUS = "bounded_autonomous"


class ActionClass(StrEnum):
    """Classification of an action's autonomy impact."""

    OBSERVE = "observe"
    ANALYZE = "analyze"
    SUGGEST = "suggest"
    PLAN = "plan"
    EXECUTE_READ = "execute_read"
    EXECUTE_WRITE = "execute_write"
    COMMUNICATE = "communicate"
    APPROVE = "approve"


class AutonomyDecisionStatus(StrEnum):
    ALLOWED = "allowed"
    CONVERTED_TO_SUGGESTION = "converted_to_suggestion"
    BLOCKED_PENDING_APPROVAL = "blocked_pending_approval"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class AutonomyConstraint(ContractRecord):
    """A constraint that the autonomy mode imposes on actions."""

    constraint_id: str
    mode: AutonomyMode
    blocked_action_classes: tuple[str, ...]
    allowed_action_classes: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "constraint_id", require_non_empty_text(self.constraint_id, "constraint_id"))
        if not isinstance(self.mode, AutonomyMode):
            raise ValueError("mode must be an AutonomyMode value")
        object.__setattr__(self, "blocked_action_classes", freeze_value(list(self.blocked_action_classes)))
        object.__setattr__(self, "allowed_action_classes", freeze_value(list(self.allowed_action_classes)))


@dataclass(frozen=True, slots=True)
class AutonomyDecision(ContractRecord):
    """Result of evaluating an action against the current autonomy mode."""

    decision_id: str
    mode: AutonomyMode
    action_class: ActionClass
    status: AutonomyDecisionStatus
    reason: str
    suggestion: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        if not isinstance(self.mode, AutonomyMode):
            raise ValueError("mode must be an AutonomyMode value")
        if not isinstance(self.action_class, ActionClass):
            raise ValueError("action_class must be an ActionClass value")
        if not isinstance(self.status, AutonomyDecisionStatus):
            raise ValueError("status must be an AutonomyDecisionStatus value")
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))


@dataclass(frozen=True, slots=True)
class AutonomyViolation(ContractRecord):
    """Record of an attempted action that violated the autonomy mode."""

    violation_id: str
    mode: AutonomyMode
    action_class: ActionClass
    attempted_action: str
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        if not isinstance(self.mode, AutonomyMode):
            raise ValueError("mode must be an AutonomyMode value")
        if not isinstance(self.action_class, ActionClass):
            raise ValueError("action_class must be an ActionClass value")
        object.__setattr__(self, "attempted_action", require_non_empty_text(self.attempted_action, "attempted_action"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))


@dataclass(frozen=True, slots=True)
class AutonomyStatus(ContractRecord):
    """Current autonomy state for operator visibility."""

    mode: AutonomyMode
    total_decisions: int = 0
    allowed_count: int = 0
    blocked_count: int = 0
    suggestion_count: int = 0
    pending_approval_count: int = 0
    violations: tuple[AutonomyViolation, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.mode, AutonomyMode):
            raise ValueError("mode must be an AutonomyMode value")
        object.__setattr__(self, "total_decisions", require_non_negative_int(self.total_decisions, "total_decisions"))
        object.__setattr__(self, "allowed_count", require_non_negative_int(self.allowed_count, "allowed_count"))
        object.__setattr__(self, "blocked_count", require_non_negative_int(self.blocked_count, "blocked_count"))
        object.__setattr__(self, "suggestion_count", require_non_negative_int(self.suggestion_count, "suggestion_count"))
        object.__setattr__(self, "pending_approval_count", require_non_negative_int(self.pending_approval_count, "pending_approval_count"))
        object.__setattr__(self, "violations", freeze_value(list(self.violations)))
