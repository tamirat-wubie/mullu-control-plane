"""Purpose: canonical retention and lifecycle management contracts.
Governance scope: retention policy, prune result, and status typing.
Dependencies: shared contract base helpers.
Invariants:
  - Retention policies are explicit and configurable per artifact class.
  - Pruning is deterministic for the same inputs.
  - No silent deletion — prune results are typed and auditable.
  - Compliance-required artifacts MUST NOT be pruned by age alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_non_empty_text, require_non_negative_int


class ArtifactClass(StrEnum):
    TRACE = "trace"
    REPLAY = "replay"
    SNAPSHOT = "snapshot"
    SKILL_RECORD = "skill_record"
    RUN_HISTORY = "run_history"
    TELEMETRY = "telemetry"
    ALERT = "alert"
    RUNBOOK = "runbook"


class RetentionAction(StrEnum):
    KEEP = "keep"
    ARCHIVE = "archive"
    PRUNE = "prune"


class PruneStatus(StrEnum):
    PRUNED = "pruned"
    SKIPPED_COMPLIANCE = "skipped_compliance"
    SKIPPED_REFERENCED = "skipped_referenced"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class RetentionPolicy(ContractRecord):
    """Retention rules for one artifact class."""

    policy_id: str
    artifact_class: ArtifactClass
    max_age_days: int
    max_count: int
    compliance_hold: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", require_non_empty_text(self.policy_id, "policy_id"))
        if not isinstance(self.artifact_class, ArtifactClass):
            raise ValueError("artifact_class must be an ArtifactClass value")
        if not isinstance(self.max_age_days, int) or self.max_age_days < 0:
            raise ValueError("max_age_days must be a non-negative integer")
        if not isinstance(self.max_count, int) or self.max_count < 0:
            raise ValueError("max_count must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class PruneCandidate(ContractRecord):
    """An artifact evaluated for pruning."""

    artifact_id: str
    artifact_class: ArtifactClass
    age_days: int
    is_referenced: bool = False
    compliance_hold: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_id", require_non_empty_text(self.artifact_id, "artifact_id"))
        if not isinstance(self.artifact_class, ArtifactClass):
            raise ValueError("artifact_class must be an ArtifactClass value")
        require_non_negative_int(self.age_days, "age_days")
        if not isinstance(self.is_referenced, bool):
            raise ValueError("is_referenced must be a bool")
        if not isinstance(self.compliance_hold, bool):
            raise ValueError("compliance_hold must be a bool")


@dataclass(frozen=True, slots=True)
class PruneResult(ContractRecord):
    """Result of evaluating one artifact against retention policy."""

    artifact_id: str
    status: PruneStatus
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_id", require_non_empty_text(self.artifact_id, "artifact_id"))
        if not isinstance(self.status, PruneStatus):
            raise ValueError("status must be a PruneStatus value")
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))


@dataclass(frozen=True, slots=True)
class RetentionStatus(ContractRecord):
    """Summary of retention evaluation across artifact classes."""

    evaluated_count: int
    pruned_count: int
    skipped_count: int
    failed_count: int
    results: tuple[PruneResult, ...] = ()

    def __post_init__(self) -> None:
        require_non_negative_int(self.evaluated_count, "evaluated_count")
        require_non_negative_int(self.pruned_count, "pruned_count")
        require_non_negative_int(self.skipped_count, "skipped_count")
        require_non_negative_int(self.failed_count, "failed_count")
        object.__setattr__(self, "results", freeze_value(list(self.results)))
