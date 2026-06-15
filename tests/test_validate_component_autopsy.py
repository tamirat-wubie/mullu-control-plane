"""Tests for Component Harness autopsy validation.

Purpose: prove component autopsy examples, runtime projections, and validation
guardrails remain non-executing and evidence-bound.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_autopsy and component autopsy runtime.
Invariants: autopsy examples match runtime, live authority is false, and
missing evidence stays explicit.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.app.component_autopsy import ComponentAutopsyError, build_component_autopsy
from scripts.validate_component_autopsy import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_autopsy,
    write_component_autopsy_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_autopsy.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def test_component_autopsy_schema_valid_and_write(tmp_path: Path) -> None:
    validation = validate_component_autopsy()
    output_path = tmp_path / "component-autopsy-validation.json"

    written_path = write_component_autopsy_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.autopsy_count == 10
    assert validation.awaiting_evidence_count >= 1
    assert written_payload["errors"] == []
    assert written_payload["ok"] is True
    assert DEFAULT_OUTPUT.name == "component_autopsy_validation.json"


def test_component_autopsy_example_matches_runtime_projection() -> None:
    example = _default_payload()
    projection = build_component_autopsy("nested_mind_bridge")

    assert example == projection
    assert example["autopsy_is_not_execution_authority"] is True
    assert example["live_execution_enabled"] is False
    assert "proof_matrix_surface" in example["missing_evidence"]
    assert "memory_topology_activation_witness" in example["missing_evidence"]
    assert example["outcome"] == "AwaitingEvidence"


def test_component_autopsy_rejects_live_authority_and_missing_evidence_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["live_execution_enabled"] = True
    payload["can_execute"] = True
    payload["missing_evidence"] = []

    validation = validate_component_autopsy(example_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "live_execution_enabled" in serialized_errors
    assert "can_execute" in serialized_errors
    assert "nested_mind_bridge missing_evidence" in serialized_errors
    assert "example does not match runtime autopsy" in serialized_errors


def test_component_autopsy_rejects_unknown_component() -> None:
    with pytest.raises(ComponentAutopsyError) as exc_info:
        build_component_autopsy("missing_component")

    assert "missing_component" in str(exc_info.value)
    assert "not registered" in str(exc_info.value)
    assert "Traceback" not in str(exc_info.value)
