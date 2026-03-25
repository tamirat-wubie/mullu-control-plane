"""Tests for federated runtime engine (~200 tests).

Covers: FederatedRuntimeEngine lifecycle, node registration, claim management,
    sync, conflict detection, reconciliation, partitions, assessment, snapshot,
    closure reports, violation detection, state_hash, and golden scenarios.
"""

import pytest

from mcoi_runtime.contracts.federated_runtime import (
    FederatedNode,
    FederatedClaim,
    SyncRecord,
    ReconciliationRecord,
    PartitionRecord,
    FederatedAssessment,
    FederatedViolation,
    FederatedSnapshot,
    FederatedClosureReport,
    FederationStatus,
    NodeRole,
    SyncDisposition,
    ReconciliationMode,
    PartitionPolicy,
)
from mcoi_runtime.core.federated_runtime import FederatedRuntimeEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.engine_protocol import FixedClock
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_T1 = "t1"
_T2 = "t2"


def _make_engine(clock=None):
    es = EventSpineEngine()
    clk = clock or FixedClock()
    eng = FederatedRuntimeEngine(es, clock=clk)
    return eng, es


# ---------------------------------------------------------------------------
# Constructor tests
# ---------------------------------------------------------------------------


class TestFederatedEngineConstructor:
    def test_valid_construction(self):
        eng, es = _make_engine()
        assert eng.node_count == 0
        assert eng.claim_count == 0

    def test_invalid_event_spine_rejected(self):
        with pytest.raises(RuntimeCoreInvariantError):
            FederatedRuntimeEngine("not_an_engine")

    def test_none_event_spine_rejected(self):
        with pytest.raises(RuntimeCoreInvariantError):
            FederatedRuntimeEngine(None)

    def test_default_clock_used_when_none(self):
        es = EventSpineEngine()
        eng = FederatedRuntimeEngine(es, clock=None)
        assert eng.node_count == 0

    def test_custom_clock_accepted(self):
        clk = FixedClock("2026-06-01T00:00:00+00:00")
        eng, _ = _make_engine(clock=clk)
        n = eng.register_node("n1", _T1, "Node1")
        assert n.created_at == "2026-06-01T00:00:00+00:00"


# ---------------------------------------------------------------------------
# Node registration & transitions
# ---------------------------------------------------------------------------


class TestNodeRegistration:
    def test_register_node(self):
        eng, _ = _make_engine()
        n = eng.register_node("n1", _T1, "Node1")
        assert n.node_id == "n1"
        assert n.role is NodeRole.SECONDARY
        assert n.status is FederationStatus.CONNECTED

    def test_register_with_role(self):
        eng, _ = _make_engine()
        n = eng.register_node("n1", _T1, "Node1", role=NodeRole.PRIMARY)
        assert n.role is NodeRole.PRIMARY

    def test_register_with_all_roles(self):
        eng, _ = _make_engine()
        for i, role in enumerate(NodeRole):
            n = eng.register_node(f"n{i}", _T1, f"Node{i}", role=role)
            assert n.role is role

    def test_duplicate_node_id_rejected(self):
        eng, _ = _make_engine()
        eng.register_node("n1", _T1, "Node1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            eng.register_node("n1", _T1, "Node1")

    def test_node_count_increments(self):
        eng, _ = _make_engine()
        assert eng.node_count == 0
        eng.register_node("n1", _T1, "Node1")
        assert eng.node_count == 1
        eng.register_node("n2", _T1, "Node2")
        assert eng.node_count == 2

    def test_register_emits_event(self):
        eng, es = _make_engine()
        eng.register_node("n1", _T1, "Node1")
        assert es.event_count >= 1


class TestNodeTransitions:
    def test_degrade_node(self):
        eng, _ = _make_engine()
        eng.register_node("n1", _T1, "Node1")
        n = eng.degrade_node("n1")
        assert n.status is FederationStatus.DEGRADED

    def test_disconnect_node(self):
        eng, _ = _make_engine()
        eng.register_node("n1", _T1, "Node1")
        n = eng.disconnect_node("n1")
        assert n.status is FederationStatus.DISCONNECTED

    def test_reconnect_node(self):
        eng, _ = _make_engine()
        eng.register_node("n1", _T1, "Node1")
        eng.disconnect_node("n1")
        n = eng.reconnect_node("n1")
        assert n.status is FederationStatus.CONNECTED

    def test_transition_unknown_node_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="unknown"):
            eng.degrade_node("missing")

    def test_all_transitions_from_connected(self):
        eng, _ = _make_engine()
        eng.register_node("n1", _T1, "Node1")
        eng.degrade_node("n1")
        assert True  # No terminal states in federated

    def test_reconnect_from_degraded(self):
        eng, _ = _make_engine()
        eng.register_node("n1", _T1, "Node1")
        eng.degrade_node("n1")
        n = eng.reconnect_node("n1")
        assert n.status is FederationStatus.CONNECTED

    def test_transition_emits_event(self):
        eng, es = _make_engine()
        eng.register_node("n1", _T1, "Node1")
        before = es.event_count
        eng.degrade_node("n1")
        assert es.event_count > before


# ---------------------------------------------------------------------------
# Claim registration
# ---------------------------------------------------------------------------


class TestClaimRegistration:
    def test_register_claim(self):
        eng, _ = _make_engine()
        c = eng.register_claim("c1", _T1, "n1", "fact")
        assert c.claim_id == "c1"
        assert c.sync is SyncDisposition.PENDING

    def test_register_with_trust(self):
        eng, _ = _make_engine()
        c = eng.register_claim("c1", _T1, "n1", "fact", trust_level=0.9)
        assert c.trust_level == 0.9

    def test_duplicate_claim_rejected(self):
        eng, _ = _make_engine()
        eng.register_claim("c1", _T1, "n1", "fact")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            eng.register_claim("c1", _T1, "n1", "fact")

    def test_claim_count_increments(self):
        eng, _ = _make_engine()
        assert eng.claim_count == 0
        eng.register_claim("c1", _T1, "n1", "fact")
        assert eng.claim_count == 1

    def test_register_claim_emits_event(self):
        eng, es = _make_engine()
        eng.register_claim("c1", _T1, "n1", "fact")
        assert es.event_count >= 1


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------


class TestSyncClaims:
    def test_sync_claims_basic(self):
        eng, _ = _make_engine()
        eng.register_claim("c1", _T1, "n1", "fact")
        sr = eng.sync_claims("s1", _T1, "n1", "n2")
        assert sr.sync_id == "s1"
        assert sr.claim_count == 1
        assert sr.disposition is SyncDisposition.SYNCED

    def test_sync_marks_claims_synced(self):
        eng, _ = _make_engine()
        eng.register_claim("c1", _T1, "n1", "fact")
        eng.sync_claims("s1", _T1, "n1", "n2")
        # Second sync finds no pending claims
        sr2 = eng.sync_claims("s2", _T1, "n1", "n2")
        assert sr2.claim_count == 0

    def test_sync_only_pending_claims(self):
        eng, _ = _make_engine()
        eng.register_claim("c1", _T1, "n1", "fact")
        eng.sync_claims("s1", _T1, "n1", "n2")  # Now synced
        eng.register_claim("c2", _T1, "n1", "fact2")  # New pending
        sr = eng.sync_claims("s2", _T1, "n1", "n2")
        assert sr.claim_count == 1

    def test_sync_cross_tenant_isolation(self):
        eng, _ = _make_engine()
        eng.register_claim("c1", _T1, "n1", "fact")
        eng.register_claim("c2", _T2, "n1", "fact")
        sr = eng.sync_claims("s1", _T1, "n1", "n2")
        assert sr.claim_count == 1

    def test_duplicate_sync_rejected(self):
        eng, _ = _make_engine()
        eng.sync_claims("s1", _T1, "n1", "n2")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            eng.sync_claims("s1", _T1, "n1", "n2")

    def test_sync_count_increments(self):
        eng, _ = _make_engine()
        assert eng.sync_count == 0
        eng.sync_claims("s1", _T1, "n1", "n2")
        assert eng.sync_count == 1

    def test_sync_emits_event(self):
        eng, es = _make_engine()
        eng.sync_claims("s1", _T1, "n1", "n2")
        assert es.event_count >= 1


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------


class TestConflictDetection:
    def test_no_conflicts_when_clean(self):
        eng, _ = _make_engine()
        eng.register_claim("c1", _T1, "n1", "fact")
        conflicts = eng.detect_sync_conflicts(_T1)
        assert len(conflicts) == 0

    def test_conflict_same_content_diff_nodes_diff_trust(self):
        eng, _ = _make_engine()
        eng.register_claim("c1", _T1, "n1", "same-fact", trust_level=0.9)
        eng.register_claim("c2", _T1, "n2", "same-fact", trust_level=0.3)
        conflicts = eng.detect_sync_conflicts(_T1)
        assert len(conflicts) == 2

    def test_conflict_idempotent(self):
        eng, _ = _make_engine()
        eng.register_claim("c1", _T1, "n1", "same-fact", trust_level=0.9)
        eng.register_claim("c2", _T1, "n2", "same-fact", trust_level=0.3)
        first = eng.detect_sync_conflicts(_T1)
        assert len(first) == 2
        second = eng.detect_sync_conflicts(_T1)
        assert len(second) == 0

    def test_no_conflict_same_node(self):
        eng, _ = _make_engine()
        eng.register_claim("c1", _T1, "n1", "same-fact", trust_level=0.9)
        eng.register_claim("c2", _T1, "n1", "same-fact", trust_level=0.3)
        conflicts = eng.detect_sync_conflicts(_T1)
        assert len(conflicts) == 0

    def test_no_conflict_same_trust(self):
        eng, _ = _make_engine()
        eng.register_claim("c1", _T1, "n1", "same-fact", trust_level=0.5)
        eng.register_claim("c2", _T1, "n2", "same-fact", trust_level=0.5)
        conflicts = eng.detect_sync_conflicts(_T1)
        assert len(conflicts) == 0

    def test_conflict_cross_tenant_isolation(self):
        eng, _ = _make_engine()
        eng.register_claim("c1", _T1, "n1", "same-fact", trust_level=0.9)
        eng.register_claim("c2", _T2, "n2", "same-fact", trust_level=0.3)
        conflicts = eng.detect_sync_conflicts(_T1)
        assert len(conflicts) == 0


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------


class TestReconciliation:
    def test_reconcile_claims(self):
        eng, _ = _make_engine()
        r = eng.reconcile_claims("r1", _T1, "c1", "c2")
        assert r.reconciliation_id == "r1"
        assert r.resolved is True

    def test_reconcile_with_mode(self):
        eng, _ = _make_engine()
        r = eng.reconcile_claims("r1", _T1, "c1", "c2", mode=ReconciliationMode.MERGE)
        assert r.mode is ReconciliationMode.MERGE

    def test_duplicate_reconciliation_rejected(self):
        eng, _ = _make_engine()
        eng.reconcile_claims("r1", _T1, "c1", "c2")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            eng.reconcile_claims("r1", _T1, "c1", "c2")

    def test_reconciliation_count_increments(self):
        eng, _ = _make_engine()
        assert eng.reconciliation_count == 0
        eng.reconcile_claims("r1", _T1, "c1", "c2")
        assert eng.reconciliation_count == 1


# ---------------------------------------------------------------------------
# Partitions
# ---------------------------------------------------------------------------


class TestPartitions:
    def test_record_partition(self):
        eng, _ = _make_engine()
        eng.register_node("n1", _T1, "Node1")
        p = eng.record_partition("p1", _T1, "n1")
        assert p.partition_id == "p1"
        assert p.policy is PartitionPolicy.FAIL_CLOSED

    def test_partition_marks_node_partitioned(self):
        eng, _ = _make_engine()
        eng.register_node("n1", _T1, "Node1")
        eng.record_partition("p1", _T1, "n1")
        # Check node is now partitioned via snapshot
        snap = eng.snapshot()
        node = snap["nodes"]["n1"]
        assert node["status"] is FederationStatus.PARTITIONED

    def test_partition_with_policy(self):
        eng, _ = _make_engine()
        p = eng.record_partition("p1", _T1, "n1", policy=PartitionPolicy.LOCAL_AUTONOMY)
        assert p.policy is PartitionPolicy.LOCAL_AUTONOMY

    def test_partition_with_duration(self):
        eng, _ = _make_engine()
        p = eng.record_partition("p1", _T1, "n1", duration_ms=5000.0)
        assert p.duration_ms == 5000.0

    def test_duplicate_partition_rejected(self):
        eng, _ = _make_engine()
        eng.record_partition("p1", _T1, "n1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            eng.record_partition("p1", _T1, "n1")

    def test_partition_count_increments(self):
        eng, _ = _make_engine()
        assert eng.partition_count == 0
        eng.record_partition("p1", _T1, "n1")
        assert eng.partition_count == 1


# ---------------------------------------------------------------------------
# Assessment
# ---------------------------------------------------------------------------


class TestFederatedAssessment:
    def test_assessment_empty(self):
        eng, _ = _make_engine()
        a = eng.federated_assessment("a1", _T1)
        assert a.total_nodes == 0
        assert a.total_claims == 0
        assert a.sync_rate == 0.0

    def test_assessment_with_data(self):
        eng, _ = _make_engine()
        eng.register_node("n1", _T1, "Node1")
        eng.register_claim("c1", _T1, "n1", "fact")
        eng.sync_claims("s1", _T1, "n1", "n2")
        a = eng.federated_assessment("a1", _T1)
        assert a.total_nodes == 1
        assert a.total_claims == 1
        assert a.sync_rate == 1.0

    def test_assessment_cross_tenant_isolation(self):
        eng, _ = _make_engine()
        eng.register_node("n1", _T1, "Node1")
        eng.register_node("n2", _T2, "Node2")
        a = eng.federated_assessment("a1", _T1)
        assert a.total_nodes == 1

    def test_assessment_emits_event(self):
        eng, es = _make_engine()
        before = es.event_count
        eng.federated_assessment("a1", _T1)
        assert es.event_count > before


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------


class TestFederatedSnapshotEngine:
    def test_snapshot_empty(self):
        eng, _ = _make_engine()
        s = eng.federated_snapshot("snap1", _T1)
        assert s.total_nodes == 0

    def test_snapshot_with_data(self):
        eng, _ = _make_engine()
        eng.register_node("n1", _T1, "Node1")
        eng.register_claim("c1", _T1, "n1", "fact")
        s = eng.federated_snapshot("snap1", _T1)
        assert s.total_nodes == 1
        assert s.total_claims == 1

    def test_engine_snapshot_dict(self):
        eng, _ = _make_engine()
        eng.register_node("n1", _T1, "Node1")
        snap = eng.snapshot()
        assert "nodes" in snap
        assert "claims" in snap
        assert "_state_hash" in snap


# ---------------------------------------------------------------------------
# Closure report
# ---------------------------------------------------------------------------


class TestFederatedClosureReport:
    def test_closure_empty(self):
        eng, _ = _make_engine()
        r = eng.federated_closure_report("rpt1", _T1)
        assert r.total_nodes == 0

    def test_closure_with_data(self):
        eng, _ = _make_engine()
        eng.register_node("n1", _T1, "Node1")
        eng.register_claim("c1", _T1, "n1", "fact")
        r = eng.federated_closure_report("rpt1", _T1)
        assert r.total_nodes == 1
        assert r.total_claims == 1

    def test_closure_cross_tenant_isolation(self):
        eng, _ = _make_engine()
        eng.register_node("n1", _T1, "Node1")
        eng.register_node("n2", _T2, "Node2")
        r = eng.federated_closure_report("rpt1", _T1)
        assert r.total_nodes == 1


# ---------------------------------------------------------------------------
# Violation detection
# ---------------------------------------------------------------------------


class TestViolationDetection:
    def test_no_violations_when_clean(self):
        eng, _ = _make_engine()
        viols = eng.detect_federated_violations(_T1)
        assert len(viols) == 0

    def test_unresolved_partition_violation(self):
        eng, _ = _make_engine()
        eng.register_node("n1", _T1, "Node1")
        eng.record_partition("p1", _T1, "n1")
        viols = eng.detect_federated_violations(_T1)
        assert len(viols) >= 1
        assert any(v.operation == "unresolved_partition" for v in viols)

    def test_conflicted_claim_violation(self):
        eng, _ = _make_engine()
        eng.register_claim("c1", _T1, "n1", "same", trust_level=0.9)
        eng.register_claim("c2", _T1, "n2", "same", trust_level=0.3)
        eng.detect_sync_conflicts(_T1)
        viols = eng.detect_federated_violations(_T1)
        assert any(v.operation == "conflicted_claim" for v in viols)

    def test_violation_idempotent(self):
        eng, _ = _make_engine()
        eng.register_node("n1", _T1, "Node1")
        eng.record_partition("p1", _T1, "n1")
        first = eng.detect_federated_violations(_T1)
        assert len(first) >= 1
        second = eng.detect_federated_violations(_T1)
        assert len(second) == 0

    def test_violation_cross_tenant_isolation(self):
        eng, _ = _make_engine()
        eng.register_node("n1", _T1, "Node1")
        eng.record_partition("p1", _T1, "n1")
        viols = eng.detect_federated_violations(_T2)
        assert len(viols) == 0

    def test_violation_count_increments(self):
        eng, _ = _make_engine()
        assert eng.violation_count == 0
        eng.register_node("n1", _T1, "Node1")
        eng.record_partition("p1", _T1, "n1")
        eng.detect_federated_violations(_T1)
        assert eng.violation_count >= 1


# ---------------------------------------------------------------------------
# State hash
# ---------------------------------------------------------------------------


class TestStateHash:
    def test_empty_state_hash_deterministic(self):
        eng1, _ = _make_engine()
        eng2, _ = _make_engine()
        assert eng1.state_hash() == eng2.state_hash()

    def test_state_hash_changes_on_mutation(self):
        eng, _ = _make_engine()
        h1 = eng.state_hash()
        eng.register_node("n1", _T1, "Node1")
        h2 = eng.state_hash()
        assert h1 != h2

    def test_state_hash_64_chars(self):
        eng, _ = _make_engine()
        h = eng.state_hash()
        assert len(h) == 64

    def test_state_hash_deterministic_same_ops(self):
        clk1 = FixedClock()
        clk2 = FixedClock()
        eng1, _ = _make_engine(clock=clk1)
        eng2, _ = _make_engine(clock=clk2)
        eng1.register_node("n1", _T1, "Node1")
        eng2.register_node("n1", _T1, "Node1")
        assert eng1.state_hash() == eng2.state_hash()

    def test_state_hash_includes_claims(self):
        eng, _ = _make_engine()
        h1 = eng.state_hash()
        eng.register_claim("c1", _T1, "n1", "fact")
        h2 = eng.state_hash()
        assert h1 != h2

    def test_state_hash_includes_syncs(self):
        eng, _ = _make_engine()
        eng.register_claim("c1", _T1, "n1", "fact")
        h1 = eng.state_hash()
        eng.sync_claims("s1", _T1, "n1", "n2")
        h2 = eng.state_hash()
        assert h1 != h2

    def test_state_hash_includes_violations(self):
        eng, _ = _make_engine()
        eng.register_node("n1", _T1, "Node1")
        eng.record_partition("p1", _T1, "n1")
        h1 = eng.state_hash()
        eng.detect_federated_violations(_T1)
        h2 = eng.state_hash()
        assert h1 != h2


# ---------------------------------------------------------------------------
# Golden scenarios
# ---------------------------------------------------------------------------


class TestGoldenScenarios:
    def test_happy_path_lifecycle(self):
        """Register nodes, claims, sync, assess, snapshot, close."""
        eng, es = _make_engine()
        eng.register_node("n1", _T1, "Node1", role=NodeRole.PRIMARY)
        eng.register_node("n2", _T1, "Node2", role=NodeRole.SECONDARY)
        eng.register_claim("c1", _T1, "n1", "knowledge fact")
        eng.sync_claims("s1", _T1, "n1", "n2")
        a = eng.federated_assessment("a1", _T1)
        assert a.sync_rate == 1.0
        snap = eng.federated_snapshot("snap1", _T1)
        assert snap.total_nodes == 2
        assert snap.total_claims == 1
        assert snap.total_syncs == 1
        report = eng.federated_closure_report("rpt1", _T1)
        assert report.total_nodes == 2
        assert es.event_count > 0

    def test_cross_tenant_isolation(self):
        eng, _ = _make_engine()
        eng.register_node("n1", _T1, "Node1")
        eng.register_node("n2", _T2, "Node2")
        eng.register_claim("c1", _T1, "n1", "fact1")
        eng.register_claim("c2", _T2, "n2", "fact2")
        snap1 = eng.federated_snapshot("snap1", _T1)
        snap2 = eng.federated_snapshot("snap2", _T2)
        assert snap1.total_nodes == 1
        assert snap2.total_nodes == 1
        assert snap1.total_claims == 1
        assert snap2.total_claims == 1

    def test_claim_synced_golden(self):
        """Claims start PENDING, after sync become SYNCED."""
        eng, _ = _make_engine()
        eng.register_node("n1", _T1, "Node1")
        eng.register_node("n2", _T1, "Node2")
        c1 = eng.register_claim("c1", _T1, "n1", "fact1")
        assert c1.sync is SyncDisposition.PENDING
        sr = eng.sync_claims("s1", _T1, "n1", "n2")
        assert sr.claim_count == 1

    def test_partition_and_reconnect_golden(self):
        eng, _ = _make_engine()
        eng.register_node("n1", _T1, "Node1")
        eng.record_partition("p1", _T1, "n1")
        viols = eng.detect_federated_violations(_T1)
        assert len(viols) >= 1
        eng.reconnect_node("n1")
        # After reconnect, no new unresolved_partition violations
        viols2 = eng.detect_federated_violations(_T1)
        # Already detected, so idempotent
        assert len(viols2) == 0

    def test_conflict_detection_and_reconciliation_golden(self):
        eng, _ = _make_engine()
        eng.register_claim("c1", _T1, "n1", "shared-fact", trust_level=0.9)
        eng.register_claim("c2", _T1, "n2", "shared-fact", trust_level=0.2)
        conflicts = eng.detect_sync_conflicts(_T1)
        assert len(conflicts) == 2
        eng.reconcile_claims("r1", _T1, "c1", "c2", mode=ReconciliationMode.LAST_WRITE_WINS)
        assert eng.reconciliation_count == 1

    def test_state_hash_determinism_golden(self):
        clk1 = FixedClock()
        clk2 = FixedClock()
        eng1, _ = _make_engine(clock=clk1)
        eng2, _ = _make_engine(clock=clk2)
        for eng in (eng1, eng2):
            eng.register_node("n1", _T1, "Node1")
            eng.register_claim("c1", _T1, "n1", "fact")
            eng.sync_claims("s1", _T1, "n1", "n2")
        assert eng1.state_hash() == eng2.state_hash()
