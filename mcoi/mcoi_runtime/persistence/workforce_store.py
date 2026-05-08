"""Purpose: explicit local persistence for live workforce assignment state.
Governance scope: persistence layer worker, assignment-request, and assignment-decision storage only.
Dependencies: workforce runtime contracts, deterministic JSON helpers, persistence errors.
Invariants:
  - Worker, request, and decision serialization is deterministic and identifier-stable.
  - Restore validates cross-record references before mutating a target engine.
  - Restore never replays assignment side effects; it restores exact persisted records.
  - Derived workforce artifacts remain outside this store and must be recomputed explicitly.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcoi_runtime.contracts.workforce_runtime import (
    AssignmentDecision,
    AssignmentDisposition,
    AssignmentRequest,
    WorkerRecord,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.workforce_runtime import WorkforceRuntimeEngine

from ._serialization import deserialize_record, serialize_record
from .errors import CorruptedDataError, PersistenceError, PersistenceWriteError


def _deterministic_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


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
        raise PersistenceWriteError(f"failed to write {path}: {exc}") from exc


def _record_payload(record: object) -> dict[str, Any]:
    payload = json.loads(serialize_record(record))
    if not isinstance(payload, dict):
        raise PersistenceError("serialized workforce record must be a JSON object")
    return payload


def _deserialize_contract(raw: object, record_type: type) -> object:
    if not isinstance(raw, dict):
        raise CorruptedDataError(f"{record_type.__name__} payload must be a JSON object")
    return deserialize_record(_deterministic_json(raw), record_type)


@dataclass(frozen=True, slots=True)
class WorkforceRuntimeState:
    """Explicit snapshot of workforce assignment carriers for deterministic restore."""

    workers: tuple[WorkerRecord, ...]
    requests: tuple[AssignmentRequest, ...]
    decisions: tuple[AssignmentDecision, ...]

    def __post_init__(self) -> None:
        if any(not isinstance(worker, WorkerRecord) for worker in self.workers):
            raise PersistenceError("workers must contain WorkerRecord instances only")
        if any(not isinstance(request, AssignmentRequest) for request in self.requests):
            raise PersistenceError("requests must contain AssignmentRequest instances only")
        if any(not isinstance(decision, AssignmentDecision) for decision in self.decisions):
            raise PersistenceError("decisions must contain AssignmentDecision instances only")


class WorkforceStore:
    """Persist explicit workforce queue carriers as a deterministic JSON witness."""

    def __init__(self, base_path: Path) -> None:
        if not isinstance(base_path, Path):
            raise PersistenceError("base_path must be a Path instance")
        self._base_path = base_path

    def _state_path(self) -> Path:
        return self._base_path / "workforce_runtime.json"

    def save_state(self, engine: WorkforceRuntimeEngine) -> str:
        if not isinstance(engine, WorkforceRuntimeEngine):
            raise PersistenceError("engine must be a WorkforceRuntimeEngine instance")

        payload = {
            "workers": [_record_payload(worker) for worker in engine.list_workers()],
            "requests": [_record_payload(request) for request in engine.list_requests()],
            "decisions": [_record_payload(decision) for decision in engine.list_decisions()],
        }
        content = _deterministic_json(payload)
        _atomic_write(self._state_path(), content)
        return content

    def load_state(self) -> WorkforceRuntimeState:
        path = self._state_path()
        if not path.exists():
            raise CorruptedDataError(f"workforce runtime file not found: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise CorruptedDataError(f"malformed workforce runtime file: {exc}") from exc
        if not isinstance(payload, dict):
            raise CorruptedDataError("workforce runtime payload must be a JSON object")

        workers_raw = payload.get("workers")
        requests_raw = payload.get("requests")
        decisions_raw = payload.get("decisions")
        if not isinstance(workers_raw, list):
            raise CorruptedDataError("workforce runtime workers must be a JSON array")
        if not isinstance(requests_raw, list):
            raise CorruptedDataError("workforce runtime requests must be a JSON array")
        if not isinstance(decisions_raw, list):
            raise CorruptedDataError("workforce runtime decisions must be a JSON array")

        return WorkforceRuntimeState(
            workers=tuple(
                _deserialize_contract(raw, WorkerRecord) for raw in workers_raw
            ),
            requests=tuple(
                _deserialize_contract(raw, AssignmentRequest) for raw in requests_raw
            ),
            decisions=tuple(
                _deserialize_contract(raw, AssignmentDecision) for raw in decisions_raw
            ),
        )

    def restore_state(self, engine: WorkforceRuntimeEngine) -> WorkforceRuntimeState:
        if not isinstance(engine, WorkforceRuntimeEngine):
            raise PersistenceError("engine must be a WorkforceRuntimeEngine instance")

        state = self.load_state()
        self._validate_restore_preconditions(engine, state)
        for worker in state.workers:
            engine.restore_worker(worker)
        for request in state.requests:
            engine.restore_request(request)
        for decision in state.decisions:
            engine.restore_decision(decision)
        return state

    def exists(self) -> bool:
        return self._state_path().exists()

    @staticmethod
    def _validate_restore_preconditions(
        engine: WorkforceRuntimeEngine,
        state: WorkforceRuntimeState,
    ) -> None:
        worker_ids = tuple(worker.worker_id for worker in state.workers)
        request_ids = tuple(request.request_id for request in state.requests)
        decision_ids = tuple(decision.decision_id for decision in state.decisions)

        WorkforceStore._require_unique(worker_ids, label="worker")
        WorkforceStore._require_unique(request_ids, label="request")
        WorkforceStore._require_unique(decision_ids, label="decision")

        for worker_id in worker_ids:
            try:
                engine.get_worker(worker_id)
            except RuntimeCoreInvariantError:
                pass
            else:
                raise RuntimeCoreInvariantError(f"worker already registered: {worker_id}")

        existing_request_ids = {
            request.request_id for request in engine.list_requests()
        }
        existing_decision_ids = {
            decision.decision_id for decision in engine.list_decisions()
        }
        for request_id in request_ids:
            if request_id in existing_request_ids:
                raise RuntimeCoreInvariantError(
                    f"assignment request already exists: {request_id}"
                )
        for decision_id in decision_ids:
            if decision_id in existing_decision_ids:
                raise RuntimeCoreInvariantError(
                    f"assignment decision already exists: {decision_id}"
                )

        available_worker_ids = set(worker_ids)
        available_request_ids = set(request_ids)
        assigned_counts: dict[str, int] = {}

        for decision in state.decisions:
            if decision.request_id not in available_request_ids:
                raise RuntimeCoreInvariantError(
                    f"unknown assignment request: {decision.request_id}"
                )
            if decision.disposition is AssignmentDisposition.ASSIGNED:
                if decision.worker_id not in available_worker_ids:
                    raise RuntimeCoreInvariantError(f"unknown worker: {decision.worker_id}")
                assigned_counts[decision.worker_id] = (
                    assigned_counts.get(decision.worker_id, 0) + 1
                )

        for worker in state.workers:
            assigned = assigned_counts.get(worker.worker_id, 0)
            if assigned != worker.current_assignments:
                raise RuntimeCoreInvariantError(
                    "worker current_assignments does not match persisted assigned decisions: "
                    f"{worker.worker_id}"
                )

    @staticmethod
    def _require_unique(ids: tuple[str, ...], *, label: str) -> None:
        if len(ids) != len(set(ids)):
            raise CorruptedDataError(
                f"duplicate {label} identifier in workforce runtime payload"
            )
