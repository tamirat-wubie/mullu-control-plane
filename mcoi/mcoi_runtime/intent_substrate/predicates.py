"""Three starter predicate kinds.

All evaluate against an entity's attribute mapping (a plain
`Mapping[str, Any]`). Missing entity / missing attribute -> False.

The application supplies the StateView callable that produces these
mappings. For mcoi this is typically a thin adapter over whichever
state-bearing engine holds the entity's current state — obligation
runtime, approval queue, workflow runtime, etc.

Add a fourth kind only when at least two real intents need it.
"""

from __future__ import annotations

import math
import operator
from dataclasses import dataclass
from numbers import Real
from typing import Any, Callable, Mapping

from mcoi_runtime.contracts.event import EventType

from .primitives import EntityId

_DEFAULT_WATCHES: tuple[EventType, ...] = (EventType.WORLD_STATE_CHANGED,)


@dataclass(frozen=True)
class EntityAttributeEq:
    """True iff state[attribute] == value.

    Use for boolean / string / enum equality. Missing state or
    attribute -> False.
    """

    entity_id: EntityId
    attribute: str
    value: Any
    watches_kinds: tuple[EventType, ...] = _DEFAULT_WATCHES

    def evaluate(self, state: "Mapping[str, Any] | None") -> bool:
        if state is None:
            return False
        if self.attribute not in state:
            return False
        return state[self.attribute] == self.value

    def watches(self) -> set[EventType]:
        return set(self.watches_kinds)


_OPS: dict[str, Callable[[Any, Any], bool]] = {
    ">":  operator.gt,
    ">=": operator.ge,
    "<":  operator.lt,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
}


@dataclass(frozen=True)
class EntityAttributeThreshold:
    """True iff `state[attribute] <op> threshold` numerically.

    Coerces observed state values via `float()`. Missing or non-numeric
    observed values -> False. Thresholds must be finite numeric values.
    For non-numeric equality use EntityAttributeEq.
    """

    entity_id: EntityId
    attribute: str
    op: str
    threshold: float
    watches_kinds: tuple[EventType, ...] = _DEFAULT_WATCHES

    def __post_init__(self) -> None:
        if self.op not in _OPS:
            raise ValueError(f"op must be one of {sorted(_OPS)}, got {self.op!r}")
        if isinstance(self.threshold, bool) or not isinstance(self.threshold, Real):
            raise ValueError("threshold must be a finite number")
        if not math.isfinite(float(self.threshold)):
            raise ValueError("threshold must be a finite number")

    def evaluate(self, state: "Mapping[str, Any] | None") -> bool:
        if state is None:
            return False
        raw = state.get(self.attribute)
        if raw is None:
            return False
        try:
            return _OPS[self.op](float(raw), float(self.threshold))
        except (TypeError, ValueError):
            return False

    def watches(self) -> set[EventType]:
        return set(self.watches_kinds)


@dataclass(frozen=True)
class EntityExists:
    """True iff the entity is present in the state view (non-None mapping)."""

    entity_id: EntityId
    watches_kinds: tuple[EventType, ...] = _DEFAULT_WATCHES

    def evaluate(self, state: "Mapping[str, Any] | None") -> bool:
        return state is not None

    def watches(self) -> set[EventType]:
        return set(self.watches_kinds)
