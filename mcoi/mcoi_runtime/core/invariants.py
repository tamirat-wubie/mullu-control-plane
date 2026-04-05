"""Purpose: shared invariant helpers for the MCOI runtime core.
Governance scope: runtime-core validation and defensive copying only.
Dependencies: Python standard library only.
Invariants: validation is explicit, deterministic, and side-effect free.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import is_dataclass
from datetime import datetime
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, Mapping, TypeVar

ValueT = TypeVar("ValueT")


class RuntimeCoreInvariantError(ValueError):
    """Raised when runtime-core input violates an explicit invariant."""


class DuplicateRuntimeIdentifierError(RuntimeCoreInvariantError):
    """Raised when a runtime-core identifier is registered more than once."""


def ensure_non_empty_text(field_name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeCoreInvariantError(f"{field_name} must be a non-empty string")
    return value


def ensure_iso_timestamp(field_name: str, value: str) -> str:
    normalized = ensure_non_empty_text(field_name, value).replace("Z", "+00:00")
    try:
        datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise RuntimeCoreInvariantError("value must be an ISO-8601 timestamp") from exc
    return value


def ensure_dataclass_instance(field_name: str, value: Any) -> Any:
    if not is_dataclass(value) or isinstance(value, type):
        raise RuntimeCoreInvariantError("value must be a dataclass instance")
    return value


def copied(value: ValueT) -> ValueT:
    return deepcopy(value)


def freeze_mapping(value: Mapping[str, ValueT]) -> Mapping[str, ValueT]:
    return MappingProxyType({key: copied(item) for key, item in value.items()})


def stable_identifier(prefix: str, payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return f"{prefix}-{sha256(encoded.encode('ascii', 'ignore')).hexdigest()[:12]}"
