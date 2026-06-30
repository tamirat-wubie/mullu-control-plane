"""Tests for Component Harness read-model validation.

Purpose: prove the read-model schema, example, and runtime projection stay
aligned with non-executing Component Harness posture.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_read_model and component read-model
fixtures.
Invariants: example matches runtime projection, live authority is false, and
drift fails closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.component_read_model import build_component_read_model
from scripts.validate_component_read_model import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_read_model,
    write_component_read_model_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_read_model.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def test_component_read_model_schema_valid(tmp_path: Path) -> None:
    validation = validate_component_read_model()
    output_path = tmp_path / "component-read-model-validation.json"

    written_path = write_component_read_model_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.bound_route_count == 35
    assert validation.route_family_classification_count == 81
    assert validation.classified_declared_route_count == 458
    assert validation.proof_bound_count == 9
    assert written_payload["errors"] == []
    assert written_payload["ok"] is True
    assert DEFAULT_OUTPUT.name == "component_read_model_validation.json"


def test_component_read_model_example_matches_runtime_projection() -> None:
    example = _default_payload()
    projection = build_component_read_model()

    assert example == projection
    assert example["read_model_is_not_execution_authority"] is True
    assert example["live_execution_enabled"] is False
    assert example["summary"]["component_count"] == 10
    assert example["summary"]["lifecycle_receipt_count"] == 10
    assert example["summary"]["route_family_classification_count"] == 81
    assert example["summary"]["classified_declared_route_count"] == 458
    assert example["components"][0]["lifecycle_receipt"]["proof_state"] == "Pass"
    assert example["components"][0]["authority_witness"]["proof_state"] == "Pass"


def test_component_read_model_rejects_live_authority_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["live_execution_enabled"] = True
    components = payload["components"]
    assert isinstance(components, list)
    first_component = components[0]
    assert isinstance(first_component, dict)
    authority = first_component["authority"]
    assert isinstance(authority, dict)
    authority["can_execute"] = True
    lifecycle_receipt = first_component["lifecycle_receipt"]
    assert isinstance(lifecycle_receipt, dict)
    lifecycle_receipt["external_effect"] = True
    authority_witness = first_component["authority_witness"]
    assert isinstance(authority_witness, dict)
    authority_witness["witness_is_not_execution_authority"] = False

    validation = validate_component_read_model(example_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "live_execution_enabled" in serialized_errors
    assert "authority.can_execute" in serialized_errors
    assert "lifecycle receipt external_effect" in serialized_errors
    assert "authority witness must not grant execution authority" in serialized_errors
    assert "example does not match runtime projection" in serialized_errors
