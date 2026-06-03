"""Atomic tenant-status transitions under cross-replica concurrency (audit follow-up).

The TenantGatingRegistry validates a status transition against a read
(`update_status`: read current → check `_VALID_TRANSITIONS` → write) and
persists via an unconditional UPSERT (`status = EXCLUDED.status`). Guarded
only by a per-process lock, that is single-process safe — but across
replicas two callers can both read `active`, both validate (one to
`terminated`, one to `suspended`), and last-write-wins. The dangerous
case: a `terminated` tenant (permanent ban) gets overwritten with
`suspended`, regaining request admission. The `TERMINATED` terminal-state
invariant — `_VALID_TRANSITIONS[TERMINATED] = frozenset()` — is soft by N
replicas.

Fix (Atomic Store Doctrine): `TenantGatingStore.try_transition` performs a
conditional compare-and-set — set status iff the *committed* status is in
`allowed_from`. In-memory uses a `threading.Lock`; Postgres a single
`UPDATE ... WHERE status = ANY(allowed) RETURNING ...`. The registry
delegates via MRO override-detection.

These tests exercise the in-memory atomic path (fully, including
concurrency) plus dispatch and structural surfaces. The Postgres atomic
SQL is exercised by the gated integration suite.
"""
from __future__ import annotations

import threading

import pytest

from mcoi_runtime.governance.guards.tenant_gating import (
    InvalidTenantStatusTransitionError,
    TenantGatingRegistry,
    TenantGatingStore,
    TenantNotRegisteredError,
    TenantStatus,
)
from mcoi_runtime.persistence.postgres_governance_stores import (
    InMemoryTenantGatingStore,
    PostgresTenantGatingStore,
)

_CLOCK = lambda: "2026-06-03T00:00:00Z"  # noqa: E731

_ACTIVE = TenantStatus.ACTIVE
_SUSPENDED = TenantStatus.SUSPENDED
_TERMINATED = TenantStatus.TERMINATED


# ============================================================
# Base contract + override detection
# ============================================================


class TestTryTransitionContract:
    def test_base_returns_none(self):
        store = TenantGatingStore()
        assert (
            store.try_transition("t", frozenset({_ACTIVE}), _SUSPENDED, "", _CLOCK())
            is None
        )

    def test_in_memory_overrides_base(self):
        assert (
            InMemoryTenantGatingStore.try_transition
            is not TenantGatingStore.try_transition
        )

    def test_postgres_overrides_base(self):
        assert (
            PostgresTenantGatingStore.try_transition
            is not TenantGatingStore.try_transition
        )


# ============================================================
# InMemory try_transition semantics
# ============================================================


class TestInMemoryTryTransition:
    def test_success_when_current_in_allowed_from(self):
        store = InMemoryTenantGatingStore()
        store.save(_gate("t1", _ACTIVE))
        gate = store.try_transition("t1", frozenset({_ACTIVE}), _SUSPENDED, "quota", _CLOCK())
        assert gate is not None
        assert gate.status is _SUSPENDED
        assert store.load("t1").status is _SUSPENDED

    def test_rejected_when_current_not_in_allowed_from(self):
        store = InMemoryTenantGatingStore()
        store.save(_gate("t1", _TERMINATED))
        # Attempt terminated -> suspended: allowed_from for suspend is
        # {active}; terminated is not in it.
        gate = store.try_transition("t1", frozenset({_ACTIVE}), _SUSPENDED, "", _CLOCK())
        assert gate is None
        assert store.load("t1").status is _TERMINATED  # unchanged

    def test_rejected_for_unknown_tenant(self):
        store = InMemoryTenantGatingStore()
        assert store.try_transition("ghost", frozenset({_ACTIVE}), _SUSPENDED, "", _CLOCK()) is None


# ============================================================
# THE security property: terminated is terminal under concurrency
# ============================================================


class TestTerminalInvariantUnderConcurrency:
    def test_terminated_is_terminal_under_racing_transitions(self):
        """40 registries (replica stand-ins) sharing one store race on
        one tenant: half terminate, half suspend. Terminate can fire
        from active or suspended; nothing fires from terminated. So the
        committed final status is ALWAYS terminated — never un-terminated
        to suspended. (Pre-fix, the stale-read + unconditional UPSERT
        could land suspended over terminated.)"""
        store = InMemoryTenantGatingStore()
        seed = TenantGatingRegistry(clock=_CLOCK, store=store)
        seed.register("t1", status=_ACTIVE)

        outcomes: list[tuple[str, TenantStatus]] = []
        lock = threading.Lock()

        def worker(i: int):
            reg = TenantGatingRegistry(clock=_CLOCK, store=store)
            target = _TERMINATED if i % 2 == 0 else _SUSPENDED
            try:
                reg.update_status("t1", target, reason=f"w{i}")
                with lock:
                    outcomes.append(("ok", target))
            except InvalidTenantStatusTransitionError:
                with lock:
                    outcomes.append(("rejected", target))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(40)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Authoritative committed state: terminated, always.
        assert store.load("t1").status is _TERMINATED
        # At least one terminate succeeded; no suspend "ok" can have been
        # the last committed write (the store rejects suspend unless the
        # row is active, which it never is after the first move).
        assert ("ok", _TERMINATED) in outcomes

    def test_exactly_one_winner_for_single_step_transition(self):
        """50 threads all attempt active -> suspended on one tenant.
        Suspend is allowed only from active; the first commit moves the
        row off active, so exactly one wins and the rest are rejected."""
        store = InMemoryTenantGatingStore()
        seed = TenantGatingRegistry(clock=_CLOCK, store=store)
        seed.register("t1", status=_ACTIVE)

        wins: list[int] = []
        lock = threading.Lock()

        def worker(i: int):
            reg = TenantGatingRegistry(clock=_CLOCK, store=store)
            try:
                reg.update_status("t1", _SUSPENDED, reason=f"w{i}")
                with lock:
                    wins.append(i)
            except InvalidTenantStatusTransitionError:
                pass

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(wins) == 1
        assert store.load("t1").status is _SUSPENDED


# ============================================================
# Registry dispatch
# ============================================================


class TestRegistryDispatch:
    def test_registry_uses_store_override(self):
        store = InMemoryTenantGatingStore()
        reg = TenantGatingRegistry(clock=_CLOCK, store=store)
        reg.register("t1", status=_ACTIVE)
        gate = reg.update_status("t1", _TERMINATED, reason="ban")
        assert gate.status is _TERMINATED
        assert store.load("t1").status is _TERMINATED

    def test_registry_rejects_invalid_transition_via_store(self):
        store = InMemoryTenantGatingStore()
        reg = TenantGatingRegistry(clock=_CLOCK, store=store)
        reg.register("t1", status=_TERMINATED)
        with pytest.raises(InvalidTenantStatusTransitionError):
            reg.update_status("t1", _ACTIVE, reason="revive")  # terminal, no exit
        assert store.load("t1").status is _TERMINATED

    def test_registry_raises_not_registered_via_store(self):
        store = InMemoryTenantGatingStore()
        reg = TenantGatingRegistry(clock=_CLOCK, store=store)
        with pytest.raises(TenantNotRegisteredError):
            reg.update_status("ghost", _SUSPENDED)

    def test_registry_falls_through_for_legacy_store(self):
        # A store that does NOT override try_transition → registry uses
        # the legacy read-validate-write path, still correct single-process.
        class LegacyStore(TenantGatingStore):
            def __init__(self):
                self._g = {}

            def load(self, tid):
                return self._g.get(tid)

            def save(self, gate):
                self._g[gate.tenant_id] = gate

            def load_all(self):
                return list(self._g.values())

        store = LegacyStore()
        reg = TenantGatingRegistry(clock=_CLOCK, store=store)
        reg.register("t1", status=_ACTIVE)
        gate = reg.update_status("t1", _SUSPENDED)
        assert gate.status is _SUSPENDED

    def test_registry_no_store_uses_legacy(self):
        reg = TenantGatingRegistry(clock=_CLOCK)
        reg.register("t1", status=_ACTIVE)
        gate = reg.update_status("t1", _TERMINATED)
        assert gate.status is _TERMINATED


# ============================================================
# Postgres structural (no-DB)
# ============================================================


class TestPostgresTryTransitionStructure:
    def test_returns_none_without_connection(self):
        store = PostgresTenantGatingStore.__new__(PostgresTenantGatingStore)
        store._conn = None
        store._available = False
        store._lock = threading.Lock()
        assert (
            store.try_transition("t", frozenset({_ACTIVE}), _SUSPENDED, "", _CLOCK())
            is None
        )

    def test_empty_allowed_from_rejects_without_db(self):
        # No source state can reach the target (e.g. -> onboarding):
        # reject without touching the DB, never raise.
        store = PostgresTenantGatingStore.__new__(PostgresTenantGatingStore)
        store._conn = None
        store._available = False
        store._lock = threading.Lock()
        assert store.try_transition("t", frozenset(), _ACTIVE, "", _CLOCK()) is None


def _gate(tenant_id: str, status: TenantStatus):
    from mcoi_runtime.governance.guards.tenant_gating import TenantGate
    return TenantGate(tenant_id=tenant_id, status=status, reason="", gated_at=_CLOCK())
