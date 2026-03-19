"""Purpose: append-only trace entry persistence.
Governance scope: persistence layer trace storage only.
Dependencies: persistence errors, serialization helpers, TraceEntry contract.
Invariants: one file per trace entry, append-only, fail closed on malformed data.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from mcoi_runtime.contracts.trace import TraceEntry

from ._serialization import serialize_record
from .errors import (
    CorruptedDataError,
    PersistenceError,
    PersistenceWriteError,
    TraceNotFoundError,
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


def _load_trace_file(path: Path) -> TraceEntry:
    """Load and validate a single trace entry JSON file."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise CorruptedDataError(f"malformed trace file {path.name}: {exc}") from exc

    if not isinstance(raw, dict):
        raise CorruptedDataError(f"trace file {path.name} is not a JSON object")

    try:
        return TraceEntry(**raw)
    except (TypeError, ValueError) as exc:
        raise CorruptedDataError(f"invalid trace entry in {path.name}: {exc}") from exc


class TraceStore:
    """Append-only persistence for TraceEntry records.

    Each trace entry is stored as a single JSON file named {trace_id}.json
    under base_path. Ordering is by sorted trace_id.
    """

    def __init__(self, base_path: Path) -> None:
        if not isinstance(base_path, Path):
            raise PersistenceError("base_path must be a Path instance")
        self._base_path = base_path

    def _trace_path(self, trace_id: str) -> Path:
        return self._base_path / f"{trace_id}.json"

    def append(self, entry: TraceEntry) -> None:
        if not isinstance(entry, TraceEntry):
            raise PersistenceError("entry must be a TraceEntry instance")

        path = self._trace_path(entry.trace_id)
        content = serialize_record(entry)
        _atomic_write(path, content)

    def list_traces(self) -> tuple[str, ...]:
        if not self._base_path.exists():
            return ()

        trace_ids: list[str] = []
        for entry in sorted(self._base_path.iterdir()):
            if entry.is_file() and entry.suffix == ".json":
                trace_ids.append(entry.stem)

        return tuple(trace_ids)

    def load_trace(self, trace_id: str) -> TraceEntry:
        if not isinstance(trace_id, str) or not trace_id.strip():
            raise PersistenceError("trace_id must be a non-empty string")

        path = self._trace_path(trace_id)
        if not path.exists():
            raise TraceNotFoundError(f"trace entry not found: {trace_id}")

        return _load_trace_file(path)

    def load_all(self) -> tuple[TraceEntry, ...]:
        if not self._base_path.exists():
            return ()

        entries: list[TraceEntry] = []
        for file_path in sorted(self._base_path.iterdir()):
            if file_path.is_file() and file_path.suffix == ".json":
                entries.append(_load_trace_file(file_path))

        return tuple(entries)
