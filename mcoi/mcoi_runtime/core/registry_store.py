"""Purpose: typed registry storage for deterministic runtime-core lookups.
Governance scope: runtime-core storage only.
Dependencies: runtime-core invariant helpers.
Invariants: store holds typed entries only, preserves explicit lifecycle, and does not derive indexes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, TypeVar

from .invariants import RuntimeCoreInvariantError, copied, ensure_dataclass_instance, ensure_non_empty_text

EntryT = TypeVar("EntryT")


class RegistryLifecycle(StrEnum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    DEPRECATED = "deprecated"


@dataclass(frozen=True, slots=True)
class RegistryEntry(Generic[EntryT]):
    entry_id: str
    entry_type: str
    value: EntryT
    lifecycle: RegistryLifecycle

    def __post_init__(self) -> None:
        object.__setattr__(self, "entry_id", ensure_non_empty_text("entry_id", self.entry_id))
        object.__setattr__(self, "entry_type", ensure_non_empty_text("entry_type", self.entry_type))
        object.__setattr__(self, "value", ensure_dataclass_instance("value", self.value))
        if not isinstance(self.lifecycle, RegistryLifecycle):
            raise RuntimeCoreInvariantError("lifecycle must be a RegistryLifecycle value")


class RegistryStore(Generic[EntryT]):
    """Explicit typed store with no internal indexing or lifecycle inference."""

    def __init__(self) -> None:
        self._entries: dict[str, RegistryEntry[EntryT]] = {}

    def add(self, entry: RegistryEntry[EntryT]) -> RegistryEntry[EntryT]:
        if entry.entry_id in self._entries:
            raise RuntimeCoreInvariantError(f"entry_id already exists: {entry.entry_id}")
        self._entries[entry.entry_id] = copied(entry)
        return copied(self._entries[entry.entry_id])

    def get(self, entry_id: str) -> RegistryEntry[EntryT] | None:
        ensure_non_empty_text("entry_id", entry_id)
        entry = self._entries.get(entry_id)
        if entry is None:
            return None
        return copied(entry)

    def list(
        self,
        *,
        entry_type: str | None = None,
        lifecycle: RegistryLifecycle | None = None,
    ) -> tuple[RegistryEntry[EntryT], ...]:
        if entry_type is not None:
            ensure_non_empty_text("entry_type", entry_type)
        if lifecycle is not None and not isinstance(lifecycle, RegistryLifecycle):
            raise RuntimeCoreInvariantError("lifecycle must be a RegistryLifecycle value")

        entries = tuple(
            copied(entry)
            for entry_id, entry in sorted(self._entries.items())
            if (entry_type is None or entry.entry_type == entry_type)
            and (lifecycle is None or entry.lifecycle == lifecycle)
        )
        return entries
