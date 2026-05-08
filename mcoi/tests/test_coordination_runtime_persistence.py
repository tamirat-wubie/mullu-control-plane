"""Purpose: verify explicit persistence and restore for live coordination records.
Governance scope: coordination runtime persistence only.
Dependencies: access runtime, team runtime, coordination persistence bridge, coordination store.
Invariants:
  - Delegation records persist and restore deterministically.
  - Handoff records persist and restore deterministically.
  - Restore fails closed when engine prerequisites are missing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.contracts.access_runtime import AuthContextKind, IdentityKind, RoleKind
from mcoi_runtime.contracts.roles import HandoffReason, WorkerProfile, WorkerStatus
from mcoi_runtime.core.coordination_persistence import CoordinationPersistenceBridge
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.team_runtime import TeamEngine, WorkerRegistry
from mcoi_runtime.governance.guards.access import AccessRuntimeEngine
from mcoi_runtime.persistence.coordination_store import CoordinationStore


_TS = "2026-05-01T12:00:00+00:00"


def _setup_access_engine() -> AccessRuntimeEngine:
    engine = AccessRuntimeEngine(EventSpineEngine())
    engine.register_identity("from-1", "From", kind=IdentityKind.HUMAN, tenant_id="tenant-1")
    engine.register_identity("to-1", "To", kind=IdentityKind.HUMAN, tenant_id="tenant-1")
    engine.register_role(
        "role-1",
        "Operator",
        kind=RoleKind.OPERATOR,
        permissions=["workflow:handoff"],
    )
    return engine


def _setup_team_engine() -> TeamEngine:
    registry = WorkerRegistry(clock=lambda: _TS)
    registry.register_worker(
        WorkerProfile(
            worker_id="worker-1",
            name="Worker One",
            roles=("role-1",),
            max_concurrent_jobs=2,
            status=WorkerStatus.AVAILABLE,
        )
    )
    registry.register_worker(
        WorkerProfile(
            worker_id="worker-2",
            name="Worker Two",
            roles=("role-1",),
            max_concurrent_jobs=2,
            status=WorkerStatus.AVAILABLE,
        )
    )
    return TeamEngine(registry=registry, clock=lambda: _TS)


def test_delegation_records_round_trip_through_coordination_store(tmp_path: Path) -> None:
    store = CoordinationStore(tmp_path / "coordination")
    source = _setup_access_engine()
    delegation = source.delegate_permission(
        "delegation-1",
        "from-1",
        "to-1",
        "role-1",
        scope_kind=AuthContextKind.WORKSPACE,
        scope_ref_id="workspace-1",
    )

    saved = CoordinationPersistenceBridge.save_delegations(store, source)
    restored = _setup_access_engine()
    restored_count = CoordinationPersistenceBridge.restore_delegations(store, restored)

    assert saved == 1
    assert restored_count == 1
    assert store.list_states() == (f"delegation-{delegation.delegation_id}",)
    assert restored.delegation_count == 1
    assert restored.list_delegations()[0] == delegation


def test_handoff_records_round_trip_through_coordination_store(tmp_path: Path) -> None:
    store = CoordinationStore(tmp_path / "coordination")
    source = _setup_team_engine()
    handoff = source.handoff_job(
        "job-1",
        "worker-1",
        "worker-2",
        HandoffReason.ESCALATION,
        thread_id="thread-1",
    )

    saved = CoordinationPersistenceBridge.save_handoffs(store, source)
    restored = _setup_team_engine()
    restored_count = CoordinationPersistenceBridge.restore_handoffs(store, restored)

    assert saved == 1
    assert restored_count == 1
    assert store.list_states() == (f"handoff-{handoff.handoff_id}",)
    assert restored.handoff_count == 1
    assert restored.get_handoff(handoff.handoff_id) == handoff


def test_restore_fails_closed_when_coordination_prerequisites_are_missing(tmp_path: Path) -> None:
    store = CoordinationStore(tmp_path / "coordination")
    source = _setup_team_engine()
    source.handoff_job("job-1", "worker-1", "worker-2", HandoffReason.CAPACITY_EXCEEDED)
    saved = CoordinationPersistenceBridge.save_handoffs(store, source)

    registry = WorkerRegistry(clock=lambda: _TS)
    registry.register_worker(
        WorkerProfile(
            worker_id="worker-1",
            name="Worker One",
            roles=("role-1",),
            max_concurrent_jobs=2,
            status=WorkerStatus.AVAILABLE,
        )
    )
    incomplete = TeamEngine(registry=registry, clock=lambda: _TS)

    assert saved == 1
    assert len(store.list_states()) == 1
    with pytest.raises(RuntimeCoreInvariantError, match="worker not found"):
        CoordinationPersistenceBridge.restore_handoffs(store, incomplete)
    assert incomplete.handoff_count == 0
