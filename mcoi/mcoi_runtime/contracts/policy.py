"""Purpose: canonical policy decision contract mapping.
Governance scope: shared policy gate adoption without reinterpretation.
Dependencies: policy schema and policy-verification shared docs.
Invariants: policy gate precedes execution and remains explicit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_datetime_text, require_non_empty_text, require_non_empty_tuple


class PolicyDecisionStatus(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    ESCALATE = "escalate"


@dataclass(frozen=True, slots=True)
class DecisionReason(ContractRecord):
    message: str
    code: str | None = None
    details: Any = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "message", require_non_empty_text(self.message, "message"))
        if self.code is not None:
            object.__setattr__(self, "code", require_non_empty_text(self.code, "code"))
        object.__setattr__(self, "details", freeze_value(self.details))


@dataclass(frozen=True, slots=True)
class PolicyDecision(ContractRecord):
    decision_id: str
    subject_id: str
    goal_id: str
    status: PolicyDecisionStatus
    reasons: tuple[DecisionReason, ...]
    issued_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    extensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("decision_id", "subject_id", "goal_id"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.status, PolicyDecisionStatus):
            raise ValueError("status must be a PolicyDecisionStatus value")
        object.__setattr__(self, "reasons", require_non_empty_tuple(self.reasons, "reasons"))
        object.__setattr__(self, "issued_at", require_datetime_text(self.issued_at, "issued_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
        object.__setattr__(self, "extensions", freeze_value(self.extensions))
