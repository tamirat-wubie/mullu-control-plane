"""Purpose: canonical replay record contract mapping.
Governance scope: shared replay adoption without new replay semantics.
Dependencies: replay schema and trace-replay shared docs.
Invariants: replay records remain explicit, complete, and deterministic in shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_datetime_text, require_non_empty_text


class ReplayMode(StrEnum):
    OBSERVATION_ONLY = "observation_only"
    EFFECT_BEARING = "effect_bearing"


@dataclass(frozen=True, slots=True)
class ReplayEffect(ContractRecord):
    effect_id: str
    description: str | None = None
    details: Any = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "effect_id", require_non_empty_text(self.effect_id, "effect_id"))
        if self.description is not None:
            object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))
        object.__setattr__(self, "details", freeze_value(self.details))


@dataclass(frozen=True, slots=True)
class ReplayRecord(ContractRecord):
    replay_id: str
    trace_id: str
    source_hash: str
    approved_effects: tuple[ReplayEffect, ...]
    blocked_effects: tuple[ReplayEffect, ...]
    mode: ReplayMode
    recorded_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    extensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("replay_id", "trace_id", "source_hash"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        object.__setattr__(self, "approved_effects", freeze_value(list(self.approved_effects)))
        object.__setattr__(self, "blocked_effects", freeze_value(list(self.blocked_effects)))
        if not isinstance(self.mode, ReplayMode):
            raise ValueError("mode must be a ReplayMode value")
        object.__setattr__(self, "recorded_at", require_datetime_text(self.recorded_at, "recorded_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
        object.__setattr__(self, "extensions", freeze_value(self.extensions))
