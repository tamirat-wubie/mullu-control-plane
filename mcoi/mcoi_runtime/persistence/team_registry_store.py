"""Purpose: explicit local persistence for team registry state.
Governance scope: persistence layer worker, role, policy, and load-state storage only.
Dependencies: team runtime contracts, deterministic JSON helpers, persistence errors.
Invariants:
  - Worker, role, and policy serialization is deterministic and identifier-sorted.
  - Load-state serialization preserves exact current_load, including overload.
  - Load fails closed on malformed content or missing fields.
  - Restore is explicit; this module never auto-loads on import.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcoi_runtime.contracts.roles import AssignmentPolicy, RoleDescriptor, WorkerProfile
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.team_runtime import WorkerLoadState, WorkerRegistry

from ._serialization import deserialize_record, loads_strict_json, serialize_record
from .errors import CorruptedDataError, PersistenceError, PersistenceWriteError


def _deterministic_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


def _bounded_store_error(summary: str, exc: BaseException) -> str:
    return f"{summary} ({type(exc).__name__})"


def _atomic_write(path: Path, content: str) -> None:
    """Write content to a file atomically via temp-file-then-rename."""
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    try:
        fd, tmp_path = tempfile.mkstemp(dir=str(parent), suffix=".tmp")
        try:
            os.write(fd, content.encode("utf-8"))
            os.close(fd)
            fd = -1
            os.replace(tmp_path, str(path))
        except BaseException:
            if fd >= 0:
                os.close(fd)
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
    except OSError as exc:
        raise PersistenceWriteError(_bounded_store_error("team registry write failed", exc)) from exc


def _record_payload(record: object) -> dict[str, Any]:
    payload = loads_strict_json(serialize_record(record))
    if not isinstance(payload, dict):
        raise PersistenceError("serialized registry record must be a JSON object")
    return payload


def _deserialize_contract(raw: object, record_type: type) -> object:
    if not isinstance(raw, dict):
        raise CorruptedDataError(f"{record_type.__name__} payload must be a JSON object")
    return deserialize_record(_deterministic_json(raw), record_type)


def _deserialize_load_state(raw: object) -> WorkerLoadState:
    if not isinstance(raw, dict):
        raise CorruptedDataError("WorkerLoadState payload must be a JSON object")
    try:
        return WorkerLoadState(
            worker_id=raw["worker_id"],
            current_load=raw["current_load"],
        )
    except (KeyError, TypeError, ValueError, RuntimeCoreInvariantError) as exc:
        raise CorruptedDataError(_bounded_store_error("invalid WorkerLoadState payload", exc)) from exc


@dataclass(frozen=True, slots=True)
class TeamRegistryState:
    """Explicit snapshot of registry records for deterministic save/load."""

    workers: tuple[WorkerProfile, ...]
    roles: tuple[RoleDescriptor, ...]
    policies: tuple[AssignmentPolicy, ...]
    load_states: tuple[WorkerLoadState, ...]

    def __post_init__(self) -> None:
        if any(not isinstance(worker, WorkerProfile) for worker in self.workers):
            raise PersistenceError("workers must contain WorkerProfile instances only")
        if any(not isinstance(role, RoleDescriptor) for role in self.roles):
            raise PersistenceError("roles must contain RoleDescriptor instances only")
        if any(not isinstance(policy, AssignmentPolicy) for policy in self.policies):
            raise PersistenceError("policies must contain AssignmentPolicy instances only")
        if any(not isinstance(state, WorkerLoadState) for state in self.load_states):
            raise PersistenceError("load_states must contain WorkerLoadState instances only")


class TeamRegistryStore:
    """Persist explicit team registry state as a deterministic JSON witness."""

    def __init__(self, base_path: Path) -> None:
        if not isinstance(base_path, Path):
            raise PersistenceError("base_path must be a Path instance")
        self._base_path = base_path

    def _registry_path(self) -> Path:
        return self._base_path / "team_registry.json"

    def save_registry(self, registry: WorkerRegistry) -> str:
        if not isinstance(registry, WorkerRegistry):
            raise PersistenceError("registry must be a WorkerRegistry instance")

        payload = {
            "workers": [_record_payload(worker) for worker in registry.list_workers()],
            "roles": [_record_payload(role) for role in registry.list_roles()],
            "policies": [_record_payload(policy) for policy in registry.list_policies()],
            "load_states": [
                {
                    "worker_id": state.worker_id,
                    "current_load": state.current_load,
                }
                for state in registry.list_load_states()
            ],
        }
        content = _deterministic_json(payload)
        _atomic_write(self._registry_path(), content)
        return content

    def load_registry_state(self) -> TeamRegistryState:
        path = self._registry_path()
        if not path.exists():
            raise CorruptedDataError("team registry file not found")
        try:
            payload = loads_strict_json(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            raise CorruptedDataError(_bounded_store_error("malformed team registry file", exc)) from exc
        if not isinstance(payload, dict):
            raise CorruptedDataError("team registry payload must be a JSON object")

        workers_raw = payload.get("workers")
        roles_raw = payload.get("roles")
        policies_raw = payload.get("policies")
        load_states_raw = payload.get("load_states")
        if not isinstance(workers_raw, list):
            raise CorruptedDataError("team registry workers must be a JSON array")
        if not isinstance(roles_raw, list):
            raise CorruptedDataError("team registry roles must be a JSON array")
        if not isinstance(policies_raw, list):
            raise CorruptedDataError("team registry policies must be a JSON array")
        if not isinstance(load_states_raw, list):
            raise CorruptedDataError("team registry load_states must be a JSON array")

        return TeamRegistryState(
            workers=tuple(
                _deserialize_contract(raw, WorkerProfile) for raw in workers_raw
            ),
            roles=tuple(
                _deserialize_contract(raw, RoleDescriptor) for raw in roles_raw
            ),
            policies=tuple(
                _deserialize_contract(raw, AssignmentPolicy) for raw in policies_raw
            ),
            load_states=tuple(
                _deserialize_load_state(raw) for raw in load_states_raw
            ),
        )

    def restore_registry(self, registry: WorkerRegistry) -> TeamRegistryState:
        if not isinstance(registry, WorkerRegistry):
            raise PersistenceError("registry must be a WorkerRegistry instance")

        state = self.load_registry_state()
        self._validate_restore_preconditions(registry, state)
        for role in state.roles:
            registry.restore_role(role)
        for worker in state.workers:
            registry.restore_worker(worker)
        for policy in state.policies:
            registry.restore_policy(policy)
        for load_state in state.load_states:
            registry.restore_load_state(load_state)
        return state

    def exists(self) -> bool:
        return self._registry_path().exists()

    @staticmethod
    def _validate_restore_preconditions(
        registry: WorkerRegistry,
        state: TeamRegistryState,
    ) -> None:
        role_ids = tuple(role.role_id for role in state.roles)
        worker_ids = tuple(worker.worker_id for worker in state.workers)
        policy_ids = tuple(policy.policy_id for policy in state.policies)
        load_worker_ids = tuple(load_state.worker_id for load_state in state.load_states)

        TeamRegistryStore._require_unique(role_ids, label="role")
        TeamRegistryStore._require_unique(worker_ids, label="worker")
        TeamRegistryStore._require_unique(policy_ids, label="policy")
        TeamRegistryStore._require_unique(load_worker_ids, label="load_state worker")

        for role_id in role_ids:
            if registry.get_role(role_id) is not None:
                raise RuntimeCoreInvariantError(f"role already registered: {role_id}")
        for worker_id in worker_ids:
            if registry.get_worker(worker_id) is not None:
                raise RuntimeCoreInvariantError(f"worker already registered: {worker_id}")
        for policy_id in policy_ids:
            if registry.get_policy(policy_id) is not None:
                raise RuntimeCoreInvariantError(f"policy already registered: {policy_id}")

        persisted_workers = set(worker_ids)
        for worker_id in load_worker_ids:
            if worker_id not in persisted_workers and registry.get_worker(worker_id) is None:
                raise RuntimeCoreInvariantError(f"worker not found: {worker_id}")

    @staticmethod
    def _require_unique(ids: tuple[str, ...], *, label: str) -> None:
        if len(ids) != len(set(ids)):
            raise CorruptedDataError(f"duplicate {label} identifier in team registry payload")
