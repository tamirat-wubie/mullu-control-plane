"""Purpose: canonical verification result contract mapping.
Governance scope: shared verification closure adoption.
Dependencies: verification schema and policy-verification docs.
Invariants: verification closure stays explicit and terminal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_datetime_text, require_non_empty_text, require_non_empty_tuple
from .evidence import EvidenceRecord


class VerificationStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True, slots=True)
class VerificationCheck(ContractRecord):
    name: str
    status: VerificationStatus
    details: Any = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        if not isinstance(self.status, VerificationStatus):
            raise ValueError("status must be a VerificationStatus value")
        object.__setattr__(self, "details", freeze_value(self.details))


@dataclass(frozen=True, slots=True)
class VerificationResult(ContractRecord):
    verification_id: str
    execution_id: str
    status: VerificationStatus
    checks: tuple[VerificationCheck, ...]
    evidence: tuple[EvidenceRecord, ...]
    closed_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    extensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "verification_id", require_non_empty_text(self.verification_id, "verification_id"))
        object.__setattr__(self, "execution_id", require_non_empty_text(self.execution_id, "execution_id"))
        if not isinstance(self.status, VerificationStatus):
            raise ValueError("status must be a VerificationStatus value")
        object.__setattr__(self, "checks", require_non_empty_tuple(self.checks, "checks"))
        object.__setattr__(self, "evidence", require_non_empty_tuple(self.evidence, "evidence"))
        object.__setattr__(self, "closed_at", require_datetime_text(self.closed_at, "closed_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
        object.__setattr__(self, "extensions", freeze_value(self.extensions))
