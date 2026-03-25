"""Purpose: verify ContinuityRuntimeEngine — plans, recovery, disruptions,
    failover, execution, objectives, verification, violations, snapshots.
Governance scope: continuity runtime engine tests only.
Dependencies: continuity_runtime contracts, event_spine, core invariants.
Invariants:
  - Recovery plans must reference valid continuity plans.
  - Failed verification keeps system degraded.
  - Terminal recoveries cannot be re-opened.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.continuity_runtime import ContinuityRuntimeEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.continuity_runtime import (
    ContinuityClosureReport,
    ContinuityPlan,
    ContinuityScope,
    ContinuitySnapshot,
    ContinuityStatus,
    ContinuityViolation,
    DisruptionEvent,
    DisruptionSeverity,
    FailoverDisposition,
    FailoverRecord,
    RecoveryExecution,
    RecoveryObjective,
    RecoveryPlan,
    RecoveryStatus,
    RecoveryVerificationStatus,
    VerificationRecord,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture()
def engine(spine: EventSpineEngine) -> ContinuityRuntimeEngine:
    return ContinuityRuntimeEngine(spine)


def _make_plan(engine: ContinuityRuntimeEngine, plan_id: str = "plan-1",
               name: str = "Plan A", tenant_id: str = "t-1", **kw) -> ContinuityPlan:
    return engine.register_continuity_plan(plan_id, name, tenant_id, **kw)


def _make_recovery(engine: ContinuityRuntimeEngine,
                   recovery_plan_id: str = "rp-1", plan_id: str = "plan-1",
                   name: str = "RP-A", tenant_id: str = "t-1", **kw) -> RecoveryPlan:
    return engine.register_recovery_plan(recovery_plan_id, plan_id, name, tenant_id, **kw)


def _make_disruption(engine: ContinuityRuntimeEngine,
                     disruption_id: str = "dis-1", tenant_id: str = "t-1",
                     **kw) -> DisruptionEvent:
    return engine.record_disruption(disruption_id, tenant_id, **kw)


def _setup_failover(engine: ContinuityRuntimeEngine,
                    plan_id: str = "plan-1", disruption_id: str = "dis-1",
                    failover_id: str = "fo-1", tenant_id: str = "t-1",
                    **plan_kw) -> FailoverRecord:
    """Register plan, disruption, trigger failover."""
    _make_plan(engine, plan_id, tenant_id=tenant_id, **plan_kw)
    _make_disruption(engine, disruption_id, tenant_id)
    return engine.trigger_failover(failover_id, plan_id, disruption_id)


def _setup_execution(engine: ContinuityRuntimeEngine,
                     execution_id: str = "exe-1",
                     recovery_plan_id: str = "rp-1",
                     plan_id: str = "plan-1",
                     disruption_id: str = "dis-1",
                     tenant_id: str = "t-1") -> RecoveryExecution:
    """Register plan, recovery plan, disruption, start execution."""
    _make_plan(engine, plan_id, tenant_id=tenant_id)
    _make_recovery(engine, recovery_plan_id, plan_id, tenant_id=tenant_id)
    _make_disruption(engine, disruption_id, tenant_id)
    return engine.start_recovery(execution_id, recovery_plan_id, disruption_id)


# ===================================================================
# 1. CONSTRUCTOR TESTS
# ===================================================================


class TestConstructor:
    def test_valid_creation(self, spine: EventSpineEngine) -> None:
        eng = ContinuityRuntimeEngine(spine)
        assert eng is not None

    def test_invalid_type_string_raises(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="EventSpineEngine"):
            ContinuityRuntimeEngine("not-a-spine")  # type: ignore[arg-type]

    def test_invalid_type_none_raises(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="EventSpineEngine"):
            ContinuityRuntimeEngine(None)  # type: ignore[arg-type]

    def test_invalid_type_int_raises(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ContinuityRuntimeEngine(42)  # type: ignore[arg-type]

    def test_invalid_type_dict_raises(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ContinuityRuntimeEngine({})  # type: ignore[arg-type]

    def test_initial_plan_count_zero(self, engine: ContinuityRuntimeEngine) -> None:
        assert engine.plan_count == 0

    def test_initial_recovery_plan_count_zero(self, engine: ContinuityRuntimeEngine) -> None:
        assert engine.recovery_plan_count == 0

    def test_initial_disruption_count_zero(self, engine: ContinuityRuntimeEngine) -> None:
        assert engine.disruption_count == 0

    def test_initial_failover_count_zero(self, engine: ContinuityRuntimeEngine) -> None:
        assert engine.failover_count == 0

    def test_initial_execution_count_zero(self, engine: ContinuityRuntimeEngine) -> None:
        assert engine.execution_count == 0

    def test_initial_objective_count_zero(self, engine: ContinuityRuntimeEngine) -> None:
        assert engine.objective_count == 0

    def test_initial_verification_count_zero(self, engine: ContinuityRuntimeEngine) -> None:
        assert engine.verification_count == 0

    def test_initial_violation_count_zero(self, engine: ContinuityRuntimeEngine) -> None:
        assert engine.violation_count == 0


# ===================================================================
# 2. CONTINUITY PLANS
# ===================================================================


class TestRegisterContinuityPlan:
    def test_returns_plan(self, engine: ContinuityRuntimeEngine) -> None:
        plan = _make_plan(engine)
        assert isinstance(plan, ContinuityPlan)

    def test_status_active(self, engine: ContinuityRuntimeEngine) -> None:
        plan = _make_plan(engine)
        assert plan.status == ContinuityStatus.ACTIVE

    def test_plan_id_preserved(self, engine: ContinuityRuntimeEngine) -> None:
        plan = _make_plan(engine, "my-plan")
        assert plan.plan_id == "my-plan"

    def test_name_preserved(self, engine: ContinuityRuntimeEngine) -> None:
        plan = _make_plan(engine, name="Continuity Alpha")
        assert plan.name == "Continuity Alpha"

    def test_tenant_id_preserved(self, engine: ContinuityRuntimeEngine) -> None:
        plan = _make_plan(engine, tenant_id="tenant-xyz")
        assert plan.tenant_id == "tenant-xyz"

    def test_scope_default_service(self, engine: ContinuityRuntimeEngine) -> None:
        plan = _make_plan(engine)
        assert plan.scope == ContinuityScope.SERVICE

    def test_scope_connector(self, engine: ContinuityRuntimeEngine) -> None:
        plan = _make_plan(engine, scope=ContinuityScope.CONNECTOR)
        assert plan.scope == ContinuityScope.CONNECTOR

    def test_scope_environment(self, engine: ContinuityRuntimeEngine) -> None:
        plan = _make_plan(engine, scope=ContinuityScope.ENVIRONMENT)
        assert plan.scope == ContinuityScope.ENVIRONMENT

    def test_scope_asset(self, engine: ContinuityRuntimeEngine) -> None:
        plan = _make_plan(engine, scope=ContinuityScope.ASSET)
        assert plan.scope == ContinuityScope.ASSET

    def test_scope_workspace(self, engine: ContinuityRuntimeEngine) -> None:
        plan = _make_plan(engine, scope=ContinuityScope.WORKSPACE)
        assert plan.scope == ContinuityScope.WORKSPACE

    def test_scope_tenant(self, engine: ContinuityRuntimeEngine) -> None:
        plan = _make_plan(engine, scope=ContinuityScope.TENANT)
        assert plan.scope == ContinuityScope.TENANT

    def test_scope_ref_id(self, engine: ContinuityRuntimeEngine) -> None:
        plan = _make_plan(engine, scope_ref_id="svc-123")
        assert plan.scope_ref_id == "svc-123"

    def test_rto_minutes(self, engine: ContinuityRuntimeEngine) -> None:
        plan = _make_plan(engine, rto_minutes=30)
        assert plan.rto_minutes == 30

    def test_rpo_minutes(self, engine: ContinuityRuntimeEngine) -> None:
        plan = _make_plan(engine, rpo_minutes=15)
        assert plan.rpo_minutes == 15

    def test_failover_target_ref(self, engine: ContinuityRuntimeEngine) -> None:
        plan = _make_plan(engine, failover_target_ref="backup-node-1")
        assert plan.failover_target_ref == "backup-node-1"

    def test_owner_ref(self, engine: ContinuityRuntimeEngine) -> None:
        plan = _make_plan(engine, owner_ref="ops-team")
        assert plan.owner_ref == "ops-team"

    def test_created_at_set(self, engine: ContinuityRuntimeEngine) -> None:
        plan = _make_plan(engine)
        assert plan.created_at != ""

    def test_increments_plan_count(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        assert engine.plan_count == 1

    def test_duplicate_raises(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine, "dup-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            _make_plan(engine, "dup-1")

    def test_plan_count_after_two(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine, "p1")
        _make_plan(engine, "p2")
        assert engine.plan_count == 2

    def test_emits_event(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        before = spine.event_count
        _make_plan(engine)
        assert spine.event_count > before


class TestGetPlan:
    def test_returns_registered_plan(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine, "p-1")
        plan = engine.get_plan("p-1")
        assert plan.plan_id == "p-1"

    def test_unknown_raises(self, engine: ContinuityRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown plan_id"):
            engine.get_plan("no-exist")

    def test_returns_immutable(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        plan = engine.get_plan("plan-1")
        with pytest.raises(AttributeError):
            plan.name = "new"  # type: ignore[misc]


class TestActivatePlan:
    def test_activate_active_plan(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        updated = engine.activate_plan("plan-1")
        assert updated.status == ContinuityStatus.ACTIVATED

    def test_activate_suspended_plan(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.suspend_plan("plan-1")
        updated = engine.activate_plan("plan-1")
        assert updated.status == ContinuityStatus.ACTIVATED

    def test_activate_retired_raises(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.retire_plan("plan-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot activate"):
            engine.activate_plan("plan-1")

    def test_activate_preserves_name(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine, name="Alpha")
        updated = engine.activate_plan("plan-1")
        assert updated.name == "Alpha"

    def test_activate_preserves_tenant(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine, tenant_id="tt")
        updated = engine.activate_plan("plan-1")
        assert updated.tenant_id == "tt"

    def test_activate_preserves_scope(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine, scope=ContinuityScope.CONNECTOR)
        updated = engine.activate_plan("plan-1")
        assert updated.scope == ContinuityScope.CONNECTOR

    def test_activate_unknown_raises(self, engine: ContinuityRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown plan_id"):
            engine.activate_plan("nope")

    def test_activate_emits_event(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        before = spine.event_count
        engine.activate_plan("plan-1")
        assert spine.event_count > before

    def test_double_activate(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.activate_plan("plan-1")
        updated = engine.activate_plan("plan-1")
        assert updated.status == ContinuityStatus.ACTIVATED


class TestSuspendPlan:
    def test_suspend_active(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        updated = engine.suspend_plan("plan-1")
        assert updated.status == ContinuityStatus.SUSPENDED

    def test_suspend_activated(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.activate_plan("plan-1")
        updated = engine.suspend_plan("plan-1")
        assert updated.status == ContinuityStatus.SUSPENDED

    def test_suspend_retired_raises(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.retire_plan("plan-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot suspend"):
            engine.suspend_plan("plan-1")

    def test_suspend_unknown_raises(self, engine: ContinuityRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown plan_id"):
            engine.suspend_plan("nope")

    def test_suspend_preserves_fields(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine, rto_minutes=60)
        updated = engine.suspend_plan("plan-1")
        assert updated.rto_minutes == 60

    def test_suspend_emits_event(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        before = spine.event_count
        engine.suspend_plan("plan-1")
        assert spine.event_count > before

    def test_suspend_already_suspended(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.suspend_plan("plan-1")
        updated = engine.suspend_plan("plan-1")
        assert updated.status == ContinuityStatus.SUSPENDED


class TestRetirePlan:
    def test_retire_active(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        updated = engine.retire_plan("plan-1")
        assert updated.status == ContinuityStatus.RETIRED

    def test_retire_activated(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.activate_plan("plan-1")
        updated = engine.retire_plan("plan-1")
        assert updated.status == ContinuityStatus.RETIRED

    def test_retire_suspended(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.suspend_plan("plan-1")
        updated = engine.retire_plan("plan-1")
        assert updated.status == ContinuityStatus.RETIRED

    def test_retire_already_retired_raises(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.retire_plan("plan-1")
        with pytest.raises(RuntimeCoreInvariantError, match="already retired"):
            engine.retire_plan("plan-1")

    def test_retire_unknown_raises(self, engine: ContinuityRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown plan_id"):
            engine.retire_plan("nope")

    def test_retire_emits_event(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        before = spine.event_count
        engine.retire_plan("plan-1")
        assert spine.event_count > before

    def test_retire_preserves_created_at(self, engine: ContinuityRuntimeEngine) -> None:
        plan = _make_plan(engine)
        retired = engine.retire_plan("plan-1")
        assert retired.created_at == plan.created_at


class TestPlansForTenant:
    def test_empty_tenant(self, engine: ContinuityRuntimeEngine) -> None:
        result = engine.plans_for_tenant("t-none")
        assert result == ()

    def test_returns_tuple(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine, tenant_id="t-1")
        result = engine.plans_for_tenant("t-1")
        assert isinstance(result, tuple)

    def test_one_plan(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine, tenant_id="t-1")
        result = engine.plans_for_tenant("t-1")
        assert len(result) == 1

    def test_two_plans_same_tenant(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine, "p1", tenant_id="t-1")
        _make_plan(engine, "p2", tenant_id="t-1")
        result = engine.plans_for_tenant("t-1")
        assert len(result) == 2

    def test_filters_by_tenant(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine, "p1", tenant_id="t-1")
        _make_plan(engine, "p2", tenant_id="t-2")
        assert len(engine.plans_for_tenant("t-1")) == 1
        assert len(engine.plans_for_tenant("t-2")) == 1

    def test_correct_plan_ids(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine, "p1", tenant_id="t-1")
        _make_plan(engine, "p2", tenant_id="t-2")
        ids = {p.plan_id for p in engine.plans_for_tenant("t-1")}
        assert ids == {"p1"}


# ===================================================================
# 3. RECOVERY PLANS
# ===================================================================


class TestRegisterRecoveryPlan:
    def test_returns_recovery_plan(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        rp = _make_recovery(engine)
        assert isinstance(rp, RecoveryPlan)

    def test_status_pending(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        rp = _make_recovery(engine)
        assert rp.status == RecoveryStatus.PENDING

    def test_recovery_plan_id(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        rp = _make_recovery(engine, "rp-abc")
        assert rp.recovery_plan_id == "rp-abc"

    def test_plan_id_linked(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        rp = _make_recovery(engine)
        assert rp.plan_id == "plan-1"

    def test_name_preserved(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        rp = _make_recovery(engine, name="Recovery Beta")
        assert rp.name == "Recovery Beta"

    def test_tenant_id_preserved(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        rp = _make_recovery(engine, tenant_id="t-1")
        assert rp.tenant_id == "t-1"

    def test_priority_default(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        rp = _make_recovery(engine)
        assert rp.priority == 0

    def test_priority_custom(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        rp = _make_recovery(engine, priority=5)
        assert rp.priority == 5

    def test_description(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        rp = _make_recovery(engine, description="Failover to DR site")
        assert rp.description == "Failover to DR site"

    def test_created_at_set(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        rp = _make_recovery(engine)
        assert rp.created_at != ""

    def test_increments_count(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_recovery(engine)
        assert engine.recovery_plan_count == 1

    def test_duplicate_raises(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_recovery(engine, "rp-dup")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            _make_recovery(engine, "rp-dup")

    def test_unknown_plan_id_raises(self, engine: ContinuityRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown plan_id"):
            engine.register_recovery_plan("rp-1", "no-plan", "RP", "t-1")

    def test_emits_event(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        before = spine.event_count
        _make_recovery(engine)
        assert spine.event_count > before


class TestGetRecoveryPlan:
    def test_returns_plan(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_recovery(engine, "rp-1")
        rp = engine.get_recovery_plan("rp-1")
        assert rp.recovery_plan_id == "rp-1"

    def test_unknown_raises(self, engine: ContinuityRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown recovery_plan_id"):
            engine.get_recovery_plan("no-rp")


class TestRecoveryPlansForPlan:
    def test_empty(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        assert engine.recovery_plans_for_plan("plan-1") == ()

    def test_returns_tuple(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_recovery(engine)
        result = engine.recovery_plans_for_plan("plan-1")
        assert isinstance(result, tuple)

    def test_one_plan(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_recovery(engine)
        assert len(engine.recovery_plans_for_plan("plan-1")) == 1

    def test_filters_by_plan_id(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine, "p1")
        _make_plan(engine, "p2")
        _make_recovery(engine, "rp-1", "p1")
        _make_recovery(engine, "rp-2", "p2")
        assert len(engine.recovery_plans_for_plan("p1")) == 1
        assert len(engine.recovery_plans_for_plan("p2")) == 1

    def test_multiple_for_same_plan(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_recovery(engine, "rp-1")
        _make_recovery(engine, "rp-2")
        assert len(engine.recovery_plans_for_plan("plan-1")) == 2


# ===================================================================
# 4. DISRUPTIONS
# ===================================================================


class TestRecordDisruption:
    def test_returns_disruption(self, engine: ContinuityRuntimeEngine) -> None:
        d = _make_disruption(engine)
        assert isinstance(d, DisruptionEvent)

    def test_disruption_id(self, engine: ContinuityRuntimeEngine) -> None:
        d = _make_disruption(engine, "d-abc")
        assert d.disruption_id == "d-abc"

    def test_tenant_id(self, engine: ContinuityRuntimeEngine) -> None:
        d = _make_disruption(engine, tenant_id="t-99")
        assert d.tenant_id == "t-99"

    def test_scope_default(self, engine: ContinuityRuntimeEngine) -> None:
        d = _make_disruption(engine)
        assert d.scope == ContinuityScope.SERVICE

    def test_scope_connector(self, engine: ContinuityRuntimeEngine) -> None:
        d = _make_disruption(engine, scope=ContinuityScope.CONNECTOR)
        assert d.scope == ContinuityScope.CONNECTOR

    def test_scope_ref_id(self, engine: ContinuityRuntimeEngine) -> None:
        d = _make_disruption(engine, scope_ref_id="svc-x")
        assert d.scope_ref_id == "svc-x"

    def test_severity_default_medium(self, engine: ContinuityRuntimeEngine) -> None:
        d = _make_disruption(engine)
        assert d.severity == DisruptionSeverity.MEDIUM

    def test_severity_low(self, engine: ContinuityRuntimeEngine) -> None:
        d = _make_disruption(engine, severity=DisruptionSeverity.LOW)
        assert d.severity == DisruptionSeverity.LOW

    def test_severity_high(self, engine: ContinuityRuntimeEngine) -> None:
        d = _make_disruption(engine, severity=DisruptionSeverity.HIGH)
        assert d.severity == DisruptionSeverity.HIGH

    def test_severity_critical(self, engine: ContinuityRuntimeEngine) -> None:
        d = _make_disruption(engine, severity=DisruptionSeverity.CRITICAL)
        assert d.severity == DisruptionSeverity.CRITICAL

    def test_description(self, engine: ContinuityRuntimeEngine) -> None:
        d = _make_disruption(engine, description="DB connection lost")
        assert d.description == "DB connection lost"

    def test_detected_at_set(self, engine: ContinuityRuntimeEngine) -> None:
        d = _make_disruption(engine)
        assert d.detected_at != ""

    def test_resolved_at_empty(self, engine: ContinuityRuntimeEngine) -> None:
        d = _make_disruption(engine)
        assert d.resolved_at == ""

    def test_increments_count(self, engine: ContinuityRuntimeEngine) -> None:
        _make_disruption(engine)
        assert engine.disruption_count == 1

    def test_duplicate_raises(self, engine: ContinuityRuntimeEngine) -> None:
        _make_disruption(engine, "d-dup")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            _make_disruption(engine, "d-dup")

    def test_emits_event(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        before = spine.event_count
        _make_disruption(engine)
        assert spine.event_count > before


class TestGetDisruption:
    def test_returns_disruption(self, engine: ContinuityRuntimeEngine) -> None:
        _make_disruption(engine, "d-1")
        d = engine.get_disruption("d-1")
        assert d.disruption_id == "d-1"

    def test_unknown_raises(self, engine: ContinuityRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown disruption_id"):
            engine.get_disruption("no-d")


class TestResolveDisruption:
    def test_resolve_sets_resolved_at(self, engine: ContinuityRuntimeEngine) -> None:
        _make_disruption(engine)
        resolved = engine.resolve_disruption("dis-1")
        assert resolved.resolved_at != ""

    def test_resolve_preserves_id(self, engine: ContinuityRuntimeEngine) -> None:
        _make_disruption(engine)
        resolved = engine.resolve_disruption("dis-1")
        assert resolved.disruption_id == "dis-1"

    def test_resolve_preserves_tenant(self, engine: ContinuityRuntimeEngine) -> None:
        _make_disruption(engine, tenant_id="t-x")
        resolved = engine.resolve_disruption("dis-1")
        assert resolved.tenant_id == "t-x"

    def test_resolve_preserves_severity(self, engine: ContinuityRuntimeEngine) -> None:
        _make_disruption(engine, severity=DisruptionSeverity.CRITICAL)
        resolved = engine.resolve_disruption("dis-1")
        assert resolved.severity == DisruptionSeverity.CRITICAL

    def test_already_resolved_raises(self, engine: ContinuityRuntimeEngine) -> None:
        _make_disruption(engine)
        engine.resolve_disruption("dis-1")
        with pytest.raises(RuntimeCoreInvariantError, match="already resolved"):
            engine.resolve_disruption("dis-1")

    def test_unknown_raises(self, engine: ContinuityRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown disruption_id"):
            engine.resolve_disruption("no-dis")

    def test_emits_event(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _make_disruption(engine)
        before = spine.event_count
        engine.resolve_disruption("dis-1")
        assert spine.event_count > before


class TestDisruptionsForTenant:
    def test_empty(self, engine: ContinuityRuntimeEngine) -> None:
        assert engine.disruptions_for_tenant("t-none") == ()

    def test_returns_tuple(self, engine: ContinuityRuntimeEngine) -> None:
        _make_disruption(engine)
        result = engine.disruptions_for_tenant("t-1")
        assert isinstance(result, tuple)

    def test_one_disruption(self, engine: ContinuityRuntimeEngine) -> None:
        _make_disruption(engine)
        assert len(engine.disruptions_for_tenant("t-1")) == 1

    def test_filters_by_tenant(self, engine: ContinuityRuntimeEngine) -> None:
        _make_disruption(engine, "d1", "t-1")
        _make_disruption(engine, "d2", "t-2")
        assert len(engine.disruptions_for_tenant("t-1")) == 1
        assert len(engine.disruptions_for_tenant("t-2")) == 1

    def test_multiple_same_tenant(self, engine: ContinuityRuntimeEngine) -> None:
        _make_disruption(engine, "d1", "t-1")
        _make_disruption(engine, "d2", "t-1")
        assert len(engine.disruptions_for_tenant("t-1")) == 2


# ===================================================================
# 5. FAILOVER
# ===================================================================


class TestTriggerFailover:
    def test_returns_record(self, engine: ContinuityRuntimeEngine) -> None:
        fo = _setup_failover(engine)
        assert isinstance(fo, FailoverRecord)

    def test_disposition_initiated(self, engine: ContinuityRuntimeEngine) -> None:
        fo = _setup_failover(engine)
        assert fo.disposition == FailoverDisposition.INITIATED

    def test_failover_id(self, engine: ContinuityRuntimeEngine) -> None:
        fo = _setup_failover(engine, failover_id="fo-abc")
        assert fo.failover_id == "fo-abc"

    def test_plan_id_linked(self, engine: ContinuityRuntimeEngine) -> None:
        fo = _setup_failover(engine)
        assert fo.plan_id == "plan-1"

    def test_disruption_id_linked(self, engine: ContinuityRuntimeEngine) -> None:
        fo = _setup_failover(engine)
        assert fo.disruption_id == "dis-1"

    def test_source_ref(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_disruption(engine)
        fo = engine.trigger_failover("fo-1", "plan-1", "dis-1", source_ref="primary-node")
        assert fo.source_ref == "primary-node"

    def test_target_ref_explicit(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_disruption(engine)
        fo = engine.trigger_failover("fo-1", "plan-1", "dis-1", target_ref="backup-1")
        assert fo.target_ref == "backup-1"

    def test_target_ref_from_plan(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine, failover_target_ref="dr-site")
        _make_disruption(engine)
        fo = engine.trigger_failover("fo-1", "plan-1", "dis-1")
        assert fo.target_ref == "dr-site"

    def test_explicit_target_overrides_plan(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine, failover_target_ref="dr-site")
        _make_disruption(engine)
        fo = engine.trigger_failover("fo-1", "plan-1", "dis-1", target_ref="custom")
        assert fo.target_ref == "custom"

    def test_initiated_at_set(self, engine: ContinuityRuntimeEngine) -> None:
        fo = _setup_failover(engine)
        assert fo.initiated_at != ""

    def test_auto_activates_plan(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_disruption(engine)
        engine.trigger_failover("fo-1", "plan-1", "dis-1")
        plan = engine.get_plan("plan-1")
        assert plan.status == ContinuityStatus.ACTIVATED

    def test_already_activated_plan_stays(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.activate_plan("plan-1")
        _make_disruption(engine)
        engine.trigger_failover("fo-1", "plan-1", "dis-1")
        plan = engine.get_plan("plan-1")
        assert plan.status == ContinuityStatus.ACTIVATED

    def test_increments_count(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_failover(engine)
        assert engine.failover_count == 1

    def test_duplicate_raises(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_failover(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.trigger_failover("fo-1", "plan-1", "dis-1")

    def test_retired_plan_raises(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.retire_plan("plan-1")
        _make_disruption(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="retired"):
            engine.trigger_failover("fo-1", "plan-1", "dis-1")

    def test_unknown_disruption_raises(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown disruption_id"):
            engine.trigger_failover("fo-1", "plan-1", "no-dis")

    def test_unknown_plan_raises(self, engine: ContinuityRuntimeEngine) -> None:
        _make_disruption(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown plan_id"):
            engine.trigger_failover("fo-1", "no-plan", "dis-1")

    def test_emits_event(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_disruption(engine)
        before = spine.event_count
        engine.trigger_failover("fo-1", "plan-1", "dis-1")
        assert spine.event_count > before

    def test_suspended_plan_auto_activates(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.suspend_plan("plan-1")
        _make_disruption(engine)
        engine.trigger_failover("fo-1", "plan-1", "dis-1")
        plan = engine.get_plan("plan-1")
        assert plan.status == ContinuityStatus.ACTIVATED


class TestCompleteFailover:
    def test_initiated_to_completed(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_failover(engine)
        updated = engine.complete_failover("fo-1")
        assert updated.disposition == FailoverDisposition.COMPLETED

    def test_completed_at_set(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_failover(engine)
        updated = engine.complete_failover("fo-1")
        assert updated.completed_at != ""

    def test_preserves_plan_id(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_failover(engine)
        updated = engine.complete_failover("fo-1")
        assert updated.plan_id == "plan-1"

    def test_preserves_disruption_id(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_failover(engine)
        updated = engine.complete_failover("fo-1")
        assert updated.disruption_id == "dis-1"

    def test_already_completed_raises(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_failover(engine)
        engine.complete_failover("fo-1")
        with pytest.raises(RuntimeCoreInvariantError, match="INITIATED"):
            engine.complete_failover("fo-1")

    def test_failed_raises(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_failover(engine)
        engine.fail_failover("fo-1")
        with pytest.raises(RuntimeCoreInvariantError, match="INITIATED"):
            engine.complete_failover("fo-1")

    def test_rolled_back_raises(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_failover(engine)
        engine.rollback_failover("fo-1")
        with pytest.raises(RuntimeCoreInvariantError, match="INITIATED"):
            engine.complete_failover("fo-1")

    def test_unknown_raises(self, engine: ContinuityRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown failover_id"):
            engine.complete_failover("no-fo")

    def test_emits_event(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _setup_failover(engine)
        before = spine.event_count
        engine.complete_failover("fo-1")
        assert spine.event_count > before


class TestFailFailover:
    def test_initiated_to_failed(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_failover(engine)
        updated = engine.fail_failover("fo-1")
        assert updated.disposition == FailoverDisposition.FAILED

    def test_completed_at_set(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_failover(engine)
        updated = engine.fail_failover("fo-1")
        assert updated.completed_at != ""

    def test_already_failed_raises(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_failover(engine)
        engine.fail_failover("fo-1")
        with pytest.raises(RuntimeCoreInvariantError, match="INITIATED"):
            engine.fail_failover("fo-1")

    def test_completed_raises(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_failover(engine)
        engine.complete_failover("fo-1")
        with pytest.raises(RuntimeCoreInvariantError, match="INITIATED"):
            engine.fail_failover("fo-1")

    def test_unknown_raises(self, engine: ContinuityRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown failover_id"):
            engine.fail_failover("no-fo")

    def test_emits_event(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _setup_failover(engine)
        before = spine.event_count
        engine.fail_failover("fo-1")
        assert spine.event_count > before


class TestRollbackFailover:
    def test_initiated_to_rolled_back(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_failover(engine)
        updated = engine.rollback_failover("fo-1")
        assert updated.disposition == FailoverDisposition.ROLLED_BACK

    def test_completed_to_rolled_back(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_failover(engine)
        engine.complete_failover("fo-1")
        updated = engine.rollback_failover("fo-1")
        assert updated.disposition == FailoverDisposition.ROLLED_BACK

    def test_rolled_back_raises(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_failover(engine)
        engine.rollback_failover("fo-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot roll back"):
            engine.rollback_failover("fo-1")

    def test_failed_raises(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_failover(engine)
        engine.fail_failover("fo-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot roll back"):
            engine.rollback_failover("fo-1")

    def test_unknown_raises(self, engine: ContinuityRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown failover_id"):
            engine.rollback_failover("no-fo")

    def test_completed_at_set(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_failover(engine)
        updated = engine.rollback_failover("fo-1")
        assert updated.completed_at != ""

    def test_emits_event(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _setup_failover(engine)
        before = spine.event_count
        engine.rollback_failover("fo-1")
        assert spine.event_count > before


class TestFailoversForPlan:
    def test_empty(self, engine: ContinuityRuntimeEngine) -> None:
        assert engine.failovers_for_plan("no-plan") == ()

    def test_returns_tuple(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_failover(engine)
        result = engine.failovers_for_plan("plan-1")
        assert isinstance(result, tuple)

    def test_one_failover(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_failover(engine)
        assert len(engine.failovers_for_plan("plan-1")) == 1

    def test_filters_by_plan(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine, "p1")
        _make_plan(engine, "p2")
        _make_disruption(engine, "d1")
        _make_disruption(engine, "d2")
        engine.trigger_failover("fo-1", "p1", "d1")
        engine.trigger_failover("fo-2", "p2", "d2")
        assert len(engine.failovers_for_plan("p1")) == 1
        assert len(engine.failovers_for_plan("p2")) == 1

    def test_multiple_for_same_plan(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine, "p1")
        _make_disruption(engine, "d1")
        _make_disruption(engine, "d2")
        engine.trigger_failover("fo-1", "p1", "d1")
        engine.trigger_failover("fo-2", "p1", "d2")
        assert len(engine.failovers_for_plan("p1")) == 2


# ===================================================================
# 6. RECOVERY EXECUTION
# ===================================================================


class TestStartRecovery:
    def test_returns_execution(self, engine: ContinuityRuntimeEngine) -> None:
        exe = _setup_execution(engine)
        assert isinstance(exe, RecoveryExecution)

    def test_status_in_progress(self, engine: ContinuityRuntimeEngine) -> None:
        exe = _setup_execution(engine)
        assert exe.status == RecoveryStatus.IN_PROGRESS

    def test_execution_id(self, engine: ContinuityRuntimeEngine) -> None:
        exe = _setup_execution(engine, execution_id="exe-abc")
        assert exe.execution_id == "exe-abc"

    def test_recovery_plan_linked(self, engine: ContinuityRuntimeEngine) -> None:
        exe = _setup_execution(engine)
        assert exe.recovery_plan_id == "rp-1"

    def test_disruption_linked(self, engine: ContinuityRuntimeEngine) -> None:
        exe = _setup_execution(engine)
        assert exe.disruption_id == "dis-1"

    def test_executed_by_default(self, engine: ContinuityRuntimeEngine) -> None:
        exe = _setup_execution(engine)
        assert exe.executed_by == "system"

    def test_executed_by_custom(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_recovery(engine)
        _make_disruption(engine)
        exe = engine.start_recovery("exe-1", "rp-1", "dis-1", executed_by="ops-lead")
        assert exe.executed_by == "ops-lead"

    def test_started_at_set(self, engine: ContinuityRuntimeEngine) -> None:
        exe = _setup_execution(engine)
        assert exe.started_at != ""

    def test_increments_count(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        assert engine.execution_count == 1

    def test_duplicate_raises(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.start_recovery("exe-1", "rp-1", "dis-1")

    def test_unknown_recovery_plan_raises(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_disruption(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown recovery_plan_id"):
            engine.start_recovery("exe-1", "no-rp", "dis-1")

    def test_unknown_disruption_raises(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_recovery(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown disruption_id"):
            engine.start_recovery("exe-1", "rp-1", "no-dis")

    def test_emits_event(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_recovery(engine)
        _make_disruption(engine)
        before = spine.event_count
        engine.start_recovery("exe-1", "rp-1", "dis-1")
        assert spine.event_count > before


class TestCompleteRecovery:
    def test_in_progress_to_completed(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        updated = engine.complete_recovery("exe-1")
        assert updated.status == RecoveryStatus.COMPLETED

    def test_completed_at_set(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        updated = engine.complete_recovery("exe-1")
        assert updated.completed_at != ""

    def test_preserves_execution_id(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        updated = engine.complete_recovery("exe-1")
        assert updated.execution_id == "exe-1"

    def test_preserves_executed_by(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_recovery(engine)
        _make_disruption(engine)
        engine.start_recovery("exe-1", "rp-1", "dis-1", executed_by="alice")
        updated = engine.complete_recovery("exe-1")
        assert updated.executed_by == "alice"

    def test_already_completed_raises(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        engine.complete_recovery("exe-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.complete_recovery("exe-1")

    def test_already_failed_raises(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        engine.fail_recovery("exe-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.complete_recovery("exe-1")

    def test_already_cancelled_raises(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        engine.cancel_recovery("exe-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.complete_recovery("exe-1")

    def test_unknown_raises(self, engine: ContinuityRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown execution_id"):
            engine.complete_recovery("no-exe")

    def test_emits_event(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        before = spine.event_count
        engine.complete_recovery("exe-1")
        assert spine.event_count > before


class TestFailRecovery:
    def test_in_progress_to_failed(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        updated = engine.fail_recovery("exe-1")
        assert updated.status == RecoveryStatus.FAILED

    def test_completed_at_set(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        updated = engine.fail_recovery("exe-1")
        assert updated.completed_at != ""

    def test_already_completed_raises(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        engine.complete_recovery("exe-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.fail_recovery("exe-1")

    def test_already_failed_raises(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        engine.fail_recovery("exe-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.fail_recovery("exe-1")

    def test_already_cancelled_raises(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        engine.cancel_recovery("exe-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.fail_recovery("exe-1")

    def test_unknown_raises(self, engine: ContinuityRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown execution_id"):
            engine.fail_recovery("no-exe")

    def test_emits_event(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        before = spine.event_count
        engine.fail_recovery("exe-1")
        assert spine.event_count > before


class TestCancelRecovery:
    def test_in_progress_to_cancelled(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        updated = engine.cancel_recovery("exe-1")
        assert updated.status == RecoveryStatus.CANCELLED

    def test_already_completed_raises(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        engine.complete_recovery("exe-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.cancel_recovery("exe-1")

    def test_already_failed_raises(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        engine.fail_recovery("exe-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.cancel_recovery("exe-1")

    def test_already_cancelled_raises(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        engine.cancel_recovery("exe-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.cancel_recovery("exe-1")

    def test_unknown_raises(self, engine: ContinuityRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown execution_id"):
            engine.cancel_recovery("no-exe")

    def test_emits_event(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        before = spine.event_count
        engine.cancel_recovery("exe-1")
        assert spine.event_count > before

    def test_preserves_started_at(self, engine: ContinuityRuntimeEngine) -> None:
        exe = _setup_execution(engine)
        cancelled = engine.cancel_recovery("exe-1")
        assert cancelled.started_at == exe.started_at


class TestExecutionsForDisruption:
    def test_empty(self, engine: ContinuityRuntimeEngine) -> None:
        assert engine.executions_for_disruption("no-dis") == ()

    def test_returns_tuple(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        result = engine.executions_for_disruption("dis-1")
        assert isinstance(result, tuple)

    def test_one_execution(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        assert len(engine.executions_for_disruption("dis-1")) == 1

    def test_filters_by_disruption(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_recovery(engine, "rp-1")
        _make_recovery(engine, "rp-2")
        _make_disruption(engine, "d1")
        _make_disruption(engine, "d2")
        engine.start_recovery("exe-1", "rp-1", "d1")
        engine.start_recovery("exe-2", "rp-2", "d2")
        assert len(engine.executions_for_disruption("d1")) == 1
        assert len(engine.executions_for_disruption("d2")) == 1

    def test_multiple_for_same_disruption(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_recovery(engine, "rp-1")
        _make_recovery(engine, "rp-2")
        _make_disruption(engine)
        engine.start_recovery("exe-1", "rp-1", "dis-1")
        engine.start_recovery("exe-2", "rp-2", "dis-1")
        assert len(engine.executions_for_disruption("dis-1")) == 2


# ===================================================================
# 7. RECOVERY OBJECTIVES
# ===================================================================


class TestRecordObjective:
    def test_returns_objective(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        obj = engine.record_objective("obj-1", "plan-1", "RTO", 30, 20)
        assert isinstance(obj, RecoveryObjective)

    def test_objective_id(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        obj = engine.record_objective("obj-abc", "plan-1", "RTO", 30, 20)
        assert obj.objective_id == "obj-abc"

    def test_plan_id(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        obj = engine.record_objective("obj-1", "plan-1", "RTO", 30, 20)
        assert obj.plan_id == "plan-1"

    def test_name(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        obj = engine.record_objective("obj-1", "plan-1", "Recovery Time", 30, 20)
        assert obj.name == "Recovery Time"

    def test_target_minutes(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        obj = engine.record_objective("obj-1", "plan-1", "RTO", 60, 45)
        assert obj.target_minutes == 60

    def test_actual_minutes(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        obj = engine.record_objective("obj-1", "plan-1", "RTO", 60, 45)
        assert obj.actual_minutes == 45

    def test_met_when_actual_less(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        obj = engine.record_objective("obj-1", "plan-1", "RTO", 30, 20)
        assert obj.met is True

    def test_met_when_actual_equal(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        obj = engine.record_objective("obj-1", "plan-1", "RTO", 30, 30)
        assert obj.met is True

    def test_not_met_when_actual_greater(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        obj = engine.record_objective("obj-1", "plan-1", "RTO", 30, 45)
        assert obj.met is False

    def test_met_zero_target_zero_actual(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        obj = engine.record_objective("obj-1", "plan-1", "RTO", 0, 0)
        assert obj.met is True

    def test_not_met_zero_target_positive_actual(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        obj = engine.record_objective("obj-1", "plan-1", "RTO", 0, 1)
        assert obj.met is False

    def test_evaluated_at_set(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        obj = engine.record_objective("obj-1", "plan-1", "RTO", 30, 20)
        assert obj.evaluated_at != ""

    def test_increments_count(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.record_objective("obj-1", "plan-1", "RTO", 30, 20)
        assert engine.objective_count == 1

    def test_duplicate_raises(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.record_objective("obj-dup", "plan-1", "RTO", 30, 20)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.record_objective("obj-dup", "plan-1", "RPO", 15, 10)

    def test_unknown_plan_raises(self, engine: ContinuityRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown plan_id"):
            engine.record_objective("obj-1", "no-plan", "RTO", 30, 20)

    def test_emits_event(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        before = spine.event_count
        engine.record_objective("obj-1", "plan-1", "RTO", 30, 20)
        assert spine.event_count > before


class TestObjectivesForPlan:
    def test_empty(self, engine: ContinuityRuntimeEngine) -> None:
        assert engine.objectives_for_plan("no-plan") == ()

    def test_returns_tuple(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.record_objective("obj-1", "plan-1", "RTO", 30, 20)
        result = engine.objectives_for_plan("plan-1")
        assert isinstance(result, tuple)

    def test_one_objective(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.record_objective("obj-1", "plan-1", "RTO", 30, 20)
        assert len(engine.objectives_for_plan("plan-1")) == 1

    def test_filters_by_plan(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine, "p1")
        _make_plan(engine, "p2")
        engine.record_objective("obj-1", "p1", "RTO", 30, 20)
        engine.record_objective("obj-2", "p2", "RTO", 30, 20)
        assert len(engine.objectives_for_plan("p1")) == 1
        assert len(engine.objectives_for_plan("p2")) == 1

    def test_multiple_for_same_plan(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.record_objective("obj-1", "plan-1", "RTO", 30, 20)
        engine.record_objective("obj-2", "plan-1", "RPO", 15, 10)
        assert len(engine.objectives_for_plan("plan-1")) == 2


# ===================================================================
# 8. VERIFICATION
# ===================================================================


class TestVerifyRecovery:
    def test_returns_record(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        vr = engine.verify_recovery("v-1", "exe-1")
        assert isinstance(vr, VerificationRecord)

    def test_verification_id(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        vr = engine.verify_recovery("v-abc", "exe-1")
        assert vr.verification_id == "v-abc"

    def test_execution_id_linked(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        vr = engine.verify_recovery("v-1", "exe-1")
        assert vr.execution_id == "exe-1"

    def test_status_default_passed(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        vr = engine.verify_recovery("v-1", "exe-1")
        assert vr.status == RecoveryVerificationStatus.PASSED

    def test_status_passed(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        vr = engine.verify_recovery("v-1", "exe-1", status=RecoveryVerificationStatus.PASSED)
        assert vr.status == RecoveryVerificationStatus.PASSED

    def test_status_failed(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        vr = engine.verify_recovery("v-1", "exe-1", status=RecoveryVerificationStatus.FAILED)
        assert vr.status == RecoveryVerificationStatus.FAILED

    def test_status_skipped(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        vr = engine.verify_recovery("v-1", "exe-1", status=RecoveryVerificationStatus.SKIPPED)
        assert vr.status == RecoveryVerificationStatus.SKIPPED

    def test_verified_by_default(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        vr = engine.verify_recovery("v-1", "exe-1")
        assert vr.verified_by == "system"

    def test_verified_by_custom(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        vr = engine.verify_recovery("v-1", "exe-1", verified_by="qa-lead")
        assert vr.verified_by == "qa-lead"

    def test_confidence_default(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        vr = engine.verify_recovery("v-1", "exe-1")
        assert vr.confidence == 1.0

    def test_confidence_custom(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        vr = engine.verify_recovery("v-1", "exe-1", confidence=0.85)
        assert vr.confidence == 0.85

    def test_reason(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        vr = engine.verify_recovery("v-1", "exe-1", reason="All checks passed")
        assert vr.reason == "All checks passed"

    def test_verified_at_set(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        vr = engine.verify_recovery("v-1", "exe-1")
        assert vr.verified_at != ""

    def test_increments_count(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        engine.verify_recovery("v-1", "exe-1")
        assert engine.verification_count == 1

    def test_duplicate_raises(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        engine.verify_recovery("v-dup", "exe-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.verify_recovery("v-dup", "exe-1")

    def test_unknown_execution_raises(self, engine: ContinuityRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown execution_id"):
            engine.verify_recovery("v-1", "no-exe")

    def test_failed_verification_auto_fails_execution(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        engine.verify_recovery("v-1", "exe-1", status=RecoveryVerificationStatus.FAILED)
        exe = engine.executions_for_disruption("dis-1")[0]
        assert exe.status == RecoveryStatus.FAILED

    def test_passed_does_not_change_execution(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        engine.verify_recovery("v-1", "exe-1", status=RecoveryVerificationStatus.PASSED)
        exe = engine.executions_for_disruption("dis-1")[0]
        assert exe.status == RecoveryStatus.IN_PROGRESS

    def test_skipped_does_not_change_execution(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        engine.verify_recovery("v-1", "exe-1", status=RecoveryVerificationStatus.SKIPPED)
        exe = engine.executions_for_disruption("dis-1")[0]
        assert exe.status == RecoveryStatus.IN_PROGRESS

    def test_failed_verification_on_terminal_execution(self, engine: ContinuityRuntimeEngine) -> None:
        """Failed verification on already-completed execution does not re-fail."""
        _setup_execution(engine)
        engine.complete_recovery("exe-1")
        # Should not raise — execution is already terminal, so fail_recovery is skipped
        vr = engine.verify_recovery("v-1", "exe-1", status=RecoveryVerificationStatus.FAILED)
        assert vr.status == RecoveryVerificationStatus.FAILED

    def test_emits_event(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        before = spine.event_count
        engine.verify_recovery("v-1", "exe-1")
        assert spine.event_count > before


class TestVerificationsForExecution:
    def test_empty(self, engine: ContinuityRuntimeEngine) -> None:
        assert engine.verifications_for_execution("no-exe") == ()

    def test_returns_tuple(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        engine.verify_recovery("v-1", "exe-1")
        result = engine.verifications_for_execution("exe-1")
        assert isinstance(result, tuple)

    def test_one_verification(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        engine.verify_recovery("v-1", "exe-1")
        assert len(engine.verifications_for_execution("exe-1")) == 1

    def test_multiple_for_same_execution(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        engine.verify_recovery("v-1", "exe-1", status=RecoveryVerificationStatus.PASSED)
        engine.verify_recovery("v-2", "exe-1", status=RecoveryVerificationStatus.PASSED)
        assert len(engine.verifications_for_execution("exe-1")) == 2

    def test_filters_by_execution(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_recovery(engine, "rp-1")
        _make_recovery(engine, "rp-2")
        _make_disruption(engine)
        engine.start_recovery("exe-1", "rp-1", "dis-1")
        engine.start_recovery("exe-2", "rp-2", "dis-1")
        engine.verify_recovery("v-1", "exe-1")
        engine.verify_recovery("v-2", "exe-2")
        assert len(engine.verifications_for_execution("exe-1")) == 1
        assert len(engine.verifications_for_execution("exe-2")) == 1


# ===================================================================
# 9. VIOLATION DETECTION
# ===================================================================


class TestDetectContinuityViolations:
    def test_no_violations_clean_state(self, engine: ContinuityRuntimeEngine) -> None:
        violations = engine.detect_continuity_violations()
        assert violations == ()

    def test_activated_no_recovery_violation(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.activate_plan("plan-1")
        violations = engine.detect_continuity_violations()
        assert len(violations) == 1
        assert violations[0].operation == "activated_no_recovery"

    def test_activated_no_recovery_has_plan_id(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.activate_plan("plan-1")
        violations = engine.detect_continuity_violations()
        assert violations[0].plan_id == "plan-1"

    def test_activated_no_recovery_has_tenant(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine, tenant_id="t-x")
        engine.activate_plan("plan-1")
        violations = engine.detect_continuity_violations()
        assert violations[0].tenant_id == "t-x"

    def test_activated_with_recovery_no_violation(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_recovery(engine)
        engine.activate_plan("plan-1")
        violations = engine.detect_continuity_violations()
        activated_violations = [v for v in violations if v.operation == "activated_no_recovery"]
        assert len(activated_violations) == 0

    def test_active_plan_no_recovery_no_violation(self, engine: ContinuityRuntimeEngine) -> None:
        """Only ACTIVATED (not ACTIVE) triggers activated_no_recovery."""
        _make_plan(engine)
        violations = engine.detect_continuity_violations()
        activated_violations = [v for v in violations if v.operation == "activated_no_recovery"]
        assert len(activated_violations) == 0

    def test_failed_failover_no_recovery_violation(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_failover(engine)
        engine.fail_failover("fo-1")
        violations = engine.detect_continuity_violations()
        fo_violations = [v for v in violations if v.operation == "failed_failover_no_recovery"]
        assert len(fo_violations) == 1

    def test_failed_failover_with_recovery_no_violation(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_recovery(engine)
        _make_disruption(engine)
        engine.trigger_failover("fo-1", "plan-1", "dis-1")
        engine.fail_failover("fo-1")
        engine.start_recovery("exe-1", "rp-1", "dis-1")
        violations = engine.detect_continuity_violations()
        fo_violations = [v for v in violations if v.operation == "failed_failover_no_recovery"]
        assert len(fo_violations) == 0

    def test_all_recoveries_failed_violation(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_recovery(engine)
        _make_disruption(engine)
        engine.start_recovery("exe-1", "rp-1", "dis-1")
        engine.fail_recovery("exe-1")
        violations = engine.detect_continuity_violations()
        all_failed = [v for v in violations if v.operation == "all_recoveries_failed"]
        assert len(all_failed) == 1

    def test_all_recoveries_failed_has_reason(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_recovery(engine)
        _make_disruption(engine)
        engine.start_recovery("exe-1", "rp-1", "dis-1")
        engine.fail_recovery("exe-1")
        violations = engine.detect_continuity_violations()
        all_failed = [v for v in violations if v.operation == "all_recoveries_failed"]
        assert "1 recovery" in all_failed[0].reason

    def test_one_recovery_succeeded_no_all_failed(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_recovery(engine, "rp-1")
        _make_recovery(engine, "rp-2")
        _make_disruption(engine)
        engine.start_recovery("exe-1", "rp-1", "dis-1")
        engine.fail_recovery("exe-1")
        engine.start_recovery("exe-2", "rp-2", "dis-1")
        engine.complete_recovery("exe-2")
        violations = engine.detect_continuity_violations()
        all_failed = [v for v in violations if v.operation == "all_recoveries_failed"]
        assert len(all_failed) == 0

    def test_resolved_disruption_no_all_failed(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_recovery(engine)
        _make_disruption(engine)
        engine.start_recovery("exe-1", "rp-1", "dis-1")
        engine.fail_recovery("exe-1")
        engine.resolve_disruption("dis-1")
        violations = engine.detect_continuity_violations()
        all_failed = [v for v in violations if v.operation == "all_recoveries_failed"]
        assert len(all_failed) == 0

    def test_idempotent_second_scan_empty(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.activate_plan("plan-1")
        v1 = engine.detect_continuity_violations()
        assert len(v1) == 1
        v2 = engine.detect_continuity_violations()
        assert len(v2) == 0

    def test_idempotent_violation_count_stable(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.activate_plan("plan-1")
        engine.detect_continuity_violations()
        count_after_first = engine.violation_count
        engine.detect_continuity_violations()
        assert engine.violation_count == count_after_first

    def test_multiple_violation_types(self, engine: ContinuityRuntimeEngine) -> None:
        # activated_no_recovery
        _make_plan(engine, "p1")
        engine.activate_plan("p1")
        # failed_failover_no_recovery
        _make_plan(engine, "p2")
        _make_disruption(engine, "d1")
        engine.trigger_failover("fo-1", "p2", "d1")
        engine.fail_failover("fo-1")
        violations = engine.detect_continuity_violations()
        ops = {v.operation for v in violations}
        assert "activated_no_recovery" in ops
        assert "failed_failover_no_recovery" in ops

    def test_emits_event_when_violations_found(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.activate_plan("plan-1")
        before = spine.event_count
        engine.detect_continuity_violations()
        assert spine.event_count > before

    def test_no_event_when_no_violations(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        before = spine.event_count
        engine.detect_continuity_violations()
        assert spine.event_count == before

    def test_disruption_no_executions_no_all_failed(self, engine: ContinuityRuntimeEngine) -> None:
        """Unresolved disruption with NO executions does not trigger all_recoveries_failed."""
        _make_disruption(engine)
        violations = engine.detect_continuity_violations()
        all_failed = [v for v in violations if v.operation == "all_recoveries_failed"]
        assert len(all_failed) == 0

    def test_in_progress_recovery_no_all_failed(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_recovery(engine)
        _make_disruption(engine)
        engine.start_recovery("exe-1", "rp-1", "dis-1")
        violations = engine.detect_continuity_violations()
        all_failed = [v for v in violations if v.operation == "all_recoveries_failed"]
        assert len(all_failed) == 0

    def test_two_failed_recoveries_all_failed(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_recovery(engine, "rp-1")
        _make_recovery(engine, "rp-2")
        _make_disruption(engine)
        engine.start_recovery("exe-1", "rp-1", "dis-1")
        engine.fail_recovery("exe-1")
        engine.start_recovery("exe-2", "rp-2", "dis-1")
        engine.fail_recovery("exe-2")
        violations = engine.detect_continuity_violations()
        all_failed = [v for v in violations if v.operation == "all_recoveries_failed"]
        assert len(all_failed) == 1
        assert "2 recovery" in all_failed[0].reason


class TestViolationsForPlan:
    def test_empty(self, engine: ContinuityRuntimeEngine) -> None:
        assert engine.violations_for_plan("no-plan") == ()

    def test_returns_tuple(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.activate_plan("plan-1")
        engine.detect_continuity_violations()
        result = engine.violations_for_plan("plan-1")
        assert isinstance(result, tuple)

    def test_one_violation(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.activate_plan("plan-1")
        engine.detect_continuity_violations()
        assert len(engine.violations_for_plan("plan-1")) == 1

    def test_filters_by_plan(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine, "p1")
        _make_plan(engine, "p2")
        engine.activate_plan("p1")
        engine.activate_plan("p2")
        engine.detect_continuity_violations()
        assert len(engine.violations_for_plan("p1")) == 1
        assert len(engine.violations_for_plan("p2")) == 1


# ===================================================================
# 10. SNAPSHOT
# ===================================================================


class TestContinuitySnapshot:
    def test_returns_snapshot(self, engine: ContinuityRuntimeEngine) -> None:
        snap = engine.continuity_snapshot("snap-1")
        assert isinstance(snap, ContinuitySnapshot)

    def test_snapshot_id(self, engine: ContinuityRuntimeEngine) -> None:
        snap = engine.continuity_snapshot("snap-abc")
        assert snap.snapshot_id == "snap-abc"

    def test_duplicate_raises(self, engine: ContinuityRuntimeEngine) -> None:
        engine.continuity_snapshot("snap-dup")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.continuity_snapshot("snap-dup")

    def test_total_plans(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        snap = engine.continuity_snapshot("s1")
        assert snap.total_plans == 1

    def test_total_plans_zero(self, engine: ContinuityRuntimeEngine) -> None:
        snap = engine.continuity_snapshot("s1")
        assert snap.total_plans == 0

    def test_total_active_plans_active(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        snap = engine.continuity_snapshot("s1")
        assert snap.total_active_plans == 1

    def test_total_active_plans_activated(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.activate_plan("plan-1")
        snap = engine.continuity_snapshot("s1")
        assert snap.total_active_plans == 1

    def test_total_active_plans_both(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine, "p1")
        _make_plan(engine, "p2")
        engine.activate_plan("p2")
        snap = engine.continuity_snapshot("s1")
        assert snap.total_active_plans == 2

    def test_total_active_plans_excludes_retired(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.retire_plan("plan-1")
        snap = engine.continuity_snapshot("s1")
        assert snap.total_active_plans == 0

    def test_total_active_plans_excludes_suspended(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.suspend_plan("plan-1")
        snap = engine.continuity_snapshot("s1")
        assert snap.total_active_plans == 0

    def test_total_recovery_plans(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_recovery(engine)
        snap = engine.continuity_snapshot("s1")
        assert snap.total_recovery_plans == 1

    def test_total_disruptions(self, engine: ContinuityRuntimeEngine) -> None:
        _make_disruption(engine)
        snap = engine.continuity_snapshot("s1")
        assert snap.total_disruptions == 1

    def test_total_failovers(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_failover(engine)
        snap = engine.continuity_snapshot("s1")
        assert snap.total_failovers == 1

    def test_total_recoveries(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        snap = engine.continuity_snapshot("s1")
        assert snap.total_recoveries == 1

    def test_total_verifications(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        engine.verify_recovery("v-1", "exe-1")
        snap = engine.continuity_snapshot("s1")
        assert snap.total_verifications == 1

    def test_total_violations(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.activate_plan("plan-1")
        engine.detect_continuity_violations()
        snap = engine.continuity_snapshot("s1")
        assert snap.total_violations == 1

    def test_total_objectives(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.record_objective("obj-1", "plan-1", "RTO", 30, 20)
        snap = engine.continuity_snapshot("s1")
        assert snap.total_objectives == 1

    def test_captured_at_set(self, engine: ContinuityRuntimeEngine) -> None:
        snap = engine.continuity_snapshot("s1")
        assert snap.captured_at != ""

    def test_emits_event(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        before = spine.event_count
        engine.continuity_snapshot("s1")
        assert spine.event_count > before


# ===================================================================
# 11. STATE HASH
# ===================================================================


class TestStateHash:
    def test_returns_string(self, engine: ContinuityRuntimeEngine) -> None:
        h = engine.state_hash()
        assert isinstance(h, str)

    def test_non_empty(self, engine: ContinuityRuntimeEngine) -> None:
        assert len(engine.state_hash()) > 0

    def test_deterministic(self, engine: ContinuityRuntimeEngine) -> None:
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_changes_after_plan(self, engine: ContinuityRuntimeEngine) -> None:
        h1 = engine.state_hash()
        _make_plan(engine)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_disruption(self, engine: ContinuityRuntimeEngine) -> None:
        h1 = engine.state_hash()
        _make_disruption(engine)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_recovery_plan(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        h1 = engine.state_hash()
        _make_recovery(engine)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_failover(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_disruption(engine)
        h1 = engine.state_hash()
        engine.trigger_failover("fo-1", "plan-1", "dis-1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_execution(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_recovery(engine)
        _make_disruption(engine)
        h1 = engine.state_hash()
        engine.start_recovery("exe-1", "rp-1", "dis-1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_objective(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        h1 = engine.state_hash()
        engine.record_objective("obj-1", "plan-1", "RTO", 30, 20)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_verification(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        h1 = engine.state_hash()
        engine.verify_recovery("v-1", "exe-1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_violation(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.activate_plan("plan-1")
        h1 = engine.state_hash()
        engine.detect_continuity_violations()
        h2 = engine.state_hash()
        assert h1 != h2

    def test_length_consistent(self, engine: ContinuityRuntimeEngine) -> None:
        assert len(engine.state_hash()) == 64


# ===================================================================
# 12. PROPERTIES
# ===================================================================


class TestProperties:
    def test_plan_count_increments(self, engine: ContinuityRuntimeEngine) -> None:
        assert engine.plan_count == 0
        _make_plan(engine, "p1")
        assert engine.plan_count == 1
        _make_plan(engine, "p2")
        assert engine.plan_count == 2

    def test_recovery_plan_count_increments(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        assert engine.recovery_plan_count == 0
        _make_recovery(engine, "rp-1")
        assert engine.recovery_plan_count == 1
        _make_recovery(engine, "rp-2")
        assert engine.recovery_plan_count == 2

    def test_disruption_count_increments(self, engine: ContinuityRuntimeEngine) -> None:
        assert engine.disruption_count == 0
        _make_disruption(engine, "d1")
        assert engine.disruption_count == 1

    def test_failover_count_increments(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_disruption(engine, "d1")
        _make_disruption(engine, "d2")
        assert engine.failover_count == 0
        engine.trigger_failover("fo-1", "plan-1", "d1")
        assert engine.failover_count == 1
        engine.trigger_failover("fo-2", "plan-1", "d2")
        assert engine.failover_count == 2

    def test_execution_count_increments(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_recovery(engine, "rp-1")
        _make_recovery(engine, "rp-2")
        _make_disruption(engine)
        assert engine.execution_count == 0
        engine.start_recovery("exe-1", "rp-1", "dis-1")
        assert engine.execution_count == 1
        engine.start_recovery("exe-2", "rp-2", "dis-1")
        assert engine.execution_count == 2

    def test_objective_count_increments(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        assert engine.objective_count == 0
        engine.record_objective("obj-1", "plan-1", "RTO", 30, 20)
        assert engine.objective_count == 1

    def test_verification_count_increments(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        assert engine.verification_count == 0
        engine.verify_recovery("v-1", "exe-1")
        assert engine.verification_count == 1

    def test_violation_count_increments(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.activate_plan("plan-1")
        assert engine.violation_count == 0
        engine.detect_continuity_violations()
        assert engine.violation_count == 1


# ===================================================================
# 13. EVENT EMISSION
# ===================================================================


class TestEventEmission:
    def test_register_plan_emits(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        before = spine.event_count
        _make_plan(engine)
        assert spine.event_count == before + 1

    def test_activate_plan_emits(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        before = spine.event_count
        engine.activate_plan("plan-1")
        assert spine.event_count == before + 1

    def test_suspend_plan_emits(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        before = spine.event_count
        engine.suspend_plan("plan-1")
        assert spine.event_count == before + 1

    def test_retire_plan_emits(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        before = spine.event_count
        engine.retire_plan("plan-1")
        assert spine.event_count == before + 1

    def test_register_recovery_plan_emits(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        before = spine.event_count
        _make_recovery(engine)
        assert spine.event_count == before + 1

    def test_record_disruption_emits(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        before = spine.event_count
        _make_disruption(engine)
        assert spine.event_count == before + 1

    def test_resolve_disruption_emits(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _make_disruption(engine)
        before = spine.event_count
        engine.resolve_disruption("dis-1")
        assert spine.event_count == before + 1

    def test_trigger_failover_emits(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.activate_plan("plan-1")
        _make_disruption(engine)
        before = spine.event_count
        engine.trigger_failover("fo-1", "plan-1", "dis-1")
        # trigger_failover emits 1 event (plan already activated)
        assert spine.event_count == before + 1

    def test_trigger_failover_auto_activate_emits_extra(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_disruption(engine)
        before = spine.event_count
        engine.trigger_failover("fo-1", "plan-1", "dis-1")
        # activate_plan + trigger_failover = 2 events
        assert spine.event_count == before + 2

    def test_complete_failover_emits(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _setup_failover(engine)
        before = spine.event_count
        engine.complete_failover("fo-1")
        assert spine.event_count == before + 1

    def test_fail_failover_emits(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _setup_failover(engine)
        before = spine.event_count
        engine.fail_failover("fo-1")
        assert spine.event_count == before + 1

    def test_rollback_failover_emits(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _setup_failover(engine)
        before = spine.event_count
        engine.rollback_failover("fo-1")
        assert spine.event_count == before + 1

    def test_start_recovery_emits(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_recovery(engine)
        _make_disruption(engine)
        before = spine.event_count
        engine.start_recovery("exe-1", "rp-1", "dis-1")
        assert spine.event_count == before + 1

    def test_complete_recovery_emits(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        before = spine.event_count
        engine.complete_recovery("exe-1")
        assert spine.event_count == before + 1

    def test_fail_recovery_emits(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        before = spine.event_count
        engine.fail_recovery("exe-1")
        assert spine.event_count == before + 1

    def test_cancel_recovery_emits(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        before = spine.event_count
        engine.cancel_recovery("exe-1")
        assert spine.event_count == before + 1

    def test_record_objective_emits(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        before = spine.event_count
        engine.record_objective("obj-1", "plan-1", "RTO", 30, 20)
        assert spine.event_count == before + 1

    def test_verify_recovery_emits(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        before = spine.event_count
        engine.verify_recovery("v-1", "exe-1")
        assert spine.event_count == before + 1

    def test_snapshot_emits(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        before = spine.event_count
        engine.continuity_snapshot("s1")
        assert spine.event_count == before + 1

    def test_violations_emit_when_found(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.activate_plan("plan-1")
        before = spine.event_count
        engine.detect_continuity_violations()
        assert spine.event_count == before + 1


# ===================================================================
# 14. GOLDEN SCENARIO 1: Connector outage full lifecycle
# ===================================================================


class TestGoldenScenario1ConnectorOutage:
    """GS-1: Connector outage -> disruption -> failover -> complete ->
    recovery -> complete -> verify PASSED -> resolve disruption."""

    def test_full_lifecycle(self, engine: ContinuityRuntimeEngine) -> None:
        # Register plan with failover target
        plan = engine.register_continuity_plan(
            "plan-conn", "Connector DR", "tenant-a",
            scope=ContinuityScope.CONNECTOR,
            scope_ref_id="conn-salesforce",
            rto_minutes=30, rpo_minutes=15,
            failover_target_ref="conn-salesforce-backup",
        )
        assert plan.status == ContinuityStatus.ACTIVE

        # Register recovery plan
        rp = engine.register_recovery_plan(
            "rp-conn", "plan-conn", "Connector Recovery", "tenant-a",
            priority=1, description="Failover to backup connector",
        )
        assert rp.status == RecoveryStatus.PENDING

        # Record disruption
        dis = engine.record_disruption(
            "dis-conn", "tenant-a",
            scope=ContinuityScope.CONNECTOR,
            scope_ref_id="conn-salesforce",
            severity=DisruptionSeverity.HIGH,
            description="Salesforce connector timeout",
        )
        assert dis.resolved_at == ""

        # Trigger failover
        fo = engine.trigger_failover("fo-conn", "plan-conn", "dis-conn")
        assert fo.disposition == FailoverDisposition.INITIATED
        assert fo.target_ref == "conn-salesforce-backup"
        assert engine.get_plan("plan-conn").status == ContinuityStatus.ACTIVATED

        # Complete failover
        fo_done = engine.complete_failover("fo-conn")
        assert fo_done.disposition == FailoverDisposition.COMPLETED

        # Start recovery
        exe = engine.start_recovery("exe-conn", "rp-conn", "dis-conn")
        assert exe.status == RecoveryStatus.IN_PROGRESS

        # Complete recovery
        exe_done = engine.complete_recovery("exe-conn")
        assert exe_done.status == RecoveryStatus.COMPLETED

        # Verify PASSED
        vr = engine.verify_recovery("vr-conn", "exe-conn",
                                     status=RecoveryVerificationStatus.PASSED,
                                     confidence=0.95)
        assert vr.status == RecoveryVerificationStatus.PASSED

        # Resolve disruption
        dis_resolved = engine.resolve_disruption("dis-conn")
        assert dis_resolved.resolved_at != ""

        # No violations
        violations = engine.detect_continuity_violations()
        assert len(violations) == 0

    def test_snapshot_after_lifecycle(self, engine: ContinuityRuntimeEngine) -> None:
        engine.register_continuity_plan("plan-conn", "Conn DR", "tenant-a",
                                         scope=ContinuityScope.CONNECTOR,
                                         failover_target_ref="backup")
        engine.register_recovery_plan("rp-conn", "plan-conn", "RP", "tenant-a")
        engine.record_disruption("dis-conn", "tenant-a")
        engine.trigger_failover("fo-conn", "plan-conn", "dis-conn")
        engine.complete_failover("fo-conn")
        engine.start_recovery("exe-conn", "rp-conn", "dis-conn")
        engine.complete_recovery("exe-conn")
        engine.verify_recovery("vr-conn", "exe-conn")
        engine.resolve_disruption("dis-conn")

        snap = engine.continuity_snapshot("snap-gs1")
        assert snap.total_plans == 1
        assert snap.total_recovery_plans == 1
        assert snap.total_disruptions == 1
        assert snap.total_failovers == 1
        assert snap.total_recoveries == 1
        assert snap.total_verifications == 1


# ===================================================================
# 15. GOLDEN SCENARIO 2: Environment degradation, all recoveries fail
# ===================================================================


class TestGoldenScenario2AllRecoveriesFail:
    """GS-2: Environment degradation -> disruption -> recovery fails ->
    verify FAILED -> detect violations -> all_recoveries_failed."""

    def test_full_lifecycle(self, engine: ContinuityRuntimeEngine) -> None:
        # Setup
        engine.register_continuity_plan(
            "plan-env", "Env DR", "tenant-b",
            scope=ContinuityScope.ENVIRONMENT,
            rto_minutes=60,
        )
        engine.register_recovery_plan("rp-env", "plan-env", "Env Recovery", "tenant-b")
        engine.record_disruption(
            "dis-env", "tenant-b",
            scope=ContinuityScope.ENVIRONMENT,
            severity=DisruptionSeverity.CRITICAL,
            description="Environment degraded",
        )

        # Start recovery
        exe = engine.start_recovery("exe-env", "rp-env", "dis-env")
        assert exe.status == RecoveryStatus.IN_PROGRESS

        # Fail recovery
        exe_failed = engine.fail_recovery("exe-env")
        assert exe_failed.status == RecoveryStatus.FAILED

        # Verify FAILED (execution already terminal, no double-fail)
        vr = engine.verify_recovery("vr-env", "exe-env",
                                     status=RecoveryVerificationStatus.FAILED,
                                     reason="Environment still degraded")
        assert vr.status == RecoveryVerificationStatus.FAILED

        # Detect violations
        violations = engine.detect_continuity_violations()
        all_failed = [v for v in violations if v.operation == "all_recoveries_failed"]
        assert len(all_failed) == 1
        assert "dis-env" in all_failed[0].reason

    def test_violation_tenant_matches(self, engine: ContinuityRuntimeEngine) -> None:
        engine.register_continuity_plan("plan-env", "Env DR", "tenant-b")
        engine.register_recovery_plan("rp-env", "plan-env", "RP", "tenant-b")
        engine.record_disruption("dis-env", "tenant-b")
        engine.start_recovery("exe-env", "rp-env", "dis-env")
        engine.fail_recovery("exe-env")
        violations = engine.detect_continuity_violations()
        all_failed = [v for v in violations if v.operation == "all_recoveries_failed"]
        assert all_failed[0].tenant_id == "tenant-b"


# ===================================================================
# 16. GOLDEN SCENARIO 3: Activated plan with no recovery
# ===================================================================


class TestGoldenScenario3ActivatedNoRecovery:
    """GS-3: Activated plan with no recovery plans -> violation."""

    def test_violation_detected(self, engine: ContinuityRuntimeEngine) -> None:
        engine.register_continuity_plan("plan-no-rp", "No RP", "tenant-c")
        engine.activate_plan("plan-no-rp")
        violations = engine.detect_continuity_violations()
        assert len(violations) == 1
        assert violations[0].operation == "activated_no_recovery"
        assert violations[0].plan_id == "plan-no-rp"

    def test_adding_recovery_clears_violation(self, engine: ContinuityRuntimeEngine) -> None:
        engine.register_continuity_plan("plan-no-rp", "No RP", "tenant-c")
        engine.activate_plan("plan-no-rp")
        engine.detect_continuity_violations()
        # Now add recovery and re-check — but violation already recorded
        engine.register_recovery_plan("rp-fix", "plan-no-rp", "Fix", "tenant-c")
        # Second scan returns empty because violation was already recorded
        v2 = engine.detect_continuity_violations()
        assert len(v2) == 0

    def test_suspended_plan_not_violated(self, engine: ContinuityRuntimeEngine) -> None:
        engine.register_continuity_plan("plan-sus", "Sus", "tenant-c")
        engine.suspend_plan("plan-sus")
        violations = engine.detect_continuity_violations()
        activated_v = [v for v in violations if v.operation == "activated_no_recovery"]
        assert len(activated_v) == 0


# ===================================================================
# 17. GOLDEN SCENARIO 4: Failed failover, no recovery started
# ===================================================================


class TestGoldenScenario4FailedFailoverNoRecovery:
    """GS-4: Failover fails -> no recovery started -> violation."""

    def test_violation_detected(self, engine: ContinuityRuntimeEngine) -> None:
        engine.register_continuity_plan("plan-fo", "FO Plan", "tenant-d",
                                         failover_target_ref="backup")
        engine.record_disruption("dis-fo", "tenant-d")
        engine.trigger_failover("fo-fail", "plan-fo", "dis-fo")
        engine.fail_failover("fo-fail")
        violations = engine.detect_continuity_violations()
        fo_violations = [v for v in violations if v.operation == "failed_failover_no_recovery"]
        assert len(fo_violations) == 1

    def test_recovery_started_clears(self, engine: ContinuityRuntimeEngine) -> None:
        engine.register_continuity_plan("plan-fo", "FO Plan", "tenant-d")
        engine.register_recovery_plan("rp-fo", "plan-fo", "RP", "tenant-d")
        engine.record_disruption("dis-fo", "tenant-d")
        engine.trigger_failover("fo-fail", "plan-fo", "dis-fo")
        engine.fail_failover("fo-fail")
        engine.start_recovery("exe-fo", "rp-fo", "dis-fo")
        violations = engine.detect_continuity_violations()
        fo_violations = [v for v in violations if v.operation == "failed_failover_no_recovery"]
        assert len(fo_violations) == 0

    def test_violation_has_tenant(self, engine: ContinuityRuntimeEngine) -> None:
        engine.register_continuity_plan("plan-fo", "FO", "tenant-d")
        engine.record_disruption("dis-fo", "tenant-d")
        engine.trigger_failover("fo-fail", "plan-fo", "dis-fo")
        engine.fail_failover("fo-fail")
        violations = engine.detect_continuity_violations()
        fo_violations = [v for v in violations if v.operation == "failed_failover_no_recovery"]
        assert fo_violations[0].tenant_id == "tenant-d"


# ===================================================================
# 18. GOLDEN SCENARIO 5: Continuity drill with objectives
# ===================================================================


class TestGoldenScenario5ContinuityDrill:
    """GS-5: Register plan + recovery -> disruption -> failover -> recovery
    -> objective evaluation (met/not met) -> verify -> resolve."""

    def test_drill_objectives_met(self, engine: ContinuityRuntimeEngine) -> None:
        engine.register_continuity_plan(
            "plan-drill", "Drill Plan", "tenant-e",
            rto_minutes=30, rpo_minutes=15,
            failover_target_ref="dr-site",
        )
        engine.register_recovery_plan("rp-drill", "plan-drill", "Drill RP", "tenant-e")
        engine.record_disruption("dis-drill", "tenant-e", description="Scheduled drill")
        engine.trigger_failover("fo-drill", "plan-drill", "dis-drill")
        engine.complete_failover("fo-drill")
        engine.start_recovery("exe-drill", "rp-drill", "dis-drill")
        engine.complete_recovery("exe-drill")

        # Evaluate objectives
        obj_rto = engine.record_objective("obj-rto", "plan-drill", "RTO", 30, 25)
        obj_rpo = engine.record_objective("obj-rpo", "plan-drill", "RPO", 15, 10)
        assert obj_rto.met is True
        assert obj_rpo.met is True

        # Verify
        vr = engine.verify_recovery("vr-drill", "exe-drill",
                                     status=RecoveryVerificationStatus.PASSED,
                                     confidence=1.0)
        assert vr.status == RecoveryVerificationStatus.PASSED

        engine.resolve_disruption("dis-drill")

        # Check objectives for plan
        objs = engine.objectives_for_plan("plan-drill")
        assert len(objs) == 2
        assert all(o.met for o in objs)

    def test_drill_objective_not_met(self, engine: ContinuityRuntimeEngine) -> None:
        engine.register_continuity_plan("plan-drill2", "Drill 2", "tenant-e",
                                         rto_minutes=30, rpo_minutes=15)
        engine.register_recovery_plan("rp-drill2", "plan-drill2", "RP", "tenant-e")
        engine.record_disruption("dis-drill2", "tenant-e")
        engine.trigger_failover("fo-drill2", "plan-drill2", "dis-drill2")
        engine.complete_failover("fo-drill2")
        engine.start_recovery("exe-drill2", "rp-drill2", "dis-drill2")
        engine.complete_recovery("exe-drill2")

        obj_rto = engine.record_objective("obj-rto2", "plan-drill2", "RTO", 30, 45)
        assert obj_rto.met is False

    def test_drill_mixed_objectives(self, engine: ContinuityRuntimeEngine) -> None:
        engine.register_continuity_plan("plan-drill3", "Drill 3", "tenant-e",
                                         rto_minutes=30, rpo_minutes=15)
        obj_met = engine.record_objective("obj-met", "plan-drill3", "RTO", 30, 20)
        obj_missed = engine.record_objective("obj-missed", "plan-drill3", "RPO", 15, 25)
        assert obj_met.met is True
        assert obj_missed.met is False


# ===================================================================
# 19. GOLDEN SCENARIO 6: Multi-tenant isolation
# ===================================================================


class TestGoldenScenario6MultiTenantIsolation:
    """GS-6: Plans for 2 tenants -> plans_for_tenant/disruptions_for_tenant
    return only matching."""

    def test_plan_isolation(self, engine: ContinuityRuntimeEngine) -> None:
        engine.register_continuity_plan("plan-t1a", "T1-A", "tenant-1")
        engine.register_continuity_plan("plan-t1b", "T1-B", "tenant-1")
        engine.register_continuity_plan("plan-t2a", "T2-A", "tenant-2")

        t1_plans = engine.plans_for_tenant("tenant-1")
        t2_plans = engine.plans_for_tenant("tenant-2")
        assert len(t1_plans) == 2
        assert len(t2_plans) == 1
        assert all(p.tenant_id == "tenant-1" for p in t1_plans)
        assert all(p.tenant_id == "tenant-2" for p in t2_plans)

    def test_disruption_isolation(self, engine: ContinuityRuntimeEngine) -> None:
        engine.record_disruption("dis-t1a", "tenant-1")
        engine.record_disruption("dis-t1b", "tenant-1")
        engine.record_disruption("dis-t2a", "tenant-2")

        t1_dis = engine.disruptions_for_tenant("tenant-1")
        t2_dis = engine.disruptions_for_tenant("tenant-2")
        assert len(t1_dis) == 2
        assert len(t2_dis) == 1
        assert all(d.tenant_id == "tenant-1" for d in t1_dis)
        assert all(d.tenant_id == "tenant-2" for d in t2_dis)

    def test_nonexistent_tenant_empty(self, engine: ContinuityRuntimeEngine) -> None:
        engine.register_continuity_plan("plan-1", "P1", "tenant-1")
        engine.record_disruption("dis-1", "tenant-1")
        assert engine.plans_for_tenant("tenant-99") == ()
        assert engine.disruptions_for_tenant("tenant-99") == ()

    def test_plans_independent_lifecycle(self, engine: ContinuityRuntimeEngine) -> None:
        engine.register_continuity_plan("plan-t1", "T1", "tenant-1")
        engine.register_continuity_plan("plan-t2", "T2", "tenant-2")
        engine.activate_plan("plan-t1")
        engine.retire_plan("plan-t2")
        t1_plans = engine.plans_for_tenant("tenant-1")
        t2_plans = engine.plans_for_tenant("tenant-2")
        assert t1_plans[0].status == ContinuityStatus.ACTIVATED
        assert t2_plans[0].status == ContinuityStatus.RETIRED

    def test_failover_isolation(self, engine: ContinuityRuntimeEngine) -> None:
        engine.register_continuity_plan("plan-t1", "T1", "tenant-1")
        engine.register_continuity_plan("plan-t2", "T2", "tenant-2")
        engine.record_disruption("dis-t1", "tenant-1")
        engine.record_disruption("dis-t2", "tenant-2")
        engine.trigger_failover("fo-t1", "plan-t1", "dis-t1")
        engine.trigger_failover("fo-t2", "plan-t2", "dis-t2")
        assert len(engine.failovers_for_plan("plan-t1")) == 1
        assert len(engine.failovers_for_plan("plan-t2")) == 1

    def test_violation_tenant_isolation(self, engine: ContinuityRuntimeEngine) -> None:
        engine.register_continuity_plan("plan-t1", "T1", "tenant-1")
        engine.register_continuity_plan("plan-t2", "T2", "tenant-2")
        engine.activate_plan("plan-t1")
        engine.activate_plan("plan-t2")
        violations = engine.detect_continuity_violations()
        t1_v = [v for v in violations if v.tenant_id == "tenant-1"]
        t2_v = [v for v in violations if v.tenant_id == "tenant-2"]
        assert len(t1_v) == 1
        assert len(t2_v) == 1


# ===================================================================
# Additional edge cases
# ===================================================================


class TestEdgeCases:
    def test_register_many_plans(self, engine: ContinuityRuntimeEngine) -> None:
        for i in range(20):
            _make_plan(engine, f"plan-{i}", tenant_id="t-bulk")
        assert engine.plan_count == 20
        assert len(engine.plans_for_tenant("t-bulk")) == 20

    def test_multiple_snapshots_unique(self, engine: ContinuityRuntimeEngine) -> None:
        s1 = engine.continuity_snapshot("s-1")
        _make_plan(engine)
        s2 = engine.continuity_snapshot("s-2")
        assert s1.total_plans != s2.total_plans

    def test_failover_complete_then_rollback(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_failover(engine)
        engine.complete_failover("fo-1")
        rolled = engine.rollback_failover("fo-1")
        assert rolled.disposition == FailoverDisposition.ROLLED_BACK

    def test_cancel_recovery_no_completed_at(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        cancelled = engine.cancel_recovery("exe-1")
        # cancel_recovery does not set completed_at per the engine code
        assert cancelled.completed_at == ""

    def test_state_hash_two_engines_same_state(self, spine: EventSpineEngine) -> None:
        e1 = ContinuityRuntimeEngine(spine)
        e2 = ContinuityRuntimeEngine(EventSpineEngine())
        assert e1.state_hash() == e2.state_hash()

    def test_state_hash_diverges(self, spine: EventSpineEngine) -> None:
        e1 = ContinuityRuntimeEngine(spine)
        e2 = ContinuityRuntimeEngine(EventSpineEngine())
        _make_plan(e1)
        assert e1.state_hash() != e2.state_hash()

    def test_recovery_plan_multiple_plans(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine, "p1")
        _make_plan(engine, "p2")
        _make_recovery(engine, "rp-1", "p1")
        _make_recovery(engine, "rp-2", "p1")
        _make_recovery(engine, "rp-3", "p2")
        assert len(engine.recovery_plans_for_plan("p1")) == 2
        assert len(engine.recovery_plans_for_plan("p2")) == 1

    def test_disruption_all_severities(self, engine: ContinuityRuntimeEngine) -> None:
        for i, sev in enumerate(DisruptionSeverity):
            d = engine.record_disruption(f"d-{i}", "t-1", severity=sev)
            assert d.severity == sev

    def test_disruption_all_scopes(self, engine: ContinuityRuntimeEngine) -> None:
        for i, scope in enumerate(ContinuityScope):
            d = engine.record_disruption(f"d-{i}", "t-1", scope=scope)
            assert d.scope == scope

    def test_verification_confidence_zero(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        vr = engine.verify_recovery("v-1", "exe-1", confidence=0.0)
        assert vr.confidence == 0.0

    def test_verification_confidence_one(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        vr = engine.verify_recovery("v-1", "exe-1", confidence=1.0)
        assert vr.confidence == 1.0

    def test_plan_immutable(self, engine: ContinuityRuntimeEngine) -> None:
        plan = _make_plan(engine)
        with pytest.raises(AttributeError):
            plan.status = ContinuityStatus.RETIRED  # type: ignore[misc]

    def test_disruption_immutable(self, engine: ContinuityRuntimeEngine) -> None:
        d = _make_disruption(engine)
        with pytest.raises(AttributeError):
            d.severity = DisruptionSeverity.LOW  # type: ignore[misc]

    def test_failover_immutable(self, engine: ContinuityRuntimeEngine) -> None:
        fo = _setup_failover(engine)
        with pytest.raises(AttributeError):
            fo.disposition = FailoverDisposition.COMPLETED  # type: ignore[misc]

    def test_execution_immutable(self, engine: ContinuityRuntimeEngine) -> None:
        exe = _setup_execution(engine)
        with pytest.raises(AttributeError):
            exe.status = RecoveryStatus.COMPLETED  # type: ignore[misc]

    def test_objective_immutable(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        obj = engine.record_objective("obj-1", "plan-1", "RTO", 30, 20)
        with pytest.raises(AttributeError):
            obj.met = False  # type: ignore[misc]

    def test_verification_immutable(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        vr = engine.verify_recovery("v-1", "exe-1")
        with pytest.raises(AttributeError):
            vr.status = RecoveryVerificationStatus.FAILED  # type: ignore[misc]

    def test_snapshot_immutable(self, engine: ContinuityRuntimeEngine) -> None:
        snap = engine.continuity_snapshot("s1")
        with pytest.raises(AttributeError):
            snap.total_plans = 999  # type: ignore[misc]

    def test_activate_then_suspend_then_activate(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        engine.activate_plan("plan-1")
        engine.suspend_plan("plan-1")
        updated = engine.activate_plan("plan-1")
        assert updated.status == ContinuityStatus.ACTIVATED

    def test_multiple_disruptions_same_tenant(self, engine: ContinuityRuntimeEngine) -> None:
        for i in range(5):
            _make_disruption(engine, f"d-{i}", "t-1")
        assert len(engine.disruptions_for_tenant("t-1")) == 5

    def test_failover_preserves_source_ref(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine)
        _make_disruption(engine)
        fo = engine.trigger_failover("fo-1", "plan-1", "dis-1", source_ref="src-node")
        completed = engine.complete_failover("fo-1")
        assert completed.source_ref == "src-node"

    def test_failover_preserves_target_ref(self, engine: ContinuityRuntimeEngine) -> None:
        _make_plan(engine, failover_target_ref="tgt-node")
        _make_disruption(engine)
        fo = engine.trigger_failover("fo-1", "plan-1", "dis-1")
        completed = engine.complete_failover("fo-1")
        assert completed.target_ref == "tgt-node"

    def test_execution_preserves_recovery_plan_id(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        completed = engine.complete_recovery("exe-1")
        assert completed.recovery_plan_id == "rp-1"

    def test_execution_preserves_disruption_id(self, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        completed = engine.complete_recovery("exe-1")
        assert completed.disruption_id == "dis-1"

    def test_failed_verification_auto_fail_event_count(self, spine: EventSpineEngine, engine: ContinuityRuntimeEngine) -> None:
        _setup_execution(engine)
        before = spine.event_count
        engine.verify_recovery("v-1", "exe-1", status=RecoveryVerificationStatus.FAILED)
        # fail_recovery emits + verify_recovery emits = 2 events
        assert spine.event_count == before + 2

    def test_objectives_for_nonexistent_plan(self, engine: ContinuityRuntimeEngine) -> None:
        assert engine.objectives_for_plan("nonexistent") == ()

    def test_failovers_for_nonexistent_plan(self, engine: ContinuityRuntimeEngine) -> None:
        assert engine.failovers_for_plan("nonexistent") == ()

    def test_executions_for_nonexistent_disruption(self, engine: ContinuityRuntimeEngine) -> None:
        assert engine.executions_for_disruption("nonexistent") == ()

    def test_verifications_for_nonexistent_execution(self, engine: ContinuityRuntimeEngine) -> None:
        assert engine.verifications_for_execution("nonexistent") == ()

    def test_violations_for_nonexistent_plan(self, engine: ContinuityRuntimeEngine) -> None:
        assert engine.violations_for_plan("nonexistent") == ()
