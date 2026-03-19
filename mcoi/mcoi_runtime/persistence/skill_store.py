"""Purpose: persistence for skill execution records.
Governance scope: persistence layer skill record storage only.
Dependencies: persistence errors, serialization helpers, skill contracts.
Invariants: one file per skill record, append-only, fail closed on malformed data.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from mcoi_runtime.contracts.skill import SkillExecutionRecord

from ._serialization import deserialize_record, serialize_record
from .errors import (
    CorruptedDataError,
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


class SkillStore:
    """Append-only persistence for SkillExecutionRecord artifacts.

    Each record is stored as a single JSON file named {record_id}.json.
    Ordering is by sorted record_id.
    """

    def __init__(self, base_path: Path) -> None:
        if not isinstance(base_path, Path):
            raise PersistenceError("base_path must be a Path instance")
        self._base_path = base_path

    def _record_path(self, record_id: str) -> Path:
        return self._base_path / f"{record_id}.json"

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
            raise PersistenceError(f"skill record not found: {record_id}")
        return _load_skill_file(path)

    def list_records(self) -> tuple[str, ...]:
        """List all persisted skill record IDs in sorted order."""
        if not self._base_path.exists():
            return ()
        return tuple(
            entry.stem
            for entry in sorted(self._base_path.iterdir())
            if entry.is_file() and entry.suffix == ".json"
        )

    def load_all(self) -> tuple[SkillExecutionRecord, ...]:
        """Load all skill execution records in sorted order."""
        if not self._base_path.exists():
            return ()
        records: list[SkillExecutionRecord] = []
        for file_path in sorted(self._base_path.iterdir()):
            if file_path.is_file() and file_path.suffix == ".json":
                records.append(_load_skill_file(file_path))
        return tuple(records)


def _load_skill_file(path: Path) -> SkillExecutionRecord:
    """Load and validate a single skill execution record JSON file."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CorruptedDataError(f"cannot read skill file {path.name}: {exc}") from exc

    try:
        return deserialize_record(content, SkillExecutionRecord)
    except CorruptedDataError:
        raise
    except (TypeError, ValueError) as exc:
        raise CorruptedDataError(f"invalid skill record in {path.name}: {exc}") from exc
