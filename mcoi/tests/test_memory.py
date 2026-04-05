"""Purpose: verify minimal memory hierarchy — working and episodic tiers.
Governance scope: memory-core tests only.
Dependencies: core/memory module.
Invariants: working memory is session-scoped, episodic is append-only, promotion requires verification.
"""

from __future__ import annotations

from types import MappingProxyType

import pytest

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory import (
    EpisodicMemory,
    MemoryEntry,
    MemoryTier,
    PromotionStatus,
    WorkingMemory,
    promote_to_episodic,
)


def _working_entry(entry_id: str = "w-1", category: str = "observation") -> MemoryEntry:
    return MemoryEntry(
        entry_id=entry_id,
        tier=MemoryTier.WORKING,
        category=category,
        content={"key": "value"},
        source_ids=("src-1",),
    )


# --- Working memory ---


def test_working_memory_store_and_get() -> None:
    wm = WorkingMemory()
    entry = _working_entry()
    wm.store(entry)
    assert wm.get("w-1") is entry
    assert wm.size == 1


def test_memory_entry_freezes_content_and_source_ids() -> None:
    entry = MemoryEntry(
        entry_id="w-freeze",
        tier=MemoryTier.WORKING,
        category="observation",
        content={"nested": {"value": 1}},
        source_ids=["src-1"],
    )

    assert isinstance(entry.content, MappingProxyType)
    assert isinstance(entry.content["nested"], MappingProxyType)
    assert entry.source_ids == ("src-1",)
    with pytest.raises(TypeError):
        entry.content["new"] = True  # type: ignore[index]


def test_working_memory_rejects_episodic_tier() -> None:
    wm = WorkingMemory()
    with pytest.raises(RuntimeCoreInvariantError, match="working-tier"):
        wm.store(MemoryEntry(
            entry_id="e-1",
            tier=MemoryTier.EPISODIC,
            category="trace",
            content={},
        ))


def test_working_memory_capacity_bound() -> None:
    wm = WorkingMemory(max_entries=2)
    wm.store(_working_entry("w-1"))
    wm.store(_working_entry("w-2"))
    with pytest.raises(RuntimeCoreInvariantError, match="capacity"):
        wm.store(_working_entry("w-3"))


def test_working_memory_overwrite_within_capacity() -> None:
    wm = WorkingMemory(max_entries=1)
    wm.store(_working_entry("w-1"))
    updated = MemoryEntry(
        entry_id="w-1",
        tier=MemoryTier.WORKING,
        category="updated",
        content={"new": True},
    )
    wm.store(updated)
    assert wm.get("w-1").category == "updated"
    assert wm.size == 1


def test_working_memory_list_and_filter() -> None:
    wm = WorkingMemory()
    wm.store(_working_entry("w-1", category="observation"))
    wm.store(_working_entry("w-2", category="plan"))
    wm.store(_working_entry("w-3", category="observation"))

    assert len(wm.list_entries()) == 3
    assert len(wm.list_entries(category="observation")) == 2
    assert len(wm.list_entries(category="plan")) == 1


def test_working_memory_remove() -> None:
    wm = WorkingMemory()
    wm.store(_working_entry("w-1"))
    assert wm.remove("w-1") is True
    assert wm.get("w-1") is None
    assert wm.remove("w-1") is False


def test_working_memory_clear() -> None:
    wm = WorkingMemory()
    wm.store(_working_entry("w-1"))
    wm.store(_working_entry("w-2"))
    assert wm.clear() == 2
    assert wm.size == 0


# --- Episodic memory ---


def _episodic_entry(entry_id: str = "e-1") -> MemoryEntry:
    return MemoryEntry(
        entry_id=entry_id,
        tier=MemoryTier.EPISODIC,
        category="trace",
        content={"execution_id": "exec-1"},
        source_ids=("exec-1",),
    )


def test_episodic_memory_admit_and_get() -> None:
    em = EpisodicMemory()
    entry = _episodic_entry()
    em.admit(entry)
    assert em.get("e-1") is entry
    assert em.size == 1


def test_episodic_memory_rejects_working_tier() -> None:
    em = EpisodicMemory()
    with pytest.raises(RuntimeCoreInvariantError, match="episodic-tier"):
        em.admit(_working_entry())


def test_episodic_memory_rejects_duplicates() -> None:
    em = EpisodicMemory()
    em.admit(_episodic_entry("e-1"))
    with pytest.raises(
        RuntimeCoreInvariantError,
        match="^entry_id already exists in episodic memory$",
    ) as exc_info:
        em.admit(_episodic_entry("e-1"))
    assert "e-1" not in str(exc_info.value)


def test_episodic_memory_preserves_temporal_order() -> None:
    em = EpisodicMemory()
    em.admit(_episodic_entry("e-3"))
    em.admit(_episodic_entry("e-1"))
    em.admit(_episodic_entry("e-2"))
    ids = tuple(e.entry_id for e in em.list_entries())
    assert ids == ("e-3", "e-1", "e-2")  # insertion order, not sorted


def test_episodic_memory_filter_by_category() -> None:
    em = EpisodicMemory()
    em.admit(MemoryEntry(entry_id="e-1", tier=MemoryTier.EPISODIC, category="trace", content={}))
    em.admit(MemoryEntry(entry_id="e-2", tier=MemoryTier.EPISODIC, category="snapshot", content={}))
    assert len(em.list_entries(category="trace")) == 1
    assert len(em.list_entries(category="snapshot")) == 1


# --- Promotion ---


def test_promote_verified_entry() -> None:
    wm = WorkingMemory()
    em = EpisodicMemory()
    wm.store(_working_entry("w-1"))

    result = promote_to_episodic(wm, em, "w-1", verified=True)

    assert result.status is PromotionStatus.PROMOTED
    assert wm.get("w-1") is None  # removed from working
    assert em.get("w-1") is not None  # exists in episodic
    assert em.get("w-1").tier is MemoryTier.EPISODIC


def test_promote_unverified_rejected() -> None:
    wm = WorkingMemory()
    em = EpisodicMemory()
    wm.store(_working_entry("w-1"))

    result = promote_to_episodic(wm, em, "w-1", verified=False)

    assert result.status is PromotionStatus.REJECTED
    assert "verification" in result.reason
    assert wm.get("w-1") is not None  # still in working
    assert em.get("w-1") is None  # not in episodic


def test_promote_missing_entry_rejected() -> None:
    wm = WorkingMemory()
    em = EpisodicMemory()

    result = promote_to_episodic(wm, em, "nonexistent", verified=True)

    assert result.status is PromotionStatus.REJECTED
    assert "not found" in result.reason


def test_promote_preserves_source_ids() -> None:
    wm = WorkingMemory()
    em = EpisodicMemory()
    wm.store(_working_entry("w-1"))

    promote_to_episodic(wm, em, "w-1", verified=True)

    episodic = em.get("w-1")
    assert episodic.source_ids == ("src-1",)
