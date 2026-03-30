"""Purpose: deterministic JSON serialization and recursive typed deserialization.
Governance scope: persistence serialization only.
Dependencies: contracts _base (thaw_value), dataclasses, json, typing.
Invariants:
  - Round-trip invariant: serialize(deserialize(serialize(x))) == serialize(x).
  - Nested dataclasses reconstruct recursively.
  - Unsupported nested shapes fail closed.
  - No silent raw dict leakage into typed fields.
"""

from __future__ import annotations

import enum
import json
from dataclasses import fields, is_dataclass
from typing import Any, Type, TypeVar, Union, get_args, get_origin, get_type_hints

from mcoi_runtime.contracts._base import ContractRecord, freeze_value, thaw_value

from .errors import CorruptedDataError

RecordT = TypeVar("RecordT")

_MAX_DESERIALIZATION_DEPTH = 32


def serialize_record(record: Any) -> str:
    """Deterministic JSON serialization for a ContractRecord or frozen dataclass.

    Uses sorted keys, ASCII-only encoding, and compact separators to ensure
    identical output for identical input across all runs.
    """
    if (is_dataclass(record) and not isinstance(record, type)) or isinstance(record, ContractRecord):
        data = _serialize_value(record)
    else:
        raise CorruptedDataError(
            f"serialize_record requires a ContractRecord or dataclass instance, got {type(record).__name__}"
        )

    return json.dumps(data, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _serialize_value(value: Any) -> Any:
    """Recursively serialize a value to JSON-compatible form."""
    if value is None:
        return None
    if isinstance(value, enum.Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: _serialize_value(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, (tuple, list)):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    # Handle MappingProxyType and other Mapping types
    from types import MappingProxyType
    if isinstance(value, MappingProxyType):
        return {k: _serialize_value(v) for k, v in value.items()}
    return value


def deserialize_record(json_str: str, record_type: Type[RecordT]) -> RecordT:
    """Deserialize a JSON string back to a typed record with recursive reconstruction.

    Supports:
    - Flat dataclass fields (primitives, strings, booleans)
    - Nested dataclass fields (reconstructed recursively)
    - Tuples of dataclasses or primitives
    - Optional fields (None or typed value)
    - Enum fields (reconstructed from string values)
    - Mappings (passed through)

    Fails closed on unsupported or ambiguous nested shapes.
    """
    if not isinstance(json_str, str) or not json_str.strip():
        raise CorruptedDataError("json_str must be a non-empty string")

    if not is_dataclass(record_type) or not isinstance(record_type, type):
        raise CorruptedDataError(
            f"record_type must be a dataclass class, got {record_type!r}"
        )

    try:
        raw = json.loads(json_str)
    except (json.JSONDecodeError, TypeError) as exc:
        raise CorruptedDataError(f"malformed JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise CorruptedDataError(f"expected JSON object, got {type(raw).__name__}")

    try:
        return _reconstruct_dataclass(raw, record_type, depth=0)
    except CorruptedDataError:
        raise
    except (TypeError, ValueError) as exc:
        raise CorruptedDataError(
            f"failed to construct {record_type.__name__}: {exc}"
        ) from exc


def _reconstruct_dataclass(raw: dict[str, Any], dc_type: type, *, depth: int = 0) -> Any:
    """Recursively reconstruct a dataclass from a raw dict."""
    if depth > _MAX_DESERIALIZATION_DEPTH:
        raise CorruptedDataError(
            f"deserialization depth limit ({_MAX_DESERIALIZATION_DEPTH}) exceeded"
        )
    try:
        hints = get_type_hints(dc_type)
    except (TypeError, NameError, AttributeError) as exc:
        raise CorruptedDataError(
            f"cannot resolve type hints for {dc_type.__name__}: {exc}"
        ) from exc

    reconstructed: dict[str, Any] = {}
    for f in fields(dc_type):
        if f.name not in raw:
            continue  # Let the constructor handle missing fields via defaults
        value = raw[f.name]
        field_type = hints.get(f.name)
        if field_type is not None:
            reconstructed[f.name] = _reconstruct_value(value, field_type, f"field '{f.name}'", depth=depth + 1)
        else:
            reconstructed[f.name] = value

    return dc_type(**reconstructed)


def _reconstruct_value(value: Any, target_type: type, context: str, *, depth: int = 0) -> Any:
    """Reconstruct a single value to match the declared target type."""
    if depth > _MAX_DESERIALIZATION_DEPTH:
        raise CorruptedDataError(
            f"deserialization depth limit ({_MAX_DESERIALIZATION_DEPTH}) exceeded at {context}"
        )

    # Handle None
    if value is None:
        return None

    # Unwrap Optional (Union[X, None]) — extract X and reconstruct
    origin = get_origin(target_type)
    args = get_args(target_type)

    import types as _types
    if origin is Union or isinstance(target_type, _types.UnionType):
        # Filter out NoneType to find the real type
        non_none_args = [a for a in args if a is not type(None)]
        if value is None:
            return None
        if len(non_none_args) == 1:
            return _reconstruct_value(value, non_none_args[0], context, depth=depth + 1)
        # Ambiguous union — try each non-None arg, fail if none works
        for arg in non_none_args:
            try:
                return _reconstruct_value(value, arg, context, depth=depth + 1)
            except (CorruptedDataError, TypeError, ValueError):
                continue
        raise CorruptedDataError(f"cannot reconstruct {context}: ambiguous union type {target_type}")

    # Dataclass — recursive reconstruction
    if is_dataclass(target_type) and isinstance(target_type, type):
        if isinstance(value, dict):
            return _reconstruct_dataclass(value, target_type, depth=depth + 1)
        # Already the right type (shouldn't happen from JSON, but defensive)
        if is_dataclass(value) and isinstance(value, target_type):
            return value
        raise CorruptedDataError(f"cannot reconstruct {context}: expected dict for dataclass, got {type(value).__name__}")

    # Enum — reconstruct from string value
    if isinstance(target_type, type) and issubclass(target_type, enum.Enum):
        try:
            return target_type(value)
        except (ValueError, KeyError) as exc:
            raise CorruptedDataError(f"cannot reconstruct {context}: invalid enum value '{value}' for {target_type.__name__}") from exc

    # tuple — reconstruct from list
    if origin is tuple:
        if not isinstance(value, (list, tuple)):
            raise CorruptedDataError(f"cannot reconstruct {context}: expected list/tuple, got {type(value).__name__}")
        if args:
            if len(args) == 2 and args[1] is Ellipsis:
                # tuple[X, ...] — homogeneous tuple
                elem_type = args[0]
                return tuple(_reconstruct_value(v, elem_type, f"{context}[{i}]", depth=depth + 1) for i, v in enumerate(value))
            else:
                # Fixed-length tuple — tuple[X, Y, Z]
                if len(value) != len(args):
                    raise CorruptedDataError(f"cannot reconstruct {context}: expected {len(args)} elements, got {len(value)}")
                return tuple(_reconstruct_value(v, t, f"{context}[{i}]", depth=depth + 1) for i, (v, t) in enumerate(zip(value, args)))
        return tuple(value)

    # list — reconstruct elements
    if origin is list:
        if not isinstance(value, list):
            raise CorruptedDataError(f"cannot reconstruct {context}: expected list, got {type(value).__name__}")
        if args:
            elem_type = args[0]
            return [_reconstruct_value(v, elem_type, f"{context}[{i}]", depth=depth + 1) for i, v in enumerate(value)]
        return list(value)

    # dict/Mapping — reconstruct values if value type is known
    if origin is dict or (isinstance(origin, type) and issubclass(origin, dict)):
        if not isinstance(value, dict):
            raise CorruptedDataError(f"cannot reconstruct {context}: expected dict, got {type(value).__name__}")
        if args and len(args) == 2:
            _, val_type = args
            return {k: _reconstruct_value(v, val_type, f"{context}[{k}]", depth=depth + 1) for k, v in value.items()}
        return dict(value)

    # Mapping type from typing — pass through
    if origin is not None and hasattr(origin, '__mro__'):
        from collections.abc import Mapping
        if issubclass(origin, Mapping):
            return value

    # Primitives (str, int, float, bool) — pass through
    if isinstance(target_type, type) and target_type in (str, int, float, bool):
        return value

    # Any — pass through
    if target_type is Any:
        return value

    # Unknown type — pass through (defensive, let __post_init__ validate)
    return value
