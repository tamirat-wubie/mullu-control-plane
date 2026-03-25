"""Purpose: minimal memory hierarchy for the MCOI runtime.
Governance scope: memory tier management per docs/09_memory_hierarchy.md.
Dependencies: persistence stores, trace/snapshot contracts, runtime-core invariants.
Invariants:
  - Working memory is session-scoped and mutable.
  - Episodic memory is append-only after verification closure.
  - Promotion from working to episodic requires verification closure.
  - No tier may be skipped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text


class MemoryTier(StrEnum):
    WORKING = "working"
    EPISODIC = "episodic"


class PromotionStatus(StrEnum):
    PROMOTED = "promoted"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class MemoryEntry:
    """A single memory entry with explicit tier and provenance."""

    entry_id: str
    tier: MemoryTier
    category: str
    content: Mapping[str, Any]
    source_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "entry_id", ensure_non_empty_text("entry_id", self.entry_id))
        if not isinstance(self.tier, MemoryTier):
            raise RuntimeCoreInvariantError("tier must be a MemoryTier value")
        object.__setattr__(self, "category", ensure_non_empty_text("category", self.category))
        if not isinstance(self.content, Mapping):
            raise RuntimeCoreInvariantError("content must be a mapping")


@dataclass(frozen=True, slots=True)
class PromotionResult:
    """Result of attempting to promote a working memory entry to episodic."""

    entry_id: str
    status: PromotionStatus
    reason: str


class WorkingMemory:
    """Session-scoped mutable memory. Discarded when session ends unless promoted.

    Per docs/09_memory_hierarchy.md:
    - Fully mutable within the session.
    - Trust level: untrusted until verified.
    - MUST NOT be used as a source for cross-session reasoning.
    - Size MUST be bounded.
    """

    def __init__(self, *, max_entries: int = 1000) -> None:
        if max_entries <= 0:
            raise RuntimeCoreInvariantError("max_entries must be positive")
        self._entries: dict[str, MemoryEntry] = {}
        self._max_entries = max_entries

    def store(self, entry: MemoryEntry) -> MemoryEntry:
        if entry.tier is not MemoryTier.WORKING:
            raise RuntimeCoreInvariantError("only working-tier entries may be stored in working memory")
        if len(self._entries) >= self._max_entries and entry.entry_id not in self._entries:
            raise RuntimeCoreInvariantError("working memory capacity exceeded")
        self._entries[entry.entry_id] = entry
        return entry

    def get(self, entry_id: str) -> MemoryEntry | None:
        ensure_non_empty_text("entry_id", entry_id)
        return self._entries.get(entry_id)

    def list_entries(self, *, category: str | None = None) -> tuple[MemoryEntry, ...]:
        entries = sorted(self._entries.values(), key=lambda e: e.entry_id)
        if category is not None:
            ensure_non_empty_text("category", category)
            entries = [e for e in entries if e.category == category]
        return tuple(entries)

    def remove(self, entry_id: str) -> bool:
        ensure_non_empty_text("entry_id", entry_id)
        return self._entries.pop(entry_id, None) is not None

    def clear(self) -> int:
        count = len(self._entries)
        self._entries.clear()
        return count

    @property
    def size(self) -> int:
        return len(self._entries)


class EpisodicMemory:
    """Append-only memory for verified execution outcomes and closed traces.

    Per docs/09_memory_hierarchy.md:
    - Append-only after verification closure.
    - Trust level: trusted.
    - Queryable by identity chain.
    - Preserves temporal ordering.
    """

    def __init__(self) -> None:
        self._entries: dict[str, MemoryEntry] = {}
        self._order: list[str] = []

    def admit(self, entry: MemoryEntry) -> MemoryEntry:
        """Admit a verified entry into episodic memory.

        Entries must be episodic-tier. Duplicate entry_ids are rejected.
        """
        if entry.tier is not MemoryTier.EPISODIC:
            raise RuntimeCoreInvariantError("only episodic-tier entries may be admitted to episodic memory")
        if entry.entry_id in self._entries:
            raise RuntimeCoreInvariantError(f"entry_id already exists in episodic memory: {entry.entry_id}")
        self._entries[entry.entry_id] = entry
        self._order.append(entry.entry_id)
        return entry

    def get(self, entry_id: str) -> MemoryEntry | None:
        ensure_non_empty_text("entry_id", entry_id)
        return self._entries.get(entry_id)

    def list_entries(self, *, category: str | None = None) -> tuple[MemoryEntry, ...]:
        entries = [self._entries[eid] for eid in self._order]
        if category is not None:
            ensure_non_empty_text("category", category)
            entries = [e for e in entries if e.category == category]
        return tuple(entries)

    @property
    def size(self) -> int:
        return len(self._entries)


def promote_to_episodic(
    working: WorkingMemory,
    episodic: EpisodicMemory,
    entry_id: str,
    *,
    verified: bool,
) -> PromotionResult:
    """Promote a working memory entry to episodic memory.

    Per docs/09_memory_hierarchy.md:
    - Promotion requires verification closure.
    - The entry is re-created as episodic-tier.
    - The original working memory entry is removed on success.
    """
    ensure_non_empty_text("entry_id", entry_id)

    source = working.get(entry_id)
    if source is None:
        return PromotionResult(
            entry_id=entry_id,
            status=PromotionStatus.REJECTED,
            reason="entry not found in working memory",
        )

    if not verified:
        return PromotionResult(
            entry_id=entry_id,
            status=PromotionStatus.REJECTED,
            reason="promotion requires verification closure",
        )

    episodic_entry = MemoryEntry(
        entry_id=source.entry_id,
        tier=MemoryTier.EPISODIC,
        category=source.category,
        content=source.content,
        source_ids=source.source_ids,
    )

    # Construct-then-commit: remove from working first (reversible),
    # then admit to episodic. If admission fails, re-add to working.
    # This prevents the entry existing in both tiers simultaneously.
    working.remove(entry_id)

    try:
        episodic.admit(episodic_entry)
    except RuntimeCoreInvariantError:
        # Rollback: re-add to working memory
        working.store(source)
        return PromotionResult(
            entry_id=entry_id,
            status=PromotionStatus.REJECTED,
            reason="entry already exists in episodic memory",
        )

    return PromotionResult(
        entry_id=entry_id,
        status=PromotionStatus.PROMOTED,
        reason="promoted from working to episodic",
    )
