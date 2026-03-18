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

    def __post_init__(self) -> None:
        object.__setattr__(self, "replay_id", ensure_non_empty_text("replay_id", self.replay_id))
        object.__setattr__(self, "trace_id", ensure_non_empty_text("trace_id", self.trace_id))
        object.__setattr__(self, "source_hash", ensure_non_empty_text("source_hash", self.source_hash))
        if not isinstance(self.mode, ReplayMode):
            raise RuntimeCoreInvariantError("mode must be a ReplayMode value")
        object.__setattr__(self, "recorded_at", ensure_iso_timestamp("recorded_at", self.recorded_at))


@dataclass(frozen=True, slots=True)
class ReplayValidationResult:
    ready: bool
    reasons: tuple[str, ...]
    artifacts: tuple[ReplayArtifact, ...]


class ReplayEngine:
    """Validate replay records without invoking any live effect path."""

    def validate(self, replay_record: ReplayRecord) -> ReplayValidationResult:
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

        return ReplayValidationResult(
            ready=not reasons,
            reasons=tuple(reasons),
            artifacts=replay_record.artifacts if not reasons else (),
        )
