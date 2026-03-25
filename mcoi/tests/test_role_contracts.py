"""Tests for team runtime role and worker contracts."""

import json

import pytest

from mcoi_runtime.contracts.roles import (
    AssignmentDecision,
    AssignmentPolicy,
    AssignmentStrategy,
    HandoffReason,
    HandoffRecord,
    RoleDescriptor,
    TeamQueueState,
    WorkerCapacity,
    WorkerProfile,
    WorkerStatus,
    WorkloadSnapshot,
)


TS = "2025-06-01T12:00:00+00:00"
TS2 = "2025-06-01T13:00:00+00:00"


# --- Helpers ---


def _role(**overrides):
    defaults = dict(
        role_id="role-001",
        name="Triage Agent",
        description="Handles initial triage of incoming jobs",
        required_skills=("triage", "classification"),
    )
    defaults.update(overrides)
    return RoleDescriptor(**defaults)


def _worker(**overrides):
    defaults = dict(
        worker_id="wkr-001",
        name="Agent Alpha",
        roles=("role-001",),
        max_concurrent_jobs=5,
        status=WorkerStatus.AVAILABLE,
    )
    defaults.update(overrides)
    return WorkerProfile(**defaults)


def _capacity(**overrides):
    defaults = dict(
        worker_id="wkr-001",
        max_concurrent=5,
        current_load=2,
        available_slots=3,
        updated_at=TS,
    )
    defaults.update(overrides)
    return WorkerCapacity(**defaults)


def _policy(**overrides):
    defaults = dict(
        policy_id="pol-001",
        role_id="role-001",
        strategy=AssignmentStrategy.LEAST_LOADED,
    )
    defaults.update(overrides)
    return AssignmentPolicy(**defaults)


def _decision(**overrides):
    defaults = dict(
        decision_id="dec-001",
        job_id="job-001",
        worker_id="wkr-001",
        role_id="role-001",
        reason="least loaded worker",
        decided_at=TS,
    )
    defaults.update(overrides)
    return AssignmentDecision(**defaults)


def _handoff(**overrides):
    defaults = dict(
        handoff_id="ho-001",
        job_id="job-001",
        from_worker_id="wkr-001",
        to_worker_id="wkr-002",
        reason=HandoffReason.CAPACITY_EXCEEDED,
        handoff_at=TS,
    )
    defaults.update(overrides)
    return HandoffRecord(**defaults)


def _snapshot(**overrides):
    cap = _capacity()
    defaults = dict(
        snapshot_id="snap-001",
        team_id="team-001",
        worker_capacities=(cap,),
        captured_at=TS,
    )
    defaults.update(overrides)
    return WorkloadSnapshot(**defaults)


def _queue_state(**overrides):
    defaults = dict(
        team_id="team-001",
        queued_jobs=3,
        assigned_jobs=5,
        waiting_jobs=1,
        overloaded_workers=0,
        captured_at=TS,
    )
    defaults.update(overrides)
    return TeamQueueState(**defaults)


# ========================================================================
# Enum tests
# ========================================================================


class TestWorkerStatusEnum:
    def test_all_values(self):
        assert set(WorkerStatus) == {
            WorkerStatus.AVAILABLE,
            WorkerStatus.BUSY,
            WorkerStatus.OVERLOADED,
            WorkerStatus.OFFLINE,
            WorkerStatus.ON_HOLD,
        }

    def test_string_values(self):
        assert WorkerStatus.AVAILABLE == "available"
        assert WorkerStatus.ON_HOLD == "on_hold"


class TestAssignmentStrategyEnum:
    def test_all_values(self):
        assert set(AssignmentStrategy) == {
            AssignmentStrategy.LEAST_LOADED,
            AssignmentStrategy.ROUND_ROBIN,
            AssignmentStrategy.EXPLICIT,
            AssignmentStrategy.ESCALATE,
        }

    def test_string_values(self):
        assert AssignmentStrategy.LEAST_LOADED == "least_loaded"
        assert AssignmentStrategy.ESCALATE == "escalate"


class TestHandoffReasonEnum:
    def test_all_values(self):
        assert set(HandoffReason) == {
            HandoffReason.CAPACITY_EXCEEDED,
            HandoffReason.ROLE_CHANGE,
            HandoffReason.ESCALATION,
            HandoffReason.OPERATOR_OVERRIDE,
            HandoffReason.SHIFT_CHANGE,
        }

    def test_string_values(self):
        assert HandoffReason.CAPACITY_EXCEEDED == "capacity_exceeded"
        assert HandoffReason.SHIFT_CHANGE == "shift_change"


# ========================================================================
# RoleDescriptor tests
# ========================================================================


class TestRoleDescriptor:
    def test_valid_construction(self):
        role = _role()
        assert role.role_id == "role-001"
        assert role.name == "Triage Agent"
        assert role.required_skills == ("triage", "classification")
        assert role.approval_required is False
        assert role.max_concurrent_per_worker == 5

    def test_empty_role_id_rejected(self):
        with pytest.raises(ValueError, match="role_id"):
            _role(role_id="")

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError, match="name"):
            _role(name="")

    def test_empty_description_rejected(self):
        with pytest.raises(ValueError, match="description"):
            _role(description="")

    def test_empty_required_skills_rejected(self):
        with pytest.raises(ValueError, match="required_skills"):
            _role(required_skills=())

    def test_blank_skill_rejected(self):
        with pytest.raises(ValueError, match="required_skills"):
            _role(required_skills=("triage", ""))

    def test_max_concurrent_per_worker_zero_rejected(self):
        with pytest.raises(ValueError, match="max_concurrent_per_worker"):
            _role(max_concurrent_per_worker=0)

    def test_max_concurrent_per_worker_negative_rejected(self):
        with pytest.raises(ValueError, match="max_concurrent_per_worker"):
            _role(max_concurrent_per_worker=-1)

    def test_frozen(self):
        role = _role()
        with pytest.raises(AttributeError):
            role.name = "changed"

    def test_to_dict(self):
        role = _role()
        d = role.to_dict()
        assert d["role_id"] == "role-001"
        assert d["required_skills"] == ["triage", "classification"]

    def test_to_json_roundtrip(self):
        role = _role()
        parsed = json.loads(role.to_json())
        assert parsed["role_id"] == "role-001"

    def test_metadata_frozen(self):
        role = _role(metadata={"key": "value"})
        with pytest.raises(TypeError):
            role.metadata["new_key"] = "fail"

    def test_approval_required_non_bool_rejected(self):
        with pytest.raises(ValueError, match="approval_required"):
            _role(approval_required="yes")


# ========================================================================
# WorkerProfile tests
# ========================================================================


class TestWorkerProfile:
    def test_valid_construction(self):
        w = _worker()
        assert w.worker_id == "wkr-001"
        assert w.name == "Agent Alpha"
        assert w.roles == ("role-001",)
        assert w.max_concurrent_jobs == 5
        assert w.status == WorkerStatus.AVAILABLE

    def test_empty_worker_id_rejected(self):
        with pytest.raises(ValueError, match="worker_id"):
            _worker(worker_id="")

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError, match="name"):
            _worker(name="")

    def test_empty_roles_rejected(self):
        with pytest.raises(ValueError, match="roles"):
            _worker(roles=())

    def test_blank_role_id_rejected(self):
        with pytest.raises(ValueError, match="roles"):
            _worker(roles=("role-001", ""))

    def test_max_concurrent_jobs_zero_rejected(self):
        with pytest.raises(ValueError, match="max_concurrent_jobs"):
            _worker(max_concurrent_jobs=0)

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError, match="status"):
            _worker(status="ready")

    def test_frozen(self):
        w = _worker()
        with pytest.raises(AttributeError):
            w.status = WorkerStatus.BUSY

    def test_to_dict(self):
        w = _worker()
        d = w.to_dict()
        assert d["worker_id"] == "wkr-001"
        assert d["roles"] == ["role-001"]

    def test_multiple_roles(self):
        w = _worker(roles=("role-001", "role-002"))
        assert w.roles == ("role-001", "role-002")


# ========================================================================
# WorkerCapacity tests
# ========================================================================


class TestWorkerCapacity:
    def test_valid_construction(self):
        cap = _capacity()
        assert cap.worker_id == "wkr-001"
        assert cap.max_concurrent == 5
        assert cap.current_load == 2
        assert cap.available_slots == 3

    def test_empty_worker_id_rejected(self):
        with pytest.raises(ValueError, match="worker_id"):
            _capacity(worker_id="")

    def test_max_concurrent_zero_rejected(self):
        with pytest.raises(ValueError, match="max_concurrent"):
            _capacity(max_concurrent=0, current_load=0, available_slots=0)

    def test_negative_current_load_rejected(self):
        with pytest.raises(ValueError, match="current_load"):
            _capacity(current_load=-1, available_slots=6)

    def test_negative_available_slots_rejected(self):
        with pytest.raises(ValueError, match="available_slots"):
            _capacity(available_slots=-1)

    def test_slots_mismatch_rejected(self):
        with pytest.raises(ValueError, match="available_slots must equal"):
            _capacity(max_concurrent=5, current_load=2, available_slots=10)

    def test_invalid_updated_at_rejected(self):
        with pytest.raises(ValueError, match="updated_at"):
            _capacity(updated_at="not-a-date")

    def test_frozen(self):
        cap = _capacity()
        with pytest.raises(AttributeError):
            cap.current_load = 3

    def test_to_json_roundtrip(self):
        cap = _capacity()
        parsed = json.loads(cap.to_json())
        assert parsed["available_slots"] == 3

    def test_full_load(self):
        cap = _capacity(max_concurrent=5, current_load=5, available_slots=0)
        assert cap.available_slots == 0

    def test_zero_load(self):
        cap = _capacity(max_concurrent=5, current_load=0, available_slots=5)
        assert cap.available_slots == 5


# ========================================================================
# AssignmentPolicy tests
# ========================================================================


class TestAssignmentPolicy:
    def test_valid_construction(self):
        pol = _policy()
        assert pol.policy_id == "pol-001"
        assert pol.strategy == AssignmentStrategy.LEAST_LOADED
        assert pol.fallback_team_id is None
        assert pol.escalation_chain_id is None

    def test_with_optional_fields(self):
        pol = _policy(fallback_team_id="team-fallback", escalation_chain_id="esc-001")
        assert pol.fallback_team_id == "team-fallback"
        assert pol.escalation_chain_id == "esc-001"

    def test_empty_policy_id_rejected(self):
        with pytest.raises(ValueError, match="policy_id"):
            _policy(policy_id="")

    def test_empty_role_id_rejected(self):
        with pytest.raises(ValueError, match="role_id"):
            _policy(role_id="")

    def test_invalid_strategy_rejected(self):
        with pytest.raises(ValueError, match="strategy"):
            _policy(strategy="random")

    def test_blank_fallback_team_id_rejected(self):
        with pytest.raises(ValueError, match="fallback_team_id"):
            _policy(fallback_team_id="  ")

    def test_blank_escalation_chain_id_rejected(self):
        with pytest.raises(ValueError, match="escalation_chain_id"):
            _policy(escalation_chain_id="")

    def test_frozen(self):
        pol = _policy()
        with pytest.raises(AttributeError):
            pol.strategy = AssignmentStrategy.ROUND_ROBIN


# ========================================================================
# AssignmentDecision tests
# ========================================================================


class TestAssignmentDecision:
    def test_valid_construction(self):
        dec = _decision()
        assert dec.decision_id == "dec-001"
        assert dec.job_id == "job-001"
        assert dec.worker_id == "wkr-001"
        assert dec.role_id == "role-001"

    def test_empty_decision_id_rejected(self):
        with pytest.raises(ValueError, match="decision_id"):
            _decision(decision_id="")

    def test_empty_job_id_rejected(self):
        with pytest.raises(ValueError, match="job_id"):
            _decision(job_id="")

    def test_empty_worker_id_rejected(self):
        with pytest.raises(ValueError, match="worker_id"):
            _decision(worker_id="")

    def test_empty_role_id_rejected(self):
        with pytest.raises(ValueError, match="role_id"):
            _decision(role_id="")

    def test_empty_reason_rejected(self):
        with pytest.raises(ValueError, match="reason"):
            _decision(reason="")

    def test_invalid_decided_at_rejected(self):
        with pytest.raises(ValueError, match="decided_at"):
            _decision(decided_at="bad-date")

    def test_frozen(self):
        dec = _decision()
        with pytest.raises(AttributeError):
            dec.reason = "changed"

    def test_to_dict(self):
        dec = _decision()
        d = dec.to_dict()
        assert d["decision_id"] == "dec-001"
        assert d["decided_at"] == TS


# ========================================================================
# HandoffRecord tests
# ========================================================================


class TestHandoffRecord:
    def test_valid_construction(self):
        ho = _handoff()
        assert ho.handoff_id == "ho-001"
        assert ho.from_worker_id == "wkr-001"
        assert ho.to_worker_id == "wkr-002"
        assert ho.reason == HandoffReason.CAPACITY_EXCEEDED
        assert ho.thread_id is None

    def test_with_thread_id(self):
        ho = _handoff(thread_id="thread-42")
        assert ho.thread_id == "thread-42"

    def test_empty_handoff_id_rejected(self):
        with pytest.raises(ValueError, match="handoff_id"):
            _handoff(handoff_id="")

    def test_empty_job_id_rejected(self):
        with pytest.raises(ValueError, match="job_id"):
            _handoff(job_id="")

    def test_empty_from_worker_rejected(self):
        with pytest.raises(ValueError, match="from_worker_id"):
            _handoff(from_worker_id="")

    def test_empty_to_worker_rejected(self):
        with pytest.raises(ValueError, match="to_worker_id"):
            _handoff(to_worker_id="")

    def test_invalid_reason_rejected(self):
        with pytest.raises(ValueError, match="reason"):
            _handoff(reason="bored")

    def test_blank_thread_id_rejected(self):
        with pytest.raises(ValueError, match="thread_id"):
            _handoff(thread_id="  ")

    def test_invalid_handoff_at_rejected(self):
        with pytest.raises(ValueError, match="handoff_at"):
            _handoff(handoff_at="not-a-time")

    def test_frozen(self):
        ho = _handoff()
        with pytest.raises(AttributeError):
            ho.reason = HandoffReason.ESCALATION

    def test_all_handoff_reasons(self):
        for reason in HandoffReason:
            ho = _handoff(reason=reason)
            assert ho.reason == reason

    def test_to_json_roundtrip(self):
        ho = _handoff(thread_id="thread-99")
        parsed = json.loads(ho.to_json())
        assert parsed["thread_id"] == "thread-99"
        assert parsed["reason"] == "capacity_exceeded"


# ========================================================================
# WorkloadSnapshot tests
# ========================================================================


class TestWorkloadSnapshot:
    def test_valid_construction(self):
        snap = _snapshot()
        assert snap.snapshot_id == "snap-001"
        assert snap.team_id == "team-001"
        assert len(snap.worker_capacities) == 1

    def test_empty_snapshot_id_rejected(self):
        with pytest.raises(ValueError, match="snapshot_id"):
            _snapshot(snapshot_id="")

    def test_empty_team_id_rejected(self):
        with pytest.raises(ValueError, match="team_id"):
            _snapshot(team_id="")

    def test_empty_capacities_rejected(self):
        with pytest.raises(ValueError, match="worker_capacities"):
            _snapshot(worker_capacities=())

    def test_non_capacity_entry_rejected(self):
        with pytest.raises(ValueError, match="WorkerCapacity"):
            _snapshot(worker_capacities=("not-a-capacity",))

    def test_invalid_captured_at_rejected(self):
        with pytest.raises(ValueError, match="captured_at"):
            _snapshot(captured_at="nope")

    def test_frozen(self):
        snap = _snapshot()
        with pytest.raises(AttributeError):
            snap.team_id = "other"

    def test_multiple_workers(self):
        c1 = _capacity(worker_id="wkr-001")
        c2 = _capacity(worker_id="wkr-002", max_concurrent=3, current_load=1, available_slots=2)
        snap = _snapshot(worker_capacities=(c1, c2))
        assert len(snap.worker_capacities) == 2


# ========================================================================
# TeamQueueState tests
# ========================================================================


class TestTeamQueueState:
    def test_valid_construction(self):
        qs = _queue_state()
        assert qs.team_id == "team-001"
        assert qs.queued_jobs == 3
        assert qs.assigned_jobs == 5
        assert qs.waiting_jobs == 1
        assert qs.overloaded_workers == 0

    def test_empty_team_id_rejected(self):
        with pytest.raises(ValueError, match="team_id"):
            _queue_state(team_id="")

    def test_negative_queued_jobs_rejected(self):
        with pytest.raises(ValueError, match="queued_jobs"):
            _queue_state(queued_jobs=-1)

    def test_negative_assigned_jobs_rejected(self):
        with pytest.raises(ValueError, match="assigned_jobs"):
            _queue_state(assigned_jobs=-1)

    def test_negative_waiting_jobs_rejected(self):
        with pytest.raises(ValueError, match="waiting_jobs"):
            _queue_state(waiting_jobs=-1)

    def test_negative_overloaded_workers_rejected(self):
        with pytest.raises(ValueError, match="overloaded_workers"):
            _queue_state(overloaded_workers=-1)

    def test_invalid_captured_at_rejected(self):
        with pytest.raises(ValueError, match="captured_at"):
            _queue_state(captured_at="nah")

    def test_frozen(self):
        qs = _queue_state()
        with pytest.raises(AttributeError):
            qs.queued_jobs = 99

    def test_zero_counts_valid(self):
        qs = _queue_state(queued_jobs=0, assigned_jobs=0, waiting_jobs=0, overloaded_workers=0)
        assert qs.queued_jobs == 0

    def test_to_dict(self):
        qs = _queue_state()
        d = qs.to_dict()
        assert d["queued_jobs"] == 3
        assert d["captured_at"] == TS

    def test_to_json_roundtrip(self):
        qs = _queue_state()
        parsed = json.loads(qs.to_json())
        assert parsed["assigned_jobs"] == 5
