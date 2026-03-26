"""Purpose: explicit local persistence for working and episodic memory tiers.
Governance scope: persistence layer memory storage only.
Dependencies: persistence errors, core memory contracts, deterministic JSON helpers.
Invariants:
  - Working memory serialization is deterministic and sorted by entry_id.
  - Episodic memory serialization preserves append order.
  - Load fails closed on malformed content.
  - Restore is explicit; this module never auto-loads on import.
"""

from __future__ import annotations

import json
import os
import tempfile
from hashlib import sha256
from pathlib import Path
from typing import Any

from mcoi_runtime.contracts._base import thaw_value
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory import (
    EpisodicMemory,
    MemoryEntry,
    MemoryTier,
    WorkingMemory,
)

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


def _serialize_entry(entry: MemoryEntry) -> dict[str, Any]:
    return {
        "entry_id": entry.entry_id,
        "tier": entry.tier.value,
        "category": entry.category,
        "content": thaw_value(entry.content),
        "source_ids": list(entry.source_ids),
    }


def _load_payload(path: Path, *, label: str) -> dict[str, Any]:
    if not path.exists():
        raise CorruptedDataError(f"{label} file not found: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise CorruptedDataError(f"malformed {label} file: {exc}") from exc
    if not isinstance(raw, dict):
        raise CorruptedDataError(f"{label} file must be a JSON object")
    return raw


def _deserialize_entry(raw: dict[str, Any], *, expected_tier: MemoryTier) -> MemoryEntry:
    if not isinstance(raw, dict):
        raise CorruptedDataError("memory entry must be a JSON object")
    try:
        tier = MemoryTier(raw["tier"])
        entry = MemoryEntry(
            entry_id=raw["entry_id"],
            tier=tier,
            category=raw["category"],
            content=raw["content"],
            source_ids=tuple(raw.get("source_ids", ())),
        )
    except (KeyError, TypeError, ValueError, RuntimeCoreInvariantError) as exc:
        raise CorruptedDataError(f"invalid memory entry: {exc}") from exc

    if entry.tier is not expected_tier:
        raise CorruptedDataError(
            f"memory entry tier mismatch: expected {expected_tier.value}, got {entry.tier.value}"
        )
    return entry


class MemoryStore:
    """Persist working and episodic memory tiers as deterministic JSON files."""

    def __init__(self, base_path: Path) -> None:
        if not isinstance(base_path, Path):
            raise PersistenceError("base_path must be a Path instance")
        self._base_path = base_path

    def _working_path(self) -> Path:
        return self._base_path / "working_memory.json"

    def _episodic_path(self) -> Path:
        return self._base_path / "episodic_memory.json"

    def save_working(self, memory: WorkingMemory) -> str:
        if not isinstance(memory, WorkingMemory):
            raise PersistenceError("memory must be a WorkingMemory instance")
        payload = {
            "max_entries": memory.max_entries,
            "entries": [_serialize_entry(entry) for entry in memory.list_entries()],
        }
        content = _deterministic_json(payload)
        _atomic_write(self._working_path(), content)
        return sha256(content.encode("ascii", "ignore")).hexdigest()

    def save_episodic(self, memory: EpisodicMemory) -> str:
        if not isinstance(memory, EpisodicMemory):
            raise PersistenceError("memory must be an EpisodicMemory instance")
        payload = {
            "entries": [_serialize_entry(entry) for entry in memory.list_entries()],
        }
        content = _deterministic_json(payload)
        _atomic_write(self._episodic_path(), content)
        return sha256(content.encode("ascii", "ignore")).hexdigest()

    def save_all(
        self,
        *,
        working: WorkingMemory,
        episodic: EpisodicMemory,
    ) -> tuple[str, str]:
        return (self.save_working(working), self.save_episodic(episodic))

    def load_working(self) -> WorkingMemory:
        payload = _load_payload(self._working_path(), label="working memory")
        if "max_entries" not in payload or "entries" not in payload:
            raise CorruptedDataError("working memory payload must contain max_entries and entries")
        max_entries = payload["max_entries"]
        entries_raw = payload["entries"]
        if not isinstance(max_entries, int) or max_entries <= 0:
            raise CorruptedDataError("working memory max_entries must be a positive integer")
        if not isinstance(entries_raw, list):
            raise CorruptedDataError("working memory entries must be a JSON array")
        entries = tuple(
            _deserialize_entry(raw, expected_tier=MemoryTier.WORKING) for raw in entries_raw
        )
        return WorkingMemory.from_entries(entries, max_entries=max_entries)

    def load_episodic(self) -> EpisodicMemory:
        payload = _load_payload(self._episodic_path(), label="episodic memory")
        entries_raw = payload.get("entries")
        if not isinstance(entries_raw, list):
            raise CorruptedDataError("episodic memory entries must be a JSON array")
        entries = tuple(
            _deserialize_entry(raw, expected_tier=MemoryTier.EPISODIC) for raw in entries_raw
        )
        return EpisodicMemory.from_entries(entries)

    def load_all(
        self,
        *,
        allow_missing: bool = False,
        working_max_entries: int = 1000,
    ) -> tuple[WorkingMemory, EpisodicMemory]:
        if allow_missing and not self.working_exists():
            working = WorkingMemory(max_entries=working_max_entries)
        else:
            working = self.load_working()

        if allow_missing and not self.episodic_exists():
            episodic = EpisodicMemory()
        else:
            episodic = self.load_episodic()

        return working, episodic

    def working_exists(self) -> bool:
        return self._working_path().exists()

    def episodic_exists(self) -> bool:
        return self._episodic_path().exists()
