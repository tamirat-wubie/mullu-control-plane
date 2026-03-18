"""Purpose: explicit derived registry lookup views for runtime-core.
Governance scope: runtime-core indexing only.
Dependencies: registry store and invariant helpers.
Invariants: index derives only from store contents and never becomes a second source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from .invariants import freeze_mapping
from .registry_store import RegistryLifecycle, RegistryStore

EntryT = TypeVar("EntryT")


@dataclass(frozen=True, slots=True)
class RegistryIndexSnapshot:
    by_type: dict[str, tuple[str, ...]]
    by_lifecycle: dict[str, tuple[str, ...]]


class RegistryIndex(Generic[EntryT]):
    """Deterministic lookup views built explicitly from registry store state."""

    def __init__(self) -> None:
        self._by_type: dict[str, tuple[str, ...]] = {}
        self._by_lifecycle: dict[str, tuple[str, ...]] = {}

    def refresh(self, store: RegistryStore[EntryT]) -> RegistryIndexSnapshot:
        entries = store.list()
        by_type: dict[str, list[str]] = {}
        by_lifecycle: dict[str, list[str]] = {}

        for entry in entries:
            by_type.setdefault(entry.entry_type, []).append(entry.entry_id)
            by_lifecycle.setdefault(entry.lifecycle.value, []).append(entry.entry_id)

        self._by_type = {
            entry_type: tuple(sorted(entry_ids))
            for entry_type, entry_ids in sorted(by_type.items())
        }
        self._by_lifecycle = {
            lifecycle: tuple(sorted(entry_ids))
            for lifecycle, entry_ids in sorted(by_lifecycle.items())
        }
        return self.snapshot()

    def ids_for_type(self, entry_type: str) -> tuple[str, ...]:
        return self._by_type.get(entry_type, ())

    def ids_for_lifecycle(self, lifecycle: RegistryLifecycle) -> tuple[str, ...]:
        return self._by_lifecycle.get(lifecycle.value, ())

    def snapshot(self) -> RegistryIndexSnapshot:
        return RegistryIndexSnapshot(
            by_type=dict(freeze_mapping(self._by_type)),
            by_lifecycle=dict(freeze_mapping(self._by_lifecycle)),
        )
