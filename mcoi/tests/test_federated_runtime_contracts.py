"""Tests for federated runtime contracts (~200 tests).

Covers: FederatedNode, FederatedClaim, SyncRecord, ReconciliationRecord,
    PartitionRecord, FederatedDecision, FederatedAssessment, FederatedViolation,
    FederatedSnapshot, FederatedClosureReport, and all enums.
"""

import pytest
from dataclasses import FrozenInstanceError

from mcoi_runtime.contracts.federated_runtime import (
    FederatedNode,
    FederatedClaim,
    SyncRecord,
    ReconciliationRecord,
    PartitionRecord,
    FederatedDecision,
    FederatedAssessment,
    FederatedViolation,
    FederatedSnapshot,
    FederatedClosureReport,
    FederationStatus,
    NodeRole,
    SyncDisposition,
    ReconciliationMode,
    PartitionPolicy,
    FederatedRiskLevel,
)

_NOW = "2026-01-01T00:00:00+00:00"


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestFederationStatusEnum:
    def test_values(self):
        assert FederationStatus.CONNECTED.value == "connected"
        assert FederationStatus.DEGRADED.value == "degraded"
        assert FederationStatus.PARTITIONED.value == "partitioned"
        assert FederationStatus.DISCONNECTED.value == "disconnected"

    def test_member_count(self):
        assert len(FederationStatus) == 4


class TestNodeRoleEnum:
    def test_values(self):
        assert NodeRole.PRIMARY.value == "primary"
        assert NodeRole.SECONDARY.value == "secondary"
        assert NodeRole.EDGE.value == "edge"
        assert NodeRole.OBSERVER.value == "observer"

    def test_member_count(self):
        assert len(NodeRole) == 4


class TestSyncDispositionEnum:
    def test_values(self):
        assert SyncDisposition.SYNCED.value == "synced"
        assert SyncDisposition.PENDING.value == "pending"
        assert SyncDisposition.CONFLICTED.value == "conflicted"
        assert SyncDisposition.STALE.value == "stale"

    def test_member_count(self):
        assert len(SyncDisposition) == 4


class TestReconciliationModeEnum:
    def test_values(self):
        assert ReconciliationMode.LAST_WRITE_WINS.value == "last_write_wins"
        assert ReconciliationMode.MERGE.value == "merge"
        assert ReconciliationMode.MANUAL.value == "manual"
        assert ReconciliationMode.REJECT.value == "reject"

    def test_member_count(self):
        assert len(ReconciliationMode) == 4


class TestPartitionPolicyEnum:
    def test_values(self):
        assert PartitionPolicy.FAIL_CLOSED.value == "fail_closed"
        assert PartitionPolicy.DEGRADE.value == "degrade"
        assert PartitionPolicy.LOCAL_AUTONOMY.value == "local_autonomy"
        assert PartitionPolicy.REJECT.value == "reject"

    def test_member_count(self):
        assert len(PartitionPolicy) == 4


class TestFederatedRiskLevelEnum:
    def test_values(self):
        assert FederatedRiskLevel.LOW.value == "low"
        assert FederatedRiskLevel.MEDIUM.value == "medium"
        assert FederatedRiskLevel.HIGH.value == "high"
        assert FederatedRiskLevel.CRITICAL.value == "critical"

    def test_member_count(self):
        assert len(FederatedRiskLevel) == 4


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _node(**ov):
    d = dict(node_id="n1", tenant_id="t1", display_name="Node1",
             role=NodeRole.PRIMARY, status=FederationStatus.CONNECTED, created_at=_NOW)
    d.update(ov)
    return FederatedNode(**d)


def _claim(**ov):
    d = dict(claim_id="c1", tenant_id="t1", origin_node_ref="n1",
             content="fact", trust_level=0.5, sync=SyncDisposition.PENDING, created_at=_NOW)
    d.update(ov)
    return FederatedClaim(**d)


def _sync(**ov):
    d = dict(sync_id="s1", tenant_id="t1", source_node_ref="n1",
             target_node_ref="n2", claim_count=0, disposition=SyncDisposition.SYNCED, synced_at=_NOW)
    d.update(ov)
    return SyncRecord(**d)


def _reconciliation(**ov):
    d = dict(reconciliation_id="r1", tenant_id="t1", claim_a_ref="c1",
             claim_b_ref="c2", mode=ReconciliationMode.LAST_WRITE_WINS, resolved=True, created_at=_NOW)
    d.update(ov)
    return ReconciliationRecord(**d)


def _partition(**ov):
    d = dict(partition_id="p1", tenant_id="t1", node_ref="n1",
             policy=PartitionPolicy.FAIL_CLOSED, duration_ms=100.0, detected_at=_NOW)
    d.update(ov)
    return PartitionRecord(**d)


def _decision(**ov):
    d = dict(decision_id="d1", tenant_id="t1", node_ref="n1",
             disposition="approved", reason="ok", decided_at=_NOW)
    d.update(ov)
    return FederatedDecision(**d)


def _assessment(**ov):
    d = dict(assessment_id="a1", tenant_id="t1", total_nodes=1, total_claims=1,
             total_partitions=0, sync_rate=0.5, assessed_at=_NOW)
    d.update(ov)
    return FederatedAssessment(**d)


def _violation(**ov):
    d = dict(violation_id="v1", tenant_id="t1", operation="stale_sync",
             reason="stale", detected_at=_NOW)
    d.update(ov)
    return FederatedViolation(**d)


def _snapshot(**ov):
    d = dict(snapshot_id="snap1", tenant_id="t1", total_nodes=1, total_claims=1,
             total_syncs=0, total_partitions=0, total_reconciliations=0,
             total_violations=0, captured_at=_NOW)
    d.update(ov)
    return FederatedSnapshot(**d)


def _closure(**ov):
    d = dict(report_id="rpt1", tenant_id="t1", total_nodes=1, total_claims=1,
             total_syncs=0, total_violations=0, created_at=_NOW)
    d.update(ov)
    return FederatedClosureReport(**d)


# ---------------------------------------------------------------------------
# FederatedNode tests
# ---------------------------------------------------------------------------


class TestFederatedNode:
    def test_valid_construction(self):
        n = _node()
        assert n.node_id == "n1"
        assert n.tenant_id == "t1"
        assert n.role is NodeRole.PRIMARY
        assert n.status is FederationStatus.CONNECTED

    def test_all_roles(self):
        for role in NodeRole:
            n = _node(role=role)
            assert n.role is role

    def test_all_statuses(self):
        for status in FederationStatus:
            n = _node(status=status)
            assert n.status is status

    def test_empty_node_id_rejected(self):
        with pytest.raises(ValueError, match="node_id"):
            _node(node_id="")

    def test_whitespace_node_id_rejected(self):
        with pytest.raises(ValueError, match="node_id"):
            _node(node_id="   ")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _node(tenant_id="")

    def test_empty_display_name_rejected(self):
        with pytest.raises(ValueError, match="display_name"):
            _node(display_name="")

    def test_invalid_role_rejected(self):
        with pytest.raises(ValueError, match="role"):
            _node(role="admin")

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError, match="status"):
            _node(status="unknown")

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _node(created_at="not-a-date")

    def test_frozen(self):
        n = _node()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(n, "node_id", "x")

    def test_to_dict(self):
        n = _node()
        d = n.to_dict()
        assert d["node_id"] == "n1"
        assert d["role"] is NodeRole.PRIMARY

    def test_to_json_dict(self):
        d = _node().to_json_dict()
        assert d["role"] == "primary"
        assert d["status"] == "connected"

    def test_metadata_frozen(self):
        n = _node(metadata={"k": "v"})
        with pytest.raises(TypeError):
            n.metadata["new"] = "val"

    def test_metadata_preserved_in_to_dict(self):
        n = _node(metadata={"k": "v"})
        assert "k" in n.to_dict()["metadata"]


# ---------------------------------------------------------------------------
# FederatedClaim tests
# ---------------------------------------------------------------------------


class TestFederatedClaim:
    def test_valid_construction(self):
        c = _claim()
        assert c.claim_id == "c1"
        assert c.trust_level == 0.5
        assert c.sync is SyncDisposition.PENDING

    def test_all_sync_dispositions(self):
        for sd in SyncDisposition:
            c = _claim(sync=sd)
            assert c.sync is sd

    def test_trust_level_zero(self):
        c = _claim(trust_level=0.0)
        assert c.trust_level == 0.0

    def test_trust_level_one(self):
        c = _claim(trust_level=1.0)
        assert c.trust_level == 1.0

    def test_trust_level_negative_rejected(self):
        with pytest.raises(ValueError, match="trust_level"):
            _claim(trust_level=-0.1)

    def test_trust_level_above_one_rejected(self):
        with pytest.raises(ValueError, match="trust_level"):
            _claim(trust_level=1.1)

    def test_trust_level_nan_rejected(self):
        with pytest.raises(ValueError, match="trust_level"):
            _claim(trust_level=float("nan"))

    def test_trust_level_inf_rejected(self):
        with pytest.raises(ValueError, match="trust_level"):
            _claim(trust_level=float("inf"))

    def test_trust_level_bool_rejected(self):
        with pytest.raises(ValueError, match="trust_level"):
            _claim(trust_level=True)

    def test_empty_claim_id_rejected(self):
        with pytest.raises(ValueError, match="claim_id"):
            _claim(claim_id="")

    def test_empty_content_rejected(self):
        with pytest.raises(ValueError, match="content"):
            _claim(content="")

    def test_empty_origin_node_ref_rejected(self):
        with pytest.raises(ValueError, match="origin_node_ref"):
            _claim(origin_node_ref="")

    def test_invalid_sync_rejected(self):
        with pytest.raises(ValueError, match="sync"):
            _claim(sync="invalid")

    def test_frozen(self):
        c = _claim()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(c, "claim_id", "x")

    def test_to_dict_preserves_enum(self):
        d = _claim().to_dict()
        assert d["sync"] is SyncDisposition.PENDING

    def test_to_json_dict_converts_enum(self):
        d = _claim().to_json_dict()
        assert d["sync"] == "pending"


# ---------------------------------------------------------------------------
# SyncRecord tests
# ---------------------------------------------------------------------------


class TestSyncRecord:
    def test_valid_construction(self):
        s = _sync()
        assert s.sync_id == "s1"
        assert s.claim_count == 0

    def test_claim_count_positive(self):
        s = _sync(claim_count=10)
        assert s.claim_count == 10

    def test_claim_count_negative_rejected(self):
        with pytest.raises(ValueError, match="claim_count"):
            _sync(claim_count=-1)

    def test_claim_count_bool_rejected(self):
        with pytest.raises(ValueError, match="claim_count"):
            _sync(claim_count=True)

    def test_empty_sync_id_rejected(self):
        with pytest.raises(ValueError, match="sync_id"):
            _sync(sync_id="")

    def test_empty_source_node_ref_rejected(self):
        with pytest.raises(ValueError, match="source_node_ref"):
            _sync(source_node_ref="")

    def test_empty_target_node_ref_rejected(self):
        with pytest.raises(ValueError, match="target_node_ref"):
            _sync(target_node_ref="")

    def test_invalid_disposition_rejected(self):
        with pytest.raises(ValueError, match="disposition"):
            _sync(disposition="invalid")

    def test_frozen(self):
        s = _sync()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, "sync_id", "x")

    def test_all_dispositions(self):
        for d in SyncDisposition:
            s = _sync(disposition=d)
            assert s.disposition is d

    def test_to_dict(self):
        d = _sync().to_dict()
        assert d["disposition"] is SyncDisposition.SYNCED


# ---------------------------------------------------------------------------
# ReconciliationRecord tests
# ---------------------------------------------------------------------------


class TestReconciliationRecord:
    def test_valid_construction(self):
        r = _reconciliation()
        assert r.reconciliation_id == "r1"
        assert r.resolved is True

    def test_resolved_false(self):
        r = _reconciliation(resolved=False)
        assert r.resolved is False

    def test_resolved_non_bool_rejected(self):
        with pytest.raises(ValueError, match="resolved"):
            _reconciliation(resolved=1)

    def test_resolved_string_rejected(self):
        with pytest.raises(ValueError, match="resolved"):
            _reconciliation(resolved="true")

    def test_all_modes(self):
        for mode in ReconciliationMode:
            r = _reconciliation(mode=mode)
            assert r.mode is mode

    def test_invalid_mode_rejected(self):
        with pytest.raises(ValueError, match="mode"):
            _reconciliation(mode="auto")

    def test_empty_reconciliation_id_rejected(self):
        with pytest.raises(ValueError, match="reconciliation_id"):
            _reconciliation(reconciliation_id="")

    def test_empty_claim_a_ref_rejected(self):
        with pytest.raises(ValueError, match="claim_a_ref"):
            _reconciliation(claim_a_ref="")

    def test_empty_claim_b_ref_rejected(self):
        with pytest.raises(ValueError, match="claim_b_ref"):
            _reconciliation(claim_b_ref="")

    def test_frozen(self):
        r = _reconciliation()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(r, "reconciliation_id", "x")

    def test_to_dict(self):
        d = _reconciliation().to_dict()
        assert d["mode"] is ReconciliationMode.LAST_WRITE_WINS


# ---------------------------------------------------------------------------
# PartitionRecord tests
# ---------------------------------------------------------------------------


class TestPartitionRecord:
    def test_valid_construction(self):
        p = _partition()
        assert p.partition_id == "p1"
        assert p.duration_ms == 100.0

    def test_duration_zero(self):
        p = _partition(duration_ms=0.0)
        assert p.duration_ms == 0.0

    def test_duration_negative_rejected(self):
        with pytest.raises(ValueError, match="duration_ms"):
            _partition(duration_ms=-1.0)

    def test_duration_nan_rejected(self):
        with pytest.raises(ValueError, match="duration_ms"):
            _partition(duration_ms=float("nan"))

    def test_duration_inf_rejected(self):
        with pytest.raises(ValueError, match="duration_ms"):
            _partition(duration_ms=float("inf"))

    def test_all_policies(self):
        for policy in PartitionPolicy:
            p = _partition(policy=policy)
            assert p.policy is policy

    def test_invalid_policy_rejected(self):
        with pytest.raises(ValueError, match="policy"):
            _partition(policy="auto")

    def test_empty_partition_id_rejected(self):
        with pytest.raises(ValueError, match="partition_id"):
            _partition(partition_id="")

    def test_empty_node_ref_rejected(self):
        with pytest.raises(ValueError, match="node_ref"):
            _partition(node_ref="")

    def test_frozen(self):
        p = _partition()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(p, "partition_id", "x")

    def test_to_dict(self):
        d = _partition().to_dict()
        assert d["policy"] is PartitionPolicy.FAIL_CLOSED


# ---------------------------------------------------------------------------
# FederatedDecision tests
# ---------------------------------------------------------------------------


class TestFederatedDecision:
    def test_valid_construction(self):
        d = _decision()
        assert d.decision_id == "d1"
        assert d.disposition == "approved"

    def test_empty_decision_id_rejected(self):
        with pytest.raises(ValueError, match="decision_id"):
            _decision(decision_id="")

    def test_empty_disposition_rejected(self):
        with pytest.raises(ValueError, match="disposition"):
            _decision(disposition="")

    def test_empty_reason_rejected(self):
        with pytest.raises(ValueError, match="reason"):
            _decision(reason="")

    def test_empty_node_ref_rejected(self):
        with pytest.raises(ValueError, match="node_ref"):
            _decision(node_ref="")

    def test_frozen(self):
        d = _decision()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(d, "decision_id", "x")

    def test_to_dict(self):
        d = _decision().to_dict()
        assert d["disposition"] == "approved"


# ---------------------------------------------------------------------------
# FederatedAssessment tests
# ---------------------------------------------------------------------------


class TestFederatedAssessment:
    def test_valid_construction(self):
        a = _assessment()
        assert a.assessment_id == "a1"
        assert a.sync_rate == 0.5

    def test_sync_rate_zero(self):
        a = _assessment(sync_rate=0.0)
        assert a.sync_rate == 0.0

    def test_sync_rate_one(self):
        a = _assessment(sync_rate=1.0)
        assert a.sync_rate == 1.0

    def test_sync_rate_negative_rejected(self):
        with pytest.raises(ValueError, match="sync_rate"):
            _assessment(sync_rate=-0.1)

    def test_sync_rate_above_one_rejected(self):
        with pytest.raises(ValueError, match="sync_rate"):
            _assessment(sync_rate=1.1)

    def test_total_nodes_negative_rejected(self):
        with pytest.raises(ValueError, match="total_nodes"):
            _assessment(total_nodes=-1)

    def test_total_claims_negative_rejected(self):
        with pytest.raises(ValueError, match="total_claims"):
            _assessment(total_claims=-1)

    def test_total_partitions_negative_rejected(self):
        with pytest.raises(ValueError, match="total_partitions"):
            _assessment(total_partitions=-1)

    def test_empty_assessment_id_rejected(self):
        with pytest.raises(ValueError, match="assessment_id"):
            _assessment(assessment_id="")

    def test_frozen(self):
        a = _assessment()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(a, "assessment_id", "x")

    def test_to_dict(self):
        d = _assessment().to_dict()
        assert d["sync_rate"] == 0.5


# ---------------------------------------------------------------------------
# FederatedViolation tests
# ---------------------------------------------------------------------------


class TestFederatedViolation:
    def test_valid_construction(self):
        v = _violation()
        assert v.violation_id == "v1"

    def test_empty_violation_id_rejected(self):
        with pytest.raises(ValueError, match="violation_id"):
            _violation(violation_id="")

    def test_empty_operation_rejected(self):
        with pytest.raises(ValueError, match="operation"):
            _violation(operation="")

    def test_empty_reason_rejected(self):
        with pytest.raises(ValueError, match="reason"):
            _violation(reason="")

    def test_frozen(self):
        v = _violation()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(v, "violation_id", "x")

    def test_to_dict(self):
        d = _violation().to_dict()
        assert d["operation"] == "stale_sync"


# ---------------------------------------------------------------------------
# FederatedSnapshot tests
# ---------------------------------------------------------------------------


class TestFederatedSnapshot:
    def test_valid_construction(self):
        s = _snapshot()
        assert s.snapshot_id == "snap1"

    def test_all_counts_zero(self):
        s = _snapshot(total_nodes=0, total_claims=0, total_syncs=0,
                      total_partitions=0, total_reconciliations=0, total_violations=0)
        assert s.total_nodes == 0

    def test_total_nodes_negative_rejected(self):
        with pytest.raises(ValueError, match="total_nodes"):
            _snapshot(total_nodes=-1)

    def test_total_claims_negative_rejected(self):
        with pytest.raises(ValueError, match="total_claims"):
            _snapshot(total_claims=-1)

    def test_total_syncs_negative_rejected(self):
        with pytest.raises(ValueError, match="total_syncs"):
            _snapshot(total_syncs=-1)

    def test_total_partitions_negative_rejected(self):
        with pytest.raises(ValueError, match="total_partitions"):
            _snapshot(total_partitions=-1)

    def test_total_reconciliations_negative_rejected(self):
        with pytest.raises(ValueError, match="total_reconciliations"):
            _snapshot(total_reconciliations=-1)

    def test_total_violations_negative_rejected(self):
        with pytest.raises(ValueError, match="total_violations"):
            _snapshot(total_violations=-1)

    def test_empty_snapshot_id_rejected(self):
        with pytest.raises(ValueError, match="snapshot_id"):
            _snapshot(snapshot_id="")

    def test_frozen(self):
        s = _snapshot()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, "snapshot_id", "x")

    def test_to_dict(self):
        d = _snapshot().to_dict()
        assert d["total_nodes"] == 1


# ---------------------------------------------------------------------------
# FederatedClosureReport tests
# ---------------------------------------------------------------------------


class TestFederatedClosureReport:
    def test_valid_construction(self):
        r = _closure()
        assert r.report_id == "rpt1"

    def test_total_nodes_negative_rejected(self):
        with pytest.raises(ValueError, match="total_nodes"):
            _closure(total_nodes=-1)

    def test_total_claims_negative_rejected(self):
        with pytest.raises(ValueError, match="total_claims"):
            _closure(total_claims=-1)

    def test_total_syncs_negative_rejected(self):
        with pytest.raises(ValueError, match="total_syncs"):
            _closure(total_syncs=-1)

    def test_total_violations_negative_rejected(self):
        with pytest.raises(ValueError, match="total_violations"):
            _closure(total_violations=-1)

    def test_empty_report_id_rejected(self):
        with pytest.raises(ValueError, match="report_id"):
            _closure(report_id="")

    def test_frozen(self):
        r = _closure()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(r, "report_id", "x")

    def test_to_dict(self):
        d = _closure().to_dict()
        assert d["report_id"] == "rpt1"

    def test_to_json_dict(self):
        d = _closure().to_json_dict()
        assert isinstance(d["report_id"], str)


# ---------------------------------------------------------------------------
# Cross-cutting contract invariant tests
# ---------------------------------------------------------------------------


class TestContractCrossCutting:
    """Tests that apply across all contract types."""

    def test_node_metadata_nested_dict_frozen(self):
        n = _node(metadata={"outer": {"inner": "v"}})
        with pytest.raises(TypeError):
            n.metadata["outer"]["new"] = "fail"

    def test_claim_metadata_list_frozen(self):
        c = _claim(metadata={"items": [1, 2, 3]})
        # Lists are frozen to tuples
        assert isinstance(c.metadata["items"], tuple)

    def test_node_to_json_roundtrip(self):
        import json
        n = _node()
        j = n.to_json()
        parsed = json.loads(j)
        assert parsed["node_id"] == "n1"
        assert parsed["role"] == "primary"

    def test_claim_to_json_roundtrip(self):
        import json
        c = _claim()
        j = c.to_json()
        parsed = json.loads(j)
        assert parsed["claim_id"] == "c1"
        assert parsed["sync"] == "pending"

    def test_sync_to_json_roundtrip(self):
        import json
        s = _sync()
        j = s.to_json()
        parsed = json.loads(j)
        assert parsed["sync_id"] == "s1"

    def test_reconciliation_to_json_roundtrip(self):
        import json
        r = _reconciliation()
        j = r.to_json()
        parsed = json.loads(j)
        assert parsed["mode"] == "last_write_wins"

    def test_partition_to_json_roundtrip(self):
        import json
        p = _partition()
        j = p.to_json()
        parsed = json.loads(j)
        assert parsed["policy"] == "fail_closed"

    def test_all_contracts_have_to_dict(self):
        objs = [_node(), _claim(), _sync(), _reconciliation(),
                _partition(), _decision(), _assessment(), _violation(),
                _snapshot(), _closure()]
        for obj in objs:
            d = obj.to_dict()
            assert isinstance(d, dict)

    def test_all_contracts_have_to_json_dict(self):
        objs = [_node(), _claim(), _sync(), _reconciliation(),
                _partition(), _decision(), _assessment(), _violation(),
                _snapshot(), _closure()]
        for obj in objs:
            d = obj.to_json_dict()
            assert isinstance(d, dict)

    def test_all_contracts_have_to_json(self):
        import json
        objs = [_node(), _claim(), _sync(), _reconciliation(),
                _partition(), _decision(), _assessment(), _violation(),
                _snapshot(), _closure()]
        for obj in objs:
            j = obj.to_json()
            assert isinstance(json.loads(j), dict)

    def test_all_contracts_frozen(self):
        objs = [_node(), _claim(), _sync(), _reconciliation(),
                _partition(), _decision(), _assessment(), _violation(),
                _snapshot(), _closure()]
        for obj in objs:
            with pytest.raises((FrozenInstanceError, AttributeError)):
                setattr(obj, "tenant_id", "x")

    def test_invalid_datetime_all_contracts(self):
        with pytest.raises(ValueError):
            _node(created_at="bad")
        with pytest.raises(ValueError):
            _claim(created_at="bad")
        with pytest.raises(ValueError):
            _sync(synced_at="bad")
        with pytest.raises(ValueError):
            _reconciliation(created_at="bad")
        with pytest.raises(ValueError):
            _partition(detected_at="bad")
        with pytest.raises(ValueError):
            _decision(decided_at="bad")
        with pytest.raises(ValueError):
            _assessment(assessed_at="bad")
        with pytest.raises(ValueError):
            _violation(detected_at="bad")
        with pytest.raises(ValueError):
            _snapshot(captured_at="bad")
        with pytest.raises(ValueError):
            _closure(created_at="bad")

    def test_empty_tenant_id_all_contracts(self):
        with pytest.raises(ValueError):
            _node(tenant_id="")
        with pytest.raises(ValueError):
            _claim(tenant_id="")
        with pytest.raises(ValueError):
            _sync(tenant_id="")
        with pytest.raises(ValueError):
            _reconciliation(tenant_id="")
        with pytest.raises(ValueError):
            _partition(tenant_id="")
        with pytest.raises(ValueError):
            _decision(tenant_id="")
        with pytest.raises(ValueError):
            _assessment(tenant_id="")
        with pytest.raises(ValueError):
            _violation(tenant_id="")
        with pytest.raises(ValueError):
            _snapshot(tenant_id="")
        with pytest.raises(ValueError):
            _closure(tenant_id="")
