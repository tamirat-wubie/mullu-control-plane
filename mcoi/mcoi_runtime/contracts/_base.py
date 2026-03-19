"""Purpose: shared contract utilities for deterministic runtime contracts.
Governance scope: contract typing and validation only.
Dependencies: Python standard library dataclasses, typing, and json.
Invariants: field ordering is stable; contracts reject silent invalid state.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import datetime
import json
from types import MappingProxyType
from typing import Any, Mapping, Sequence


FrozenValue = Any


def freeze_value(value: Any) -> FrozenValue:
    """Recursively freeze lists and dictionaries used by contract values."""
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze_value(item) for key, item in value.items()})
    if isinstance(value, tuple):
        return tuple(freeze_value(item) for item in value)
    if isinstance(value, list):
        return tuple(freeze_value(item) for item in value)
    return value


def thaw_value(value: Any) -> Any:
    """Convert frozen values back to standard Python serialization surfaces."""
    if isinstance(value, Mapping):
        return {key: thaw_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_value(item) for item in value]
    return value


def require_non_empty_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def require_datetime_text(value: str, field_name: str) -> str:
    require_non_empty_text(value, field_name)
    normalized = value.replace("Z", "+00:00")
    try:
        datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO 8601 date-time string") from exc
    return value


def require_non_empty_tuple(values: Sequence[Any], field_name: str) -> tuple[Any, ...]:
    frozen = freeze_value(list(values))
    if not isinstance(frozen, tuple) or not frozen:
        raise ValueError(f"{field_name} must contain at least one item")
    return frozen


class ContractRecord:
    """Deterministic serialization helper for frozen dataclasses."""

    def to_dict(self) -> dict[str, Any]:
        return {field.name: thaw_value(getattr(self, field.name)) for field in fields(self)}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=True, separators=(",", ":"))
