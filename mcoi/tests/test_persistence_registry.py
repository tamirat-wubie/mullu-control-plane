"""Purpose: verify registry backend persistence with lifecycle preservation.
Governance scope: persistence layer tests only.
Dependencies: registry backend module, registry store types, tmp_path fixture.
Invariants: preserves lifecycle state explicitly, fail closed on malformed data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from mcoi_runtime.core.registry_store import RegistryEntry, RegistryLifecycle, RegistryStore
from mcoi_runtime.persistence import (
    CorruptedDataError,
    RegistryBackend,
)
from mcoi_runtime.persistence.registry_backend import _entry_value_to_dict


@dataclass(frozen=True, slots=True)
class FakeCapability:
    name: str
    version: str


@dataclass(frozen=True, slots=True)
class CapabilityWithTags:
    name: str
    tags: list[str]


def test_save_and_load_registry(tmp_path: Path) -> None:
    backend = RegistryBackend(tmp_path / "registry")
    store: RegistryStore[FakeCapability] = RegistryStore()
    store.add(
        RegistryEntry(
            entry_id="cap-1",
            entry_type="capability",
            value=FakeCapability(name="shell", version="1.0"),
            lifecycle=RegistryLifecycle.ACTIVE,
        )
    )
    store.add(
        RegistryEntry(
            entry_id="cap-2",
            entry_type="capability",
            value=FakeCapability(name="filesystem", version="2.0"),
            lifecycle=RegistryLifecycle.DEPRECATED,
        )
    )

    content_hash = backend.save_registry(store)
    assert content_hash  # non-empty

    loaded = backend.load_registry()
    entries = loaded.list()
    assert len(entries) == 2

    cap1 = loaded.get("cap-1")
    assert cap1 is not None
    assert cap1.entry_type == "capability"
    assert cap1.lifecycle == RegistryLifecycle.ACTIVE

    cap2 = loaded.get("cap-2")
    assert cap2 is not None
    assert cap2.lifecycle == RegistryLifecycle.DEPRECATED


def test_load_registry_preserves_mutable_value_fields(tmp_path: Path) -> None:
    backend = RegistryBackend(tmp_path / "registry")
    store: RegistryStore[CapabilityWithTags] = RegistryStore()
    store.add(
        RegistryEntry(
            entry_id="cap-1",
            entry_type="capability",
            value=CapabilityWithTags(name="shell", tags=["local", "governed"]),
            lifecycle=RegistryLifecycle.ACTIVE,
        )
    )

    backend.save_registry(store)
    loaded = backend.load_registry()
    cap1 = loaded.get("cap-1")

    assert cap1 is not None
    assert cap1.value.tags == ["local", "governed"]
    assert cap1.lifecycle == RegistryLifecycle.ACTIVE


def test_registry_exists(tmp_path: Path) -> None:
    backend = RegistryBackend(tmp_path / "registry")
    assert backend.registry_exists() is False

    store: RegistryStore[FakeCapability] = RegistryStore()
    backend.save_registry(store)
    assert backend.registry_exists() is True


def test_save_empty_registry(tmp_path: Path) -> None:
    backend = RegistryBackend(tmp_path / "registry")
    store: RegistryStore[FakeCapability] = RegistryStore()
    content_hash = backend.save_registry(store)
    assert content_hash

    loaded = backend.load_registry()
    assert loaded.list() == ()


def test_entry_value_to_dict_bounds_non_dataclass_value_error() -> None:
    with pytest.raises(
        CorruptedDataError,
        match=r"^registry entry value must be a dataclass instance$",
    ) as excinfo:
        _entry_value_to_dict({"name": "shell"})
    assert "dict" not in str(excinfo.value)


def test_load_nonexistent_registry_raises(tmp_path: Path) -> None:
    backend = RegistryBackend(tmp_path / "registry")
    with pytest.raises(CorruptedDataError):
        backend.load_registry()


def test_malformed_registry_file_raises(tmp_path: Path) -> None:
    reg_dir = tmp_path / "registry"
    reg_dir.mkdir(parents=True)
    (reg_dir / "registry.json").write_text("not json", encoding="utf-8")

    backend = RegistryBackend(reg_dir)
    with pytest.raises(CorruptedDataError, match=r"^malformed registry file \(JSONDecodeError\)$"):
        backend.load_registry()


def test_registry_entry_id_mismatch_raises(tmp_path: Path) -> None:
    backend = RegistryBackend(tmp_path / "registry")
    store: RegistryStore[FakeCapability] = RegistryStore()
    store.add(
        RegistryEntry(
            entry_id="cap-1",
            entry_type="capability",
            value=FakeCapability(name="test", version="1.0"),
            lifecycle=RegistryLifecycle.ACTIVE,
        )
    )
    backend.save_registry(store)
    registry_path = tmp_path / "registry" / "registry.json"
    raw = json.loads(registry_path.read_text(encoding="utf-8"))
    raw["entries"]["cap-1"]["entry_id"] = "cap-other"
    registry_path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(CorruptedDataError, match=r"^registry entry id mismatch$"):
        backend.load_registry()


def test_registry_invalid_value_field_raises(tmp_path: Path) -> None:
    reg_dir = tmp_path / "registry"
    reg_dir.mkdir(parents=True)
    (reg_dir / "registry.json").write_text(
        json.dumps(
            {
                "entries": {
                    "cap-1": {
                        "entry_id": "cap-1",
                        "entry_type": "capability",
                        "lifecycle": "active",
                        "value": {"bad-field": "x"},
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    backend = RegistryBackend(reg_dir)
    with pytest.raises(CorruptedDataError, match=r"^registry entry value has invalid field$"):
        backend.load_registry()


def test_deterministic_hash_for_same_content(tmp_path: Path) -> None:
    backend1 = RegistryBackend(tmp_path / "reg1")
    backend2 = RegistryBackend(tmp_path / "reg2")

    store: RegistryStore[FakeCapability] = RegistryStore()
    store.add(
        RegistryEntry(
            entry_id="cap-1",
            entry_type="capability",
            value=FakeCapability(name="test", version="1.0"),
            lifecycle=RegistryLifecycle.ACTIVE,
        )
    )

    hash1 = backend1.save_registry(store)
    hash2 = backend2.save_registry(store)
    assert hash1 == hash2
