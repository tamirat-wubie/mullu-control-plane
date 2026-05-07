"""Comprehensive tests for DistributedRuntimeEngine.

Covers: constructor validation, worker lifecycle (register/drain/terminate/query),
queue lifecycle (create/pause/resume/close/query), lease lifecycle (acquire/release/
expire/revoke), shard lifecycle (register/migrate/complete/decommission), checkpoint
lifecycle (create/commit/fail/rollback), retry schedules (create/increment/exhaust),
concurrency locks (acquire/release/duplicate-resource), backpressure computation,
distributed snapshot, violation detection (idempotent), state hashing, replay
determinism, and six golden scenarios.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.distributed_runtime import DistributedRuntimeEngine
from mcoi_runtime.contracts.distributed_runtime import (
    BackpressureLevel,
    CheckpointDisposition,
    LeaseStatus,
    QueueStatus,
    ShardStatus,
    WorkerStatus,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# =====================================================================
# Fixtures
# =====================================================================


@pytest.fixture
def spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture
def engine(spine: EventSpineEngine) -> DistributedRuntimeEngine:
    return DistributedRuntimeEngine(spine)


# =====================================================================
# 1. Constructor validation
# =====================================================================


class TestConstructor:
    def test_valid_event_spine(self, spine):
        eng = DistributedRuntimeEngine(spine)
        assert eng.worker_count == 0

    def test_none_raises(self):
        with pytest.raises(RuntimeCoreInvariantError):
            DistributedRuntimeEngine(None)

    def test_string_raises(self):
        with pytest.raises(RuntimeCoreInvariantError):
            DistributedRuntimeEngine("not-a-spine")

    def test_dict_raises(self):
        with pytest.raises(RuntimeCoreInvariantError):
            DistributedRuntimeEngine({})

    def test_integer_raises(self):
        with pytest.raises(RuntimeCoreInvariantError):
            DistributedRuntimeEngine(42)

    def test_initial_counts_zero(self, engine):
        assert engine.worker_count == 0
        assert engine.queue_count == 0
        assert engine.lease_count == 0
        assert engine.shard_count == 0
        assert engine.checkpoint_count == 0
        assert engine.lock_count == 0
        assert engine.retry_count == 0
        assert engine.violation_count == 0


# =====================================================================
# 2. Worker registration
# =====================================================================


class TestRegisterWorker:
    def test_basic_registration(self, engine):
        w = engine.register_worker("w1", "t1", "Worker-A")
        assert w.worker_id == "w1"
        assert w.tenant_id == "t1"
        assert w.display_name == "Worker-A"
        assert w.status == WorkerStatus.IDLE
        assert w.capacity == 10
        assert w.active_leases == 0

    def test_registration_increments_count(self, engine):
        engine.register_worker("w1", "t1", "W1")
        engine.register_worker("w2", "t1", "W2")
        assert engine.worker_count == 2

    def test_duplicate_raises(self, engine):
        engine.register_worker("w1", "t1", "W1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate") as exc_info:
            engine.register_worker("w1", "t1", "W1")
        assert str(exc_info.value) == "duplicate worker_id"
        assert "w1" not in str(exc_info.value)

    def test_custom_capacity(self, engine):
        w = engine.register_worker("w1", "t1", "W", capacity=50)
        assert w.capacity == 50

    def test_custom_queue_ref(self, engine):
        w = engine.register_worker("w1", "t1", "W", queue_ref="q-special")
        assert w.queue_ref == "q-special"

    def test_default_queue_ref(self, engine):
        w = engine.register_worker("w1", "t1", "W")
        assert w.queue_ref == "default"

    def test_emits_event(self, engine, spine):
        engine.register_worker("w1", "t1", "W")
        assert spine.event_count >= 1

    def test_get_after_register(self, engine):
        engine.register_worker("w1", "t1", "W")
        w = engine.get_worker("w1")
        assert w.worker_id == "w1"

    def test_multiple_tenants(self, engine):
        engine.register_worker("w1", "t1", "W1")
        engine.register_worker("w2", "t2", "W2")
        assert engine.worker_count == 2


# =====================================================================
# 3. Worker lifecycle (drain, terminate)
# =====================================================================


class TestWorkerDrain:
    def test_drain_idle_worker(self, engine):
        engine.register_worker("w1", "t1", "W")
        w = engine.drain_worker("w1")
        assert w.status == WorkerStatus.DRAINING

    def test_drain_active_worker(self, engine):
        engine.register_worker("w1", "t1", "W")
        w = engine.drain_worker("w1")
        assert w.status == WorkerStatus.DRAINING

    def test_drain_terminated_raises(self, engine):
        engine.register_worker("w1", "t1", "W")
        engine.terminate_worker("w1")
        with pytest.raises(RuntimeCoreInvariantError, match="TERMINATED") as exc_info:
            engine.drain_worker("w1")
        assert str(exc_info.value) == "worker is TERMINATED"
        assert "w1" not in str(exc_info.value)

    def test_drain_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown") as exc_info:
            engine.drain_worker("no-such")
        assert str(exc_info.value) == "unknown worker_id"
        assert "no-such" not in str(exc_info.value)

    def test_drain_emits_event(self, engine, spine):
        engine.register_worker("w1", "t1", "W")
        before = spine.event_count
        engine.drain_worker("w1")
        assert spine.event_count > before

    def test_drain_preserves_capacity(self, engine):
        engine.register_worker("w1", "t1", "W", capacity=25)
        w = engine.drain_worker("w1")
        assert w.capacity == 25


class TestWorkerTerminate:
    def test_terminate_idle(self, engine):
        engine.register_worker("w1", "t1", "W")
        w = engine.terminate_worker("w1")
        assert w.status == WorkerStatus.TERMINATED

    def test_terminate_draining(self, engine):
        engine.register_worker("w1", "t1", "W")
        engine.drain_worker("w1")
        w = engine.terminate_worker("w1")
        assert w.status == WorkerStatus.TERMINATED

    def test_terminate_already_terminated_raises(self, engine):
        engine.register_worker("w1", "t1", "W")
        engine.terminate_worker("w1")
        with pytest.raises(RuntimeCoreInvariantError, match="already TERMINATED"):
            engine.terminate_worker("w1")

    def test_terminate_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown"):
            engine.terminate_worker("no-such")

    def test_terminate_emits_event(self, engine, spine):
        engine.register_worker("w1", "t1", "W")
        before = spine.event_count
        engine.terminate_worker("w1")
        assert spine.event_count > before

    def test_terminate_preserves_tenant(self, engine):
        engine.register_worker("w1", "t1", "W")
        w = engine.terminate_worker("w1")
        assert w.tenant_id == "t1"


class TestWorkersForTenant:
    def test_empty(self, engine):
        assert engine.workers_for_tenant("t1") == ()

    def test_returns_correct_tenant(self, engine):
        engine.register_worker("w1", "t1", "W1")
        engine.register_worker("w2", "t2", "W2")
        result = engine.workers_for_tenant("t1")
        assert len(result) == 1
        assert result[0].worker_id == "w1"

    def test_multiple_workers_same_tenant(self, engine):
        engine.register_worker("w1", "t1", "W1")
        engine.register_worker("w2", "t1", "W2")
        result = engine.workers_for_tenant("t1")
        assert len(result) == 2

    def test_returns_tuple(self, engine):
        result = engine.workers_for_tenant("t1")
        assert isinstance(result, tuple)


# =====================================================================
# 4. Queue lifecycle
# =====================================================================


class TestCreateQueue:
    def test_basic_creation(self, engine):
        q = engine.create_queue("q1", "t1", "Queue-A")
        assert q.queue_id == "q1"
        assert q.tenant_id == "t1"
        assert q.display_name == "Queue-A"
        assert q.status == QueueStatus.ACTIVE
        assert q.depth == 0
        assert q.max_depth == 1000
        assert q.backpressure == BackpressureLevel.NONE

    def test_duplicate_raises(self, engine):
        engine.create_queue("q1", "t1", "Q")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            engine.create_queue("q1", "t1", "Q")

    def test_custom_max_depth(self, engine):
        q = engine.create_queue("q1", "t1", "Q", max_depth=500)
        assert q.max_depth == 500

    def test_increments_count(self, engine):
        engine.create_queue("q1", "t1", "Q1")
        engine.create_queue("q2", "t1", "Q2")
        assert engine.queue_count == 2

    def test_emits_event(self, engine, spine):
        engine.create_queue("q1", "t1", "Q")
        assert spine.event_count >= 1

    def test_get_after_create(self, engine):
        engine.create_queue("q1", "t1", "Q")
        q = engine.get_queue("q1")
        assert q.queue_id == "q1"


class TestPauseQueue:
    def test_pause_active(self, engine):
        engine.create_queue("q1", "t1", "Q")
        q = engine.pause_queue("q1")
        assert q.status == QueueStatus.PAUSED

    def test_pause_closed_raises(self, engine):
        engine.create_queue("q1", "t1", "Q")
        engine.close_queue("q1")
        with pytest.raises(RuntimeCoreInvariantError, match="CLOSED"):
            engine.pause_queue("q1")

    def test_pause_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown"):
            engine.pause_queue("no-such")

    def test_pause_emits_event(self, engine, spine):
        engine.create_queue("q1", "t1", "Q")
        before = spine.event_count
        engine.pause_queue("q1")
        assert spine.event_count > before


class TestResumeQueue:
    def test_resume_paused(self, engine):
        engine.create_queue("q1", "t1", "Q")
        engine.pause_queue("q1")
        q = engine.resume_queue("q1")
        assert q.status == QueueStatus.ACTIVE

    def test_resume_closed_raises(self, engine):
        engine.create_queue("q1", "t1", "Q")
        engine.close_queue("q1")
        with pytest.raises(RuntimeCoreInvariantError, match="CLOSED"):
            engine.resume_queue("q1")

    def test_resume_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.resume_queue("no-such")


class TestCloseQueue:
    def test_close_active(self, engine):
        engine.create_queue("q1", "t1", "Q")
        q = engine.close_queue("q1")
        assert q.status == QueueStatus.CLOSED

    def test_close_paused(self, engine):
        engine.create_queue("q1", "t1", "Q")
        engine.pause_queue("q1")
        q = engine.close_queue("q1")
        assert q.status == QueueStatus.CLOSED

    def test_close_already_closed_raises(self, engine):
        engine.create_queue("q1", "t1", "Q")
        engine.close_queue("q1")
        with pytest.raises(RuntimeCoreInvariantError, match="already CLOSED") as exc_info:
            engine.close_queue("q1")
        assert str(exc_info.value) == "queue is already CLOSED"
        assert "q1" not in str(exc_info.value)

    def test_close_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.close_queue("no-such")

    def test_close_emits_event(self, engine, spine):
        engine.create_queue("q1", "t1", "Q")
        before = spine.event_count
        engine.close_queue("q1")
        assert spine.event_count > before


class TestQueuesForTenant:
    def test_empty(self, engine):
        assert engine.queues_for_tenant("t1") == ()

    def test_correct_tenant(self, engine):
        engine.create_queue("q1", "t1", "Q1")
        engine.create_queue("q2", "t2", "Q2")
        result = engine.queues_for_tenant("t1")
        assert len(result) == 1
        assert result[0].queue_id == "q1"

    def test_returns_tuple(self, engine):
        assert isinstance(engine.queues_for_tenant("t1"), tuple)


# =====================================================================
# 5. Lease lifecycle
# =====================================================================


class TestAcquireLease:
    def test_basic_acquisition(self, engine):
        le = engine.acquire_lease("l1", "t1", "w1", "task-1")
        assert le.lease_id == "l1"
        assert le.tenant_id == "t1"
        assert le.worker_id == "w1"
        assert le.task_ref == "task-1"
        assert le.status == LeaseStatus.HELD
        assert le.ttl_ms == 30000

    def test_custom_ttl(self, engine):
        le = engine.acquire_lease("l1", "t1", "w1", "task-1", ttl_ms=60000)
        assert le.ttl_ms == 60000

    def test_duplicate_raises(self, engine):
        engine.acquire_lease("l1", "t1", "w1", "task-1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            engine.acquire_lease("l1", "t1", "w1", "task-1")

    def test_increments_count(self, engine):
        engine.acquire_lease("l1", "t1", "w1", "task-1")
        engine.acquire_lease("l2", "t1", "w1", "task-2")
        assert engine.lease_count == 2

    def test_emits_event(self, engine, spine):
        engine.acquire_lease("l1", "t1", "w1", "task-1")
        assert spine.event_count >= 1


class TestReleaseLease:
    def test_release_held(self, engine):
        engine.acquire_lease("l1", "t1", "w1", "task-1")
        le = engine.release_lease("l1")
        assert le.status == LeaseStatus.RELEASED

    def test_release_already_released_raises(self, engine):
        engine.acquire_lease("l1", "t1", "w1", "task-1")
        engine.release_lease("l1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal") as exc_info:
            engine.release_lease("l1")
        assert str(exc_info.value) == "lease is in terminal state"
        assert "l1" not in str(exc_info.value)
        assert LeaseStatus.RELEASED.value not in str(exc_info.value)

    def test_release_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown"):
            engine.release_lease("no-such")

    def test_release_emits_event(self, engine, spine):
        engine.acquire_lease("l1", "t1", "w1", "task-1")
        before = spine.event_count
        engine.release_lease("l1")
        assert spine.event_count > before


class TestExpireLease:
    def test_expire_held(self, engine):
        engine.acquire_lease("l1", "t1", "w1", "task-1")
        le = engine.expire_lease("l1")
        assert le.status == LeaseStatus.EXPIRED

    def test_expire_already_expired_raises(self, engine):
        engine.acquire_lease("l1", "t1", "w1", "task-1")
        engine.expire_lease("l1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.expire_lease("l1")

    def test_expire_released_raises(self, engine):
        engine.acquire_lease("l1", "t1", "w1", "task-1")
        engine.release_lease("l1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.expire_lease("l1")


class TestRevokeLease:
    def test_revoke_held(self, engine):
        engine.acquire_lease("l1", "t1", "w1", "task-1")
        le = engine.revoke_lease("l1")
        assert le.status == LeaseStatus.REVOKED

    def test_revoke_already_revoked_raises(self, engine):
        engine.acquire_lease("l1", "t1", "w1", "task-1")
        engine.revoke_lease("l1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.revoke_lease("l1")

    def test_revoke_expired_raises(self, engine):
        engine.acquire_lease("l1", "t1", "w1", "task-1")
        engine.expire_lease("l1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.revoke_lease("l1")

    def test_revoke_released_raises(self, engine):
        engine.acquire_lease("l1", "t1", "w1", "task-1")
        engine.release_lease("l1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.revoke_lease("l1")


class TestLeaseTerminalBlock:
    """All three terminal states block all transitions."""

    @pytest.mark.parametrize("terminal_fn", ["release_lease", "expire_lease", "revoke_lease"])
    @pytest.mark.parametrize("attempt_fn", ["release_lease", "expire_lease", "revoke_lease"])
    def test_terminal_blocks_all(self, engine, terminal_fn, attempt_fn):
        engine.acquire_lease("l1", "t1", "w1", "task-1")
        getattr(engine, terminal_fn)("l1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            getattr(engine, attempt_fn)("l1")


# =====================================================================
# 6. Shard lifecycle
# =====================================================================


class TestRegisterShard:
    def test_basic_registration(self, engine):
        s = engine.register_shard("s1", "t1", "pk1", "w1")
        assert s.shard_id == "s1"
        assert s.tenant_id == "t1"
        assert s.partition_key == "pk1"
        assert s.assigned_worker == "w1"
        assert s.status == ShardStatus.ASSIGNED
        assert s.record_count == 0

    def test_custom_record_count(self, engine):
        s = engine.register_shard("s1", "t1", "pk1", "w1", record_count=100)
        assert s.record_count == 100

    def test_duplicate_raises(self, engine):
        engine.register_shard("s1", "t1", "pk1", "w1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            engine.register_shard("s1", "t1", "pk1", "w1")

    def test_increments_count(self, engine):
        engine.register_shard("s1", "t1", "pk1", "w1")
        engine.register_shard("s2", "t1", "pk2", "w2")
        assert engine.shard_count == 2

    def test_emits_event(self, engine, spine):
        engine.register_shard("s1", "t1", "pk1", "w1")
        assert spine.event_count >= 1


class TestMigrateShard:
    def test_migrate_assigned(self, engine):
        engine.register_shard("s1", "t1", "pk1", "w1")
        s = engine.migrate_shard("s1")
        assert s.status == ShardStatus.MIGRATING

    def test_migrate_decommissioned_raises(self, engine):
        engine.register_shard("s1", "t1", "pk1", "w1")
        engine.decommission_shard("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.migrate_shard("s1")

    def test_migrate_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown") as exc_info:
            engine.migrate_shard("no-such")
        assert str(exc_info.value) == "unknown shard_id"
        assert "no-such" not in str(exc_info.value)


class TestCompleteMigration:
    def test_complete_migrating(self, engine):
        engine.register_shard("s1", "t1", "pk1", "w1")
        engine.migrate_shard("s1")
        s = engine.complete_migration("s1")
        assert s.status == ShardStatus.ASSIGNED

    def test_complete_decommissioned_raises(self, engine):
        engine.register_shard("s1", "t1", "pk1", "w1")
        engine.decommission_shard("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.complete_migration("s1")


class TestDecommissionShard:
    def test_decommission_assigned(self, engine):
        engine.register_shard("s1", "t1", "pk1", "w1")
        s = engine.decommission_shard("s1")
        assert s.status == ShardStatus.DECOMMISSIONED

    def test_decommission_migrating(self, engine):
        engine.register_shard("s1", "t1", "pk1", "w1")
        engine.migrate_shard("s1")
        s = engine.decommission_shard("s1")
        assert s.status == ShardStatus.DECOMMISSIONED

    def test_decommission_already_decommissioned_raises(self, engine):
        engine.register_shard("s1", "t1", "pk1", "w1")
        engine.decommission_shard("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.decommission_shard("s1")

    def test_decommission_emits_event(self, engine, spine):
        engine.register_shard("s1", "t1", "pk1", "w1")
        before = spine.event_count
        engine.decommission_shard("s1")
        assert spine.event_count > before


# =====================================================================
# 7. Checkpoint lifecycle
# =====================================================================


class TestCreateCheckpoint:
    def test_basic_creation(self, engine):
        cp = engine.create_checkpoint("cp1", "t1")
        assert cp.checkpoint_id == "cp1"
        assert cp.tenant_id == "t1"
        assert cp.disposition == CheckpointDisposition.PENDING
        assert cp.shard_count == 0
        assert cp.worker_count == 0

    def test_custom_counts(self, engine):
        cp = engine.create_checkpoint("cp1", "t1", shard_count=5, worker_count=3)
        assert cp.shard_count == 5
        assert cp.worker_count == 3

    def test_duplicate_raises(self, engine):
        engine.create_checkpoint("cp1", "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            engine.create_checkpoint("cp1", "t1")

    def test_increments_count(self, engine):
        engine.create_checkpoint("cp1", "t1")
        engine.create_checkpoint("cp2", "t1")
        assert engine.checkpoint_count == 2


class TestCommitCheckpoint:
    def test_commit_pending(self, engine):
        engine.create_checkpoint("cp1", "t1")
        cp = engine.commit_checkpoint("cp1")
        assert cp.disposition == CheckpointDisposition.COMMITTED

    def test_commit_already_committed_raises(self, engine):
        engine.create_checkpoint("cp1", "t1")
        engine.commit_checkpoint("cp1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.commit_checkpoint("cp1")

    def test_commit_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown"):
            engine.commit_checkpoint("no-such")


class TestFailCheckpoint:
    def test_fail_pending(self, engine):
        engine.create_checkpoint("cp1", "t1")
        cp = engine.fail_checkpoint("cp1")
        assert cp.disposition == CheckpointDisposition.FAILED

    def test_fail_already_failed_raises(self, engine):
        engine.create_checkpoint("cp1", "t1")
        engine.fail_checkpoint("cp1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.fail_checkpoint("cp1")

    def test_fail_committed_raises(self, engine):
        engine.create_checkpoint("cp1", "t1")
        engine.commit_checkpoint("cp1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.fail_checkpoint("cp1")


class TestRollbackCheckpoint:
    def test_rollback_pending(self, engine):
        engine.create_checkpoint("cp1", "t1")
        cp = engine.rollback_checkpoint("cp1")
        assert cp.disposition == CheckpointDisposition.ROLLED_BACK

    def test_rollback_already_rolled_back_raises(self, engine):
        engine.create_checkpoint("cp1", "t1")
        engine.rollback_checkpoint("cp1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.rollback_checkpoint("cp1")

    def test_rollback_committed_raises(self, engine):
        engine.create_checkpoint("cp1", "t1")
        engine.commit_checkpoint("cp1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.rollback_checkpoint("cp1")

    def test_rollback_failed_raises(self, engine):
        engine.create_checkpoint("cp1", "t1")
        engine.fail_checkpoint("cp1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.rollback_checkpoint("cp1")


class TestCheckpointTerminalBlock:
    """All terminal dispositions block all transitions."""

    @pytest.mark.parametrize("terminal_fn", [
        "commit_checkpoint", "fail_checkpoint", "rollback_checkpoint",
    ])
    @pytest.mark.parametrize("attempt_fn", [
        "commit_checkpoint", "fail_checkpoint", "rollback_checkpoint",
    ])
    def test_terminal_blocks_all(self, engine, terminal_fn, attempt_fn):
        engine.create_checkpoint("cp1", "t1")
        getattr(engine, terminal_fn)("cp1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            getattr(engine, attempt_fn)("cp1")


# =====================================================================
# 8. Retry schedules
# =====================================================================


class TestCreateRetrySchedule:
    def test_basic_creation(self, engine):
        rs = engine.create_retry_schedule("rs1", "t1", "task-1")
        assert rs.schedule_id == "rs1"
        assert rs.tenant_id == "t1"
        assert rs.task_ref == "task-1"
        assert rs.max_retries == 3
        assert rs.retry_count == 0
        assert rs.backoff_ms == 1000

    def test_custom_max_retries(self, engine):
        rs = engine.create_retry_schedule("rs1", "t1", "task-1", max_retries=10)
        assert rs.max_retries == 10

    def test_custom_backoff(self, engine):
        rs = engine.create_retry_schedule("rs1", "t1", "task-1", backoff_ms=5000)
        assert rs.backoff_ms == 5000

    def test_duplicate_raises(self, engine):
        engine.create_retry_schedule("rs1", "t1", "task-1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            engine.create_retry_schedule("rs1", "t1", "task-1")

    def test_increments_count(self, engine):
        engine.create_retry_schedule("rs1", "t1", "task-1")
        engine.create_retry_schedule("rs2", "t1", "task-2")
        assert engine.retry_count == 2


class TestIncrementRetry:
    def test_increment_once(self, engine):
        engine.create_retry_schedule("rs1", "t1", "task-1", max_retries=3)
        rs = engine.increment_retry("rs1")
        assert rs.retry_count == 1

    def test_increment_twice(self, engine):
        engine.create_retry_schedule("rs1", "t1", "task-1", max_retries=3)
        engine.increment_retry("rs1")
        rs = engine.increment_retry("rs1")
        assert rs.retry_count == 2

    def test_exhaust_raises(self, engine):
        engine.create_retry_schedule("rs1", "t1", "task-1", max_retries=2)
        engine.increment_retry("rs1")
        with pytest.raises(RuntimeCoreInvariantError, match="exceeded max_retries") as exc_info:
            engine.increment_retry("rs1")
        assert str(exc_info.value) == "retry schedule exceeded max_retries"
        assert "rs1" not in str(exc_info.value)
        assert "2" not in str(exc_info.value)

    def test_exhaust_max_one(self, engine):
        engine.create_retry_schedule("rs1", "t1", "task-1", max_retries=1)
        with pytest.raises(RuntimeCoreInvariantError, match="exceeded max_retries"):
            engine.increment_retry("rs1")

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown"):
            engine.increment_retry("no-such")

    def test_increment_emits_event(self, engine, spine):
        engine.create_retry_schedule("rs1", "t1", "task-1", max_retries=5)
        before = spine.event_count
        engine.increment_retry("rs1")
        assert spine.event_count > before

    def test_preserves_backoff(self, engine):
        engine.create_retry_schedule("rs1", "t1", "task-1", max_retries=5, backoff_ms=2000)
        rs = engine.increment_retry("rs1")
        assert rs.backoff_ms == 2000

    def test_preserves_task_ref(self, engine):
        engine.create_retry_schedule("rs1", "t1", "task-1", max_retries=5)
        rs = engine.increment_retry("rs1")
        assert rs.task_ref == "task-1"


# =====================================================================
# 9. Concurrency locks
# =====================================================================


class TestAcquireLock:
    def test_basic_acquisition(self, engine):
        lk = engine.acquire_lock("lk1", "t1", "res1", "w1")
        assert lk.lock_id == "lk1"
        assert lk.tenant_id == "t1"
        assert lk.resource_ref == "res1"
        assert lk.holder_ref == "w1"

    def test_duplicate_id_raises(self, engine):
        engine.acquire_lock("lk1", "t1", "res1", "w1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            engine.acquire_lock("lk1", "t1", "res2", "w2")

    def test_duplicate_resource_raises(self, engine):
        engine.acquire_lock("lk1", "t1", "res1", "w1")
        with pytest.raises(RuntimeCoreInvariantError, match="already locked"):
            engine.acquire_lock("lk2", "t1", "res1", "w2")

    def test_increments_count(self, engine):
        engine.acquire_lock("lk1", "t1", "res1", "w1")
        engine.acquire_lock("lk2", "t1", "res2", "w2")
        assert engine.lock_count == 2

    def test_emits_event(self, engine, spine):
        engine.acquire_lock("lk1", "t1", "res1", "w1")
        assert spine.event_count >= 1

    def test_different_resources_ok(self, engine):
        engine.acquire_lock("lk1", "t1", "res1", "w1")
        lk2 = engine.acquire_lock("lk2", "t1", "res2", "w1")
        assert lk2.resource_ref == "res2"


class TestReleaseLock:
    def test_release_existing(self, engine):
        engine.acquire_lock("lk1", "t1", "res1", "w1")
        lk = engine.release_lock("lk1")
        assert lk.lock_id == "lk1"
        assert engine.lock_count == 0

    def test_release_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown"):
            engine.release_lock("no-such")

    def test_release_allows_reacquire(self, engine):
        engine.acquire_lock("lk1", "t1", "res1", "w1")
        engine.release_lock("lk1")
        lk2 = engine.acquire_lock("lk2", "t1", "res1", "w2")
        assert lk2.resource_ref == "res1"

    def test_release_emits_event(self, engine, spine):
        engine.acquire_lock("lk1", "t1", "res1", "w1")
        before = spine.event_count
        engine.release_lock("lk1")
        assert spine.event_count > before


# =====================================================================
# 10. Backpressure computation
# =====================================================================


class TestComputeBackpressure:
    def test_zero_max_depth_gives_none(self, engine):
        engine.create_queue("q1", "t1", "Q", max_depth=0)
        q = engine.compute_backpressure("q1")
        assert q.backpressure == BackpressureLevel.NONE

    def test_empty_queue_none(self, engine):
        engine.create_queue("q1", "t1", "Q", max_depth=100)
        q = engine.compute_backpressure("q1")
        assert q.backpressure == BackpressureLevel.NONE

    def test_unknown_queue_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown"):
            engine.compute_backpressure("no-such")

    def test_emits_event(self, engine, spine):
        engine.create_queue("q1", "t1", "Q")
        before = spine.event_count
        engine.compute_backpressure("q1")
        assert spine.event_count > before


class TestBackpressureEscalation:
    """Test the escalation ladder: NONE -> LOW -> MEDIUM -> HIGH -> CRITICAL.
    Thresholds: <0.3 NONE, >=0.3 LOW, >=0.5 MEDIUM, >=0.7 HIGH, >=0.9 CRITICAL.
    """

    @pytest.mark.parametrize("depth,max_depth,expected", [
        (0, 100, BackpressureLevel.NONE),
        (10, 100, BackpressureLevel.NONE),
        (29, 100, BackpressureLevel.NONE),
        (30, 100, BackpressureLevel.LOW),
        (40, 100, BackpressureLevel.LOW),
        (49, 100, BackpressureLevel.LOW),
        (50, 100, BackpressureLevel.MEDIUM),
        (60, 100, BackpressureLevel.MEDIUM),
        (69, 100, BackpressureLevel.MEDIUM),
        (70, 100, BackpressureLevel.HIGH),
        (80, 100, BackpressureLevel.HIGH),
        (89, 100, BackpressureLevel.HIGH),
        (90, 100, BackpressureLevel.CRITICAL),
        (95, 100, BackpressureLevel.CRITICAL),
        (100, 100, BackpressureLevel.CRITICAL),
    ])
    def test_escalation_levels(self, engine, depth, max_depth, expected):
        engine.create_queue("q1", "t1", "Q", max_depth=max_depth)
        # Need to set depth directly since create_queue sets it to 0
        # We'll create a queue record with the right depth by manipulating internals
        q = engine.get_queue("q1")
        from mcoi_runtime.contracts.distributed_runtime import QueueRecord
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        updated = QueueRecord(
            queue_id=q.queue_id, tenant_id=q.tenant_id,
            display_name=q.display_name, status=q.status,
            depth=depth, max_depth=max_depth,
            backpressure=q.backpressure, created_at=now,
        )
        engine._queues["q1"] = updated
        result = engine.compute_backpressure("q1")
        assert result.backpressure == expected


# =====================================================================
# 11. Distributed snapshot
# =====================================================================


class TestDistributedSnapshot:
    def test_empty_snapshot(self, engine):
        snap = engine.distributed_snapshot("snap1", "t1")
        assert snap.snapshot_id == "snap1"
        assert snap.tenant_id == "t1"
        assert snap.total_workers == 0
        assert snap.total_queues == 0
        assert snap.total_leases == 0
        assert snap.total_shards == 0
        assert snap.total_checkpoints == 0
        assert snap.total_violations == 0

    def test_snapshot_reflects_workers(self, engine):
        engine.register_worker("w1", "t1", "W1")
        engine.register_worker("w2", "t1", "W2")
        snap = engine.distributed_snapshot("snap1", "t1")
        assert snap.total_workers == 2

    def test_snapshot_filters_by_tenant(self, engine):
        engine.register_worker("w1", "t1", "W1")
        engine.register_worker("w2", "t2", "W2")
        snap = engine.distributed_snapshot("snap1", "t1")
        assert snap.total_workers == 1

    def test_snapshot_includes_queues(self, engine):
        engine.create_queue("q1", "t1", "Q")
        snap = engine.distributed_snapshot("snap1", "t1")
        assert snap.total_queues == 1

    def test_snapshot_includes_leases(self, engine):
        engine.acquire_lease("l1", "t1", "w1", "task-1")
        snap = engine.distributed_snapshot("snap1", "t1")
        assert snap.total_leases == 1

    def test_snapshot_includes_shards(self, engine):
        engine.register_shard("s1", "t1", "pk1", "w1")
        snap = engine.distributed_snapshot("snap1", "t1")
        assert snap.total_shards == 1

    def test_snapshot_includes_checkpoints(self, engine):
        engine.create_checkpoint("cp1", "t1")
        snap = engine.distributed_snapshot("snap1", "t1")
        assert snap.total_checkpoints == 1

    def test_snapshot_emits_event(self, engine, spine):
        before = spine.event_count
        engine.distributed_snapshot("snap1", "t1")
        assert spine.event_count > before

    def test_snapshot_different_tenant_zero(self, engine):
        engine.register_worker("w1", "t1", "W")
        snap = engine.distributed_snapshot("snap1", "t2")
        assert snap.total_workers == 0


# =====================================================================
# 12. Violation detection
# =====================================================================


class TestDetectViolations:
    def test_no_violations_on_clean_state(self, engine):
        engine.register_worker("w1", "t1", "W")
        result = engine.detect_distributed_violations("t1")
        assert len(result) == 0

    def test_orphaned_shard_violation(self, engine):
        engine.register_shard("s1", "t1", "pk1", "w1")
        # Manually set shard to ORPHANED
        from mcoi_runtime.contracts.distributed_runtime import ShardRecord
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        orphaned = ShardRecord(
            shard_id="s1", tenant_id="t1", partition_key="pk1",
            status=ShardStatus.ORPHANED, record_count=0,
            assigned_worker="w1", created_at=now,
        )
        engine._shards["s1"] = orphaned
        result = engine.detect_distributed_violations("t1")
        assert len(result) >= 1
        ops = [v.operation for v in result]
        assert "orphaned_shard" in ops
        violation = next(v for v in result if v.operation == "orphaned_shard")
        assert violation.reason == "orphaned shard"
        assert "s1" not in violation.reason

    def test_held_lease_violation(self, engine):
        engine.acquire_lease("l1", "t1", "w1", "task-1")
        result = engine.detect_distributed_violations("t1")
        assert len(result) >= 1
        ops = [v.operation for v in result]
        assert "expired_lease_held" in ops
        violation = next(v for v in result if v.operation == "expired_lease_held")
        assert violation.reason == "held lease may be expired"
        assert "l1" not in violation.reason

    def test_critical_backpressure_violation(self, engine):
        engine.create_queue("q1", "t1", "Q", max_depth=100)
        # Set depth to trigger critical
        from mcoi_runtime.contracts.distributed_runtime import QueueRecord
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        updated = QueueRecord(
            queue_id="q1", tenant_id="t1", display_name="Q",
            status=QueueStatus.ACTIVE, depth=95, max_depth=100,
            backpressure=BackpressureLevel.CRITICAL, created_at=now,
        )
        engine._queues["q1"] = updated
        result = engine.detect_distributed_violations("t1")
        assert len(result) >= 1
        ops = [v.operation for v in result]
        assert "queue_critical_backpressure" in ops
        violation = next(v for v in result if v.operation == "queue_critical_backpressure")
        assert violation.reason == "queue has critical backpressure"
        assert "q1" not in violation.reason

    def test_idempotent_second_call_empty(self, engine):
        engine.acquire_lease("l1", "t1", "w1", "task-1")
        first = engine.detect_distributed_violations("t1")
        assert len(first) >= 1
        second = engine.detect_distributed_violations("t1")
        assert len(second) == 0

    def test_idempotent_preserves_count(self, engine):
        engine.acquire_lease("l1", "t1", "w1", "task-1")
        engine.detect_distributed_violations("t1")
        count_after_first = engine.violation_count
        engine.detect_distributed_violations("t1")
        assert engine.violation_count == count_after_first

    def test_violations_filter_by_tenant(self, engine):
        engine.acquire_lease("l1", "t1", "w1", "task-1")
        result = engine.detect_distributed_violations("t2")
        assert len(result) == 0

    def test_violations_emits_event_when_found(self, engine, spine):
        engine.acquire_lease("l1", "t1", "w1", "task-1")
        before = spine.event_count
        engine.detect_distributed_violations("t1")
        assert spine.event_count > before

    def test_violations_no_event_when_clean(self, engine, spine):
        engine.register_worker("w1", "t1", "W")
        before = spine.event_count
        engine.detect_distributed_violations("t1")
        assert spine.event_count == before

    def test_multiple_violation_types(self, engine):
        # Lease held -> violation
        engine.acquire_lease("l1", "t1", "w1", "task-1")
        # Orphaned shard -> violation
        from mcoi_runtime.contracts.distributed_runtime import ShardRecord
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        orphaned = ShardRecord(
            shard_id="s1", tenant_id="t1", partition_key="pk1",
            status=ShardStatus.ORPHANED, record_count=0,
            assigned_worker="w1", created_at=now,
        )
        engine._shards["s1"] = orphaned
        result = engine.detect_distributed_violations("t1")
        assert len(result) >= 2


# =====================================================================
# 13. State hash
# =====================================================================


class TestStateHash:
    def test_empty_state_hash(self, engine):
        h = engine.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex

    def test_deterministic(self, engine):
        engine.register_worker("w1", "t1", "W")
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_different_after_mutation(self, engine):
        h_empty = engine.state_hash()
        engine.register_worker("w1", "t1", "W")
        h_worker = engine.state_hash()
        assert h_empty != h_worker

    def test_different_after_status_change(self, engine):
        engine.register_worker("w1", "t1", "W")
        h_before = engine.state_hash()
        engine.drain_worker("w1")
        h_after = engine.state_hash()
        assert h_before != h_after

    def test_includes_leases(self, engine):
        h_before = engine.state_hash()
        engine.acquire_lease("l1", "t1", "w1", "task-1")
        h_after = engine.state_hash()
        assert h_before != h_after

    def test_includes_shards(self, engine):
        h_before = engine.state_hash()
        engine.register_shard("s1", "t1", "pk1", "w1")
        h_after = engine.state_hash()
        assert h_before != h_after

    def test_includes_checkpoints(self, engine):
        h_before = engine.state_hash()
        engine.create_checkpoint("cp1", "t1")
        h_after = engine.state_hash()
        assert h_before != h_after

    def test_includes_locks(self, engine):
        h_before = engine.state_hash()
        engine.acquire_lock("lk1", "t1", "res1", "w1")
        h_after = engine.state_hash()
        assert h_before != h_after

    def test_includes_retries(self, engine):
        h_before = engine.state_hash()
        engine.create_retry_schedule("rs1", "t1", "task-1")
        h_after = engine.state_hash()
        assert h_before != h_after

    def test_includes_violations(self, engine):
        engine.acquire_lease("l1", "t1", "w1", "task-1")
        h_before = engine.state_hash()
        engine.detect_distributed_violations("t1")
        h_after = engine.state_hash()
        assert h_before != h_after


# =====================================================================
# 14. Replay determinism
# =====================================================================


class TestReplayDeterminism:
    def test_same_ops_same_hash(self):
        """Two engines with identical operations produce identical state_hash."""
        spine1 = EventSpineEngine()
        spine2 = EventSpineEngine()
        eng1 = DistributedRuntimeEngine(spine1)
        eng2 = DistributedRuntimeEngine(spine2)

        for eng in (eng1, eng2):
            eng.register_worker("w1", "t1", "W1")
            eng.register_worker("w2", "t1", "W2")
            eng.create_queue("q1", "t1", "Q1")
            eng.acquire_lease("l1", "t1", "w1", "task-1")
            eng.register_shard("s1", "t1", "pk1", "w1")
            eng.create_checkpoint("cp1", "t1")
            eng.create_retry_schedule("rs1", "t1", "task-1")
            eng.acquire_lock("lk1", "t1", "res1", "w1")

        assert eng1.state_hash() == eng2.state_hash()

    def test_different_order_different_ops_different_hash(self):
        spine1 = EventSpineEngine()
        spine2 = EventSpineEngine()
        eng1 = DistributedRuntimeEngine(spine1)
        eng2 = DistributedRuntimeEngine(spine2)

        eng1.register_worker("w1", "t1", "W1")
        eng2.register_worker("w2", "t1", "W2")

        assert eng1.state_hash() != eng2.state_hash()


# =====================================================================
# 15. Golden scenarios
# =====================================================================


class TestGoldenScenario1WorkerLifecycle:
    """Worker registers, acquires lease, completes work (release lease), terminates."""

    def test_full_lifecycle(self, engine, spine):
        w = engine.register_worker("w1", "t1", "Worker-A")
        assert w.status == WorkerStatus.IDLE

        le = engine.acquire_lease("l1", "t1", "w1", "task-1")
        assert le.status == LeaseStatus.HELD

        le_released = engine.release_lease("l1")
        assert le_released.status == LeaseStatus.RELEASED

        w_drained = engine.drain_worker("w1")
        assert w_drained.status == WorkerStatus.DRAINING

        w_terminated = engine.terminate_worker("w1")
        assert w_terminated.status == WorkerStatus.TERMINATED

        assert spine.event_count >= 5


class TestGoldenScenario2BackpressureEscalation:
    """Queue backpressure escalates NONE -> LOW -> MEDIUM -> HIGH -> CRITICAL."""

    def test_escalation_ladder(self, engine):
        engine.create_queue("q1", "t1", "Q", max_depth=100)

        from mcoi_runtime.contracts.distributed_runtime import QueueRecord
        from datetime import datetime, timezone

        thresholds = [
            (0, BackpressureLevel.NONE),
            (30, BackpressureLevel.LOW),
            (50, BackpressureLevel.MEDIUM),
            (70, BackpressureLevel.HIGH),
            (90, BackpressureLevel.CRITICAL),
        ]

        for depth, expected_level in thresholds:
            now = datetime.now(timezone.utc).isoformat()
            q = engine.get_queue("q1")
            updated = QueueRecord(
                queue_id=q.queue_id, tenant_id=q.tenant_id,
                display_name=q.display_name, status=q.status,
                depth=depth, max_depth=100,
                backpressure=q.backpressure, created_at=now,
            )
            engine._queues["q1"] = updated
            result = engine.compute_backpressure("q1")
            assert result.backpressure == expected_level


class TestGoldenScenario3ShardMigration:
    """Shard migration lifecycle: ASSIGNED -> MIGRATING -> ASSIGNED -> DECOMMISSIONED."""

    def test_migration_lifecycle(self, engine, spine):
        s = engine.register_shard("s1", "t1", "pk1", "w1")
        assert s.status == ShardStatus.ASSIGNED

        s_migrating = engine.migrate_shard("s1")
        assert s_migrating.status == ShardStatus.MIGRATING

        s_assigned = engine.complete_migration("s1")
        assert s_assigned.status == ShardStatus.ASSIGNED

        s_decom = engine.decommission_shard("s1")
        assert s_decom.status == ShardStatus.DECOMMISSIONED

        # Terminal blocks
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.migrate_shard("s1")

        assert spine.event_count >= 4


class TestGoldenScenario4CheckpointCommitRollback:
    """Checkpoint commit/rollback: create -> commit (OK), create -> rollback (OK)."""

    def test_commit(self, engine):
        cp = engine.create_checkpoint("cp1", "t1", shard_count=3, worker_count=2)
        assert cp.disposition == CheckpointDisposition.PENDING

        committed = engine.commit_checkpoint("cp1")
        assert committed.disposition == CheckpointDisposition.COMMITTED

    def test_rollback(self, engine):
        cp = engine.create_checkpoint("cp2", "t1")
        assert cp.disposition == CheckpointDisposition.PENDING

        rolled = engine.rollback_checkpoint("cp2")
        assert rolled.disposition == CheckpointDisposition.ROLLED_BACK


class TestGoldenScenario5RetryExhaustion:
    """Retry schedule: max_retries=3, increment 2 times OK, third raises."""

    def test_exhaust_retries(self, engine, spine):
        engine.create_retry_schedule("rs1", "t1", "task-1", max_retries=3)

        rs1 = engine.increment_retry("rs1")
        assert rs1.retry_count == 1

        rs2 = engine.increment_retry("rs1")
        assert rs2.retry_count == 2

        with pytest.raises(RuntimeCoreInvariantError, match="exceeded max_retries") as exc_info:
            engine.increment_retry("rs1")
        assert str(exc_info.value) == "retry schedule exceeded max_retries"
        assert "rs1" not in str(exc_info.value)
        assert "3" not in str(exc_info.value)

        assert spine.event_count >= 3


class TestGoldenScenario6ReplaySameHash:
    """Same operations on two independent engines -> same state_hash."""

    def test_replay_determinism(self):
        def run_scenario(eng: DistributedRuntimeEngine):
            eng.register_worker("w1", "t1", "Worker-A", capacity=10)
            eng.register_worker("w2", "t1", "Worker-B", capacity=20)
            eng.create_queue("q1", "t1", "Queue-A", max_depth=500)
            eng.acquire_lease("l1", "t1", "w1", "task-1", ttl_ms=10000)
            eng.release_lease("l1")
            eng.register_shard("s1", "t1", "pk1", "w1", record_count=50)
            eng.migrate_shard("s1")
            eng.complete_migration("s1")
            eng.create_checkpoint("cp1", "t1", shard_count=1, worker_count=2)
            eng.commit_checkpoint("cp1")
            eng.create_retry_schedule("rs1", "t1", "task-1", max_retries=5, backoff_ms=2000)
            eng.increment_retry("rs1")
            eng.acquire_lock("lk1", "t1", "res1", "w1")
            eng.drain_worker("w1")
            eng.terminate_worker("w1")

        spine1 = EventSpineEngine()
        spine2 = EventSpineEngine()
        eng1 = DistributedRuntimeEngine(spine1)
        eng2 = DistributedRuntimeEngine(spine2)

        run_scenario(eng1)
        run_scenario(eng2)

        assert eng1.state_hash() == eng2.state_hash()


# =====================================================================
# 16. Edge cases: get_worker / get_queue for unknown IDs
# =====================================================================


class TestGetWorker:
    def test_get_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown"):
            engine.get_worker("no-such")

    def test_get_returns_registered(self, engine):
        engine.register_worker("w1", "t1", "W")
        w = engine.get_worker("w1")
        assert w.worker_id == "w1"


class TestGetQueue:
    def test_get_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown"):
            engine.get_queue("no-such")

    def test_get_returns_created(self, engine):
        engine.create_queue("q1", "t1", "Q")
        q = engine.get_queue("q1")
        assert q.queue_id == "q1"


# =====================================================================
# 17. Additional property count tests
# =====================================================================


class TestPropertyCounts:
    def test_worker_count_after_terminate(self, engine):
        engine.register_worker("w1", "t1", "W")
        engine.terminate_worker("w1")
        # Terminated workers still count
        assert engine.worker_count == 1

    def test_lease_count_after_release(self, engine):
        engine.acquire_lease("l1", "t1", "w1", "task-1")
        engine.release_lease("l1")
        # Released leases still count
        assert engine.lease_count == 1

    def test_shard_count_after_decommission(self, engine):
        engine.register_shard("s1", "t1", "pk1", "w1")
        engine.decommission_shard("s1")
        assert engine.shard_count == 1

    def test_checkpoint_count_after_commit(self, engine):
        engine.create_checkpoint("cp1", "t1")
        engine.commit_checkpoint("cp1")
        assert engine.checkpoint_count == 1

    def test_lock_count_after_release(self, engine):
        engine.acquire_lock("lk1", "t1", "res1", "w1")
        engine.release_lock("lk1")
        # Locks are removed on release
        assert engine.lock_count == 0

    def test_violation_count_after_detection(self, engine):
        engine.acquire_lease("l1", "t1", "w1", "task-1")
        engine.detect_distributed_violations("t1")
        assert engine.violation_count >= 1


# =====================================================================
# 18. Event spine integration
# =====================================================================


class TestEventSpineIntegration:
    def test_all_operations_emit_events(self, engine, spine):
        engine.register_worker("w1", "t1", "W")
        engine.create_queue("q1", "t1", "Q")
        engine.acquire_lease("l1", "t1", "w1", "task-1")
        engine.register_shard("s1", "t1", "pk1", "w1")
        engine.create_checkpoint("cp1", "t1")
        engine.create_retry_schedule("rs1", "t1", "task-1", max_retries=5)
        engine.acquire_lock("lk1", "t1", "res1", "w1")
        engine.drain_worker("w1")
        engine.pause_queue("q1")
        engine.release_lease("l1")
        engine.migrate_shard("s1")
        engine.commit_checkpoint("cp1")
        engine.increment_retry("rs1")
        engine.release_lock("lk1")
        engine.terminate_worker("w1")
        engine.resume_queue("q1")
        engine.complete_migration("s1")
        engine.compute_backpressure("q1")
        engine.distributed_snapshot("snap1", "t1")

        # Each operation emits at least one event
        assert spine.event_count >= 19

    def test_event_count_starts_zero(self, spine):
        assert spine.event_count == 0

    def test_register_worker_single_event(self, engine, spine):
        engine.register_worker("w1", "t1", "W")
        assert spine.event_count == 1


# =====================================================================
# 19. Multi-tenant isolation
# =====================================================================


class TestMultiTenantIsolation:
    def test_workers_isolated(self, engine):
        engine.register_worker("w1", "t1", "W1")
        engine.register_worker("w2", "t2", "W2")
        assert len(engine.workers_for_tenant("t1")) == 1
        assert len(engine.workers_for_tenant("t2")) == 1

    def test_queues_isolated(self, engine):
        engine.create_queue("q1", "t1", "Q1")
        engine.create_queue("q2", "t2", "Q2")
        assert len(engine.queues_for_tenant("t1")) == 1
        assert len(engine.queues_for_tenant("t2")) == 1

    def test_snapshot_isolated(self, engine):
        engine.register_worker("w1", "t1", "W1")
        engine.register_worker("w2", "t2", "W2")
        engine.create_queue("q1", "t1", "Q1")
        snap = engine.distributed_snapshot("snap1", "t1")
        assert snap.total_workers == 1
        assert snap.total_queues == 1

    def test_violations_isolated(self, engine):
        engine.acquire_lease("l1", "t1", "w1", "task-1")
        engine.acquire_lease("l2", "t2", "w2", "task-2")
        v1 = engine.detect_distributed_violations("t1")
        v2 = engine.detect_distributed_violations("t2")
        assert len(v1) >= 1
        assert len(v2) >= 1
        # Each tenant has its own violations
        t1_ids = {v.violation_id for v in v1}
        t2_ids = {v.violation_id for v in v2}
        assert t1_ids.isdisjoint(t2_ids)


# =====================================================================
# 20. Concurrent lock edge cases
# =====================================================================


class TestLockEdgeCases:
    def test_same_holder_different_resources(self, engine):
        engine.acquire_lock("lk1", "t1", "res1", "w1")
        lk2 = engine.acquire_lock("lk2", "t1", "res2", "w1")
        assert lk2.holder_ref == "w1"
        assert engine.lock_count == 2

    def test_release_then_reacquire_same_resource(self, engine):
        engine.acquire_lock("lk1", "t1", "res1", "w1")
        engine.release_lock("lk1")
        lk2 = engine.acquire_lock("lk2", "t1", "res1", "w2")
        assert lk2.holder_ref == "w2"

    def test_release_then_reacquire_same_id_different_resource(self, engine):
        engine.acquire_lock("lk1", "t1", "res1", "w1")
        engine.release_lock("lk1")
        # After release, the same ID is gone, so we can't reuse it
        # (lock_id removed from dict on release)
        lk2 = engine.acquire_lock("lk1", "t1", "res2", "w2")
        assert lk2.lock_id == "lk1"
