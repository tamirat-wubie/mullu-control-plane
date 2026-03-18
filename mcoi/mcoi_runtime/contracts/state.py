"""Purpose: typed state references with explicit category separation.
Governance scope: runtime state capture surface only.
Dependencies: MAF kernel boundary and MCOI state capture boundary docs.
Invariants: kernel, runtime, and environment state remain explicitly separated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_datetime_text, require_non_empty_text


class StateCategory(StrEnum):
    KERNEL = "kernel"
    RUNTIME = "runtime"
    ENVIRONMENT = "environment"


@dataclass(frozen=True, slots=True)
class StateReference(ContractRecord):
    state_id: str
    category: StateCategory
    state_hash: str
    captured_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    extensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "state_id", require_non_empty_text(self.state_id, "state_id"))
        object.__setattr__(self, "state_hash", require_non_empty_text(self.state_hash, "state_hash"))
        object.__setattr__(self, "captured_at", require_datetime_text(self.captured_at, "captured_at"))
        if not isinstance(self.category, StateCategory):
            raise ValueError("category must be a StateCategory value")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
        object.__setattr__(self, "extensions", freeze_value(self.extensions))
