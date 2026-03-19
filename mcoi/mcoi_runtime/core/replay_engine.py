"""Purpose: fail-closed replay validation over recorded artifacts only.
Governance scope: runtime-core replay boundary only.
Dependencies: runtime-core invariant helpers.
Invariants: replay never re-executes uncontrolled external effects and never invokes live adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .invariants import RuntimeCoreInvariantError, ensure_iso_timestamp, ensure_non_empty_text


class ReplayMode(StrEnum):
    OBSERVATION_ONLY = "observation_only"
    EFFECT_BEARING = "effect_bearing"


class EffectControl(StrEnum):
    CONTROLLED = "controlled"
    UNCONTROLLED_EXTERNAL = "uncontrolled_external"


class ReplayVerdict(StrEnum):
    """Classified replay validation outcome."""

    MATCH = "replay_match"
    STATE_MISMATCH = "replay_state_mismatch"
    ENVIRONMENT_MISMATCH = "replay_environment_mismatch"
    ARTIFACT_INCOMPLETE = "replay_artifact_incomplete"
    UNSUPPORTED = "replay_unsupported"
    INVALID_RECORD = "replay_invalid_record"


@dataclass(frozen=True, slots=True)
class ReplayArtifact:
    artifact_id: str
    payload_digest: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_id", ensure_non_empty_text("artifact_id", self.artifact_id))
        object.__setattr__(self, "payload_digest", ensure_non_empty_text("payload_digest", self.payload_digest))


@dataclass(frozen=True, slots=True)
class ReplayEffect:
    effect_id: str
    control: EffectControl
    artifact_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "effect_id", ensure_non_empty_text("effect_id", self.effect_id))
        if not isinstance(self.control, EffectControl):
            raise RuntimeCoreInvariantError("control must be an EffectControl value")
        if self.artifact_id is not None:
            object.__setattr__(self, "artifact_id", ensure_non_empty_text("artifact_id", self.artifact_id))


@dataclass(frozen=True, slots=True)
class ReplayRecord:
    replay_id: str
    trace_id: str
    source_hash: str
    approved_effects: tuple[ReplayEffect, ...]
    blocked_effects: tuple[ReplayEffect, ...]
    mode: ReplayMode
    recorded_at: str
    artifacts: tuple[ReplayArtifact, ...]
    state_hash: str | None = None
    environment_digest: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "replay_id", ensure_non_empty_text("replay_id", self.replay_id))
        object.__setattr__(self, "trace_id", ensure_non_empty_text("trace_id", self.trace_id))
        object.__setattr__(self, "source_hash", ensure_non_empty_text("source_hash", self.source_hash))
        if not isinstance(self.mode, ReplayMode):
            raise RuntimeCoreInvariantError("mode must be a ReplayMode value")
        object.__setattr__(self, "recorded_at", ensure_iso_timestamp("recorded_at", self.recorded_at))
        if self.state_hash is not None:
            object.__setattr__(self, "state_hash", ensure_non_empty_text("state_hash", self.state_hash))
        if self.environment_digest is not None:
            object.__setattr__(self, "environment_digest", ensure_non_empty_text("environment_digest", self.environment_digest))


@dataclass(frozen=True, slots=True)
class ReplayContext:
    """Current environment context for replay comparison."""

    state_hash: str | None = None
    environment_digest: str | None = None

    def __post_init__(self) -> None:
        if self.state_hash is not None:
            object.__setattr__(self, "state_hash", ensure_non_empty_text("state_hash", self.state_hash))
        if self.environment_digest is not None:
            object.__setattr__(self, "environment_digest", ensure_non_empty_text("environment_digest", self.environment_digest))


@dataclass(frozen=True, slots=True)
class ReplayValidationResult:
    ready: bool
    reasons: tuple[str, ...]
    artifacts: tuple[ReplayArtifact, ...]
    verdict: ReplayVerdict = ReplayVerdict.MATCH


class ReplayEngine:
    """Validate replay records without invoking any live effect path."""

    def validate(self, replay_record: ReplayRecord) -> ReplayValidationResult:
        """Validate artifact completeness and effect control. Original API preserved."""
        reasons: list[str] = []
        artifact_ids = {artifact.artifact_id for artifact in replay_record.artifacts}

        if not replay_record.artifacts:
            reasons.append("missing_artifacts")

        for effect in replay_record.approved_effects:
            if effect.control is EffectControl.UNCONTROLLED_EXTERNAL:
                reasons.append("uncontrolled_effect_reexecution")
            if effect.artifact_id is None:
                reasons.append(f"{effect.effect_id}:missing_artifact_reference")
                continue
            if effect.artifact_id not in artifact_ids:
                reasons.append(f"{effect.effect_id}:unknown_artifact_reference")

        verdict = ReplayVerdict.MATCH if not reasons else ReplayVerdict.ARTIFACT_INCOMPLETE
        return ReplayValidationResult(
            ready=not reasons,
            reasons=tuple(reasons),
            artifacts=replay_record.artifacts if not reasons else (),
            verdict=verdict,
        )

    def validate_with_context(
        self,
        replay_record: ReplayRecord,
        context: ReplayContext,
    ) -> ReplayValidationResult:
        """Full replay validation including state hash and environment fingerprint comparison.

        Checks are applied in priority order:
        1. Artifact completeness and effect control (ARTIFACT_INCOMPLETE / INVALID_RECORD)
        2. State hash comparison (STATE_MISMATCH)
        3. Environment fingerprint comparison (ENVIRONMENT_MISMATCH)

        The first failing check determines the verdict.
        """
        # Step 1: run base artifact/effect validation
        base_result = self.validate(replay_record)
        if not base_result.ready:
            return base_result

        reasons: list[str] = []

        # Step 2: state hash comparison
        if replay_record.state_hash is not None and context.state_hash is not None:
            if replay_record.state_hash != context.state_hash:
                reasons.append(
                    f"state_hash_mismatch:recorded={replay_record.state_hash},current={context.state_hash}"
                )

        # Step 3: environment fingerprint comparison
        if replay_record.environment_digest is not None and context.environment_digest is not None:
            if replay_record.environment_digest != context.environment_digest:
                reasons.append(
                    f"environment_mismatch:recorded={replay_record.environment_digest},current={context.environment_digest}"
                )

        if not reasons:
            return ReplayValidationResult(
                ready=True,
                reasons=(),
                artifacts=replay_record.artifacts,
                verdict=ReplayVerdict.MATCH,
            )

        # Classify verdict by first mismatch type
        if any(r.startswith("state_hash_mismatch") for r in reasons):
            verdict = ReplayVerdict.STATE_MISMATCH
        elif any(r.startswith("environment_mismatch") for r in reasons):
            verdict = ReplayVerdict.ENVIRONMENT_MISMATCH
        else:
            verdict = ReplayVerdict.INVALID_RECORD

        return ReplayValidationResult(
            ready=False,
            reasons=tuple(reasons),
            artifacts=(),
            verdict=verdict,
        )
