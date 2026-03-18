"""Purpose: canonical workflow contract mapping.
Governance scope: shared workflow adoption without added execution semantics.
Dependencies: workflow schema and shared compatibility policy.
Invariants: workflow structure remains declarative and ordered.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_non_empty_text, require_non_empty_tuple


@dataclass(frozen=True, slots=True)
class WorkflowStep(ContractRecord):
    step_id: str
    name: str
    depends_on: tuple[str, ...] = ()
    description: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "step_id", require_non_empty_text(self.step_id, "step_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(self, "depends_on", freeze_value(list(self.depends_on)))
        for index, dependency in enumerate(self.depends_on):
            require_non_empty_text(dependency, f"depends_on[{index}]")


@dataclass(frozen=True, slots=True)
class Workflow(ContractRecord):
    workflow_id: str
    name: str
    description: str | None = None
    steps: tuple[WorkflowStep, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    extensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "workflow_id", require_non_empty_text(self.workflow_id, "workflow_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(self, "steps", require_non_empty_tuple(self.steps, "steps"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
        object.__setattr__(self, "extensions", freeze_value(self.extensions))
