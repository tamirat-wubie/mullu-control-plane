"""Purpose: canonical trace entry contract mapping.
Governance scope: shared trace contract adoption.
Dependencies: trace schema and trace-replay shared docs.
Invariants: trace parent-child causality remains explicit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_datetime_text, require_non_empty_text


@dataclass(frozen=True, slots=True)
class TraceEntry(ContractRecord):
    trace_id: str
    parent_trace_id: str | None
    event_type: str
    subject_id: str
    goal_id: str
    state_hash: str
    registry_hash: str
    timestamp: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    extensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("trace_id", "event_type", "subject_id", "goal_id", "state_hash", "registry_hash"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if self.parent_trace_id is not None:
            object.__setattr__(
                self,
                "parent_trace_id",
                require_non_empty_text(self.parent_trace_id, "parent_trace_id"),
            )
        object.__setattr__(self, "timestamp", require_datetime_text(self.timestamp, "timestamp"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
        object.__setattr__(self, "extensions", freeze_value(self.extensions))
