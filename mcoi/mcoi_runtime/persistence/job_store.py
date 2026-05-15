"""Purpose: explicit local persistence for governed job descriptors and states.
Governance scope: persistence layer job runtime descriptor/state storage only.
Dependencies: job contracts, job engine, deterministic JSON helpers, persistence errors.
Invariants:
  - Job descriptor and state serialization is deterministic and identifier-stable.
  - Load fails closed on malformed content, duplicate identifiers, or mismatched descriptor/state pairs.
  - Restore never replays lifecycle transitions; it restores exact persisted descriptors and states.
  - Derived queue, deadline, and follow-up artifacts remain outside this store.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from mcoi_runtime.contracts.job import JobDescriptor, JobState
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.jobs import JobEngine

from ._serialization import deserialize_record, loads_strict_json, serialize_record
from .errors import CorruptedDataError, PersistenceError, PersistenceWriteError


def _deterministic_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


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
        raise PersistenceWriteError(_bounded_store_error("job store write failed", exc)) from exc


def _record_payload(record: object) -> dict[str, object]:
    payload = loads_strict_json(serialize_record(record))
    if not isinstance(payload, dict):
        raise PersistenceError("serialized job record must be a JSON object")
    return payload


@dataclass(frozen=True, slots=True)
class JobRuntimeState:
    """Explicit snapshot of live job descriptors and states for deterministic restore."""

    descriptors: tuple[JobDescriptor, ...]
    states: tuple[JobState, ...]

    def __post_init__(self) -> None:
        if any(not isinstance(descriptor, JobDescriptor) for descriptor in self.descriptors):
            raise PersistenceError("descriptors must contain JobDescriptor instances only")
        if any(not isinstance(state, JobState) for state in self.states):
            raise PersistenceError("states must contain JobState instances only")


class JobStore:
    """Persist exact job descriptors and states as a deterministic JSON witness."""

    def __init__(self, base_path: Path) -> None:
        if not isinstance(base_path, Path):
            raise PersistenceError("base_path must be a Path instance")
        self._base_path = base_path

    def _state_path(self) -> Path:
        return self._base_path / "job_runtime.json"

    def save_state(self, engine: JobEngine) -> str:
        if not isinstance(engine, JobEngine):
            raise PersistenceError("engine must be a JobEngine instance")
        payload = {
            "descriptors": [
                _record_payload(descriptor)
                for descriptor in engine.list_job_descriptors()
            ],
            "states": [
                _record_payload(state)
                for state in engine.list_job_states()
            ],
        }
        content = _deterministic_json(payload)
        _atomic_write(self._state_path(), content)
        return content

    def load_state(self) -> JobRuntimeState:
        path = self._state_path()
        if not path.exists():
            raise CorruptedDataError("job runtime file not found")
        try:
            payload = loads_strict_json(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            raise CorruptedDataError(_bounded_store_error("malformed job runtime file", exc)) from exc
        if not isinstance(payload, dict):
            raise CorruptedDataError("job runtime payload must be a JSON object")

        descriptors_raw = payload.get("descriptors")
        states_raw = payload.get("states")
        if not isinstance(descriptors_raw, list):
            raise CorruptedDataError("job runtime descriptors must be a JSON array")
        if not isinstance(states_raw, list):
            raise CorruptedDataError("job runtime states must be a JSON array")

        descriptors = tuple(
            self._deserialize_descriptor(raw) for raw in descriptors_raw
        )
        states = tuple(
            self._deserialize_state(raw) for raw in states_raw
        )
        self._validate_pairing(descriptors, states)
        return JobRuntimeState(descriptors=descriptors, states=states)

    def restore_state(self, engine: JobEngine) -> JobRuntimeState:
        if not isinstance(engine, JobEngine):
            raise PersistenceError("engine must be a JobEngine instance")
        state = self.load_state()
        self._validate_restore_preconditions(engine, state)
        state_by_job_id = {job_state.job_id: job_state for job_state in state.states}
        for descriptor in state.descriptors:
            engine.restore_job(descriptor, state_by_job_id[descriptor.job_id])
        return state

    def exists(self) -> bool:
        return self._state_path().exists()

    @staticmethod
    def _deserialize_descriptor(raw: object) -> JobDescriptor:
        if not isinstance(raw, dict):
            raise CorruptedDataError("job descriptor entry must be a JSON object")
        return deserialize_record(_deterministic_json(raw), JobDescriptor)

    @staticmethod
    def _deserialize_state(raw: object) -> JobState:
        if not isinstance(raw, dict):
            raise CorruptedDataError("job state entry must be a JSON object")
        return deserialize_record(_deterministic_json(raw), JobState)

    @staticmethod
    def _validate_pairing(
        descriptors: tuple[JobDescriptor, ...],
        states: tuple[JobState, ...],
    ) -> None:
        descriptor_ids = tuple(descriptor.job_id for descriptor in descriptors)
        state_ids = tuple(state.job_id for state in states)
        JobStore._require_unique(descriptor_ids, label="job descriptor")
        JobStore._require_unique(state_ids, label="job state")
        if set(descriptor_ids) != set(state_ids):
            raise CorruptedDataError(
                "job runtime descriptors and states must cover the same job_ids"
            )

    @staticmethod
    def _validate_restore_preconditions(
        engine: JobEngine,
        state: JobRuntimeState,
    ) -> None:
        for descriptor in state.descriptors:
            if engine.get_job_descriptor(descriptor.job_id) is not None:
                raise RuntimeCoreInvariantError(
                    f"job already restored: {descriptor.job_id}"
                )
        for job_state in state.states:
            if engine.get_job_state(job_state.job_id) is not None:
                raise RuntimeCoreInvariantError(
                    f"job state already restored: {job_state.job_id}"
                )

    @staticmethod
    def _require_unique(ids: tuple[str, ...], *, label: str) -> None:
        if len(ids) != len(set(ids)):
            raise CorruptedDataError(
                f"duplicate {label} identifier in job runtime payload"
            )
