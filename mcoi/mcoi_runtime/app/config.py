"""Purpose: provide deterministic local configuration for the MCOI operator entry path.
Governance scope: operator-loop configuration loading only.
Dependencies: Python standard library dataclasses only.
Invariants: configuration loading is explicit, deterministic, and free of import-time side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


def _require_text_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)):
        raise ValueError(f"{field_name} must be a sequence of strings")
    items = tuple(value)
    if not items:
        raise ValueError(f"{field_name} must contain at least one item")
    for index, item in enumerate(items):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name}[{index}] must be a non-empty string")
    return items


@dataclass(frozen=True, slots=True)
class AppConfig:
    allowed_planning_classes: tuple[str, ...] = ("constraint",)
    enabled_executor_routes: tuple[str, ...] = ("shell_command",)
    enabled_observer_routes: tuple[str, ...] = ("filesystem", "process")
    autonomy_mode: str = "bounded_autonomous"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "allowed_planning_classes",
            _require_text_tuple(self.allowed_planning_classes, "allowed_planning_classes"),
        )
        object.__setattr__(
            self,
            "enabled_executor_routes",
            _require_text_tuple(self.enabled_executor_routes, "enabled_executor_routes"),
        )
        object.__setattr__(
            self,
            "enabled_observer_routes",
            _require_text_tuple(self.enabled_observer_routes, "enabled_observer_routes"),
        )

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any] | None = None) -> AppConfig:
        normalized = dict(values or {})
        return cls(
            allowed_planning_classes=tuple(
                normalized.get("allowed_planning_classes", ("constraint",))
            ),
            enabled_executor_routes=tuple(
                normalized.get("enabled_executor_routes", ("shell_command",))
            ),
            enabled_observer_routes=tuple(
                normalized.get("enabled_observer_routes", ("filesystem", "process"))
            ),
            autonomy_mode=str(
                normalized.get("autonomy_mode", "bounded_autonomous")
            ),
        )
