"""
Purpose: export JSON Schema for every domain adapter request shape.
Governance scope: adapter payload contract publication and drift detection.
Dependencies: domain adapter registry, dataclasses, typing, and json.
Invariants: generated schemas are deterministic, strict, and registry-complete.

Each adapter's request is a dataclass with typed fields. This tool
introspects the shared registry and emits a JSON Schema (draft
2020-12) per adapter, plus a top-level object keyed by adapter name.
The artifact lets external callers - anything submitting JSON to the
adapters, e.g. a workflow engine or a future API - validate payloads
*before* sending, generate forms, or drive SDK type generation.

Field -> schema type mapping (annotations are PEP-563 strings):
  - str                 -> {"type": "string"}
  - bool                -> {"type": "boolean"}
  - int                 -> {"type": "integer"}
  - float | Decimal     -> {"type": "number"}   (JSON has no Decimal)
  - tuple[str, ...]     -> {"type": "array", "items": {"type": "string"}}
  - the ``kind`` field  -> {"type": "string", "enum": [<ActionKind values>]}

A field with no default is ``required``; a field with a default is
optional and its default is recorded in the schema.

Output: ``mullu-control-plane/request_schemas.json`` by default, or
stdout with ``--print``. ``--check`` exits non-zero if the on-disk
artifact is stale (CI mode), mirroring the constraint-matrix tool.

Run::

    python -m mcoi.tools.export_request_schemas
    python -m mcoi.tools.export_request_schemas --print
    python -m mcoi.tools.export_request_schemas --check
"""
from __future__ import annotations

import argparse
import dataclasses
import enum
import json
import sys
import typing
from decimal import Decimal
from pathlib import Path
from typing import Any

from mcoi_runtime.domain_adapters._registry import ADAPTERS, AdapterEntry


_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"


def _schema_for_type(tp: Any) -> dict[str, Any] | None:
    """Map a *resolved* Python type (from typing.get_type_hints) to a
    JSON Schema fragment. Returns None for types not part of the JSON
    payload surface (UUID auto-generated, nested dataclass specs,
    dict, etc.) - those are request-internal.

    Handles:
      - Enum subclass            -> string enum of the enum's values
      - bool                     -> boolean   (checked before int)
      - int                      -> integer
      - float | Decimal          -> number
      - str                      -> string
      - tuple[str, ...]          -> array of strings
      - tuple[<Enum>, ...]       -> array of string-enum
    """
    # Enum scalar (e.g. the `kind` field, or software_dev's `mode`)
    if isinstance(tp, type) and issubclass(tp, enum.Enum):
        return {"type": "string", "enum": [e.value for e in tp]}
    # bool is a subclass of int, so check it first.
    if tp is bool:
        return {"type": "boolean"}
    if tp is int:
        return {"type": "integer"}
    if tp is float or tp is Decimal:
        return {"type": "number"}
    if tp is str:
        return {"type": "string"}
    # tuple[X, ...]
    if typing.get_origin(tp) is tuple:
        args = typing.get_args(tp)
        if args:
            elem = args[0]
            if isinstance(elem, type) and issubclass(elem, enum.Enum):
                return {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [e.value for e in elem],
                    },
                }
            if elem is str:
                return {"type": "array", "items": {"type": "string"}}
    return None


_NO_DEFAULT = object()


def _json_safe_default(value: Any) -> Any:
    """Recursively coerce a default value to JSON-safe form: enum to
    value, tuple to list with coerced elements, Decimal to float."""
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, tuple):
        return [_json_safe_default(v) for v in value]
    if isinstance(value, list):
        return [_json_safe_default(v) for v in value]
    return value


def _default_for(field: dataclasses.Field) -> Any:
    """Return a JSON-safe default value for a field, or a sentinel
    ``_NO_DEFAULT`` if the field is required."""
    if field.default is not dataclasses.MISSING:
        value = field.default
    elif field.default_factory is not dataclasses.MISSING:  # type: ignore[misc]
        value = field.default_factory()  # type: ignore[misc]
    else:
        return _NO_DEFAULT
    return _json_safe_default(value)


def schema_for_adapter(entry: AdapterEntry) -> dict[str, Any]:
    """Build the JSON Schema object for one adapter's request shape.

    Uses ``typing.get_type_hints`` to resolve PEP-563 string
    annotations into real types, so enum, enum-tuple, and int fields
    are modeled correctly (not just the simple str/bool/tuple[str]
    shapes)."""
    properties: dict[str, Any] = {}
    required: list[str] = []

    hints = typing.get_type_hints(entry.request_cls)

    for field in dataclasses.fields(entry.request_cls):
        resolved = hints.get(field.name, None)
        prop = _schema_for_type(resolved) if resolved is not None else None
        if prop is None:
            # Field type not part of the JSON payload surface
            # (UUID auto-generated, nested dataclass spec, etc.) - skip.
            continue
        prop = dict(prop)

        if field.name == "kind":
            prop["description"] = (
                f"One of the {entry.action_kind_cls.__name__} values."
            )

        default = _default_for(field)
        if default is _NO_DEFAULT:
            required.append(field.name)
        else:
            prop["default"] = default

        properties[field.name] = prop

    return {
        "type": "object",
        "title": entry.request_cls.__name__,
        "description": (
            f"Request payload for the {entry.name} domain adapter."
        ),
        "properties": properties,
        "required": sorted(required),
        # Reject unknown fields; this matches the CLI's strict input policy.
        "additionalProperties": False,
    }


def generate_schemas() -> dict[str, Any]:
    """Return the full schema document: dialect + per-adapter schemas
    under a ``schemas`` object keyed by adapter name."""
    return {
        "$schema": _SCHEMA_DIALECT,
        "title": "Domain adapter request schemas",
        "description": (
            f"JSON Schema for the request payload of each of the "
            f"{len(ADAPTERS)} domain adapters. Generated from the shared "
            f"adapter registry by tools/export_request_schemas.py."
        ),
        "adapter_count": len(ADAPTERS),
        "schemas": {
            entry.name: schema_for_adapter(entry) for entry in ADAPTERS
        },
    }


def render() -> str:
    """Pretty-printed JSON document, stable across runs (sorted keys
    inside each schema's required list; insertion-ordered adapters)."""
    return json.dumps(generate_schemas(), indent=2, ensure_ascii=False) + "\n"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def artifact_path() -> Path:
    return repo_root() / "request_schemas.json"


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        pass

    parser = argparse.ArgumentParser(
        description="Export JSON Schema for every adapter request shape.",
    )
    parser.add_argument("--print", action="store_true",
                        help="Write to stdout instead of disk.")
    parser.add_argument("--check", action="store_true",
                        help="Exit non-zero if the on-disk artifact is stale.")
    args = parser.parse_args(argv)

    doc = render()

    if args.print:
        sys.stdout.write(doc)
        return 0

    target = artifact_path()
    if args.check:
        if not target.exists():
            sys.stderr.write(
                f"request_schemas.json missing at {target}; "
                "run without --check to generate.\n"
            )
            return 1
        if target.read_text(encoding="utf-8") != doc:
            sys.stderr.write(
                "request_schemas.json is stale. Regenerate with "
                "`python -m mcoi.tools.export_request_schemas`.\n"
            )
            return 1
        return 0

    target.write_text(doc, encoding="utf-8")
    sys.stdout.write(f"wrote {target}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
