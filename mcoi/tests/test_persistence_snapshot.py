"""Purpose: verify snapshot store persistence with atomic writes and fail-closed loading.
Governance scope: persistence layer tests only.
Dependencies: snapshot store module, tmp_path fixture.
Invariants: no partial writes, fail closed on malformed data, deterministic hashing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.persistence import (
    CorruptedDataError,
    PersistenceError,
    SnapshotNotFoundError,
    SnapshotStore,
)


def test_save_and_load_snapshot(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path / "snapshots")
    data = {"key": "value", "nested": {"a": 1}}
    meta = store.save_snapshot("snap-1", data, description="test snapshot")

    assert meta.snapshot_id == "snap-1"
    assert meta.description == "test snapshot"
    assert meta.content_hash  # non-empty

    loaded_meta, loaded_data = store.load_snapshot("snap-1")
    assert loaded_meta.snapshot_id == "snap-1"
    assert loaded_data == {"key": "value", "nested": {"a": 1}}


def test_save_snapshot_produces_deterministic_hash(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path / "snapshots")
    data = {"b": 2, "a": 1}
    meta1 = store.save_snapshot("snap-1", data)
    meta2 = store.save_snapshot("snap-2", data)
    assert meta1.content_hash == meta2.content_hash


def test_load_nonexistent_snapshot_raises(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path / "snapshots")
    with pytest.raises(SnapshotNotFoundError):
        store.load_snapshot("no-such-snap")


def test_list_snapshots(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path / "snapshots")
    assert store.list_snapshots() == ()

    store.save_snapshot("snap-a", {"x": 1})
    store.save_snapshot("snap-b", {"y": 2})

    listed = store.list_snapshots()
    ids = tuple(m.snapshot_id for m in listed)
    assert "snap-a" in ids
    assert "snap-b" in ids


def test_snapshot_exists(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path / "snapshots")
    assert store.snapshot_exists("snap-1") is False
    store.save_snapshot("snap-1", {"k": "v"})
    assert store.snapshot_exists("snap-1") is True


def test_malformed_metadata_raises_corrupted(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path / "snapshots")
    snap_dir = tmp_path / "snapshots" / "bad-snap"
    snap_dir.mkdir(parents=True)
    (snap_dir / "metadata.json").write_text("not json", encoding="utf-8")
    (snap_dir / "data.json").write_text("{}", encoding="utf-8")

    with pytest.raises(CorruptedDataError):
        store.load_snapshot("bad-snap")


def test_malformed_data_raises_corrupted(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path / "snapshots")
    snap_dir = tmp_path / "snapshots" / "bad-data"
    snap_dir.mkdir(parents=True)
    meta = {
        "snapshot_id": "bad-data",
        "created_at": "2026-03-19T00:00:00+00:00",
        "description": "",
        "content_hash": "abc123",
    }
    (snap_dir / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    (snap_dir / "data.json").write_text("not json", encoding="utf-8")

    with pytest.raises(CorruptedDataError):
        store.load_snapshot("bad-data")


def test_tampered_data_raises_corrupted(tmp_path: Path) -> None:
    """Verify that load_snapshot detects corruption when data.json is tampered with."""
    store = SnapshotStore(tmp_path / "snapshots")
    store.save_snapshot("snap-tamper", {"key": "original"})

    # Tamper with the data.json file on disk
    data_path = tmp_path / "snapshots" / "snap-tamper" / "data.json"
    data_path.write_text(json.dumps({"key": "TAMPERED"}), encoding="utf-8")

    with pytest.raises(CorruptedDataError, match="content hash mismatch"):
        store.load_snapshot("snap-tamper")


def test_empty_snapshot_id_raises(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path / "snapshots")
    with pytest.raises(PersistenceError):
        store.save_snapshot("", {"k": "v"})
    with pytest.raises(PersistenceError):
        store.load_snapshot("")
    with pytest.raises(PersistenceError):
        store.snapshot_exists("")
