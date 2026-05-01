"""Purpose: explicit persistence bridge for governed coordination records.
Governance scope: coordination persistence only — no live coordination logic.
Dependencies: access/team runtime engines, coordination store, delegation and handoff contracts.
Invariants:
  - Persisted delegation and handoff records retain stable identity prefixes.
  - Restore is explicit and fail-closed on prerequisite mismatch.
  - Bridge never invents coordination records.
"""

from __future__ import annotations

from mcoi_runtime.contracts.access_runtime import DelegationRecord
from mcoi_runtime.contracts.roles import HandoffRecord
from mcoi_runtime.core.access_runtime import AccessRuntimeEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.team_runtime import TeamEngine
from mcoi_runtime.persistence.coordination_store import CoordinationStore


_DELEGATION_PREFIX = "delegation"
_HANDOFF_PREFIX = "handoff"


def _state_id(prefix: str, record_id: str) -> str:
    return f"{prefix}-{record_id}"


class CoordinationPersistenceBridge:
    """Bridge between live coordination engines and explicit persistent storage."""

    @staticmethod
    def save_delegations(
        store: CoordinationStore,
        engine: AccessRuntimeEngine,
    ) -> int:
        if not isinstance(store, CoordinationStore):
            raise RuntimeCoreInvariantError("store must be a CoordinationStore")
        if not isinstance(engine, AccessRuntimeEngine):
            raise RuntimeCoreInvariantError("engine must be an AccessRuntimeEngine")

        count = 0
        for record in engine.list_delegations():
            store.save_state(_state_id(_DELEGATION_PREFIX, record.delegation_id), record)
            count += 1
        return count

    @staticmethod
    def restore_delegations(
        store: CoordinationStore,
        engine: AccessRuntimeEngine,
    ) -> int:
        if not isinstance(store, CoordinationStore):
            raise RuntimeCoreInvariantError("store must be a CoordinationStore")
        if not isinstance(engine, AccessRuntimeEngine):
            raise RuntimeCoreInvariantError("engine must be an AccessRuntimeEngine")

        count = 0
        for state_id in store.list_states():
            if not state_id.startswith(f"{_DELEGATION_PREFIX}-"):
                continue
            record = store.load_state(state_id, DelegationRecord)
            engine.restore_delegation(record)
            count += 1
        return count

    @staticmethod
    def save_handoffs(
        store: CoordinationStore,
        engine: TeamEngine,
    ) -> int:
        if not isinstance(store, CoordinationStore):
            raise RuntimeCoreInvariantError("store must be a CoordinationStore")
        if not isinstance(engine, TeamEngine):
            raise RuntimeCoreInvariantError("engine must be a TeamEngine")

        count = 0
        for record in engine.list_handoffs():
            store.save_state(_state_id(_HANDOFF_PREFIX, record.handoff_id), record)
            count += 1
        return count

    @staticmethod
    def restore_handoffs(
        store: CoordinationStore,
        engine: TeamEngine,
    ) -> int:
        if not isinstance(store, CoordinationStore):
            raise RuntimeCoreInvariantError("store must be a CoordinationStore")
        if not isinstance(engine, TeamEngine):
            raise RuntimeCoreInvariantError("engine must be a TeamEngine")

        count = 0
        for state_id in store.list_states():
            if not state_id.startswith(f"{_HANDOFF_PREFIX}-"):
                continue
            record = store.load_state(state_id, HandoffRecord)
            engine.restore_handoff(record)
            count += 1
        return count
