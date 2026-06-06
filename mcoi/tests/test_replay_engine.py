"""Purpose: verify fail-closed replay validation for runtime-core.
Governance scope: runtime-core tests only.
Dependencies: the runtime-core replay engine module.
Invariants: replay works from recorded artifacts only and refuses uncontrolled effect re-execution.
"""

from __future__ import annotations

from mcoi_runtime.core.replay_engine import (
    EffectControl,
    ReplayContext,
    ReplayArtifact,
    ReplayEffect,
    ReplayEngine,
    ReplayMode,
    ReplayRecord,
    ReplayVerdict,
)


def test_replay_engine_accepts_complete_recorded_artifact_sets() -> None:
    engine = ReplayEngine()
    result = engine.validate(
        ReplayRecord(
            replay_id="replay-1",
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
            recorded_at="2026-03-18T12:00:00+00:00",
            artifacts=(ReplayArtifact(artifact_id="artifact-1", payload_digest="digest-1"),),
        )
    )

    assert result.ready is True
    assert result.reasons == ()
    assert result.artifacts[0].artifact_id == "artifact-1"


def test_replay_engine_rejects_uncontrolled_or_incomplete_replay_records() -> None:
    engine = ReplayEngine()
    result = engine.validate(
        ReplayRecord(
            replay_id="replay-1",
            trace_id="trace-1",
            source_hash="source-1",
            approved_effects=(
                ReplayEffect(
                    effect_id="effect-1",
                    control=EffectControl.UNCONTROLLED_EXTERNAL,
                    artifact_id=None,
                ),
            ),
            blocked_effects=(),
            mode=ReplayMode.EFFECT_BEARING,
            recorded_at="2026-03-18T12:00:00+00:00",
            artifacts=(),
        )
    )

    assert result.ready is False
    assert "missing_artifacts" in result.reasons
    assert "uncontrolled_effect_reexecution" in result.reasons
    assert result.artifacts == ()


def test_replay_engine_rejects_duplicate_artifact_ids() -> None:
    engine = ReplayEngine()
    record = ReplayRecord(
        replay_id="replay-duplicate-artifact",
        trace_id="trace-1",
        source_hash="source-hash",
        approved_effects=(
            ReplayEffect(
                effect_id="effect-1",
                control=EffectControl.CONTROLLED,
                artifact_id="artifact-1",
            ),
        ),
        blocked_effects=(),
        mode=ReplayMode.OBSERVATION_ONLY,
        recorded_at="2026-05-17T12:00:00+00:00",
        artifacts=(
            ReplayArtifact(artifact_id="artifact-1", payload_digest="digest-a"),
            ReplayArtifact(artifact_id="artifact-1", payload_digest="digest-b"),
        ),
    )

    result = engine.validate(record)

    assert result.ready is False
    assert result.verdict is ReplayVerdict.ARTIFACT_INCOMPLETE
    assert "duplicate_artifact_id" in result.reasons
    assert not any("artifact-1" in reason for reason in result.reasons)
    assert result.artifacts == ()


def test_replay_engine_blocks_missing_state_context_when_record_declares_state() -> None:
    engine = ReplayEngine()
    record = ReplayRecord(
        replay_id="replay-state-context",
        trace_id="trace-state",
        source_hash="source-state",
        approved_effects=(
            ReplayEffect(
                effect_id="effect-state",
                control=EffectControl.CONTROLLED,
                artifact_id="artifact-state",
            ),
        ),
        blocked_effects=(),
        mode=ReplayMode.OBSERVATION_ONLY,
        recorded_at="2026-05-29T12:00:00+00:00",
        artifacts=(ReplayArtifact(artifact_id="artifact-state", payload_digest="digest-state"),),
        state_hash="recorded-state",
    )

    result = engine.validate_with_context(record, ReplayContext())

    assert result.ready is False
    assert result.verdict is ReplayVerdict.STATE_MISMATCH
    assert result.reasons == ("state_hash_missing_current_context",)
    assert result.artifacts == ()


def test_replay_engine_blocks_missing_environment_context_when_record_declares_environment() -> None:
    engine = ReplayEngine()
    record = ReplayRecord(
        replay_id="replay-env-context",
        trace_id="trace-env",
        source_hash="source-env",
        approved_effects=(
            ReplayEffect(
                effect_id="effect-env",
                control=EffectControl.CONTROLLED,
                artifact_id="artifact-env",
            ),
        ),
        blocked_effects=(),
        mode=ReplayMode.OBSERVATION_ONLY,
        recorded_at="2026-05-29T12:00:00+00:00",
        artifacts=(ReplayArtifact(artifact_id="artifact-env", payload_digest="digest-env"),),
        environment_digest="recorded-env",
    )

    result = engine.validate_with_context(record, ReplayContext())

    assert result.ready is False
    assert result.verdict is ReplayVerdict.ENVIRONMENT_MISMATCH
    assert result.reasons == ("environment_missing_current_context",)
    assert result.artifacts == ()


def test_replay_engine_accepts_matching_state_and_environment_context() -> None:
    engine = ReplayEngine()
    record = ReplayRecord(
        replay_id="replay-context-match",
        trace_id="trace-context",
        source_hash="source-context",
        approved_effects=(
            ReplayEffect(
                effect_id="effect-context",
                control=EffectControl.CONTROLLED,
                artifact_id="artifact-context",
            ),
        ),
        blocked_effects=(),
        mode=ReplayMode.OBSERVATION_ONLY,
        recorded_at="2026-05-29T12:00:00+00:00",
        artifacts=(ReplayArtifact(artifact_id="artifact-context", payload_digest="digest-context"),),
        state_hash="state-context",
        environment_digest="env-context",
    )

    result = engine.validate_with_context(
        record,
        ReplayContext(
            state_hash="state-context",
            environment_digest="env-context",
        ),
    )

    assert result.ready is True
    assert result.verdict is ReplayVerdict.MATCH
    assert result.reasons == ()
    assert result.artifacts == record.artifacts
