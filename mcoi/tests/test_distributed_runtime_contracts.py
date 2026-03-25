"""Comprehensive tests for distributed_runtime contracts.

Covers all 6 enums (membership counts, value strings), all 11 frozen
dataclasses (valid construction, frozen immutability, to_dict round-trip,
to_json_dict, field validators, metadata freezing, boundary values,
date-only acceptance, MappingProxyType metadata).
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.distributed_runtime import (
    BackpressureLevel,
    CheckpointDisposition,
    ConcurrencyLock,
    DistributedCheckpoint,
    DistributedClosureReport,
    DistributedSnapshot,
    DistributedViolation,
    LeaseRecord,
    LeaseStatus,
    QueueRecord,
    QueueStatus,
    RetrySchedule,
    ShardRecord,
    ShardStatus,
    WorkerRecord,
    WorkerStatus,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime.now(timezone.utc).isoformat()
DATE_ONLY = "2025-06-01"


def _worker(**overrides):
    defaults = dict(
        worker_id="w1", tenant_id="t1", display_name="Worker-A",
        status=WorkerStatus.IDLE, queue_ref="q1", capacity=10,
        active_leases=0, registered_at=NOW, metadata={"k": "v"},
    )
    defaults.update(overrides)
    return WorkerRecord(**defaults)


def _queue(**overrides):
    defaults = dict(
        queue_id="q1", tenant_id="t1", display_name="Queue-A",
        status=QueueStatus.ACTIVE, depth=5, max_depth=100,
        backpressure=BackpressureLevel.NONE, created_at=NOW,
        metadata={"env": "prod"},
    )
    defaults.update(overrides)
    return QueueRecord(**defaults)


def _lease(**overrides):
    defaults = dict(
        lease_id="l1", tenant_id="t1", worker_id="w1",
        task_ref="task-1", status=LeaseStatus.HELD, ttl_ms=30000,
        acquired_at=NOW, metadata={},
    )
    defaults.update(overrides)
    return LeaseRecord(**defaults)


def _shard(**overrides):
    defaults = dict(
        shard_id="s1", tenant_id="t1", partition_key="pk1",
        status=ShardStatus.ASSIGNED, record_count=100,
        assigned_worker="w1", created_at=NOW, metadata={},
    )
    defaults.update(overrides)
    return ShardRecord(**defaults)


def _checkpoint(**overrides):
    defaults = dict(
        checkpoint_id="cp1", tenant_id="t1",
        disposition=CheckpointDisposition.PENDING,
        shard_count=3, worker_count=2, created_at=NOW, metadata={},
    )
    defaults.update(overrides)
    return DistributedCheckpoint(**defaults)


def _retry(**overrides):
    defaults = dict(
        schedule_id="rs1", tenant_id="t1", task_ref="task-1",
        max_retries=3, retry_count=0, backoff_ms=1000,
        created_at=NOW, metadata={},
    )
    defaults.update(overrides)
    return RetrySchedule(**defaults)


def _lock(**overrides):
    defaults = dict(
        lock_id="lk1", tenant_id="t1", resource_ref="res1",
        holder_ref="w1", acquired_at=NOW, metadata={},
    )
    defaults.update(overrides)
    return ConcurrencyLock(**defaults)


def _snapshot(**overrides):
    defaults = dict(
        snapshot_id="snap1", tenant_id="t1",
        total_workers=5, total_queues=2, total_leases=3,
        total_shards=4, total_checkpoints=1, total_violations=0,
        captured_at=NOW, metadata={},
    )
    defaults.update(overrides)
    return DistributedSnapshot(**defaults)


def _violation(**overrides):
    defaults = dict(
        violation_id="v1", tenant_id="t1",
        operation="orphaned_shard", reason="shard is orphaned",
        detected_at=NOW, metadata={},
    )
    defaults.update(overrides)
    return DistributedViolation(**defaults)


def _closure(**overrides):
    defaults = dict(
        report_id="cr1", tenant_id="t1",
        total_workers=10, total_queues=3, total_leases=5,
        total_checkpoints=2, total_violations=1,
        created_at=NOW, metadata={},
    )
    defaults.update(overrides)
    return DistributedClosureReport(**defaults)


# ===================================================================
# 1. Enum membership counts and .value strings
# ===================================================================


class TestWorkerStatusEnum:
    def test_member_count(self):
        assert len(WorkerStatus) == 4

    @pytest.mark.parametrize("member,value", [
        (WorkerStatus.IDLE, "idle"),
        (WorkerStatus.ACTIVE, "active"),
        (WorkerStatus.DRAINING, "draining"),
        (WorkerStatus.TERMINATED, "terminated"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    def test_is_enum(self):
        assert hasattr(WorkerStatus, "__members__")

    def test_unique_values(self):
        vals = [m.value for m in WorkerStatus]
        assert len(vals) == len(set(vals))


class TestQueueStatusEnum:
    def test_member_count(self):
        assert len(QueueStatus) == 4

    @pytest.mark.parametrize("member,value", [
        (QueueStatus.ACTIVE, "active"),
        (QueueStatus.PAUSED, "paused"),
        (QueueStatus.DRAINING, "draining"),
        (QueueStatus.CLOSED, "closed"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    def test_unique_values(self):
        vals = [m.value for m in QueueStatus]
        assert len(vals) == len(set(vals))


class TestLeaseStatusEnum:
    def test_member_count(self):
        assert len(LeaseStatus) == 4

    @pytest.mark.parametrize("member,value", [
        (LeaseStatus.HELD, "held"),
        (LeaseStatus.RELEASED, "released"),
        (LeaseStatus.EXPIRED, "expired"),
        (LeaseStatus.REVOKED, "revoked"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    def test_unique_values(self):
        vals = [m.value for m in LeaseStatus]
        assert len(vals) == len(set(vals))


class TestShardStatusEnum:
    def test_member_count(self):
        assert len(ShardStatus) == 4

    @pytest.mark.parametrize("member,value", [
        (ShardStatus.ASSIGNED, "assigned"),
        (ShardStatus.MIGRATING, "migrating"),
        (ShardStatus.ORPHANED, "orphaned"),
        (ShardStatus.DECOMMISSIONED, "decommissioned"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    def test_unique_values(self):
        vals = [m.value for m in ShardStatus]
        assert len(vals) == len(set(vals))


class TestCheckpointDispositionEnum:
    def test_member_count(self):
        assert len(CheckpointDisposition) == 4

    @pytest.mark.parametrize("member,value", [
        (CheckpointDisposition.PENDING, "pending"),
        (CheckpointDisposition.COMMITTED, "committed"),
        (CheckpointDisposition.FAILED, "failed"),
        (CheckpointDisposition.ROLLED_BACK, "rolled_back"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    def test_unique_values(self):
        vals = [m.value for m in CheckpointDisposition]
        assert len(vals) == len(set(vals))


class TestBackpressureLevelEnum:
    def test_member_count(self):
        assert len(BackpressureLevel) == 5

    @pytest.mark.parametrize("member,value", [
        (BackpressureLevel.NONE, "none"),
        (BackpressureLevel.LOW, "low"),
        (BackpressureLevel.MEDIUM, "medium"),
        (BackpressureLevel.HIGH, "high"),
        (BackpressureLevel.CRITICAL, "critical"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    def test_unique_values(self):
        vals = [m.value for m in BackpressureLevel]
        assert len(vals) == len(set(vals))


# ===================================================================
# 2. WorkerRecord
# ===================================================================


class TestWorkerRecordValid:
    def test_basic_construction(self):
        w = _worker()
        assert w.worker_id == "w1"
        assert w.tenant_id == "t1"
        assert w.display_name == "Worker-A"
        assert w.status == WorkerStatus.IDLE
        assert w.queue_ref == "q1"
        assert w.capacity == 10
        assert w.active_leases == 0

    def test_metadata_frozen_to_mapping_proxy(self):
        w = _worker()
        assert isinstance(w.metadata, MappingProxyType)
        assert w.metadata["k"] == "v"

    def test_to_dict_metadata_plain_dict(self):
        w = _worker()
        d = w.to_dict()
        assert isinstance(d["metadata"], dict)
        assert d["metadata"]["k"] == "v"

    def test_to_dict_preserves_enum_objects(self):
        w = _worker()
        d = w.to_dict()
        assert d["status"] is WorkerStatus.IDLE

    def test_to_json_dict_converts_enums(self):
        w = _worker()
        d = w.to_json_dict()
        assert d["status"] == "idle"

    def test_to_json_serializable(self):
        w = _worker()
        j = w.to_json()
        parsed = json.loads(j)
        assert parsed["worker_id"] == "w1"

    def test_frozen_immutability(self):
        w = _worker()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(w, "worker_id", "x")

    def test_frozen_status(self):
        w = _worker()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(w, "status", WorkerStatus.ACTIVE)

    def test_frozen_capacity(self):
        w = _worker()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(w, "capacity", 99)

    def test_date_only_accepted(self):
        w = _worker(registered_at=DATE_ONLY)
        assert w.registered_at == DATE_ONLY

    def test_all_statuses_accepted(self):
        for s in WorkerStatus:
            w = _worker(status=s)
            assert w.status == s

    def test_capacity_zero(self):
        w = _worker(capacity=0)
        assert w.capacity == 0

    def test_active_leases_zero(self):
        w = _worker(active_leases=0)
        assert w.active_leases == 0

    def test_large_capacity(self):
        w = _worker(capacity=1_000_000)
        assert w.capacity == 1_000_000

    def test_empty_metadata(self):
        w = _worker(metadata={})
        assert isinstance(w.metadata, MappingProxyType)
        assert len(w.metadata) == 0

    def test_nested_metadata(self):
        w = _worker(metadata={"a": {"b": 1}})
        assert isinstance(w.metadata["a"], MappingProxyType)


class TestWorkerRecordInvalid:
    def test_empty_worker_id(self):
        with pytest.raises(ValueError):
            _worker(worker_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _worker(tenant_id="")

    def test_empty_display_name(self):
        with pytest.raises(ValueError):
            _worker(display_name="")

    def test_empty_queue_ref(self):
        with pytest.raises(ValueError):
            _worker(queue_ref="")

    def test_whitespace_worker_id(self):
        with pytest.raises(ValueError):
            _worker(worker_id="   ")

    def test_invalid_status_string(self):
        with pytest.raises(ValueError):
            _worker(status="idle")

    def test_invalid_status_none(self):
        with pytest.raises(ValueError):
            _worker(status=None)

    def test_negative_capacity(self):
        with pytest.raises(ValueError):
            _worker(capacity=-1)

    def test_bool_capacity(self):
        with pytest.raises(ValueError):
            _worker(capacity=True)

    def test_float_capacity(self):
        with pytest.raises(ValueError):
            _worker(capacity=1.5)

    def test_negative_active_leases(self):
        with pytest.raises(ValueError):
            _worker(active_leases=-1)

    def test_bool_active_leases(self):
        with pytest.raises(ValueError):
            _worker(active_leases=False)

    def test_float_active_leases(self):
        with pytest.raises(ValueError):
            _worker(active_leases=2.0)

    def test_invalid_registered_at(self):
        with pytest.raises(ValueError):
            _worker(registered_at="not-a-date")

    def test_empty_registered_at(self):
        with pytest.raises(ValueError):
            _worker(registered_at="")


# ===================================================================
# 3. QueueRecord
# ===================================================================


class TestQueueRecordValid:
    def test_basic_construction(self):
        q = _queue()
        assert q.queue_id == "q1"
        assert q.tenant_id == "t1"
        assert q.display_name == "Queue-A"
        assert q.status == QueueStatus.ACTIVE
        assert q.depth == 5
        assert q.max_depth == 100
        assert q.backpressure == BackpressureLevel.NONE

    def test_metadata_frozen(self):
        q = _queue()
        assert isinstance(q.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        q = _queue()
        d = q.to_dict()
        assert d["status"] is QueueStatus.ACTIVE
        assert d["backpressure"] is BackpressureLevel.NONE

    def test_to_dict_metadata_plain_dict(self):
        q = _queue()
        d = q.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_frozen(self):
        q = _queue()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(q, "depth", 99)

    def test_date_only_accepted(self):
        q = _queue(created_at=DATE_ONLY)
        assert q.created_at == DATE_ONLY

    def test_all_statuses(self):
        for s in QueueStatus:
            q = _queue(status=s)
            assert q.status == s

    def test_all_backpressure_levels(self):
        for bp in BackpressureLevel:
            q = _queue(backpressure=bp)
            assert q.backpressure == bp

    def test_depth_zero(self):
        q = _queue(depth=0)
        assert q.depth == 0

    def test_max_depth_zero(self):
        q = _queue(max_depth=0)
        assert q.max_depth == 0

    def test_to_json_serializable(self):
        q = _queue()
        parsed = json.loads(q.to_json())
        assert parsed["queue_id"] == "q1"

    def test_to_json_dict_enums_as_strings(self):
        q = _queue()
        d = q.to_json_dict()
        assert d["status"] == "active"
        assert d["backpressure"] == "none"


class TestQueueRecordInvalid:
    def test_empty_queue_id(self):
        with pytest.raises(ValueError):
            _queue(queue_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _queue(tenant_id="")

    def test_empty_display_name(self):
        with pytest.raises(ValueError):
            _queue(display_name="")

    def test_invalid_status(self):
        with pytest.raises(ValueError):
            _queue(status="active")

    def test_negative_depth(self):
        with pytest.raises(ValueError):
            _queue(depth=-1)

    def test_bool_depth(self):
        with pytest.raises(ValueError):
            _queue(depth=True)

    def test_float_depth(self):
        with pytest.raises(ValueError):
            _queue(depth=1.5)

    def test_negative_max_depth(self):
        with pytest.raises(ValueError):
            _queue(max_depth=-1)

    def test_bool_max_depth(self):
        with pytest.raises(ValueError):
            _queue(max_depth=False)

    def test_float_max_depth(self):
        with pytest.raises(ValueError):
            _queue(max_depth=2.0)

    def test_invalid_backpressure(self):
        with pytest.raises(ValueError):
            _queue(backpressure="none")

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            _queue(created_at="xyz")

    def test_empty_created_at(self):
        with pytest.raises(ValueError):
            _queue(created_at="")


# ===================================================================
# 4. LeaseRecord
# ===================================================================


class TestLeaseRecordValid:
    def test_basic_construction(self):
        le = _lease()
        assert le.lease_id == "l1"
        assert le.tenant_id == "t1"
        assert le.worker_id == "w1"
        assert le.task_ref == "task-1"
        assert le.status == LeaseStatus.HELD
        assert le.ttl_ms == 30000

    def test_metadata_frozen(self):
        le = _lease(metadata={"x": 1})
        assert isinstance(le.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        le = _lease()
        d = le.to_dict()
        assert d["status"] is LeaseStatus.HELD

    def test_to_dict_metadata_plain(self):
        le = _lease(metadata={"x": 1})
        d = le.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_frozen(self):
        le = _lease()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(le, "lease_id", "x")

    def test_all_statuses(self):
        for s in LeaseStatus:
            le = _lease(status=s)
            assert le.status == s

    def test_date_only_accepted(self):
        le = _lease(acquired_at=DATE_ONLY)
        assert le.acquired_at == DATE_ONLY

    def test_ttl_zero(self):
        le = _lease(ttl_ms=0)
        assert le.ttl_ms == 0

    def test_large_ttl(self):
        le = _lease(ttl_ms=999999)
        assert le.ttl_ms == 999999

    def test_to_json_serializable(self):
        le = _lease()
        parsed = json.loads(le.to_json())
        assert parsed["lease_id"] == "l1"


class TestLeaseRecordInvalid:
    def test_empty_lease_id(self):
        with pytest.raises(ValueError):
            _lease(lease_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _lease(tenant_id="")

    def test_empty_worker_id(self):
        with pytest.raises(ValueError):
            _lease(worker_id="")

    def test_empty_task_ref(self):
        with pytest.raises(ValueError):
            _lease(task_ref="")

    def test_invalid_status(self):
        with pytest.raises(ValueError):
            _lease(status="held")

    def test_negative_ttl(self):
        with pytest.raises(ValueError):
            _lease(ttl_ms=-1)

    def test_bool_ttl(self):
        with pytest.raises(ValueError):
            _lease(ttl_ms=True)

    def test_float_ttl(self):
        with pytest.raises(ValueError):
            _lease(ttl_ms=1.5)

    def test_invalid_acquired_at(self):
        with pytest.raises(ValueError):
            _lease(acquired_at="nope")

    def test_whitespace_lease_id(self):
        with pytest.raises(ValueError):
            _lease(lease_id="   ")


# ===================================================================
# 5. ShardRecord
# ===================================================================


class TestShardRecordValid:
    def test_basic_construction(self):
        s = _shard()
        assert s.shard_id == "s1"
        assert s.tenant_id == "t1"
        assert s.partition_key == "pk1"
        assert s.status == ShardStatus.ASSIGNED
        assert s.record_count == 100
        assert s.assigned_worker == "w1"

    def test_metadata_frozen(self):
        s = _shard(metadata={"x": 1})
        assert isinstance(s.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        s = _shard()
        d = s.to_dict()
        assert d["status"] is ShardStatus.ASSIGNED

    def test_frozen(self):
        s = _shard()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, "shard_id", "x")

    def test_all_statuses(self):
        for st in ShardStatus:
            s = _shard(status=st)
            assert s.status == st

    def test_date_only_accepted(self):
        s = _shard(created_at=DATE_ONLY)
        assert s.created_at == DATE_ONLY

    def test_record_count_zero(self):
        s = _shard(record_count=0)
        assert s.record_count == 0

    def test_to_json_serializable(self):
        s = _shard()
        parsed = json.loads(s.to_json())
        assert parsed["shard_id"] == "s1"

    def test_nested_metadata(self):
        s = _shard(metadata={"a": {"b": 2}})
        assert isinstance(s.metadata["a"], MappingProxyType)


class TestShardRecordInvalid:
    def test_empty_shard_id(self):
        with pytest.raises(ValueError):
            _shard(shard_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _shard(tenant_id="")

    def test_empty_partition_key(self):
        with pytest.raises(ValueError):
            _shard(partition_key="")

    def test_empty_assigned_worker(self):
        with pytest.raises(ValueError):
            _shard(assigned_worker="")

    def test_invalid_status(self):
        with pytest.raises(ValueError):
            _shard(status="assigned")

    def test_negative_record_count(self):
        with pytest.raises(ValueError):
            _shard(record_count=-1)

    def test_bool_record_count(self):
        with pytest.raises(ValueError):
            _shard(record_count=True)

    def test_float_record_count(self):
        with pytest.raises(ValueError):
            _shard(record_count=1.0)

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            _shard(created_at="bad")


# ===================================================================
# 6. DistributedCheckpoint
# ===================================================================


class TestCheckpointValid:
    def test_basic_construction(self):
        cp = _checkpoint()
        assert cp.checkpoint_id == "cp1"
        assert cp.tenant_id == "t1"
        assert cp.disposition == CheckpointDisposition.PENDING
        assert cp.shard_count == 3
        assert cp.worker_count == 2

    def test_metadata_frozen(self):
        cp = _checkpoint(metadata={"a": 1})
        assert isinstance(cp.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        cp = _checkpoint()
        d = cp.to_dict()
        assert d["disposition"] is CheckpointDisposition.PENDING

    def test_frozen(self):
        cp = _checkpoint()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(cp, "checkpoint_id", "x")

    def test_all_dispositions(self):
        for disp in CheckpointDisposition:
            cp = _checkpoint(disposition=disp)
            assert cp.disposition == disp

    def test_date_only_accepted(self):
        cp = _checkpoint(created_at=DATE_ONLY)
        assert cp.created_at == DATE_ONLY

    def test_shard_count_zero(self):
        cp = _checkpoint(shard_count=0)
        assert cp.shard_count == 0

    def test_worker_count_zero(self):
        cp = _checkpoint(worker_count=0)
        assert cp.worker_count == 0

    def test_to_json_serializable(self):
        cp = _checkpoint()
        parsed = json.loads(cp.to_json())
        assert parsed["checkpoint_id"] == "cp1"

    def test_to_json_dict_converts_enums(self):
        cp = _checkpoint()
        d = cp.to_json_dict()
        assert d["disposition"] == "pending"


class TestCheckpointInvalid:
    def test_empty_checkpoint_id(self):
        with pytest.raises(ValueError):
            _checkpoint(checkpoint_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _checkpoint(tenant_id="")

    def test_invalid_disposition(self):
        with pytest.raises(ValueError):
            _checkpoint(disposition="pending")

    def test_negative_shard_count(self):
        with pytest.raises(ValueError):
            _checkpoint(shard_count=-1)

    def test_bool_shard_count(self):
        with pytest.raises(ValueError):
            _checkpoint(shard_count=True)

    def test_float_shard_count(self):
        with pytest.raises(ValueError):
            _checkpoint(shard_count=1.5)

    def test_negative_worker_count(self):
        with pytest.raises(ValueError):
            _checkpoint(worker_count=-1)

    def test_bool_worker_count(self):
        with pytest.raises(ValueError):
            _checkpoint(worker_count=False)

    def test_float_worker_count(self):
        with pytest.raises(ValueError):
            _checkpoint(worker_count=2.0)

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            _checkpoint(created_at="nah")


# ===================================================================
# 7. RetrySchedule
# ===================================================================


class TestRetryScheduleValid:
    def test_basic_construction(self):
        rs = _retry()
        assert rs.schedule_id == "rs1"
        assert rs.tenant_id == "t1"
        assert rs.task_ref == "task-1"
        assert rs.max_retries == 3
        assert rs.retry_count == 0
        assert rs.backoff_ms == 1000

    def test_metadata_frozen(self):
        rs = _retry(metadata={"x": 1})
        assert isinstance(rs.metadata, MappingProxyType)

    def test_to_dict_metadata_plain(self):
        rs = _retry(metadata={"x": 1})
        d = rs.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_frozen(self):
        rs = _retry()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(rs, "schedule_id", "x")

    def test_date_only_accepted(self):
        rs = _retry(created_at=DATE_ONLY)
        assert rs.created_at == DATE_ONLY

    def test_max_retries_zero(self):
        rs = _retry(max_retries=0)
        assert rs.max_retries == 0

    def test_retry_count_zero(self):
        rs = _retry(retry_count=0)
        assert rs.retry_count == 0

    def test_backoff_zero(self):
        rs = _retry(backoff_ms=0)
        assert rs.backoff_ms == 0

    def test_large_max_retries(self):
        rs = _retry(max_retries=100)
        assert rs.max_retries == 100

    def test_to_json_serializable(self):
        rs = _retry()
        parsed = json.loads(rs.to_json())
        assert parsed["schedule_id"] == "rs1"


class TestRetryScheduleInvalid:
    def test_empty_schedule_id(self):
        with pytest.raises(ValueError):
            _retry(schedule_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _retry(tenant_id="")

    def test_empty_task_ref(self):
        with pytest.raises(ValueError):
            _retry(task_ref="")

    def test_negative_max_retries(self):
        with pytest.raises(ValueError):
            _retry(max_retries=-1)

    def test_bool_max_retries(self):
        with pytest.raises(ValueError):
            _retry(max_retries=True)

    def test_float_max_retries(self):
        with pytest.raises(ValueError):
            _retry(max_retries=1.0)

    def test_negative_retry_count(self):
        with pytest.raises(ValueError):
            _retry(retry_count=-1)

    def test_bool_retry_count(self):
        with pytest.raises(ValueError):
            _retry(retry_count=False)

    def test_float_retry_count(self):
        with pytest.raises(ValueError):
            _retry(retry_count=2.0)

    def test_negative_backoff(self):
        with pytest.raises(ValueError):
            _retry(backoff_ms=-1)

    def test_bool_backoff(self):
        with pytest.raises(ValueError):
            _retry(backoff_ms=True)

    def test_float_backoff(self):
        with pytest.raises(ValueError):
            _retry(backoff_ms=1.5)

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            _retry(created_at="xx")


# ===================================================================
# 8. ConcurrencyLock
# ===================================================================


class TestConcurrencyLockValid:
    def test_basic_construction(self):
        lk = _lock()
        assert lk.lock_id == "lk1"
        assert lk.tenant_id == "t1"
        assert lk.resource_ref == "res1"
        assert lk.holder_ref == "w1"

    def test_metadata_frozen(self):
        lk = _lock(metadata={"a": 1})
        assert isinstance(lk.metadata, MappingProxyType)

    def test_to_dict_metadata_plain(self):
        lk = _lock(metadata={"a": 1})
        d = lk.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_frozen(self):
        lk = _lock()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(lk, "lock_id", "x")

    def test_date_only_accepted(self):
        lk = _lock(acquired_at=DATE_ONLY)
        assert lk.acquired_at == DATE_ONLY

    def test_to_json_serializable(self):
        lk = _lock()
        parsed = json.loads(lk.to_json())
        assert parsed["lock_id"] == "lk1"


class TestConcurrencyLockInvalid:
    def test_empty_lock_id(self):
        with pytest.raises(ValueError):
            _lock(lock_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _lock(tenant_id="")

    def test_empty_resource_ref(self):
        with pytest.raises(ValueError):
            _lock(resource_ref="")

    def test_empty_holder_ref(self):
        with pytest.raises(ValueError):
            _lock(holder_ref="")

    def test_invalid_acquired_at(self):
        with pytest.raises(ValueError):
            _lock(acquired_at="nope")

    def test_whitespace_lock_id(self):
        with pytest.raises(ValueError):
            _lock(lock_id="   ")


# ===================================================================
# 9. DistributedSnapshot
# ===================================================================


class TestSnapshotValid:
    def test_basic_construction(self):
        sn = _snapshot()
        assert sn.snapshot_id == "snap1"
        assert sn.tenant_id == "t1"
        assert sn.total_workers == 5
        assert sn.total_queues == 2
        assert sn.total_leases == 3
        assert sn.total_shards == 4
        assert sn.total_checkpoints == 1
        assert sn.total_violations == 0

    def test_metadata_frozen(self):
        sn = _snapshot(metadata={"a": 1})
        assert isinstance(sn.metadata, MappingProxyType)

    def test_to_dict_metadata_plain(self):
        sn = _snapshot(metadata={"a": 1})
        d = sn.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_frozen(self):
        sn = _snapshot()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(sn, "snapshot_id", "x")

    def test_date_only_accepted(self):
        sn = _snapshot(captured_at=DATE_ONLY)
        assert sn.captured_at == DATE_ONLY

    def test_all_zeros(self):
        sn = _snapshot(
            total_workers=0, total_queues=0, total_leases=0,
            total_shards=0, total_checkpoints=0, total_violations=0,
        )
        assert sn.total_workers == 0

    def test_to_json_serializable(self):
        sn = _snapshot()
        parsed = json.loads(sn.to_json())
        assert parsed["snapshot_id"] == "snap1"


class TestSnapshotInvalid:
    def test_empty_snapshot_id(self):
        with pytest.raises(ValueError):
            _snapshot(snapshot_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _snapshot(tenant_id="")

    @pytest.mark.parametrize("field", [
        "total_workers", "total_queues", "total_leases",
        "total_shards", "total_checkpoints", "total_violations",
    ])
    def test_negative_int_field(self, field):
        with pytest.raises(ValueError):
            _snapshot(**{field: -1})

    @pytest.mark.parametrize("field", [
        "total_workers", "total_queues", "total_leases",
        "total_shards", "total_checkpoints", "total_violations",
    ])
    def test_bool_int_field(self, field):
        with pytest.raises(ValueError):
            _snapshot(**{field: True})

    @pytest.mark.parametrize("field", [
        "total_workers", "total_queues", "total_leases",
        "total_shards", "total_checkpoints", "total_violations",
    ])
    def test_float_int_field(self, field):
        with pytest.raises(ValueError):
            _snapshot(**{field: 1.0})

    def test_invalid_captured_at(self):
        with pytest.raises(ValueError):
            _snapshot(captured_at="bad-date")


# ===================================================================
# 10. DistributedViolation
# ===================================================================


class TestViolationValid:
    def test_basic_construction(self):
        v = _violation()
        assert v.violation_id == "v1"
        assert v.tenant_id == "t1"
        assert v.operation == "orphaned_shard"
        assert v.reason == "shard is orphaned"

    def test_metadata_frozen(self):
        v = _violation(metadata={"a": 1})
        assert isinstance(v.metadata, MappingProxyType)

    def test_to_dict_metadata_plain(self):
        v = _violation(metadata={"a": 1})
        d = v.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_frozen(self):
        v = _violation()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(v, "violation_id", "x")

    def test_date_only_accepted(self):
        v = _violation(detected_at=DATE_ONLY)
        assert v.detected_at == DATE_ONLY

    def test_to_json_serializable(self):
        v = _violation()
        parsed = json.loads(v.to_json())
        assert parsed["violation_id"] == "v1"


class TestViolationInvalid:
    def test_empty_violation_id(self):
        with pytest.raises(ValueError):
            _violation(violation_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _violation(tenant_id="")

    def test_empty_operation(self):
        with pytest.raises(ValueError):
            _violation(operation="")

    def test_empty_reason(self):
        with pytest.raises(ValueError):
            _violation(reason="")

    def test_invalid_detected_at(self):
        with pytest.raises(ValueError):
            _violation(detected_at="nope")

    def test_whitespace_operation(self):
        with pytest.raises(ValueError):
            _violation(operation="   ")


# ===================================================================
# 11. DistributedClosureReport
# ===================================================================


class TestClosureReportValid:
    def test_basic_construction(self):
        cr = _closure()
        assert cr.report_id == "cr1"
        assert cr.tenant_id == "t1"
        assert cr.total_workers == 10
        assert cr.total_queues == 3
        assert cr.total_leases == 5
        assert cr.total_checkpoints == 2
        assert cr.total_violations == 1

    def test_metadata_frozen(self):
        cr = _closure(metadata={"x": 1})
        assert isinstance(cr.metadata, MappingProxyType)

    def test_to_dict_metadata_plain(self):
        cr = _closure(metadata={"x": 1})
        d = cr.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_frozen(self):
        cr = _closure()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(cr, "report_id", "x")

    def test_date_only_accepted(self):
        cr = _closure(created_at=DATE_ONLY)
        assert cr.created_at == DATE_ONLY

    def test_all_zeros(self):
        cr = _closure(
            total_workers=0, total_queues=0, total_leases=0,
            total_checkpoints=0, total_violations=0,
        )
        assert cr.total_workers == 0

    def test_to_json_serializable(self):
        cr = _closure()
        parsed = json.loads(cr.to_json())
        assert parsed["report_id"] == "cr1"

    def test_to_json_dict(self):
        cr = _closure()
        d = cr.to_json_dict()
        assert isinstance(d["total_workers"], int)


class TestClosureReportInvalid:
    def test_empty_report_id(self):
        with pytest.raises(ValueError):
            _closure(report_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _closure(tenant_id="")

    @pytest.mark.parametrize("field", [
        "total_workers", "total_queues", "total_leases",
        "total_checkpoints", "total_violations",
    ])
    def test_negative_int_field(self, field):
        with pytest.raises(ValueError):
            _closure(**{field: -1})

    @pytest.mark.parametrize("field", [
        "total_workers", "total_queues", "total_leases",
        "total_checkpoints", "total_violations",
    ])
    def test_bool_int_field(self, field):
        with pytest.raises(ValueError):
            _closure(**{field: True})

    @pytest.mark.parametrize("field", [
        "total_workers", "total_queues", "total_leases",
        "total_checkpoints", "total_violations",
    ])
    def test_float_int_field(self, field):
        with pytest.raises(ValueError):
            _closure(**{field: 1.0})

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            _closure(created_at="nope")
