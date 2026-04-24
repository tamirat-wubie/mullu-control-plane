"""Purpose: verify end-to-end persisted replay — store, reload, validate deterministically.
Governance scope: persisted replay integration tests only.
Dependencies: persisted_replay module, persistence stores, replay engine.
Invariants:
  - A completed run survives process death and replays deterministically.
  - Fail closed on missing or corrupted artifacts.
  - Never execute live effects.
"""

from __future__ import annotations

from pathlib import Path

from mcoi_runtime.contracts.trace import TraceEntry
from mcoi_runtime.core.persisted_replay import PersistedReplayValidator
from mcoi_runtime.core.replay_engine import (
    EffectControl,
    ReplayArtifact,
    ReplayContext,
    ReplayEffect,
    ReplayMode,
    ReplayRecord,
    ReplayVerdict,
)
from mcoi_runtime.persistence import ReplayStore, TraceStore
from mcoi_runtime.persistence.errors import PersistenceError


def _make_replay_record(
    replay_id: str = "replay-1",
    trace_id: str = "trace-1",
    state_hash: str | None = "state-abc",
    environment_digest: str | None = "env-xyz",
) -> ReplayRecord:
    return ReplayRecord(
        replay_id=replay_id,
        trace_id=trace_id,
        source_hash="source-hash-1",
        approved_effects=(
            ReplayEffect(
                effect_id="eff-1",
                control=EffectControl.CONTROLLED,
                artifact_id="art-1",
            ),
        ),
        blocked_effects=(),
        mode=ReplayMode.OBSERVATION_ONLY,
        recorded_at="2026-03-19T00:00:00+00:00",
        artifacts=(ReplayArtifact(artifact_id="art-1", payload_digest="digest-1"),),
        state_hash=state_hash,
        environment_digest=environment_digest,
    )


def _make_trace_entry(trace_id: str = "trace-1", state_hash: str = "source-hash-1") -> TraceEntry:
    return TraceEntry(
        trace_id=trace_id,
        parent_trace_id=None,
        event_type="execution",
        subject_id="subject-1",
        goal_id="goal-1",
        state_hash=state_hash,
        registry_hash="reg-hash-1",
        timestamp="2026-03-19T00:00:00+00:00",
    )


def _setup(tmp_path: Path) -> tuple[ReplayStore, TraceStore, PersistedReplayValidator]:
    replay_store = ReplayStore(tmp_path / "replays")
    trace_store = TraceStore(tmp_path / "traces")
    validator = PersistedReplayValidator(
        replay_store=replay_store,
        trace_store=trace_store,
    )
    return replay_store, trace_store, validator


# --- Core persisted replay tests ---


def test_persisted_replay_match(tmp_path: Path) -> None:
    """Store a replay record and trace, reload, validate — should match."""
    replay_store, trace_store, validator = _setup(tmp_path)

    record = _make_replay_record()
    trace = _make_trace_entry()
    replay_store.save(record)
    trace_store.append(trace)

    result = validator.validate(
        "replay-1",
        context=ReplayContext(state_hash="state-abc", environment_digest="env-xyz"),
    )

    assert result.replay_id == "replay-1"
    assert result.trace_id == "trace-1"
    assert result.validation.ready is True
    assert result.validation.verdict is ReplayVerdict.MATCH
    assert result.trace_found is True
    assert result.trace_hash_matches is True


def test_persisted_replay_state_mismatch(tmp_path: Path) -> None:
    """Stored state_hash differs from current context — should detect mismatch."""
    replay_store, trace_store, validator = _setup(tmp_path)

    replay_store.save(_make_replay_record(state_hash="state-abc"))
    trace_store.append(_make_trace_entry())

    result = validator.validate(
        "replay-1",
        context=ReplayContext(state_hash="state-DIFFERENT", environment_digest="env-xyz"),
    )

    assert result.validation.ready is False
    assert result.validation.verdict is ReplayVerdict.STATE_MISMATCH


def test_persisted_replay_environment_mismatch(tmp_path: Path) -> None:
    replay_store, trace_store, validator = _setup(tmp_path)

    replay_store.save(_make_replay_record(environment_digest="env-xyz"))
    trace_store.append(_make_trace_entry())

    result = validator.validate(
        "replay-1",
        context=ReplayContext(state_hash="state-abc", environment_digest="env-DIFFERENT"),
    )

    assert result.validation.ready is False
    assert result.validation.verdict is ReplayVerdict.ENVIRONMENT_MISMATCH


def test_persisted_replay_without_context(tmp_path: Path) -> None:
    """No context supplied — validates artifact completeness only."""
    replay_store, trace_store, validator = _setup(tmp_path)

    replay_store.save(_make_replay_record())

    result = validator.validate("replay-1")  # no context

    assert result.validation.ready is True
    assert result.validation.verdict is ReplayVerdict.MATCH
    assert result.trace_found is False  # no trace stored


def test_persisted_replay_missing_record(tmp_path: Path) -> None:
    """Replay record not in store — should fail closed."""
    _, _, validator = _setup(tmp_path)

    result = validator.validate("nonexistent-replay")

    assert result.validation.ready is False
    assert result.validation.verdict is ReplayVerdict.INVALID_RECORD
    assert any("persistence_load_failed" in r for r in result.validation.reasons)


def test_persisted_replay_load_error_is_bounded(tmp_path: Path) -> None:
    replay_store, _, validator = _setup(tmp_path)

    def _boom(_: str) -> ReplayRecord:
        raise PersistenceError("secret persistence detail")

    replay_store.load = _boom  # type: ignore[method-assign]

    result = validator.validate("replay-1")

    assert result.validation.ready is False
    assert result.validation.verdict is ReplayVerdict.INVALID_RECORD
    assert result.validation.reasons == ("persistence_load_failed:PersistenceError",)


def test_persisted_replay_corrupted_record(tmp_path: Path) -> None:
    """Corrupted replay file — should fail closed."""
    replay_store, _, validator = _setup(tmp_path)

    replay_dir = tmp_path / "replays"
    replay_dir.mkdir(parents=True, exist_ok=True)
    (replay_dir / "bad-replay.json").write_text("not json", encoding="utf-8")

    result = validator.validate("bad-replay")

    assert result.validation.ready is False
    assert result.validation.verdict is ReplayVerdict.INVALID_RECORD


def test_persisted_replay_trace_not_found_still_validates(tmp_path: Path) -> None:
    """Trace not stored but replay record is valid — validates artifacts only."""
    replay_store, _, validator = _setup(tmp_path)

    replay_store.save(_make_replay_record())

    result = validator.validate(
        "replay-1",
        context=ReplayContext(state_hash="state-abc", environment_digest="env-xyz"),
    )

    assert result.validation.ready is True
    assert result.trace_found is False
    assert result.trace_hash_matches is None
    assert result.trace_lookup_reason == "trace_lookup_failed:TraceNotFoundError"


def test_persisted_replay_trace_lookup_error_is_bounded(tmp_path: Path) -> None:
    replay_store, _, validator = _setup(tmp_path)
    replay_store.save(_make_replay_record())

    trace_dir = tmp_path / "traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    (trace_dir / "trace-1.json").write_text("not json", encoding="utf-8")

    result = validator.validate(
        "replay-1",
        context=ReplayContext(state_hash="state-abc", environment_digest="env-xyz"),
    )

    assert result.validation.ready is True
    assert result.trace_found is False
    assert result.trace_hash_matches is None
    assert result.trace_lookup_reason == "trace_lookup_failed:CorruptedDataError"
    assert "not json" not in result.trace_lookup_reason


def test_persisted_replay_trace_hash_mismatch(tmp_path: Path) -> None:
    """Trace exists but its state_hash doesn't match replay source_hash."""
    replay_store, trace_store, validator = _setup(tmp_path)

    replay_store.save(_make_replay_record())
    trace_store.append(_make_trace_entry(state_hash="DIFFERENT-source-hash"))

    result = validator.validate("replay-1")

    assert result.trace_found is True
    assert result.trace_hash_matches is False


def test_persisted_replay_artifact_incomplete(tmp_path: Path) -> None:
    """Replay record with uncontrolled effects — should detect artifact issue."""
    replay_store, _, validator = _setup(tmp_path)

    bad_record = ReplayRecord(
        replay_id="replay-bad",
        trace_id="trace-1",
        source_hash="source-1",
        approved_effects=(
            ReplayEffect(
                effect_id="eff-1",
                control=EffectControl.UNCONTROLLED_EXTERNAL,
                artifact_id=None,
            ),
        ),
        blocked_effects=(),
        mode=ReplayMode.EFFECT_BEARING,
        recorded_at="2026-03-19T00:00:00+00:00",
        artifacts=(),
    )
    replay_store.save(bad_record)

    result = validator.validate("replay-bad")

    assert result.validation.ready is False
    assert result.validation.verdict is ReplayVerdict.ARTIFACT_INCOMPLETE


def test_validate_all(tmp_path: Path) -> None:
    """Validate all persisted replays at once."""
    replay_store, trace_store, validator = _setup(tmp_path)

    replay_store.save(_make_replay_record("replay-a"))
    replay_store.save(_make_replay_record("replay-b"))
    trace_store.append(_make_trace_entry())

    results = validator.validate_all(
        context=ReplayContext(state_hash="state-abc", environment_digest="env-xyz"),
    )

    assert len(results) == 2
    assert all(r.validation.ready for r in results)
    assert all(r.validation.verdict is ReplayVerdict.MATCH for r in results)


def test_validate_all_empty(tmp_path: Path) -> None:
    """No persisted replays — returns empty tuple."""
    _, _, validator = _setup(tmp_path)
    assert validator.validate_all() == ()


def test_persisted_replay_survives_simulated_process_restart(tmp_path: Path) -> None:
    """Simulate process death: create stores, save, destroy validator,
    create new stores from same paths, validate — must still match."""
    replay_path = tmp_path / "replays"
    trace_path = tmp_path / "traces"

    # Process 1: save artifacts
    store1 = ReplayStore(replay_path)
    trace1 = TraceStore(trace_path)
    store1.save(_make_replay_record())
    trace1.append(_make_trace_entry())

    # "Process death" — discard all in-memory state
    del store1, trace1

    # Process 2: new stores from same disk paths
    store2 = ReplayStore(replay_path)
    trace2 = TraceStore(trace_path)
    validator2 = PersistedReplayValidator(
        replay_store=store2,
        trace_store=trace2,
    )

    result = validator2.validate(
        "replay-1",
        context=ReplayContext(state_hash="state-abc", environment_digest="env-xyz"),
    )

    assert result.validation.ready is True
    assert result.validation.verdict is ReplayVerdict.MATCH
    assert result.trace_found is True
    assert result.trace_hash_matches is True
