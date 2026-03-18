"""Purpose: verify fail-closed replay validation for runtime-core.
Governance scope: runtime-core tests only.
Dependencies: the runtime-core replay engine module.
Invariants: replay works from recorded artifacts only and refuses uncontrolled effect re-execution.
"""

from __future__ import annotations

from mcoi_runtime.core.replay_engine import (
    EffectControl,
    ReplayArtifact,
    ReplayEffect,
    ReplayEngine,
    ReplayMode,
    ReplayRecord,
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
