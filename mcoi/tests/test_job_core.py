"""Tests for the job core engine — WorkQueue and JobEngine."""

import pytest

from mcoi_runtime.contracts.job import (
    AssignmentRecord,
    DeadlineRecord,
    FollowUpRecord,
    JobDescriptor,
    JobExecutionRecord,
    JobPauseRecord,
    JobPriority,
    JobResumeRecord,
    JobState,
    JobStatus,
    PauseReason,
    SlaStatus,
    WorkQueueEntry,
)
from mcoi_runtime.core.jobs import JobEngine, WorkQueue
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# --- Helpers ---

_T0 = "2025-06-01T12:00:00+00:00"
_T1 = "2025-06-01T12:00:01+00:00"
_T2 = "2025-06-01T12:00:02+00:00"
_T3 = "2025-06-01T12:00:03+00:00"
_T4 = "2025-06-01T12:00:04+00:00"
_T5 = "2025-06-01T12:00:05+00:00"
_T6 = "2025-06-01T12:00:06+00:00"
_T7 = "2025-06-01T12:00:07+00:00"
_T8 = "2025-06-01T12:00:08+00:00"
_T9 = "2025-06-01T12:00:09+00:00"
_T10 = "2025-06-01T12:00:10+00:00"

_DEADLINE_FUTURE = "2025-07-01T00:00:00+00:00"
_DEADLINE_PAST = "2025-05-01T00:00:00+00:00"

# Offsets from T0
_T0_PLUS_30M = "2025-06-01T12:30:00+00:00"
_T0_PLUS_50M = "2025-06-01T12:50:00+00:00"
_T0_PLUS_80M = "2025-06-01T13:20:00+00:00"
_T0_PLUS_120M = "2025-06-01T14:00:00+00:00"


def _make_clock(times: list[str]):
    """Return a clock function that yields successive timestamps."""
    it = iter(times)

    def clock() -> str:
        return next(it)

    return clock


def _fixed_clock(t: str = _T0):
    """Return a clock that always returns the same time."""
    return lambda: t


# ============================================================
# WorkQueue tests
# ============================================================


class TestWorkQueueEnqueue:
    def test_enqueue_returns_entry(self):
        clock = _make_clock([_T0, _T0])
        q = WorkQueue(clock=clock)
        desc = JobDescriptor(
            job_id="j-1", name="Task A", description="Do A",
            priority=JobPriority.NORMAL, created_at=_T0,
        )
        entry = q.enqueue(desc)
        assert isinstance(entry, WorkQueueEntry)
        assert entry.job_id == "j-1"
        assert entry.priority == JobPriority.NORMAL

    def test_enqueue_multiple(self):
        clock = _make_clock([_T0, _T0, _T1, _T1, _T2, _T2])
        q = WorkQueue(clock=clock)
        for i, prio in enumerate([JobPriority.LOW, JobPriority.HIGH, JobPriority.NORMAL]):
            desc = JobDescriptor(
                job_id=f"j-{i}", name=f"Task {i}", description=f"Do {i}",
                priority=prio, created_at=_T0,
            )
            q.enqueue(desc)
        entries = q.list_entries()
        assert len(entries) == 3
        # Sorted: HIGH, NORMAL, LOW
        assert entries[0].priority == JobPriority.HIGH
        assert entries[1].priority == JobPriority.NORMAL
        assert entries[2].priority == JobPriority.LOW

    def test_duplicate_entry_rejected_without_reflection(self):
        clock = _fixed_clock()
        q = WorkQueue(clock=clock)
        desc = JobDescriptor(
            job_id="j-dup", name="Task A", description="Do A",
            priority=JobPriority.NORMAL, created_at=_T0,
        )
        q.enqueue(desc)
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate queue entry") as excinfo:
            q.enqueue(desc)
        assert str(excinfo.value) == "duplicate queue entry"
        assert "j-dup" not in str(excinfo.value)


class TestWorkQueueDequeue:
    def test_dequeue_empty(self):
        q = WorkQueue(clock=_fixed_clock())
        assert q.dequeue_next() is None

    def test_dequeue_priority_order(self):
        clock = _make_clock([_T0, _T0, _T1, _T1, _T2, _T2])
        q = WorkQueue(clock=clock)
        descs = [
            JobDescriptor(job_id="j-low", name="Low", description="d",
                          priority=JobPriority.LOW, created_at=_T0),
            JobDescriptor(job_id="j-crit", name="Crit", description="d",
                          priority=JobPriority.CRITICAL, created_at=_T0),
            JobDescriptor(job_id="j-norm", name="Norm", description="d",
                          priority=JobPriority.NORMAL, created_at=_T0),
        ]
        for d in descs:
            q.enqueue(d)
        first = q.dequeue_next()
        assert first is not None
        assert first.priority == JobPriority.CRITICAL

    def test_dequeue_fifo_same_priority(self):
        clock = _make_clock([_T0, _T0, _T1, _T1])
        q = WorkQueue(clock=clock)
        d1 = JobDescriptor(job_id="j-a", name="A", description="d",
                           priority=JobPriority.NORMAL, created_at=_T0)
        d2 = JobDescriptor(job_id="j-b", name="B", description="d",
                           priority=JobPriority.NORMAL, created_at=_T0)
        q.enqueue(d1)
        q.enqueue(d2)
        first = q.dequeue_next()
        assert first is not None
        assert first.job_id == "j-a"

    def test_dequeue_removes_entry(self):
        clock = _make_clock([_T0, _T0])
        q = WorkQueue(clock=clock)
        desc = JobDescriptor(job_id="j-1", name="A", description="d",
                             priority=JobPriority.NORMAL, created_at=_T0)
        q.enqueue(desc)
        q.dequeue_next()
        assert q.dequeue_next() is None


class TestWorkQueuePeek:
    def test_peek_empty(self):
        q = WorkQueue(clock=_fixed_clock())
        assert q.peek() is None

    def test_peek_does_not_remove(self):
        clock = _make_clock([_T0, _T0])
        q = WorkQueue(clock=clock)
        desc = JobDescriptor(job_id="j-1", name="A", description="d",
                             priority=JobPriority.NORMAL, created_at=_T0)
        q.enqueue(desc)
        entry = q.peek()
        assert entry is not None
        assert len(q.list_entries()) == 1


class TestWorkQueueAssign:
    def test_assign_returns_record(self):
        clock = _make_clock([_T0, _T0, _T1, _T1])
        q = WorkQueue(clock=clock)
        desc = JobDescriptor(job_id="j-1", name="A", description="d",
                             priority=JobPriority.NORMAL, created_at=_T0)
        entry = q.enqueue(desc)
        record = q.assign(entry.entry_id, "person-1", "manager-1", "needed expertise")
        assert isinstance(record, AssignmentRecord)
        assert record.job_id == "j-1"
        assert record.assigned_to_id == "person-1"

    def test_assign_nonexistent_entry_raises(self):
        q = WorkQueue(clock=_fixed_clock())
        with pytest.raises(RuntimeCoreInvariantError, match="queue entry not found") as excinfo:
            q.assign("no-such-entry", "person-1", "manager-1", "reason")
        assert str(excinfo.value) == "queue entry not found"
        assert "no-such-entry" not in str(excinfo.value)


class TestWorkQueueRemove:
    def test_remove_existing(self):
        clock = _make_clock([_T0, _T0])
        q = WorkQueue(clock=clock)
        desc = JobDescriptor(job_id="j-1", name="A", description="d",
                             priority=JobPriority.NORMAL, created_at=_T0)
        entry = q.enqueue(desc)
        assert q.remove(entry.entry_id) is True
        assert len(q.list_entries()) == 0

    def test_remove_nonexistent(self):
        q = WorkQueue(clock=_fixed_clock())
        assert q.remove("no-such-entry") is False


# ============================================================
# JobEngine — creation
# ============================================================


class TestJobCreation:
    def test_create_job_returns_descriptor_and_state(self):
        engine = JobEngine(clock=_make_clock([_T0, _T0]))
        desc, state = engine.create_job(
            "Task A", "Do task A", JobPriority.NORMAL,
        )
        assert isinstance(desc, JobDescriptor)
        assert isinstance(state, JobState)
        assert desc.name == "Task A"
        assert state.status == JobStatus.CREATED
        assert state.sla_status == SlaStatus.NOT_APPLICABLE

    def test_create_job_with_optional_fields(self):
        engine = JobEngine(clock=_make_clock([_T0, _T0]))
        desc, state = engine.create_job(
            "Task B", "Do task B", JobPriority.HIGH,
            goal_id="g-1", workflow_id="wf-1",
            deadline=_DEADLINE_FUTURE, sla_target_minutes=60,
        )
        assert desc.goal_id == "g-1"
        assert desc.workflow_id == "wf-1"
        assert desc.deadline == _DEADLINE_FUTURE
        assert desc.sla_target_minutes == 60

    def test_create_job_empty_name_raises(self):
        engine = JobEngine(clock=_fixed_clock())
        with pytest.raises(RuntimeCoreInvariantError):
            engine.create_job("", "description", JobPriority.NORMAL)


# ============================================================
# JobEngine — full lifecycle
# ============================================================


class TestJobLifecycleCreateStartComplete:
    def test_create_start_complete(self):
        engine = JobEngine(clock=_make_clock([_T0, _T0, _T1, _T2, _T3]))
        desc, state = engine.create_job("A", "desc", JobPriority.NORMAL)
        state = engine.start_job(desc.job_id)
        assert state.status == JobStatus.IN_PROGRESS
        state, record = engine.complete_job(desc.job_id, "all done")
        assert state.status == JobStatus.COMPLETED
        assert record.status == JobStatus.COMPLETED
        assert record.outcome_summary == "all done"


class TestJobLifecycleCreateStartPauseResumeComplete:
    def test_pause_resume_complete(self):
        clock = _make_clock([_T0, _T0, _T1, _T2, _T3, _T4, _T5, _T6, _T7])
        engine = JobEngine(clock=clock)
        desc, _ = engine.create_job("A", "desc", JobPriority.NORMAL)
        engine.start_job(desc.job_id)
        state, pause_rec = engine.pause_job(desc.job_id, PauseReason.AWAITING_RESPONSE)
        assert state.status == JobStatus.PAUSED
        assert isinstance(pause_rec, JobPauseRecord)
        assert pause_rec.reason == PauseReason.AWAITING_RESPONSE
        state, resume_rec = engine.resume_job(desc.job_id, "person-1", "input received")
        assert state.status == JobStatus.IN_PROGRESS
        assert isinstance(resume_rec, JobResumeRecord)
        state, exec_rec = engine.complete_job(desc.job_id, "done after resume")
        assert state.status == JobStatus.COMPLETED


class TestJobLifecycleCreateStartFail:
    def test_start_then_fail(self):
        engine = JobEngine(clock=_make_clock([_T0, _T0, _T1, _T2, _T3]))
        desc, _ = engine.create_job("A", "desc", JobPriority.NORMAL)
        engine.start_job(desc.job_id)
        state, record = engine.fail_job(desc.job_id, ("error-1", "error-2"))
        assert state.status == JobStatus.FAILED
        assert record.status == JobStatus.FAILED
        assert "error-1" in record.outcome_summary


class TestJobCancellation:
    def test_cancel_from_created(self):
        engine = JobEngine(clock=_make_clock([_T0, _T0, _T1]))
        desc, _ = engine.create_job("A", "desc", JobPriority.NORMAL)
        state = engine.cancel_job(desc.job_id, "no longer needed")
        assert state.status == JobStatus.CANCELLED

    def test_cancel_from_in_progress(self):
        engine = JobEngine(clock=_make_clock([_T0, _T0, _T1, _T2]))
        desc, _ = engine.create_job("A", "desc", JobPriority.NORMAL)
        engine.start_job(desc.job_id)
        state = engine.cancel_job(desc.job_id, "cancelled mid-run")
        assert state.status == JobStatus.CANCELLED

    def test_cancel_from_paused(self):
        engine = JobEngine(clock=_make_clock([_T0, _T0, _T1, _T2, _T3, _T4]))
        desc, _ = engine.create_job("A", "desc", JobPriority.NORMAL)
        engine.start_job(desc.job_id)
        engine.pause_job(desc.job_id, PauseReason.OPERATOR_HOLD)
        state = engine.cancel_job(desc.job_id, "abandoned")
        assert state.status == JobStatus.CANCELLED


# ============================================================
# Invalid transitions
# ============================================================


class TestInvalidTransitions:
    def test_start_archived_raises(self):
        """Cannot start an archived job."""
        engine = JobEngine(clock=_make_clock([_T0, _T0, _T1, _T2, _T3]))
        desc, _ = engine.create_job("A", "desc", JobPriority.NORMAL)
        engine.cancel_job(desc.job_id, "cancel")
        # Manually set to archived for this test
        engine._states[desc.job_id] = JobState(
            job_id=desc.job_id,
            status=JobStatus.ARCHIVED,
            sla_status=SlaStatus.NOT_APPLICABLE,
            updated_at=_T3,
        )
        with pytest.raises(RuntimeCoreInvariantError, match="invalid job state transition"):
            engine.start_job(desc.job_id)

    def test_complete_created_raises(self):
        """Cannot complete a job that hasn't started."""
        engine = JobEngine(clock=_make_clock([_T0, _T0, _T1]))
        desc, _ = engine.create_job("A", "desc", JobPriority.NORMAL)
        with pytest.raises(RuntimeCoreInvariantError, match="invalid job state transition"):
            engine.complete_job(desc.job_id, "premature")

    def test_pause_completed_raises(self):
        """Cannot pause a completed job."""
        engine = JobEngine(clock=_make_clock([_T0, _T0, _T1, _T2, _T3, _T4]))
        desc, _ = engine.create_job("A", "desc", JobPriority.NORMAL)
        engine.start_job(desc.job_id)
        engine.complete_job(desc.job_id, "done")
        with pytest.raises(RuntimeCoreInvariantError, match="invalid job state transition"):
            engine.pause_job(desc.job_id, PauseReason.OPERATOR_HOLD)

    def test_resume_non_paused_raises(self):
        """Cannot resume a job that isn't paused."""
        engine = JobEngine(clock=_make_clock([_T0, _T0, _T1, _T2]))
        desc, _ = engine.create_job("A", "desc", JobPriority.NORMAL)
        engine.start_job(desc.job_id)
        with pytest.raises(RuntimeCoreInvariantError, match="invalid job state transition"):
            engine.resume_job(desc.job_id, "person-1", "why")

    def test_cancel_archived_raises(self):
        """Cannot cancel an archived job."""
        engine = JobEngine(clock=_make_clock([_T0, _T0, _T1]))
        desc, _ = engine.create_job("A", "desc", JobPriority.NORMAL)
        engine._states[desc.job_id] = JobState(
            job_id=desc.job_id,
            status=JobStatus.ARCHIVED,
            sla_status=SlaStatus.NOT_APPLICABLE,
            updated_at=_T1,
        )
        with pytest.raises(RuntimeCoreInvariantError, match="invalid job state transition"):
            engine.cancel_job(desc.job_id, "too late")

    def test_fail_created_raises(self):
        """Cannot fail a job that hasn't started."""
        engine = JobEngine(clock=_make_clock([_T0, _T0, _T1]))
        desc, _ = engine.create_job("A", "desc", JobPriority.NORMAL)
        with pytest.raises(RuntimeCoreInvariantError, match="invalid job state transition"):
            engine.fail_job(desc.job_id, ("err",))


# ============================================================
# SLA evaluation
# ============================================================


class TestSlaEvaluation:
    def test_sla_not_applicable(self):
        engine = JobEngine(clock=_make_clock([_T0, _T0]))
        desc, _ = engine.create_job("A", "desc", JobPriority.NORMAL)
        record = engine.evaluate_sla(desc.job_id, _T0_PLUS_30M)
        assert record.sla_status == SlaStatus.NOT_APPLICABLE

    def test_sla_on_track(self):
        engine = JobEngine(clock=_make_clock([_T0, _T0]))
        desc, _ = engine.create_job(
            "A", "desc", JobPriority.NORMAL, sla_target_minutes=60,
        )
        # 30 minutes in, 50% of 60 min target -> on_track
        record = engine.evaluate_sla(desc.job_id, _T0_PLUS_30M)
        assert record.sla_status == SlaStatus.ON_TRACK

    def test_sla_at_risk(self):
        engine = JobEngine(clock=_make_clock([_T0, _T0]))
        desc, _ = engine.create_job(
            "A", "desc", JobPriority.NORMAL, sla_target_minutes=60,
        )
        # 50 minutes in, 83% of 60 min target -> at_risk
        record = engine.evaluate_sla(desc.job_id, _T0_PLUS_50M)
        assert record.sla_status == SlaStatus.AT_RISK

    def test_sla_breached(self):
        engine = JobEngine(clock=_make_clock([_T0, _T0]))
        desc, _ = engine.create_job(
            "A", "desc", JobPriority.NORMAL, sla_target_minutes=60,
        )
        # 80 minutes in, 133% of 60 min target -> breached
        record = engine.evaluate_sla(desc.job_id, _T0_PLUS_80M)
        assert record.sla_status == SlaStatus.BREACHED

    def test_sla_exact_boundary_at_risk(self):
        """Exactly at 80% should be at_risk."""
        engine = JobEngine(clock=_make_clock([_T0, _T0]))
        desc, _ = engine.create_job(
            "A", "desc", JobPriority.NORMAL, sla_target_minutes=100,
        )
        # 80 minutes of 100 min target = exactly 80% -> at_risk
        record = engine.evaluate_sla(desc.job_id, _T0_PLUS_80M)
        assert record.sla_status == SlaStatus.AT_RISK

    def test_sla_record_includes_target_minutes(self):
        engine = JobEngine(clock=_make_clock([_T0, _T0]))
        desc, _ = engine.create_job(
            "A", "desc", JobPriority.NORMAL, sla_target_minutes=60,
        )
        record = engine.evaluate_sla(desc.job_id, _T0_PLUS_30M)
        assert record.sla_target_minutes == 60


# ============================================================
# Follow-up scheduling
# ============================================================


class TestFollowUpScheduling:
    def test_schedule_follow_up(self):
        engine = JobEngine(clock=_make_clock([_T0, _T0]))
        desc, _ = engine.create_job("A", "desc", JobPriority.NORMAL)
        record = engine.schedule_follow_up(
            desc.job_id, "check status", _DEADLINE_FUTURE,
        )
        assert isinstance(record, FollowUpRecord)
        assert record.job_id == desc.job_id
        assert record.reason == "check status"
        assert record.resolved is False

    def test_schedule_follow_up_nonexistent_job_raises(self):
        engine = JobEngine(clock=_fixed_clock())
        with pytest.raises(RuntimeCoreInvariantError, match="job not found") as excinfo:
            engine.schedule_follow_up("no-such-job", "reason", _DEADLINE_FUTURE)
        assert str(excinfo.value) == "job not found"
        assert "no-such-job" not in str(excinfo.value)


# ============================================================
# Overdue job detection
# ============================================================


class TestOverdueDetection:
    def test_find_overdue_with_past_deadline(self):
        engine = JobEngine(clock=_make_clock([_T0, _T0]))
        desc, _ = engine.create_job(
            "A", "desc", JobPriority.NORMAL, deadline=_DEADLINE_PAST,
        )
        overdue = engine.find_overdue_jobs(_T0)
        assert desc.job_id in overdue

    def test_find_overdue_with_future_deadline(self):
        engine = JobEngine(clock=_make_clock([_T0, _T0]))
        desc, _ = engine.create_job(
            "A", "desc", JobPriority.NORMAL, deadline=_DEADLINE_FUTURE,
        )
        overdue = engine.find_overdue_jobs(_T0)
        assert desc.job_id not in overdue

    def test_find_overdue_no_deadline(self):
        engine = JobEngine(clock=_make_clock([_T0, _T0]))
        desc, _ = engine.create_job("A", "desc", JobPriority.NORMAL)
        overdue = engine.find_overdue_jobs(_T0)
        assert desc.job_id not in overdue

    def test_overdue_excludes_completed_jobs(self):
        engine = JobEngine(clock=_make_clock([_T0, _T0, _T1, _T2, _T3]))
        desc, _ = engine.create_job(
            "A", "desc", JobPriority.NORMAL, deadline=_DEADLINE_PAST,
        )
        engine.start_job(desc.job_id)
        engine.complete_job(desc.job_id, "done")
        overdue = engine.find_overdue_jobs(_T0)
        assert desc.job_id not in overdue


# ============================================================
# Stale job detection
# ============================================================


class TestStaleDetection:
    def test_find_stale_jobs(self):
        engine = JobEngine(clock=_make_clock([_T0, _T0]))
        desc, _ = engine.create_job("A", "desc", JobPriority.NORMAL)
        # 120 minutes later with 60 min threshold -> stale
        stale = engine.find_stale_jobs(60, _T0_PLUS_120M)
        assert desc.job_id in stale

    def test_find_stale_jobs_recently_updated(self):
        engine = JobEngine(clock=_make_clock([_T0, _T0]))
        desc, _ = engine.create_job("A", "desc", JobPriority.NORMAL)
        # 30 minutes later with 60 min threshold -> not stale
        stale = engine.find_stale_jobs(60, _T0_PLUS_30M)
        assert desc.job_id not in stale

    def test_stale_excludes_completed(self):
        engine = JobEngine(clock=_make_clock([_T0, _T0, _T1, _T2, _T3]))
        desc, _ = engine.create_job("A", "desc", JobPriority.NORMAL)
        engine.start_job(desc.job_id)
        engine.complete_job(desc.job_id, "done")
        stale = engine.find_stale_jobs(60, _T0_PLUS_120M)
        assert desc.job_id not in stale


# ============================================================
# Clock injection determinism
# ============================================================


class TestClockDeterminism:
    def test_same_clock_same_results(self):
        """Two engines with identical clocks produce identical job IDs."""
        clock1 = _make_clock([_T0, _T0])
        clock2 = _make_clock([_T0, _T0])
        engine1 = JobEngine(clock=clock1)
        engine2 = JobEngine(clock=clock2)
        desc1, state1 = engine1.create_job("X", "desc", JobPriority.HIGH)
        desc2, state2 = engine2.create_job("X", "desc", JobPriority.HIGH)
        assert desc1.job_id == desc2.job_id
        assert state1.updated_at == state2.updated_at

    def test_different_clocks_different_ids(self):
        """Different clock values produce different job IDs."""
        engine1 = JobEngine(clock=_make_clock([_T0, _T0]))
        engine2 = JobEngine(clock=_make_clock([_T1, _T1]))
        desc1, _ = engine1.create_job("X", "desc", JobPriority.HIGH)
        desc2, _ = engine2.create_job("X", "desc", JobPriority.HIGH)
        assert desc1.job_id != desc2.job_id

    def test_queue_determinism(self):
        """Queue entry IDs are deterministic given the same clock."""
        clock1 = _make_clock([_T0, _T0])
        clock2 = _make_clock([_T0, _T0])
        q1 = WorkQueue(clock=clock1)
        q2 = WorkQueue(clock=clock2)
        desc = JobDescriptor(
            job_id="j-1", name="A", description="d",
            priority=JobPriority.NORMAL, created_at=_T0,
        )
        e1 = q1.enqueue(desc)
        e2 = q2.enqueue(desc)
        assert e1.entry_id == e2.entry_id


# ============================================================
# Edge cases
# ============================================================


class TestEdgeCases:
    def test_nonexistent_job_raises(self):
        engine = JobEngine(clock=_fixed_clock())
        with pytest.raises(RuntimeCoreInvariantError, match="job not found") as excinfo:
            engine.start_job("nonexistent")
        assert str(excinfo.value) == "job not found"
        assert "nonexistent" not in str(excinfo.value)

    def test_empty_description_raises(self):
        engine = JobEngine(clock=_fixed_clock())
        with pytest.raises(RuntimeCoreInvariantError):
            engine.create_job("name", "", JobPriority.NORMAL)

    def test_cancel_empty_reason_raises(self):
        engine = JobEngine(clock=_make_clock([_T0, _T0, _T1]))
        desc, _ = engine.create_job("A", "desc", JobPriority.NORMAL)
        with pytest.raises(RuntimeCoreInvariantError):
            engine.cancel_job(desc.job_id, "")

    def test_resume_empty_fields_raises(self):
        engine = JobEngine(clock=_make_clock([_T0, _T0, _T1, _T2, _T3]))
        desc, _ = engine.create_job("A", "desc", JobPriority.NORMAL)
        engine.start_job(desc.job_id)
        engine.pause_job(desc.job_id, PauseReason.BLOCKED_DEPENDENCY)
        with pytest.raises(RuntimeCoreInvariantError):
            engine.resume_job(desc.job_id, "", "reason")

    def test_queue_list_entries_empty(self):
        q = WorkQueue(clock=_fixed_clock())
        assert q.list_entries() == ()

    def test_fail_from_waiting(self):
        """Can fail a job that is waiting."""
        engine = JobEngine(clock=_make_clock([_T0, _T0, _T1, _T2, _T3]))
        desc, _ = engine.create_job("A", "desc", JobPriority.NORMAL)
        engine.start_job(desc.job_id)
        # Manually set to waiting
        engine._states[desc.job_id] = JobState(
            job_id=desc.job_id,
            status=JobStatus.WAITING,
            sla_status=SlaStatus.NOT_APPLICABLE,
            updated_at=_T2,
        )
        state, record = engine.fail_job(desc.job_id, ("timeout",))
        assert state.status == JobStatus.FAILED

    def test_fail_from_paused(self):
        """Can fail a paused job."""
        engine = JobEngine(clock=_make_clock([_T0, _T0, _T1, _T2, _T3, _T4, _T5]))
        desc, _ = engine.create_job("A", "desc", JobPriority.NORMAL)
        engine.start_job(desc.job_id)
        engine.pause_job(desc.job_id, PauseReason.SYSTEM_ERROR)
        state, record = engine.fail_job(desc.job_id, ("unrecoverable",))
        assert state.status == JobStatus.FAILED
