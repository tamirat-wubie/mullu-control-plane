"""Purpose: typed recovery references for reserved runtime stabilization work.
Governance scope: identifier-level runtime typing only.
Dependencies: execution and trace identifiers.
Invariants: recovery surfaces remain explicit and separate from policy logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_datetime_text, require_non_empty_text


@dataclass(frozen=True, slots=True)
class RecoveryRecord(ContractRecord):
    recovery_id: str
    execution_id: str
    trace_id: str
    recorded_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    extensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("recovery_id", "execution_id", "trace_id"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        object.__setattr__(self, "recorded_at", require_datetime_text(self.recorded_at, "recorded_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
        object.__setattr__(self, "extensions", freeze_value(self.extensions))
