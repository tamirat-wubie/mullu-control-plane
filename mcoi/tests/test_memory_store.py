"""Purpose: verify deterministic persistence for working and episodic memory tiers.
Governance scope: persistence memory-store tests only.
Dependencies: core memory contracts and persistence memory store.
Invariants:
  - Working memory round-trips with bounded capacity preserved.
  - Episodic memory round-trips with append order preserved.
  - Malformed persisted content fails closed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.core.memory import EpisodicMemory, MemoryEntry, MemoryTier, WorkingMemory
from mcoi_runtime.persistence.errors import CorruptedDataError
from mcoi_runtime.persistence.memory_store import MemoryStore


def _working_entry(entry_id: str, *, category: str = "observation") -> MemoryEntry:
    return MemoryEntry(
        entry_id=entry_id,
        tier=MemoryTier.WORKING,
        category=category,
        content={"entry_id": entry_id, "category": category},
        source_ids=(f"src-{entry_id}",),
    )


def _episodic_entry(entry_id: str) -> MemoryEntry:
    return MemoryEntry(
        entry_id=entry_id,
        tier=MemoryTier.EPISODIC,
        category="trace",
        content={"entry_id": entry_id},
        source_ids=(f"trace-{entry_id}",),
    )


def test_memory_store_round_trip_preserves_capacity_and_order(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory")
    working = WorkingMemory(max_entries=3)
    episodic = EpisodicMemory()
    working.store(_working_entry("w-2"))
    working.store(_working_entry("w-1"))
    episodic.admit(_episodic_entry("e-2"))
    episodic.admit(_episodic_entry("e-1"))

    first_hashes = store.save_all(working=working, episodic=episodic)
    restored_working, restored_episodic = store.load_all()
    second_hashes = store.save_all(working=restored_working, episodic=restored_episodic)

    assert restored_working.max_entries == 3
    assert tuple(entry.entry_id for entry in restored_working.list_entries()) == ("w-1", "w-2")
    assert tuple(entry.entry_id for entry in restored_episodic.list_entries()) == ("e-2", "e-1")
    assert first_hashes == second_hashes


def test_memory_store_allow_missing_restores_empty_tiers(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory")

    working, episodic = store.load_all(allow_missing=True, working_max_entries=7)

    assert working.size == 0
    assert working.max_entries == 7
    assert episodic.size == 0
    assert store.working_exists() is False
    assert store.episodic_exists() is False


def test_memory_store_rejects_malformed_working_payload(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory")
    path = tmp_path / "memory" / "working_memory.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "max_entries": 2,
                "entries": [
                    {
                        "entry_id": "w-1",
                        "tier": "episodic",
                        "category": "observation",
                        "content": {"entry_id": "w-1"},
                        "source_ids": ["src-w-1"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(CorruptedDataError, match=r"^memory entry tier mismatch$") as excinfo:
        store.load_working()
    assert "episodic" not in str(excinfo.value)
    assert "working" not in str(excinfo.value)


def test_memory_store_rejects_non_object_payload(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory")
    path = tmp_path / "memory" / "episodic_memory.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(
        CorruptedDataError,
        match=r"^memory store payload must be a JSON object$",
    ):
        store.load_episodic()


def test_memory_store_bounds_file_parse_errors(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory")
    path = tmp_path / "memory" / "episodic_memory.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json", encoding="utf-8")

    with pytest.raises(CorruptedDataError, match=r"^malformed memory store file \(JSONDecodeError\)$"):
        store.load_episodic()


def test_memory_store_bounds_missing_file_error(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory")

    with pytest.raises(CorruptedDataError, match=r"^memory store file not found$") as excinfo:
        store.load_working()
    assert "working" not in str(excinfo.value)
