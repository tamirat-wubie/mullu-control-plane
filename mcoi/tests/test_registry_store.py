"""Purpose: verify typed registry storage behavior for runtime-core.
Governance scope: runtime-core tests only.
Dependencies: pytest and the runtime-core registry store module.
Invariants: registry storage preserves lifecycle state and avoids hidden mutation on read.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.registry_store import RegistryEntry, RegistryLifecycle, RegistryStore


@dataclass(slots=True)
class CapabilityRecord:
    capability_id: str
    tags: list[str]


def test_registry_store_add_get_and_list_preserve_explicit_lifecycle() -> None:
    store: RegistryStore[CapabilityRecord] = RegistryStore()
    entry = RegistryEntry(
        entry_id="capability-1",
        entry_type="capability",
        value=CapabilityRecord(capability_id="cap-1", tags=["workspace"]),
        lifecycle=RegistryLifecycle.ACTIVE,
    )

    stored = store.add(entry)
    loaded = store.get("capability-1")
    listed = store.list(entry_type="capability", lifecycle=RegistryLifecycle.ACTIVE)

    assert stored.entry_id == "capability-1"
    assert loaded is not None
    assert loaded.lifecycle is RegistryLifecycle.ACTIVE
    assert listed[0].value.capability_id == "cap-1"


def test_registry_store_returns_copied_entries_on_read() -> None:
    store: RegistryStore[CapabilityRecord] = RegistryStore()
    store.add(
        RegistryEntry(
            entry_id="capability-1",
            entry_type="capability",
            value=CapabilityRecord(capability_id="cap-1", tags=["workspace"]),
            lifecycle=RegistryLifecycle.ACTIVE,
        )
    )

    first_read = store.get("capability-1")
    assert first_read is not None
    assert first_read.value.tags == ["workspace"]

    first_read.value.tags.append("mutated")
    second_read = store.get("capability-1")

    assert second_read is not None
    assert second_read.value.tags == ["workspace"]
    assert first_read.value.tags == ["workspace", "mutated"]


def test_registry_store_rejects_duplicate_entry_ids() -> None:
    store: RegistryStore[CapabilityRecord] = RegistryStore()
    entry = RegistryEntry(
        entry_id="capability-1",
        entry_type="capability",
        value=CapabilityRecord(capability_id="cap-1", tags=["workspace"]),
        lifecycle=RegistryLifecycle.ACTIVE,
    )
    store.add(entry)

    with pytest.raises(RuntimeCoreInvariantError) as exc_info:
        store.add(entry)

    assert str(exc_info.value) == "entry_id already exists"
    assert "capability-1" not in str(exc_info.value)
    assert store.get("capability-1") is not None
    assert len(store.list()) == 1
