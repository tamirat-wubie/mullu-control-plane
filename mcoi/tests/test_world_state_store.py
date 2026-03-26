"""Phase 201B — World-state persistence store tests."""

import pytest
from mcoi_runtime.persistence.world_state_store import (
    WorldStateStore,
    StoredSnapshot,
    StoredDelta,
    EntityHistoryEntry,
)

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


class TestWorldStateStore:
    def test_store_snapshot(self):
        store = WorldStateStore()
        snap = store.store_snapshot(
            snapshot_id="snap-1",
            state_hash="abc123",
            entity_count=5,
            relation_count=3,
            overall_confidence=0.85,
            captured_at=FIXED_CLOCK(),
            payload={"entities": []},
        )
        assert snap.snapshot_id == "snap-1"
        assert snap.state_hash == "abc123"
        assert snap.entity_count == 5

    def test_duplicate_snapshot_raises(self):
        store = WorldStateStore()
        store.store_snapshot("s1", "h1", 1, 0, 1.0, FIXED_CLOCK(), {})
        with pytest.raises(ValueError, match="already exists"):
            store.store_snapshot("s1", "h2", 2, 0, 1.0, FIXED_CLOCK(), {})

    def test_get_snapshot(self):
        store = WorldStateStore()
        store.store_snapshot("s1", "h1", 1, 0, 1.0, FIXED_CLOCK(), {"k": "v"})
        snap = store.get_snapshot("s1")
        assert snap is not None
        assert snap.state_hash == "h1"

    def test_get_missing_snapshot(self):
        store = WorldStateStore()
        assert store.get_snapshot("nonexistent") is None

    def test_latest_snapshot(self):
        store = WorldStateStore()
        store.store_snapshot("s1", "h1", 1, 0, 1.0, FIXED_CLOCK(), {})
        store.store_snapshot("s2", "h2", 2, 0, 0.9, FIXED_CLOCK(), {})
        latest = store.latest_snapshot()
        assert latest.snapshot_id == "s2"

    def test_latest_snapshot_empty(self):
        store = WorldStateStore()
        assert store.latest_snapshot() is None

    def test_list_snapshots(self):
        store = WorldStateStore()
        for i in range(5):
            store.store_snapshot(f"s{i}", f"h{i}", i, 0, 1.0, FIXED_CLOCK(), {})
        snaps = store.list_snapshots(limit=3)
        assert len(snaps) == 3
        assert snaps[0].snapshot_id == "s4"  # Most recent first

    def test_store_delta(self):
        store = WorldStateStore()
        delta = store.store_delta(
            delta_id="d1",
            previous_snapshot_id="s1",
            current_snapshot_id="s2",
            changes=[{"kind": "added", "entity": "e1"}],
            computed_at=FIXED_CLOCK(),
        )
        assert delta.delta_id == "d1"
        assert len(delta.changes) == 1

    def test_duplicate_delta_raises(self):
        store = WorldStateStore()
        store.store_delta("d1", "s1", "s2", [], FIXED_CLOCK())
        with pytest.raises(ValueError, match="already exists"):
            store.store_delta("d1", "s1", "s2", [], FIXED_CLOCK())

    def test_deltas_for_snapshot(self):
        store = WorldStateStore()
        store.store_delta("d1", "s1", "s2", [], FIXED_CLOCK())
        store.store_delta("d2", "s2", "s3", [], FIXED_CLOCK())
        deltas = store.deltas_for_snapshot("s2")
        assert len(deltas) == 1
        assert deltas[0].previous_snapshot_id == "s1"

    def test_record_entity_state(self):
        store = WorldStateStore()
        entry = store.record_entity_state(
            entity_id="e1",
            snapshot_id="s1",
            attributes={"status": "running"},
            confidence=0.95,
            recorded_at=FIXED_CLOCK(),
        )
        assert entry.entity_id == "e1"
        assert entry.confidence == 0.95

    def test_entity_history(self):
        store = WorldStateStore()
        store.record_entity_state("e1", "s1", {"v": 1}, 0.9, FIXED_CLOCK())
        store.record_entity_state("e1", "s2", {"v": 2}, 0.8, FIXED_CLOCK())
        history = store.entity_history("e1")
        assert len(history) == 2

    def test_entity_at_snapshot(self):
        store = WorldStateStore()
        store.record_entity_state("e1", "s1", {"v": 1}, 0.9, FIXED_CLOCK())
        store.record_entity_state("e1", "s2", {"v": 2}, 0.8, FIXED_CLOCK())
        entry = store.entity_at_snapshot("e1", "s2")
        assert entry is not None
        assert entry.attributes["v"] == 2

    def test_entity_at_missing_snapshot(self):
        store = WorldStateStore()
        store.record_entity_state("e1", "s1", {}, 1.0, FIXED_CLOCK())
        assert store.entity_at_snapshot("e1", "nonexistent") is None

    def test_counts(self):
        store = WorldStateStore()
        assert store.snapshot_count == 0
        assert store.delta_count == 0
        assert store.tracked_entity_count == 0
        store.store_snapshot("s1", "h1", 1, 0, 1.0, FIXED_CLOCK(), {})
        store.store_delta("d1", "s0", "s1", [], FIXED_CLOCK())
        store.record_entity_state("e1", "s1", {}, 1.0, FIXED_CLOCK())
        assert store.snapshot_count == 1
        assert store.delta_count == 1
        assert store.tracked_entity_count == 1

    def test_summary(self):
        store = WorldStateStore()
        store.store_snapshot("s1", "h1", 1, 0, 1.0, FIXED_CLOCK(), {})
        summary = store.summary()
        assert summary["snapshots"] == 1
        assert summary["latest_snapshot"] == "s1"
