"""Purpose: verify path traversal prevention across all persistence stores.
Governance scope: persistence layer security tests.
Dependencies: all persistence stores, PathTraversalError, tmp_path fixture.
Invariants: no ID may escape the store's base directory.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.contracts.trace import TraceEntry
from mcoi_runtime.core.replay_engine import (
    EffectControl,
    ReplayArtifact,
    ReplayEffect,
    ReplayMode,
    ReplayRecord,
)
from mcoi_runtime.persistence import (
    PathTraversalError,
    ReplayStore,
    SkillStore,
    SnapshotStore,
    TraceStore,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MALICIOUS_IDS = [
    "../../etc/passwd",
    "foo/bar",
    "foo\\bar",
    "foo\0bar",
    "..\\..\\windows\\system32\\config\\sam",
    "../secret",
]


def _make_trace(trace_id: str) -> TraceEntry:
    return TraceEntry(
        trace_id=trace_id,
        parent_trace_id=None,
        event_type="test_event",
        subject_id="subject-1",
        goal_id="goal-1",
        state_hash="state-hash-1",
        registry_hash="registry-hash-1",
        timestamp="2026-03-19T00:00:00+00:00",
    )


def _make_replay(replay_id: str) -> ReplayRecord:
    return ReplayRecord(
        replay_id=replay_id,
        trace_id="trace-1",
        source_hash="source-1",
        approved_effects=(
            ReplayEffect(
                effect_id="effect-1",
                control=EffectControl.CONTROLLED,
                artifact_id="artifact-1",
            ),
        ),
        blocked_effects=(),
        mode=ReplayMode.OBSERVATION_ONLY,
        recorded_at="2026-03-19T00:00:00+00:00",
        artifacts=(ReplayArtifact(artifact_id="artifact-1", payload_digest="digest-1"),),
        state_hash="hash-a",
        environment_digest="env-a",
    )


# ---------------------------------------------------------------------------
# SnapshotStore
# ---------------------------------------------------------------------------

class TestSnapshotStorePathTraversal:

    def test_normal_id_works(self, tmp_path: Path) -> None:
        store = SnapshotStore(tmp_path / "snapshots")
        meta = store.save_snapshot("valid-snap-1", {"key": "value"})
        assert meta.snapshot_id == "valid-snap-1"
        loaded_meta, loaded_data = store.load_snapshot("valid-snap-1")
        assert loaded_data == {"key": "value"}

    @pytest.mark.parametrize("bad_id", MALICIOUS_IDS)
    def test_malicious_id_rejected_on_save(self, tmp_path: Path, bad_id: str) -> None:
        store = SnapshotStore(tmp_path / "snapshots")
        with pytest.raises(PathTraversalError) as excinfo:
            store.save_snapshot(bad_id, {"key": "value"})
        expected = (
            "identifier contains null byte"
            if "\0" in bad_id
            else "identifier contains forbidden characters"
        )
        assert str(excinfo.value) == expected
        assert bad_id not in str(excinfo.value)

    @pytest.mark.parametrize("bad_id", MALICIOUS_IDS)
    def test_malicious_id_rejected_on_load(self, tmp_path: Path, bad_id: str) -> None:
        store = SnapshotStore(tmp_path / "snapshots")
        with pytest.raises(PathTraversalError):
            store.load_snapshot(bad_id)

    @pytest.mark.parametrize("bad_id", MALICIOUS_IDS)
    def test_malicious_id_rejected_on_exists(self, tmp_path: Path, bad_id: str) -> None:
        store = SnapshotStore(tmp_path / "snapshots")
        with pytest.raises(PathTraversalError):
            store.snapshot_exists(bad_id)


# ---------------------------------------------------------------------------
# TraceStore
# ---------------------------------------------------------------------------

class TestTraceStorePathTraversal:

    def test_normal_id_works(self, tmp_path: Path) -> None:
        store = TraceStore(tmp_path / "traces")
        entry = _make_trace("valid-trace-1")
        store.append(entry)
        loaded = store.load_trace("valid-trace-1")
        assert loaded.trace_id == "valid-trace-1"

    @pytest.mark.parametrize("bad_id", MALICIOUS_IDS)
    def test_malicious_id_rejected_on_append(self, tmp_path: Path, bad_id: str) -> None:
        store = TraceStore(tmp_path / "traces")
        entry = _make_trace(bad_id)
        with pytest.raises(PathTraversalError):
            store.append(entry)

    @pytest.mark.parametrize("bad_id", MALICIOUS_IDS)
    def test_malicious_id_rejected_on_load(self, tmp_path: Path, bad_id: str) -> None:
        store = TraceStore(tmp_path / "traces")
        with pytest.raises(PathTraversalError) as excinfo:
            store.load_trace(bad_id)
        expected = (
            "identifier contains null byte"
            if "\0" in bad_id
            else "identifier contains forbidden characters"
        )
        assert str(excinfo.value) == expected
        assert bad_id not in str(excinfo.value)


# ---------------------------------------------------------------------------
# ReplayStore
# ---------------------------------------------------------------------------

class TestReplayStorePathTraversal:

    def test_normal_id_works(self, tmp_path: Path) -> None:
        store = ReplayStore(tmp_path / "replays")
        record = _make_replay("valid-replay-1")
        store.save(record)
        loaded = store.load("valid-replay-1")
        assert loaded.replay_id == "valid-replay-1"

    @pytest.mark.parametrize("bad_id", MALICIOUS_IDS)
    def test_malicious_id_rejected_on_save(self, tmp_path: Path, bad_id: str) -> None:
        store = ReplayStore(tmp_path / "replays")
        record = _make_replay(bad_id)
        with pytest.raises(PathTraversalError):
            store.save(record)

    @pytest.mark.parametrize("bad_id", MALICIOUS_IDS)
    def test_malicious_id_rejected_on_load(self, tmp_path: Path, bad_id: str) -> None:
        store = ReplayStore(tmp_path / "replays")
        with pytest.raises(PathTraversalError) as excinfo:
            store.load(bad_id)
        expected = (
            "identifier contains null byte"
            if "\0" in bad_id
            else "identifier contains forbidden characters"
        )
        assert str(excinfo.value) == expected
        assert bad_id not in str(excinfo.value)


# ---------------------------------------------------------------------------
# SkillStore
# ---------------------------------------------------------------------------

class TestSkillStorePathTraversal:

    @pytest.mark.parametrize("bad_id", MALICIOUS_IDS)
    def test_malicious_id_rejected_on_load(self, tmp_path: Path, bad_id: str) -> None:
        store = SkillStore(tmp_path / "skills")
        with pytest.raises(PathTraversalError) as excinfo:
            store.load(bad_id)
        expected = (
            "identifier contains null byte"
            if "\0" in bad_id
            else "identifier contains forbidden characters"
        )
        assert str(excinfo.value) == expected
        assert bad_id not in str(excinfo.value)
