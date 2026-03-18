"""Purpose: verify deterministic registry index derivation for runtime-core.
Governance scope: runtime-core tests only.
Dependencies: the runtime-core registry store and registry index modules.
Invariants: index state derives only from store contents and refreshes explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass

from mcoi_runtime.core.registry_index import RegistryIndex
from mcoi_runtime.core.registry_store import RegistryEntry, RegistryLifecycle, RegistryStore


@dataclass(slots=True)
class RegistryRecord:
    record_id: str


def test_registry_index_refresh_derives_lookups_from_store_only() -> None:
    store: RegistryStore[RegistryRecord] = RegistryStore()
    index: RegistryIndex[RegistryRecord] = RegistryIndex()

    store.add(
        RegistryEntry(
            entry_id="record-1",
            entry_type="capability",
            value=RegistryRecord(record_id="record-1"),
            lifecycle=RegistryLifecycle.ACTIVE,
        )
    )
    first_snapshot = index.refresh(store)

    store.add(
        RegistryEntry(
            entry_id="record-2",
            entry_type="capability",
            value=RegistryRecord(record_id="record-2"),
            lifecycle=RegistryLifecycle.BLOCKED,
        )
    )

    assert first_snapshot.by_type["capability"] == ("record-1",)
    assert index.ids_for_type("capability") == ("record-1",)
    assert index.ids_for_lifecycle(RegistryLifecycle.BLOCKED) == ()

    second_snapshot = index.refresh(store)

    assert second_snapshot.by_type["capability"] == ("record-1", "record-2")
    assert second_snapshot.by_lifecycle["blocked"] == ("record-2",)
    assert index.ids_for_type("capability") == ("record-1", "record-2")
