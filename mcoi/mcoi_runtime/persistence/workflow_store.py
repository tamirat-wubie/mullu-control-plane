"""Purpose: persistence for workflow execution records.
Governance scope: persistence layer workflow record storage only.
Dependencies: persistence errors, serialization helpers, workflow contracts.
Invariants: one file per execution record, atomic writes, fail closed on malformed data.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from mcoi_runtime.contracts.workflow import WorkflowExecutionRecord

from ._serialization import deserialize_record, serialize_record
from .errors import (
    CorruptedDataError,
    PathTraversalError,
    PersistenceError,
    PersistenceWriteError,
)


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


class WorkflowStore:
    """Append-only persistence for WorkflowExecutionRecord artifacts.

    Each record is stored as a single JSON file named {execution_id}.json.
    """

    def __init__(self, base_path: Path) -> None:
        if not isinstance(base_path, Path):
            raise PersistenceError("base_path must be a Path instance")
        self._base_path = base_path

    def _safe_path(self, id_value: str, suffix: str = ".json") -> Path:
        """Construct a path from *id_value* and validate it stays inside _base_path."""
        if "\0" in id_value:
            raise PathTraversalError(f"ID contains null byte: {id_value!r}")
        if "/" in id_value or "\\" in id_value or ".." in id_value:
            raise PathTraversalError(
                f"ID contains forbidden characters: {id_value!r}"
            )
        candidate = (self._base_path / f"{id_value}{suffix}").resolve()
        base_resolved = self._base_path.resolve()
        if not candidate.is_relative_to(base_resolved):
            raise PathTraversalError(
                f"path escapes base directory: {id_value!r}"
            )
        return candidate

    def save_execution_record(self, record: WorkflowExecutionRecord) -> None:
        """Persist a workflow execution record."""
        if not isinstance(record, WorkflowExecutionRecord):
            raise PersistenceError("record must be a WorkflowExecutionRecord instance")
        path = self._safe_path(record.execution_id)
        content = serialize_record(record)
        _atomic_write(path, content)

    def load_execution_record(self, execution_id: str) -> WorkflowExecutionRecord:
        """Load a workflow execution record by execution ID."""
        if not isinstance(execution_id, str) or not execution_id.strip():
            raise PersistenceError("execution_id must be a non-empty string")
        path = self._safe_path(execution_id)
        if not path.exists():
            raise PersistenceError(f"workflow execution record not found: {execution_id}")
        return _load_workflow_file(path)

    def list_executions(self) -> tuple[str, ...]:
        """List all persisted workflow execution IDs in sorted order."""
        if not self._base_path.exists():
            return ()
        return tuple(
            entry.stem
            for entry in sorted(self._base_path.iterdir())
            if entry.is_file() and entry.suffix == ".json"
        )


def _load_workflow_file(path: Path) -> WorkflowExecutionRecord:
    """Load and validate a single workflow execution record JSON file."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CorruptedDataError(f"cannot read workflow file {path.name}: {exc}") from exc

    try:
        return deserialize_record(content, WorkflowExecutionRecord)
    except CorruptedDataError:
        raise
    except (TypeError, ValueError) as exc:
        raise CorruptedDataError(f"invalid workflow record in {path.name}: {exc}") from exc
