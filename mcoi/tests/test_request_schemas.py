"""
Purpose: verify generated JSON Schema coverage for domain adapter requests.
Governance scope: request contract drift detection for external callers.
Dependencies: jsonschema, adapter registry, and export_request_schemas.
Invariants: every adapter is covered and minimal requests validate.

The tool emits a JSON Schema per adapter request shape. These tests
verify:
  - every registered adapter appears in the schema document
  - each schema is structurally well-formed (object, properties,
    required list, kind enum matching the ActionKind values)
  - ROUND-TRIP: the registry's minimal-valid request for each adapter,
    serialized to a JSON-safe dict, validates against its own schema
    under jsonschema. This is the strong guarantee: the schema
    actually describes the payloads the adapters accept.
  - the checked-in request_schemas.json is up to date with the tool.
"""
from __future__ import annotations

import dataclasses
import enum
from decimal import Decimal

import jsonschema
import pytest

from tools.export_request_schemas import (
    artifact_path,
    generate_schemas,
    render,
    schema_for_adapter,
)
from mcoi_runtime.domain_adapters._registry import ADAPTERS


_SKIP = object()


def _json_safe_value(value):
    """Coerce a request field value to JSON-safe form, mirroring how
    an external caller would serialize it. Returns ``_SKIP`` for
    field types that aren't part of the JSON payload surface (nested
    dataclass specs, UUIDs)."""
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bool):
        return value
    if isinstance(value, (str, int, float)):
        return value
    if isinstance(value, (tuple, list)):
        coerced = [_json_safe_value(v) for v in value]
        if any(c is _SKIP for c in coerced):
            return _SKIP
        return coerced
    return _SKIP


def _request_to_json_safe(request) -> dict:
    """Serialize an adapter request dataclass to a JSON-safe dict the
    way an external caller would send it. Fields whose types aren't
    part of the JSON payload surface (nested dataclasses, UUIDs) are
    omitted; those are request-internal and not in the schema."""
    out: dict = {}
    for field in dataclasses.fields(request):
        value = _json_safe_value(getattr(request, field.name))
        if value is _SKIP:
            continue
        out[field.name] = value
    return out


# ---- structure ----


def test_document_covers_every_adapter():
    doc = generate_schemas()
    schema_names = set(doc["schemas"].keys())
    registry_names = {entry.name for entry in ADAPTERS}
    assert schema_names == registry_names
    assert doc["adapter_count"] == len(ADAPTERS)


def test_each_schema_is_well_formed():
    doc = generate_schemas()
    for name, schema in doc["schemas"].items():
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema
        assert schema["additionalProperties"] is False
        # kind is always present, always an enum
        assert "kind" in schema["properties"]
        assert schema["properties"]["kind"]["type"] == "string"
        assert "enum" in schema["properties"]["kind"]


def test_kind_enum_matches_action_kind_values():
    for entry in ADAPTERS:
        schema = schema_for_adapter(entry)
        schema_enum = set(schema["properties"]["kind"]["enum"])
        actual = {k.value for k in entry.action_kind_cls}
        assert schema_enum == actual, (
            f"{entry.name}: schema kind enum {schema_enum} != "
            f"ActionKind values {actual}"
        )


def test_summary_is_required_for_every_adapter():
    for entry in ADAPTERS:
        schema = schema_for_adapter(entry)
        assert "summary" in schema["required"], (
            f"{entry.name}: summary should be required"
        )
        assert "kind" in schema["required"]


def test_schemas_are_valid_jsonschema():
    """Every generated schema must itself be a valid JSON Schema
    under the draft 2020-12 metaschema."""
    doc = generate_schemas()
    validator_cls = jsonschema.validators.validator_for(
        {"$schema": doc["$schema"]}
    )
    for name, schema in doc["schemas"].items():
        # Raises SchemaError if the schema is malformed
        validator_cls.check_schema(schema)


# ---- round-trip: minimal requests validate against their schema ----


@pytest.mark.parametrize(
    "entry", ADAPTERS, ids=lambda e: e.name,
)
def test_minimal_request_validates_against_schema(entry):
    """The registry's canonical minimal request for each adapter,
    serialized as JSON, must validate against that adapter's schema.
    This is the guarantee that the schema actually describes what the
    adapter accepts."""
    schema = schema_for_adapter(entry)
    payload = _request_to_json_safe(entry.build())
    # Raises ValidationError on mismatch
    jsonschema.validate(instance=payload, schema=schema)


@pytest.mark.parametrize(
    "entry", ADAPTERS, ids=lambda e: e.name,
)
def test_unknown_field_rejected_by_schema(entry):
    """additionalProperties=False means a typo'd field fails
    validation; the schema enforces the same strict-input policy
    the CLI does."""
    schema = schema_for_adapter(entry)
    payload = _request_to_json_safe(entry.build())
    payload["totally_made_up_field"] = "x"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=schema)


@pytest.mark.parametrize(
    "entry", ADAPTERS, ids=lambda e: e.name,
)
def test_bad_kind_rejected_by_schema(entry):
    """A kind value outside the enum fails validation."""
    schema = schema_for_adapter(entry)
    payload = _request_to_json_safe(entry.build())
    payload["kind"] = "this_is_not_a_valid_kind"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=schema)


# ---- staleness ----


def test_artifact_is_up_to_date():
    p = artifact_path()
    if not p.exists():
        pytest.skip("request_schemas.json missing; generate it first")
    on_disk = p.read_text(encoding="utf-8")
    fresh = render()
    assert on_disk == fresh, (
        "request_schemas.json is stale. Regenerate with "
        "`python -m mcoi.tools.export_request_schemas`."
    )
