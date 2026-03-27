"""Tests for Phase 228C — Rollback Snapshot Manager."""
from __future__ import annotations
import pytest
from mcoi_runtime.core.rollback_snapshot import SnapshotManager


class TestSnapshotManager:
    def test_create_snapshot(self):
        mgr = SnapshotManager()
        state = {"config": {"debug": True}, "version": "2.9.0"}
        snap = mgr.create_snapshot("s1", "Pre-deploy", state)
        assert snap.snapshot_id == "s1"
        assert snap.checksum
        assert mgr.snapshot_count == 1

    def test_snapshot_immutable(self):
        mgr = SnapshotManager()
        state = {"key": "original"}
        snap = mgr.create_snapshot("s1", "test", state)
        state["key"] = "modified"  # mutate original
        assert snap.state["key"] == "original"  # snapshot unchanged

    def test_get_snapshot(self):
        mgr = SnapshotManager()
        mgr.create_snapshot("s1", "test", {"a": 1})
        snap = mgr.get_snapshot("s1")
        assert snap is not None
        assert snap.state["a"] == 1

    def test_get_nonexistent(self):
        mgr = SnapshotManager()
        assert mgr.get_snapshot("nonexistent") is None

    def test_rollback_success(self):
        mgr = SnapshotManager()
        mgr.create_snapshot("s1", "backup", {"flag": True, "version": "1.0"})
        restored = {}
        result = mgr.rollback("s1", apply_fn=lambda s: restored.update(s))
        assert result.success
        assert restored["flag"] is True
        assert "flag" in result.restored_keys

    def test_rollback_nonexistent(self):
        mgr = SnapshotManager()
        result = mgr.rollback("nonexistent")
        assert not result.success
        assert "not found" in result.error

    def test_rollback_with_error(self):
        mgr = SnapshotManager()
        mgr.create_snapshot("s1", "test", {"a": 1})
        def bad_apply(state):
            raise RuntimeError("apply failed")
        result = mgr.rollback("s1", apply_fn=bad_apply)
        assert not result.success
        assert "apply failed" in result.error

    def test_eviction_when_full(self):
        mgr = SnapshotManager(max_snapshots=2)
        mgr.create_snapshot("s1", "first", {})
        mgr.create_snapshot("s2", "second", {})
        mgr.create_snapshot("s3", "third", {})
        assert mgr.snapshot_count == 2
        assert mgr.get_snapshot("s1") is None  # evicted

    def test_list_snapshots(self):
        mgr = SnapshotManager()
        for i in range(5):
            mgr.create_snapshot(f"s{i}", f"snap-{i}", {"i": i})
        recent = mgr.list_snapshots(limit=3)
        assert len(recent) == 3
        assert recent[0].snapshot_id == "s4"  # most recent first

    def test_delete_snapshot(self):
        mgr = SnapshotManager()
        mgr.create_snapshot("s1", "test", {})
        assert mgr.delete_snapshot("s1")
        assert mgr.snapshot_count == 0
        assert not mgr.delete_snapshot("nonexistent")

    def test_to_dict(self):
        mgr = SnapshotManager()
        snap = mgr.create_snapshot("s1", "test", {"config": "val"})
        d = snap.to_dict()
        assert d["snapshot_id"] == "s1"
        assert "config" in d["state_keys"]

    def test_summary(self):
        mgr = SnapshotManager(max_snapshots=10)
        mgr.create_snapshot("s1", "test", {})
        s = mgr.summary()
        assert s["total_snapshots_created"] == 1
        assert s["current_snapshots"] == 1
        assert s["max_snapshots"] == 10
