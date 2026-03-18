"""Purpose: typed template references for reserved execution surfaces.
Governance scope: identifier-level MCOI runtime contract only.
Dependencies: workflow contracts and MCOI execution boundary docs.
Invariants: template references remain explicit and free of planner logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_non_empty_text


@dataclass(frozen=True, slots=True)
class TemplateReference(ContractRecord):
    template_id: str
    name: str
    version: str
    workflow_id: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    extensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("template_id", "name", "version", "workflow_id"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
        object.__setattr__(self, "extensions", freeze_value(self.extensions))
