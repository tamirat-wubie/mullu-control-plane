"""Comprehensive tests for WorkforceRuntimeEngine.

Covers: constructor validation, worker lifecycle, role/team capacity,
assignment requests, assignment decisions (manual + lowest-load),
coverage gap detection, load snapshots, workforce assessment,
violation detection, closure reports, state hashing, and six
golden scenarios from the specification.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.workforce_runtime import WorkforceRuntimeEngine
from mcoi_runtime.contracts.workforce_runtime import (
    WorkerStatus,
    CapacityStatus,
    AssignmentDisposition,
    EscalationMode,
    LoadBand,
    CoverageStatus,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# =====================================================================
# Fixtures
# =====================================================================


@pytest.fixture
def spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture
def engine(spine: EventSpineEngine) -> WorkforceRuntimeEngine:
    return WorkforceRuntimeEngine(spine)


def _register(
    eng: WorkforceRuntimeEngine,
    wid: str = "w1",
    tenant: str = "t1",
    role: str = "reviewer",
    team: str = "alpha",
    name: str = "Alice",
    max_assign: int = 5,
    status: WorkerStatus = WorkerStatus.ACTIVE,
):
    return eng.register_worker(wid, tenant, role, team, name, max_assign, status)


# =====================================================================
# 1. Constructor validation
# =====================================================================


class TestConstructor:
    def test_valid_event_spine(self, spine):
        eng = WorkforceRuntimeEngine(spine)
        assert eng.worker_count == 0

    def test_none_raises(self):
        with pytest.raises(RuntimeCoreInvariantError):
            WorkforceRuntimeEngine(None)

    def test_string_raises(self):
        with pytest.raises(RuntimeCoreInvariantError):
            WorkforceRuntimeEngine("not-a-spine")

    def test_dict_raises(self):
        with pytest.raises(RuntimeCoreInvariantError):
            WorkforceRuntimeEngine({})

    def test_integer_raises(self):
        with pytest.raises(RuntimeCoreInvariantError):
            WorkforceRuntimeEngine(42)

    def test_initial_counts_zero(self, engine):
        assert engine.worker_count == 0
        assert engine.role_capacity_count == 0
        assert engine.team_capacity_count == 0
        assert engine.request_count == 0
        assert engine.decision_count == 0
        assert engine.gap_count == 0
        assert engine.violation_count == 0


# =====================================================================
# 2. Worker registration
# =====================================================================


class TestRegisterWorker:
    def test_basic_registration(self, engine):
        w = _register(engine)
        assert w.worker_id == "w1"
        assert w.tenant_id == "t1"
        assert w.role_ref == "reviewer"
        assert w.team_ref == "alpha"
        assert w.display_name == "Alice"
        assert w.max_assignments == 5
        assert w.current_assignments == 0
        assert w.status == WorkerStatus.ACTIVE

    def test_registration_increments_count(self, engine):
        _register(engine, "w1")
        _register(engine, "w2", name="Bob")
        assert engine.worker_count == 2

    def test_duplicate_raises(self, engine):
        _register(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="already registered"):
            _register(engine)

    def test_custom_max_assignments(self, engine):
        w = _register(engine, max_assign=10)
        assert w.max_assignments == 10

    def test_custom_status(self, engine):
        w = _register(engine, status=WorkerStatus.ON_LEAVE)
        assert w.status == WorkerStatus.ON_LEAVE

    def test_multiple_tenants(self, engine):
        _register(engine, "w1", tenant="t1")
        _register(engine, "w2", tenant="t2")
        assert engine.worker_count == 2

    def test_multiple_roles_same_tenant(self, engine):
        _register(engine, "w1", role="reviewer")
        _register(engine, "w2", role="auditor", name="Bob")
        assert engine.worker_count == 2

    def test_worker_record_is_frozen(self, engine):
        w = _register(engine)
        with pytest.raises(AttributeError):
            w.worker_id = "changed"

    def test_created_at_populated(self, engine):
        w = _register(engine)
        assert w.created_at  # non-empty ISO string

    def test_emits_event(self, spine, engine):
        initial = spine.event_count
        _register(engine)
        assert spine.event_count == initial + 1


# =====================================================================
# 3. get_worker
# =====================================================================


class TestGetWorker:
    def test_get_existing(self, engine):
        _register(engine)
        w = engine.get_worker("w1")
        assert w.worker_id == "w1"

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown worker"):
            engine.get_worker("no-such")

    def test_returns_same_data(self, engine):
        original = _register(engine)
        fetched = engine.get_worker("w1")
        assert original.worker_id == fetched.worker_id
        assert original.display_name == fetched.display_name


# =====================================================================
# 4. update_worker_status
# =====================================================================


class TestUpdateWorkerStatus:
    def test_active_to_on_leave(self, engine):
        _register(engine)
        updated = engine.update_worker_status("w1", WorkerStatus.ON_LEAVE)
        assert updated.status == WorkerStatus.ON_LEAVE

    def test_active_to_suspended(self, engine):
        _register(engine)
        updated = engine.update_worker_status("w1", WorkerStatus.SUSPENDED)
        assert updated.status == WorkerStatus.SUSPENDED

    def test_active_to_unavailable(self, engine):
        _register(engine)
        updated = engine.update_worker_status("w1", WorkerStatus.UNAVAILABLE)
        assert updated.status == WorkerStatus.UNAVAILABLE

    def test_active_to_offboarded(self, engine):
        _register(engine)
        updated = engine.update_worker_status("w1", WorkerStatus.OFFBOARDED)
        assert updated.status == WorkerStatus.OFFBOARDED

    def test_offboarded_is_terminal(self, engine):
        _register(engine)
        engine.update_worker_status("w1", WorkerStatus.OFFBOARDED)
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.update_worker_status("w1", WorkerStatus.ACTIVE)

    def test_offboarded_cannot_go_on_leave(self, engine):
        _register(engine)
        engine.update_worker_status("w1", WorkerStatus.OFFBOARDED)
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.update_worker_status("w1", WorkerStatus.ON_LEAVE)

    def test_on_leave_to_active(self, engine):
        _register(engine, status=WorkerStatus.ON_LEAVE)
        updated = engine.update_worker_status("w1", WorkerStatus.ACTIVE)
        assert updated.status == WorkerStatus.ACTIVE

    def test_suspended_to_active(self, engine):
        _register(engine, status=WorkerStatus.SUSPENDED)
        updated = engine.update_worker_status("w1", WorkerStatus.ACTIVE)
        assert updated.status == WorkerStatus.ACTIVE

    def test_unknown_worker_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown worker"):
            engine.update_worker_status("nope", WorkerStatus.ACTIVE)

    def test_preserves_assignments(self, engine):
        _register(engine)
        req = engine.request_assignment("r1", "t1", "scope1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1", AssignmentDisposition.ASSIGNED)
        engine.update_worker_status("w1", WorkerStatus.ON_LEAVE)
        w = engine.get_worker("w1")
        assert w.current_assignments == 1
        assert w.status == WorkerStatus.ON_LEAVE

    def test_emits_event(self, spine, engine):
        _register(engine)
        before = spine.event_count
        engine.update_worker_status("w1", WorkerStatus.ON_LEAVE)
        assert spine.event_count == before + 1


# =====================================================================
# 5. Worker query methods
# =====================================================================


class TestWorkerQueries:
    def test_workers_for_tenant_empty(self, engine):
        assert engine.workers_for_tenant("t1") == ()

    def test_workers_for_tenant(self, engine):
        _register(engine, "w1", tenant="t1")
        _register(engine, "w2", tenant="t1", name="Bob")
        _register(engine, "w3", tenant="t2", name="Charlie")
        result = engine.workers_for_tenant("t1")
        assert len(result) == 2

    def test_workers_for_role_empty(self, engine):
        assert engine.workers_for_role("t1", "reviewer") == ()

    def test_workers_for_role(self, engine):
        _register(engine, "w1", role="reviewer")
        _register(engine, "w2", role="auditor", name="Bob")
        result = engine.workers_for_role("t1", "reviewer")
        assert len(result) == 1
        assert result[0].worker_id == "w1"

    def test_workers_for_role_multi(self, engine):
        _register(engine, "w1", role="reviewer")
        _register(engine, "w2", role="reviewer", name="Bob")
        result = engine.workers_for_role("t1", "reviewer")
        assert len(result) == 2

    def test_available_workers_active_only(self, engine):
        _register(engine, "w1", status=WorkerStatus.ACTIVE)
        _register(engine, "w2", status=WorkerStatus.ON_LEAVE, name="Bob")
        result = engine.available_workers_for_role("t1", "reviewer")
        assert len(result) == 1
        assert result[0].worker_id == "w1"

    def test_available_workers_excludes_max_load(self, engine):
        _register(engine, "w1", max_assign=1)
        engine.request_assignment("r1", "t1", "scope1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1", AssignmentDisposition.ASSIGNED)
        result = engine.available_workers_for_role("t1", "reviewer")
        assert len(result) == 0

    def test_available_workers_excludes_suspended(self, engine):
        _register(engine, "w1", status=WorkerStatus.SUSPENDED)
        assert engine.available_workers_for_role("t1", "reviewer") == ()

    def test_available_workers_excludes_offboarded(self, engine):
        _register(engine, "w1", status=WorkerStatus.OFFBOARDED)
        assert engine.available_workers_for_role("t1", "reviewer") == ()

    def test_available_workers_excludes_unavailable(self, engine):
        _register(engine, "w1", status=WorkerStatus.UNAVAILABLE)
        assert engine.available_workers_for_role("t1", "reviewer") == ()

    def test_available_workers_cross_tenant_isolation(self, engine):
        _register(engine, "w1", tenant="t1")
        _register(engine, "w2", tenant="t2", name="Bob")
        result = engine.available_workers_for_role("t1", "reviewer")
        assert len(result) == 1

    def test_workers_for_tenant_returns_tuple(self, engine):
        result = engine.workers_for_tenant("t1")
        assert isinstance(result, tuple)


# =====================================================================
# 6. Role capacity
# =====================================================================


class TestRoleCapacity:
    def test_register_empty_role(self, engine):
        rc = engine.register_role_capacity("rc1", "t1", "reviewer")
        assert rc.capacity_id == "rc1"
        assert rc.total_workers == 0
        assert rc.available_workers == 0
        assert rc.utilization == 0.0
        assert rc.status == CapacityStatus.EMPTY

    def test_register_with_workers(self, engine):
        _register(engine, "w1")
        _register(engine, "w2", name="Bob")
        rc = engine.register_role_capacity("rc1", "t1", "reviewer")
        assert rc.total_workers == 2
        assert rc.available_workers == 2
        assert rc.total_capacity == 10
        assert rc.used_capacity == 0
        assert rc.utilization == 0.0
        assert rc.status == CapacityStatus.EMPTY

    def test_register_with_partial_load(self, engine):
        _register(engine, "w1", max_assign=2)
        _register(engine, "w2", name="Bob", max_assign=2)
        engine.request_assignment("r1", "t1", "scope1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1", AssignmentDisposition.ASSIGNED)
        rc = engine.register_role_capacity("rc1", "t1", "reviewer")
        assert rc.used_capacity == 1
        assert rc.total_capacity == 4
        assert rc.utilization == 0.25
        assert rc.status == CapacityStatus.NOMINAL

    def test_duplicate_raises(self, engine):
        engine.register_role_capacity("rc1", "t1", "reviewer")
        with pytest.raises(RuntimeCoreInvariantError, match="already registered"):
            engine.register_role_capacity("rc1", "t1", "reviewer")

    def test_get_role_capacity(self, engine):
        engine.register_role_capacity("rc1", "t1", "reviewer")
        rc = engine.get_role_capacity("rc1")
        assert rc.capacity_id == "rc1"

    def test_get_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown role capacity"):
            engine.get_role_capacity("nope")

    def test_role_capacities_for_tenant(self, engine):
        engine.register_role_capacity("rc1", "t1", "reviewer")
        engine.register_role_capacity("rc2", "t1", "auditor")
        engine.register_role_capacity("rc3", "t2", "reviewer")
        result = engine.role_capacities_for_tenant("t1")
        assert len(result) == 2

    def test_role_capacities_for_tenant_empty(self, engine):
        assert engine.role_capacities_for_tenant("t1") == ()

    def test_strained_status(self, engine):
        # utilization >= 0.7 but < 0.9
        _register(engine, "w1", max_assign=10)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        engine.request_assignment("r2", "t1", "s2", "reviewer")
        engine.decide_assignment("d2", "r2", "w1")
        engine.request_assignment("r3", "t1", "s3", "reviewer")
        engine.decide_assignment("d3", "r3", "w1")
        engine.request_assignment("r4", "t1", "s4", "reviewer")
        engine.decide_assignment("d4", "r4", "w1")
        engine.request_assignment("r5", "t1", "s5", "reviewer")
        engine.decide_assignment("d5", "r5", "w1")
        engine.request_assignment("r6", "t1", "s6", "reviewer")
        engine.decide_assignment("d6", "r6", "w1")
        engine.request_assignment("r7", "t1", "s7", "reviewer")
        engine.decide_assignment("d7", "r7", "w1")
        # 7/10 = 0.7
        rc = engine.register_role_capacity("rc1", "t1", "reviewer")
        assert rc.utilization == 0.7
        assert rc.status == CapacityStatus.STRAINED

    def test_critical_status(self, engine):
        # utilization >= 0.9 but < 1.0
        _register(engine, "w1", max_assign=10)
        for i in range(9):
            engine.request_assignment(f"r{i}", "t1", f"s{i}", "reviewer")
            engine.decide_assignment(f"d{i}", f"r{i}", "w1")
        rc = engine.register_role_capacity("rc1", "t1", "reviewer")
        assert rc.utilization == 0.9
        assert rc.status == CapacityStatus.CRITICAL

    def test_overloaded_status(self, engine):
        # utilization == 1.0
        _register(engine, "w1", max_assign=2)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        engine.request_assignment("r2", "t1", "s2", "reviewer")
        engine.decide_assignment("d2", "r2", "w1")
        rc = engine.register_role_capacity("rc1", "t1", "reviewer")
        assert rc.utilization == 1.0
        assert rc.status == CapacityStatus.OVERLOADED

    def test_nominal_status(self, engine):
        # utilization > 0 and < 0.7
        _register(engine, "w1", max_assign=10)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        rc = engine.register_role_capacity("rc1", "t1", "reviewer")
        assert rc.utilization == 0.1
        assert rc.status == CapacityStatus.NOMINAL

    def test_record_is_frozen(self, engine):
        rc = engine.register_role_capacity("rc1", "t1", "reviewer")
        with pytest.raises(AttributeError):
            rc.capacity_id = "changed"

    def test_emits_event(self, spine, engine):
        before = spine.event_count
        engine.register_role_capacity("rc1", "t1", "reviewer")
        assert spine.event_count == before + 1


# =====================================================================
# 7. Team capacity
# =====================================================================


class TestTeamCapacity:
    def test_register_empty_team(self, engine):
        tc = engine.register_team_capacity("tc1", "t1", "alpha")
        assert tc.total_members == 0
        assert tc.status == CapacityStatus.EMPTY

    def test_register_with_workers(self, engine):
        _register(engine, "w1", team="alpha")
        _register(engine, "w2", team="alpha", name="Bob")
        tc = engine.register_team_capacity("tc1", "t1", "alpha")
        assert tc.total_members == 2
        assert tc.available_members == 2

    def test_duplicate_raises(self, engine):
        engine.register_team_capacity("tc1", "t1", "alpha")
        with pytest.raises(RuntimeCoreInvariantError, match="already registered"):
            engine.register_team_capacity("tc1", "t1", "alpha")

    def test_get_team_capacity(self, engine):
        engine.register_team_capacity("tc1", "t1", "alpha")
        tc = engine.get_team_capacity("tc1")
        assert tc.capacity_id == "tc1"

    def test_get_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown team capacity"):
            engine.get_team_capacity("nope")

    def test_team_capacities_for_tenant(self, engine):
        engine.register_team_capacity("tc1", "t1", "alpha")
        engine.register_team_capacity("tc2", "t2", "beta")
        result = engine.team_capacities_for_tenant("t1")
        assert len(result) == 1

    def test_team_capacities_for_tenant_empty(self, engine):
        assert engine.team_capacities_for_tenant("t1") == ()

    def test_team_capacity_with_load(self, engine):
        _register(engine, "w1", team="alpha", max_assign=4)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        tc = engine.register_team_capacity("tc1", "t1", "alpha")
        assert tc.used_capacity == 1
        assert tc.total_capacity == 4
        assert tc.utilization == 0.25

    def test_team_cross_tenant_isolation(self, engine):
        _register(engine, "w1", tenant="t1", team="alpha")
        _register(engine, "w2", tenant="t2", team="alpha", name="Bob")
        tc = engine.register_team_capacity("tc1", "t1", "alpha")
        assert tc.total_members == 1

    def test_record_is_frozen(self, engine):
        tc = engine.register_team_capacity("tc1", "t1", "alpha")
        with pytest.raises(AttributeError):
            tc.capacity_id = "changed"

    def test_emits_event(self, spine, engine):
        before = spine.event_count
        engine.register_team_capacity("tc1", "t1", "alpha")
        assert spine.event_count == before + 1


# =====================================================================
# 8. Assignment requests
# =====================================================================


class TestAssignmentRequest:
    def test_basic_request(self, engine):
        req = engine.request_assignment("r1", "t1", "scope1", "reviewer")
        assert req.request_id == "r1"
        assert req.tenant_id == "t1"
        assert req.scope_ref_id == "scope1"
        assert req.role_ref == "reviewer"
        assert req.priority == 1
        assert req.source_type == "manual"

    def test_custom_priority(self, engine):
        req = engine.request_assignment("r1", "t1", "s1", "reviewer", priority=5)
        assert req.priority == 5

    def test_custom_source_type(self, engine):
        req = engine.request_assignment("r1", "t1", "s1", "reviewer", source_type="auto")
        assert req.source_type == "auto"

    def test_duplicate_raises(self, engine):
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            engine.request_assignment("r1", "t1", "s1", "reviewer")

    def test_get_request(self, engine):
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        req = engine.get_request("r1")
        assert req.request_id == "r1"

    def test_get_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown assignment request"):
            engine.get_request("nope")

    def test_requests_for_tenant(self, engine):
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.request_assignment("r2", "t1", "s2", "auditor")
        engine.request_assignment("r3", "t2", "s3", "reviewer")
        result = engine.requests_for_tenant("t1")
        assert len(result) == 2

    def test_requests_for_tenant_empty(self, engine):
        assert engine.requests_for_tenant("t1") == ()

    def test_request_count(self, engine):
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        assert engine.request_count == 1

    def test_record_is_frozen(self, engine):
        req = engine.request_assignment("r1", "t1", "s1", "reviewer")
        with pytest.raises(AttributeError):
            req.request_id = "changed"

    def test_emits_event(self, spine, engine):
        before = spine.event_count
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        assert spine.event_count == before + 1


# =====================================================================
# 9. decide_assignment
# =====================================================================


class TestDecideAssignment:
    def test_assign_to_known_worker(self, engine):
        _register(engine, "w1")
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        dec = engine.decide_assignment("d1", "r1", "w1", AssignmentDisposition.ASSIGNED)
        assert dec.decision_id == "d1"
        assert dec.request_id == "r1"
        assert dec.worker_id == "w1"
        assert dec.disposition == AssignmentDisposition.ASSIGNED

    def test_assign_increments_current(self, engine):
        _register(engine, "w1")
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1", AssignmentDisposition.ASSIGNED)
        w = engine.get_worker("w1")
        assert w.current_assignments == 1

    def test_multiple_assigns_increment(self, engine):
        _register(engine, "w1", max_assign=5)
        for i in range(3):
            engine.request_assignment(f"r{i}", "t1", f"s{i}", "reviewer")
            engine.decide_assignment(f"d{i}", f"r{i}", "w1")
        w = engine.get_worker("w1")
        assert w.current_assignments == 3

    def test_duplicate_decision_raises(self, engine):
        _register(engine, "w1")
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            engine.decide_assignment("d1", "r1", "w1")

    def test_unknown_request_raises(self, engine):
        _register(engine, "w1")
        with pytest.raises(RuntimeCoreInvariantError, match="unknown assignment request"):
            engine.decide_assignment("d1", "nope", "w1")

    def test_unknown_worker_raises(self, engine):
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        with pytest.raises(RuntimeCoreInvariantError, match="unknown worker"):
            engine.decide_assignment("d1", "r1", "ghost")

    def test_on_leave_worker_raises(self, engine):
        _register(engine, "w1", status=WorkerStatus.ON_LEAVE)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        with pytest.raises(RuntimeCoreInvariantError, match="unavailable"):
            engine.decide_assignment("d1", "r1", "w1")

    def test_suspended_worker_raises(self, engine):
        _register(engine, "w1", status=WorkerStatus.SUSPENDED)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        with pytest.raises(RuntimeCoreInvariantError, match="unavailable"):
            engine.decide_assignment("d1", "r1", "w1")

    def test_unavailable_worker_raises(self, engine):
        _register(engine, "w1", status=WorkerStatus.UNAVAILABLE)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        with pytest.raises(RuntimeCoreInvariantError, match="unavailable"):
            engine.decide_assignment("d1", "r1", "w1")

    def test_offboarded_worker_raises(self, engine):
        _register(engine, "w1", status=WorkerStatus.OFFBOARDED)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        with pytest.raises(RuntimeCoreInvariantError, match="unavailable"):
            engine.decide_assignment("d1", "r1", "w1")

    def test_at_max_raises(self, engine):
        _register(engine, "w1", max_assign=1)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        engine.request_assignment("r2", "t1", "s2", "reviewer")
        with pytest.raises(RuntimeCoreInvariantError, match="max assignments"):
            engine.decide_assignment("d2", "r2", "w1")

    def test_deferred_no_worker(self, engine):
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        dec = engine.decide_assignment("d1", "r1", disposition=AssignmentDisposition.DEFERRED)
        assert dec.disposition == AssignmentDisposition.DEFERRED
        assert dec.worker_id == "none"

    def test_rejected_no_worker(self, engine):
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        dec = engine.decide_assignment("d1", "r1", disposition=AssignmentDisposition.REJECTED)
        assert dec.disposition == AssignmentDisposition.REJECTED
        assert dec.worker_id == "none"

    def test_escalated_no_worker(self, engine):
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        dec = engine.decide_assignment("d1", "r1", disposition=AssignmentDisposition.ESCALATED)
        assert dec.disposition == AssignmentDisposition.ESCALATED
        assert dec.worker_id == "none"

    def test_default_reason_from_disposition(self, engine):
        _register(engine, "w1")
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        dec = engine.decide_assignment("d1", "r1", "w1")
        assert dec.reason == "assigned"

    def test_custom_reason(self, engine):
        _register(engine, "w1")
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        dec = engine.decide_assignment("d1", "r1", "w1", reason="best fit")
        assert dec.reason == "best fit"

    def test_decisions_for_request(self, engine):
        _register(engine, "w1", max_assign=5)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        result = engine.decisions_for_request("r1")
        assert len(result) == 1

    def test_decisions_for_request_empty(self, engine):
        assert engine.decisions_for_request("r1") == ()

    def test_decisions_for_worker(self, engine):
        _register(engine, "w1", max_assign=5)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.request_assignment("r2", "t1", "s2", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        engine.decide_assignment("d2", "r2", "w1")
        result = engine.decisions_for_worker("w1")
        assert len(result) == 2

    def test_decisions_for_worker_empty(self, engine):
        assert engine.decisions_for_worker("w1") == ()

    def test_decision_count(self, engine):
        _register(engine, "w1")
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        assert engine.decision_count == 1

    def test_record_is_frozen(self, engine):
        _register(engine, "w1")
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        dec = engine.decide_assignment("d1", "r1", "w1")
        with pytest.raises(AttributeError):
            dec.decision_id = "changed"

    def test_emits_event(self, spine, engine):
        _register(engine, "w1")
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        before = spine.event_count
        engine.decide_assignment("d1", "r1", "w1")
        assert spine.event_count == before + 1


# =====================================================================
# 10. assign_to_lowest_load
# =====================================================================


class TestAssignToLowestLoad:
    def test_picks_lowest_load(self, engine):
        _register(engine, "w1", max_assign=5)
        _register(engine, "w2", name="Bob", max_assign=5)
        # Give w1 one assignment
        engine.request_assignment("r0", "t1", "s0", "reviewer")
        engine.decide_assignment("d0", "r0", "w1")
        # Now auto-assign next
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        dec = engine.assign_to_lowest_load("d1", "r1")
        assert dec.worker_id == "w2"
        assert dec.disposition == AssignmentDisposition.ASSIGNED

    def test_escalates_when_no_available(self, engine):
        _register(engine, "w1", max_assign=1)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        engine.request_assignment("r2", "t1", "s2", "reviewer")
        dec = engine.assign_to_lowest_load("d2", "r2")
        assert dec.disposition == AssignmentDisposition.ESCALATED
        assert dec.worker_id == "escalation"

    def test_escalates_when_all_on_leave(self, engine):
        _register(engine, "w1", status=WorkerStatus.ON_LEAVE)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        dec = engine.assign_to_lowest_load("d1", "r1")
        assert dec.disposition == AssignmentDisposition.ESCALATED

    def test_escalates_when_no_workers(self, engine):
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        dec = engine.assign_to_lowest_load("d1", "r1")
        assert dec.disposition == AssignmentDisposition.ESCALATED

    def test_duplicate_decision_raises(self, engine):
        _register(engine, "w1")
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.assign_to_lowest_load("d1", "r1")
        engine.request_assignment("r2", "t1", "s2", "reviewer")
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            engine.assign_to_lowest_load("d1", "r2")

    def test_unknown_request_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown assignment request"):
            engine.assign_to_lowest_load("d1", "nope")

    def test_increments_load_on_assigned(self, engine):
        _register(engine, "w1", max_assign=5)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.assign_to_lowest_load("d1", "r1")
        w = engine.get_worker("w1")
        assert w.current_assignments == 1

    def test_custom_reason(self, engine):
        _register(engine, "w1")
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        dec = engine.assign_to_lowest_load("d1", "r1", reason="auto-route")
        assert dec.reason == "auto-route"

    def test_default_reason_assigned(self, engine):
        _register(engine, "w1")
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        dec = engine.assign_to_lowest_load("d1", "r1")
        assert dec.reason == "lowest_load"

    def test_default_reason_escalated(self, engine):
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        dec = engine.assign_to_lowest_load("d1", "r1")
        assert dec.reason == "no_available_workers"

    def test_balances_across_three_workers(self, engine):
        _register(engine, "w1", max_assign=5)
        _register(engine, "w2", name="Bob", max_assign=5)
        _register(engine, "w3", name="Charlie", max_assign=5)
        # Assign one to w1
        engine.request_assignment("r0", "t1", "s0", "reviewer")
        engine.decide_assignment("d0", "r0", "w1")
        # Auto-assign: should pick w2 or w3 (both at 0)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        dec1 = engine.assign_to_lowest_load("d1", "r1")
        assert dec1.worker_id in ("w2", "w3")
        # Now the one picked has 1, the other has 0
        engine.request_assignment("r2", "t1", "s2", "reviewer")
        dec2 = engine.assign_to_lowest_load("d2", "r2")
        # Should pick the one still at 0
        other = "w3" if dec1.worker_id == "w2" else "w2"
        assert dec2.worker_id == other

    def test_picks_among_equal_load(self, engine):
        _register(engine, "w1", max_assign=5)
        _register(engine, "w2", name="Bob", max_assign=5)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        dec = engine.assign_to_lowest_load("d1", "r1")
        # Both at 0 load, either is acceptable
        assert dec.worker_id in ("w1", "w2")

    def test_skips_non_matching_role(self, engine):
        _register(engine, "w1", role="reviewer")
        _register(engine, "w2", name="Bob", role="auditor")
        engine.request_assignment("r1", "t1", "s1", "auditor")
        dec = engine.assign_to_lowest_load("d1", "r1")
        assert dec.worker_id == "w2"


# =====================================================================
# 11. Coverage gap detection
# =====================================================================


class TestCoverageGaps:
    def test_no_gaps_all_active(self, engine):
        _register(engine, "w1")
        gaps = engine.detect_coverage_gaps("t1")
        assert len(gaps) == 0

    def test_gap_when_all_on_leave(self, engine):
        _register(engine, "w1", status=WorkerStatus.ON_LEAVE)
        _register(engine, "w2", name="Bob", status=WorkerStatus.ON_LEAVE)
        gaps = engine.detect_coverage_gaps("t1")
        assert len(gaps) == 1
        assert gaps[0].status == CoverageStatus.GAP
        assert gaps[0].available_workers == 0
        assert gaps[0].escalation_mode == EscalationMode.MANAGER

    def test_critical_gap_three_or_more(self, engine):
        for i in range(3):
            _register(engine, f"w{i}", name=f"Worker{i}", status=WorkerStatus.ON_LEAVE)
        gaps = engine.detect_coverage_gaps("t1")
        assert len(gaps) == 1
        assert gaps[0].status == CoverageStatus.CRITICAL_GAP

    def test_gap_fewer_than_three(self, engine):
        _register(engine, "w1", status=WorkerStatus.SUSPENDED)
        gaps = engine.detect_coverage_gaps("t1")
        assert len(gaps) == 1
        assert gaps[0].status == CoverageStatus.GAP

    def test_idempotent(self, engine):
        _register(engine, "w1", status=WorkerStatus.ON_LEAVE)
        gaps1 = engine.detect_coverage_gaps("t1")
        gaps2 = engine.detect_coverage_gaps("t1")
        assert len(gaps1) == 1
        assert len(gaps2) == 0  # second call produces no NEW gaps
        assert engine.gap_count == 1

    def test_gaps_for_tenant(self, engine):
        _register(engine, "w1", status=WorkerStatus.ON_LEAVE)
        engine.detect_coverage_gaps("t1")
        result = engine.gaps_for_tenant("t1")
        assert len(result) == 1

    def test_gaps_for_tenant_empty(self, engine):
        assert engine.gaps_for_tenant("t1") == ()

    def test_no_gap_if_some_available(self, engine):
        _register(engine, "w1", status=WorkerStatus.ACTIVE)
        _register(engine, "w2", name="Bob", status=WorkerStatus.ON_LEAVE)
        gaps = engine.detect_coverage_gaps("t1")
        assert len(gaps) == 0

    def test_gap_cross_tenant_isolation(self, engine):
        _register(engine, "w1", tenant="t1", status=WorkerStatus.ON_LEAVE)
        _register(engine, "w2", tenant="t2", name="Bob", status=WorkerStatus.ACTIVE)
        gaps = engine.detect_coverage_gaps("t1")
        assert len(gaps) == 1

    def test_gap_at_max_assignments_counts(self, engine):
        # Worker is active but at max -- not available
        _register(engine, "w1", max_assign=1)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        gaps = engine.detect_coverage_gaps("t1")
        assert len(gaps) == 1

    def test_multiple_roles_independent_gaps(self, engine):
        _register(engine, "w1", role="reviewer", status=WorkerStatus.ON_LEAVE)
        _register(engine, "w2", role="auditor", name="Bob", status=WorkerStatus.ON_LEAVE)
        gaps = engine.detect_coverage_gaps("t1")
        assert len(gaps) == 2

    def test_gap_emits_event(self, spine, engine):
        _register(engine, "w1", status=WorkerStatus.ON_LEAVE)
        before = spine.event_count
        engine.detect_coverage_gaps("t1")
        assert spine.event_count > before

    def test_gap_record_is_frozen(self, engine):
        _register(engine, "w1", status=WorkerStatus.ON_LEAVE)
        gaps = engine.detect_coverage_gaps("t1")
        with pytest.raises(AttributeError):
            gaps[0].gap_id = "changed"

    def test_no_workers_no_gaps(self, engine):
        gaps = engine.detect_coverage_gaps("t1")
        assert len(gaps) == 0

    def test_gap_team_ref_from_first_worker(self, engine):
        _register(engine, "w1", team="alpha", status=WorkerStatus.ON_LEAVE)
        _register(engine, "w2", name="Bob", team="alpha", status=WorkerStatus.ON_LEAVE)
        gaps = engine.detect_coverage_gaps("t1")
        assert gaps[0].team_ref == "alpha"


# =====================================================================
# 12. Load snapshot
# =====================================================================


class TestLoadSnapshot:
    def test_empty_snapshot(self, engine):
        snap = engine.load_snapshot("s1", "t1")
        assert snap.total_workers == 0
        assert snap.active_workers == 0
        assert snap.utilization == 0.0
        assert snap.load_band == LoadBand.IDLE

    def test_snapshot_with_workers(self, engine):
        _register(engine, "w1", max_assign=5)
        _register(engine, "w2", name="Bob", max_assign=5)
        snap = engine.load_snapshot("s1", "t1")
        assert snap.total_workers == 2
        assert snap.active_workers == 2
        assert snap.total_capacity == 10

    def test_snapshot_with_load(self, engine):
        _register(engine, "w1", max_assign=2)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        snap = engine.load_snapshot("s1", "t1")
        assert snap.total_assignments == 1
        assert snap.used_capacity == 1
        assert snap.utilization == 0.5
        assert snap.load_band == LoadBand.MODERATE

    def test_duplicate_raises(self, engine):
        engine.load_snapshot("s1", "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            engine.load_snapshot("s1", "t1")

    def test_load_band_idle(self, engine):
        snap = engine.load_snapshot("s1", "t1")
        assert snap.load_band == LoadBand.IDLE

    def test_load_band_low(self, engine):
        _register(engine, "w1", max_assign=10)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        snap = engine.load_snapshot("s1", "t1")
        assert snap.utilization == 0.1
        assert snap.load_band == LoadBand.LOW

    def test_load_band_moderate(self, engine):
        _register(engine, "w1", max_assign=2)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        snap = engine.load_snapshot("s1", "t1")
        assert snap.utilization == 0.5
        assert snap.load_band == LoadBand.MODERATE

    def test_load_band_high(self, engine):
        _register(engine, "w1", max_assign=5)
        for i in range(4):
            engine.request_assignment(f"r{i}", "t1", f"s{i}", "reviewer")
            engine.decide_assignment(f"d{i}", f"r{i}", "w1")
        snap = engine.load_snapshot("s1", "t1")
        assert snap.utilization == 0.8
        assert snap.load_band == LoadBand.HIGH

    def test_load_band_overloaded(self, engine):
        _register(engine, "w1", max_assign=1)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        snap = engine.load_snapshot("s1", "t1")
        assert snap.utilization == 1.0
        assert snap.load_band == LoadBand.OVERLOADED

    def test_inactive_worker_counted_total_not_active(self, engine):
        _register(engine, "w1", status=WorkerStatus.ON_LEAVE)
        snap = engine.load_snapshot("s1", "t1")
        assert snap.total_workers == 1
        assert snap.active_workers == 0

    def test_cross_tenant_isolation(self, engine):
        _register(engine, "w1", tenant="t1")
        _register(engine, "w2", tenant="t2", name="Bob")
        snap = engine.load_snapshot("s1", "t1")
        assert snap.total_workers == 1

    def test_emits_event(self, spine, engine):
        before = spine.event_count
        engine.load_snapshot("s1", "t1")
        assert spine.event_count == before + 1


# =====================================================================
# 13. Workforce assessment
# =====================================================================


class TestWorkforceAssessment:
    def test_empty_assessment(self, engine):
        a = engine.workforce_assessment("a1", "t1")
        assert a.total_workers == 0
        assert a.active_workers == 0
        assert a.total_roles == 0
        assert a.total_teams == 0
        assert a.total_requests == 0
        assert a.total_decisions == 0
        assert a.total_gaps == 0
        assert a.total_violations == 0

    def test_assessment_counts_workers(self, engine):
        _register(engine, "w1")
        _register(engine, "w2", name="Bob", status=WorkerStatus.ON_LEAVE)
        a = engine.workforce_assessment("a1", "t1")
        assert a.total_workers == 2
        assert a.active_workers == 1

    def test_assessment_counts_roles_and_teams(self, engine):
        _register(engine, "w1", role="reviewer", team="alpha")
        _register(engine, "w2", name="Bob", role="auditor", team="beta")
        a = engine.workforce_assessment("a1", "t1")
        assert a.total_roles == 2
        assert a.total_teams == 2

    def test_assessment_counts_requests_decisions(self, engine):
        _register(engine, "w1")
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        a = engine.workforce_assessment("a1", "t1")
        assert a.total_requests == 1
        assert a.total_decisions == 1

    def test_assessment_counts_gaps(self, engine):
        _register(engine, "w1", status=WorkerStatus.ON_LEAVE)
        engine.detect_coverage_gaps("t1")
        a = engine.workforce_assessment("a1", "t1")
        assert a.total_gaps == 1

    def test_assessment_counts_violations(self, engine):
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.detect_workforce_violations("t1")
        a = engine.workforce_assessment("a1", "t1")
        assert a.total_violations >= 1

    def test_cross_tenant_isolation(self, engine):
        _register(engine, "w1", tenant="t1")
        _register(engine, "w2", tenant="t2", name="Bob")
        a = engine.workforce_assessment("a1", "t1")
        assert a.total_workers == 1

    def test_emits_event(self, spine, engine):
        before = spine.event_count
        engine.workforce_assessment("a1", "t1")
        assert spine.event_count == before + 1


# =====================================================================
# 14. detect_workforce_violations
# =====================================================================


class TestDetectViolations:
    def test_no_violations_clean(self, engine):
        _register(engine, "w1")
        viols = engine.detect_workforce_violations("t1")
        assert len(viols) == 0

    def test_overloaded_worker(self, engine):
        _register(engine, "w1", max_assign=1)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        viols = engine.detect_workforce_violations("t1")
        ops = [v.operation for v in viols]
        assert "overloaded_worker" in ops

    def test_unassigned_request(self, engine):
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        viols = engine.detect_workforce_violations("t1")
        ops = [v.operation for v in viols]
        assert "unassigned_request" in ops

    def test_empty_role(self, engine):
        engine.request_assignment("r1", "t1", "s1", "ghostrole")
        viols = engine.detect_workforce_violations("t1")
        ops = [v.operation for v in viols]
        assert "empty_role" in ops

    def test_idempotent(self, engine):
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        viols1 = engine.detect_workforce_violations("t1")
        viols2 = engine.detect_workforce_violations("t1")
        assert len(viols1) >= 1
        assert len(viols2) == 0  # no NEW violations

    def test_violations_for_tenant(self, engine):
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.detect_workforce_violations("t1")
        result = engine.violations_for_tenant("t1")
        assert len(result) >= 1

    def test_violations_for_tenant_empty(self, engine):
        assert engine.violations_for_tenant("t1") == ()

    def test_violation_count(self, engine):
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.detect_workforce_violations("t1")
        assert engine.violation_count >= 1

    def test_cross_tenant_isolation(self, engine):
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.request_assignment("r2", "t2", "s2", "auditor")
        engine.detect_workforce_violations("t1")
        result = engine.violations_for_tenant("t2")
        assert len(result) == 0

    def test_emits_event(self, spine, engine):
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        before = spine.event_count
        engine.detect_workforce_violations("t1")
        assert spine.event_count > before

    def test_overloaded_only_active(self, engine):
        # Suspended at max should NOT trigger overloaded_worker
        _register(engine, "w1", max_assign=1, status=WorkerStatus.ON_LEAVE)
        viols = engine.detect_workforce_violations("t1")
        ops = [v.operation for v in viols]
        assert "overloaded_worker" not in ops

    def test_multiple_violations_at_once(self, engine):
        _register(engine, "w1", max_assign=1)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        engine.request_assignment("r2", "t1", "s2", "reviewer")
        # r2 is unassigned, w1 is overloaded
        viols = engine.detect_workforce_violations("t1")
        ops = [v.operation for v in viols]
        assert "overloaded_worker" in ops
        assert "unassigned_request" in ops


# =====================================================================
# 15. Closure report
# =====================================================================


class TestClosureReport:
    def test_empty_report(self, engine):
        rpt = engine.closure_report("rpt1", "t1")
        assert rpt.report_id == "rpt1"
        assert rpt.total_workers == 0
        assert rpt.total_role_capacities == 0
        assert rpt.total_team_capacities == 0
        assert rpt.total_requests == 0
        assert rpt.total_decisions == 0
        assert rpt.total_gaps == 0
        assert rpt.total_violations == 0

    def test_report_counts_everything(self, engine):
        _register(engine, "w1")
        engine.register_role_capacity("rc1", "t1", "reviewer")
        engine.register_team_capacity("tc1", "t1", "alpha")
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        rpt = engine.closure_report("rpt1", "t1")
        assert rpt.total_workers == 1
        assert rpt.total_role_capacities == 1
        assert rpt.total_team_capacities == 1
        assert rpt.total_requests == 1
        assert rpt.total_decisions == 1

    def test_cross_tenant_isolation(self, engine):
        _register(engine, "w1", tenant="t1")
        _register(engine, "w2", tenant="t2", name="Bob")
        rpt = engine.closure_report("rpt1", "t1")
        assert rpt.total_workers == 1

    def test_emits_event(self, spine, engine):
        before = spine.event_count
        engine.closure_report("rpt1", "t1")
        assert spine.event_count == before + 1

    def test_closed_at_populated(self, engine):
        rpt = engine.closure_report("rpt1", "t1")
        assert rpt.closed_at  # non-empty string


# =====================================================================
# 16. state_hash
# =====================================================================


class TestStateHash:
    def test_empty_hash_deterministic(self, engine):
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_hash_changes_with_worker(self, engine):
        h1 = engine.state_hash()
        _register(engine)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_changes_with_request(self, engine):
        h1 = engine.state_hash()
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_changes_with_decision(self, engine):
        _register(engine, "w1")
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        h1 = engine.state_hash()
        engine.decide_assignment("d1", "r1", "w1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_changes_with_role_capacity(self, engine):
        h1 = engine.state_hash()
        engine.register_role_capacity("rc1", "t1", "reviewer")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_changes_with_team_capacity(self, engine):
        h1 = engine.state_hash()
        engine.register_team_capacity("tc1", "t1", "alpha")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_changes_with_gap(self, engine):
        _register(engine, "w1", status=WorkerStatus.ON_LEAVE)
        h1 = engine.state_hash()
        engine.detect_coverage_gaps("t1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_changes_with_violation(self, engine):
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        h1 = engine.state_hash()
        engine.detect_workforce_violations("t1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_is_sha256_hex(self, engine):
        h = engine.state_hash()
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_same_state_same_hash(self, spine):
        e1 = WorkforceRuntimeEngine(spine)
        e2 = WorkforceRuntimeEngine(EventSpineEngine())
        _register(e1, "w1")
        _register(e2, "w1")
        assert e1.state_hash() == e2.state_hash()


# =====================================================================
# 17. Properties
# =====================================================================


class TestProperties:
    def test_worker_count(self, engine):
        assert engine.worker_count == 0
        _register(engine, "w1")
        assert engine.worker_count == 1

    def test_role_capacity_count(self, engine):
        assert engine.role_capacity_count == 0
        engine.register_role_capacity("rc1", "t1", "reviewer")
        assert engine.role_capacity_count == 1

    def test_team_capacity_count(self, engine):
        assert engine.team_capacity_count == 0
        engine.register_team_capacity("tc1", "t1", "alpha")
        assert engine.team_capacity_count == 1

    def test_request_count(self, engine):
        assert engine.request_count == 0
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        assert engine.request_count == 1

    def test_decision_count(self, engine):
        assert engine.decision_count == 0
        _register(engine, "w1")
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        assert engine.decision_count == 1

    def test_gap_count(self, engine):
        assert engine.gap_count == 0
        _register(engine, "w1", status=WorkerStatus.ON_LEAVE)
        engine.detect_coverage_gaps("t1")
        assert engine.gap_count == 1

    def test_violation_count(self, engine):
        assert engine.violation_count == 0
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.detect_workforce_violations("t1")
        assert engine.violation_count >= 1


# =====================================================================
# 18. Capacity status derivation (edge cases)
# =====================================================================


class TestCapacityStatusDerivation:
    def test_zero_utilization(self, engine):
        status = WorkforceRuntimeEngine._derive_capacity_status(0.0)
        assert status == CapacityStatus.EMPTY

    def test_0_01_utilization(self, engine):
        status = WorkforceRuntimeEngine._derive_capacity_status(0.01)
        assert status == CapacityStatus.NOMINAL

    def test_0_69_utilization(self, engine):
        status = WorkforceRuntimeEngine._derive_capacity_status(0.69)
        assert status == CapacityStatus.NOMINAL

    def test_0_7_utilization(self, engine):
        status = WorkforceRuntimeEngine._derive_capacity_status(0.7)
        assert status == CapacityStatus.STRAINED

    def test_0_89_utilization(self, engine):
        status = WorkforceRuntimeEngine._derive_capacity_status(0.89)
        assert status == CapacityStatus.STRAINED

    def test_0_9_utilization(self, engine):
        status = WorkforceRuntimeEngine._derive_capacity_status(0.9)
        assert status == CapacityStatus.CRITICAL

    def test_0_99_utilization(self, engine):
        status = WorkforceRuntimeEngine._derive_capacity_status(0.99)
        assert status == CapacityStatus.CRITICAL

    def test_1_0_utilization(self, engine):
        status = WorkforceRuntimeEngine._derive_capacity_status(1.0)
        assert status == CapacityStatus.OVERLOADED


# =====================================================================
# 19. Load band derivation (edge cases)
# =====================================================================


class TestLoadBandDerivation:
    def test_zero_idle(self, engine):
        band = WorkforceRuntimeEngine._derive_load_band(0.0)
        assert band == LoadBand.IDLE

    def test_0_01_low(self, engine):
        band = WorkforceRuntimeEngine._derive_load_band(0.01)
        assert band == LoadBand.LOW

    def test_0_49_low(self, engine):
        band = WorkforceRuntimeEngine._derive_load_band(0.49)
        assert band == LoadBand.LOW

    def test_0_5_moderate(self, engine):
        band = WorkforceRuntimeEngine._derive_load_band(0.5)
        assert band == LoadBand.MODERATE

    def test_0_79_moderate(self, engine):
        band = WorkforceRuntimeEngine._derive_load_band(0.79)
        assert band == LoadBand.MODERATE

    def test_0_8_high(self, engine):
        band = WorkforceRuntimeEngine._derive_load_band(0.8)
        assert band == LoadBand.HIGH

    def test_0_99_high(self, engine):
        band = WorkforceRuntimeEngine._derive_load_band(0.99)
        assert band == LoadBand.HIGH

    def test_1_0_overloaded(self, engine):
        band = WorkforceRuntimeEngine._derive_load_band(1.0)
        assert band == LoadBand.OVERLOADED


# =====================================================================
# GOLDEN SCENARIO 1: Service request routed to lowest-load qualified worker
# =====================================================================


class TestGoldenScenario1_LowestLoadRouting:
    """Validate that a service request goes to the least loaded qualified worker."""

    def test_routes_to_least_loaded(self, engine):
        _register(engine, "w1", max_assign=5)
        _register(engine, "w2", name="Bob", max_assign=5)
        _register(engine, "w3", name="Charlie", max_assign=5)
        # Load w1 with 3, w2 with 1, w3 with 0
        for i in range(3):
            engine.request_assignment(f"load-r{i}", "t1", f"ls{i}", "reviewer")
            engine.decide_assignment(f"load-d{i}", f"load-r{i}", "w1")
        engine.request_assignment("load-r3", "t1", "ls3", "reviewer")
        engine.decide_assignment("load-d3", "load-r3", "w2")
        # New request should go to w3 (0 assignments)
        engine.request_assignment("new-req", "t1", "scope-new", "reviewer")
        dec = engine.assign_to_lowest_load("new-dec", "new-req")
        assert dec.worker_id == "w3"
        assert dec.disposition == AssignmentDisposition.ASSIGNED

    def test_second_request_balanced(self, engine):
        _register(engine, "w1", max_assign=10)
        _register(engine, "w2", name="Bob", max_assign=10)
        # Both at 0 -- first goes to one, second to the other
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        d1 = engine.assign_to_lowest_load("d1", "r1")
        engine.request_assignment("r2", "t1", "s2", "reviewer")
        d2 = engine.assign_to_lowest_load("d2", "r2")
        assert d1.worker_id != d2.worker_id

    def test_ignores_other_role_workers(self, engine):
        _register(engine, "w1", role="reviewer", max_assign=5)
        _register(engine, "w2", name="Bob", role="auditor", max_assign=5)
        # w2 has 0 load but wrong role
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        dec = engine.assign_to_lowest_load("d1", "r1")
        assert dec.worker_id == "w1"

    def test_full_cycle_with_snapshot(self, engine):
        _register(engine, "w1", max_assign=3)
        _register(engine, "w2", name="Bob", max_assign=3)
        # Assign 3 requests via lowest-load
        for i in range(3):
            engine.request_assignment(f"r{i}", "t1", f"s{i}", "reviewer")
            engine.assign_to_lowest_load(f"d{i}", f"r{i}")
        # Should be w1=2, w2=1 or w1=1, w2=2 (balanced)
        w1 = engine.get_worker("w1")
        w2 = engine.get_worker("w2")
        assert abs(w1.current_assignments - w2.current_assignments) <= 1
        snap = engine.load_snapshot("snap1", "t1")
        assert snap.total_assignments == 3

    def test_five_requests_round_robin_like(self, engine):
        _register(engine, "w1", max_assign=10)
        _register(engine, "w2", name="Bob", max_assign=10)
        for i in range(5):
            engine.request_assignment(f"r{i}", "t1", f"s{i}", "reviewer")
            engine.assign_to_lowest_load(f"d{i}", f"r{i}")
        w1 = engine.get_worker("w1")
        w2 = engine.get_worker("w2")
        assert w1.current_assignments + w2.current_assignments == 5
        assert abs(w1.current_assignments - w2.current_assignments) <= 1


# =====================================================================
# GOLDEN SCENARIO 2: Missing coverage creates escalation
# =====================================================================


class TestGoldenScenario2_CoverageEscalation:
    """All workers unavailable for a role triggers escalation and gap detection."""

    def test_all_on_leave_escalates(self, engine):
        _register(engine, "w1", status=WorkerStatus.ON_LEAVE)
        _register(engine, "w2", name="Bob", status=WorkerStatus.SUSPENDED)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        dec = engine.assign_to_lowest_load("d1", "r1")
        assert dec.disposition == AssignmentDisposition.ESCALATED
        assert dec.worker_id == "escalation"

    def test_gap_detected_after_escalation(self, engine):
        _register(engine, "w1", status=WorkerStatus.ON_LEAVE)
        _register(engine, "w2", name="Bob", status=WorkerStatus.ON_LEAVE)
        _register(engine, "w3", name="Charlie", status=WorkerStatus.ON_LEAVE)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.assign_to_lowest_load("d1", "r1")
        gaps = engine.detect_coverage_gaps("t1")
        assert len(gaps) == 1
        assert gaps[0].status == CoverageStatus.CRITICAL_GAP
        assert gaps[0].escalation_mode == EscalationMode.MANAGER

    def test_escalation_then_assessment(self, engine):
        _register(engine, "w1", status=WorkerStatus.ON_LEAVE)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.assign_to_lowest_load("d1", "r1")
        engine.detect_coverage_gaps("t1")
        a = engine.workforce_assessment("a1", "t1")
        assert a.total_gaps == 1
        assert a.total_decisions == 1

    def test_gap_only_for_affected_role(self, engine):
        _register(engine, "w1", role="reviewer", status=WorkerStatus.ON_LEAVE)
        _register(engine, "w2", role="auditor", name="Bob", status=WorkerStatus.ACTIVE)
        gaps = engine.detect_coverage_gaps("t1")
        assert len(gaps) == 1
        assert gaps[0].role_ref == "reviewer"


# =====================================================================
# GOLDEN SCENARIO 3: Overloaded reviewer triggers alternate assignment
# =====================================================================


class TestGoldenScenario3_OverloadedAlternate:
    """When one reviewer is at max, work is routed to another."""

    def test_overloaded_worker_skipped(self, engine):
        _register(engine, "w1", max_assign=2)
        _register(engine, "w2", name="Bob", max_assign=5)
        # Fill w1 to max
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        engine.request_assignment("r2", "t1", "s2", "reviewer")
        engine.decide_assignment("d2", "r2", "w1")
        # Next auto-assign should go to w2
        engine.request_assignment("r3", "t1", "s3", "reviewer")
        dec = engine.assign_to_lowest_load("d3", "r3")
        assert dec.worker_id == "w2"

    def test_manual_assign_to_overloaded_fails(self, engine):
        _register(engine, "w1", max_assign=1)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        engine.request_assignment("r2", "t1", "s2", "reviewer")
        with pytest.raises(RuntimeCoreInvariantError, match="max assignments"):
            engine.decide_assignment("d2", "r2", "w1")

    def test_violation_detected_for_overloaded(self, engine):
        _register(engine, "w1", max_assign=1)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        viols = engine.detect_workforce_violations("t1")
        ops = [v.operation for v in viols]
        assert "overloaded_worker" in ops

    def test_escalates_when_all_overloaded(self, engine):
        _register(engine, "w1", max_assign=1)
        _register(engine, "w2", name="Bob", max_assign=1)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        engine.request_assignment("r2", "t1", "s2", "reviewer")
        engine.decide_assignment("d2", "r2", "w2")
        engine.request_assignment("r3", "t1", "s3", "reviewer")
        dec = engine.assign_to_lowest_load("d3", "r3")
        assert dec.disposition == AssignmentDisposition.ESCALATED

    def test_overloaded_snapshot(self, engine):
        _register(engine, "w1", max_assign=1)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        snap = engine.load_snapshot("s1", "t1")
        assert snap.utilization == 1.0
        assert snap.load_band == LoadBand.OVERLOADED


# =====================================================================
# GOLDEN SCENARIO 4: Case review board pull reflects current availability
# =====================================================================


class TestGoldenScenario4_ReviewBoardAvailability:
    """Review board queries should reflect real-time availability."""

    def test_available_changes_with_status(self, engine):
        _register(engine, "w1")
        _register(engine, "w2", name="Bob")
        _register(engine, "w3", name="Charlie")
        assert len(engine.available_workers_for_role("t1", "reviewer")) == 3
        engine.update_worker_status("w2", WorkerStatus.ON_LEAVE)
        assert len(engine.available_workers_for_role("t1", "reviewer")) == 2

    def test_available_changes_with_load(self, engine):
        _register(engine, "w1", max_assign=1)
        _register(engine, "w2", name="Bob", max_assign=1)
        assert len(engine.available_workers_for_role("t1", "reviewer")) == 2
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        assert len(engine.available_workers_for_role("t1", "reviewer")) == 1

    def test_role_capacity_snapshot_reflects_state(self, engine):
        _register(engine, "w1", max_assign=2)
        _register(engine, "w2", name="Bob", max_assign=2)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        rc = engine.register_role_capacity("rc1", "t1", "reviewer")
        assert rc.total_workers == 2
        assert rc.available_workers == 2  # w2 available, w1 has 1/2
        assert rc.used_capacity == 1
        assert rc.status == CapacityStatus.NOMINAL

    def test_board_sees_zero_after_all_maxed(self, engine):
        _register(engine, "w1", max_assign=1)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        assert len(engine.available_workers_for_role("t1", "reviewer")) == 0

    def test_assessment_after_status_changes(self, engine):
        _register(engine, "w1")
        _register(engine, "w2", name="Bob")
        engine.update_worker_status("w1", WorkerStatus.ON_LEAVE)
        a = engine.workforce_assessment("a1", "t1")
        assert a.total_workers == 2
        assert a.active_workers == 1

    def test_team_capacity_reflects_availability(self, engine):
        _register(engine, "w1", team="alpha", max_assign=2)
        _register(engine, "w2", name="Bob", team="alpha", max_assign=2)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        engine.request_assignment("r2", "t1", "s2", "reviewer")
        engine.decide_assignment("d2", "r2", "w1")
        tc = engine.register_team_capacity("tc1", "t1", "alpha")
        assert tc.available_members == 1  # w1 is at max
        assert tc.used_capacity == 2

    def test_workers_for_role_includes_all_statuses(self, engine):
        _register(engine, "w1")
        _register(engine, "w2", name="Bob", status=WorkerStatus.ON_LEAVE)
        result = engine.workers_for_role("t1", "reviewer")
        assert len(result) == 2

    def test_available_excludes_all_unavailable_statuses(self, engine):
        _register(engine, "w1", status=WorkerStatus.ON_LEAVE)
        _register(engine, "w2", name="Bob", status=WorkerStatus.UNAVAILABLE)
        _register(engine, "w3", name="Charlie", status=WorkerStatus.SUSPENDED)
        _register(engine, "w4", name="Dave", status=WorkerStatus.OFFBOARDED)
        assert len(engine.available_workers_for_role("t1", "reviewer")) == 0


# =====================================================================
# GOLDEN SCENARIO 5: Remediation ownership reassigns after capacity loss
# =====================================================================


class TestGoldenScenario5_RemediationReassignment:
    """Worker going ON_LEAVE means new assignment must go elsewhere."""

    def test_reassign_after_leave(self, engine):
        _register(engine, "w1", max_assign=5)
        _register(engine, "w2", name="Bob", max_assign=5)
        # w1 gets initial assignment
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        d1 = engine.assign_to_lowest_load("d1", "r1")
        original_worker = d1.worker_id
        # That worker goes on leave
        engine.update_worker_status(original_worker, WorkerStatus.ON_LEAVE)
        # Next assignment should go to the other worker
        engine.request_assignment("r2", "t1", "s2", "reviewer")
        d2 = engine.assign_to_lowest_load("d2", "r2")
        other = "w2" if original_worker == "w1" else "w1"
        assert d2.worker_id == other

    def test_coverage_gap_after_both_leave(self, engine):
        _register(engine, "w1", max_assign=5)
        _register(engine, "w2", name="Bob", max_assign=5)
        engine.update_worker_status("w1", WorkerStatus.ON_LEAVE)
        engine.update_worker_status("w2", WorkerStatus.ON_LEAVE)
        gaps = engine.detect_coverage_gaps("t1")
        assert len(gaps) == 1

    def test_escalation_after_capacity_loss(self, engine):
        _register(engine, "w1", max_assign=1)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        # w1 goes on leave after being assigned
        engine.update_worker_status("w1", WorkerStatus.ON_LEAVE)
        # Next request must escalate
        engine.request_assignment("r2", "t1", "s2", "reviewer")
        d2 = engine.assign_to_lowest_load("d2", "r2")
        assert d2.disposition == AssignmentDisposition.ESCALATED

    def test_new_worker_fills_gap(self, engine):
        _register(engine, "w1", max_assign=5)
        engine.update_worker_status("w1", WorkerStatus.ON_LEAVE)
        # Register a replacement
        _register(engine, "w2", name="Bob", max_assign=5)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        dec = engine.assign_to_lowest_load("d1", "r1")
        assert dec.worker_id == "w2"
        assert dec.disposition == AssignmentDisposition.ASSIGNED

    def test_leave_preserves_existing_assignments(self, engine):
        _register(engine, "w1", max_assign=5)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        engine.update_worker_status("w1", WorkerStatus.ON_LEAVE)
        w = engine.get_worker("w1")
        assert w.current_assignments == 1

    def test_return_from_leave_restores_availability(self, engine):
        _register(engine, "w1", max_assign=5)
        engine.update_worker_status("w1", WorkerStatus.ON_LEAVE)
        assert len(engine.available_workers_for_role("t1", "reviewer")) == 0
        engine.update_worker_status("w1", WorkerStatus.ACTIVE)
        assert len(engine.available_workers_for_role("t1", "reviewer")) == 1

    def test_offboarded_cannot_return(self, engine):
        _register(engine, "w1")
        engine.update_worker_status("w1", WorkerStatus.OFFBOARDED)
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.update_worker_status("w1", WorkerStatus.ACTIVE)
        assert len(engine.available_workers_for_role("t1", "reviewer")) == 0

    def test_closure_report_after_reassignment(self, engine):
        _register(engine, "w1", max_assign=5)
        _register(engine, "w2", name="Bob", max_assign=5)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.assign_to_lowest_load("d1", "r1")
        engine.update_worker_status("w1", WorkerStatus.ON_LEAVE)
        engine.request_assignment("r2", "t1", "s2", "reviewer")
        engine.assign_to_lowest_load("d2", "r2")
        rpt = engine.closure_report("rpt1", "t1")
        assert rpt.total_requests == 2
        assert rpt.total_decisions == 2


# =====================================================================
# GOLDEN SCENARIO 6: Replay/restore preserves worker load and
#   assignment history (state_hash consistency)
# =====================================================================


class TestGoldenScenario6_ReplayRestore:
    """Re-applying the same operations produces the same state hash."""

    def _build_scenario(self, eng: WorkforceRuntimeEngine):
        """Build a deterministic scenario and return state hash."""
        _register(eng, "w1", max_assign=5)
        _register(eng, "w2", name="Bob", max_assign=5)
        _register(eng, "w3", name="Charlie", max_assign=5, role="auditor")
        eng.request_assignment("r1", "t1", "s1", "reviewer")
        eng.decide_assignment("d1", "r1", "w1")
        eng.request_assignment("r2", "t1", "s2", "reviewer")
        eng.assign_to_lowest_load("d2", "r2")
        eng.request_assignment("r3", "t1", "s3", "auditor")
        eng.assign_to_lowest_load("d3", "r3")
        eng.register_role_capacity("rc1", "t1", "reviewer")
        eng.register_team_capacity("tc1", "t1", "alpha")
        eng.update_worker_status("w1", WorkerStatus.ON_LEAVE)
        eng.detect_coverage_gaps("t1")
        eng.detect_workforce_violations("t1")
        return eng.state_hash()

    def test_same_operations_same_hash(self):
        e1 = WorkforceRuntimeEngine(EventSpineEngine())
        e2 = WorkforceRuntimeEngine(EventSpineEngine())
        h1 = self._build_scenario(e1)
        h2 = self._build_scenario(e2)
        assert h1 == h2

    def test_different_operations_different_hash(self):
        e1 = WorkforceRuntimeEngine(EventSpineEngine())
        e2 = WorkforceRuntimeEngine(EventSpineEngine())
        h1 = self._build_scenario(e1)
        _register(e2, "w1", max_assign=5)
        h2 = e2.state_hash()
        assert h1 != h2

    def test_worker_load_preserved_in_hash(self):
        e1 = WorkforceRuntimeEngine(EventSpineEngine())
        _register(e1, "w1", max_assign=5)
        e1.request_assignment("r1", "t1", "s1", "reviewer")
        e1.decide_assignment("d1", "r1", "w1")
        h_after_assign = e1.state_hash()
        # Verify worker load is reflected
        w = e1.get_worker("w1")
        assert w.current_assignments == 1
        # A fresh engine with same ops
        e2 = WorkforceRuntimeEngine(EventSpineEngine())
        _register(e2, "w1", max_assign=5)
        e2.request_assignment("r1", "t1", "s1", "reviewer")
        e2.decide_assignment("d1", "r1", "w1")
        assert e2.state_hash() == h_after_assign

    def test_hash_after_gap_detection(self):
        e1 = WorkforceRuntimeEngine(EventSpineEngine())
        _register(e1, "w1", status=WorkerStatus.ON_LEAVE)
        h_before = e1.state_hash()
        e1.detect_coverage_gaps("t1")
        h_after = e1.state_hash()
        assert h_before != h_after

    def test_hash_after_violation_detection(self):
        e1 = WorkforceRuntimeEngine(EventSpineEngine())
        e1.request_assignment("r1", "t1", "s1", "reviewer")
        h_before = e1.state_hash()
        e1.detect_workforce_violations("t1")
        h_after = e1.state_hash()
        assert h_before != h_after

    def test_full_lifecycle_hash_consistency(self):
        """Full lifecycle: register, assign, leave, detect, assess, close -- same hash twice."""
        def run():
            eng = WorkforceRuntimeEngine(EventSpineEngine())
            _register(eng, "w1", max_assign=3)
            _register(eng, "w2", name="Bob", max_assign=3)
            for i in range(4):
                eng.request_assignment(f"r{i}", "t1", f"s{i}", "reviewer")
                eng.assign_to_lowest_load(f"d{i}", f"r{i}")
            eng.update_worker_status("w1", WorkerStatus.ON_LEAVE)
            eng.detect_coverage_gaps("t1")
            eng.detect_workforce_violations("t1")
            eng.register_role_capacity("rc1", "t1", "reviewer")
            eng.register_team_capacity("tc1", "t1", "alpha")
            return eng.state_hash()
        assert run() == run()


# =====================================================================
# 20. Multi-tenant isolation
# =====================================================================


class TestMultiTenantIsolation:
    def test_workers_isolated(self, engine):
        _register(engine, "w1", tenant="t1")
        _register(engine, "w2", tenant="t2", name="Bob")
        assert len(engine.workers_for_tenant("t1")) == 1
        assert len(engine.workers_for_tenant("t2")) == 1

    def test_requests_isolated(self, engine):
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.request_assignment("r2", "t2", "s2", "auditor")
        assert len(engine.requests_for_tenant("t1")) == 1
        assert len(engine.requests_for_tenant("t2")) == 1

    def test_gaps_isolated(self, engine):
        _register(engine, "w1", tenant="t1", status=WorkerStatus.ON_LEAVE)
        _register(engine, "w2", tenant="t2", name="Bob")
        engine.detect_coverage_gaps("t1")
        engine.detect_coverage_gaps("t2")
        assert len(engine.gaps_for_tenant("t1")) == 1
        assert len(engine.gaps_for_tenant("t2")) == 0

    def test_violations_isolated(self, engine):
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.detect_workforce_violations("t1")
        assert len(engine.violations_for_tenant("t1")) >= 1
        assert len(engine.violations_for_tenant("t2")) == 0

    def test_role_capacities_isolated(self, engine):
        engine.register_role_capacity("rc1", "t1", "reviewer")
        engine.register_role_capacity("rc2", "t2", "reviewer")
        assert len(engine.role_capacities_for_tenant("t1")) == 1
        assert len(engine.role_capacities_for_tenant("t2")) == 1

    def test_team_capacities_isolated(self, engine):
        engine.register_team_capacity("tc1", "t1", "alpha")
        engine.register_team_capacity("tc2", "t2", "alpha")
        assert len(engine.team_capacities_for_tenant("t1")) == 1
        assert len(engine.team_capacities_for_tenant("t2")) == 1

    def test_closure_reports_isolated(self, engine):
        _register(engine, "w1", tenant="t1")
        _register(engine, "w2", tenant="t2", name="Bob")
        rpt1 = engine.closure_report("rpt1", "t1")
        rpt2 = engine.closure_report("rpt2", "t2")
        assert rpt1.total_workers == 1
        assert rpt2.total_workers == 1

    def test_load_snapshots_isolated(self, engine):
        _register(engine, "w1", tenant="t1")
        _register(engine, "w2", tenant="t2", name="Bob")
        s1 = engine.load_snapshot("s1", "t1")
        s2 = engine.load_snapshot("s2", "t2")
        assert s1.total_workers == 1
        assert s2.total_workers == 1


# =====================================================================
# 21. Edge cases and integration
# =====================================================================


class TestEdgeCasesIntegration:
    def test_deferred_then_reassign(self, engine):
        _register(engine, "w1")
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", disposition=AssignmentDisposition.DEFERRED)
        # Can make another decision on the same request
        dec2 = engine.decide_assignment("d2", "r1", "w1", AssignmentDisposition.ASSIGNED)
        assert dec2.disposition == AssignmentDisposition.ASSIGNED
        decs = engine.decisions_for_request("r1")
        assert len(decs) == 2

    def test_multiple_decisions_same_request(self, engine):
        _register(engine, "w1", max_assign=5)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", disposition=AssignmentDisposition.REJECTED)
        engine.decide_assignment("d2", "r1", "w1", AssignmentDisposition.ASSIGNED)
        decs = engine.decisions_for_request("r1")
        assert len(decs) == 2

    def test_max_1_assignment(self, engine):
        _register(engine, "w1", max_assign=1)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        assert engine.get_worker("w1").current_assignments == 1
        engine.request_assignment("r2", "t1", "s2", "reviewer")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.decide_assignment("d2", "r2", "w1")

    def test_large_max_assignments(self, engine):
        _register(engine, "w1", max_assign=100)
        for i in range(50):
            engine.request_assignment(f"r{i}", "t1", f"s{i}", "reviewer")
            engine.decide_assignment(f"d{i}", f"r{i}", "w1")
        w = engine.get_worker("w1")
        assert w.current_assignments == 50
        assert len(engine.available_workers_for_role("t1", "reviewer")) == 1

    def test_worker_with_different_teams(self, engine):
        _register(engine, "w1", team="alpha")
        _register(engine, "w2", name="Bob", team="beta")
        tc_a = engine.register_team_capacity("tc1", "t1", "alpha")
        tc_b = engine.register_team_capacity("tc2", "t1", "beta")
        assert tc_a.total_members == 1
        assert tc_b.total_members == 1

    def test_no_request_no_violation(self, engine):
        _register(engine, "w1")
        viols = engine.detect_workforce_violations("t1")
        assert len(viols) == 0

    def test_assigned_request_no_unassigned_violation(self, engine):
        _register(engine, "w1")
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        viols = engine.detect_workforce_violations("t1")
        ops = [v.operation for v in viols]
        assert "unassigned_request" not in ops

    def test_empty_role_violation_only_with_requests(self, engine):
        # No requests for a missing role: no violation
        viols = engine.detect_workforce_violations("t1")
        assert "empty_role" not in [v.operation for v in viols]

    def test_assessment_with_complex_state(self, engine):
        _register(engine, "w1", max_assign=2)
        _register(engine, "w2", name="Bob", max_assign=2, role="auditor")
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        engine.request_assignment("r2", "t1", "s2", "auditor")
        engine.request_assignment("r3", "t1", "s3", "ghostrole")
        engine.detect_workforce_violations("t1")
        engine.detect_coverage_gaps("t1")
        a = engine.workforce_assessment("a1", "t1")
        assert a.total_workers == 2
        assert a.total_roles == 2
        assert a.total_teams == 1
        assert a.total_requests == 3
        assert a.total_decisions == 1

    def test_snapshot_after_full_lifecycle(self, engine):
        _register(engine, "w1", max_assign=3)
        _register(engine, "w2", name="Bob", max_assign=3)
        for i in range(3):
            engine.request_assignment(f"r{i}", "t1", f"s{i}", "reviewer")
            engine.assign_to_lowest_load(f"d{i}", f"r{i}")
        engine.update_worker_status("w1", WorkerStatus.ON_LEAVE)
        snap = engine.load_snapshot("s1", "t1")
        assert snap.total_assignments == 3
        # w1 on leave is not active
        assert snap.active_workers == 1

    def test_event_spine_receives_all_events(self, spine, engine):
        _register(engine, "w1")
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        engine.register_role_capacity("rc1", "t1", "reviewer")
        engine.register_team_capacity("tc1", "t1", "alpha")
        engine.detect_coverage_gaps("t1")
        engine.detect_workforce_violations("t1")
        engine.load_snapshot("s1", "t1")
        engine.workforce_assessment("a1", "t1")
        engine.closure_report("rpt1", "t1")
        # At minimum: register_worker + request + decision + rc + tc + violations + snapshot + assessment + closure = 9
        assert spine.event_count >= 9

    def test_state_hash_empty_engine(self, engine):
        h = engine.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64

    def test_closure_report_counts_gaps_and_violations(self, engine):
        _register(engine, "w1", max_assign=1, status=WorkerStatus.ON_LEAVE)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.detect_coverage_gaps("t1")
        engine.detect_workforce_violations("t1")
        rpt = engine.closure_report("rpt1", "t1")
        assert rpt.total_gaps == 1
        assert rpt.total_violations >= 1


# =====================================================================
# 22. Stress / volume tests
# =====================================================================


class TestVolumeStress:
    def test_ten_workers_ten_requests(self, engine):
        for i in range(10):
            _register(engine, f"w{i}", name=f"Worker{i}", max_assign=5)
        for i in range(10):
            engine.request_assignment(f"r{i}", "t1", f"s{i}", "reviewer")
            engine.assign_to_lowest_load(f"d{i}", f"r{i}")
        assert engine.worker_count == 10
        assert engine.request_count == 10
        assert engine.decision_count == 10
        # Each worker should have exactly 1 assignment
        for i in range(10):
            w = engine.get_worker(f"w{i}")
            assert w.current_assignments == 1

    def test_twenty_requests_two_workers(self, engine):
        _register(engine, "w1", max_assign=10)
        _register(engine, "w2", name="Bob", max_assign=10)
        for i in range(20):
            engine.request_assignment(f"r{i}", "t1", f"s{i}", "reviewer")
            engine.assign_to_lowest_load(f"d{i}", f"r{i}")
        w1 = engine.get_worker("w1")
        w2 = engine.get_worker("w2")
        assert w1.current_assignments == 10
        assert w2.current_assignments == 10

    def test_five_roles_five_teams(self, engine):
        roles = ["reviewer", "auditor", "analyst", "admin", "manager"]
        teams = ["alpha", "beta", "gamma", "delta", "epsilon"]
        for i, (role, team) in enumerate(zip(roles, teams)):
            _register(engine, f"w{i}", name=f"W{i}", role=role, team=team, max_assign=3)
        for i, role in enumerate(roles):
            engine.request_assignment(f"r{i}", "t1", f"s{i}", role)
            engine.assign_to_lowest_load(f"d{i}", f"r{i}")
        assert engine.worker_count == 5
        assert engine.decision_count == 5

    def test_all_capacities_registered(self, engine):
        roles = ["reviewer", "auditor"]
        teams = ["alpha", "beta"]
        for i, role in enumerate(roles):
            _register(engine, f"w{i}", name=f"W{i}", role=role, team=teams[i])
        for i, role in enumerate(roles):
            engine.register_role_capacity(f"rc{i}", "t1", role)
        for i, team in enumerate(teams):
            engine.register_team_capacity(f"tc{i}", "t1", team)
        assert engine.role_capacity_count == 2
        assert engine.team_capacity_count == 2


# =====================================================================
# 23. Escalation with worker_id="escalation"
# =====================================================================


class TestEscalationWorkerIdHandling:
    def test_escalated_decision_worker_id(self, engine):
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        dec = engine.assign_to_lowest_load("d1", "r1")
        assert dec.worker_id == "escalation"
        assert dec.disposition == AssignmentDisposition.ESCALATED

    def test_manual_escalation(self, engine):
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        dec = engine.decide_assignment("d1", "r1", disposition=AssignmentDisposition.ESCALATED)
        assert dec.worker_id == "none"

    def test_decisions_for_worker_escalation(self, engine):
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.assign_to_lowest_load("d1", "r1")
        decs = engine.decisions_for_worker("escalation")
        assert len(decs) == 1


# =====================================================================
# 24. Worker status transitions
# =====================================================================


class TestStatusTransitions:
    def test_active_to_every_status(self, engine):
        for i, st in enumerate(WorkerStatus):
            _register(engine, f"w{i}", name=f"W{i}")
            engine.update_worker_status(f"w{i}", st)
            assert engine.get_worker(f"w{i}").status == st

    def test_on_leave_to_every_non_terminal(self, engine):
        for i, st in enumerate([WorkerStatus.ACTIVE, WorkerStatus.UNAVAILABLE, WorkerStatus.SUSPENDED]):
            _register(engine, f"w{i}", name=f"W{i}", status=WorkerStatus.ON_LEAVE)
            engine.update_worker_status(f"w{i}", st)
            assert engine.get_worker(f"w{i}").status == st

    def test_suspended_to_active(self, engine):
        _register(engine, "w1", status=WorkerStatus.SUSPENDED)
        engine.update_worker_status("w1", WorkerStatus.ACTIVE)
        assert engine.get_worker("w1").status == WorkerStatus.ACTIVE

    def test_unavailable_to_active(self, engine):
        _register(engine, "w1", status=WorkerStatus.UNAVAILABLE)
        engine.update_worker_status("w1", WorkerStatus.ACTIVE)
        assert engine.get_worker("w1").status == WorkerStatus.ACTIVE

    def test_double_status_update(self, engine):
        _register(engine, "w1")
        engine.update_worker_status("w1", WorkerStatus.ON_LEAVE)
        engine.update_worker_status("w1", WorkerStatus.ACTIVE)
        assert engine.get_worker("w1").status == WorkerStatus.ACTIVE

    def test_same_status_noop(self, engine):
        _register(engine, "w1")
        w = engine.update_worker_status("w1", WorkerStatus.ACTIVE)
        assert w.status == WorkerStatus.ACTIVE


# =====================================================================
# 25. Additional gap detection edge cases
# =====================================================================


class TestGapEdgeCases:
    def test_gap_when_all_offboarded(self, engine):
        _register(engine, "w1", status=WorkerStatus.OFFBOARDED)
        gaps = engine.detect_coverage_gaps("t1")
        assert len(gaps) == 1

    def test_gap_when_mix_unavailable(self, engine):
        _register(engine, "w1", status=WorkerStatus.SUSPENDED)
        _register(engine, "w2", name="Bob", status=WorkerStatus.ON_LEAVE)
        gaps = engine.detect_coverage_gaps("t1")
        assert len(gaps) == 1
        assert gaps[0].status == CoverageStatus.GAP  # 2 workers < 3

    def test_critical_gap_threshold(self, engine):
        for i in range(4):
            _register(engine, f"w{i}", name=f"W{i}", status=WorkerStatus.ON_LEAVE)
        gaps = engine.detect_coverage_gaps("t1")
        assert gaps[0].status == CoverageStatus.CRITICAL_GAP

    def test_no_gap_one_active_of_many(self, engine):
        _register(engine, "w1")
        _register(engine, "w2", name="Bob", status=WorkerStatus.ON_LEAVE)
        _register(engine, "w3", name="Charlie", status=WorkerStatus.ON_LEAVE)
        gaps = engine.detect_coverage_gaps("t1")
        assert len(gaps) == 0  # w1 is available

    def test_gap_required_workers_always_1(self, engine):
        _register(engine, "w1", status=WorkerStatus.ON_LEAVE)
        gaps = engine.detect_coverage_gaps("t1")
        assert gaps[0].required_workers == 1

    def test_gap_available_workers_always_0(self, engine):
        _register(engine, "w1", status=WorkerStatus.ON_LEAVE)
        gaps = engine.detect_coverage_gaps("t1")
        assert gaps[0].available_workers == 0


# =====================================================================
# 26. Snapshot duplicate handling
# =====================================================================


class TestSnapshotDuplicates:
    def test_duplicate_snapshot_id(self, engine):
        engine.load_snapshot("s1", "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            engine.load_snapshot("s1", "t1")

    def test_different_ids_same_tenant(self, engine):
        s1 = engine.load_snapshot("s1", "t1")
        s2 = engine.load_snapshot("s2", "t1")
        assert s1.snapshot_id != s2.snapshot_id

    def test_different_ids_different_tenants(self, engine):
        s1 = engine.load_snapshot("s1", "t1")
        s2 = engine.load_snapshot("s2", "t2")
        assert s1.snapshot_id == "s1"
        assert s2.snapshot_id == "s2"


# =====================================================================
# 27. Complex multi-step workflows
# =====================================================================


class TestComplexWorkflows:
    def test_full_onboard_assign_offboard_cycle(self, engine):
        # Onboard
        _register(engine, "w1", max_assign=3)
        # Assign work
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        assert engine.get_worker("w1").current_assignments == 1
        # More work
        engine.request_assignment("r2", "t1", "s2", "reviewer")
        engine.decide_assignment("d2", "r2", "w1")
        # Offboard
        engine.update_worker_status("w1", WorkerStatus.OFFBOARDED)
        assert engine.get_worker("w1").status == WorkerStatus.OFFBOARDED
        # Cannot assign more
        engine.request_assignment("r3", "t1", "s3", "reviewer")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.decide_assignment("d3", "r3", "w1")

    def test_coverage_gap_then_hire_then_close(self, engine):
        _register(engine, "w1", status=WorkerStatus.ON_LEAVE)
        engine.detect_coverage_gaps("t1")
        assert engine.gap_count == 1
        # Hire replacement
        _register(engine, "w2", name="Bob")
        # Assign work to new hire
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        dec = engine.assign_to_lowest_load("d1", "r1")
        assert dec.worker_id == "w2"
        # Close report
        rpt = engine.closure_report("rpt1", "t1")
        assert rpt.total_workers == 2
        assert rpt.total_gaps == 1
        assert rpt.total_decisions == 1

    def test_multi_role_capacity_assessment(self, engine):
        _register(engine, "w1", role="reviewer", max_assign=5)
        _register(engine, "w2", name="Bob", role="auditor", max_assign=5)
        engine.register_role_capacity("rc1", "t1", "reviewer")
        engine.register_role_capacity("rc2", "t1", "auditor")
        rc1 = engine.get_role_capacity("rc1")
        rc2 = engine.get_role_capacity("rc2")
        assert rc1.total_workers == 1
        assert rc2.total_workers == 1
        a = engine.workforce_assessment("a1", "t1")
        assert a.total_roles == 2

    def test_detect_all_then_report(self, engine):
        _register(engine, "w1", max_assign=1)
        _register(engine, "w2", name="Bob", status=WorkerStatus.ON_LEAVE)
        engine.request_assignment("r1", "t1", "s1", "reviewer")
        engine.decide_assignment("d1", "r1", "w1")
        engine.request_assignment("r2", "t1", "s2", "reviewer")
        # Detect everything
        engine.detect_coverage_gaps("t1")
        engine.detect_workforce_violations("t1")
        rpt = engine.closure_report("rpt1", "t1")
        assert rpt.total_violations >= 1
        # Both w1 (overloaded) and w2 (on leave) contribute to issues
        a = engine.workforce_assessment("a1", "t1")
        assert a.active_workers == 1
