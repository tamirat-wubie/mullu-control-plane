"""Purpose: canonical plan contract mapping.
Governance scope: shared plan adoption without planner reinterpretation.
Dependencies: shared plan schema and shared invariants.
Invariants: same state, registry, and goal map to the same plan input surface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_datetime_text, require_non_empty_text, require_non_empty_tuple


def _freeze_dependency_ids(dependencies: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    if isinstance(dependencies, (str, bytes)) or not isinstance(dependencies, (tuple, list)):
        raise ValueError(f"{field_name} must be an array of item ids")
    frozen = freeze_value(list(dependencies))
    for index, dependency in enumerate(frozen):
        require_non_empty_text(dependency, f"{field_name}[{index}]")
    return frozen


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
        object.__setattr__(self, "depends_on", _freeze_dependency_ids(self.depends_on, "depends_on"))


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
        item_ids: set[str] = set()
        for item in self.items:
            if not isinstance(item, PlanItem):
                raise ValueError("items must contain only PlanItem instances")
            if item.item_id in item_ids:
                raise ValueError("items must have unique item_id values")
            item_ids.add(item.item_id)
        dependency_graph = {item.item_id: item.depends_on for item in self.items}
        _validate_dependency_graph(dependency_graph)
        if self.status is not None:
            object.__setattr__(self, "status", require_non_empty_text(self.status, "status"))
        if self.created_at is not None:
            object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        if self.updated_at is not None:
            object.__setattr__(self, "updated_at", require_datetime_text(self.updated_at, "updated_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
        object.__setattr__(self, "extensions", freeze_value(self.extensions))


def _validate_dependency_graph(dependency_graph: dict[str, tuple[str, ...]]) -> None:
    visited: set[str] = set()
    visiting: set[str] = set()

    def visit(item_id: str) -> None:
        if item_id in visited:
            return
        if item_id in visiting:
            raise ValueError("depends_on must not contain dependency cycles")
        visiting.add(item_id)
        for dependency_id in dependency_graph[item_id]:
            if dependency_id == item_id:
                raise ValueError("depends_on must not reference the same item_id")
            if dependency_id not in dependency_graph:
                raise ValueError("depends_on must reference declared item_id values")
            visit(dependency_id)
        visiting.remove(item_id)
        visited.add(item_id)

    for item_id in dependency_graph:
        visit(item_id)
