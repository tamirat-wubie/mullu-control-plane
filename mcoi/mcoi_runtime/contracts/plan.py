"""Purpose: canonical plan contract mapping.
Governance scope: shared plan adoption without planner reinterpretation.
Dependencies: shared plan schema and shared invariants.
Invariants: same state, registry, and goal map to the same plan input surface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_datetime_text, require_non_empty_text, require_non_empty_tuple


@dataclass(frozen=True, slots=True)
class PlanItem(ContractRecord):
    item_id: str
    description: str
    order: int | None = None
    depends_on: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "item_id", require_non_empty_text(self.item_id, "item_id"))
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))
        if self.order is not None and self.order < 0:
            raise ValueError("order must be greater than or equal to zero")
        object.__setattr__(self, "depends_on", freeze_value(list(self.depends_on)))
        for index, dependency in enumerate(self.depends_on):
            require_non_empty_text(dependency, f"depends_on[{index}]")


@dataclass(frozen=True, slots=True)
class Plan(ContractRecord):
    plan_id: str
    goal_id: str
    state_hash: str
    registry_hash: str
    items: tuple[PlanItem, ...]
    status: str | None = None
    objective: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    extensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("plan_id", "goal_id", "state_hash", "registry_hash"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        object.__setattr__(self, "items", require_non_empty_tuple(self.items, "items"))
        for idx, item in enumerate(self.items):
            if not isinstance(item, PlanItem):
                raise ValueError(f"items[{idx}] must be a PlanItem instance")
        if self.status is not None:
            object.__setattr__(self, "status", require_non_empty_text(self.status, "status"))
        if self.created_at is not None:
            object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        if self.updated_at is not None:
            object.__setattr__(self, "updated_at", require_datetime_text(self.updated_at, "updated_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
        object.__setattr__(self, "extensions", freeze_value(self.extensions))
