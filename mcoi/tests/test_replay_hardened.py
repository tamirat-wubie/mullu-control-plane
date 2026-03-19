"""Purpose: verify hardened replay validation with state hash and environment comparison.
Governance scope: runtime-core replay hardening tests only.
Dependencies: replay engine module with verdict classification.
Invariants: replay of same record yields same interpretation; mismatches are explicit, never silent.
"""

from __future__ import annotations

from mcoi_runtime.core.replay_engine import (
    EffectControl,
    ReplayArtifact,
    ReplayContext,
    ReplayEffect,
    ReplayEngine,
    ReplayMode,
    ReplayRecord,
    ReplayValidationResult,
    ReplayVerdict,
)


def _make_record(
    *,
    state_hash: str | None = None,
    environment_digest: str | None = None,
) -> ReplayRecord:
    return ReplayRecord(
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
        recorded_at="2026-03-19T00:00:00+00:00",
        artifacts=(ReplayArtifact(artifact_id="artifact-1", payload_digest="digest-1"),),
        state_hash=state_hash,
        environment_digest=environment_digest,
    )


def test_validate_with_context_match() -> None:
    engine = ReplayEngine()
    record = _make_record(state_hash="hash-a", environment_digest="env-a")
    context = ReplayContext(state_hash="hash-a", environment_digest="env-a")

    result = engine.validate_with_context(record, context)
    assert result.ready is True
    assert result.verdict is ReplayVerdict.MATCH
    assert result.reasons == ()
    assert len(result.artifacts) == 1


def test_validate_with_context_state_mismatch() -> None:
    engine = ReplayEngine()
    record = _make_record(state_hash="hash-a", environment_digest="env-a")
    context = ReplayContext(state_hash="hash-b", environment_digest="env-a")

    result = engine.validate_with_context(record, context)
    assert result.ready is False
    assert result.verdict is ReplayVerdict.STATE_MISMATCH
    assert any("state_hash_mismatch" in r for r in result.reasons)


def test_validate_with_context_environment_mismatch() -> None:
    engine = ReplayEngine()
    record = _make_record(state_hash="hash-a", environment_digest="env-a")
    context = ReplayContext(state_hash="hash-a", environment_digest="env-b")

    result = engine.validate_with_context(record, context)
    assert result.ready is False
    assert result.verdict is ReplayVerdict.ENVIRONMENT_MISMATCH
    assert any("environment_mismatch" in r for r in result.reasons)


def test_validate_with_context_both_mismatches_returns_state_first() -> None:
    engine = ReplayEngine()
    record = _make_record(state_hash="hash-a", environment_digest="env-a")
    context = ReplayContext(state_hash="hash-b", environment_digest="env-b")

    result = engine.validate_with_context(record, context)
    assert result.ready is False
    assert result.verdict is ReplayVerdict.STATE_MISMATCH
    assert len(result.reasons) == 2


def test_validate_with_context_skips_comparison_when_either_is_none() -> None:
    engine = ReplayEngine()
    # Record has hashes but context does not — no comparison possible, should pass
    record = _make_record(state_hash="hash-a", environment_digest="env-a")
    context = ReplayContext()

    result = engine.validate_with_context(record, context)
    assert result.ready is True
    assert result.verdict is ReplayVerdict.MATCH


def test_validate_with_context_no_hashes_on_record() -> None:
    engine = ReplayEngine()
    record = _make_record()
    context = ReplayContext(state_hash="hash-a", environment_digest="env-a")

    result = engine.validate_with_context(record, context)
    assert result.ready is True
    assert result.verdict is ReplayVerdict.MATCH


def test_validate_with_context_fails_on_artifact_issues_first() -> None:
    engine = ReplayEngine()
    record = ReplayRecord(
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
        recorded_at="2026-03-19T00:00:00+00:00",
        artifacts=(),
        state_hash="hash-a",
        environment_digest="env-a",
    )
    context = ReplayContext(state_hash="hash-a", environment_digest="env-a")

    result = engine.validate_with_context(record, context)
    assert result.ready is False
    assert result.verdict is ReplayVerdict.ARTIFACT_INCOMPLETE


def test_verdict_enum_values() -> None:
    assert ReplayVerdict.MATCH == "replay_match"
    assert ReplayVerdict.STATE_MISMATCH == "replay_state_mismatch"
    assert ReplayVerdict.ENVIRONMENT_MISMATCH == "replay_environment_mismatch"
    assert ReplayVerdict.ARTIFACT_INCOMPLETE == "replay_artifact_incomplete"
    assert ReplayVerdict.UNSUPPORTED == "replay_unsupported"
    assert ReplayVerdict.INVALID_RECORD == "replay_invalid_record"


def test_existing_validate_still_works_with_verdict() -> None:
    """Ensure backward compatibility: original validate() returns verdict field."""
    engine = ReplayEngine()
    record = _make_record()
    result = engine.validate(record)
    assert result.ready is True
    assert result.verdict is ReplayVerdict.MATCH
