"""Purpose: persistence for skill execution records.
Governance scope: persistence layer skill record storage only.
Dependencies: persistence errors, serialization helpers, skill contracts.
Invariants: one file per skill record, append-only, fail closed on malformed data.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from mcoi_runtime.contracts.skill import SkillExecutionRecord

from ._serialization import deserialize_record, serialize_record
from .errors import (
    CorruptedDataError,
    PathTraversalError,
    PersistenceError,
    PersistenceWriteError,
)


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
        raise PersistenceWriteError(_bounded_store_error("skill store write failed", exc)) from exc


class SkillStore:
    """Append-only persistence for SkillExecutionRecord artifacts.

    Each record is stored as a single JSON file named {record_id}.json.
    Ordering is by sorted record_id.
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

    def _record_path(self, record_id: str) -> Path:
        return self._safe_path(record_id, suffix=".json")

    def _listed_record_id(self, file_path: Path) -> str:
        record_id = file_path.stem
        try:
            self._record_path(record_id)
        except PathTraversalError as exc:
            raise CorruptedDataError("skill record filename is invalid") from exc
        return record_id

    def save(self, record: SkillExecutionRecord) -> None:
        """Persist a skill execution record."""
        if not isinstance(record, SkillExecutionRecord):
            raise PersistenceError("record must be a SkillExecutionRecord instance")
        path = self._record_path(record.record_id)
        content = serialize_record(record)
        _atomic_write(path, content)

    def load(self, record_id: str) -> SkillExecutionRecord:
        """Load a skill execution record by ID."""
        if not isinstance(record_id, str) or not record_id.strip():
            raise PersistenceError("record_id must be a non-empty string")
        path = self._record_path(record_id)
        if not path.exists():
            raise PersistenceError("skill record not found")
        return _load_skill_file(path, expected_record_id=record_id)

    def list_records(self) -> tuple[str, ...]:
        """List all persisted skill record IDs in sorted order."""
        if not self._base_path.exists():
            return ()
        record_ids: list[str] = []
        for entry in sorted(self._base_path.iterdir()):
            if entry.is_file() and entry.suffix == ".json":
                record_ids.append(self._listed_record_id(entry))
        return tuple(record_ids)

    def load_all(self) -> tuple[SkillExecutionRecord, ...]:
        """Load all skill execution records in sorted order."""
        if not self._base_path.exists():
            return ()
        records: list[SkillExecutionRecord] = []
        for file_path in sorted(self._base_path.iterdir()):
            if file_path.is_file() and file_path.suffix == ".json":
                expected_record_id = self._listed_record_id(file_path)
                records.append(_load_skill_file(file_path, expected_record_id=expected_record_id))
        return tuple(records)


def _load_skill_file(path: Path, *, expected_record_id: str | None = None) -> SkillExecutionRecord:
    """Load and validate a single skill execution record JSON file."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CorruptedDataError(_bounded_store_error("skill store read failed", exc)) from exc

    try:
        record = deserialize_record(content, SkillExecutionRecord)
    except CorruptedDataError:
        raise
    except (TypeError, ValueError) as exc:
        raise CorruptedDataError(_bounded_store_error("invalid skill record", exc)) from exc
    if expected_record_id is not None and record.record_id != expected_record_id:
        raise CorruptedDataError("skill record id mismatch")
    return record
