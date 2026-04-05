"""Tests for the team runtime core engine — WorkerRegistry and TeamEngine."""

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
from mcoi_runtime.core.team_runtime import TeamEngine, WorkerRegistry
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# --- Helpers ---

_T0 = "2025-06-01T12:00:00+00:00"
_T1 = "2025-06-01T12:00:01+00:00"
_T2 = "2025-06-01T12:00:02+00:00"
_T3 = "2025-06-01T12:00:03+00:00"
_T4 = "2025-06-01T12:00:04+00:00"
_T5 = "2025-06-01T12:00:05+00:00"


def _make_clock(times: list[str]):
    """Return a clock function that yields successive timestamps."""
    it = iter(times)

    def clock() -> str:
        return next(it)

    return clock


def _fixed_clock(t: str = _T0):
    """Return a clock that always returns the same time."""
    return lambda: t


def _make_worker(
    worker_id: str = "w-1",
    name: str = "Worker One",
    roles: tuple[str, ...] = ("role-dev",),
    max_concurrent_jobs: int = 3,
    status: WorkerStatus = WorkerStatus.AVAILABLE,
) -> WorkerProfile:
    return WorkerProfile(
        worker_id=worker_id,
        name=name,
        roles=roles,
        max_concurrent_jobs=max_concurrent_jobs,
        status=status,
    )


def _make_role(
    role_id: str = "role-dev",
    name: str = "Developer",
    description: str = "Handles development tasks",
    required_skills: tuple[str, ...] = ("python",),
) -> RoleDescriptor:
    return RoleDescriptor(
        role_id=role_id,
        name=name,
        description=description,
        required_skills=required_skills,
    )


def _make_policy(
    policy_id: str = "policy-default",
    role_id: str = "role-dev",
    strategy: AssignmentStrategy = AssignmentStrategy.LEAST_LOADED,
) -> AssignmentPolicy:
    return AssignmentPolicy(
        policy_id=policy_id,
        role_id=role_id,
        strategy=strategy,
    )


# ============================================================
# WorkerRegistry — Worker registration and lookup
# ============================================================


class TestWorkerRegistration:
    def test_register_worker_returns_profile(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        w = _make_worker()
        result = reg.register_worker(w)
        assert result is w
        assert result.worker_id == "w-1"

    def test_register_duplicate_worker_raises(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        reg.register_worker(_make_worker(worker_id="w-1"))
        with pytest.raises(RuntimeCoreInvariantError, match="worker already registered"):
            reg.register_worker(_make_worker(worker_id="w-1", name="Duplicate"))

    def test_get_worker_returns_profile(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        reg.register_worker(_make_worker(worker_id="w-1"))
        result = reg.get_worker("w-1")
        assert result is not None
        assert result.worker_id == "w-1"

    def test_get_worker_unknown_returns_none(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        assert reg.get_worker("nonexistent") is None

    def test_register_worker_initializes_capacity(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        reg.register_worker(_make_worker(worker_id="w-1", max_concurrent_jobs=5))
        cap = reg.get_internal_capacity("w-1")
        assert cap is not None
        assert cap.max_concurrent == 5
        assert cap.current_load == 0
        assert cap.available_slots == 5


# ============================================================
# WorkerRegistry — Role registration
# ============================================================


class TestRoleRegistration:
    def test_register_role_returns_descriptor(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        r = _make_role()
        result = reg.register_role(r)
        assert result is r
        assert result.role_id == "role-dev"

    def test_register_duplicate_role_raises(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        reg.register_role(_make_role(role_id="role-dev"))
        with pytest.raises(RuntimeCoreInvariantError, match="role already registered"):
            reg.register_role(_make_role(role_id="role-dev", name="Duplicate Dev"))

    def test_get_role_returns_descriptor(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        reg.register_role(_make_role(role_id="role-dev"))
        result = reg.get_role("role-dev")
        assert result is not None
        assert result.role_id == "role-dev"

    def test_get_role_unknown_returns_none(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        assert reg.get_role("nonexistent") is None


# ============================================================
# WorkerRegistry — Policy registration
# ============================================================


class TestPolicyRegistration:
    def test_register_policy_returns_policy(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        p = _make_policy()
        result = reg.register_policy(p)
        assert result is p
        assert result.policy_id == "policy-default"

    def test_register_duplicate_policy_raises(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        reg.register_policy(_make_policy(policy_id="p-1"))
        with pytest.raises(RuntimeCoreInvariantError, match="policy already registered"):
            reg.register_policy(_make_policy(policy_id="p-1"))

    def test_get_policy_returns_policy(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        p = _make_policy(policy_id="p-1")
        reg.register_policy(p)
        result = reg.get_policy("p-1")
        assert result is not None
        assert result.policy_id == "p-1"

    def test_get_policy_unknown_returns_none(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        assert reg.get_policy("nonexistent") is None


# ============================================================
# WorkerRegistry — Workers for role
# ============================================================


class TestWorkersForRole:
    def test_get_workers_for_role_filters_correctly(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        reg.register_worker(_make_worker(worker_id="w-1", roles=("role-dev",)))
        reg.register_worker(_make_worker(worker_id="w-2", name="W2", roles=("role-qa",)))
        reg.register_worker(_make_worker(worker_id="w-3", name="W3", roles=("role-dev", "role-qa")))
        devs = reg.get_workers_for_role("role-dev")
        dev_ids = [w.worker_id for w in devs]
        assert "w-1" in dev_ids
        assert "w-3" in dev_ids
        assert "w-2" not in dev_ids

    def test_get_workers_for_role_empty(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        assert reg.get_workers_for_role("role-dev") == ()


# ============================================================
# WorkerRegistry — Capacity update
# ============================================================


class TestCapacityUpdate:
    def test_update_capacity_recalculates_slots(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        reg.register_worker(_make_worker(worker_id="w-1", max_concurrent_jobs=5))
        cap = reg.update_capacity("w-1", current_load=3)
        assert isinstance(cap, WorkerCapacity)
        assert cap.current_load == 3
        assert cap.available_slots == 2
        assert cap.max_concurrent == 5

    def test_update_capacity_overload_clamps_in_contract(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        reg.register_worker(_make_worker(worker_id="w-1", max_concurrent_jobs=2))
        cap = reg.update_capacity("w-1", current_load=5)
        # Contract record clamps to max; internal tracks real load
        assert cap.current_load == 2
        assert cap.available_slots == 0
        # Internal still knows the real load
        internal = reg.get_internal_capacity("w-1")
        assert internal is not None
        assert internal.current_load == 5

    def test_update_capacity_unknown_worker_raises(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        with pytest.raises(RuntimeCoreInvariantError, match="worker not found"):
            reg.update_capacity("nonexistent", current_load=1)

    def test_update_capacity_uses_clock(self):
        clock = _make_clock([_T3])
        reg = WorkerRegistry(clock=clock)
        reg.register_worker(_make_worker(worker_id="w-1"))
        cap = reg.update_capacity("w-1", current_load=1)
        assert cap.updated_at == _T3


# ============================================================
# TeamEngine — Assignment: least_loaded picks correct worker
# ============================================================


class TestAssignment:
    def _setup_engine(self, clock=None):
        if clock is None:
            clock = _fixed_clock()
        reg = WorkerRegistry(clock=clock)
        reg.register_worker(_make_worker(worker_id="w-1", max_concurrent_jobs=3))
        reg.register_worker(_make_worker(worker_id="w-2", name="W2", max_concurrent_jobs=3))
        reg.register_worker(_make_worker(worker_id="w-3", name="W3", max_concurrent_jobs=3))
        engine = TeamEngine(registry=reg, clock=clock)
        return reg, engine

    def test_assign_picks_least_loaded(self):
        clock = _fixed_clock()
        reg, engine = self._setup_engine(clock=clock)
        # w-1: load 2, w-2: load 0, w-3: load 1
        reg.update_capacity("w-1", current_load=2)
        reg.update_capacity("w-2", current_load=0)
        reg.update_capacity("w-3", current_load=1)
        decision = engine.assign_job("job-1", "role-dev")
        assert isinstance(decision, AssignmentDecision)
        assert decision.worker_id == "w-2"

    def test_assign_all_at_capacity_returns_none(self):
        clock = _fixed_clock()
        reg, engine = self._setup_engine(clock=clock)
        reg.update_capacity("w-1", current_load=3)
        reg.update_capacity("w-2", current_load=3)
        reg.update_capacity("w-3", current_load=3)
        decision = engine.assign_job("job-1", "role-dev")
        assert decision is None

    def test_assign_no_workers_for_role_returns_none(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        engine = TeamEngine(registry=reg, clock=_fixed_clock())
        decision = engine.assign_job("job-1", "role-unknown")
        assert decision is None

    def test_assign_skips_non_available_workers(self):
        clock = _fixed_clock()
        reg = WorkerRegistry(clock=clock)
        reg.register_worker(_make_worker(
            worker_id="w-active", status=WorkerStatus.AVAILABLE, max_concurrent_jobs=3,
        ))
        reg.register_worker(_make_worker(
            worker_id="w-offline", name="Offline", status=WorkerStatus.OFFLINE,
            max_concurrent_jobs=3,
        ))
        engine = TeamEngine(registry=reg, clock=clock)
        decision = engine.assign_job("job-1", "role-dev")
        assert decision is not None
        assert decision.worker_id == "w-active"

    def test_assign_empty_job_id_raises(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        engine = TeamEngine(registry=reg, clock=_fixed_clock())
        with pytest.raises(RuntimeCoreInvariantError, match="job_id"):
            engine.assign_job("", "role-dev")

    def test_assign_empty_role_id_raises(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        engine = TeamEngine(registry=reg, clock=_fixed_clock())
        with pytest.raises(RuntimeCoreInvariantError, match="role_id"):
            engine.assign_job("job-1", "")

    def test_assign_includes_role_id_in_decision(self):
        clock = _fixed_clock()
        reg = WorkerRegistry(clock=clock)
        reg.register_worker(_make_worker(worker_id="w-1"))
        engine = TeamEngine(registry=reg, clock=clock)
        decision = engine.assign_job("job-1", "role-dev")
        assert decision is not None
        assert decision.role_id == "role-dev"
        assert decision.job_id == "job-1"


# ============================================================
# TeamEngine — Handoff
# ============================================================


class TestHandoff:
    def test_handoff_creates_record(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        engine = TeamEngine(registry=reg, clock=_fixed_clock())
        record = engine.handoff_job(
            "job-1", "w-1", "w-2", HandoffReason.CAPACITY_EXCEEDED,
        )
        assert isinstance(record, HandoffRecord)
        assert record.job_id == "job-1"
        assert record.from_worker_id == "w-1"
        assert record.to_worker_id == "w-2"
        assert record.reason == HandoffReason.CAPACITY_EXCEEDED
        assert record.thread_id is None
        assert record.handoff_at == _T0

    def test_handoff_with_thread_id(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        engine = TeamEngine(registry=reg, clock=_fixed_clock())
        record = engine.handoff_job(
            "job-1", "w-1", "w-2", HandoffReason.ROLE_CHANGE,
            thread_id="thread-42",
        )
        assert record.thread_id == "thread-42"

    def test_handoff_uses_clock(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        clock = _make_clock([_T3])
        engine = TeamEngine(registry=reg, clock=clock)
        record = engine.handoff_job(
            "job-1", "w-1", "w-2", HandoffReason.ESCALATION,
        )
        assert record.handoff_at == _T3

    def test_handoff_empty_job_id_raises(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        engine = TeamEngine(registry=reg, clock=_fixed_clock())
        with pytest.raises(RuntimeCoreInvariantError, match="job_id"):
            engine.handoff_job("", "w-1", "w-2", HandoffReason.CAPACITY_EXCEEDED)

    def test_handoff_empty_from_worker_raises(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        engine = TeamEngine(registry=reg, clock=_fixed_clock())
        with pytest.raises(RuntimeCoreInvariantError, match="from_worker_id"):
            engine.handoff_job("job-1", "", "w-2", HandoffReason.CAPACITY_EXCEEDED)

    def test_handoff_empty_to_worker_raises(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        engine = TeamEngine(registry=reg, clock=_fixed_clock())
        with pytest.raises(RuntimeCoreInvariantError, match="to_worker_id"):
            engine.handoff_job("job-1", "w-1", "", HandoffReason.CAPACITY_EXCEEDED)

    def test_handoff_id_is_deterministic(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        e1 = TeamEngine(registry=reg, clock=_fixed_clock(_T0))
        e2 = TeamEngine(registry=reg, clock=_fixed_clock(_T0))
        r1 = e1.handoff_job("job-1", "w-1", "w-2", HandoffReason.CAPACITY_EXCEEDED)
        r2 = e2.handoff_job("job-1", "w-1", "w-2", HandoffReason.CAPACITY_EXCEEDED)
        assert r1.handoff_id == r2.handoff_id


# ============================================================
# TeamEngine — Workload snapshot
# ============================================================


class TestWorkloadSnapshot:
    def test_capture_workload_returns_snapshot(self):
        clock = _fixed_clock()
        reg = WorkerRegistry(clock=clock)
        reg.register_worker(_make_worker(worker_id="w-1", max_concurrent_jobs=5))
        reg.register_worker(_make_worker(worker_id="w-2", name="W2", max_concurrent_jobs=3))
        reg.update_capacity("w-1", current_load=2)
        reg.update_capacity("w-2", current_load=1)
        engine = TeamEngine(registry=reg, clock=clock)
        snap = engine.capture_workload("team-alpha")
        assert isinstance(snap, WorkloadSnapshot)
        assert snap.team_id == "team-alpha"
        assert len(snap.worker_capacities) == 2
        assert snap.captured_at == _T0

    def test_capture_workload_empty_returns_none(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        engine = TeamEngine(registry=reg, clock=_fixed_clock())
        snap = engine.capture_workload("team-empty")
        assert snap is None

    def test_capture_workload_empty_team_id_raises(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        engine = TeamEngine(registry=reg, clock=_fixed_clock())
        with pytest.raises(RuntimeCoreInvariantError, match="team_id"):
            engine.capture_workload("")

    def test_capture_workload_capacities_match_workers(self):
        clock = _fixed_clock()
        reg = WorkerRegistry(clock=clock)
        reg.register_worker(_make_worker(worker_id="w-1", max_concurrent_jobs=4))
        reg.update_capacity("w-1", current_load=2)
        engine = TeamEngine(registry=reg, clock=clock)
        snap = engine.capture_workload("team-1")
        assert snap is not None
        cap = snap.worker_capacities[0]
        assert cap.worker_id == "w-1"
        assert cap.current_load == 2
        assert cap.available_slots == 2


# ============================================================
# TeamEngine — Queue state capture
# ============================================================


class TestQueueStateCapture:
    def test_capture_queue_state_returns_state(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        engine = TeamEngine(registry=reg, clock=_fixed_clock())
        state = engine.capture_queue_state("team-alpha", queued=5, assigned=3, waiting=2)
        assert isinstance(state, TeamQueueState)
        assert state.team_id == "team-alpha"
        assert state.queued_jobs == 5
        assert state.assigned_jobs == 3
        assert state.waiting_jobs == 2
        assert state.captured_at == _T0

    def test_capture_queue_state_includes_overloaded_count(self):
        clock = _fixed_clock()
        reg = WorkerRegistry(clock=clock)
        reg.register_worker(_make_worker(worker_id="w-1", max_concurrent_jobs=2))
        reg.update_capacity("w-1", current_load=3)
        engine = TeamEngine(registry=reg, clock=clock)
        state = engine.capture_queue_state("team-1", queued=0, assigned=0, waiting=0)
        assert state.overloaded_workers == 1

    def test_capture_queue_state_empty_team_id_raises(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        engine = TeamEngine(registry=reg, clock=_fixed_clock())
        with pytest.raises(RuntimeCoreInvariantError, match="team_id"):
            engine.capture_queue_state("", queued=0, assigned=0, waiting=0)


# ============================================================
# TeamEngine — Overloaded worker detection
# ============================================================


class TestOverloadedWorkers:
    def test_find_overloaded_workers_detects_at_capacity(self):
        clock = _fixed_clock()
        reg = WorkerRegistry(clock=clock)
        reg.register_worker(_make_worker(worker_id="w-1", max_concurrent_jobs=2))
        reg.register_worker(_make_worker(worker_id="w-2", name="W2", max_concurrent_jobs=3))
        reg.update_capacity("w-1", current_load=2)
        reg.update_capacity("w-2", current_load=1)
        engine = TeamEngine(registry=reg, clock=clock)
        overloaded = engine.find_overloaded_workers()
        assert "w-1" in overloaded
        assert "w-2" not in overloaded

    def test_find_overloaded_workers_detects_over_capacity(self):
        clock = _fixed_clock()
        reg = WorkerRegistry(clock=clock)
        reg.register_worker(_make_worker(worker_id="w-1", max_concurrent_jobs=2))
        reg.update_capacity("w-1", current_load=5)
        engine = TeamEngine(registry=reg, clock=clock)
        overloaded = engine.find_overloaded_workers()
        assert "w-1" in overloaded

    def test_find_overloaded_workers_none_overloaded(self):
        clock = _fixed_clock()
        reg = WorkerRegistry(clock=clock)
        reg.register_worker(_make_worker(worker_id="w-1", max_concurrent_jobs=5))
        engine = TeamEngine(registry=reg, clock=clock)
        assert engine.find_overloaded_workers() == []


# ============================================================
# TeamEngine — Available worker filtering
# ============================================================


class TestAvailableWorkers:
    def test_find_available_workers_filters_by_role_and_slots(self):
        clock = _fixed_clock()
        reg = WorkerRegistry(clock=clock)
        reg.register_worker(_make_worker(worker_id="w-1", roles=("role-dev",), max_concurrent_jobs=3))
        reg.register_worker(_make_worker(worker_id="w-2", name="W2", roles=("role-dev",), max_concurrent_jobs=3))
        reg.register_worker(_make_worker(worker_id="w-3", name="W3", roles=("role-qa",), max_concurrent_jobs=3))
        reg.update_capacity("w-1", current_load=3)  # at capacity
        reg.update_capacity("w-2", current_load=1)  # available
        engine = TeamEngine(registry=reg, clock=clock)
        available = engine.find_available_workers("role-dev")
        ids = [w.worker_id for w in available]
        assert "w-2" in ids
        assert "w-1" not in ids
        assert "w-3" not in ids

    def test_find_available_workers_excludes_offline(self):
        clock = _fixed_clock()
        reg = WorkerRegistry(clock=clock)
        reg.register_worker(_make_worker(
            worker_id="w-1", status=WorkerStatus.OFFLINE, max_concurrent_jobs=3,
        ))
        engine = TeamEngine(registry=reg, clock=clock)
        assert engine.find_available_workers("role-dev") == []

    def test_find_available_workers_no_role_match(self):
        clock = _fixed_clock()
        reg = WorkerRegistry(clock=clock)
        reg.register_worker(_make_worker(worker_id="w-1", roles=("role-qa",)))
        engine = TeamEngine(registry=reg, clock=clock)
        assert engine.find_available_workers("role-dev") == []


# ============================================================
# TeamEngine — Rebalance suggestion
# ============================================================


class TestRebalanceSuggestion:
    def test_rebalance_moves_from_overloaded_to_underloaded(self):
        clock = _fixed_clock()
        reg = WorkerRegistry(clock=clock)
        reg.register_worker(_make_worker(worker_id="w-1", max_concurrent_jobs=3))
        reg.register_worker(_make_worker(worker_id="w-2", name="W2", max_concurrent_jobs=3))
        reg.update_capacity("w-1", current_load=4)  # overloaded
        reg.update_capacity("w-2", current_load=0)  # underloaded
        engine = TeamEngine(registry=reg, clock=clock)
        suggestions = engine.rebalance_suggestion("role-dev")
        assert len(suggestions) > 0
        from_ids = [s[0] for s in suggestions]
        to_ids = [s[1] for s in suggestions]
        assert "w-1" in from_ids
        assert "w-2" in to_ids

    def test_rebalance_no_workers_returns_empty(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        engine = TeamEngine(registry=reg, clock=_fixed_clock())
        assert engine.rebalance_suggestion("role-dev") == []

    def test_rebalance_no_overloaded_returns_empty(self):
        clock = _fixed_clock()
        reg = WorkerRegistry(clock=clock)
        reg.register_worker(_make_worker(worker_id="w-1", max_concurrent_jobs=5))
        reg.register_worker(_make_worker(worker_id="w-2", name="W2", max_concurrent_jobs=5))
        reg.update_capacity("w-1", current_load=1)
        reg.update_capacity("w-2", current_load=1)
        engine = TeamEngine(registry=reg, clock=clock)
        assert engine.rebalance_suggestion("role-dev") == []

    def test_rebalance_all_overloaded_returns_empty(self):
        clock = _fixed_clock()
        reg = WorkerRegistry(clock=clock)
        reg.register_worker(_make_worker(worker_id="w-1", max_concurrent_jobs=2))
        reg.register_worker(_make_worker(worker_id="w-2", name="W2", max_concurrent_jobs=2))
        reg.update_capacity("w-1", current_load=3)
        reg.update_capacity("w-2", current_load=3)
        engine = TeamEngine(registry=reg, clock=clock)
        assert engine.rebalance_suggestion("role-dev") == []

    def test_rebalance_job_count_is_correct(self):
        clock = _fixed_clock()
        reg = WorkerRegistry(clock=clock)
        reg.register_worker(_make_worker(worker_id="w-1", max_concurrent_jobs=2))
        reg.register_worker(_make_worker(worker_id="w-2", name="W2", max_concurrent_jobs=5))
        reg.update_capacity("w-1", current_load=4)  # 2 over capacity
        reg.update_capacity("w-2", current_load=0)
        engine = TeamEngine(registry=reg, clock=clock)
        suggestions = engine.rebalance_suggestion("role-dev")
        # w-1 has load 4, max 2 (overloaded). w-2 has load 0, max 5.
        # Algorithm moves one at a time until w-1 < max (load < 2), so 3 moves.
        assert len(suggestions) == 1
        assert suggestions[0] == ("w-1", "w-2", 3)


# ============================================================
# TeamEngine — Clock determinism
# ============================================================


class TestClockDeterminism:
    def test_assignment_uses_injected_clock(self):
        clock = _make_clock([_T2, _T2])
        reg = WorkerRegistry(clock=clock)
        reg.register_worker(_make_worker(worker_id="w-1", max_concurrent_jobs=3))
        engine = TeamEngine(registry=reg, clock=clock)
        decision = engine.assign_job("job-1", "role-dev")
        assert decision is not None
        assert decision.decided_at == _T2

    def test_workload_snapshot_uses_injected_clock(self):
        clock = _make_clock([_T0, _T1, _T2, _T3, _T4])
        reg = WorkerRegistry(clock=clock)
        reg.register_worker(_make_worker(worker_id="w-1", max_concurrent_jobs=3))
        engine = TeamEngine(registry=reg, clock=clock)
        snap = engine.capture_workload("team-1")
        assert snap is not None
        # The snapshot timestamp comes from the clock at capture time
        assert snap.captured_at in (_T0, _T1, _T2, _T3, _T4)

    def test_queue_state_uses_injected_clock(self):
        clock = _make_clock([_T5])
        reg = WorkerRegistry(clock=clock)
        engine = TeamEngine(registry=reg, clock=clock)
        state = engine.capture_queue_state("team-1", queued=0, assigned=0, waiting=0)
        assert state.captured_at == _T5

    def test_same_inputs_produce_same_decision_id(self):
        c1 = _make_clock([_T0, _T0])
        c2 = _make_clock([_T0, _T0])
        reg1 = WorkerRegistry(clock=c1)
        reg2 = WorkerRegistry(clock=c2)
        reg1.register_worker(_make_worker(worker_id="w-1", max_concurrent_jobs=3))
        reg2.register_worker(_make_worker(worker_id="w-1", max_concurrent_jobs=3))
        e1 = TeamEngine(registry=reg1, clock=c1)
        e2 = TeamEngine(registry=reg2, clock=c2)
        d1 = e1.assign_job("job-1", "role-dev")
        d2 = e2.assign_job("job-1", "role-dev")
        assert d1 is not None and d2 is not None
        assert d1.decision_id == d2.decision_id


# ============================================================
# Edge cases
# ============================================================


class TestEdgeCases:
    def test_multiple_roles_per_worker(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        reg.register_worker(_make_worker(
            worker_id="w-multi", roles=("role-dev", "role-qa", "role-ops"),
        ))
        assert len(reg.get_workers_for_role("role-dev")) == 1
        assert len(reg.get_workers_for_role("role-qa")) == 1
        assert len(reg.get_workers_for_role("role-ops")) == 1

    def test_assign_with_single_worker_at_zero_load(self):
        clock = _fixed_clock()
        reg = WorkerRegistry(clock=clock)
        reg.register_worker(_make_worker(worker_id="w-1", max_concurrent_jobs=1))
        engine = TeamEngine(registry=reg, clock=clock)
        decision = engine.assign_job("job-1", "role-dev")
        assert decision is not None
        assert decision.worker_id == "w-1"

    def test_assign_single_worker_at_capacity(self):
        clock = _fixed_clock()
        reg = WorkerRegistry(clock=clock)
        reg.register_worker(_make_worker(worker_id="w-1", max_concurrent_jobs=1))
        reg.update_capacity("w-1", current_load=1)
        engine = TeamEngine(registry=reg, clock=clock)
        decision = engine.assign_job("job-1", "role-dev")
        assert decision is None

    def test_capacity_update_to_zero_load(self):
        clock = _make_clock([_T0, _T1])
        reg = WorkerRegistry(clock=clock)
        reg.register_worker(_make_worker(worker_id="w-1", max_concurrent_jobs=5))
        reg.update_capacity("w-1", current_load=3)
        cap = reg.update_capacity("w-1", current_load=0)
        assert cap.available_slots == 5
        assert cap.current_load == 0

    def test_handoff_different_reasons(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        engine = TeamEngine(registry=reg, clock=_make_clock([_T0, _T1, _T2]))
        r1 = engine.handoff_job("j-1", "w-1", "w-2", HandoffReason.CAPACITY_EXCEEDED)
        r2 = engine.handoff_job("j-2", "w-1", "w-2", HandoffReason.ROLE_CHANGE)
        r3 = engine.handoff_job("j-3", "w-1", "w-2", HandoffReason.ESCALATION)
        assert r1.reason == HandoffReason.CAPACITY_EXCEEDED
        assert r2.reason == HandoffReason.ROLE_CHANGE
        assert r3.reason == HandoffReason.ESCALATION

    def test_assign_busy_workers_skipped(self):
        clock = _fixed_clock()
        reg = WorkerRegistry(clock=clock)
        reg.register_worker(_make_worker(
            worker_id="w-busy", status=WorkerStatus.BUSY, max_concurrent_jobs=3,
        ))
        reg.register_worker(_make_worker(
            worker_id="w-avail", name="Avail", status=WorkerStatus.AVAILABLE, max_concurrent_jobs=3,
        ))
        engine = TeamEngine(registry=reg, clock=clock)
        decision = engine.assign_job("job-1", "role-dev")
        assert decision is not None
        assert decision.worker_id == "w-avail"

    def test_all_non_available_statuses_skipped_in_assignment(self):
        clock = _fixed_clock()
        reg = WorkerRegistry(clock=clock)
        for i, status in enumerate([WorkerStatus.BUSY, WorkerStatus.OVERLOADED,
                                     WorkerStatus.OFFLINE, WorkerStatus.ON_HOLD]):
            reg.register_worker(_make_worker(
                worker_id=f"w-{i}", name=f"W{i}", status=status, max_concurrent_jobs=3,
            ))
        engine = TeamEngine(registry=reg, clock=clock)
        decision = engine.assign_job("job-1", "role-dev")
        assert decision is None

    def test_handoff_operator_override_reason(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        engine = TeamEngine(registry=reg, clock=_fixed_clock())
        record = engine.handoff_job("j-1", "w-1", "w-2", HandoffReason.OPERATOR_OVERRIDE)
        assert record.reason == HandoffReason.OPERATOR_OVERRIDE

    def test_handoff_shift_change_reason(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        engine = TeamEngine(registry=reg, clock=_fixed_clock())
        record = engine.handoff_job("j-1", "w-1", "w-2", HandoffReason.SHIFT_CHANGE)
        assert record.reason == HandoffReason.SHIFT_CHANGE


class TestBoundedTeamContracts:
    def test_registry_messages_are_bounded(self):
        reg = WorkerRegistry(clock=_fixed_clock())
        reg.register_worker(_make_worker(worker_id="worker-secret"))
        with pytest.raises(RuntimeCoreInvariantError, match="worker already registered") as worker_exc:
            reg.register_worker(_make_worker(worker_id="worker-secret", name="Duplicate"))

        reg.register_role(_make_role(role_id="role-secret"))
        with pytest.raises(RuntimeCoreInvariantError, match="role already registered") as role_exc:
            reg.register_role(_make_role(role_id="role-secret", name="Duplicate"))

        reg.register_policy(_make_policy(policy_id="policy-secret"))
        with pytest.raises(RuntimeCoreInvariantError, match="policy already registered") as policy_exc:
            reg.register_policy(_make_policy(policy_id="policy-secret"))

        with pytest.raises(RuntimeCoreInvariantError, match="worker not found") as missing_exc:
            reg.update_capacity("worker-missing", current_load=1)

        assert "worker-secret" not in str(worker_exc.value)
        assert "role-secret" not in str(role_exc.value)
        assert "policy-secret" not in str(policy_exc.value)
        assert "worker-missing" not in str(missing_exc.value)

    def test_assignment_reason_is_bounded(self):
        clock = _fixed_clock()
        reg = WorkerRegistry(clock=clock)
        reg.register_worker(_make_worker(worker_id="w-busy", max_concurrent_jobs=5))
        reg.register_worker(_make_worker(worker_id="w-light", name="Light", max_concurrent_jobs=5))
        reg.update_capacity("w-busy", current_load=4)
        reg.update_capacity("w-light", current_load=1)
        engine = TeamEngine(registry=reg, clock=clock)

        decision = engine.assign_job("job-secret", "role-dev")
        assert decision is not None
        assert decision.reason == "least loaded available worker"
        assert "slots" not in decision.reason
        assert "4" not in decision.reason
        assert "1" not in decision.reason
