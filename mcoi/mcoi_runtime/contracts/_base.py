"""Purpose: shared contract utilities for deterministic runtime contracts.
Governance scope: contract typing and validation only.
Dependencies: Python standard library dataclasses, typing, json, and math.
Invariants: field ordering is stable; contracts reject silent invalid state.
"""

from __future__ import annotations

import enum
import math
from dataclasses import fields
from datetime import datetime
import json
from types import MappingProxyType
from typing import Any, Mapping, Sequence


FrozenValue = Any


def freeze_value(value: Any) -> FrozenValue:
    """Recursively freeze lists, dictionaries, and sets used by contract values."""
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze_value(item) for key, item in value.items()})
    if isinstance(value, tuple):
        return tuple(freeze_value(item) for item in value)
    if isinstance(value, list):
        return tuple(freeze_value(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(freeze_value(item) for item in value)
    return value


def thaw_value(value: Any) -> Any:
    """Convert frozen values back to standard Python serialization surfaces.

    Handles nested ContractRecord instances by recursively calling to_dict().
    Enum values are preserved as Enum objects (use thaw_value_json for JSON-safe output).
    """
    if hasattr(value, "to_dict") and hasattr(value, "__dataclass_fields__"):
        return value.to_dict()
    if isinstance(value, Mapping):
        return {key: thaw_value(item) for key, item in value.items()}
    if isinstance(value, frozenset):
        return sorted([thaw_value(item) for item in value], key=str)
    if isinstance(value, tuple):
        return [thaw_value(item) for item in value]
    return value


def thaw_value_json(value: Any) -> Any:
    """Convert frozen values to JSON-serializable Python objects.

    Like thaw_value, but also converts Enum instances to their .value string.
    Safe for json.dumps().
    """
    if hasattr(value, "to_json_dict") and hasattr(value, "__dataclass_fields__"):
        return value.to_json_dict()
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, Mapping):
        return {key: thaw_value_json(item) for key, item in value.items()}
    if isinstance(value, frozenset):
        return sorted([thaw_value_json(item) for item in value], key=str)
    if isinstance(value, tuple):
        return [thaw_value_json(item) for item in value]
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


# ---------------------------------------------------------------------------
# Numeric validation helpers (shared across all contract modules)
# ---------------------------------------------------------------------------


def require_unit_float(value: float, field_name: str) -> float:
    """Validate that a float is finite and within [0.0, 1.0]."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be a number")
    fval = float(value)
    if not math.isfinite(fval):
        raise ValueError(f"{field_name} must be finite")
    if not (0.0 <= fval <= 1.0):
        raise ValueError(f"{field_name} must be between 0.0 and 1.0")
    return fval


def require_non_negative_float(value: float, field_name: str) -> float:
    """Validate that a float is finite and non-negative."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be a number")
    fval = float(value)
    if not math.isfinite(fval):
        raise ValueError(f"{field_name} must be finite")
    if fval < 0.0:
        raise ValueError(f"{field_name} must be non-negative")
    return fval


def require_finite_float(value: float, field_name: str) -> float:
    """Validate that a float is finite (may be negative)."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be a number")
    fval = float(value)
    if not math.isfinite(fval):
        raise ValueError(f"{field_name} must be finite")
    return fval


def require_non_negative_int(value: int, field_name: str) -> int:
    """Validate that a value is a non-negative integer."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return value


def require_positive_int(value: int, field_name: str) -> int:
    """Validate that a value is a positive integer (>= 1)."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    if value < 1:
        raise ValueError(f"{field_name} must be >= 1")
    return value


class ContractRecord:
    """Deterministic serialization helper for frozen dataclasses."""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict preserving Enum objects (not JSON-safe)."""
        return {field.name: thaw_value(getattr(self, field.name)) for field in fields(self)}

    def to_json_dict(self) -> dict[str, Any]:
        """Convert to JSON-safe dict (Enum values converted to strings)."""
        return {field.name: thaw_value_json(getattr(self, field.name)) for field in fields(self)}

    def to_json(self) -> str:
        """Serialize to JSON string (uses to_json_dict for Enum safety)."""
        return json.dumps(self.to_json_dict(), ensure_ascii=True, separators=(",", ":"))
