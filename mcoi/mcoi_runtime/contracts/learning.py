"""Purpose: canonical learning admission decision contract mapping.
Governance scope: shared learning admission adoption.
Dependencies: learning admission schema and shared learning docs.
Invariants: only admitted knowledge may enter planning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_datetime_text, require_non_empty_text, require_non_empty_tuple
from .policy import DecisionReason


class LearningAdmissionStatus(StrEnum):
    ADMIT = "admit"
    REJECT = "reject"
    DEFER = "defer"


@dataclass(frozen=True, slots=True)
class LearningAdmissionDecision(ContractRecord):
    admission_id: str
    knowledge_id: str
    status: LearningAdmissionStatus
    reasons: tuple[DecisionReason, ...]
    issued_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    extensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "admission_id", require_non_empty_text(self.admission_id, "admission_id"))
        object.__setattr__(self, "knowledge_id", require_non_empty_text(self.knowledge_id, "knowledge_id"))
        if not isinstance(self.status, LearningAdmissionStatus):
            raise ValueError("status must be a LearningAdmissionStatus value")
        object.__setattr__(self, "reasons", require_non_empty_tuple(self.reasons, "reasons"))
        object.__setattr__(self, "issued_at", require_datetime_text(self.issued_at, "issued_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
        object.__setattr__(self, "extensions", freeze_value(self.extensions))
