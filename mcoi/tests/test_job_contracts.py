"""Tests for job ownership runtime contracts."""

import pytest

from mcoi_runtime.contracts.job import (
    AssignmentRecord,
    DeadlineRecord,
    FollowUpRecord,
    JOB_PRIORITY_RANK,
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


TS = "2025-06-01T12:00:00+00:00"
TS2 = "2025-06-01T13:00:00+00:00"


# --- Helpers ---


def _descriptor(**overrides):
    defaults = dict(
        job_id="job-001",
        name="test job",
        description="a test job",
        priority=JobPriority.NORMAL,
        created_at=TS,
    )
    defaults.update(overrides)
    return JobDescriptor(**defaults)


def _queue_entry(**overrides):
    defaults = dict(
        entry_id="qe-001",
        job_id="job-001",
        priority=JobPriority.NORMAL,
        enqueued_at=TS,
    )
    defaults.update(overrides)
    return WorkQueueEntry(**defaults)


def _assignment(**overrides):
    defaults = dict(
        assignment_id="asgn-001",
        job_id="job-001",
        assigned_to_id="agent-001",
        assigned_by_id="operator-001",
        assigned_at=TS,
        reason="initial assignment",
    )
    defaults.update(overrides)
    return AssignmentRecord(**defaults)


def _state(**overrides):
    defaults = dict(
        job_id="job-001",
        status=JobStatus.CREATED,
        sla_status=SlaStatus.NOT_APPLICABLE,
    )
    defaults.update(overrides)
    return JobState(**defaults)


def _follow_up(**overrides):
    defaults = dict(
        follow_up_id="fu-001",
        job_id="job-001",
        reason="stalled too long",
        scheduled_at=TS,
    )
    defaults.update(overrides)
    return FollowUpRecord(**defaults)


def _deadline(**overrides):
    defaults = dict(
        job_id="job-001",
        deadline=TS,
        sla_status=SlaStatus.ON_TRACK,
        evaluated_at=TS,
    )
    defaults.update(overrides)
    return DeadlineRecord(**defaults)


def _execution(**overrides):
    defaults = dict(
        job_id="job-001",
        execution_id="exec-001",
        status=JobStatus.COMPLETED,
        started_at=TS,
        outcome_summary="completed successfully",
    )
    defaults.update(overrides)
    return JobExecutionRecord(**defaults)


def _pause(**overrides):
    defaults = dict(
        job_id="job-001",
        paused_at=TS,
        reason=PauseReason.AWAITING_APPROVAL,
    )
    defaults.update(overrides)
    return JobPauseRecord(**defaults)


def _resume(**overrides):
    defaults = dict(
        job_id="job-001",
        resumed_at=TS,
        resumed_by_id="operator-001",
        reason="approval granted",
    )
    defaults.update(overrides)
    return JobResumeRecord(**defaults)


# --- Enum tests ---


class TestJobStatus:
    def test_all_values(self):
        expected = {
            "created", "queued", "assigned", "in_progress", "waiting",
            "paused", "completed", "failed", "cancelled", "archived",
        }
        assert {s.value for s in JobStatus} == expected

    def test_string_identity(self):
        assert JobStatus.CREATED == "created"
        assert JobStatus.ARCHIVED == "archived"


class TestJobPriority:
    def test_all_values(self):
        expected = {"critical", "high", "normal", "low", "background"}
        assert {p.value for p in JobPriority} == expected

    def test_rank_ordering(self):
        assert JOB_PRIORITY_RANK[JobPriority.CRITICAL] < JOB_PRIORITY_RANK[JobPriority.HIGH]
        assert JOB_PRIORITY_RANK[JobPriority.HIGH] < JOB_PRIORITY_RANK[JobPriority.NORMAL]
        assert JOB_PRIORITY_RANK[JobPriority.NORMAL] < JOB_PRIORITY_RANK[JobPriority.LOW]
        assert JOB_PRIORITY_RANK[JobPriority.LOW] < JOB_PRIORITY_RANK[JobPriority.BACKGROUND]


class TestPauseReason:
    def test_all_values(self):
        expected = {
            "awaiting_approval", "awaiting_response", "awaiting_review",
            "blocked_dependency", "operator_hold", "system_error",
        }
        assert {r.value for r in PauseReason} == expected


class TestSlaStatus:
    def test_all_values(self):
        expected = {"on_track", "at_risk", "breached", "not_applicable"}
        assert {s.value for s in SlaStatus} == expected


# --- JobDescriptor tests ---


class TestJobDescriptor:
    def test_valid_minimal(self):
        d = _descriptor()
        assert d.job_id == "job-001"
        assert d.name == "test job"
        assert d.priority is JobPriority.NORMAL
        assert d.goal_id is None
        assert d.workflow_id is None
        assert d.deadline is None
        assert d.sla_target_minutes is None

    def test_valid_full(self):
        d = _descriptor(
            goal_id="goal-001",
            workflow_id="wf-001",
            deadline=TS2,
            sla_target_minutes=60,
            metadata={"key": "value"},
        )
        assert d.goal_id == "goal-001"
        assert d.workflow_id == "wf-001"
        assert d.deadline == TS2
        assert d.sla_target_minutes == 60
        assert d.metadata["key"] == "value"

    def test_empty_job_id_rejected(self):
        with pytest.raises(ValueError, match="job_id"):
            _descriptor(job_id="")

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError, match="name"):
            _descriptor(name="")

    def test_empty_description_rejected(self):
        with pytest.raises(ValueError, match="description"):
            _descriptor(description="")

    def test_invalid_priority_rejected(self):
        with pytest.raises(ValueError, match="priority"):
            _descriptor(priority="invalid")

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _descriptor(created_at="not-a-date")

    def test_invalid_deadline_rejected(self):
        with pytest.raises(ValueError, match="deadline"):
            _descriptor(deadline="not-a-date")

    def test_sla_zero_rejected(self):
        with pytest.raises(ValueError, match="sla_target_minutes"):
            _descriptor(sla_target_minutes=0)

    def test_sla_negative_rejected(self):
        with pytest.raises(ValueError, match="sla_target_minutes"):
            _descriptor(sla_target_minutes=-1)

    def test_empty_goal_id_rejected(self):
        with pytest.raises(ValueError, match="goal_id"):
            _descriptor(goal_id="")

    def test_empty_workflow_id_rejected(self):
        with pytest.raises(ValueError, match="workflow_id"):
            _descriptor(workflow_id="")

    def test_frozen(self):
        d = _descriptor()
        with pytest.raises(AttributeError):
            d.name = "changed"

    def test_serialization_roundtrip(self):
        d = _descriptor(metadata={"k": "v"})
        data = d.to_dict()
        assert data["job_id"] == "job-001"
        assert data["metadata"] == {"k": "v"}
        assert isinstance(d.to_json(), str)


# --- WorkQueueEntry tests ---


class TestWorkQueueEntry:
    def test_valid_minimal(self):
        e = _queue_entry()
        assert e.entry_id == "qe-001"
        assert e.assigned_to_person_id is None
        assert e.assigned_to_team_id is None

    def test_valid_with_assignments(self):
        e = _queue_entry(assigned_to_person_id="person-1", assigned_to_team_id="team-1")
        assert e.assigned_to_person_id == "person-1"
        assert e.assigned_to_team_id == "team-1"

    def test_empty_entry_id_rejected(self):
        with pytest.raises(ValueError, match="entry_id"):
            _queue_entry(entry_id="")

    def test_invalid_priority_rejected(self):
        with pytest.raises(ValueError, match="priority"):
            _queue_entry(priority="invalid")

    def test_empty_person_id_rejected(self):
        with pytest.raises(ValueError, match="assigned_to_person_id"):
            _queue_entry(assigned_to_person_id="")

    def test_empty_team_id_rejected(self):
        with pytest.raises(ValueError, match="assigned_to_team_id"):
            _queue_entry(assigned_to_team_id="")

    def test_frozen(self):
        e = _queue_entry()
        with pytest.raises(AttributeError):
            e.entry_id = "changed"


# --- AssignmentRecord tests ---


class TestAssignmentRecord:
    def test_valid(self):
        a = _assignment()
        assert a.assignment_id == "asgn-001"
        assert a.reason == "initial assignment"

    def test_empty_assignment_id_rejected(self):
        with pytest.raises(ValueError, match="assignment_id"):
            _assignment(assignment_id="")

    def test_empty_assigned_to_id_rejected(self):
        with pytest.raises(ValueError, match="assigned_to_id"):
            _assignment(assigned_to_id="")

    def test_empty_assigned_by_id_rejected(self):
        with pytest.raises(ValueError, match="assigned_by_id"):
            _assignment(assigned_by_id="")

    def test_empty_reason_rejected(self):
        with pytest.raises(ValueError, match="reason"):
            _assignment(reason="")

    def test_invalid_assigned_at_rejected(self):
        with pytest.raises(ValueError, match="assigned_at"):
            _assignment(assigned_at="bad")

    def test_frozen(self):
        a = _assignment()
        with pytest.raises(AttributeError):
            a.reason = "changed"

    def test_serialization(self):
        a = _assignment()
        data = a.to_dict()
        assert data["assigned_to_id"] == "agent-001"


# --- JobState tests ---


class TestJobState:
    def test_valid_minimal(self):
        s = _state()
        assert s.status is JobStatus.CREATED
        assert s.sla_status is SlaStatus.NOT_APPLICABLE
        assert s.current_assignment_id is None
        assert s.pause_reason is None

    def test_valid_full(self):
        s = _state(
            status=JobStatus.PAUSED,
            sla_status=SlaStatus.AT_RISK,
            current_assignment_id="asgn-001",
            pause_reason=PauseReason.AWAITING_APPROVAL,
            thread_id="thread-001",
            goal_id="goal-001",
            workflow_id="wf-001",
            started_at=TS,
            updated_at=TS2,
        )
        assert s.pause_reason is PauseReason.AWAITING_APPROVAL
        assert s.thread_id == "thread-001"

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError, match="status"):
            _state(status="invalid")

    def test_invalid_sla_status_rejected(self):
        with pytest.raises(ValueError, match="sla_status"):
            _state(sla_status="invalid")

    def test_invalid_pause_reason_rejected(self):
        with pytest.raises(ValueError, match="pause_reason"):
            _state(pause_reason="invalid")

    def test_empty_thread_id_rejected(self):
        with pytest.raises(ValueError, match="thread_id"):
            _state(thread_id="")

    def test_invalid_started_at_rejected(self):
        with pytest.raises(ValueError, match="started_at"):
            _state(started_at="bad")

    def test_invalid_updated_at_rejected(self):
        with pytest.raises(ValueError, match="updated_at"):
            _state(updated_at="bad")

    def test_frozen(self):
        s = _state()
        with pytest.raises(AttributeError):
            s.status = JobStatus.QUEUED


# --- FollowUpRecord tests ---


class TestFollowUpRecord:
    def test_valid_minimal(self):
        f = _follow_up()
        assert f.resolved is False
        assert f.executed_at is None

    def test_valid_with_execution(self):
        f = _follow_up(resolved=True, executed_at=TS2)
        assert f.resolved is True
        assert f.executed_at == TS2

    def test_empty_follow_up_id_rejected(self):
        with pytest.raises(ValueError, match="follow_up_id"):
            _follow_up(follow_up_id="")

    def test_empty_reason_rejected(self):
        with pytest.raises(ValueError, match="reason"):
            _follow_up(reason="")

    def test_invalid_scheduled_at_rejected(self):
        with pytest.raises(ValueError, match="scheduled_at"):
            _follow_up(scheduled_at="bad")

    def test_invalid_executed_at_rejected(self):
        with pytest.raises(ValueError, match="executed_at"):
            _follow_up(executed_at="bad")

    def test_frozen(self):
        f = _follow_up()
        with pytest.raises(AttributeError):
            f.resolved = True


# --- DeadlineRecord tests ---


class TestDeadlineRecord:
    def test_valid_minimal(self):
        d = _deadline()
        assert d.sla_target_minutes is None

    def test_valid_with_sla(self):
        d = _deadline(sla_target_minutes=120)
        assert d.sla_target_minutes == 120

    def test_empty_job_id_rejected(self):
        with pytest.raises(ValueError, match="job_id"):
            _deadline(job_id="")

    def test_invalid_deadline_rejected(self):
        with pytest.raises(ValueError, match="deadline"):
            _deadline(deadline="bad")

    def test_invalid_sla_status_rejected(self):
        with pytest.raises(ValueError, match="sla_status"):
            _deadline(sla_status="invalid")

    def test_sla_zero_rejected(self):
        with pytest.raises(ValueError, match="sla_target_minutes"):
            _deadline(sla_target_minutes=0)

    def test_frozen(self):
        d = _deadline()
        with pytest.raises(AttributeError):
            d.sla_status = SlaStatus.BREACHED


# --- JobExecutionRecord tests ---


class TestJobExecutionRecord:
    def test_valid_minimal(self):
        e = _execution()
        assert e.errors == ()
        assert e.completed_at is None

    def test_valid_with_errors(self):
        e = _execution(
            status=JobStatus.FAILED,
            errors=("timeout", "retry exhausted"),
            completed_at=TS2,
        )
        assert e.errors == ("timeout", "retry exhausted")
        assert e.completed_at == TS2

    def test_empty_execution_id_rejected(self):
        with pytest.raises(ValueError, match="execution_id"):
            _execution(execution_id="")

    def test_empty_outcome_summary_rejected(self):
        with pytest.raises(ValueError, match="outcome_summary"):
            _execution(outcome_summary="")

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError, match="status"):
            _execution(status="invalid")

    def test_empty_error_string_rejected(self):
        with pytest.raises(ValueError, match="errors"):
            _execution(errors=("",))

    def test_invalid_completed_at_rejected(self):
        with pytest.raises(ValueError, match="completed_at"):
            _execution(completed_at="bad")

    def test_frozen(self):
        e = _execution()
        with pytest.raises(AttributeError):
            e.status = JobStatus.FAILED

    def test_errors_frozen_from_list(self):
        e = _execution(errors=["err1", "err2"])
        assert isinstance(e.errors, tuple)


# --- JobPauseRecord tests ---


class TestJobPauseRecord:
    def test_valid_minimal(self):
        p = _pause()
        assert p.resumed_at is None

    def test_valid_with_resume(self):
        p = _pause(resumed_at=TS2)
        assert p.resumed_at == TS2

    def test_empty_job_id_rejected(self):
        with pytest.raises(ValueError, match="job_id"):
            _pause(job_id="")

    def test_invalid_paused_at_rejected(self):
        with pytest.raises(ValueError, match="paused_at"):
            _pause(paused_at="bad")

    def test_invalid_reason_rejected(self):
        with pytest.raises(ValueError, match="reason"):
            _pause(reason="invalid")

    def test_invalid_resumed_at_rejected(self):
        with pytest.raises(ValueError, match="resumed_at"):
            _pause(resumed_at="bad")

    def test_frozen(self):
        p = _pause()
        with pytest.raises(AttributeError):
            p.reason = PauseReason.OPERATOR_HOLD


# --- JobResumeRecord tests ---


class TestJobResumeRecord:
    def test_valid(self):
        r = _resume()
        assert r.resumed_by_id == "operator-001"

    def test_empty_job_id_rejected(self):
        with pytest.raises(ValueError, match="job_id"):
            _resume(job_id="")

    def test_invalid_resumed_at_rejected(self):
        with pytest.raises(ValueError, match="resumed_at"):
            _resume(resumed_at="bad")

    def test_empty_resumed_by_id_rejected(self):
        with pytest.raises(ValueError, match="resumed_by_id"):
            _resume(resumed_by_id="")

    def test_empty_reason_rejected(self):
        with pytest.raises(ValueError, match="reason"):
            _resume(reason="")

    def test_frozen(self):
        r = _resume()
        with pytest.raises(AttributeError):
            r.reason = "changed"

    def test_serialization(self):
        r = _resume()
        data = r.to_dict()
        assert data["resumed_by_id"] == "operator-001"
        assert isinstance(r.to_json(), str)
