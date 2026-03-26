"""Purpose: append-only trace entry persistence.
Governance scope: persistence layer trace storage only.
Dependencies: persistence errors, serialization helpers, TraceEntry contract, hash chain.
Invariants: one file per trace entry, append-only, fail closed on malformed data.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from mcoi_runtime.contracts.trace import TraceEntry

from ._serialization import serialize_record
from .errors import (
    CorruptedDataError,
    PathTraversalError,
    PersistenceError,
    PersistenceWriteError,
    TraceNotFoundError,
)

if TYPE_CHECKING:
    from .hash_chain import HashChainStore


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

    When a hash_chain is provided, each append computes a SHA-256 content hash
    of the serialized entry and records it in the chain for tamper detection.
    """

    def __init__(
        self, base_path: Path, *, hash_chain: HashChainStore | None = None
    ) -> None:
        if not isinstance(base_path, Path):
            raise PersistenceError("base_path must be a Path instance")
        self._base_path = base_path
        self._hash_chain = hash_chain

    def _safe_path(self, id_value: str, suffix: str = "") -> Path:
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

    def _trace_path(self, trace_id: str) -> Path:
        return self._safe_path(trace_id, suffix=".json")

    def append(self, entry: TraceEntry) -> None:
        if not isinstance(entry, TraceEntry):
            raise PersistenceError("entry must be a TraceEntry instance")

        path = self._trace_path(entry.trace_id)
        content = serialize_record(entry)
        _atomic_write(path, content)

        if self._hash_chain is not None:
            from .hash_chain import compute_content_hash

            self._hash_chain.append(compute_content_hash(content))

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
