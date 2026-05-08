"""Purpose: verify explicit persistence and restore for team registry state.
Governance scope: worker, role, policy, and load-state persistence only.
Dependencies: team runtime, team registry store, persistence errors.
Invariants:
  - Team registry serialization is deterministic for the same input.
  - Restore preserves exact current load, including overloaded workers.
  - Malformed payloads fail closed.
  - Restore preconditions reject missing worker references before mutation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.contracts.roles import (
    AssignmentPolicy,
    AssignmentStrategy,
    RoleDescriptor,
    WorkerProfile,
    WorkerStatus,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.team_runtime import WorkerRegistry
from mcoi_runtime.persistence.errors import CorruptedDataError
from mcoi_runtime.persistence.team_registry_store import TeamRegistryStore


_TS = "2026-05-01T12:00:00+00:00"


def _build_registry() -> WorkerRegistry:
    registry = WorkerRegistry(clock=lambda: _TS)
    registry.register_role(
        RoleDescriptor(
            role_id="role-ops",
            name="Operations",
            description="Handles live operations",
            required_skills=("shell",),
        )
    )
    registry.register_role(
        RoleDescriptor(
            role_id="role-review",
            name="Review",
            description="Handles review work",
            required_skills=("policy",),
        )
    )
    registry.register_worker(
        WorkerProfile(
            worker_id="worker-b",
            name="Worker B",
            roles=("role-ops",),
            max_concurrent_jobs=2,
            status=WorkerStatus.AVAILABLE,
        )
    )
    registry.register_worker(
        WorkerProfile(
            worker_id="worker-a",
            name="Worker A",
            roles=("role-ops", "role-review"),
            max_concurrent_jobs=3,
            status=WorkerStatus.BUSY,
        )
    )
    registry.register_policy(
        AssignmentPolicy(
            policy_id="policy-review",
            role_id="role-review",
            strategy=AssignmentStrategy.LEAST_LOADED,
        )
    )
    registry.register_policy(
        AssignmentPolicy(
            policy_id="policy-ops",
            role_id="role-ops",
            strategy=AssignmentStrategy.LEAST_LOADED,
        )
    )
    registry.update_capacity("worker-a", current_load=1)
    registry.update_capacity("worker-b", current_load=5)
    return registry


def test_team_registry_store_round_trip_preserves_registry_records(tmp_path: Path) -> None:
    store = TeamRegistryStore(tmp_path / "team")
    source = _build_registry()

    saved = store.save_registry(source)
    restored = WorkerRegistry(clock=lambda: _TS)
    state = store.restore_registry(restored)

    assert "\"load_states\"" in saved
    assert tuple(worker.worker_id for worker in state.workers) == ("worker-a", "worker-b")
    assert tuple(role.role_id for role in state.roles) == ("role-ops", "role-review")
    assert tuple(policy.policy_id for policy in state.policies) == ("policy-ops", "policy-review")
    assert tuple(load.current_load for load in state.load_states) == (1, 5)
    assert tuple(load.worker_id for load in restored.list_load_states()) == ("worker-a", "worker-b")
    assert tuple(load.current_load for load in restored.list_load_states()) == (1, 5)
    assert restored.get_internal_capacity("worker-b") is not None
    assert restored.get_internal_capacity("worker-b").current_load == 5


def test_team_registry_store_serialization_is_stable_for_same_input(tmp_path: Path) -> None:
    store = TeamRegistryStore(tmp_path / "team")
    registry = _build_registry()

    first = store.save_registry(registry)
    second = store.save_registry(registry)
    persisted = (tmp_path / "team" / "team_registry.json").read_text(encoding="utf-8")

    assert first == second
    assert persisted == first
    assert store.exists() is True


def test_team_registry_store_fails_closed_on_malformed_payload(tmp_path: Path) -> None:
    base_path = tmp_path / "team"
    base_path.mkdir(parents=True, exist_ok=True)
    payload_path = base_path / "team_registry.json"
    payload_path.write_text(
        json.dumps({"workers": {}, "roles": [], "policies": [], "load_states": []}),
        encoding="utf-8",
    )
    store = TeamRegistryStore(base_path)

    assert payload_path.exists() is True
    assert "\"load_states\"" in payload_path.read_text(encoding="utf-8")
    with pytest.raises(CorruptedDataError, match="workers must be a JSON array"):
        store.load_registry_state()
    assert store.exists() is True


def test_restore_registry_fails_closed_before_mutation_when_worker_reference_is_missing(
    tmp_path: Path,
) -> None:
    base_path = tmp_path / "team"
    base_path.mkdir(parents=True, exist_ok=True)
    payload_path = base_path / "team_registry.json"
    payload_path.write_text(
        json.dumps(
            {
                "workers": [],
                "roles": [
                    {
                        "role_id": "role-ops",
                        "name": "Operations",
                        "description": "Handles live operations",
                        "required_skills": ["shell"],
                        "approval_required": False,
                        "max_concurrent_per_worker": 5,
                        "metadata": {},
                    }
                ],
                "policies": [
                    {
                        "policy_id": "policy-ops",
                        "role_id": "role-ops",
                        "strategy": "least_loaded",
                        "fallback_team_id": None,
                        "escalation_chain_id": None,
                    }
                ],
                "load_states": [
                    {
                        "worker_id": "worker-missing",
                        "current_load": 2,
                    }
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    store = TeamRegistryStore(base_path)
    target = WorkerRegistry(clock=lambda: _TS)

    assert payload_path.exists() is True
    with pytest.raises(RuntimeCoreInvariantError, match="worker not found: worker-missing"):
        store.restore_registry(target)
    assert target.get_role("role-ops") is None
    assert target.get_policy("policy-ops") is None
    assert target.get_worker("worker-missing") is None
    assert target.list_load_states() == ()
