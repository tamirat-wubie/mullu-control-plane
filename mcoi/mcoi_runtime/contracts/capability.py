"""Purpose: canonical capability descriptor contract mapping.
Governance scope: shared contract adoption without reinterpretation.
Dependencies: docs/02_shared_contracts.md and capability schema.
Invariants: required shared fields remain ordered and explicit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_non_empty_text, require_non_empty_tuple


@dataclass(frozen=True, slots=True)
class CapabilityDescriptor(ContractRecord):
    capability_id: str
    subject_id: str
    name: str
    version: str
    scope: str
    constraints: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    extensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("capability_id", "subject_id", "name", "version", "scope"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        object.__setattr__(self, "constraints", require_non_empty_tuple(self.constraints, "constraints"))
        for index, constraint in enumerate(self.constraints):
            require_non_empty_text(constraint, f"constraints[{index}]")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
        object.__setattr__(self, "extensions", freeze_value(self.extensions))
