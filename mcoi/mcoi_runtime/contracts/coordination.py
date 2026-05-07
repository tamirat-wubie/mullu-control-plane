"""Purpose: canonical coordination contracts for delegation, handoff, merge, conflict, and checkpoint.
Governance scope: coordination plane contract typing only.
Dependencies: shared contract base helpers.
Invariants:
  - All coordination preserves provenance and identity.
  - Delegation is explicit with named target.
  - Conflicts are recorded, never silently discarded.
  - Checkpoints carry lease expiration and retry counts.
  - Restore is governed: expired, drifted, or over-retried checkpoints are rejected.
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
)


class DelegationStatus(StrEnum):
    """Outcome of a delegation attempt."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


class MergeOutcome(StrEnum):
    """Outcome of combining results from multiple sources."""

    MERGED = "merged"
    CONFLICT_DETECTED = "conflict_detected"
    DEFERRED = "deferred"


class ConflictStrategy(StrEnum):
    """How to resolve conflicting results."""

    PREFER_LATEST = "prefer_latest"
    PREFER_HIGHEST_CONFIDENCE = "prefer_highest_confidence"
    ESCALATE = "escalate"
    MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class DelegationRequest(ContractRecord):
    """Request to assign work to another agent or role."""

    delegation_id: str
    delegator_id: str
    delegate_id: str
    goal_id: str
    action_scope: str
    deadline: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("delegation_id", "delegator_id", "delegate_id", "goal_id", "action_scope"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if self.delegator_id == self.delegate_id:
            raise ValueError("delegator and delegate must be different")
        if self.deadline is not None:
            object.__setattr__(self, "deadline", require_datetime_text(self.deadline, "deadline"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class DelegationResult(ContractRecord):
    """Outcome of a delegation attempt."""

    delegation_id: str
    status: DelegationStatus
    reason: str
    resolved_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "delegation_id", require_non_empty_text(self.delegation_id, "delegation_id"))
        if not isinstance(self.status, DelegationStatus):
            raise ValueError("status must be a DelegationStatus value")
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        object.__setattr__(self, "resolved_at", require_datetime_text(self.resolved_at, "resolved_at"))


@dataclass(frozen=True, slots=True)
class HandoffRecord(ContractRecord):
    """Provenance-preserving transfer of responsibility."""

    handoff_id: str
    from_party: str
    to_party: str
    goal_id: str
    context_ids: tuple[str, ...]
    handed_off_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("handoff_id", "from_party", "to_party", "goal_id"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if self.from_party == self.to_party:
            raise ValueError("from_party and to_party must be different")
        if not self.context_ids:
            raise ValueError("context_ids must contain at least one item")
        for cid in self.context_ids:
            require_non_empty_text(cid, "context_id")
        object.__setattr__(self, "handed_off_at", require_datetime_text(self.handed_off_at, "handed_off_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class MergeDecision(ContractRecord):
    """Outcome of combining results from multiple sources."""

    merge_id: str
    goal_id: str
    source_ids: tuple[str, ...]
    outcome: MergeOutcome
    reason: str
    resolved_at: str

    def __post_init__(self) -> None:
        for field_name in ("merge_id", "goal_id", "reason"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if len(self.source_ids) < 2:
            raise ValueError("merge requires at least two source_ids")
        for sid in self.source_ids:
            require_non_empty_text(sid, "source_id")
        if not isinstance(self.outcome, MergeOutcome):
            raise ValueError("outcome must be a MergeOutcome value")
        object.__setattr__(self, "resolved_at", require_datetime_text(self.resolved_at, "resolved_at"))


@dataclass(frozen=True, slots=True)
class ConflictRecord(ContractRecord):
    """Explicit record of conflicting results or decisions."""

    conflict_id: str
    goal_id: str
    conflicting_ids: tuple[str, ...]
    strategy: ConflictStrategy
    resolved: bool
    resolution_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("conflict_id", "goal_id"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if len(self.conflicting_ids) < 2:
            raise ValueError("conflict requires at least two conflicting_ids")
        for cid in self.conflicting_ids:
            require_non_empty_text(cid, "conflicting_id")
        if not isinstance(self.strategy, ConflictStrategy):
            raise ValueError("strategy must be a ConflictStrategy value")
        if self.resolved and self.resolution_id is None:
            raise ValueError("resolved conflicts must carry a resolution_id")
        if self.resolution_id is not None:
            object.__setattr__(self, "resolution_id", require_non_empty_text(self.resolution_id, "resolution_id"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


class RestoreStatus(StrEnum):
    """Outcome of attempting to restore a coordination checkpoint."""

    RESUMED = "resumed"
    EXPIRED = "expired"
    INVALID = "invalid"
    NEEDS_REVIEW = "needs_review"
    ABORTED = "aborted"


@dataclass(frozen=True, slots=True)
class CoordinationCheckpoint(ContractRecord):
    """Snapshot of coordination engine state for persistence and governed restore."""

    checkpoint_id: str
    delegations: tuple[DelegationRequest, ...]
    delegation_results: tuple[DelegationResult, ...]
    handoffs: tuple[HandoffRecord, ...]
    merges: tuple[MergeDecision, ...]
    conflicts: tuple[ConflictRecord, ...]
    created_at: str
    lease_expires_at: str
    retry_count: int
    policy_pack_id: str
    restore_conditions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "checkpoint_id",
            require_non_empty_text(self.checkpoint_id, "checkpoint_id"),
        )
        object.__setattr__(
            self, "created_at",
            require_datetime_text(self.created_at, "created_at"),
        )
        object.__setattr__(
            self, "lease_expires_at",
            require_datetime_text(self.lease_expires_at, "lease_expires_at"),
        )
        object.__setattr__(
            self, "retry_count",
            require_non_negative_int(self.retry_count, "retry_count"),
        )
        object.__setattr__(
            self, "policy_pack_id",
            require_non_empty_text(self.policy_pack_id, "policy_pack_id"),
        )
        object.__setattr__(
            self, "restore_conditions",
            freeze_value(self.restore_conditions),
        )


@dataclass(frozen=True, slots=True)
class RestoreOutcome(ContractRecord):
    """Result of attempting to restore a coordination checkpoint."""

    checkpoint_id: str
    status: RestoreStatus
    reason: str
    restored_at: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "checkpoint_id",
            require_non_empty_text(self.checkpoint_id, "checkpoint_id"),
        )
        if not isinstance(self.status, RestoreStatus):
            raise ValueError("status must be a RestoreStatus value")
        object.__setattr__(
            self, "reason",
            require_non_empty_text(self.reason, "reason"),
        )
        object.__setattr__(
            self, "restored_at",
            require_datetime_text(self.restored_at, "restored_at"),
        )
