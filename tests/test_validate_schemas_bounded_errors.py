"""Tests for schema validation bounded errors.

Purpose: prove schema validation failures preserve causal category without
reflecting raw parser text or unresolved reference payloads.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_schemas.
Invariants:
  - Malformed schema JSON reports a stable category.
  - Unresolved local refs do not echo reference segment values.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import scripts.validate_schemas as schema_validator
from scripts.validate_schemas import _validate_schema_instance, validate_json_schemas


def test_validate_json_schemas_bounds_malformed_json_detail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir()
    schema_path = schema_dir / "secret.schema.json"
    schema_path.write_text('{"secret": "secret-schema-token",', encoding="utf-8")
    monkeypatch.setattr(schema_validator, "SCHEMA_DIR", schema_dir)

    errors = validate_json_schemas()

    assert errors == ["secret.schema.json: invalid JSON"]
    assert all("secret-schema-token" not in error for error in errors)
    assert all("Expecting" not in error for error in errors)


def test_validate_schema_instance_bounds_unresolved_ref_detail() -> None:
    schema = {"$ref": "#/$defs/secret-ref-token"}
    root = {"$defs": {}}

    errors = _validate_schema_instance(schema, {}, "$", root)

    assert errors == ["$: unresolved schema ref"]
    assert all("secret-ref-token" not in error for error in errors)
