"""Purpose: federated mesh / distributed knowledge runtime engine.
Governance scope: governed node/claim/sync/reconciliation/partition runtime
    with federation status tracking, conflict detection, partition recording,
    violation detection, and replayable state hashing.
Dependencies: event_spine, invariants, contracts, engine_protocol.
Invariants:
  - Duplicate IDs are rejected fail-closed.
  - Node transitions allow all states (no terminal).
  - Violation detection is idempotent.
  - All outputs are frozen.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
from mcoi_runtime.contracts.federated_runtime import (
    FederatedAssessment,
    FederatedClaim,
    FederatedClosureReport,
    FederatedDecision,
    FederatedNode,
    FederatedSnapshot,
    FederatedViolation,
    FederationStatus,
    NodeRole,
    PartitionPolicy,
    PartitionRecord,
    ReconciliationMode,
    ReconciliationRecord,
    SyncDisposition,
    SyncRecord,
)
from mcoi_runtime.core.engine_protocol import Clock, WallClock
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _emit(es: EventSpineEngine, action: str, payload: dict[str, Any], cid: str, clock: Clock) -> None:
    now = clock.now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-fed", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.EXTERNAL,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)


class FederatedRuntimeEngine:
    """Governed federated mesh / distributed knowledge engine."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._nodes: dict[str, FederatedNode] = {}
        self._claims: dict[str, FederatedClaim] = {}
        self._syncs: dict[str, SyncRecord] = {}
        self._reconciliations: dict[str, ReconciliationRecord] = {}
        self._partitions: dict[str, PartitionRecord] = {}
        self._decisions: dict[str, FederatedDecision] = {}
        self._violations: dict[str, FederatedViolation] = {}

    # -- Clock --

    def _now(self) -> str:
        return self._clock.now_iso()

    # -- Properties --

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def claim_count(self) -> int:
        return len(self._claims)

    @property
    def sync_count(self) -> int:
        return len(self._syncs)

    @property
    def reconciliation_count(self) -> int:
        return len(self._reconciliations)

    @property
    def partition_count(self) -> int:
        return len(self._partitions)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # -------------------------------------------------------------------
    # Nodes
    # -------------------------------------------------------------------

    def register_node(
        self,
        node_id: str,
        tenant_id: str,
        display_name: str,
        role: NodeRole = NodeRole.SECONDARY,
    ) -> FederatedNode:
        if node_id in self._nodes:
            raise RuntimeCoreInvariantError("duplicate node_id")
        now = self._now()
        node = FederatedNode(
            node_id=node_id, tenant_id=tenant_id, display_name=display_name,
            role=role, status=FederationStatus.CONNECTED, created_at=now,
        )
        self._nodes[node_id] = node
        _emit(self._events, "register_node", {"node_id": node_id}, node_id, self._clock)
        return node

    def _get_node(self, node_id: str) -> FederatedNode:
        if node_id not in self._nodes:
            raise RuntimeCoreInvariantError("unknown node_id")
        return self._nodes[node_id]

    def _transition_node(self, node_id: str, target: FederationStatus) -> FederatedNode:
        node = self._get_node(node_id)
        now = self._now()
        updated = FederatedNode(
            node_id=node.node_id, tenant_id=node.tenant_id,
            display_name=node.display_name, role=node.role,
            status=target, created_at=now,
        )
        self._nodes[node_id] = updated
        _emit(self._events, f"node_{target.value}", {"node_id": node_id}, node_id, self._clock)
        return updated

    def degrade_node(self, node_id: str) -> FederatedNode:
        return self._transition_node(node_id, FederationStatus.DEGRADED)

    def disconnect_node(self, node_id: str) -> FederatedNode:
        return self._transition_node(node_id, FederationStatus.DISCONNECTED)

    def reconnect_node(self, node_id: str) -> FederatedNode:
        return self._transition_node(node_id, FederationStatus.CONNECTED)

    # -------------------------------------------------------------------
    # Claims
    # -------------------------------------------------------------------

    def register_claim(
        self,
        claim_id: str,
        tenant_id: str,
        origin_node_ref: str,
        content: str,
        trust_level: float = 0.5,
    ) -> FederatedClaim:
        if claim_id in self._claims:
            raise RuntimeCoreInvariantError("duplicate claim_id")
        now = self._now()
        claim = FederatedClaim(
            claim_id=claim_id, tenant_id=tenant_id, origin_node_ref=origin_node_ref,
            content=content, trust_level=trust_level,
            sync=SyncDisposition.PENDING, created_at=now,
        )
        self._claims[claim_id] = claim
        _emit(self._events, "register_claim", {"claim_id": claim_id}, claim_id, self._clock)
        return claim

    # -------------------------------------------------------------------
    # Sync
    # -------------------------------------------------------------------

    def sync_claims(
        self,
        sync_id: str,
        tenant_id: str,
        source_node_ref: str,
        target_node_ref: str,
    ) -> SyncRecord:
        if sync_id in self._syncs:
            raise RuntimeCoreInvariantError("duplicate sync_id")
        now = self._now()
        # Count claims from source node that are PENDING
        relevant = [
            c for c in self._claims.values()
            if c.tenant_id == tenant_id and c.origin_node_ref == source_node_ref
            and c.sync == SyncDisposition.PENDING
        ]
        # Mark them SYNCED
        for c in relevant:
            updated_claim = FederatedClaim(
                claim_id=c.claim_id, tenant_id=c.tenant_id,
                origin_node_ref=c.origin_node_ref, content=c.content,
                trust_level=c.trust_level, sync=SyncDisposition.SYNCED,
                created_at=c.created_at,
            )
            self._claims[c.claim_id] = updated_claim
        sr = SyncRecord(
            sync_id=sync_id, tenant_id=tenant_id,
            source_node_ref=source_node_ref, target_node_ref=target_node_ref,
            claim_count=len(relevant), disposition=SyncDisposition.SYNCED,
            synced_at=now,
        )
        self._syncs[sync_id] = sr
        _emit(self._events, "sync_claims", {"sync_id": sync_id, "count": len(relevant)}, sync_id, self._clock)
        return sr

    # -------------------------------------------------------------------
    # Conflict detection
    # -------------------------------------------------------------------

    def detect_sync_conflicts(self, tenant_id: str) -> tuple[FederatedClaim, ...]:
        """Detect claims with same content from different nodes with different trust."""
        conflicts: list[FederatedClaim] = []
        claims_by_content: dict[str, list[FederatedClaim]] = {}
        for c in self._claims.values():
            if c.tenant_id != tenant_id:
                continue
            claims_by_content.setdefault(c.content, []).append(c)
        for content_group in claims_by_content.values():
            if len(content_group) < 2:
                continue
            nodes = {c.origin_node_ref for c in content_group}
            trusts = {c.trust_level for c in content_group}
            if len(nodes) > 1 and len(trusts) > 1:
                for c in content_group:
                    if c.sync != SyncDisposition.CONFLICTED:
                        updated = FederatedClaim(
                            claim_id=c.claim_id, tenant_id=c.tenant_id,
                            origin_node_ref=c.origin_node_ref, content=c.content,
                            trust_level=c.trust_level, sync=SyncDisposition.CONFLICTED,
                            created_at=c.created_at,
                        )
                        self._claims[c.claim_id] = updated
                        conflicts.append(updated)
        if conflicts:
            _emit(self._events, "detect_sync_conflicts", {
                "tenant_id": tenant_id, "count": len(conflicts),
            }, tenant_id, self._clock)
        return tuple(conflicts)

    # -------------------------------------------------------------------
    # Reconciliation
    # -------------------------------------------------------------------

    def reconcile_claims(
        self,
        reconciliation_id: str,
        tenant_id: str,
        claim_a_ref: str,
        claim_b_ref: str,
        mode: ReconciliationMode = ReconciliationMode.LAST_WRITE_WINS,
    ) -> ReconciliationRecord:
        if reconciliation_id in self._reconciliations:
            raise RuntimeCoreInvariantError("duplicate reconciliation_id")
        now = self._now()
        rec = ReconciliationRecord(
            reconciliation_id=reconciliation_id, tenant_id=tenant_id,
            claim_a_ref=claim_a_ref, claim_b_ref=claim_b_ref,
            mode=mode, resolved=True, created_at=now,
        )
        self._reconciliations[reconciliation_id] = rec
        _emit(self._events, "reconcile_claims", {"reconciliation_id": reconciliation_id}, reconciliation_id, self._clock)
        return rec

    # -------------------------------------------------------------------
    # Partitions
    # -------------------------------------------------------------------

    def record_partition(
        self,
        partition_id: str,
        tenant_id: str,
        node_ref: str,
        policy: PartitionPolicy = PartitionPolicy.FAIL_CLOSED,
        duration_ms: float = 0.0,
    ) -> PartitionRecord:
        if partition_id in self._partitions:
            raise RuntimeCoreInvariantError("duplicate partition_id")
        now = self._now()
        pr = PartitionRecord(
            partition_id=partition_id, tenant_id=tenant_id,
            node_ref=node_ref, policy=policy,
            duration_ms=duration_ms, detected_at=now,
        )
        self._partitions[partition_id] = pr
        # Also mark node as PARTITIONED
        if node_ref in self._nodes:
            self._transition_node(node_ref, FederationStatus.PARTITIONED)
        _emit(self._events, "record_partition", {"partition_id": partition_id}, partition_id, self._clock)
        return pr

    # -------------------------------------------------------------------
    # Assessment
    # -------------------------------------------------------------------

    def federated_assessment(self, assessment_id: str, tenant_id: str) -> FederatedAssessment:
        now = self._now()
        t_nodes = len([n for n in self._nodes.values() if n.tenant_id == tenant_id])
        t_claims = len([c for c in self._claims.values() if c.tenant_id == tenant_id])
        t_partitions = len([p for p in self._partitions.values() if p.tenant_id == tenant_id])
        synced = len([c for c in self._claims.values() if c.tenant_id == tenant_id and c.sync == SyncDisposition.SYNCED])
        pending = len([c for c in self._claims.values() if c.tenant_id == tenant_id and c.sync == SyncDisposition.PENDING])
        conflicted = len([c for c in self._claims.values() if c.tenant_id == tenant_id and c.sync == SyncDisposition.CONFLICTED])
        denom = synced + pending + conflicted
        rate = synced / denom if denom > 0 else 0.0
        assessment = FederatedAssessment(
            assessment_id=assessment_id, tenant_id=tenant_id,
            total_nodes=t_nodes, total_claims=t_claims,
            total_partitions=t_partitions,
            sync_rate=round(rate, 4),
            assessed_at=now,
        )
        _emit(self._events, "federated_assessment", {"assessment_id": assessment_id}, assessment_id, self._clock)
        return assessment

    # -------------------------------------------------------------------
    # Snapshot
    # -------------------------------------------------------------------

    def federated_snapshot(self, snapshot_id: str, tenant_id: str) -> FederatedSnapshot:
        now = self._now()
        snap = FederatedSnapshot(
            snapshot_id=snapshot_id, tenant_id=tenant_id,
            total_nodes=len([n for n in self._nodes.values() if n.tenant_id == tenant_id]),
            total_claims=len([c for c in self._claims.values() if c.tenant_id == tenant_id]),
            total_syncs=len([s for s in self._syncs.values() if s.tenant_id == tenant_id]),
            total_partitions=len([p for p in self._partitions.values() if p.tenant_id == tenant_id]),
            total_reconciliations=len([r for r in self._reconciliations.values() if r.tenant_id == tenant_id]),
            total_violations=len([v for v in self._violations.values() if v.tenant_id == tenant_id]),
            captured_at=now,
        )
        _emit(self._events, "federated_snapshot", {"snapshot_id": snapshot_id}, snapshot_id, self._clock)
        return snap

    # -------------------------------------------------------------------
    # Closure report
    # -------------------------------------------------------------------

    def federated_closure_report(self, report_id: str, tenant_id: str) -> FederatedClosureReport:
        now = self._now()
        report = FederatedClosureReport(
            report_id=report_id, tenant_id=tenant_id,
            total_nodes=len([n for n in self._nodes.values() if n.tenant_id == tenant_id]),
            total_claims=len([c for c in self._claims.values() if c.tenant_id == tenant_id]),
            total_syncs=len([s for s in self._syncs.values() if s.tenant_id == tenant_id]),
            total_violations=len([v for v in self._violations.values() if v.tenant_id == tenant_id]),
            created_at=now,
        )
        _emit(self._events, "federated_closure_report", {"report_id": report_id}, report_id, self._clock)
        return report

    # -------------------------------------------------------------------
    # Violations
    # -------------------------------------------------------------------

    def detect_federated_violations(self, tenant_id: str) -> tuple[FederatedViolation, ...]:
        new_violations: list[FederatedViolation] = []
        now = self._now()

        # 1. Stale sync: claims still STALE
        for c in self._claims.values():
            if c.tenant_id != tenant_id:
                continue
            if c.sync == SyncDisposition.STALE:
                vid = stable_identifier("viol-fed", {"claim_id": c.claim_id, "reason": "stale_sync"})
                if vid not in self._violations:
                    v = FederatedViolation(
                        violation_id=vid, tenant_id=tenant_id,
                        operation="stale_sync",
                        reason="claim has stale sync",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # 2. Unresolved partition: partition with no reconciliation
        for p in self._partitions.values():
            if p.tenant_id != tenant_id:
                continue
            node = self._nodes.get(p.node_ref)
            if node and node.status == FederationStatus.PARTITIONED:
                vid = stable_identifier("viol-fed", {"partition_id": p.partition_id, "reason": "unresolved_partition"})
                if vid not in self._violations:
                    v = FederatedViolation(
                        violation_id=vid, tenant_id=tenant_id,
                        operation="unresolved_partition",
                        reason="partition remains unresolved",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # 3. Conflicted claim still not reconciled
        for c in self._claims.values():
            if c.tenant_id != tenant_id:
                continue
            if c.sync == SyncDisposition.CONFLICTED:
                vid = stable_identifier("viol-fed", {"claim_id": c.claim_id, "reason": "conflicted_claim"})
                if vid not in self._violations:
                    v = FederatedViolation(
                        violation_id=vid, tenant_id=tenant_id,
                        operation="conflicted_claim",
                        reason="claim is conflicted",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        if new_violations:
            _emit(self._events, "detect_federated_violations", {
                "tenant_id": tenant_id, "count": len(new_violations),
            }, tenant_id, self._clock)
        return tuple(new_violations)

    # -------------------------------------------------------------------
    # Collections / snapshot / state_hash
    # -------------------------------------------------------------------

    def _collections(self) -> dict[str, Any]:
        return {
            "nodes": self._nodes,
            "claims": self._claims,
            "syncs": self._syncs,
            "reconciliations": self._reconciliations,
            "partitions": self._partitions,
            "decisions": self._decisions,
            "violations": self._violations,
        }

    def snapshot(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name, collection in self._collections().items():
            if isinstance(collection, dict):
                result[name] = {
                    k: v.to_dict() if hasattr(v, "to_dict") else v
                    for k, v in collection.items()
                }
            elif isinstance(collection, list):
                result[name] = [
                    v.to_dict() if hasattr(v, "to_dict") else v
                    for v in collection
                ]
        result["_state_hash"] = self.state_hash()
        return result

    def state_hash(self) -> str:
        parts: list[str] = []
        for k in sorted(self._nodes):
            parts.append(f"node:{k}:{self._nodes[k].status.value}")
        for k in sorted(self._claims):
            parts.append(f"claim:{k}:{self._claims[k].sync.value}")
        for k in sorted(self._syncs):
            parts.append(f"sync:{k}:{self._syncs[k].disposition.value}")
        for k in sorted(self._reconciliations):
            parts.append(f"reconciliation:{k}:{self._reconciliations[k].resolved}")
        for k in sorted(self._partitions):
            parts.append(f"partition:{k}:{self._partitions[k].policy.value}")
        for k in sorted(self._violations):
            parts.append(f"violation:{k}")
        return sha256("|".join(parts).encode()).hexdigest()
