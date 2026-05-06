"""Purpose: durable persistence for verified runbook entries.
Governance scope: procedural memory storage for replay-admitted runbooks.
Dependencies: runbook core contracts and deterministic persistence serialization.
Invariants:
  - Runbook ids map to one JSON file inside the configured base path.
  - Saves are append-only unless the existing entry is byte-equivalent.
  - Path traversal is rejected before filesystem access.
  - Malformed persisted entries fail closed.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from mcoi_runtime.core.runbook import RunbookEntry

from ._serialization import deserialize_record, serialize_record
from .errors import CorruptedDataError, PathTraversalError, PersistenceError, PersistenceWriteError


def _bounded_store_error(summary: str, exc: BaseException) -> str:
    return f"{summary} ({type(exc).__name__})"


def _atomic_write_exclusive(path: Path, content: str) -> None:
    """Write content only when the target path does not already exist."""
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    tmp_path: str | None = None
    try:
        fd, tmp_path = tempfile.mkstemp(dir=str(parent), suffix=".tmp")
        try:
            os.write(fd, content.encode("utf-8"))
            os.close(fd)
            fd = -1
            os.replace(tmp_path, str(path))
            tmp_path = None
        except BaseException:
            if fd >= 0:
                os.close(fd)
            raise
    except OSError as exc:
        raise PersistenceWriteError(_bounded_store_error("runbook store write failed", exc)) from exc
    finally:
        if tmp_path is not None and os.path.exists(tmp_path):
            os.unlink(tmp_path)


class RunbookStore:
    """Append-only local store for verified runbook entries."""

    def __init__(self, base_path: Path) -> None:
        if not isinstance(base_path, Path):
            raise PersistenceError("base_path must be a Path instance")
        self._base_path = base_path

    def _safe_path(self, runbook_id: str) -> Path:
        if not isinstance(runbook_id, str) or not runbook_id.strip():
            raise PersistenceError("runbook_id must be a non-empty string")
        if "\0" in runbook_id:
            raise PathTraversalError("identifier contains null byte")
        if "/" in runbook_id or "\\" in runbook_id or ".." in runbook_id:
            raise PathTraversalError("identifier contains forbidden characters")
        candidate = (self._base_path / f"{runbook_id}.json").resolve()
        base_resolved = self._base_path.resolve()
        if not candidate.is_relative_to(base_resolved):
            raise PathTraversalError("path escapes base directory")
        return candidate

    def save(self, entry: RunbookEntry) -> bool:
        """Persist a runbook entry.

        Returns True when a new file was written and False when an identical
        entry already existed.
        """
        if not isinstance(entry, RunbookEntry):
            raise PersistenceError("entry must be a RunbookEntry instance")
        path = self._safe_path(entry.runbook_id)
        content = serialize_record(entry)
        if path.exists():
            existing = self.load(entry.runbook_id)
            if existing != entry:
                raise PersistenceWriteError("runbook id collision")
            return False
        _atomic_write_exclusive(path, content)
        return True

    def load(self, runbook_id: str) -> RunbookEntry:
        path = self._safe_path(runbook_id)
        if not path.exists():
            raise PersistenceError("runbook entry not found")
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise CorruptedDataError(_bounded_store_error("runbook read failed", exc)) from exc
        try:
            return deserialize_record(raw, RunbookEntry)
        except (CorruptedDataError, TypeError, ValueError) as exc:
            raise CorruptedDataError(_bounded_store_error("invalid runbook entry", exc)) from exc

    def list_runbook_ids(self) -> tuple[str, ...]:
        if not self._base_path.exists():
            return ()
        return tuple(
            entry.stem
            for entry in sorted(self._base_path.iterdir())
            if entry.is_file() and entry.suffix == ".json"
        )

    def load_all(self) -> tuple[RunbookEntry, ...]:
        return tuple(self.load(runbook_id) for runbook_id in self.list_runbook_ids())
