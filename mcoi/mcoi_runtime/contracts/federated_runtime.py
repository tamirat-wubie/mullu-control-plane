"""Purpose: federated mesh / distributed knowledge runtime contracts.
Governance scope: typed descriptors for federated nodes, claims, sync records,
    reconciliation, partitions, decisions, assessments, violations, snapshots,
    and closure reports for cross-mesh knowledge federation.
Dependencies: _base contract utilities.
Invariants:
  - Every record references a tenant.
  - All outputs are frozen and traceable.
  - Sync dispositions are explicit and computable.
  - Node role and federation status are enum-guarded.
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
    require_non_negative_float,
    require_non_negative_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class FederationStatus(Enum):
    """Status of a federated node's connectivity."""
    CONNECTED = "connected"
    DEGRADED = "degraded"
    PARTITIONED = "partitioned"
    DISCONNECTED = "disconnected"


class NodeRole(Enum):
    """Role of a node in the federation mesh."""
    PRIMARY = "primary"
    SECONDARY = "secondary"
    EDGE = "edge"
    OBSERVER = "observer"


class SyncDisposition(Enum):
    """Disposition of a claim's synchronization state."""
    SYNCED = "synced"
    PENDING = "pending"
    CONFLICTED = "conflicted"
    STALE = "stale"


class ReconciliationMode(Enum):
    """Mode used to reconcile conflicting claims."""
    LAST_WRITE_WINS = "last_write_wins"
    MERGE = "merge"
    MANUAL = "manual"
    REJECT = "reject"


class PartitionPolicy(Enum):
    """Policy applied during a network partition."""
    FAIL_CLOSED = "fail_closed"
    DEGRADE = "degrade"
    LOCAL_AUTONOMY = "local_autonomy"
    REJECT = "reject"


class FederatedRiskLevel(Enum):
    """Risk level for federated operations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FederatedNode(ContractRecord):
    """A registered node in the federation mesh."""

    node_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    role: NodeRole = NodeRole.SECONDARY
    status: FederationStatus = FederationStatus.CONNECTED
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_id", require_non_empty_text(self.node_id, "node_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        if not isinstance(self.role, NodeRole):
            raise ValueError("role must be a NodeRole")
        if not isinstance(self.status, FederationStatus):
            raise ValueError("status must be a FederationStatus")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class FederatedClaim(ContractRecord):
    """A knowledge claim registered in the federation mesh."""

    claim_id: str = ""
    tenant_id: str = ""
    origin_node_ref: str = ""
    content: str = ""
    trust_level: float = 0.0
    sync: SyncDisposition = SyncDisposition.PENDING
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_id", require_non_empty_text(self.claim_id, "claim_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "origin_node_ref", require_non_empty_text(self.origin_node_ref, "origin_node_ref"))
        object.__setattr__(self, "content", require_non_empty_text(self.content, "content"))
        object.__setattr__(self, "trust_level", require_unit_float(self.trust_level, "trust_level"))
        if not isinstance(self.sync, SyncDisposition):
            raise ValueError("sync must be a SyncDisposition")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SyncRecord(ContractRecord):
    """A record of claim synchronization between two nodes."""

    sync_id: str = ""
    tenant_id: str = ""
    source_node_ref: str = ""
    target_node_ref: str = ""
    claim_count: int = 0
    disposition: SyncDisposition = SyncDisposition.SYNCED
    synced_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "sync_id", require_non_empty_text(self.sync_id, "sync_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "source_node_ref", require_non_empty_text(self.source_node_ref, "source_node_ref"))
        object.__setattr__(self, "target_node_ref", require_non_empty_text(self.target_node_ref, "target_node_ref"))
        object.__setattr__(self, "claim_count", require_non_negative_int(self.claim_count, "claim_count"))
        if not isinstance(self.disposition, SyncDisposition):
            raise ValueError("disposition must be a SyncDisposition")
        require_datetime_text(self.synced_at, "synced_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ReconciliationRecord(ContractRecord):
    """A record of claim reconciliation between two conflicting claims."""

    reconciliation_id: str = ""
    tenant_id: str = ""
    claim_a_ref: str = ""
    claim_b_ref: str = ""
    mode: ReconciliationMode = ReconciliationMode.LAST_WRITE_WINS
    resolved: bool = False
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reconciliation_id", require_non_empty_text(self.reconciliation_id, "reconciliation_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "claim_a_ref", require_non_empty_text(self.claim_a_ref, "claim_a_ref"))
        object.__setattr__(self, "claim_b_ref", require_non_empty_text(self.claim_b_ref, "claim_b_ref"))
        if not isinstance(self.mode, ReconciliationMode):
            raise ValueError("mode must be a ReconciliationMode")
        if not isinstance(self.resolved, bool):
            raise ValueError("resolved must be a bool")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PartitionRecord(ContractRecord):
    """A record of a detected network partition."""

    partition_id: str = ""
    tenant_id: str = ""
    node_ref: str = ""
    policy: PartitionPolicy = PartitionPolicy.FAIL_CLOSED
    duration_ms: float = 0.0
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "partition_id", require_non_empty_text(self.partition_id, "partition_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "node_ref", require_non_empty_text(self.node_ref, "node_ref"))
        if not isinstance(self.policy, PartitionPolicy):
            raise ValueError("policy must be a PartitionPolicy")
        object.__setattr__(self, "duration_ms", require_non_negative_float(self.duration_ms, "duration_ms"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class FederatedDecision(ContractRecord):
    """A decision made in the federated runtime context."""

    decision_id: str = ""
    tenant_id: str = ""
    node_ref: str = ""
    disposition: str = ""
    reason: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "node_ref", require_non_empty_text(self.node_ref, "node_ref"))
        object.__setattr__(self, "disposition", require_non_empty_text(self.disposition, "disposition"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class FederatedAssessment(ContractRecord):
    """Assessment of federated mesh health for a tenant."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_nodes: int = 0
    total_claims: int = 0
    total_partitions: int = 0
    sync_rate: float = 0.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_nodes", require_non_negative_int(self.total_nodes, "total_nodes"))
        object.__setattr__(self, "total_claims", require_non_negative_int(self.total_claims, "total_claims"))
        object.__setattr__(self, "total_partitions", require_non_negative_int(self.total_partitions, "total_partitions"))
        object.__setattr__(self, "sync_rate", require_unit_float(self.sync_rate, "sync_rate"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class FederatedViolation(ContractRecord):
    """A detected violation in the federated runtime."""

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
class FederatedSnapshot(ContractRecord):
    """Point-in-time snapshot of federated runtime state."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_nodes: int = 0
    total_claims: int = 0
    total_syncs: int = 0
    total_partitions: int = 0
    total_reconciliations: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_nodes", require_non_negative_int(self.total_nodes, "total_nodes"))
        object.__setattr__(self, "total_claims", require_non_negative_int(self.total_claims, "total_claims"))
        object.__setattr__(self, "total_syncs", require_non_negative_int(self.total_syncs, "total_syncs"))
        object.__setattr__(self, "total_partitions", require_non_negative_int(self.total_partitions, "total_partitions"))
        object.__setattr__(self, "total_reconciliations", require_non_negative_int(self.total_reconciliations, "total_reconciliations"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class FederatedClosureReport(ContractRecord):
    """Closure report for federated runtime state."""

    report_id: str = ""
    tenant_id: str = ""
    total_nodes: int = 0
    total_claims: int = 0
    total_syncs: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_nodes", require_non_negative_int(self.total_nodes, "total_nodes"))
        object.__setattr__(self, "total_claims", require_non_negative_int(self.total_claims, "total_claims"))
        object.__setattr__(self, "total_syncs", require_non_negative_int(self.total_syncs, "total_syncs"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
