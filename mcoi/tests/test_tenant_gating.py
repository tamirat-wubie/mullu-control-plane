"""Phase 2D — Tenant Gating tests.

Tests: TenantGatingRegistry lifecycle management, status transitions,
    guard integration, store persistence, error cases.
"""

import threading
import time

import pytest
from mcoi_runtime.core.tenant_gating import (
    InvalidTenantStatusTransitionError,
    TenantGate,
    TenantAlreadyRegisteredError,
    TenantGatingRegistry,
    TenantGatingStore,
    TenantNotRegisteredError,
    TenantStatus,
    create_tenant_gating_guard,
)
from mcoi_runtime.core.governance_guard import GovernanceGuardChain
from mcoi_runtime.persistence.postgres_governance_stores import (
    InMemoryTenantGatingStore,
    PostgresTenantGatingStore,
    GOVERNANCE_MIGRATIONS,
)


def _clock() -> str:
    return "2026-01-01T00:00:00Z"


# ═══ TenantStatus Enum ═══


class TestTenantStatus:
    def test_all_states(self):
        assert TenantStatus.ACTIVE == "active"
        assert TenantStatus.ONBOARDING == "onboarding"
        assert TenantStatus.SUSPENDED == "suspended"
        assert TenantStatus.TERMINATED == "terminated"

    def test_string_conversion(self):
        assert str(TenantStatus.ACTIVE) == "TenantStatus.ACTIVE"
        assert TenantStatus.ACTIVE.value == "active"


# ═══ TenantGatingRegistry — Registration ═══


class TestRegistration:
    def test_register_new_tenant(self):
        reg = TenantGatingRegistry(clock=_clock)
        gate = reg.register("t1")
        assert gate.tenant_id == "t1"
        assert gate.status == TenantStatus.ONBOARDING

    def test_register_with_custom_status(self):
        reg = TenantGatingRegistry(clock=_clock)
        gate = reg.register("t1", status=TenantStatus.ACTIVE)
        assert gate.status == TenantStatus.ACTIVE

    def test_register_with_reason(self):
        reg = TenantGatingRegistry(clock=_clock)
        gate = reg.register("t1", reason="new customer signup")
        assert gate.reason == "new customer signup"

    def test_duplicate_registration_raises(self):
        reg = TenantGatingRegistry(clock=_clock)
        reg.register("t1")
        with pytest.raises(TenantAlreadyRegisteredError) as excinfo:
            reg.register("t1")
        assert excinfo.value.tenant_id == "t1"

    def test_tenant_count(self):
        reg = TenantGatingRegistry(clock=_clock)
        assert reg.tenant_count == 0
        reg.register("t1")
        reg.register("t2")
        assert reg.tenant_count == 2


# ═══ TenantGatingRegistry — Status Transitions ═══


class TestStatusTransitions:
    def test_onboarding_to_active(self):
        reg = TenantGatingRegistry(clock=_clock)
        reg.register("t1", status=TenantStatus.ONBOARDING)
        gate = reg.update_status("t1", TenantStatus.ACTIVE, "onboarding complete")
        assert gate.status == TenantStatus.ACTIVE

    def test_active_to_suspended(self):
        reg = TenantGatingRegistry(clock=_clock)
        reg.register("t1", status=TenantStatus.ACTIVE)
        gate = reg.update_status("t1", TenantStatus.SUSPENDED, "payment overdue")
        assert gate.status == TenantStatus.SUSPENDED

    def test_suspended_to_active(self):
        reg = TenantGatingRegistry(clock=_clock)
        reg.register("t1", status=TenantStatus.ACTIVE)
        reg.update_status("t1", TenantStatus.SUSPENDED)
        gate = reg.update_status("t1", TenantStatus.ACTIVE, "payment received")
        assert gate.status == TenantStatus.ACTIVE

    def test_active_to_terminated(self):
        reg = TenantGatingRegistry(clock=_clock)
        reg.register("t1", status=TenantStatus.ACTIVE)
        gate = reg.update_status("t1", TenantStatus.TERMINATED, "account closed")
        assert gate.status == TenantStatus.TERMINATED

    def test_terminated_is_terminal(self):
        reg = TenantGatingRegistry(clock=_clock)
        reg.register("t1", status=TenantStatus.ACTIVE)
        reg.update_status("t1", TenantStatus.TERMINATED)
        with pytest.raises(InvalidTenantStatusTransitionError) as excinfo:
            reg.update_status("t1", TenantStatus.ACTIVE)
        assert excinfo.value.tenant_id == "t1"
        assert excinfo.value.current_status == TenantStatus.TERMINATED
        assert excinfo.value.new_status == TenantStatus.ACTIVE

    def test_invalid_backward_transition(self):
        reg = TenantGatingRegistry(clock=_clock)
        reg.register("t1", status=TenantStatus.ACTIVE)
        with pytest.raises(InvalidTenantStatusTransitionError) as excinfo:
            reg.update_status("t1", TenantStatus.ONBOARDING)
        assert excinfo.value.tenant_id == "t1"
        assert excinfo.value.current_status == TenantStatus.ACTIVE
        assert excinfo.value.new_status == TenantStatus.ONBOARDING

    def test_unknown_tenant_raises(self):
        reg = TenantGatingRegistry(clock=_clock)
        with pytest.raises(TenantNotRegisteredError) as excinfo:
            reg.update_status("unknown", TenantStatus.ACTIVE)
        assert excinfo.value.tenant_id == "unknown"


# ═══ TenantGatingRegistry — Query ═══


class TestQuery:
    def test_get_status(self):
        reg = TenantGatingRegistry(clock=_clock)
        reg.register("t1", status=TenantStatus.ACTIVE)
        gate = reg.get_status("t1")
        assert gate is not None
        assert gate.status == TenantStatus.ACTIVE

    def test_get_unknown_tenant(self):
        reg = TenantGatingRegistry(clock=_clock)
        assert reg.get_status("unknown") is None

    def test_is_allowed_active(self):
        reg = TenantGatingRegistry(clock=_clock)
        reg.register("t1", status=TenantStatus.ACTIVE)
        assert reg.is_allowed("t1") is True

    def test_is_allowed_onboarding(self):
        reg = TenantGatingRegistry(clock=_clock)
        reg.register("t1", status=TenantStatus.ONBOARDING)
        assert reg.is_allowed("t1") is True

    def test_is_blocked_suspended(self):
        reg = TenantGatingRegistry(clock=_clock)
        reg.register("t1", status=TenantStatus.ACTIVE)
        reg.update_status("t1", TenantStatus.SUSPENDED)
        assert reg.is_allowed("t1") is False

    def test_is_blocked_terminated(self):
        reg = TenantGatingRegistry(clock=_clock)
        reg.register("t1", status=TenantStatus.ACTIVE)
        reg.update_status("t1", TenantStatus.TERMINATED)
        assert reg.is_allowed("t1") is False

    def test_unknown_tenant_is_allowed(self):
        reg = TenantGatingRegistry(clock=_clock)
        assert reg.is_allowed("unknown") is True

    def test_all_gates(self):
        reg = TenantGatingRegistry(clock=_clock)
        reg.register("t2", status=TenantStatus.ACTIVE)
        reg.register("t1", status=TenantStatus.ONBOARDING)
        gates = reg.all_gates()
        assert len(gates) == 2
        assert gates[0].tenant_id == "t1"  # Sorted
        assert gates[1].tenant_id == "t2"

    def test_summary(self):
        reg = TenantGatingRegistry(clock=_clock)
        reg.register("t1", status=TenantStatus.ACTIVE)
        reg.register("t2", status=TenantStatus.ACTIVE)
        reg.register("t3", status=TenantStatus.ONBOARDING)
        summary = reg.summary()
        assert summary["total_tenants"] == 3
        assert summary["status_counts"]["active"] == 2
        assert summary["status_counts"]["onboarding"] == 1


# ═══ Tenant Gating Guard ═══


class TestTenantGatingGuard:
    def test_allows_active_tenant(self):
        reg = TenantGatingRegistry(clock=_clock)
        reg.register("t1", status=TenantStatus.ACTIVE)
        guard = create_tenant_gating_guard(reg)
        result = guard.check({"tenant_id": "t1", "endpoint": "/api/test"})
        assert result.allowed

    def test_allows_onboarding_tenant(self):
        reg = TenantGatingRegistry(clock=_clock)
        reg.register("t1", status=TenantStatus.ONBOARDING)
        guard = create_tenant_gating_guard(reg)
        result = guard.check({"tenant_id": "t1", "endpoint": "/api/test"})
        assert result.allowed

    def test_blocks_suspended_tenant(self):
        reg = TenantGatingRegistry(clock=_clock)
        reg.register("t1", status=TenantStatus.ACTIVE)
        reg.update_status("t1", TenantStatus.SUSPENDED, "payment issue")
        guard = create_tenant_gating_guard(reg)
        result = guard.check({"tenant_id": "t1", "endpoint": "/api/test"})
        assert not result.allowed
        assert "suspended" in result.reason

    def test_blocks_terminated_tenant(self):
        reg = TenantGatingRegistry(clock=_clock)
        reg.register("t1", status=TenantStatus.ACTIVE)
        reg.update_status("t1", TenantStatus.TERMINATED, "account closed")
        guard = create_tenant_gating_guard(reg)
        result = guard.check({"tenant_id": "t1", "endpoint": "/api/test"})
        assert not result.allowed
        assert "terminated" in result.reason

    def test_allows_unknown_tenant(self):
        reg = TenantGatingRegistry(clock=_clock)
        guard = create_tenant_gating_guard(reg)
        result = guard.check({"tenant_id": "new-tenant", "endpoint": "/api/test"})
        assert result.allowed

    def test_allows_system_tenant(self):
        reg = TenantGatingRegistry(clock=_clock)
        guard = create_tenant_gating_guard(reg)
        result = guard.check({"tenant_id": "system", "endpoint": "/api/test"})
        assert result.allowed

    def test_allows_empty_tenant(self):
        reg = TenantGatingRegistry(clock=_clock)
        guard = create_tenant_gating_guard(reg)
        result = guard.check({"endpoint": "/api/test"})
        assert result.allowed

    def test_guard_in_chain(self):
        reg = TenantGatingRegistry(clock=_clock)
        reg.register("blocked", status=TenantStatus.ACTIVE)
        reg.update_status("blocked", TenantStatus.SUSPENDED, "test")
        guard = create_tenant_gating_guard(reg)
        chain = GovernanceGuardChain()
        chain.add(guard)
        result = chain.evaluate({"tenant_id": "blocked", "endpoint": "/api/test"})
        assert not result.allowed
        assert result.blocking_guard == "tenant_gating"


# ═══ Store Integration ═══


class TestStoreIntegration:
    def test_registry_with_store(self):
        store = InMemoryTenantGatingStore()
        reg = TenantGatingRegistry(clock=_clock, store=store)
        reg.register("t1", status=TenantStatus.ACTIVE)
        stored = store.load("t1")
        assert stored is not None
        assert stored.status == TenantStatus.ACTIVE

    def test_store_updated_on_status_change(self):
        store = InMemoryTenantGatingStore()
        reg = TenantGatingRegistry(clock=_clock, store=store)
        reg.register("t1", status=TenantStatus.ACTIVE)
        reg.update_status("t1", TenantStatus.SUSPENDED)
        stored = store.load("t1")
        assert stored.status == TenantStatus.SUSPENDED

    def test_store_load_on_get_status(self):
        store = InMemoryTenantGatingStore()
        # Pre-populate store
        store.save(TenantGate(
            tenant_id="t1", status=TenantStatus.ACTIVE,
            reason="pre-existing", gated_at="2026-01-01",
        ))
        reg = TenantGatingRegistry(clock=_clock, store=store)
        gate = reg.get_status("t1")
        assert gate is not None
        assert gate.status == TenantStatus.ACTIVE

    def test_register_rejects_existing_store_tenant(self):
        store = InMemoryTenantGatingStore()
        store.save(TenantGate(
            tenant_id="t1", status=TenantStatus.ACTIVE,
            reason="pre-existing", gated_at="2026-01-01",
        ))
        reg = TenantGatingRegistry(clock=_clock, store=store)
        with pytest.raises(TenantAlreadyRegisteredError):
            reg.register("t1", status=TenantStatus.ONBOARDING)

    def test_all_gates_hydrates_prepopulated_store(self):
        store = InMemoryTenantGatingStore()
        store.save(TenantGate(tenant_id="t2", status=TenantStatus.ACTIVE, gated_at="now"))
        store.save(TenantGate(tenant_id="t1", status=TenantStatus.ONBOARDING, gated_at="now"))
        reg = TenantGatingRegistry(clock=_clock, store=store)

        gates = reg.all_gates()

        assert [gate.tenant_id for gate in gates] == ["t1", "t2"]
        assert reg.tenant_count == 2
        assert reg.summary()["total_tenants"] == 2

    def test_inmemory_store_load_all(self):
        store = InMemoryTenantGatingStore()
        store.save(TenantGate(tenant_id="t2", status=TenantStatus.ACTIVE, gated_at="now"))
        store.save(TenantGate(tenant_id="t1", status=TenantStatus.ONBOARDING, gated_at="now"))
        all_gates = store.load_all()
        assert len(all_gates) == 2
        assert all_gates[0].tenant_id == "t1"  # Sorted

    def test_all_gates_snapshot_stable_during_register(self):
        iter_started = threading.Event()

        class _CoordinatedGateDict(dict[str, TenantGate]):
            def values(self):  # type: ignore[override]
                first = True
                for value in super().values():
                    if first:
                        first = False
                        iter_started.set()
                        time.sleep(0.05)
                    yield value

        reg = TenantGatingRegistry(clock=_clock)
        reg._gates = _CoordinatedGateDict()
        reg.register("t1", status=TenantStatus.ACTIVE)

        def _register() -> None:
            assert iter_started.wait(timeout=1.0)
            reg.register("t2", status=TenantStatus.ONBOARDING)

        worker = threading.Thread(target=_register)
        worker.start()
        snapshot = reg.all_gates()
        worker.join(timeout=1.0)

        assert not worker.is_alive()
        assert [gate.tenant_id for gate in snapshot] == ["t1"]
        assert [gate.tenant_id for gate in reg.all_gates()] == ["t1", "t2"]


# ═══ PostgresTenantGatingStore Structural ═══


class TestPostgresTenantGatingStoreStructure:
    def test_inherits_store(self):
        assert issubclass(PostgresTenantGatingStore, TenantGatingStore)

    def test_graceful_without_connection(self):
        store = PostgresTenantGatingStore.__new__(PostgresTenantGatingStore)
        store._conn = None
        store._available = False
        store._lock = __import__("threading").Lock()
        assert store.load("t1") is None
        store.save(TenantGate(tenant_id="t1", status=TenantStatus.ACTIVE, gated_at="now"))
        assert store.load_all() == []

    def test_migration_sql_exists(self):
        assert len(GOVERNANCE_MIGRATIONS) == 4
        assert "governance_tenant_gates" in GOVERNANCE_MIGRATIONS[3]
