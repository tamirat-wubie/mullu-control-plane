"""Purpose: typed transition references between explicit state snapshots.
Governance scope: runtime boundary typing only.
Dependencies: state references and trace boundary semantics.
Invariants: transitions keep source, destination, and trace linkage explicit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_non_empty_text
from .state import StateCategory


@dataclass(frozen=True, slots=True)
class TransitionRecord(ContractRecord):
    transition_id: str
    from_state_id: str
    from_category: StateCategory
    to_state_id: str
    to_category: StateCategory
    trace_id: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    extensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("transition_id", "from_state_id", "to_state_id", "trace_id"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        for field_name in ("from_category", "to_category"):
            if not isinstance(getattr(self, field_name), StateCategory):
                raise ValueError("state category must be a StateCategory value")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
        object.__setattr__(self, "extensions", freeze_value(self.extensions))
