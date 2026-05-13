"""Purpose: explicit local persistence for governed work-queue entry carriers.
Governance scope: persistence layer work-queue entry storage only.
Dependencies: job queue contracts, deterministic JSON helpers, persistence errors.
Invariants:
  - Queue-entry serialization is deterministic and restore preserves persisted queue order.
  - Load fails closed on malformed content or duplicate entry identifiers.
  - Restore never re-enqueues or regenerates identifiers; it restores exact persisted entries.
  - This store persists live queue-item carriers, not job descriptors, outcomes, or derived metrics.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from mcoi_runtime.contracts.job import WorkQueueEntry
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.jobs import WorkQueue

from ._serialization import deserialize_record, serialize_record
from .errors import CorruptedDataError, PersistenceError, PersistenceWriteError


def _deterministic_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


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
        raise PersistenceWriteError(_bounded_store_error("work queue store write failed", exc)) from exc


def _entry_payload(entry: WorkQueueEntry) -> dict[str, object]:
    payload = json.loads(serialize_record(entry))
    if not isinstance(payload, dict):
        raise PersistenceError("serialized work queue entry must be a JSON object")
    return payload


@dataclass(frozen=True, slots=True)
class WorkQueueState:
    """Explicit snapshot of live queue-entry carriers for deterministic restore."""

    entries: tuple[WorkQueueEntry, ...]

    def __post_init__(self) -> None:
        if any(not isinstance(entry, WorkQueueEntry) for entry in self.entries):
            raise PersistenceError("entries must contain WorkQueueEntry instances only")


class WorkQueueStore:
    """Persist exact work-queue entries as a deterministic JSON witness."""

    def __init__(self, base_path: Path) -> None:
        if not isinstance(base_path, Path):
            raise PersistenceError("base_path must be a Path instance")
        self._base_path = base_path

    def _state_path(self) -> Path:
        return self._base_path / "work_queue.json"

    def save_state(self, queue: WorkQueue) -> str:
        if not isinstance(queue, WorkQueue):
            raise PersistenceError("queue must be a WorkQueue instance")
        payload = {
            "entries": [
                _entry_payload(entry)
                for entry in queue.list_entries()
            ]
        }
        content = _deterministic_json(payload)
        _atomic_write(self._state_path(), content)
        return content

    def load_state(self) -> WorkQueueState:
        path = self._state_path()
        if not path.exists():
            raise CorruptedDataError("work queue file not found")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise CorruptedDataError(_bounded_store_error("malformed work queue file", exc)) from exc
        if not isinstance(payload, dict):
            raise CorruptedDataError("work queue payload must be a JSON object")
        entries_raw = payload.get("entries")
        if not isinstance(entries_raw, list):
            raise CorruptedDataError("work queue payload must contain an entries array")

        entries: list[WorkQueueEntry] = []
        seen_entry_ids: set[str] = set()
        for raw in entries_raw:
            if not isinstance(raw, dict):
                raise CorruptedDataError("work queue entry must be a JSON object")
            entry = deserialize_record(_deterministic_json(raw), WorkQueueEntry)
            if entry.entry_id in seen_entry_ids:
                raise CorruptedDataError("duplicate entry_id in work queue payload")
            seen_entry_ids.add(entry.entry_id)
            entries.append(entry)
        return WorkQueueState(entries=tuple(entries))

    def restore_state(self, queue: WorkQueue) -> WorkQueueState:
        if not isinstance(queue, WorkQueue):
            raise PersistenceError("queue must be a WorkQueue instance")
        state = self.load_state()
        self._validate_restore_preconditions(queue, state)
        for entry in state.entries:
            queue.restore_entry(entry)
        return state

    def exists(self) -> bool:
        return self._state_path().exists()

    @staticmethod
    def _validate_restore_preconditions(
        queue: WorkQueue,
        state: WorkQueueState,
    ) -> None:
        for entry in state.entries:
            if queue.get(entry.entry_id) is not None:
                raise RuntimeCoreInvariantError(
                    f"work queue entry already restored: {entry.entry_id}"
                )
