"""Purpose: coordination state persistence for delegation, handoff, merge, and conflict records.
Governance scope: persistence layer coordination state storage only.
Dependencies: persistence errors, serialization helpers, ContractRecord base.
Invariants:
  - One file per coordination state, keyed by state_id.
  - Atomic writes prevent partial state on disk.
  - Path traversal is prevented via _safe_path validation.
  - Fail closed on malformed or missing data.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Type, TypeVar

from mcoi_runtime.contracts._base import ContractRecord

from ._serialization import deserialize_record, serialize_record
from .errors import (
    CorruptedDataError,
    PathTraversalError,
    PersistenceError,
    PersistenceWriteError,
)

RecordT = TypeVar("RecordT")


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
        raise PersistenceWriteError(
            _bounded_store_error("coordination state write failed", exc)
        ) from exc


class CoordinationStore:
    """Persistence for coordination state records (delegation, handoff, merge, conflict).

    Each coordination state is stored as a single JSON file named {state_id}.json
    under base_path. Uses atomic writes and path traversal prevention.
    """

    def __init__(self, base_path: Path) -> None:
        if not isinstance(base_path, Path):
            raise PersistenceError("base_path must be a Path instance")
        self._base_path = base_path

    def _safe_path(self, id_value: str, suffix: str = "") -> Path:
        """Construct a path from *id_value* and validate it stays inside _base_path."""
        if "\0" in id_value:
            raise PathTraversalError("identifier contains null byte")
        if "/" in id_value or "\\" in id_value or ".." in id_value:
            raise PathTraversalError("identifier contains forbidden characters")
        candidate = (self._base_path / f"{id_value}{suffix}").resolve()
        base_resolved = self._base_path.resolve()
        if not candidate.is_relative_to(base_resolved):
            raise PathTraversalError("path escapes base directory")
        return candidate

    def _state_path(self, state_id: str) -> Path:
        return self._safe_path(state_id, suffix=".json")

    def save_state(self, state_id: str, record: ContractRecord) -> None:
        """Persist a coordination record atomically under the given state_id."""
        if not isinstance(state_id, str) or not state_id.strip():
            raise PersistenceError("state_id must be a non-empty string")
        if not isinstance(record, ContractRecord):
            raise PersistenceError("record must be a ContractRecord instance")

        path = self._state_path(state_id)
        content = serialize_record(record)
        _atomic_write(path, content)

    def load_state(self, state_id: str, record_type: Type[RecordT]) -> RecordT:
        """Load and deserialize a coordination record by state_id."""
        if not isinstance(state_id, str) or not state_id.strip():
            raise PersistenceError("state_id must be a non-empty string")

        path = self._state_path(state_id)
        if not path.exists():
            raise PersistenceError("coordination state not found")

        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise CorruptedDataError(
                _bounded_store_error("coordination state read failed", exc)
            ) from exc

        return deserialize_record(raw, record_type)

    def list_states(self) -> tuple[str, ...]:
        """Return sorted tuple of all persisted state IDs."""
        if not self._base_path.exists():
            return ()

        state_ids: list[str] = []
        for entry in sorted(self._base_path.iterdir()):
            if entry.is_file() and entry.suffix == ".json":
                state_ids.append(entry.stem)

        return tuple(state_ids)

    def delete_state(self, state_id: str) -> None:
        """Remove a persisted coordination state file."""
        if not isinstance(state_id, str) or not state_id.strip():
            raise PersistenceError("state_id must be a non-empty string")

        path = self._state_path(state_id)
        if not path.exists():
            raise PersistenceError("coordination state not found")

        try:
            path.unlink()
        except OSError as exc:
            raise PersistenceWriteError(
                _bounded_store_error("coordination state delete failed", exc)
            ) from exc
