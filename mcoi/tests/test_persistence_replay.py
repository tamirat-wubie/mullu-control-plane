"""Purpose: verify replay store persistence with round-trip fidelity.
Governance scope: persistence layer tests only.
Dependencies: replay store module, replay engine types, tmp_path fixture.
Invariants: one file per replay record, fail closed on malformed data.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.core.replay_engine import (
    EffectControl,
    ReplayArtifact,
    ReplayEffect,
    ReplayMode,
    ReplayRecord,
)
from mcoi_runtime.persistence import (
    CorruptedDataError,
    PersistenceError,
    ReplayStore,
)


def _make_record(
    replay_id: str = "replay-1",
    state_hash: str | None = "hash-a",
    environment_digest: str | None = "env-a",
) -> ReplayRecord:
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
        state_hash=state_hash,
        environment_digest=environment_digest,
    )


def test_save_and_load_replay(tmp_path: Path) -> None:
    store = ReplayStore(tmp_path / "replays")
    record = _make_record()
    store.save(record)

    loaded = store.load("replay-1")
    assert loaded.replay_id == "replay-1"
    assert loaded.trace_id == "trace-1"
    assert loaded.state_hash == "hash-a"
    assert loaded.environment_digest == "env-a"
    assert len(loaded.approved_effects) == 1
    assert loaded.approved_effects[0].effect_id == "effect-1"
    assert len(loaded.artifacts) == 1


def test_save_and_load_replay_without_hashes(tmp_path: Path) -> None:
    store = ReplayStore(tmp_path / "replays")
    record = _make_record(state_hash=None, environment_digest=None)
    store.save(record)

    loaded = store.load("replay-1")
    assert loaded.state_hash is None
    assert loaded.environment_digest is None


def test_list_replays(tmp_path: Path) -> None:
    store = ReplayStore(tmp_path / "replays")
    assert store.list_replays() == ()

    store.save(_make_record("replay-a"))
    store.save(_make_record("replay-b"))

    listed = store.list_replays()
    assert "replay-a" in listed
    assert "replay-b" in listed


def test_load_all(tmp_path: Path) -> None:
    store = ReplayStore(tmp_path / "replays")
    store.save(_make_record("replay-a"))
    store.save(_make_record("replay-b"))

    all_records = store.load_all()
    ids = tuple(r.replay_id for r in all_records)
    assert ids == ("replay-a", "replay-b")


def test_load_nonexistent_replay_raises(tmp_path: Path) -> None:
    store = ReplayStore(tmp_path / "replays")
    with pytest.raises(PersistenceError):
        store.load("no-such-replay")


def test_malformed_replay_file_raises(tmp_path: Path) -> None:
    replay_dir = tmp_path / "replays"
    replay_dir.mkdir(parents=True)
    (replay_dir / "bad-replay.json").write_text("not json", encoding="utf-8")

    store = ReplayStore(replay_dir)
    with pytest.raises(CorruptedDataError):
        store.load("bad-replay")


def test_empty_replay_id_raises(tmp_path: Path) -> None:
    store = ReplayStore(tmp_path / "replays")
    with pytest.raises(PersistenceError):
        store.load("")
